# engagement/tasks/advanced_tasks.py
"""
Advanced Celery Tasks for all new engagement systems.
"""
import logging
from datetime import date, timedelta
from celery import shared_task

logger = logging.getLogger(__name__)


# ── Analytics ─────────────────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=2, name="engagement.tasks.aggregate_daily_analytics")
def aggregate_daily_analytics(self, date_str=None, tenant_id=None):
    """Aggregate DailyPlatformMetric for yesterday. Runs at 00:15 UTC."""
    try:
        from ..services.analytics_service import AnalyticsService
        target = date.fromisoformat(date_str) if date_str else date.today() - timedelta(days=1)
        tenant = None
        if tenant_id:
            from tenants.models import Tenant
            tenant = Tenant.objects.filter(pk=tenant_id).first()
        metric = AnalyticsService.aggregate_daily(target, tenant)
        logger.info("aggregate_daily_analytics: %s DAU=%d", target, metric.dau)
        return {"date": str(target), "dau": metric.dau}
    except Exception as exc:
        logger.exception("aggregate_daily_analytics failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, name="engagement.tasks.compute_retention_cohorts")
def compute_retention_cohorts(self):
    """Compute D1/D7/D30 retention for recent cohorts. Runs daily at 01:00 UTC."""
    try:
        from ..services.analytics_service import AnalyticsService
        today = date.today()
        count = 0
        for days_ago in [1, 7, 30]:
            cohort_date = today - timedelta(days=days_ago + 1)
            for period, period_num in [("daily", 1), ("daily", 7), ("daily", 30), ("weekly", 1)]:
                result = AnalyticsService.compute_retention(cohort_date, period, period_num)
                if result:
                    count += 1
        logger.info("compute_retention_cohorts: computed %d cohorts", count)
        return {"cohorts_computed": count}
    except Exception as exc:
        logger.exception("compute_retention_cohorts failed: %s", exc)
        raise self.retry(exc=exc)


# ── Webhook ────────────────────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=2, name="engagement.tasks.retry_failed_webhooks")
def retry_failed_webhooks(self):
    """Retry failed webhook deliveries. Runs every 5 minutes."""
    try:
        from ..services.webhook_service import WebhookService
        count = WebhookService.retry_failed()
        logger.info("retry_failed_webhooks: retried %d", count)
        return {"retried": count}
    except Exception as exc:
        logger.exception("retry_failed_webhooks: %s", exc)
        raise self.retry(exc=exc)


# ── Anti-Cheat ─────────────────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=2, name="engagement.tasks.run_anticheat_scan")
def run_anticheat_scan(self):
    """Recalculate risk scores for all flagged users. Runs every 2 hours."""
    try:
        from ..services.anti_cheat_service import AntiCheatService
        from ..models.anti_cheat import AntiCheatLog
        from django.contrib.auth import get_user_model
        User = get_user_model()
        flagged_user_ids = AntiCheatLog.objects.filter(status="pending").values_list("user_id", flat=True).distinct()
        count = 0
        for uid in flagged_user_ids:
            try:
                user = User.objects.get(pk=uid)
                AntiCheatService.recalculate_risk(user)
                count += 1
            except User.DoesNotExist:
                pass
        logger.info("run_anticheat_scan: scanned %d users", count)
        return {"users_scanned": count}
    except Exception as exc:
        logger.exception("run_anticheat_scan failed: %s", exc)
        raise self.retry(exc=exc)


# ── Guild ──────────────────────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=2, name="engagement.tasks.rebuild_guild_leaderboard")
def rebuild_guild_leaderboard(self, tenant_id=None):
    """Rebuild weekly guild leaderboard. Runs every 2 hours."""
    try:
        from ..models.guild import Guild, GuildLeaderboard
        from datetime import timedelta
        monday = date.today() - timedelta(days=date.today().weekday())
        guilds = Guild.objects.filter(is_active=True)
        if tenant_id:
            guilds = guilds.filter(tenant_id=tenant_id)
        guilds = guilds.order_by("-total_xp")[:100]
        for idx, guild in enumerate(guilds, 1):
            GuildLeaderboard.objects.update_or_create(
                guild=guild, week_start=monday,
                defaults={"total_xp": guild.total_xp, "rank": idx},
            )
        logger.info("rebuild_guild_leaderboard: ranked %d guilds", guilds.count())
        return {"guilds_ranked": guilds.count()}
    except Exception as exc:
        logger.exception("rebuild_guild_leaderboard failed: %s", exc)
        raise self.retry(exc=exc)


# ── Seasonal Events ────────────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=2, name="engagement.tasks.expire_seasonal_events")
def expire_seasonal_events(self):
    """Mark expired seasonal events as inactive. Runs every hour."""
    try:
        from ..models.seasonal_event import SeasonalEvent
        from django.utils import timezone
        count = SeasonalEvent.objects.filter(
            is_active=True, ends_at__lt=timezone.now()
        ).update(is_active=False)
        logger.info("expire_seasonal_events: deactivated %d events", count)
        return {"expired": count}
    except Exception as exc:
        logger.exception("expire_seasonal_events failed: %s", exc)
        raise self.retry(exc=exc)


# ── Auction ────────────────────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=3, name="engagement.tasks.close_expired_auctions")
def close_expired_auctions(self):
    """Close all auctions past their end_at. Runs every 5 minutes."""
    try:
        from ..models.auction import Auction
        from ..services.auction_service import AuctionService
        from django.utils import timezone
        expired = Auction.objects.filter(status="active", ends_at__lt=timezone.now())
        count   = 0
        for auction in expired:
            AuctionService.close_auction(auction.pk)
            count += 1
        logger.info("close_expired_auctions: closed %d", count)
        return {"closed": count}
    except Exception as exc:
        logger.exception("close_expired_auctions failed: %s", exc)
        raise self.retry(exc=exc)


# ── Campaign ───────────────────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=2, name="engagement.tasks.deliver_scheduled_campaigns")
def deliver_scheduled_campaigns(self):
    """Deliver any campaigns that are due to start. Runs every 5 minutes."""
    try:
        from ..models.campaign import Campaign
        from ..services.campaign_service import CampaignService
        from django.utils import timezone
        due = Campaign.objects.filter(status="scheduled", starts_at__lte=timezone.now())
        total = 0
        for campaign in due:
            total += CampaignService.deliver(campaign)
        logger.info("deliver_scheduled_campaigns: delivered to %d users", total)
        return {"delivered": total}
    except Exception as exc:
        logger.exception("deliver_scheduled_campaigns failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, name="engagement.tasks.sync_all_segments")
def sync_all_segments(self):
    """Sync all dynamic user segments. Runs daily at 02:00 UTC."""
    try:
        from ..models.campaign import UserSegment
        from ..services.campaign_service import SegmentService
        segments = UserSegment.objects.filter(is_dynamic=True)
        for segment in segments:
            SegmentService.sync_segment(segment)
        logger.info("sync_all_segments: synced %d segments", segments.count())
        return {"synced": segments.count()}
    except Exception as exc:
        logger.exception("sync_all_segments failed: %s", exc)
        raise self.retry(exc=exc)


# ── Milestone Checks ───────────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=2, name="engagement.tasks.check_milestones_all_users")
def check_milestones_all_users(self):
    """Run milestone checks for all active users. Runs daily at 03:00 UTC."""
    try:
        from ..services.prestige_service import MilestoneService
        from django.contrib.auth import get_user_model
        User = get_user_model()
        total_unlocked = 0
        for user in User.objects.filter(is_active=True).iterator(chunk_size=100):
            unlocked = MilestoneService.check_all(user)
            total_unlocked += len(unlocked)
        logger.info("check_milestones_all_users: unlocked %d milestones", total_unlocked)
        return {"unlocked": total_unlocked}
    except Exception as exc:
        logger.exception("check_milestones_all_users failed: %s", exc)
        raise self.retry(exc=exc)
