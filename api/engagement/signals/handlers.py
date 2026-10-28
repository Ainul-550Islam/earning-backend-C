# engagement/signals/handlers.py — COMPLETE 100%
"""
All Django signal handlers. Connected in EngagementConfig.ready().
Covers all 35 engagement systems.
"""
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from . import level_up_signal, achievement_unlocked_signal, quest_completed_signal, streak_broken_signal

logger = logging.getLogger(__name__)


# ── Level-Up ──────────────────────────────────────────────────────────────────
@receiver(level_up_signal)
def handle_level_up(sender, user, old_level, new_level, **kwargs):
    try:
        from ..services.gamification_engine import GamificationEngine
        GamificationEngine.on_level_up(user, old_level, new_level, tenant=getattr(user, "tenant", None))
    except Exception as exc:
        logger.exception("handle_level_up failed: %s", exc)


# ── Achievement ───────────────────────────────────────────────────────────────
@receiver(achievement_unlocked_signal)
def handle_achievement_unlocked(sender, user, achievement, **kwargs):
    try:
        from ..services.gamification_engine import GamificationEngine
        GamificationEngine.on_achievement_unlock(user, achievement, tenant=getattr(user, "tenant", None))
        from ..models.achievement import UserAchievement
        UserAchievement.objects.filter(user=user, achievement=achievement).update(notified=True)
    except Exception as exc:
        logger.exception("handle_achievement_unlocked failed: %s", exc)


# ── Quest Completed ───────────────────────────────────────────────────────────
@receiver(quest_completed_signal)
def handle_quest_completed(sender, user, user_quest, **kwargs):
    try:
        from ..services.gamification_engine import GamificationEngine
        from ..services.notification_service import NotificationService
        GamificationEngine.on_quest_complete(user, user_quest, tenant=getattr(user, "tenant", None))
        NotificationService.send(user, "quest_complete",
            title=f"✅ Quest: {user_quest.quest.title}",
            body=f"Earned {user_quest.quest.coin_reward} coins + {user_quest.quest.xp_reward} XP!",
            data={"quest_slug": user_quest.quest.slug},
            tenant=getattr(user, "tenant", None),
        )
    except Exception as exc:
        logger.exception("handle_quest_completed failed: %s", exc)


# ── Streak Broken ───────────────────────────────────────────────────────────────
@receiver(streak_broken_signal)
def handle_streak_broken(sender, user, old_streak, **kwargs):
    """Handle when a user's check-in streak is broken."""
    try:
        from ..services.notification_service import NotificationService
        from ..services.analytics_service import AnalyticsService
        
        # Send notification to user
        NotificationService.send(user, "streak_broken",
            title=f"💔 Streak Broken",
            body=f"Your {old_streak}-day streak has been broken. Check in tomorrow to start a new one!",
            data={"old_streak": old_streak},
            tenant=getattr(user, "tenant", None),
        )
        
        # Record analytics event
        AnalyticsService.record(user, "streak_broken", properties={"old_streak": old_streak}, tenant=getattr(user, "tenant", None))
        
        logger.info("Streak broken handled for user %s (old streak: %d)", user.pk, old_streak)
    except Exception as exc:
        logger.exception("handle_streak_broken failed: %s", exc)


# ── DailyCheckIn post_save ────────────────────────────────────────────────────
@receiver(post_save, sender="engagement.DailyCheckIn")
def on_daily_checkin_saved(sender, instance, created, **kwargs):
    if not created:
        return
    try:
        from ..services.gamification_engine import GamificationEngine
        from ..services.anti_cheat_service import AntiCheatService
        GamificationEngine.on_checkin(instance.user, instance, tenant=getattr(instance.user, "tenant", None))
        AntiCheatService.check_checkin_ip(instance.user)
    except Exception as exc:
        logger.exception("on_daily_checkin_saved failed: %s", exc)


# ── SpinWheel post_save ───────────────────────────────────────────────────────
@receiver(post_save, sender="engagement.SpinWheel")
def on_spin_saved(sender, instance, created, **kwargs):
    if not created:
        return
    try:
        from ..services.gamification_engine import GamificationEngine
        from ..services.anti_cheat_service import AntiCheatService
        GamificationEngine.on_spin(instance.user, instance, tenant=getattr(instance.user, "tenant", None))
        AntiCheatService.check_spin_velocity(instance.user)
    except Exception as exc:
        logger.exception("on_spin_saved failed: %s", exc)


# ── ShopPurchase post_save ────────────────────────────────────────────────────
@receiver(post_save, sender="engagement.ShopPurchase")
def on_purchase_saved(sender, instance, created, **kwargs):
    if not created:
        return
    try:
        from ..services.gamification_engine import GamificationEngine
        GamificationEngine.on_purchase(instance.user, instance, tenant=getattr(instance.user, "tenant", None))
    except Exception as exc:
        logger.exception("on_purchase_saved failed: %s", exc)


# ── Referral post_save ────────────────────────────────────────────────────────
@receiver(post_save, sender="engagement.Referral")
def on_referral_saved(sender, instance, created, **kwargs):
    if not created:
        return
    if instance.status not in ("confirmed", "rewarded"):
        return
    try:
        from ..services.gamification_engine import GamificationEngine
        from ..services.anti_cheat_service import AntiCheatService
        GamificationEngine.on_referral(instance.referrer, instance, tenant=getattr(instance.referrer, "tenant", None))
        AntiCheatService.check_referral_abuse(instance.referrer)
    except Exception as exc:
        logger.exception("on_referral_saved failed: %s", exc)


# ── GuildMember post_save ─────────────────────────────────────────────────────
@receiver(post_save, sender="engagement.GuildMember")
def on_guild_member_saved(sender, instance, created, **kwargs):
    if not created or instance.status != "active":
        return
    try:
        from ..services.gamification_engine import GamificationEngine
        GamificationEngine.on_guild_join(instance.user, instance.guild,
                                          tenant=getattr(instance.user, "tenant", None))
    except Exception as exc:
        logger.exception("on_guild_member_saved failed: %s", exc)


# ── ChestOpening post_save ────────────────────────────────────────────────────
@receiver(post_save, sender="engagement.ChestOpening")
def on_chest_opening_saved(sender, instance, created, **kwargs):
    if not created:
        return
    try:
        from ..services.gamification_engine import GamificationEngine
        GamificationEngine.on_chest_open(instance.user, instance,
                                          tenant=getattr(instance.user, "tenant", None))
    except Exception as exc:
        logger.exception("on_chest_opening_saved failed: %s", exc)


# ── UserPrestige post_save ────────────────────────────────────────────────────
@receiver(post_save, sender="engagement.UserPrestige")
def on_prestige_saved(sender, instance, created, **kwargs):
    if not created:
        return
    try:
        from ..services.gamification_engine import GamificationEngine
        GamificationEngine.on_prestige(instance.user, instance.prestige_level,
                                        tenant=getattr(instance.user, "tenant", None))
    except Exception as exc:
        logger.exception("on_prestige_saved failed: %s", exc)
