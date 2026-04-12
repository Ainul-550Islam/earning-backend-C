"""GAMIFICATION/scratch_card.py — Scratch card game handler."""
from ..services import SpinWheelConfigService


class ScratchCard:
    @classmethod
    def scratch(cls, user, tenant=None, ip: str = "") -> dict:
        return SpinWheelConfigService.play(user, "scratch_card", ip)

    @classmethod
    def config(cls, tenant=None):
        return SpinWheelConfigService.get_active_config("scratch_card", tenant)

    @classmethod
    def daily_remaining(cls, user) -> int:
        from django.utils import timezone
        from ..models import SpinWheelLog
        cfg = cls.config()
        if not cfg:
            return 0
        today = SpinWheelLog.objects.filter(
            user=user, log_type="scratch_card",
            played_at__date=timezone.now().date()
        ).count()
        return max(0, cfg.daily_limit - today)
