"""
MARKETPLACE_ANALYTICS/retention_analytics.py — Customer Retention Analysis
"""
from django.db.models import Count, Min, Max
from django.utils import timezone


def retention_rate(tenant, cohort_days: int = 30, return_window: int = 60) -> dict:
    from api.marketplace.models import Order
    since   = timezone.now() - timezone.timedelta(days=cohort_days + return_window)
    cohort_end = timezone.now() - timezone.timedelta(days=return_window)

    first_orders = (
        Order.objects.filter(tenant=tenant, created_at__gte=since, created_at__lt=cohort_end)
        .values("user")
        .annotate(first_order=Min("created_at"))
    )
    cohort_users = {o["user"] for o in first_orders}
    if not cohort_users:
        return {"cohort_size": 0, "returned": 0, "retention_rate": 0}

    returned = Order.objects.filter(
        tenant=tenant,
        user__in=cohort_users,
        created_at__gte=cohort_end,
    ).values("user").distinct().count()

    return {
        "cohort_size":    len(cohort_users),
        "returned":       returned,
        "retention_rate": round(returned / len(cohort_users) * 100, 1),
    }


def churn_risk_users(tenant, inactive_days: int = 60) -> list:
    from api.marketplace.models import Order
    from django.contrib.auth import get_user_model
    User = get_user_model()
    cutoff = timezone.now() - timezone.timedelta(days=inactive_days)
    at_risk = (
        Order.objects.filter(tenant=tenant)
        .values("user")
        .annotate(last_order=Max("created_at"))
        .filter(last_order__lt=cutoff)
        .order_by("last_order")[:100]
    )
    return list(at_risk)


def avg_days_between_orders(tenant) -> float:
    from api.marketplace.models import Order
    orders = (
        Order.objects.filter(tenant=tenant)
        .values("user")
        .annotate(cnt=Count("id"), first=Min("created_at"), last=Max("created_at"))
        .filter(cnt__gte=2)
    )
    if not orders:
        return 0
    total_days = sum(
        (o["last"] - o["first"]).days / (o["cnt"] - 1)
        for o in orders
    )
    return round(total_days / len(orders), 1)
