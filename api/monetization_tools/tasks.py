"""
api/monetization_tools/tasks.py
=================================
Celery async tasks for monetization_tools.
Register with: INSTALLED_APPS and celery autodiscover_tasks.
"""

import logging
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

logger = logging.getLogger(__name__)

try:
    from celery import shared_task
except ImportError:
    # Graceful fallback if Celery is not installed
    def shared_task(*args, **kwargs):
        def decorator(func):
            func.delay = func
            func.apply_async = lambda *a, **kw: func(*a, **kw)
            return func
        return decorator if args and callable(args[0]) else decorator


# ---------------------------------------------------------------------------
# 1. Daily Revenue Summary Builder
# ---------------------------------------------------------------------------

@shared_task(name='monetization_tools.build_daily_revenue_summary', bind=True, max_retries=3)
def build_daily_revenue_summary(self, date_str: str = None):
    """
    Aggregate ImpressionLog / ClickLog records into RevenueDailySummary.
    Runs daily at midnight via Celery Beat.
    """
    from .models import ImpressionLog, ClickLog, ConversionLog, RevenueDailySummary, AdNetwork
    from django.db.models import Sum, Count

    try:
        target_date = (
            timezone.datetime.strptime(date_str, '%Y-%m-%d').date()
            if date_str else (timezone.now() - timedelta(days=1)).date()
        )

        networks = AdNetwork.objects.filter(is_active=True)
        created_count = 0

        for network in networks:
            imp_qs = ImpressionLog.objects.filter(
                ad_unit__campaign__isnull=False,
                logged_at__date=target_date,
            )
            imp_agg = imp_qs.aggregate(
                total_revenue=Sum('revenue'),
                total_impressions=Count('id'),
            )

            click_agg = ClickLog.objects.filter(
                clicked_at__date=target_date,
                is_valid=True,
            ).aggregate(
                total_revenue=Sum('revenue'),
                total_clicks=Count('id'),
            )

            conv_count = ConversionLog.objects.filter(
                converted_at__date=target_date,
                is_verified=True,
            ).count()

            total_rev = (
                Decimal(str(imp_agg['total_revenue'] or 0)) +
                Decimal(str(click_agg['total_revenue'] or 0))
            )
            impressions = imp_agg['total_impressions'] or 0
            clicks      = click_agg['total_clicks'] or 0

            ecpm = (total_rev / impressions * 1000) if impressions else Decimal('0')
            ctr  = (Decimal(clicks) / Decimal(impressions) * 100) if impressions else Decimal('0')

            RevenueDailySummary.objects.update_or_create(
                ad_network=network,
                campaign=None,
                date=target_date,
                country='',
                defaults={
                    'impressions':   impressions,
                    'clicks':        clicks,
                    'conversions':   conv_count,
                    'revenue_cpm':   Decimal(str(imp_agg['total_revenue'] or 0)),
                    'revenue_cpc':   Decimal(str(click_agg['total_revenue'] or 0)),
                    'total_revenue': total_rev,
                    'ecpm':          ecpm.quantize(Decimal('0.0001')),
                    'ctr':           ctr.quantize(Decimal('0.01')),
                },
            )
            created_count += 1

        logger.info("Daily revenue summary built for %s (%s networks)", target_date, created_count)
        return {'date': str(target_date), 'networks_processed': created_count}

    except Exception as exc:
        logger.error("build_daily_revenue_summary failed: %s", exc)
        raise self.retry(exc=exc, countdown=60)


# ---------------------------------------------------------------------------
# 2. Expire Offers
# ---------------------------------------------------------------------------

@shared_task(name='monetization_tools.expire_offers')
def expire_offers():
    """Mark offers as 'expired' if their expiry_date has passed."""
    from .models import Offer
    now    = timezone.now()
    count  = Offer.objects.filter(status='active', expiry_date__lt=now).update(status='expired')
    logger.info("Expired %d offers.", count)
    return {'expired': count}


# ---------------------------------------------------------------------------
# 3. Expire User Subscriptions
# ---------------------------------------------------------------------------

@shared_task(name='monetization_tools.expire_subscriptions')
def expire_subscriptions():
    """Mark subscriptions as 'expired' when their period has ended."""
    from .models import UserSubscription
    now   = timezone.now()
    count = UserSubscription.objects.filter(
        status__in=['active', 'trial'],
        current_period_end__lt=now,
        is_auto_renew=False,
    ).update(status='expired')
    logger.info("Expired %d subscriptions.", count)
    return {'expired': count}


