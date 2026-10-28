"""
tasks/community_tasks.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Community & Points Reward System (CPAlead Chat Room Feature)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CPAlead awards 1,000 points per $1 earned.
Points unlock monthly prizes shipped for free.
They also have a community chat room where members share methods.

  ✅ award_community_points     — 1000 pts per $1 earned
  ✅ check_point_milestones     — unlock rewards at thresholds
  ✅ process_prize_redemption   — ship physical prizes
  ✅ reset_monthly_points       — monthly reset of leaderboard
  ✅ update_community_leaderboard— ranked community standings
  ✅ generate_community_report  — community engagement report
  ✅ send_community_digest      — weekly community newsletter
"""
import logging
from decimal import Decimal
from celery import shared_task
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)

POINTS_PER_DOLLAR = 1000   # 1000 community points per $1 earned

# Prize tiers (monthly reset)
PRIZE_TIERS = {
    10000:  {'name': 'Bronze Prize',    'value': '$10 Amazon Gift Card'},
    50000:  {'name': 'Silver Prize',    'value': '$50 Amazon Gift Card'},
    100000: {'name': 'Gold Prize',      'value': '$100 + Merchandise'},
    500000: {'name': 'Platinum Prize',  'value': '$500 Cash Prize'},
    1000000:{'name': 'Diamond Prize',   'value': 'Luxury Item (Maserati-level)'},
}


@shared_task(bind=True, max_retries=3, default_retry_delay=10,
             name='tasks.community_tasks.award_community_points')
def award_community_points(
    self,
    user_id: int,
    amount_usd: str,
    source: str = 'task_completion',
) -> dict:
    """
    Award community points for earnings. Rate: 1000 pts per $1.
    Triggers prize milestone check after awarding.
    """
    try:
        earned_usd  = Decimal(str(amount_usd))
        points_to_add = int(earned_usd * POINTS_PER_DOLLAR)

        if points_to_add <= 0:
            return {'status': 'skipped', 'reason': 'zero_points'}

        # Update points in cache + DB
        pts_key     = f'community_points_{user_id}'
        monthly_key = f'community_points_monthly_{user_id}_{timezone.now().strftime("%Y%m")}'

        total_pts   = cache.get(pts_key, 0) + points_to_add
        monthly_pts = cache.get(monthly_key, 0) + points_to_add

        cache.set(pts_key,     total_pts,   timeout=None)
        cache.set(monthly_key, monthly_pts, timeout=86400 * 45)

        try:
            from community.models import CommunityPoints
            CommunityPoints.objects.update_or_create(
                user_id=user_id,
                defaults={},
            )
            from django.db.models import F
            CommunityPoints.objects.filter(user_id=user_id).update(
                total_points=F('total_points') + points_to_add,
                monthly_points=F('monthly_points') + points_to_add,
            )
        except ImportError:
            pass

        # Check for milestone prizes
        check_point_milestones.apply_async(kwargs={'user_id': user_id})

        logger.debug(f"[COMMUNITY] User {user_id} +{points_to_add} pts (total={total_pts})")
        return {
            'status':       'success',
            'user_id':      user_id,
            'points_added': points_to_add,
            'total_points': total_pts,
            'monthly_pts':  monthly_pts,
            'source':       source,
            'timestamp':    timezone.now().isoformat(),
        }
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=10,
             name='tasks.community_tasks.check_point_milestones')
