# engagement/tasks/notification_tasks.py
"""
Async notification delivery tasks.
All push-heavy work is offloaded here so API responses stay fast.
"""
import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    name="engagement.tasks.send_streak_reminders",
)
def send_streak_reminders(self):
    """
    Remind users who haven't checked in yet today (at-risk streak).
    Scheduled: daily at 20:00 UTC (8 PM — prime reminder time).
    """
    try:
        from datetime import date
        from django.contrib.auth import get_user_model
        from ..models.checkin import DailyCheckIn
        from ..services.notification_service import NotificationService

        User  = get_user_model()
        today = date.today()

        # Users who have checked in at least once but NOT today
        checked_in_today_ids = set(
            DailyCheckIn.objects.filter(date=today).values_list("user_id", flat=True)
        )
        users_with_streak = (
            User.objects.filter(
                engagement_dailycheckin_set__date=today - __import__("datetime").timedelta(days=1)
            )
            .exclude(pk__in=checked_in_today_ids)
            .distinct()
        )

        count = 0
        for user in users_with_streak.iterator(chunk_size=200):
            try:
                latest = DailyCheckIn.objects.filter(user=user).order_by("-date").first()
                streak = latest.consecutive_days if latest else 0
                NotificationService.send(
                    user,
                    "streak_at_risk",
                    title="🔥 Don't break your streak!",
                    body=f"You have a {streak}-day streak. Check in before midnight!",
                    data={"streak": streak},
                    tenant=getattr(user, "tenant", None),
                )
                count += 1
            except Exception as inner_exc:
                logger.warning("streak reminder failed for user=%s: %s", user.pk, inner_exc)

        logger.info("send_streak_reminders: notified %d users", count)
        return {"notified": count}
    except Exception as exc:
        logger.exception("send_streak_reminders failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    name="engagement.tasks.send_leaderboard_snapshot",
)
def send_leaderboard_snapshot(self):
    """
    Push today's leaderboard top-3 to all users as a motivational notification.
    Scheduled: daily at 18:00 UTC.
    """
    try:
        from datetime import date
        from django.contrib.auth import get_user_model
        from ..models.leaderboard import Leaderboard
        from ..services.notification_service import NotificationService

        User    = get_user_model()
        today   = date.today()
        top3    = (
            Leaderboard.objects.filter(date=today, rank__lte=3)
            .select_related("user")
            .order_by("rank")
        )

        if not top3.exists():
            return {"notified": 0}

        names = " · ".join(f"#{e.rank} {e.user.username}" for e in top3)
        users = User.objects.filter(is_active=True)

        NotificationService.bulk_send(
            users,
            "leaderboard",
            title="🏆 Today's Leaderboard",
            body=f"Top earners: {names}",
            data={"date": str(today)},
        )
        logger.info("send_leaderboard_snapshot: sent to %d users", users.count())
        return {"notified": users.count()}
    except Exception as exc:
        logger.exception("send_leaderboard_snapshot failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task(
    bind=True,
    max_retries=2,
    name="engagement.tasks.notify_reward_distributed",
)
def notify_reward_distributed(self, user_id: int, rank: int, coins: float):
    """
    Send a personalised reward notification after leaderboard rewards are distributed.
    Called per user by distribute_daily_rewards task.
    """
    try:
        from django.contrib.auth import get_user_model
        from ..services.notification_service import NotificationService

        User = get_user_model()
        user = User.objects.get(pk=user_id)

        NotificationService.send(
            user,
            "reward",
            title=f"🎉 Leaderboard Reward — Rank #{rank}",
            body=f"You earned {coins} coins for finishing #{rank} on yesterday's leaderboard!",
            data={"rank": rank, "coins": coins},
            tenant=getattr(user, "tenant", None),
        )
        logger.info("notify_reward_distributed: user=%s rank=%d coins=%s", user_id, rank, coins)
    except Exception as exc:
        logger.exception("notify_reward_distributed failed for user=%s: %s", user_id, exc)
        raise self.retry(exc=exc)