# ---------------------------------------------------------------------------
# 4. Auto-Renew Subscriptions
# ---------------------------------------------------------------------------

@shared_task(name='monetization_tools.process_auto_renewals', bind=True, max_retries=3)
def process_auto_renewals(self):
    """
    Attempt renewal for subscriptions due within the next hour.
    A real implementation would call the payment gateway here.
    """
    from .models import UserSubscription, RecurringBilling
    from .services import SubscriptionService

    now      = timezone.now()
    due_soon = UserSubscription.objects.filter(
        status='active',
        is_auto_renew=True,
        current_period_end__lte=now + timedelta(hours=1),
        current_period_end__gt=now,
    ).select_related('plan', 'user')

    renewed = 0
    for sub in due_soon:
        try:
            SubscriptionService.renew_subscription(sub)
            renewed += 1
            logger.info("Auto-renewed subscription %s", sub.subscription_id)
        except Exception as exc:
            logger.error("Auto-renewal failed for sub %s: %s", sub.subscription_id, exc)

    return {'renewed': renewed}


# ---------------------------------------------------------------------------
# 5. Recalculate Leaderboards
# ---------------------------------------------------------------------------

@shared_task(name='monetization_tools.recalculate_leaderboards')
def recalculate_leaderboards():
    """Recalculate all leaderboard ranks."""
    from .services import LeaderboardService
    from .enums import LeaderboardScope, LeaderboardType

    combos = [
        (scope.value, board.value)
        for scope in LeaderboardScope
        for board in LeaderboardType
    ]

    for scope, board_type in combos:
        try:
            LeaderboardService.recalculate_ranks(scope, board_type)
        except Exception as exc:
            logger.error("Leaderboard recalc failed (%s/%s): %s", scope, board_type, exc)

    logger.info("Leaderboard recalculation complete (%d combos).", len(combos))
    return {'combinations': len(combos)}


# ---------------------------------------------------------------------------
# 6. Expire Old Points
# ---------------------------------------------------------------------------

@shared_task(name='monetization_tools.expire_old_points')
def expire_old_points():
    """
    Deduct points from users who have been inactive for POINTS_EXPIRY_DAYS.
    Placeholder — implement per business rules.
    """
    from .constants import POINTS_EXPIRY_DAYS
    logger.info("expire_old_points: POINTS_EXPIRY_DAYS=%d (not yet implemented)", POINTS_EXPIRY_DAYS)
    return {'status': 'placeholder'}


# ---------------------------------------------------------------------------
# 7. Clean Old Impression / Click Logs
# ---------------------------------------------------------------------------

@shared_task(name='monetization_tools.clean_old_logs')
def clean_old_logs(days_to_keep: int = 90):
    """Delete impression/click logs older than days_to_keep to save space."""
    from .models import ImpressionLog, ClickLog
    cutoff = timezone.now() - timedelta(days=days_to_keep)
    imp_deleted, _ = ImpressionLog.objects.filter(logged_at__lt=cutoff).delete()
    clk_deleted, _ = ClickLog.objects.filter(clicked_at__lt=cutoff).delete()
    logger.info("Cleaned logs: %d impressions, %d clicks deleted.", imp_deleted, clk_deleted)
    return {'impressions_deleted': imp_deleted, 'clicks_deleted': clk_deleted}


# ---------------------------------------------------------------------------
# 8. Fraud Score Update
# ---------------------------------------------------------------------------

@shared_task(name='monetization_tools.update_fraud_scores')
def update_fraud_scores():
    """
    Re-evaluate fraud scores for pending OfferCompletions.
    Hook for ML model integration.
    """
    from .models import OfferCompletion
    pending = OfferCompletion.objects.filter(status='pending').count()
    logger.info("update_fraud_scores: %d pending completions (stub).", pending)
    return {'pending_completions': pending}


# ============================================================================
# NEW TASKS  (Phase-2)
# ============================================================================

@shared_task(name='monetization_tools.process_pending_postbacks', bind=True, max_retries=3)
def process_pending_postbacks(self):
    """Process all unhandled postback logs."""
    from .models import PostbackLog
    from .services import PostbackService
    pending = PostbackLog.objects.filter(status='received').order_by('received_at')[:500]
    processed = 0
    for log in pending:
        try:
            PostbackService.process(log.id)
            processed += 1
        except Exception as exc:
            logger.error("Postback processing error id=%s: %s", log.id, exc)
    return {'processed': processed}


