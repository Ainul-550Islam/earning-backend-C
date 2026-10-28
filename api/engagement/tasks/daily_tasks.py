# engagement/tasks/daily_tasks.py
"""
Celery tasks that run on a schedule (configured in CELERY_BEAT_SCHEDULE).
"""
import logging
from datetime import date, timedelta
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name="engagement.tasks.rebuild_daily_leaderboard",
)
def rebuild_daily_leaderboard(self, target_date_str=None, tenant_id=None):
    """
    Rebuild the Leaderboard snapshot for `target_date_str`.
    Scheduled: every hour during the day (via CELERY_BEAT_SCHEDULE).
    Also callable manually: rebuild_daily_leaderboard.delay()
    """
    try:
        from ..services.leaderboard_service import LeaderboardService
        from ..utils.cache import invalidate_leaderboard_cache

        target_date = date.fromisoformat(target_date_str) if target_date_str else date.today()

        tenant = None
        if tenant_id:
            from tenants.models import Tenant
            tenant = Tenant.objects.filter(pk=tenant_id).first()

        count = LeaderboardService.rebuild_daily(target_date, tenant)
        invalidate_leaderboard_cache(str(target_date), tenant_id)
        logger.info("rebuild_daily_leaderboard: date=%s count=%d tenant=%s", target_date, count, tenant_id)
        return {"rebuilt": count, "date": str(target_date)}
    except Exception as exc:
        logger.exception("rebuild_daily_leaderboard failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=120,
    name="engagement.tasks.distribute_daily_rewards",
)
def distribute_daily_rewards(self, target_date_str=None, tenant_id=None):
    """
    Distribute leaderboard coin rewards for yesterday's top-10.
    Scheduled: daily at 00:05 UTC.
    """
    try:
        from ..services.leaderboard_service import LeaderboardService

        target_date = date.fromisoformat(target_date_str) if target_date_str else (
            date.today() - timedelta(days=1)
        )

        tenant = None
        if tenant_id:
            from tenants.models import Tenant
            tenant = Tenant.objects.filter(pk=tenant_id).first()

        count = LeaderboardService.distribute_rewards(target_date, tenant)
        logger.info("distribute_daily_rewards: date=%s rewarded=%d", target_date, count)
        return {"rewarded": count, "date": str(target_date)}
    except Exception as exc:
        logger.exception("distribute_daily_rewards failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    name="engagement.tasks.init_daily_quests_all_users",
)
def init_daily_quests_all_users(self):
    """
    Initialise daily quest rows for every active user.
    Scheduled: daily at 00:01 UTC.
    """
    try:
        from django.contrib.auth import get_user_model
        from ..services.quest_service import QuestService

        User     = get_user_model()
        users    = User.objects.filter(is_active=True)
        total    = 0
        for user in users.iterator(chunk_size=200):
            try:
                created = QuestService.init_daily(user, tenant=getattr(user, "tenant", None))
                total  += len(created)
            except Exception as inner_exc:
                logger.warning("init_daily_quests for user=%s failed: %s", user.pk, inner_exc)

        logger.info("init_daily_quests_all_users: created %d quest rows", total)
        return {"created_rows": total}
    except Exception as exc:
        logger.exception("init_daily_quests_all_users failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    name="engagement.tasks.expire_old_quests",
)
def expire_old_quests(self):
    """
    Mark yesterday's active daily quests as 'expired'.
    Scheduled: daily at 00:02 UTC.
    """
    try:
        from django.utils import timezone
        from ..models.quest import UserQuest

        yesterday = date.today() - timedelta(days=1)
        count = UserQuest.objects.filter(
            period_date=yesterday,
            quest__type="daily",
            status="active",
        ).update(status="expired")
        logger.info("expire_old_quests: expired %d rows for %s", count, yesterday)
        return {"expired": count}
    except Exception as exc:
        logger.exception("expire_old_quests failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task(
    bind=True,
    max_retries=2,
    name="engagement.tasks.expire_shop_inventory",
)
def expire_shop_inventory(self):
    """
    Deactivate UserInventory entries whose expires_at has passed.
    Scheduled: every hour.
    """
    try:
        from django.utils import timezone
        from ..models.shop import UserInventory

        count = UserInventory.objects.filter(
            expires_at__lt=timezone.now(),
            quantity__gt=0,
        ).update(quantity=0)
        logger.info("expire_shop_inventory: expired %d entries", count)
        return {"expired": count}
    except Exception as exc:
        logger.exception("expire_shop_inventory failed: %s", exc)
        raise self.retry(exc=exc)
