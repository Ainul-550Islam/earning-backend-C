# engagement/views/stats_views.py
"""
All summary / dashboard stats endpoints live here.
These are the most frequently-called endpoints, so every response
uses cache where appropriate and minimises DB hits.
"""
from datetime import date
from django.db.models import Sum
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response

from ..services import LeaderboardService, NotificationService
from ..services.xp_service import XPService
from ..models.checkin import DailyCheckIn
from ..models.spinwheel import SpinWheel
from ..models.achievement import UserAchievement
from ..models.quest import UserQuest
from ..constants import SPIN_MAX_PER_DAY
from ..utils.cache import get_user_stats_cache, set_user_stats_cache


def _coin_balance(user) -> float:
    """Safe coin balance accessor that works regardless of user model shape."""
    try:
        return float(user.coin_balance)
    except AttributeError:
        try:
            return float(user.wallet.balance)
        except Exception:
            return 0.0


# ── GET /engagement/ ─ daily dashboard ───────────────────────────────────────

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_daily_stats(request):
    """
    GET /engagement/
    GET /engagement/daily-stats/
    Primary mobile dashboard payload — check-in status, spins remaining,
    today's earnings, XP, coin balance.
    Uses a 5-minute user-level cache.
    """
    user  = request.user
    today = date.today()

    cached = get_user_stats_cache(user.pk)
    if cached:
        return Response(cached)

    checkin    = DailyCheckIn.objects.filter(user=user, date=today).first()
    spins_used = SpinWheel.objects.filter(user=user, spun_at__date=today).count()
    xp_obj     = XPService.get_or_create(user)

    # Today's earnings — try EarningTask first, fall back to engagement coins
    todays_earnings = 0.0
    try:
        from api.analytics.models import AnalyticsEvent
        events_total = AnalyticsEvent.objects.filter(
            user=user,
            event_type__in=["task_completed", "offer_completed"],
            event_time__date=today,
        ).aggregate(total=Sum("value"))["total"] or 0
        todays_earnings = float(events_total)
    except Exception:
        spin_today = SpinWheel.objects.filter(
            user=user, spun_at__date=today
        ).aggregate(s=Sum("coins_won"))["s"] or 0
        ci_today = checkin.coins_earned if checkin else 0
        todays_earnings = float(spin_today) + float(ci_today)

    # Active quests summary
    from ..services import QuestService
    active_quests = QuestService.active_for_user(user)
    daily_complete  = sum(1 for uq in active_quests["daily"]  if uq.status == "completed")
    weekly_complete = sum(1 for uq in active_quests["weekly"] if uq.status == "completed")

    payload = {
        "check_in": {
            "has_checked_in":   checkin is not None,
            "consecutive_days": checkin.consecutive_days if checkin else 0,
            "coins_earned":     float(checkin.coins_earned) if checkin else 0,
            "streak_shield_used": checkin.streak_shield_used if checkin else False,
        },
        "spin_wheel": {
            "spins_used":      spins_used,
            "spins_remaining": max(0, SPIN_MAX_PER_DAY - spins_used),
            "can_spin":        spins_used < SPIN_MAX_PER_DAY,
        },
        "todays_earnings": todays_earnings,
        "coin_balance":    _coin_balance(user),
        "xp": {
            "total_xp":            xp_obj.total_xp,
            "level":               xp_obj.level,
            "level_pct":           xp_obj.level_pct,
            "xp_for_next_level":   xp_obj.xp_for_next_level,
            "xp_needed_for_next":  xp_obj.xp_needed_for_next,
        },
        "quests": {
            "daily_total":    len(active_quests["daily"]),
            "daily_complete": daily_complete,
            "weekly_total":   len(active_quests["weekly"]),
            "weekly_complete": weekly_complete,
        },
        "unread_notifications": NotificationService.unread_count(user),
    }

    set_user_stats_cache(user.pk, payload)
    return Response(payload)


# ── GET /engagement/stats/ ─ engagement score card ───────────────────────────

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_engagement_stats(request):
    """
    GET /engagement/stats/
    Returns a holistic engagement score (0–100) and all key metrics.
    Used for the "89% engagement" score card in the frontend.
    """
    user  = request.user
    today = date.today()

    checkin_today = DailyCheckIn.objects.filter(user=user, date=today).first()
    streak        = checkin_today.consecutive_days if checkin_today else 0
    spins_today   = SpinWheel.objects.filter(user=user, spun_at__date=today).count()
    total_checkins = DailyCheckIn.objects.filter(user=user).count()
    total_spins    = SpinWheel.objects.filter(user=user).count()
    xp_obj         = XPService.get_or_create(user)
    rank_today     = LeaderboardService.get_user_rank(
        user, today, tenant=getattr(user, "tenant", None)
    )
    unread         = NotificationService.unread_count(user)
    achievements   = UserAchievement.objects.filter(user=user).count()

    # Engagement score formula (0–100):
    # 30 pts — checked in today
    # 20 pts — spins used today (pro-rata)
    # 20 pts — streak length (caps at 7 days)
    # 15 pts — total check-in history (caps at 30)
    # 15 pts — achievements unlocked (caps at 10)
    score = min(100.0, (
        (30 if checkin_today else 0)
        + (spins_today / SPIN_MAX_PER_DAY) * 20
        + min(streak / 7, 1.0) * 20
        + min(total_checkins / 30, 1.0) * 15
        + min(achievements / 10, 1.0) * 15
    ))

    return Response({
        "engagement_score":      round(score, 1),
        "streak":                streak,
        "has_checked_in":        checkin_today is not None,
        "spins_today":           spins_today,
        "spins_remaining":       max(0, SPIN_MAX_PER_DAY - spins_today),
        "total_checkins":        total_checkins,
        "total_spins":           total_spins,
        "coin_balance":          _coin_balance(user),
        "level":                 xp_obj.level,
        "total_xp":              xp_obj.total_xp,
        "level_pct":             xp_obj.level_pct,
        "achievements_unlocked": achievements,
        "rank_today":            rank_today,
        "unread_notifications":  unread,
    })


# ── GET /engagement/admin/platform-stats/ ─ admin overview ───────────────────

@api_view(["GET"])
@permission_classes([IsAdminUser])
def platform_stats(request):
    """
    GET /engagement/admin/platform-stats/
    Platform-wide engagement metrics for the admin dashboard.
    """
    today = date.today()
    from django.contrib.auth import get_user_model
    User = get_user_model()

    total_users        = User.objects.filter(is_active=True).count()
    checkins_today     = DailyCheckIn.objects.filter(date=today).count()
    spins_today        = SpinWheel.objects.filter(spun_at__date=today).count()
    coins_given_today  = float(
        DailyCheckIn.objects.filter(date=today).aggregate(s=Sum("coins_earned"))["s"] or 0
    ) + float(
        SpinWheel.objects.filter(spun_at__date=today).aggregate(s=Sum("coins_won"))["s"] or 0
    )
    total_achievements = UserAchievement.objects.count()
    checkin_rate       = round(checkins_today / total_users * 100, 1) if total_users else 0
    spin_rate          = round(spins_today    / total_users * 100, 1) if total_users else 0

    return Response({
        "total_active_users":    total_users,
        "checkins_today":        checkins_today,
        "spins_today":           spins_today,
        "coins_distributed_today": coins_given_today,
        "total_achievements_unlocked": total_achievements,
        "checkin_rate_pct":      checkin_rate,
        "spin_rate_pct":         spin_rate,
    })
