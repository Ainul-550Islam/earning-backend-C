# engagement/services/analytics_service.py
"""
Engagement Analytics Service
Records events, computes retention, aggregates daily metrics.
"""
import logging
from datetime import date, timedelta
from django.db import transaction
from django.db.models import Count, Sum, Avg
from ..models.analytics import EngagementEvent, RetentionCohort, DailyPlatformMetric

logger = logging.getLogger(__name__)


class AnalyticsService:

    # ── Event recording ───────────────────────────────────────────────────────

    @classmethod
    def record(cls, user, event_type: str, coins_delta=0, xp_delta=0, value=0,
               properties: dict = None, session_id: str = "",
               ip_address: str = "", device_type: str = "", platform: str = "",
               app_version: str = "", tenant=None):
        """
        Record an engagement event. Fire-and-forget — never blocks the API.
        In production, call this via Celery: record_engagement_event.delay(...)
        """
        try:
            EngagementEvent.objects.create(
                user=user,
                tenant=tenant or getattr(user, "tenant", None),
                event_type=event_type,
                coins_delta=coins_delta,
                xp_delta=xp_delta,
                value=value,
                properties=properties or {},
                session_id=session_id,
                ip_address=ip_address or None,
                device_type=device_type,
                platform=platform,
                app_version=app_version,
            )
        except Exception as exc:
            logger.error("AnalyticsService.record failed: %s", exc)

    # ── Daily aggregation (called by Celery at midnight) ──────────────────────

    @classmethod
    @transaction.atomic
    def aggregate_daily(cls, target_date=None, tenant=None):
        """Compute DailyPlatformMetric for the given date."""
        target_date = target_date or (date.today() - timedelta(days=1))
        from django.contrib.auth import get_user_model
        User = get_user_model()

        from ..models.checkin import DailyCheckIn
        from ..models.spinwheel import SpinWheel
        from ..models.quest import UserQuest
        from ..models.achievement import UserAchievement
        from ..models.shop import ShopPurchase
        from ..models.loot_box import ChestOpening

        qs_filter = {"event_time__date": target_date}
        if tenant:
            qs_filter["tenant"] = tenant

        dau = EngagementEvent.objects.filter(**qs_filter).values("user").distinct().count()
        checkins      = DailyCheckIn.objects.filter(date=target_date, **({} if not tenant else {"tenant": tenant})).count()
        spins         = SpinWheel.objects.filter(spun_at__date=target_date).count()
        quests_done   = UserQuest.objects.filter(completed_at__date=target_date, status="completed").count()
        achievements  = UserAchievement.objects.filter(unlocked_at__date=target_date).count()
        purchases     = ShopPurchase.objects.filter(created_at__date=target_date).count()
        coins_dist    = (
            (DailyCheckIn.objects.filter(date=target_date).aggregate(s=Sum("coins_earned"))["s"] or 0) +
            (SpinWheel.objects.filter(spun_at__date=target_date).aggregate(s=Sum("coins_won"))["s"] or 0)
        )
        xp_dist       = EngagementEvent.objects.filter(**qs_filter).aggregate(s=Sum("xp_delta"))["s"] or 0
        chest_opens   = ChestOpening.objects.filter(opened_at__date=target_date).count()
        new_users     = User.objects.filter(date_joined__date=target_date).count()

        metric, _ = DailyPlatformMetric.objects.update_or_create(
            date=target_date,
            defaults={
                "dau":              dau,
                "checkins":         checkins,
                "spins":            spins,
                "quests_completed": quests_done,
                "achievements_unlocked": achievements,
                "shop_purchases":   purchases,
                "coins_distributed": coins_dist,
                "xp_distributed":   xp_dist,
                "new_users":        new_users,
                "chest_openings":   chest_opens,
            }
        )
        logger.info("AnalyticsService.aggregate_daily: date=%s DAU=%d", target_date, dau)
        return metric

    # ── Retention cohort ──────────────────────────────────────────────────────

    @classmethod
    def compute_retention(cls, cohort_date: date, period_type: str = "daily",
                          period_number: int = 1, tenant=None):
        """Compute D1/D7/D30 (or W1/W2) retention for a signup cohort."""
        from django.contrib.auth import get_user_model
        User = get_user_model()

        cohort_users = User.objects.filter(date_joined__date=cohort_date)
        total        = cohort_users.count()
        if total == 0:
            return

        if period_type == "daily":
            check_date = cohort_date + timedelta(days=period_number)
        else:  # weekly
            check_date = cohort_date + timedelta(weeks=period_number)

        retained = EngagementEvent.objects.filter(
            user__in=cohort_users,
            event_time__date=check_date,
        ).values("user").distinct().count()

        RetentionCohort.objects.update_or_create(
            cohort_date=cohort_date, period_type=period_type,
            period_number=period_number, tenant=tenant,
            defaults={"total_users": total, "retained": retained},
        )
        return {"total": total, "retained": retained, "rate": round(retained / total * 100, 1)}

    # ── Dashboard read helpers ────────────────────────────────────────────────

    @staticmethod
    def last_n_days_metrics(n: int = 30, tenant=None):
        """Return DailyPlatformMetric for the last N days."""
        since = date.today() - timedelta(days=n)
        qs = DailyPlatformMetric.objects.filter(date__gte=since)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return list(qs.order_by("date"))

    @staticmethod
    def user_event_summary(user, days: int = 7):
        """Return event counts for a user over the last N days."""
        since = date.today() - timedelta(days=days)
        return dict(
            EngagementEvent.objects
            .filter(user=user, event_time__date__gte=since)
            .values("event_type")
            .annotate(count=Count("id"))
            .values_list("event_type", "count")
        )