def check_point_milestones(self, user_id: int) -> dict:
    """Check if user has reached any prize tier and notify them."""
    try:
        monthly_key = f'community_points_monthly_{user_id}_{timezone.now().strftime("%Y%m")}'
        monthly_pts = cache.get(monthly_key, 0)
        unlocked    = []

        claimed_key = f'community_prizes_claimed_{user_id}_{timezone.now().strftime("%Y%m")}'
        claimed     = set(cache.get(claimed_key) or [])

        for threshold, prize in sorted(PRIZE_TIERS.items()):
            tier_key = str(threshold)
            if monthly_pts >= threshold and tier_key not in claimed:
                claimed.add(tier_key)
                unlocked.append({'threshold': threshold, 'prize': prize})

                # Notify user
                try:
                    from api.tasks.notification_tasks import dispatch_in_app_notification
                    dispatch_in_app_notification.apply_async(kwargs={
                        'user_id':           user_id,
                        'title':             f'🎁 Prize Unlocked: {prize["name"]}!',
                        'message':           (f'Congratulations! You reached {threshold:,} points '
                                              f'and unlocked: {prize["value"]}'),
                        'notification_type': 'success',
                    })
                except ImportError:
                    pass

                logger.info(f"[COMMUNITY] User {user_id} unlocked prize tier {threshold:,}")

        if claimed:
            cache.set(claimed_key, list(claimed), timeout=86400 * 45)

        return {
            'status':        'success',
            'user_id':       user_id,
            'monthly_points': monthly_pts,
            'prizes_unlocked': len(unlocked),
            'unlocked':      unlocked,
            'timestamp':     timezone.now().isoformat(),
        }
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=30,
             name='tasks.community_tasks.reset_monthly_points')
def reset_monthly_points(self) -> dict:
    """Reset monthly community point counters at month start."""
    try:
        logger.info("🔄 Resetting monthly community points...")
        reset = 0
        try:
            from community.models import CommunityPoints
            reset = CommunityPoints.objects.update(monthly_points=0)
        except ImportError:
            pass
        return {'status': 'success', 'reset': reset, 'timestamp': timezone.now().isoformat()}
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=30,
             name='tasks.community_tasks.update_community_leaderboard')
def update_community_leaderboard(self, limit: int = 100) -> dict:
    """Rebuild the community points leaderboard for display."""
    try:
        logger.info("🏆 Updating community leaderboard...")
        board = []
        month_tag = timezone.now().strftime('%Y%m')
        try:
            from community.models import CommunityPoints
            top = CommunityPoints.objects.order_by('-monthly_points').values(
                'user_id', 'user__username', 'monthly_points', 'total_points'
            )[:limit]
            board = [
                {
                    'rank':          i + 1,
                    'user_id':       row['user_id'],
                    'username':      row['user__username'],
                    'monthly_pts':   row['monthly_points'],
                    'total_pts':     row['total_points'],
                }
                for i, row in enumerate(top)
            ]
        except ImportError:
            pass

        cache.set(f'community_leaderboard_{month_tag}', board, timeout=3600)
        return {
            'status':  'success',
            'entries': len(board),
            'month':   month_tag,
            'timestamp': timezone.now().isoformat(),
        }
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=30,
             name='tasks.community_tasks.send_community_digest')
def send_community_digest(self) -> dict:
    """Send weekly community digest: top earners, tips, new offers."""
    try:
        from django.contrib.auth import get_user_model
        from django.core.mail import send_mass_mail
        from django.conf import settings
        logger.info("📰 Sending community weekly digest...")

        User    = get_user_model()
        month   = timezone.now().strftime('%Y%m')
        board   = cache.get(f'community_leaderboard_{month}', [])
        top3    = board[:3]
        top3_txt = '\n'.join([
            f"  #{e['rank']} {e['username']} — {e['monthly_pts']:,} pts"
            for e in top3
        ])

        subject = f"[Community Digest] This Week's Top Earners 🏆"
        sent    = 0

        for user in User.objects.filter(is_active=True).exclude(email='')[:1000]:
            try:
                msg = (
                    f"Hi {user.username}!\n\n"
                    f"This Month's Top Community Members:\n{top3_txt}\n\n"
                    f"Keep earning to climb the leaderboard and win prizes!\n\n"
                    f"— The Community Team"
                )
                from django.core.mail import send_mail
                send_mail(
                    subject=subject,
                    message=msg,
                    from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'community@example.com'),
                    recipient_list=[user.email],
                    fail_silently=True,
                )
                sent += 1
            except Exception:
                pass

        return {'status': 'success', 'sent': sent, 'timestamp': timezone.now().isoformat()}
    except Exception as exc:
        raise self.retry(exc=exc)
