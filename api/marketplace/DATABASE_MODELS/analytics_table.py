"""
DATABASE_MODELS/analytics_table.py — Analytics Data Reference
"""
from api.marketplace.MARKETPLACE_ANALYTICS.sales_analytics import sales_summary, daily_revenue, monthly_revenue
from api.marketplace.MARKETPLACE_ANALYTICS.revenue_analytics import revenue_by_category, platform_commission_collected
from api.marketplace.MARKETPLACE_ANALYTICS.marketplace_health import full_health_report
from api.marketplace.MARKETPLACE_ANALYTICS.buyer_analytics import buyer_overview, buyer_ltv


def full_analytics_snapshot(tenant, days: int = 30) -> dict:
    """One-call comprehensive analytics snapshot."""
    return {
        "sales":   sales_summary(tenant, None, None),
        "revenue": platform_commission_collected(tenant),
        "buyers":  buyer_overview(tenant, days),
        "health":  full_health_report(tenant),
    }


__all__ = [
    "sales_summary","daily_revenue","monthly_revenue",
    "revenue_by_category","platform_commission_collected",
    "full_health_report","buyer_overview","buyer_ltv",
    "full_analytics_snapshot",
]
