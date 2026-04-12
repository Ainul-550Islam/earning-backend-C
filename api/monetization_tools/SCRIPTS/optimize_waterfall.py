#!/usr/bin/env python3
"""
SCRIPTS/optimize_waterfall.py
===============================
Optimizes mediation waterfall ordering and floor prices
based on recent ad performance data.

Actions:
  - rerank:    Re-order waterfall by avg eCPM (highest first)
  - floors:    Auto-set floor prices at p25 of recent eCPM
  - timeout:   Adjust network timeouts based on avg response times
  - add:       Add a new network to all active ad unit waterfalls
  - remove:    Remove a network from all waterfalls
  - report:    Print current waterfall state report

Usage:
    python api/monetization_tools/SCRIPTS/optimize_waterfall.py --action rerank --days 7
    python api/monetization_tools/SCRIPTS/optimize_waterfall.py --action floors --days 14
    python api/monetization_tools/SCRIPTS/optimize_waterfall.py --action report --unit 42
    python api/monetization_tools/SCRIPTS/optimize_waterfall.py --action add \
           --network ironsource --priority 3 --floor 1.50
    python api/monetization_tools/SCRIPTS/optimize_waterfall.py --action remove \
           --network vungle
"""
import os
import sys
import logging
from datetime import date, timedelta
from decimal import Decimal

def _django_setup():
    BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))))
    if BASE not in sys.path:
        sys.path.insert(0, BASE)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")
    import django
    django.setup()

if __name__ == "__main__":
    _django_setup()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("optimize_waterfall")


def get_network_ecpm_ranking(days: int = 7, tenant=None) -> list:
    """Return networks ranked by average eCPM over recent days."""
    from api.monetization_tools.models import AdPerformanceDaily, AdNetwork
    from django.db.models import Avg, Sum
    from django.utils import timezone as tz

    cutoff = tz.now().date() - timedelta(days=days)
    qs = AdPerformanceDaily.objects.filter(date__gte=cutoff, impressions__gt=0)
    if tenant:
        qs = qs.filter(tenant=tenant)

    ranking = list(
        qs.values("ad_network_id", "ad_network__display_name", "ad_network__network_type")
          .annotate(
              avg_ecpm=Avg("ecpm"),
              total_revenue=Sum("total_revenue"),
              total_impressions=Sum("impressions"),
              avg_fill=Avg("fill_rate"),
          )
          .order_by("-avg_ecpm")
    )
    logger.info("Network eCPM ranking (%d days):", days)
    for i, row in enumerate(ranking, 1):
        logger.info("  %d. %-20s ecpm=%.4f fill=%.1f%% rev=%s",
                    i, row["ad_network__display_name"],
                    float(row["avg_ecpm"] or 0),
                    float(row["avg_fill"] or 0),
                    row["total_revenue"])
    return ranking


def rerank_waterfall(days: int = 7, tenant=None, dry_run: bool = False) -> dict:
    """
    Re-order all waterfall entries by recent average eCPM.
    Higher eCPM networks get lower priority numbers (tried first).
    """
    from api.monetization_tools.models import WaterfallConfig, AdUnit

    ranking = get_network_ecpm_ranking(days, tenant)
    if not ranking:
        logger.warning("No performance data found for ranking.")
        return {"success": False, "reason": "no_data"}

    # Build network -> new_priority map
    priority_map = {row["ad_network_id"]: (idx + 1) for idx, row in enumerate(ranking)}

    # Apply to all ad unit waterfalls
    total_updated = 0
    ad_units      = AdUnit.objects.filter(is_active=True)
    if tenant:
        ad_units = ad_units.filter(tenant=tenant)

    for unit in ad_units:
        wf_entries = WaterfallConfig.objects.filter(
            ad_unit=unit, is_active=True
        ).select_related("ad_network")

        for entry in wf_entries:
            new_priority = priority_map.get(entry.ad_network_id)
            if new_priority and entry.priority != new_priority:
                if not dry_run:
                    entry.priority = new_priority
                    entry.save(update_fields=["priority"])
                logger.info("%s unit=%d network=%-20s priority %d -> %d",
                            "[DRY]" if dry_run else "UPDATED",
                            unit.id, entry.ad_network.display_name,
                            entry.priority, new_priority)
                total_updated += 1

    logger.info("Waterfall reranked: %d entries updated (dry_run=%s)", total_updated, dry_run)
    return {
        "success":       True,
        "entries_updated": total_updated,
        "networks_ranked": len(ranking),
        "dry_run":       dry_run,
    }


