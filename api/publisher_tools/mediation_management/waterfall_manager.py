# api/publisher_tools/mediation_management/waterfall_manager.py
"""Waterfall Manager — Full waterfall lifecycle management."""
from decimal import Decimal
from typing import List, Dict
from django.db import transaction
from django.utils import timezone


def create_default_waterfall(ad_unit, networks: List = None) -> List:
    """Ad unit-এর জন্য default waterfall create করে।"""
    from api.publisher_tools.models import MediationGroup, WaterfallItem
    from api.ad_networks.models import AdNetwork
    group, created = MediationGroup.objects.get_or_create(
        ad_unit=ad_unit,
        defaults={"name": f"{ad_unit.name} — Waterfall", "mediation_type": "waterfall"},
    )
    if not created:
        return list(group.waterfall_items.filter(status="active").order_by("priority"))
    # Add default networks
    default_networks = networks or list(AdNetwork.objects.filter(is_active=True, category="offerwall")[:5])
    items = []
    for i, network in enumerate(default_networks, start=1):
        item = WaterfallItem.objects.create(
            mediation_group=group, network=network,
            name=f"{network.name} Tier {i}", priority=i,
            floor_ecpm=Decimal("0.0000"), bidding_type="dynamic", status="active",
        )
        items.append(item)
    return items


def reorder_by_ecpm(group) -> List:
    """eCPM-based waterfall reorder।"""
    from api.publisher_tools.models import WaterfallItem
    items = list(group.waterfall_items.filter(status="active").order_by("-avg_ecpm"))
    with transaction.atomic():
        for i, item in enumerate(items, start=1):
            item.priority = i
            item.save(update_fields=["priority", "updated_at"])
    return items


def get_waterfall_stats(group) -> Dict:
    from api.publisher_tools.models import WaterfallItem
    from django.db.models import Sum, Avg
    items = group.waterfall_items.filter(status="active")
    return {
        "group_id":    str(group.id),
        "name":        group.name,
        "item_count":  items.count(),
        "total_revenue": float(group.total_revenue),
        "avg_ecpm":    float(group.avg_ecpm),
        "fill_rate":   float(group.fill_rate),
        "items": [
            {"priority": item.priority, "network": item.network.name, "ecpm": float(item.avg_ecpm), "fill": float(item.fill_rate)}
            for item in items.order_by("priority")
        ],
    }


def validate_waterfall(group) -> Dict:
    """Waterfall configuration validate করে।"""
    from api.publisher_tools.models import WaterfallItem
    issues = []
    items = group.waterfall_items.filter(status="active").order_by("priority")
    if items.count() < 2:
        issues.append("At least 2 active networks required in waterfall.")
    priorities = list(items.values_list("priority", flat=True))
    if len(priorities) != len(set(priorities)):
        issues.append("Duplicate priorities detected.")
    for item in items:
        if not item.network_app_id and not item.network_unit_id:
            issues.append(f"{item.network.name}: No network credentials configured.")
    return {"valid": len(issues) == 0, "issues": issues, "item_count": items.count()}
