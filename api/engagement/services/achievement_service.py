# engagement/services/achievement_service.py
import logging
from django.db import transaction
from .coin_service import CoinService
from .xp_service import XPService
from ..models.achievement import Achievement, UserAchievement, AchievementProgress

logger = logging.getLogger(__name__)


class AchievementService:

    @classmethod
    def check_and_unlock(cls, user, achievement_type: str, current_value: int, tenant=None) -> list:
        """
        Given a type and current metric value, unlock any Achievement whose threshold
        the user now meets and hasn't already unlocked.
        Returns list of newly unlocked Achievement objects.
        """
        unlocked = []

        candidates = Achievement.objects.filter(
            type=achievement_type,
            threshold__lte=current_value,
            is_active=True,
        ).exclude(
            user_achievements__user=user
        )

        for achievement in candidates:
            ua = cls._unlock(user, achievement, tenant)
            if ua:
                unlocked.append(achievement)

        return unlocked

    @classmethod
    @transaction.atomic
    def _unlock(cls, user, achievement: Achievement, tenant=None):
        """Atomically create UserAchievement and grant rewards."""
        ua, created = UserAchievement.objects.get_or_create(
            user        = user,
            achievement = achievement,
            defaults    = {"tenant": tenant or getattr(user, "tenant", None)},
        )
        if not created:
            return None

        # Grant coin & XP rewards
        if achievement.coin_reward > 0:
            CoinService.add(user, achievement.coin_reward, source="achievement", ref_id=str(achievement.pk))
            ua.reward_claimed = True
            ua.save(update_fields=["reward_claimed"])

        if achievement.xp_reward > 0:
            XPService.grant(user, achievement.xp_reward, source="achievement", ref_id=str(achievement.pk))

        logger.info("Achievement unlocked: user=%s achievement='%s'", user.pk, achievement.slug)
        return ua

    @classmethod
    def update_progress(cls, user, achievement_type: str, increment: int = 1, tenant=None):
        """
        Increment progress counters for all active achievements of given type
        that the user hasn't yet unlocked. Auto-unlocks when threshold is met.
        """
        achievements = Achievement.objects.filter(
            type=achievement_type, is_active=True
        ).exclude(user_achievements__user=user)

        for achievement in achievements:
            prog, _ = AchievementProgress.objects.get_or_create(
                user        = user,
                achievement = achievement,
                defaults    = {"tenant": tenant or getattr(user, "tenant", None)},
            )
            prog.current = min(prog.current + increment, achievement.threshold)
            prog.save(update_fields=["current", "last_updated"])

            if prog.current >= achievement.threshold:
                cls._unlock(user, achievement, tenant)

    @staticmethod
    def get_all_with_status(user) -> list:
        """Return all active achievements with lock/unlock status for user."""
        unlocked_ids = set(
            UserAchievement.objects.filter(user=user).values_list("achievement_id", flat=True)
        )
        progress_map = {
            p.achievement_id: p.current
            for p in AchievementProgress.objects.filter(user=user)
        }

        achievements = Achievement.objects.filter(is_active=True).order_by("type", "order", "threshold")
        result = []
        for a in achievements:
            is_unlocked = a.id in unlocked_ids
            if a.is_secret and not is_unlocked:
                continue
            result.append({
                "id":          a.id,
                "slug":        a.slug,
                "name":        a.name,
                "description": a.description,
                "icon":        a.icon,
                "badge_color": a.badge_color,
                "type":        a.type,
                "threshold":   a.threshold,
                "is_unlocked": is_unlocked,
                "progress":    progress_map.get(a.id, 0),
                "pct":         min(100, int(progress_map.get(a.id, 0) / a.threshold * 100)) if a.threshold else 100,
            })
        return result
