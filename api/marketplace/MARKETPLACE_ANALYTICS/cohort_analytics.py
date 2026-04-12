"""
MARKETPLACE_ANALYTICS/cohort_analytics.py — Monthly Cohort Analysis
"""
from django.db.models import Count, Min
from django.db.models.functions import TruncMonth
from django.utils import timezone


def monthly_cohort_table(tenant, months: int = 6) -> dict:
    """
    Returns cohort table: for each acquisition month, how many users
    returned in month+1, month+2, etc.
    """
    from api.marketplace.models import Order

    since = timezone.now() - timezone.timedelta(days=months * 30)

    # Get all users + their first order month
    first_orders = (
        Order.objects.filter(tenant=tenant, created_at__gte=since)
        .values("user")
        .annotate(cohort_month=TruncMonth(Min("created_at")))
    )

    cohort_data = {}
    for row in first_orders:
        month = row["cohort_month"].strftime("%Y-%m")
        cohort_data.setdefault(month, set()).add(row["user"])

    # Count returning users per cohort per subsequent month
    all_orders = (
        Order.objects.filter(tenant=tenant, created_at__gte=since)
        .annotate(order_month=TruncMonth("created_at"))
        .values("user","order_month")
    )
    user_months = {}
    for row in all_orders:
        user_months.setdefault(row["user"], set()).add(row["order_month"].strftime("%Y-%m"))

    result = {}
    for cohort_month, users in sorted(cohort_data.items()):
        result[cohort_month] = {
            "cohort_size": len(users),
            "retention":   {}
        }
        for i in range(1, months + 1):
            from datetime import datetime
            import calendar
            y, m = map(int, cohort_month.split("-"))
            m += i
            if m > 12:
                m -= 12; y += 1
            target_month = f"{y:04d}-{m:02d}"
            retained = sum(1 for u in users if target_month in user_months.get(u, set()))
            result[cohort_month]["retention"][f"month_{i}"] = {
                "count":   retained,
                "percent": round(retained / len(users) * 100, 1) if users else 0,
            }

    return result
