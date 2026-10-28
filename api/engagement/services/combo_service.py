# engagement/services/combo_service.py
"""
Combo Multiplier Service — builds streak multipliers on repeated actions.
Energy Service — regenerates over time, costs per action.
"""
import logging
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from ..models.combo import ComboConfig, UserCombo, EnergyConfig, EnergyCost, UserEnergy

logger = logging.getLogger(__name__)


class ComboService:

    @classmethod
    @transaction.atomic
    def register_action(cls, user, action: str, tenant=None) -> dict:
        """
        Called every time user performs an action.
        Returns current multiplier and streak info.
        """
        try:
            config = ComboConfig.objects.get(action=action, is_active=True,
                                             tenant=tenant or getattr(user, "tenant", None))
        except ComboConfig.DoesNotExist:
            return {"multiplier": 1.0, "streak": 0, "combo_active": False}

        combo, created = UserCombo.objects.select_for_update().get_or_create(
            user=user, action=action,
            defaults={"tenant": tenant or getattr(user, "tenant", None)},
        )

        now = timezone.now()
        window_ok = not created and (
            (now - combo.last_action_at).total_seconds() <= config.window_seconds
        )

        if window_ok:
            combo.combo_streak += 1
        else:
            combo.combo_streak = 1

        multiplier = config.multiplier_at(combo.combo_streak)
        combo.current_multiplier = Decimal(str(multiplier))
        combo.last_action_at     = now
        combo.total_combos_ever += 1
        if combo.combo_streak > combo.max_streak_ever:
            combo.max_streak_ever = combo.combo_streak
        combo.save(update_fields=[
            "combo_streak", "current_multiplier", "last_action_at",
            "total_combos_ever", "max_streak_ever",
        ])

        logger.debug("Combo: user=%s action=%s streak=%d ×%.2f",
                     user.pk, action, combo.combo_streak, multiplier)
        return {
            "multiplier":   multiplier,
            "streak":       combo.combo_streak,
            "combo_active": combo.combo_streak > 1,
            "window_seconds": config.window_seconds,
        }

    @classmethod
    def apply_multiplier(cls, user, action: str, base_amount: Decimal) -> Decimal:
        """Apply combo multiplier to a coin/xp amount."""
        combo = UserCombo.objects.filter(user=user, action=action).first()
        if not combo:
            return base_amount
        return (base_amount * combo.current_multiplier).quantize(Decimal("1"))

    @classmethod
    def get_combo(cls, user, action: str) -> dict:
        combo = UserCombo.objects.filter(user=user, action=action).first()
        if not combo:
            return {"multiplier": 1.0, "streak": 0, "combo_active": False}
        active = combo.is_active()
        return {
            "multiplier":   float(combo.current_multiplier),
            "streak":       combo.combo_streak if active else 0,
            "combo_active": active,
            "max_streak":   combo.max_streak_ever,
        }


class EnergyService:

    @classmethod
    def get_energy(cls, user, tenant=None) -> UserEnergy:
        energy, _ = UserEnergy.objects.get_or_create(
            user=user,
            defaults={"tenant": tenant or getattr(user, "tenant", None), "current_energy": 100},
        )
        return energy

    @classmethod
    @transaction.atomic
    def spend(cls, user, action: str, tenant=None) -> dict:
        """
        Deduct energy for an action. Applies offline regen first.
        Raises ValueError if insufficient energy.
        """
        try:
            cost_obj = EnergyCost.objects.get(action=action, is_active=True)
            cost     = cost_obj.cost
        except EnergyCost.DoesNotExist:
            return {"energy_spent": 0, "energy_remaining": 100, "ok": True}

        energy   = UserEnergy.objects.select_for_update().get(user=user)
        current  = energy.compute_current()

        if current < cost:
            return {"ok": False, "error": f"Not enough energy (need {cost}, have {current})"}

        energy.current_energy = current - cost
        energy.total_spent   += cost
        energy.last_regen_at  = timezone.now()
        energy.save(update_fields=["current_energy", "total_spent", "last_regen_at"])

        return {"energy_spent": cost, "energy_remaining": energy.current_energy, "ok": True}

    @classmethod
    def refill(cls, user, amount: int = None, tenant=None):
        """Refill energy (admin action or item use)."""
        energy  = cls.get_energy(user, tenant)
        config  = EnergyConfig.objects.filter(is_active=True).first()
        max_e   = config.max_energy if config else 100
        energy.current_energy = min(max_e, energy.current_energy + (amount or max_e))
        energy.last_regen_at  = timezone.now()
        energy.save(update_fields=["current_energy", "last_regen_at"])
        return energy.current_energy

    @classmethod
    def sync_regen(cls, user) -> int:
        """Apply offline regen and persist. Returns new energy value."""
        energy  = UserEnergy.objects.select_for_update().get(user=user)
        current = energy.compute_current()
        energy.current_energy = current
        energy.last_regen_at  = timezone.now()
        energy.save(update_fields=["current_energy", "last_regen_at"])
        return current
