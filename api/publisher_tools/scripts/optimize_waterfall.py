#!/usr/bin/env python
# api/publisher_tools/scripts/optimize_waterfall.py
"""
Optimize Waterfall — Auto-optimize all mediation group waterfalls।
eCPM, fill rate, latency-based optimization।
"""
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)


def optimize_all_auto_groups():
    """auto_optimize=True সব groups-এর waterfall optimize করে।"""
    from api.publisher_tools.models import MediationGroup
    from api.publisher_tools.services import MediationService
    from datetime import timedelta
    cutoff = timezone.now() - timedelta(hours=24)
    from django.db.models import Q
    groups = MediationGroup.objects.filter(
        auto_optimize=True, is_active=True,
    ).filter(Q(last_optimized_at__isnull=True) | Q(last_optimized_at__lt=cutoff))
    optimized = 0
    errors    = 0
    for group in groups:
        try:
            result = MediationService.optimize_waterfall(group)
            optimized += 1
            print(f"  ✅ Optimized: {group.name} — {group.ad_unit.unit_id}")
        except Exception as e:
            errors += 1
            logger.error(f"Waterfall optimization error [{group.id}]: {e}")
    print(f"Waterfall optimization: {optimized} optimized, {errors} errors")
    return {"optimized": optimized, "errors": errors}


def update_floor_prices_auto():
    """Historical eCPM data-র ভিত্তিতে floor prices auto-update করে।"""
    from api.publisher_tools.models import Publisher
    from api.publisher_tools.mediation_management.floor_price_manager import bulk_update_floor_prices
    publishers = Publisher.objects.filter(status="active", tier__in=["premium","enterprise"])
    updated_total = 0
    for pub in publishers:
        try:
            result = bulk_update_floor_prices(pub, strategy="moderate")
            updated_total += result.get("units_updated", 0)
        except Exception as e:
            logger.error(f"Floor price update error [{pub.publisher_id}]: {e}")
    print(f"✅ Floor prices updated: {updated_total} ad units")
    return {"updated": updated_total}


def reorder_waterfalls_by_ecpm():
    """eCPM-based waterfall reorder করে।"""
    from api.publisher_tools.models import MediationGroup
    from api.publisher_tools.mediation_management.waterfall_manager import reorder_by_ecpm
    groups = MediationGroup.objects.filter(is_active=True)
    reordered = 0
    for group in groups:
        try:
            reorder_by_ecpm(group)
            reordered += 1
        except Exception as e:
            logger.error(f"Waterfall reorder error [{group.id}]: {e}")
    print(f"✅ Waterfalls reordered by eCPM: {reordered}")
    return {"reordered": reordered}


def analyze_network_performance():
    """Ad network performance summary।"""
    from api.publisher_tools.models import WaterfallItem
    from django.db.models import Avg, Sum
    summary = list(
        WaterfallItem.objects.filter(status="active", total_ad_requests__gte=1000)
        .values("network__name", "network__network_type")
        .annotate(
            avg_ecpm=Avg("avg_ecpm"), avg_fill=Avg("fill_rate"),
            avg_latency=Avg("avg_latency_ms"), total_rev=Sum("total_revenue"),
        ).order_by("-avg_ecpm")[:20]
    )
    print(f"✅ Network performance analyzed: {len(summary)} networks")
    return {"networks": summary}


def run():
    print(f"🔄 Waterfall optimization started at {timezone.now()}")
    return {
        "auto_optimized":  optimize_all_auto_groups(),
        "floor_prices":    update_floor_prices_auto(),
        "reordered":       reorder_waterfalls_by_ecpm(),
        "network_analysis":analyze_network_performance(),
        "completed_at":    timezone.now().isoformat(),
    }

if __name__ == "__main__":
    run()
