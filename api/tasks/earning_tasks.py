"""
tasks/earning_tasks.py
Earning-related Celery tasks:
  - calculate_daily_user_earnings   — aggregate & credit daily task earnings
  - sync_ad_network_revenue         — pull revenue from ad network APIs
  - distribute_bonus_rewards        — distribute daily/weekly bonus pools
  - recalculate_leaderboard         — refresh top-earners leaderboard
  - process_streak_rewards          — credit streak completion bonuses
  - expire_unclaimed_rewards        — expire rewards not claimed within window
"""
import logging
from decimal import Decimal
from celery import shared_task
from django.utils import timezone
from django.db import transaction
from django.core.cache import cache

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60,
             name='tasks.earning_tasks.calculate_daily_user_earnings')
def calculate_daily_user_earnings(self, date_str: str = None) -> dict:
    """
    Aggregate all UserTaskCompletion records for the day,
    compute totals per user, and update wallet + analytics.
    """
    try:
        from datetime import datetime, timedelta
        from django.db.models import Sum, Count
        from django.contrib.auth import get_user_model

        target_date = (
            datetime.strptime(date_str, '%Y-%m-%d').date()
            if date_str
            else (timezone.now() - timedelta(days=1)).date()
        )
        logger.info(f"[MONEY] Calculating daily earnings for {target_date}...")

        User      = get_user_model()
        processed = 0
        errors    = 0

        try:
            from api.tasks.models import UserTaskCompletion

            day_start = timezone.make_aware(
                datetime.combine(target_date, datetime.min.time())
            )
            day_end = day_start + timedelta(days=1)

            # Per-user daily totals
            user_totals = (
                UserTaskCompletion.objects.filter(
                    completed_at__gte=day_start,
                    completed_at__lt=day_end,
                    status='completed',
                )
                .values('user_id')
                .annotate(
                    total_earned=Sum('reward_amount'),
                    completion_count=Count('id'),
                )
            )

            for row in user_totals:
                try:
                    with transaction.atomic():
                        # Update user stats cache
                        cache.set(
                            f'user_daily_earnings_{row["user_id"]}_{target_date}',
                            {
                                'total': str(row['total_earned'] or Decimal('0')),
                                'count': row['completion_count'],
                                'date': str(target_date),
                            },
                            timeout=86400 * 7,
                        )
                        processed += 1
                except Exception as row_err:
                    logger.error(f"[ERROR] Earnings for user {row['user_id']}: {row_err}")
                    errors += 1

            # Platform totals
            platform_total = UserTaskCompletion.objects.filter(
                completed_at__gte=day_start,
                completed_at__lt=day_end,
                status='completed',
            ).aggregate(
                total=Sum('reward_amount'),
                count=Count('id'),
            )

            cache.set(f'platform_daily_earnings_{target_date}', {
                'total': str(platform_total['total'] or Decimal('0')),
                'completions': platform_total['count'] or 0,
                'users': processed,
            }, timeout=86400 * 7)

        except ImportError as e:
            logger.warning(f"[WARN] Models not available: {e}")

        result = {
            'status': 'success',
            'message': 'Daily earnings calculated',
            'timestamp': timezone.now().isoformat(),
            'date': str(target_date),
            'users_processed': processed,
            'errors': errors,
        }
        logger.info(f"[OK] Daily earnings done: {processed} users")
        return result

    except Exception as e:
        logger.error(f"[ERROR] calculate_daily_user_earnings: {e}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=120,
             name='tasks.earning_tasks.sync_ad_network_revenue')
def sync_ad_network_revenue(self, network_ids: list = None) -> dict:
    """
    Pull revenue data from ad network APIs (AdMob, Meta Audience, etc.)
    and update platform-side revenue records.
    """
    try:
        logger.info("[LOADING] Syncing ad network revenue...")
        synced  = 0
        errors  = 0
        revenue = Decimal('0')

        try:
            from ad_networks.models import AdNetwork, AdNetworkRevenue
            from ad_networks.services import AdNetworkAPIClient

            networks = AdNetwork.objects.filter(is_active=True)
            if network_ids:
                networks = networks.filter(id__in=network_ids)

            for network in networks:
                try:
                    client = AdNetworkAPIClient(network)
                    data   = client.fetch_revenue()
                    rev    = Decimal(str(data.get('revenue', 0)))

                    AdNetworkRevenue.objects.create(
                        network=network,
                        revenue=rev,
                        impressions=data.get('impressions', 0),
                        clicks=data.get('clicks', 0),
                        period_start=data.get('period_start'),
                        period_end=data.get('period_end'),
                        raw_data=data,
                    )
                    revenue += rev
                    synced  += 1

                except Exception as net_err:
                    logger.error(f"[ERROR] Network {network.name}: {net_err}")
                    errors += 1

        except ImportError as e:
            logger.warning(f"[WARN] Ad network models not available: {e}")

        result = {
            'status': 'success',
            'message': 'Ad network revenue sync completed',
            'timestamp': timezone.now().isoformat(),
            'networks_synced': synced,
            'errors': errors,
            'revenue_synced': str(revenue),
        }
        logger.info(f"[OK] Revenue sync done: {synced} networks, ${revenue} revenue")
        return result

    except Exception as e:
        logger.error(f"[ERROR] sync_ad_network_revenue: {e}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=2, default_retry_delay=60,
             name='tasks.earning_tasks.distribute_bonus_rewards')
