"""USER_MONETIZATION/user_retention_engine.py — User retention strategies."""
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta


class UserRetentionEngine:
    """Identifies at-risk users and applies retention incentives."""

    @classmethod
    def at_risk_users(cls, inactive_days: int = 7, tenant=None) -> list:
        from ..models import DailyStreak
        cutoff = timezone.now().date() - timedelta(days=inactive_days)
        qs = DailyStreak.objects.filter(
            last_login_date__lt=cutoff, current_streak__gte=3
        )
        if tenant:
            qs = qs.filter(tenant=tenant)
        return list(qs.select_related("user").values(
            "user_id", "user__username", "current_streak", "last_login_date"
        ))

    @classmethod
    def churn_risk_score(cls, user) -> float:
        from ..models import DailyStreak
        try:
            streak     = DailyStreak.objects.get(user=user)
            days_since = (timezone.now().date() - streak.last_login_date).days if streak.last_login_date else 30
            score      = min(1.0, days_since / 30)
            if streak.current_streak >= 30:
                score -= 0.2
            return max(0.0, score)
        except DailyStreak.DoesNotExist:
            return 0.8

    @classmethod
    def apply_win_back_bonus(cls, user, coins: Decimal, reason: str = "win_back") -> bool:
        try:
            from ..services import RewardService
            RewardService.credit(user, coins, transaction_type="promotion", description=reason)
            return True
        except Exception:
            return False