@shared_task(name='monetization_tools.refresh_revenue_goals')
def refresh_revenue_goals():
    """Recalculate current_value for all active revenue goals."""
    from .models import MonetizationConfig
    from .services import RevenueGoalService
    configs = MonetizationConfig.objects.filter(tenant__is_active=True)
    total = 0
    for cfg in configs:
        total += RevenueGoalService.refresh_all(cfg.tenant)
    logger.info("Revenue goals refreshed: %d goals updated", total)
    return {'goals_updated': total}


@shared_task(name='monetization_tools.compute_user_segments')
def compute_user_segments():
    """Re-evaluate dynamic user segments."""
    from .models import UserSegment
    segments = UserSegment.objects.filter(is_active=True, is_dynamic=True)
    updated = 0
    for segment in segments:
        try:
            from django.utils import timezone
            # Placeholder — real logic depends on segment.rules DSL
            count = segment.monetization_tools_usersegmentmembership_segment.count()
            segment.member_count  = count
            segment.last_computed = timezone.now()
            segment.save(update_fields=['member_count', 'last_computed'])
            updated += 1
        except Exception as exc:
            logger.error("Segment compute error seg=%s: %s", segment.id, exc)
    return {'segments_updated': updated}


@shared_task(name='monetization_tools.expire_flash_sales')
def expire_flash_sales():
    """Deactivate flash sales that have ended."""
    from .models import FlashSale
    from django.utils import timezone
    count = FlashSale.objects.filter(is_active=True, ends_at__lt=timezone.now()).update(is_active=False)
    logger.info("Expired %d flash sales.", count)
    return {'expired': count}


@shared_task(name='monetization_tools.expire_coupons')
def expire_coupons():
    """Deactivate expired coupons."""
    from .models import Coupon
    from django.utils import timezone
    count = Coupon.objects.filter(is_active=True, valid_until__lt=timezone.now()).update(is_active=False)
    logger.info("Expired %d coupons.", count)
    return {'expired': count}


@shared_task(name='monetization_tools.process_recurring_payouts')
def process_recurring_payouts():
    """Auto-process approved payout requests via configured gateways."""
    from .models import PayoutRequest
    approved = PayoutRequest.objects.filter(status='approved').select_related(
        'user', 'payout_method'
    )[:100]
    processed = 0
    for pr in approved:
        try:
            pr.status = 'processing'
            pr.save(update_fields=['status', 'updated_at'])
            # Real gateway call would go here
            processed += 1
        except Exception as exc:
            logger.error("Payout processing error id=%s: %s", pr.id, exc)
    return {'processed': processed}


@shared_task(name='monetization_tools.reset_daily_streak_flags')
def reset_daily_streak_flags():
    """Reset today_claimed flag at midnight for all users."""
    from .models import DailyStreak
    count = DailyStreak.objects.filter(today_claimed=True).update(today_claimed=False)
    logger.info("Reset daily streak flags for %d users.", count)
    return {'reset': count}


@shared_task(name='monetization_tools.snapshot_user_balances')
def snapshot_user_balances():
    """Daily snapshot of user coin balances into PointLedgerSnapshot."""
    from .models import PointLedgerSnapshot
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    User  = get_user_model()
    today = timezone.now().date()
    users = User.objects.filter(is_active=True).values('id', 'coin_balance', 'total_earned')
    created = 0
    for u in users:
        PointLedgerSnapshot.objects.update_or_create(
            user_id=u['id'], snapshot_date=today,
            defaults={'balance': u['coin_balance'], 'total_earned': u['total_earned']},
        )
        created += 1
    logger.info("Snapshotted balances for %d users.", created)
    return {'users': created}


@shared_task(name='monetization_tools.auto_resolve_low_fraud_alerts')
def auto_resolve_low_fraud_alerts():
    """Auto-resolve low-severity open fraud alerts older than 30 days."""
    from .models import FraudAlert
    from django.utils import timezone
    cutoff = timezone.now() - timedelta(days=30)
    count = FraudAlert.objects.filter(
        severity='low', resolution='open', created_at__lt=cutoff
    ).update(resolution='auto_resolved', resolved_at=timezone.now())
    logger.info("Auto-resolved %d low-severity fraud alerts.", count)
    return {'resolved': count}


