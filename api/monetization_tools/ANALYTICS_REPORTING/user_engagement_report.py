"""ANALYTICS_REPORTING/user_engagement_report.py — User engagement analytics."""
from decimal import Decimal
from django.db.models import Sum, Count, Avg


class UserEngagementReport:
    @classmethod
    def dau_mau_ratio(cls, tenant=None) -> dict:
        from ..models import PointLedgerSnapshot
        from django.utils import timezone
        from datetime import timedelta
        now    = timezone.now().date()
        dau    = PointLedgerSnapshot.objects.filter(snapshot_date=now)
        mau    = PointLedgerSnapshot.objects.filter(snapshot_date__gte=now - timedelta(days=30))
        if tenant:
            dau = dau.filter(tenant=tenant)
            mau = mau.filter(tenant=tenant)
        dau_c  = dau.values("user").distinct().count()
        mau_c  = mau.values("user").distinct().count()
        ratio  = (Decimal(dau_c) / mau_c).quantize(Decimal("0.0001")) if mau_c else Decimal("0")
        return {"dau": dau_c, "mau": mau_c, "dau_mau_ratio": ratio}

    @classmethod
    def top_earners(cls, tenant=None, limit: int = 20) -> list:
        from ..models import RewardTransaction
        from django.db.models import Sum
        qs = RewardTransaction.objects.filter(amount__gt=0)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return list(
            qs.values("user__username", "user_id")
              .annotate(total_earned=Sum("amount"))
              .order_by("-total_earned")[:limit]
        )

    @classmethod
    def streak_distribution(cls, tenant=None) -> list:
        from ..models import DailyStreak
        qs = DailyStreak.objects.all()
        if tenant:
            qs = qs.filter(tenant=tenant)
        bins = [(0,1),(1,7),(7,14),(14,30),(30,90),(90,365),(365,9999)]
        result = []
        for low, high in bins:
            count = qs.filter(current_streak__gte=low, current_streak__lt=high).count()
            result.append({"range": f"{low}-{high-1}d", "count": count})
        return result