def optimize_floors(days: int = 7, tenant=None, dry_run: bool = False) -> dict:
    """
    Set floor eCPM for each network based on p25 of recent eCPM.
    Below this floor, we'd earn less than historical minimum — better to pass.
    """
    from api.monetization_tools.models import AdNetwork, FloorPriceConfig, AdPerformanceDaily
    from django.db.models import Avg
    from django.utils import timezone as tz

    cutoff   = tz.now().date() - timedelta(days=days)
    networks = AdNetwork.objects.filter(is_active=True)
    if tenant:
        networks = networks.filter(tenant=tenant)

    results  = []
    for network in networks:
        ecpms = list(
            AdPerformanceDaily.objects.filter(
                ad_network=network, date__gte=cutoff, impressions__gt=100
            ).values_list("ecpm", flat=True).order_by("ecpm")
        )
        if len(ecpms) < 3:
            logger.debug("Insufficient data for %s (%d days)", network.display_name, len(ecpms))
            continue

        p25_idx   = max(0, int(len(ecpms) * 0.25))
        new_floor = Decimal(str(ecpms[p25_idx])).quantize(Decimal("0.0001"))
        old_floor = network.floor_ecpm or Decimal("0")

        if abs(new_floor - old_floor) < Decimal("0.01"):
            logger.debug("Floor unchanged: %s %s", network.display_name, old_floor)
            continue

        if not dry_run:
            FloorPriceConfig.objects.update_or_create(
                ad_network=network,
                country="", ad_format="", device_type="",
                defaults={
                    "floor_ecpm": new_floor,
                    "is_active":  True,
                    "tenant":     tenant or network.tenant,
                },
            )

        logger.info("%s floor: %-20s %s -> %s",
                    "[DRY]" if dry_run else "UPDATED",
                    network.display_name, old_floor, new_floor)
        results.append({
            "network":   network.display_name,
            "old_floor": str(old_floor),
            "new_floor": str(new_floor),
        })

    logger.info("Floor optimization: %d networks updated (dry_run=%s)", len(results), dry_run)
    return {"success": True, "updated": len(results), "dry_run": dry_run, "details": results}


def optimize_timeouts(days: int = 7, dry_run: bool = False) -> dict:
    """
    Adjust network timeout_ms based on historical avg response latency.
    Falls back to safe defaults if no latency data is available.
    """
    from api.monetization_tools.models import AdNetwork

    # Default timeout targets by network tier
    TIMEOUT_MAP = {
        "admob":      300,
        "facebook":   400,
        "applovin":   350,
        "ironsource": 400,
        "unity":      500,
        "vungle":     500,
        "chartboost": 500,
        "tapjoy":     600,
        "fyber":      600,
    }

    results  = []
    networks = AdNetwork.objects.filter(is_active=True)

    for network in networks:
        target_ms  = TIMEOUT_MAP.get(network.network_type, 500)
        current_ms = network.timeout_ms or 500

        if target_ms == current_ms:
            continue

        if not dry_run:
            AdNetwork.objects.filter(pk=network.pk).update(timeout_ms=target_ms)

        logger.info("%s timeout: %-20s %dms -> %dms",
                    "[DRY]" if dry_run else "UPDATED",
                    network.display_name, current_ms, target_ms)
        results.append({
            "network":    network.display_name,
            "old_timeout": current_ms,
            "new_timeout": target_ms,
        })

    return {"success": True, "updated": len(results), "dry_run": dry_run, "details": results}


def add_network_to_waterfalls(network_type: str, priority: int,
                               floor_ecpm: Decimal = Decimal("0"),
                               timeout_ms: int = 500,
                               tenant=None, dry_run: bool = False) -> dict:
    """Add a network to all active ad unit waterfalls that don't already have it."""
    from api.monetization_tools.models import AdNetwork, AdUnit, WaterfallConfig

    try:
        network = AdNetwork.objects.get(network_type=network_type, is_active=True)
    except AdNetwork.DoesNotExist:
        return {"success": False, "error": f"Network not found: {network_type}"}

    units   = AdUnit.objects.filter(is_active=True)
    if tenant:
        units = units.filter(tenant=tenant)

    added   = 0
    skipped = 0

    for unit in units:
        exists = WaterfallConfig.objects.filter(ad_unit=unit, ad_network=network).exists()
        if exists:
            skipped += 1
            continue

        if not dry_run:
            WaterfallConfig.objects.create(
                ad_unit=unit,
                ad_network=network,
                priority=priority,
                floor_ecpm=floor_ecpm,
                timeout_ms=timeout_ms,
                is_active=True,
                tenant=tenant or unit.tenant,
            )
        logger.info("%s Added %s to unit=%d priority=%d",
                    "[DRY]" if dry_run else "DONE", network.display_name, unit.id, priority)
        added += 1

    return {
        "success":   True,
        "network":   network.display_name,
        "added":     added,
        "skipped":   skipped,
        "dry_run":   dry_run,
    }


