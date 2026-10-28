# engagement/models/combo.py
"""
Combo Multiplier System
Consecutive actions within a time window build a combo and multiply rewards.

Energy System
Users have energy (stamina) that regenerates over time.
Certain actions cost energy; running out slows progression.
"""
from django.db import models
from django.utils import timezone
from .base import TenantModel, UserEngagementModel


# ── Combo System ──────────────────────────────────────────────────────────────

class ComboConfig(TenantModel):
    """Platform-wide combo rules."""
    action          = models.CharField(max_length=50, unique=True)  # "checkin", "spin"
    window_seconds  = models.IntegerField(default=3600)     # must act within this window
    max_multiplier  = models.DecimalField(max_digits=4, decimal_places=2, default=3)
    step_multiplier = models.DecimalField(max_digits=4, decimal_places=2, default=0.25)
    is_active       = models.BooleanField(default=True)

    def multiplier_at(self, streak: int) -> float:
        m = 1.0 + float(self.step_multiplier) * (streak - 1)
        return min(m, float(self.max_multiplier))


class UserCombo(UserEngagementModel):
    """Live combo state per user per action."""
    action          = models.CharField(max_length=50, db_index=True)
    combo_streak    = models.IntegerField(default=0)
    current_multiplier = models.DecimalField(max_digits=4, decimal_places=2, default=1)
    last_action_at  = models.DateTimeField(auto_now_add=True)
    total_combos_ever = models.IntegerField(default=0)
    max_streak_ever   = models.IntegerField(default=0)

    class Meta:
        unique_together = ["user", "action"]

    def __str__(self):
        return f"{self.user} [{self.action}] streak={self.combo_streak} ×{self.current_multiplier}"

    def is_active(self) -> bool:
        """Check if combo window is still open."""
        try:
            config = ComboConfig.objects.get(action=self.action, is_active=True)
            delta  = (timezone.now() - self.last_action_at).total_seconds()
            return delta <= config.window_seconds
        except ComboConfig.DoesNotExist:
            return False


# ── Energy System ─────────────────────────────────────────────────────────────

class EnergyConfig(TenantModel):
    """Platform-wide energy rules."""
    max_energy       = models.IntegerField(default=100)
    regen_per_hour   = models.IntegerField(default=10)     # energy restored per hour
    is_active        = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at"]


class EnergyCost(TenantModel):
    """How much energy each action costs."""
    action     = models.CharField(max_length=50, unique=True)
    cost       = models.IntegerField(default=5)
    is_active  = models.BooleanField(default=True)


class UserEnergy(UserEngagementModel):
    """A user's live energy state."""
    current_energy   = models.IntegerField(default=100)
    max_energy       = models.IntegerField(default=100)
    last_regen_at    = models.DateTimeField(auto_now_add=True)
    total_spent      = models.IntegerField(default=0)

    class Meta:
        unique_together = []  # one row per user

    def __str__(self):
        return f"{self.user} energy={self.current_energy}/{self.max_energy}"

    def compute_current(self) -> int:
        """Apply offline regen and return true current energy."""
        try:
            config = EnergyConfig.objects.filter(is_active=True).first()
            if not config:
                return self.current_energy
            elapsed_hours = (timezone.now() - self.last_regen_at).total_seconds() / 3600
            regen = int(elapsed_hours * config.regen_per_hour)
            return min(self.max_energy, self.current_energy + regen)
        except Exception:
            return self.current_energy
