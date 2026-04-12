"""ANALYTICS_REPORTING/cohort_analysis.py — User cohort retention analysis."""
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta


class CohortAnalyzer:
    """Monthly cohort retention analysis."""

    @classmethod
    def retention(cls, cohort_month: str, months_out: int = 6) -> dict:
        """
        cohort_month: "2024-01"
        Returns retention rates for each subsequent month.
        """
        from django.contrib.auth import get_user_model
        from ..models import PointLedgerSnapshot
        year, month = map(int, cohort_month.split("-"))
        from calendar import monthrange
        from datetime import date
        _, last_day = monthrange(year, month)
        cohort_start = date(year, month, 1)
        cohort_end   = date(year, month, last_day)
        User = get_user_model()
        cohort_users = User.objects.filter(
            date_joined__date__gte=cohort_start,
            date_joined__date__lte=cohort_end,
        ).values_list("id", flat=True)
        cohort_size = len(cohort_users)
        result      = {"cohort": cohort_month, "size": cohort_size, "retention": []}
        for m in range(1, months_out + 1):
            check_month = date(year, month, 1) + timedelta(days=30 * m)
            active = PointLedgerSnapshot.objects.filter(
                user_id__in=cohort_users,
                snapshot_date__year=check_month.year,
                snapshot_date__month=check_month.month,
            ).values("user").distinct().count()
            rate = (Decimal(active) / cohort_size * 100).quantize(Decimal("0.01")) if cohort_size else Decimal("0")
            result["retention"].append({"month": m, "active": active, "rate": rate})
        return result
