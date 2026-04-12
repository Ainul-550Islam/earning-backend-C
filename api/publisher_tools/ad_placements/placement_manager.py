# api/publisher_tools/ad_placements/placement_manager.py
"""Placement Manager — Central placement orchestration."""
from decimal import Decimal
from typing import List, Dict, Optional
from django.db import transaction
from django.utils import timezone
from django.db.models import Sum, Avg


def get_active_placements_for_site(site) -> List:
    from api.publisher_tools.models import AdPlacement, AdUnit
    return list(
        AdPlacement.objects.filter(
            ad_unit__site=site, is_active=True, ad_unit__status="active",
        ).select_related("ad_unit", "ad_unit__publisher").order_by("position")
    )


def get_active_placements_for_app(app) -> List:
    from api.publisher_tools.models import AdPlacement
    return list(
        AdPlacement.objects.filter(
            ad_unit__app=app, is_active=True, ad_unit__status="active",
        ).select_related("ad_unit").order_by("position")
    )


def get_placement_config(placement) -> Dict:
    """Placement-এর complete config — SDK/JS tag generation-এর জন্য।"""
    unit = placement.ad_unit
    return {
        "placement_id":   str(placement.id),
        "unit_id":        unit.unit_id,
        "format":         unit.format,
        "position":       placement.position,
        "size":           {"width": unit.width, "height": unit.height, "responsive": unit.is_responsive},
        "floor_price":    float(placement.effective_floor_price),
        "refresh":        {"enabled": placement.refresh_type != "none", "type": placement.refresh_type, "interval": placement.refresh_interval_seconds},
        "visibility":     {"mobile": placement.show_on_mobile, "tablet": placement.show_on_tablet, "desktop": placement.show_on_desktop},
        "viewability":    {"min_pct": placement.min_viewability_percentage},
        "css_selector":   placement.css_selector,
        "is_test_mode":   unit.is_test_mode,
    }


def toggle_placement(placement, is_active: bool) -> None:
    placement.is_active = is_active
    placement.save(update_fields=["is_active", "updated_at"])


def clone_placement(placement, new_name: str = None, new_position: str = None):
    """Placement clone করে নতুন position-এ।"""
    from api.publisher_tools.models import AdPlacement
    clone = AdPlacement.objects.create(
        ad_unit=placement.ad_unit,
        name=new_name or f"{placement.name} (Copy)",
        position=new_position or placement.position,
        is_active=False,
        show_on_mobile=placement.show_on_mobile,
        show_on_tablet=placement.show_on_tablet,
        show_on_desktop=placement.show_on_desktop,
        refresh_type=placement.refresh_type,
        refresh_interval_seconds=placement.refresh_interval_seconds,
        floor_price_override=placement.floor_price_override,
        min_viewability_percentage=placement.min_viewability_percentage,
        css_selector=placement.css_selector,
    )
    return clone


def get_placement_performance_summary(placement, days: int = 30) -> Dict:
    from api.publisher_tools.models import PublisherEarning
    from datetime import timedelta
    start = timezone.now().date() - timedelta(days=days)
    # Note: earning records don't directly link to placement, link via ad_unit
    agg = PublisherEarning.objects.filter(
        ad_unit=placement.ad_unit, date__gte=start,
    ).aggregate(
        revenue=Sum("publisher_revenue"), impressions=Sum("impressions"),
        clicks=Sum("clicks"), ecpm=Avg("ecpm"),
    )
    rev = agg.get("revenue") or Decimal("0")
    imp = agg.get("impressions") or 0
    return {
        "placement_id":  str(placement.id),
        "name":          placement.name,
        "position":      placement.position,
        "is_active":     placement.is_active,
        "revenue":       float(rev),
        "impressions":   imp,
        "clicks":        agg.get("clicks") or 0,
        "ecpm":          float(rev / imp * 1000) if imp > 0 else 0,
        "viewability":   float(placement.avg_viewability),
        "effective_floor": float(placement.effective_floor_price),
    }
