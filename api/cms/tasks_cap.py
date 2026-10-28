# api/cms/tasks_cap.py
"""CPAlead-specific Celery tasks (CAP = CPAlead Publisher)."""
import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name='cms.cap.sync_offer_cache', bind=True, max_retries=3)
def sync_offer_cache_task(self):
    """Refresh CPAlead offer cache every 30 minutes."""
    try:
        from api.cms.services_new.CPALeadService import CPALeadService
        offers = CPALeadService.fetch_offers(limit=100)
        return f"Synced {len(offers)} offers"
    except Exception as exc:
        logger.error(f"[CAP] offer cache sync failed: {exc}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(name='cms.cap.reset_daily_earning_caps')
def reset_daily_earning_caps():
    """Reset daily earning cap at midnight."""
    try:
        from api.cms.services_new.CPALeadService import EarningCapService
        EarningCapService.reset_daily_caps()
        return "Daily caps reset"
    except Exception as e:
        logger.error(f"[CAP] daily cap reset failed: {e}")


@shared_task(name='cms.cap.cleanup_click_logs', bind=True)
def cleanup_old_click_logs(self, days=30):
    """Delete click logs older than N days."""
    try:
        from api.cms.models_new.cpalead import ClickLog
        from django.utils import timezone
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(days=days)
        deleted, _ = ClickLog.objects.filter(
            created_at__lt=cutoff, has_converted=False
        ).delete()
        return f"Deleted {deleted} old click logs"
    except Exception as e:
        logger.error(f"[CAP] click log cleanup failed: {e}")


@shared_task(name='cms.cap.retry_pending_conversions')
def retry_pending_conversions():
    """Find pending conversions older than 1 hour and retry."""
    try:
        from api.cms.models_new.cpalead import ConversionLog
        from django.utils import timezone
        from datetime import timedelta
        stale = ConversionLog.objects.filter(
            status='pending',
            created_at__lt=timezone.now() - timedelta(hours=1)
        )[:50]
        count = 0
        for conv in stale:
            try:
                from api.cms.services_new.CPALeadService import CPALeadService
                success, _ = CPALeadService._award_reward(
                    user=conv.user, subid=conv.subid,
                    payout_usd=conv.payout_usd, lead_id=conv.lead_id,
                    campaign_id=conv.campaign_id, config=None,
                )
                if success:
                    conv.status = 'approved'
                    conv.save(update_fields=['status'])
                    count += 1
            except Exception:
                pass
        return f"Retried {count} pending conversions"
    except Exception as e:
        logger.error(f"[CAP] pending conversion retry failed: {e}")


@shared_task(name='cms.cap.expire_locker_unlocks')
def expire_locker_unlocks():
    """Mark expired locker unlocks as invalid."""
    try:
        from api.cms.models_new.cpalead import LockerUnlock
        from django.utils import timezone
        expired = LockerUnlock.objects.filter(
            expires_at__lt=timezone.now(), is_valid=True
        ).update(is_valid=False)
        return f"Expired {expired} locker unlocks"
    except Exception as e:
        logger.error(f"[CAP] locker unlock expiry failed: {e}")


@shared_task(name='cms.cap.generate_leaderboard_report')
def generate_leaderboard_report():
    """Refresh all leaderboard ranks."""
    try:
        from api.cms.services_new.LeaderboardService import LeaderboardService
        total = 0
        for period in ['daily', 'weekly', 'monthly']:
            for cat in ['earnings', 'coins', 'offers']:
                total += LeaderboardService.refresh_ranks(period, cat)
        return f"Refreshed {total} leaderboard entries"
    except Exception as e:
        logger.error(f"[CAP] leaderboard refresh failed: {e}")


@shared_task(name='cms.cap.reset_broken_streaks')
def reset_broken_streaks_task():
    """Reset streaks for users who didn't earn yesterday."""
    try:
        from api.cms.services_new.LeaderboardService import StreakService
        count = StreakService.reset_broken_streaks()
        return f"Reset {count} broken streaks"
    except Exception as e:
        logger.error(f"[CAP] streak reset failed: {e}")
