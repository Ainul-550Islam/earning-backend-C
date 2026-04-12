# api/publisher_tools/a_b_testing/placement_testing.py
"""Placement Testing — Position and placement A/B tests."""
from decimal import Decimal
from typing import List


def create_position_ab_test(publisher, site, positions: List[str]):
    """Site-এর position test।"""
    from api.publisher_tools.models import AdUnit
    units = AdUnit.objects.filter(site=site, status="active")
    if not units.exists():
        raise ValueError("No active ad units for this site.")
    unit = units.first()
    from .test_creator import create_placement_test
    return create_placement_test(publisher, unit, positions)


def get_best_position_by_revenue(site, days: int = 30) -> dict:
    """Revenue-based best position identify করে।"""
    from api.publisher_tools.models import AdPlacement, PublisherEarning
    from django.db.models import Sum, Avg
    from django.utils import timezone
    from datetime import timedelta
    start = timezone.now().date() - timedelta(days=days)
    data = list(
        AdPlacement.objects.filter(ad_unit__site=site, is_active=True)
        .values("position")
        .annotate(
            revenue=Sum("total_revenue"),
            impressions=Sum("total_impressions"),
            viewability=Avg("avg_viewability"),
        )
        .order_by("-revenue")[:5]
    )
    return {
        "site_id": site.site_id,
        "best_positions": data,
        "recommended": data[0]["position"] if data else "above_fold",
    }
