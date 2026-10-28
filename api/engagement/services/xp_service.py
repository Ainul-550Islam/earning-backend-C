# engagement/services/xp_service.py
import logging
from django.db import transaction
from django.utils import timezone
from ..models.xp import UserXP, XPTransaction, level_from_total_xp

logger = logging.getLogger(__name__)


class XPService:
    """
    XP grants, level-up detection, and transaction logging.
    Fires the 'level_up' signal when a user crosses a level boundary.
    """

    @classmethod
    @transaction.atomic
    def grant(cls, user, amount: int, source: str, ref_id: str = "", note: str = "") -> dict:
        """
        Grant XP to user. Returns dict with old_level, new_level, leveled_up flag.
        """
        if amount <= 0:
            raise ValueError(f"XPService.grant: amount must be positive, got {amount}")

        xp_obj, _ = UserXP.objects.select_for_update().get_or_create(
            user=user,
            defaults={"tenant": getattr(user, "tenant", None)},
        )

        old_level   = xp_obj.level
        xp_obj.total_xp += amount
        new_level   = level_from_total_xp(xp_obj.total_xp)
        leveled_up  = new_level > old_level

        if leveled_up:
            xp_obj.level = new_level
            xp_obj.level_updated_at = timezone.now()
            # Only update level_updated_at when level actually changes
            xp_obj.save(update_fields=["total_xp", "level", "level_updated_at"])
        else:
            # Only update total_xp when no level change
            xp_obj.save(update_fields=["total_xp"])

        # Audit log
        XPTransaction.objects.create(
            user=user,
            tenant=getattr(user, "tenant", None),
            source=source,
            amount=amount,
            note=note,
            ref_id=str(ref_id),
        )

        if leveled_up:
            cls._fire_level_up_signal(user, old_level, new_level)

        logger.info(
            "XPService.grant user=%s +%d (src=%s) level %d→%d",
            user.pk, amount, source, old_level, new_level,
        )

        return {
            "old_level": old_level,
            "new_level": new_level,
            "leveled_up": leveled_up,
            "total_xp": xp_obj.total_xp,
            "level_pct": xp_obj.level_pct,
        }

    @staticmethod
    def get_or_create(user) -> UserXP:
        xp_obj, _ = UserXP.objects.get_or_create(
            user=user,
            defaults={"tenant": getattr(user, "tenant", None)},
        )
        return xp_obj

    # ── Private ───────────────────────────────────────────────────────────────

    @staticmethod
    def _fire_level_up_signal(user, old_level: int, new_level: int):
        try:
            from django.dispatch import Signal
            from ..signals import level_up_signal
            level_up_signal.send(
                sender=user.__class__,
                user=user,
                old_level=old_level,
                new_level=new_level,
            )
        except Exception as exc:
            logger.warning("XPService: level_up signal failed – %s", exc)
