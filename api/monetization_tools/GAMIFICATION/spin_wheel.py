"""GAMIFICATION/spin_wheel.py — Spin wheel game handler."""
from ..services import SpinWheelConfigService


class SpinWheel:
    @classmethod
    def spin(cls, user, tenant=None, ip: str = "") -> dict:
        return SpinWheelConfigService.play(user, "spin_wheel", ip)

    @classmethod
    def config(cls, tenant=None):
        return SpinWheelConfigService.get_active_config("spin_wheel", tenant)

    @classmethod
    def can_spin_today(cls, user) -> bool:
        from django.utils import timezone
        from ..models import SpinWheelLog
        cfg   = cls.config()
        if not cfg:
            return False
        today = SpinWheelLog.objects.filter(
            user=user, log_type="spin_wheel",
            played_at__date=timezone.now().date()
        ).count()
        return today < cfg.daily_limit

    @classmethod
    def daily_remaining(cls, user) -> int:
        from django.utils import timezone
        from ..models import SpinWheelLog
        cfg   = cls.config()
        if not cfg:
            return 0
        today = SpinWheelLog.objects.filter(
            user=user, log_type="spin_wheel",
            played_at__date=timezone.now().date()
        ).count()
        return max(0, cfg.daily_limit - today)