def distribute_bonus_rewards(self, bonus_type: str = 'daily', pool_amount: Decimal = None) -> dict:
    """
    Distribute bonus reward pool to top-earning users.
    bonus_type: 'daily' | 'weekly' | 'referral_milestone'
    Top 10 users by completions share the pool proportionally.
    """
    try:
        from datetime import timedelta
        from django.db.models import Sum, Count
        logger.info(f"🎁 Distributing {bonus_type} bonus rewards...")

        if pool_amount is None:
            from django.conf import settings
            pool_amount = Decimal(str(getattr(settings, f'BONUS_POOL_{bonus_type.upper()}', '50')))

        distributed = 0
        recipients  = []

        try:
            from api.tasks.models import UserTaskCompletion
            from api.tasks.services import WalletService

            # Last 24h for daily, 7d for weekly
            hours  = 24 if bonus_type == 'daily' else 168
            cutoff = timezone.now() - timedelta(hours=hours)

            top_users = (
                UserTaskCompletion.objects.filter(
                    completed_at__gte=cutoff, status='completed'
                )
                .values('user_id')
                .annotate(
                    total_earned=Sum('reward_amount'),
                    completions=Count('id'),
                )
                .order_by('-total_earned')[:10]
            )

            top_list = list(top_users)
            if not top_list:
                return {'status': 'skipped', 'reason': 'no_qualifying_users'}

            total_earned = sum(float(u['total_earned'] or 0) for u in top_list)
            if total_earned == 0:
                return {'status': 'skipped', 'reason': 'zero_earnings'}

            ws = WalletService()
            for user_data in top_list:
                share_pct = float(user_data['total_earned'] or 0) / total_earned
                bonus     = pool_amount * Decimal(str(share_pct))
                if bonus < Decimal('0.01'):
                    continue

                ws.credit(
                    user_id=user_data['user_id'],
                    amount=bonus,
                    transaction_type='bonus_reward',
                    reference=f'bonus_{bonus_type}_{timezone.now().strftime("%Y%m%d")}',
                    metadata={'bonus_type': bonus_type, 'share_pct': share_pct},
                )
                recipients.append({'user_id': user_data['user_id'], 'bonus': str(bonus)})
                distributed += 1

        except ImportError as e:
            logger.warning(f"[WARN] Models not available: {e}")

        result = {
            'status': 'success',
            'bonus_type': bonus_type,
            'pool_amount': str(pool_amount),
            'distributed_to': distributed,
            'recipients': recipients,
            'timestamp': timezone.now().isoformat(),
        }
        logger.info(f"[OK] Bonus distribution done: ${pool_amount} to {distributed} users")
        return result

    except Exception as e:
        logger.error(f"[ERROR] distribute_bonus_rewards: {e}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=2, default_retry_delay=30,
             name='tasks.earning_tasks.recalculate_leaderboard')
