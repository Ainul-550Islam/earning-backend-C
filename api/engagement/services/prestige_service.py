# engagement/services/prestige_service.py
import logging
from django.db import transaction
from django.utils import timezone
from .coin_service import CoinService
from .xp_service import XPService
from .notification_service import NotificationService
from ..models.prestige import PrestigeLevel, UserPrestige, Milestone, UserMilestone, UserTitle, UserEquippedTitle
from ..models.xp import UserXP

logger = logging.getLogger(__name__)


class PrestigeService:

    @classmethod
    @transaction.atomic
    def attempt_prestige(cls, user, tenant=None) -> dict:
        """
        Prestige the user if they meet requirements.
        Resets XP + level, grants permanent prestige perks.
        """
        xp_obj = UserXP.objects.select_for_update().get(user=user)
        current_prestige = UserPrestige.objects.filter(user=user).count()
        next_level = current_prestige + 1

        prestige_def = PrestigeLevel.objects.filter(level=next_level).first()
        if not prestige_def:
            return {"error": "No prestige level defined."}

        if xp_obj.level < prestige_def.required_level:
            return {
                "error": f"Need level {prestige_def.required_level}, you are {xp_obj.level}.",
                "required_level": prestige_def.required_level,
            }

        # Record prestige
        UserPrestige.objects.create(
            user=user,
            tenant=tenant or getattr(user, "tenant", None),
            prestige_level=next_level,
            level_at_prestige=xp_obj.level,
            xp_at_prestige=xp_obj.total_xp,
            coin_multiplier=prestige_def.coin_multiplier,
            xp_multiplier=prestige_def.xp_multiplier,
        )

        # Reset XP and level
        xp_obj.total_xp         = 0
        xp_obj.level            = 1
        xp_obj.level_updated_at = timezone.now()
        xp_obj.save(update_fields=["total_xp", "level", "level_updated_at"])

        # Grant exclusive item if configured
        if prestige_def.exclusive_item_slug:
            try:
                from .shop_service import ShopService
                from ..models.shop import ShopItem
                item = ShopItem.objects.filter(slug=prestige_def.exclusive_item_slug, is_active=True).first()
                if item:
                    ShopService.purchase(user, item.slug, tenant=tenant)
            except Exception as exc:
                logger.warning("PrestigeService: exclusive item grant failed: %s", exc)

        # Notify
        NotificationService.send(
            user, "prestige",
            title=f"Prestige {next_level}: {prestige_def.name}!",
            body=f"You have prestiged! Coin ×{prestige_def.coin_multiplier}, XP ×{prestige_def.xp_multiplier}",
            data={"prestige_level": next_level},
            tenant=tenant,
        )

        logger.info("PrestigeService: user=%s now prestige %d", user.pk, next_level)
        return {
            "success": True,
            "prestige_level": next_level,
            "name": prestige_def.name,
            "coin_multiplier": float(prestige_def.coin_multiplier),
            "xp_multiplier": float(prestige_def.xp_multiplier),
        }

    @classmethod
    def get_multipliers(cls, user) -> dict:
        """Get the current user's prestige coin/xp multipliers."""
        latest = UserPrestige.objects.filter(user=user).order_by("-prestige_level").first()
        if not latest:
            return {"coin_multiplier": 1.0, "xp_multiplier": 1.0, "prestige_level": 0}
        return {
            "coin_multiplier": float(latest.coin_multiplier),
            "xp_multiplier": float(latest.xp_multiplier),
            "prestige_level": latest.prestige_level,
        }


class MilestoneService:

    @classmethod
    def check_all(cls, user, tenant=None) -> list:
        """Check and unlock any milestones the user now qualifies for."""
        unlocked = []
        pending = Milestone.objects.filter(is_active=True).exclude(
            user_milestones__user=user
        )
        for ms in pending:
            val = cls._get_metric(user, ms.metric)
            if val >= ms.threshold:
                um = cls._unlock(user, ms, tenant)
                if um:
                    unlocked.append(ms)
        return unlocked

    @classmethod
    @transaction.atomic
    def _unlock(cls, user, milestone: Milestone, tenant=None):
        um, created = UserMilestone.objects.get_or_create(
            user=user, milestone=milestone,
            defaults={"tenant": tenant or getattr(user, "tenant", None)},
        )
        if not created:
            return None
        if milestone.coin_reward > 0:
            CoinService.add(user, milestone.coin_reward, source="milestone")
        if milestone.xp_reward > 0:
            XPService.grant(user, milestone.xp_reward, source="milestone")
        if milestone.title_reward:
            title = UserTitle.objects.filter(slug=milestone.title_reward).first()
            if title:
                equipped, _ = UserEquippedTitle.objects.get_or_create(user=user)
                equipped.unlocked_titles.add(title)
        logger.info("MilestoneService: user=%s unlocked '%s'", user.pk, milestone.slug)
        return um

    @staticmethod
    def _get_metric(user, metric: str) -> int:
        from ..models.checkin import DailyCheckIn
        from ..models.spinwheel import SpinWheel
        from ..models.referral import Referral
        from ..models.shop import ShopPurchase
        from ..models.xp import UserXP
        try:
            if metric == "total_checkins":
                return DailyCheckIn.objects.filter(user=user).count()
            if metric == "checkin_streak":
                ci = DailyCheckIn.objects.filter(user=user).order_by("-date").first()
                return ci.consecutive_days if ci else 0
            if metric == "total_spins":
                return SpinWheel.objects.filter(user=user).count()
            if metric == "total_referrals":
                return Referral.objects.filter(referrer=user, status__in=["confirmed", "rewarded"]).count()
            if metric == "total_purchases":
                return ShopPurchase.objects.filter(user=user).count()
            if metric == "total_xp":
                xp = UserXP.objects.filter(user=user).first()
                return xp.total_xp if xp else 0
            if metric == "prestige_level":
                from ..models.prestige import UserPrestige
                up = UserPrestige.objects.filter(user=user).order_by("-prestige_level").first()
                return up.prestige_level if up else 0
            if metric == "friends_count":
                from ..models.social import Friendship
                return Friendship.objects.filter(requester=user, status="accepted").count() + \
                       Friendship.objects.filter(receiver=user, status="accepted").count()
        except Exception:
            pass
        return 0
