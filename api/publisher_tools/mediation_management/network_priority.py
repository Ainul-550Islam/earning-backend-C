# api/publisher_tools/mediation_management/network_priority.py
"""Network Priority — Dynamic network prioritization."""
from decimal import Decimal
from typing import List, Dict
from django.db.models import Avg, Sum
from django.utils import timezone
from datetime import timedelta


def calculate_network_priority_score(waterfall_item) -> float:
    """Network-এর priority score calculate করে।"""
    ecpm_score    = min(100, float(waterfall_item.avg_ecpm) / 5.0 * 100) * 0.50
    fill_score    = float(waterfall_item.fill_rate) * 0.30
    latency_score = max(0, 100 - waterfall_item.avg_latency_ms / 30) * 0.20
    return round(ecpm_score + fill_score + latency_score, 2)


def get_optimal_priorities(group) -> List[Dict]:
    """Mediation group-এর optimal network priorities।"""
    from api.publisher_tools.models import WaterfallItem
    items = list(group.waterfall_items.filter(status="active"))
    scored = [(item, calculate_network_priority_score(item)) for item in items]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [
        {"network": item.network.name, "current_priority": item.priority, "optimal_priority": i+1, "score": score, "needs_reorder": item.priority != i+1}
        for i, (item, score) in enumerate(scored)
    ]


def apply_optimal_priorities(group) -> int:
    """Optimal priorities apply করে। Returns number of items reordered."""
    from django.db import transaction
    optimal = get_optimal_priorities(group)
    count = 0
    with transaction.atomic():
        from api.publisher_tools.models import WaterfallItem
        for item_data in optimal:
            if item_data["needs_reorder"]:
                WaterfallItem.objects.filter(
                    mediation_group=group, network__name=item_data["network"]
                ).update(priority=item_data["optimal_priority"])
                count += 1
    return count


def detect_underperforming_networks(group, min_impressions: int = 1000) -> List[Dict]:
    """Underperforming networks identify করে।"""
    from api.publisher_tools.models import WaterfallItem
    issues = []
    for item in group.waterfall_items.filter(status="active"):
        if item.total_ad_requests < min_impressions:
            continue
        if float(item.fill_rate) < 10:
            issues.append({"network": item.network.name, "issue": "low_fill", "fill_rate": float(item.fill_rate), "recommendation": "Remove or pause"})
        if item.avg_latency_ms > 1500:
            issues.append({"network": item.network.name, "issue": "high_latency", "latency_ms": item.avg_latency_ms, "recommendation": "Move lower in waterfall"})
    return issues