def recalculate_leaderboard(self, period: str = 'daily', limit: int = 100) -> dict:
    """
    Recalculate top-earners leaderboard for the given period.
    Caches results for fast API retrieval.
    """
    try:
        from datetime import timedelta
        from django.db.models import Sum, Count
        logger.info(f"🏆 Recalculating {period} leaderboard...")

        hours_map = {'daily': 24, 'weekly': 168, 'monthly': 720, 'alltime': 0}
        hours     = hours_map.get(period, 24)
        leaders   = []

        try:
            from api.tasks.models import UserTaskCompletion

            qs = UserTaskCompletion.objects.filter(status='completed')
            if hours > 0:
                qs = qs.filter(completed_at__gte=timezone.now() - timedelta(hours=hours))

            leaders_qs = (
                qs
                .values('user_id', 'user__username')
                .annotate(
                    total_earned=Sum('reward_amount'),
                    completions=Count('id'),
                )
                .order_by('-total_earned')[:limit]
            )

            leaders = [
                {
                    'rank': i + 1,
                    'user_id': row['user_id'],
                    'username': row['user__username'],
                    'total_earned': str(row['total_earned'] or Decimal('0')),
                    'completions': row['completions'],
                }
                for i, row in enumerate(leaders_qs)
            ]

            cache.set(f'leaderboard_{period}', leaders, timeout=1800)

        except ImportError as e:
            logger.warning(f"[WARN] Models not available: {e}")

        result = {
            'status': 'success',
            'period': period,
            'entries': len(leaders),
            'timestamp': timezone.now().isoformat(),
        }
        logger.info(f"[OK] Leaderboard recalculated: {len(leaders)} entries")
        return result

    except Exception as e:
        logger.error(f"[ERROR] recalculate_leaderboard: {e}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=2, default_retry_delay=30,
             name='tasks.earning_tasks.process_streak_rewards')
def process_streak_rewards(self) -> dict:
    """
    Credit streak completion bonuses.
    Checks users with consecutive daily completion streaks (3d, 7d, 30d)
    and credits bonus amounts.
    """
    try:
        from datetime import timedelta, date
        from django.db.models import Count
        logger.info("🔥 Processing streak rewards...")

        STREAK_BONUSES = {3: Decimal('1.00'), 7: Decimal('3.00'), 30: Decimal('15.00')}
        credited = 0

        try:
            from api.tasks.models import UserTaskCompletion
            from api.tasks.services import WalletService

            ws      = WalletService()
            today   = timezone.now().date()
            user_ids = (
                UserTaskCompletion.objects.filter(status='completed')
                .values_list('user_id', flat=True)
                .distinct()
            )

            for uid in user_ids:
                streak = _calculate_streak(uid, today)
                if streak in STREAK_BONUSES:
                    bonus = STREAK_BONUSES[streak]
                    # Avoid double-crediting same streak same day
                    dedup_key = f'streak_reward_{uid}_{today}_{streak}'
                    if not cache.get(dedup_key):
                        ws.credit(
                            user_id=uid,
                            amount=bonus,
                            transaction_type='streak_bonus',
                            reference=f'streak_{streak}d_{today}',
                            metadata={'streak_days': streak, 'date': str(today)},
                        )
                        cache.set(dedup_key, 1, timeout=86400)
                        credited += 1

        except ImportError as e:
            logger.warning(f"[WARN] Models not available: {e}")

        result = {
            'status': 'success',
            'credited': credited,
            'timestamp': timezone.now().isoformat(),
        }
        logger.info(f"[OK] Streak rewards processed: {credited} credited")
        return result

    except Exception as e:
        logger.error(f"[ERROR] process_streak_rewards: {e}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=2, default_retry_delay=60,
             name='tasks.earning_tasks.expire_unclaimed_rewards')
def expire_unclaimed_rewards(self, expiry_days: int = 90) -> dict:
    """
    Expire reward records that have not been claimed within expiry_days.
    """
    try:
        from datetime import timedelta
        logger.info(f"⏰ Expiring unclaimed rewards (>{expiry_days} days)...")
        expired = 0
        cutoff  = timezone.now() - timedelta(days=expiry_days)

        try:
            from rewards.models import PendingReward
            expired = PendingReward.objects.filter(
                status='pending',
                created_at__lt=cutoff,
            ).update(status='expired', expired_at=timezone.now())
        except ImportError as e:
            logger.warning(f"[WARN] PendingReward model not available: {e}")

        result = {
            'status': 'success',
            'expired': expired,
            'expiry_days': expiry_days,
            'timestamp': timezone.now().isoformat(),
        }
        logger.info(f"[OK] Expired {expired} unclaimed rewards")
        return result

    except Exception as e:
        logger.error(f"[ERROR] expire_unclaimed_rewards: {e}")
        raise self.retry(exc=e)


# ── Private helpers ────────────────────────────────────────────────────────

def _calculate_streak(user_id: int, today) -> int:
    """Calculate consecutive daily completion streak for a user."""
    try:
        from api.tasks.models import UserTaskCompletion
        from datetime import timedelta

        streak = 0
        check_date = today
        for _ in range(100):  # max streak check
            has_completion = UserTaskCompletion.objects.filter(
                user_id=user_id,
                status='completed',
                completed_at__date=check_date,
            ).exists()
            if has_completion:
                streak += 1
                check_date -= timedelta(days=1)
            else:
                break
        return streak
    except Exception:
        return 0
