# api/publisher_tools/a_b_testing/network_testing.py
"""Network Testing — Ad network A/B and champion/challenger tests."""
from decimal import Decimal
from typing import List


def create_network_champion_challenger(publisher, ad_unit, champion_network, challenger_network, split: float = 20.0):
    """Champion vs challenger network test (80/20 split)。"""
    from .test_manager import ABTest, ABTestVariant
    test = ABTest.objects.create(
        publisher=publisher, ad_unit=ad_unit,
        name=f"Champion/Challenger: {champion_network.name} vs {challenger_network.name}",
        test_type="waterfall",
        hypothesis=f"Testing if {challenger_network.name} can outperform {champion_network.name}.",
        confidence_level=Decimal("90.00"), min_sample_size=5000,
    )
    ABTestVariant.objects.create(
        test=test, name=f"Champion: {champion_network.name}", is_control=True,
        traffic_split=Decimal(str(100-split)), config={"network_id": str(champion_network.id)},
    )
    ABTestVariant.objects.create(
        test=test, name=f"Challenger: {challenger_network.name}", is_control=False,
        traffic_split=Decimal(str(split)), config={"network_id": str(challenger_network.id)},
    )
    return test


def compare_network_performance(network_ids: List[str], days: int = 30) -> List[dict]:
    from api.publisher_tools.models import WaterfallItem
    from django.db.models import Avg, Sum
    from django.utils import timezone
    from datetime import timedelta
    start = timezone.now().date() - timedelta(days=days)
    results = []
    for network_id in network_ids:
        items = WaterfallItem.objects.filter(network_id=network_id, status="active")
        agg = items.aggregate(ecpm=Avg("avg_ecpm"), fill=Avg("fill_rate"), revenue=Sum("total_revenue"))
        results.append({"network_id": network_id, "avg_ecpm": float(agg.get("ecpm") or 0),
                         "avg_fill_rate": float(agg.get("fill") or 0), "total_revenue": float(agg.get("revenue") or 0)})
    return sorted(results, key=lambda x: x["avg_ecpm"], reverse=True)