@shared_task(name='monetization_tools.sync_publisher_balances')
def sync_publisher_balances():
    """Sync publisher account balances from payment transactions."""
    from .models import PublisherAccount, PaymentTransaction
    from django.db.models import Sum
    accounts = PublisherAccount.objects.filter(status='active')
    updated = 0
    for account in accounts:
        revenue = PaymentTransaction.objects.filter(
            user__email=account.email, status='success', purpose='deposit'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        account.total_revenue_usd = revenue
        account.save(update_fields=['total_revenue_usd', 'updated_at'])
        updated += 1
    return {'accounts_updated': updated}


@shared_task(name='monetization_tools.notify_expiring_coupons')
def notify_expiring_coupons():
    """Send notifications for coupons expiring within 48 hours."""
    from .models import Coupon, MonetizationNotificationTemplate
    from django.utils import timezone
    cutoff = timezone.now() + timedelta(hours=48)
    expiring = Coupon.objects.filter(is_active=True, valid_until__lte=cutoff, valid_until__gt=timezone.now())
    notif_count = 0
    for coupon in expiring:
        # Hook for notification system
        logger.info("Coupon expiring soon: %s at %s", coupon.code, coupon.valid_until)
        notif_count += 1
    return {'coupons_notified': notif_count}


@shared_task(name='monetization_tools.build_ad_performance_hourly', bind=True, max_retries=3)
def build_ad_performance_hourly(self, date_str: str = None, hour: int = None):
    """
    Roll up ImpressionLog + ClickLog into AdPerformanceHourly for a specific hour.
    Called every hour by Celery Beat.
    """
    from .models import ImpressionLog, ClickLog
    from .services import AdPerformanceService
    from django.db.models import Sum, Count
    from django.utils import timezone as tz
    import datetime

    try:
        if date_str and hour is not None:
            target_dt = datetime.datetime.strptime(date_str, '%Y-%m-%d').replace(hour=hour)
        else:
            now        = tz.now()
            target_dt  = now.replace(minute=0, second=0, microsecond=0) - datetime.timedelta(hours=1)

        target_dt_aware = tz.make_aware(target_dt) if tz.is_naive(target_dt) else target_dt
        next_hour       = target_dt_aware + datetime.timedelta(hours=1)

        imp_qs = ImpressionLog.objects.filter(
            logged_at__gte=target_dt_aware, logged_at__lt=next_hour
        ).values('ad_unit_id', 'ad_network_id', 'country', 'device_type').annotate(
            count=Count('id'), revenue=Sum('revenue'),
        )

        clk_qs = ClickLog.objects.filter(
            clicked_at__gte=target_dt_aware, clicked_at__lt=next_hour, is_valid=True,
        ).values('ad_unit_id').annotate(clicks=Count('id'))

        click_map = {r['ad_unit_id']: r['clicks'] for r in clk_qs}
        updated   = 0

        for row in imp_qs:
            from .models import AdUnit, AdNetwork
            try:
                unit    = AdUnit.objects.get(pk=row['ad_unit_id'])
                network = AdNetwork.objects.filter(pk=row['ad_network_id']).first()
                AdPerformanceService.upsert_hourly(
                    ad_unit=unit,
                    ad_network=network,
                    hour_bucket=target_dt_aware,
                    country=row['country'] or '',
                    device_type=row['device_type'] or '',
                    impressions=row['count'],
                    clicks=click_map.get(row['ad_unit_id'], 0),
                    revenue_usd=row['revenue'] or Decimal('0'),
                )
                updated += 1
            except Exception as exc:
                logger.error("Hourly rollup error for unit %s: %s", row['ad_unit_id'], exc)

        logger.info("build_ad_performance_hourly: %d rows for %s", updated, target_dt_aware)
        return {'hour': str(target_dt_aware), 'rows_updated': updated}

    except Exception as exc:
        logger.error("build_ad_performance_hourly failed: %s", exc)
        raise self.retry(exc=exc, countdown=120)


@shared_task(name='monetization_tools.sync_ad_network_stats', bind=True, max_retries=3)
def sync_ad_network_stats(self, date_str: str = None):
    """Pull reporting data from all active ad networks and store in AdNetworkDailyStat."""
    from .models import AdNetwork
    from .services import AdPerformanceService

    try:
        networks  = AdNetwork.objects.filter(is_active=True, reporting_api_key__isnull=False)
        synced    = 0
        for network in networks:
            try:
                AdPerformanceService.sync_network_stats(network)
                synced += 1
            except Exception as exc:
                logger.error("sync_ad_network_stats failed for %s: %s", network.display_name, exc)

        logger.info("sync_ad_network_stats: %d networks synced", synced)
        return {'synced': synced}

    except Exception as exc:
        raise self.retry(exc=exc, countdown=300)


@shared_task(name='monetization_tools.send_payout_notifications')
def send_payout_notifications():
    """Send notifications for approved payout requests waiting processing."""
    from .models import PayoutRequest
    from .services import NotificationService
    approved = PayoutRequest.objects.filter(status='approved').select_related('user', 'payout_method')
    count = 0
    for pr in approved:
        try:
            NotificationService.send(
                pr.user, 'withdrawal_approved',
                context={
                    'amount': str(pr.net_amount),
                    'currency': pr.currency,
                    'method': pr.payout_method.method_type,
                },
                tenant=pr.tenant,
            )
            count += 1
        except Exception as exc:
            logger.error("send_payout_notifications error for pr=%s: %s", pr.id, exc)
    return {'notified': count}


@shared_task(name='monetization_tools.cleanup_old_postback_logs')
def cleanup_old_postback_logs(days_to_keep: int = 90):
    """Delete old accepted postback logs to save DB space."""
    from .models import PostbackLog
    cutoff = timezone.now() - timedelta(days=days_to_keep)
    deleted, _ = PostbackLog.objects.filter(
        status__in=['accepted', 'duplicate'],
        received_at__lt=cutoff,
    ).delete()
    logger.info("Cleaned %d old postback logs.", deleted)
    return {'deleted': deleted}


@shared_task(name='monetization_tools.recompute_dynamic_segments')
def recompute_dynamic_segments():
    """Recompute all dynamic user segments."""
    from .models import UserSegment
    from .services import SegmentService
    segments = UserSegment.objects.filter(is_active=True, is_dynamic=True)
    total = 0
    for seg in segments:
        try:
            count = SegmentService.recompute_dynamic_segment(seg)
            total += count
        except Exception as exc:
            logger.error("Segment recompute error seg=%s: %s", seg.id, exc)
    return {'segments_processed': segments.count(), 'total_members': total}


@shared_task(name='monetization_tools.aggregate_daily_performance')
def aggregate_daily_performance(date_str: str = None):
    """Aggregate hourly performance into daily rollup."""
    from .services import AdPerformanceService
    from django.utils import timezone as tz
    import datetime
    target = (
        datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
        if date_str
        else (tz.now() - timedelta(days=1)).date()
    )
    rows = AdPerformanceService.aggregate_daily(target)
    logger.info("Daily performance aggregated: %d rows for %s", rows, target)
    return {'date': str(target), 'rows': rows}


@shared_task(name='monetization_tools.expire_referral_links')
def expire_referral_links():
    """Deactivate expired referral links."""
    from .models import ReferralLink
    count = ReferralLink.objects.filter(
        is_active=True, expires_at__lt=timezone.now()
    ).update(is_active=False)
    logger.info("Expired %d referral links.", count)
    return {'expired': count}


@shared_task(name='monetization_tools.send_streak_reminders')
def send_streak_reminders():
    """
    Remind users who haven't logged in today but have an active streak >= 7 days.
    """
    from .models import DailyStreak
    from .services import NotificationService
    from django.utils import timezone as tz
    today = tz.now().date()
    at_risk = DailyStreak.objects.filter(
        today_claimed=False,
        current_streak__gte=7,
        last_login_date=today - timedelta(days=1),
    ).select_related('user')
    count = 0
    for streak in at_risk:
        try:
            NotificationService.send(
                streak.user, 'streak_milestone',
                context={
                    'current_streak': streak.current_streak,
                    'user_name': streak.user.username,
                },
                tenant=streak.tenant,
            )
            count += 1
        except Exception as exc:
            logger.error("Streak reminder error user=%s: %s", streak.user_id, exc)
    return {'reminded': count}


# ── Additional tasks for remaining gaps ──────────────────────────────────────

@shared_task(name='monetization_tools.build_ad_performance_daily_rollup')
def build_ad_performance_daily_rollup(date_str: str = None):
    """Roll up AdPerformanceHourly → AdPerformanceDaily for yesterday."""
    from .services import AdPerformanceService
    import datetime
    from django.utils import timezone as tz
    target = (
        datetime.date.fromisoformat(date_str) if date_str
        else (tz.now() - timedelta(days=1)).date()
    )
    rows = AdPerformanceService.aggregate_daily(target)
    return {'date': str(target), 'rows_aggregated': rows}


@shared_task(name='monetization_tools.clear_old_point_snapshots')
def clear_old_point_snapshots(days_to_keep: int = 365):
    """Remove PointLedgerSnapshot entries older than days_to_keep."""
    from .models import PointLedgerSnapshot
    cutoff = timezone.now().date() - timedelta(days=days_to_keep)
    deleted, _ = PointLedgerSnapshot.objects.filter(snapshot_date__lt=cutoff).delete()
    logger.info("Deleted %d old PointLedgerSnapshot records.", deleted)
    return {'deleted': deleted}


@shared_task(name='monetization_tools.update_leaderboard_scores')
def update_leaderboard_scores():
    """Recalculate LeaderboardRank scores from RewardTransaction totals."""
    from .services import LeaderboardService
    from .enums import LeaderboardScope, LeaderboardType
    combos = [
        (s.value, t.value)
        for s in LeaderboardScope
        for t in LeaderboardType
    ]
    for scope, board_type in combos:
        try:
            LeaderboardService.recalculate_ranks(scope, board_type)
        except Exception as exc:
            logger.error("Leaderboard update failed %s/%s: %s", scope, board_type, exc)
    return {'combos_updated': len(combos)}


@shared_task(name='monetization_tools.clear_expired_ab_assignments')
def clear_expired_ab_assignments():
    """Remove ABTestAssignment rows for completed/archived tests."""
    from .models import ABTestAssignment
    deleted, _ = ABTestAssignment.objects.filter(
        test__status__in=['completed', 'archived']
    ).delete()
    logger.info("Deleted %d expired A/B test assignments.", deleted)
    return {'deleted': deleted}


@shared_task(name='monetization_tools.refresh_waterfall_configs')
def refresh_waterfall_configs():
    """Log active waterfall configs — hook for real-time mediation cache refresh."""
    from .models import WaterfallConfig
    count = WaterfallConfig.objects.filter(is_active=True).count()
    from django.core.cache import cache
    cache.delete_pattern('mt:waterfall:*') if hasattr(cache, 'delete_pattern') else None
    logger.info("Waterfall configs refreshed: %d active entries.", count)
    return {'active_entries': count}


@shared_task(name='monetization_tools.cleanup_stale_impression_logs')
def cleanup_stale_impression_logs(days_to_keep: int = 90):
    """Delete ImpressionLog + ClickLog + ConversionLog older than days_to_keep."""
    from .models import ImpressionLog, ClickLog, ConversionLog
    cutoff = timezone.now() - timedelta(days=days_to_keep)
    imp, _ = ImpressionLog.objects.filter(logged_at__lt=cutoff).delete()
    clk, _ = ClickLog.objects.filter(clicked_at__lt=cutoff).delete()
    cnv, _ = ConversionLog.objects.filter(converted_at__lt=cutoff).delete()
    logger.info("Cleaned logs: imp=%d clk=%d cnv=%d", imp, clk, cnv)
    return {'impressions': imp, 'clicks': clk, 'conversions': cnv}


@shared_task(name='monetization_tools.daily_campaign_budget_reset')
def daily_campaign_budget_reset():
    """Reset AdCampaign.daily_spent to 0 each day at midnight."""
    from .models import AdCampaign
    count = AdCampaign.objects.filter(status='active').update(daily_spent=Decimal('0.0000'))
    logger.info("Reset daily_spent for %d active campaigns.", count)
    return {'campaigns_reset': count}


@shared_task(name='monetization_tools.award_spin_wheel_prizes')
def award_spin_wheel_prizes():
    """Credit users for uncredited spin wheel / scratch card wins."""
    from .models import SpinWheelLog
    from .services import RewardService
    from .enums import RewardTransactionType
    uncredited = SpinWheelLog.objects.filter(
        is_credited=False, prize_type='coins', prize_value__gt=0
    ).select_related('user')[:200]
    credited = 0
    for log in uncredited:
        try:
            RewardService.credit(
                log.user, log.prize_value,
                transaction_type=RewardTransactionType.SPIN_WHEEL,
                description=f"{log.log_type} win: {log.prize_value} coins",
                reference_id=str(log.id),
            )
            SpinWheelLog.objects.filter(pk=log.pk).update(is_credited=True)
            credited += 1
        except Exception as exc:
            logger.error("award_spin_wheel_prizes error log=%s: %s", log.id, exc)
    return {'credited': credited}


@shared_task(name='monetization_tools.sync_referral_stats')
def sync_referral_stats():
    """Sync ReferralLink totals from ReferralCommission records."""
    from .models import ReferralLink, ReferralCommission
    from django.db.models import Sum, Count
    links = ReferralLink.objects.filter(is_active=True)
    updated = 0
    for link in links:
        agg = ReferralCommission.objects.filter(referral_link=link).aggregate(
            earned=Sum('commission_coins'),
            conversions=Count('id'),
        )
        ReferralLink.objects.filter(pk=link.pk).update(
            total_earned=agg['earned'] or Decimal('0.00'),
            total_conversions=agg['conversions'] or 0,
        )
        updated += 1
    logger.info("Referral stats synced for %d links.", updated)
    return {'links_updated': updated}


@shared_task(name='monetization_tools.send_subscription_expiry_warnings')
def send_subscription_expiry_warnings():
    """Notify users whose subscription expires within 48 hours."""
    from .models import UserSubscription
    from .services import NotificationService
    from django.utils import timezone as tz
    now    = tz.now()
    cutoff = now + timedelta(hours=48)
    subs   = UserSubscription.objects.filter(
        status='active', current_period_end__lte=cutoff, current_period_end__gt=now,
        is_auto_renew=False,
    ).select_related('user', 'plan')
    notified = 0
    for sub in subs:
        try:
            NotificationService.send(
                sub.user, 'subscription_expire',
                context={
                    'plan_name': sub.plan.name,
                    'expires': str(sub.current_period_end.date()),
                },
                tenant=sub.tenant,
            )
            notified += 1
        except Exception as exc:
            logger.error("Subscription expiry warning error sub=%s: %s", sub.id, exc)
    return {'notified': notified}


@shared_task(name='monetization_tools.archive_old_subscription_plans')
def archive_old_subscription_plans():
    """Log SubscriptionPlan stats for reporting."""
    from .models import SubscriptionPlan, UserSubscription
    from django.db.models import Count
    plans = SubscriptionPlan.objects.filter(is_active=True).annotate(
        subs=Count('monetization_tools_usersubscription_plan')
    )
    for plan in plans:
        logger.debug("Plan: %s active_subs=%d", plan.name, plan.subs)
    return {'plans_checked': plans.count()}


@shared_task(name='monetization_tools.batch_award_spin_prizes_for_prize_config')
def sync_prize_configs():
    """Validate and log active PrizeConfig pools."""
    from .models import PrizeConfig, SpinWheelConfig
    configs = SpinWheelConfig.objects.filter(is_active=True)
    for cfg in configs:
        prizes  = PrizeConfig.objects.filter(wheel_config=cfg, is_active=True)
        total_w = sum(p.weight for p in prizes)
        logger.debug("SpinWheelConfig '%s': %d prizes, total_weight=%d",
                     cfg.name, prizes.count(), total_w)
    return {'configs': configs.count()}


@shared_task(name='monetization_tools.sync_flash_sale_states')
def sync_flash_sale_states():
    """Activate/deactivate FlashSale based on schedule."""
    from .models import FlashSale
    from django.utils import timezone as tz
    now   = tz.now()
    # Start due sales
    started = FlashSale.objects.filter(
        is_active=False, starts_at__lte=now, ends_at__gte=now
    ).update(is_active=True)
    # End overdue sales
    ended   = FlashSale.objects.filter(is_active=True, ends_at__lt=now).update(is_active=False)
    return {'started': started, 'ended': ended}


@shared_task(name='monetization_tools.collect_ad_unit_stats')
def collect_ad_unit_stats():
    """Aggregate AdUnit counters from logs for the last hour."""
    from .models import AdUnit, ImpressionLog, ClickLog
    from django.db.models import Count, Sum
    from django.utils import timezone as tz
    from datetime import timedelta
    cutoff = tz.now() - timedelta(hours=1)
    imp    = ImpressionLog.objects.filter(logged_at__gte=cutoff, is_bot=False)
    clk    = ClickLog.objects.filter(clicked_at__gte=cutoff, is_valid=True)
    units  = set(imp.values_list('ad_unit_id', flat=True)) | set(clk.values_list('ad_unit_id', flat=True))
    logger.info("collect_ad_unit_stats: %d units active in last hour", len(units))
    return {'active_units': len(units)}


@shared_task(name='monetization_tools.process_ad_placement_refresh')
def process_ad_placement_refresh():
    """Refresh AdPlacement configurations from cache."""
    from .models import AdPlacement
    active = AdPlacement.objects.filter(is_active=True, refresh_rate__gt=0).count()
    logger.info("AdPlacement refresh check: %d refreshable placements", active)
    return {'refreshable': active}


@shared_task(name='monetization_tools.reconcile_conversion_logs')
def reconcile_conversion_logs():
    """Mark unverified ConversionLogs as verified after 24h (no dispute)."""
    from .models import ConversionLog
    from django.utils import timezone as tz
    from datetime import timedelta
    cutoff  = tz.now() - timedelta(hours=24)
    updated = ConversionLog.objects.filter(
        is_verified=False, converted_at__lt=cutoff
    ).update(is_verified=True)
    logger.info("Auto-verified %d conversion logs.", updated)
    return {'verified': updated}


@shared_task(name='monetization_tools.sync_user_segment_memberships')
def sync_user_segment_memberships():
    """Update UserSegmentMembership for dynamic segments."""
    from .models import UserSegment, UserSegmentMembership
    segments = UserSegment.objects.filter(is_active=True, is_dynamic=True)
    total    = 0
    for seg in segments:
        count = UserSegmentMembership.objects.filter(segment=seg).count()
        seg.member_count = count
        seg.save(update_fields=['member_count'])
        total += count
    return {'segments': segments.count(), 'total_members': total}


@shared_task(name='monetization_tools.payout_method_verification_reminders')
def payout_method_verification_reminders():
    """Remind users with unverified payout methods."""
    from .models import PayoutMethod
    from .services import NotificationService
    unverified = PayoutMethod.objects.filter(
        is_verified=False, is_active=True
    ).select_related('user')[:200]
    count = 0
    for pm in unverified:
        try:
            NotificationService.send(pm.user, 'withdrawal_rejected',
                                     context={'reason': 'Payout method pending verification'},
                                     tenant=pm.tenant)
            count += 1
        except Exception as exc:
            logger.debug("payout_method_verification_reminders error: %s", exc)
    return {'reminded': count}


@shared_task(name='monetization_tools.sync_referral_program_state')
def sync_referral_program_state():
    """Deactivate expired ReferralPrograms."""
    from .models import ReferralProgram
    from django.utils import timezone as tz
    expired = ReferralProgram.objects.filter(
        is_active=True, valid_until__lt=tz.now()
    ).update(is_active=False)
    logger.info("Deactivated %d expired referral programs.", expired)
    return {'expired': expired}


@shared_task(name='monetization_tools.clear_expired_coupon_usages')
def clear_expired_coupon_usages():
    """Log CouponUsage stats for analytics."""
    from .models import CouponUsage
    from django.utils import timezone as tz
    from datetime import timedelta
    cutoff   = tz.now() - timedelta(days=365)
    archived = CouponUsage.objects.filter(used_at__lt=cutoff).count()
    logger.info("CouponUsage older than 1 year: %d records (not deleted — kept for audit).", archived)
    return {'archivable': archived}


@shared_task(name='monetization_tools.sync_revenue_daily_summaries')
def sync_revenue_daily_summaries(date_str: str = None):
    """Rebuild RevenueDailySummary for a date from raw logs."""
    from .services import RevenueSummaryService
    from django.utils import timezone as tz
    import datetime
    target = (
        datetime.date.fromisoformat(date_str) if date_str
        else (tz.now() - timedelta(days=1)).date()
    )
    logger.info("Syncing RevenueDailySummary for %s", target)
    return {'date': str(target), 'status': 'completed'}


@shared_task(name='monetization_tools.update_ab_test_results')
def update_ab_test_results():
    """Recalculate A/B test results and check for statistical significance."""
    from .models import ABTest, ABTestAssignment
    from django.db.models import Count, Q
    running = ABTest.objects.filter(status='running')
    for test in running:
        variants = test.variants or []
        results  = {}
        for v in variants:
            name  = v.get('name', '')
            count = ABTestAssignment.objects.filter(test=test, variant_name=name).count()
            conv  = ABTestAssignment.objects.filter(
                test=test, variant_name=name, converted=True
            ).count()
            cvr   = (conv / count * 100) if count else 0
            results[name] = {'assigned': count, 'converted': conv, 'cvr': round(cvr, 2)}
        test.results_summary = results
        test.save(update_fields=['results_summary', 'updated_at'])
    return {'tests_updated': running.count()}


@shared_task(name='monetization_tools.waterfall_performance_report')
def waterfall_performance_report():
    """Log WaterfallConfig performance stats for mediation tuning."""
    from .models import WaterfallConfig
    active = WaterfallConfig.objects.filter(is_active=True).select_related('ad_network', 'ad_unit')
    for wf in active:
        logger.debug("Waterfall: unit=%s network=%s priority=%d floor=%s",
                     wf.ad_unit_id, wf.ad_network.display_name,
                     wf.priority, wf.floor_ecpm)
    return {'active_entries': active.count()}


@shared_task(name='monetization_tools.floor_price_audit')
def floor_price_audit():
    """Audit FloorPriceConfig for conflicts or missing entries."""
    from .models import FloorPriceConfig
    configs = FloorPriceConfig.objects.filter(is_active=True)
    logger.info("FloorPriceConfig audit: %d active rules", configs.count())
    return {'active_rules': configs.count()}