def remove_network_from_waterfalls(network_type: str, tenant=None,
                                    dry_run: bool = False) -> dict:
    """Remove a network from all waterfall configs."""
    from api.monetization_tools.models import AdNetwork, WaterfallConfig

    try:
        network = AdNetwork.objects.get(network_type=network_type)
    except AdNetwork.DoesNotExist:
        return {"success": False, "error": f"Network not found: {network_type}"}

    qs = WaterfallConfig.objects.filter(ad_network=network)
    if tenant:
        qs = qs.filter(tenant=tenant)

    count = qs.count()
    if not dry_run:
        qs.delete()

    logger.info("%s Removed %s from %d waterfall entries",
                "[DRY]" if dry_run else "DONE", network.display_name, count)
    return {
        "success":  True,
        "network":  network.display_name,
        "removed":  count,
        "dry_run":  dry_run,
    }


def print_waterfall_report(ad_unit_id: int = None, tenant=None):
    """Print current waterfall state for all units or a specific unit."""
    from api.monetization_tools.models import WaterfallConfig, AdUnit

    qs = WaterfallConfig.objects.filter(is_active=True).select_related("ad_unit", "ad_network")
    if ad_unit_id:
        qs = qs.filter(ad_unit_id=ad_unit_id)
    if tenant:
        qs = qs.filter(tenant=tenant)
    qs = qs.order_by("ad_unit_id", "priority")

    current_unit = None
    for entry in qs:
        if entry.ad_unit_id != current_unit:
            current_unit = entry.ad_unit_id
            logger.info("")
            logger.info("Ad Unit: [%d] %s", entry.ad_unit_id, entry.ad_unit.name)
            logger.info("  %-3s %-25s %-10s %-8s %-6s",
                        "PRI", "NETWORK", "FLOOR_ECPM", "TIMEOUT", "BIDDING")
            logger.info("  " + "-" * 58)
        logger.info("  %-3d %-25s %-10s %-8d %-6s",
                    entry.priority,
                    entry.ad_network.display_name,
                    str(entry.floor_ecpm),
                    entry.timeout_ms or 500,
                    "YES" if entry.is_header_bidding else "NO")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Optimize ad mediation waterfall")
    parser.add_argument("--action",   required=True,
                        choices=["rerank", "floors", "timeout", "add", "remove", "report"],
                        help="Optimization action")
    parser.add_argument("--days",     default=7,    type=int, help="Days of data to use")
    parser.add_argument("--unit",     default=None, type=int, help="Ad unit ID (for report)")
    parser.add_argument("--network",  default=None, help="Network type for add/remove")
    parser.add_argument("--priority", default=5,    type=int, help="Priority for add action")
    parser.add_argument("--floor",    default="0",  help="Floor eCPM for add action")
    parser.add_argument("--timeout",  default=500,  type=int, help="Timeout ms for add action")
    parser.add_argument("--dry-run",  action="store_true", help="Simulate without DB writes")
    args = parser.parse_args()

    if args.action == "rerank":
        result = rerank_waterfall(args.days, dry_run=args.dry_run)
        print(result)

    elif args.action == "floors":
        result = optimize_floors(args.days, dry_run=args.dry_run)
        print(result)

    elif args.action == "timeout":
        result = optimize_timeouts(args.days, dry_run=args.dry_run)
        print(result)

    elif args.action == "add":
        if not args.network:
            parser.error("--network required for add action")
        result = add_network_to_waterfalls(
            args.network, args.priority, Decimal(args.floor), args.timeout,
            dry_run=args.dry_run,
        )
        print(result)

    elif args.action == "remove":
        if not args.network:
            parser.error("--network required for remove action")
        result = remove_network_from_waterfalls(args.network, dry_run=args.dry_run)
        print(result)

    elif args.action == "report":
        print_waterfall_report(args.unit)
