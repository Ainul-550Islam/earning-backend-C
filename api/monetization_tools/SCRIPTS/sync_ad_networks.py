#!/usr/bin/env python3
"""
SCRIPTS/sync_ad_networks.py
============================
Management command script: syncs daily stats from all active ad networks.
Fetches reporting API data and stores in AdNetworkDailyStat.

Usage:
    python manage.py shell -c "exec(open('api/monetization_tools/SCRIPTS/sync_ad_networks.py').read())"
    OR run as standalone after django.setup():
    python api/monetization_tools/SCRIPTS/sync_ad_networks.py
"""
import os
import sys
import logging
from datetime import date, timedelta
from decimal import Decimal

# ── Django setup (standalone mode) ───────────────────────────────────────────
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

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("sync_ad_networks")


# ── Network driver registry ───────────────────────────────────────────────────
NETWORK_DRIVERS = {
    "admob":       "api.monetization_tools.AD_NETWORKS.admob_integration.AdMobIntegration",
    "facebook":    "api.monetization_tools.AD_NETWORKS.facebook_audience.FacebookAudienceNetwork",
    "applovin":    "api.monetization_tools.AD_NETWORKS.applovin_integration.AppLovinIntegration",
    "unity":       "api.monetization_tools.AD_NETWORKS.unity_ads_integration.UnityAdsIntegration",
    "ironsource":  "api.monetization_tools.AD_NETWORKS.ironSource_integration.IronSourceIntegration",
    "vungle":      "api.monetization_tools.AD_NETWORKS.vungle_integration.VungleIntegration",
    "chartboost":  "api.monetization_tools.AD_NETWORKS.chartboost_integration.ChartboostIntegration",
    "tapjoy":      "api.monetization_tools.AD_NETWORKS.tapjoy_integration.TapjoyIntegration",
    "fyber":       "api.monetization_tools.AD_NETWORKS.fyber_integration.FyberIntegration",
}


def _load_driver_class(dotted_path: str):
    """Dynamically load a driver class from dotted path string."""
    module_path, class_name = dotted_path.rsplit(".", 1)
    import importlib
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def sync_network(network, target_date: date) -> dict:
    """
    Sync reporting data for a single ad network for a given date.
    Returns dict with success status and stats.
    """
    from api.monetization_tools.models import AdNetworkDailyStat
    from django.utils import timezone as tz

    driver_path = NETWORK_DRIVERS.get(network.network_type)
    if not driver_path:
        logger.warning("No driver for network type: %s", network.network_type)
        return {"network": network.display_name, "status": "skipped", "reason": "no_driver"}

    try:
        DriverClass = _load_driver_class(driver_path)
        driver      = DriverClass(network)
        date_str    = target_date.isoformat()
        report_data = driver.fetch_reporting(date_str)

        # Upsert into AdNetworkDailyStat
        stat, created = AdNetworkDailyStat.objects.update_or_create(
            ad_network=network,
            date=target_date,
            defaults={
                "reported_revenue":    Decimal(str(report_data.get("revenue", "0"))),
                "reported_ecpm":       Decimal(str(report_data.get("ecpm", "0"))),
                "reported_impressions": int(report_data.get("impressions", 0)),
                "fetched_at":          tz.now(),
                "tenant":              network.tenant,
            },
        )

        # Calculate discrepancy vs our own records
        from api.monetization_tools.models import AdPerformanceDaily
        from django.db.models import Sum, Avg
        internal = AdPerformanceDaily.objects.filter(
            ad_network=network, date=target_date
        ).aggregate(rev=Sum("total_revenue"), imp=Sum("impressions"), ecpm=Avg("ecpm"))

        our_revenue = internal["rev"] or Decimal("0")
        net_revenue = stat.reported_revenue or Decimal("0")
        if net_revenue > 0:
            disc = ((our_revenue - net_revenue) / net_revenue * 100).quantize(Decimal("0.01"))
        else:
            disc = Decimal("0")

        AdNetworkDailyStat.objects.filter(pk=stat.pk).update(discrepancy_pct=disc)

        logger.info(
            "Synced: %s | date=%s | reported_rev=%s | our_rev=%s | discrepancy=%.2f%%",
            network.display_name, date_str, net_revenue, our_revenue, disc,
        )
        return {
            "network":      network.display_name,
            "status":       "success",
            "date":         date_str,
            "reported_rev": str(net_revenue),
            "our_rev":      str(our_revenue),
            "discrepancy":  str(disc),
            "created":      created,
        }

    except Exception as exc:
        logger.error("Sync failed for %s: %s", network.display_name, exc)
        return {
            "network": network.display_name,
            "status":  "error",
            "error":   str(exc),
        }


def sync_all_networks(target_date: date = None, dry_run: bool = False) -> dict:
    """
    Sync all active ad networks for the target date.
    target_date defaults to yesterday.
    """
    from api.monetization_tools.models import AdNetwork

    if target_date is None:
        target_date = date.today() - timedelta(days=1)

    logger.info("="*60)
    logger.info("sync_ad_networks starting")
    logger.info("  Target date : %s", target_date)
    logger.info("  Dry run     : %s", dry_run)
    logger.info("="*60)

    networks = AdNetwork.objects.filter(is_active=True, reporting_api_key__isnull=False)
    logger.info("Found %d active networks with reporting keys", networks.count())

    results = {"date": str(target_date), "networks": [], "success": 0, "error": 0, "skipped": 0}

    for network in networks:
        if dry_run:
            logger.info("[DRY RUN] Would sync: %s", network.display_name)
            results["networks"].append({"network": network.display_name, "status": "dry_run"})
            continue

        result = sync_network(network, target_date)
        results["networks"].append(result)

        if result["status"] == "success":
            results["success"] += 1
        elif result["status"] == "error":
            results["error"] += 1
        else:
            results["skipped"] += 1

    logger.info("="*60)
    logger.info("DONE: success=%d error=%d skipped=%d",
                results["success"], results["error"], results["skipped"])
    logger.info("="*60)
    return results


def sync_date_range(start: date, end: date, dry_run: bool = False) -> list:
    """Sync multiple dates (e.g. backfill)."""
    results = []
    current = start
    while current <= end:
        logger.info("Processing date: %s", current)
        result = sync_all_networks(current, dry_run)
        results.append(result)
        current += timedelta(days=1)
    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Sync ad network reporting data")
    parser.add_argument("--date",      type=str, default=None,
                        help="Target date YYYY-MM-DD (default: yesterday)")
    parser.add_argument("--start",     type=str, default=None,
                        help="Start date for range sync YYYY-MM-DD")
    parser.add_argument("--end",       type=str, default=None,
                        help="End date for range sync YYYY-MM-DD")
    parser.add_argument("--dry-run",   action="store_true",
                        help="Log what would be synced without writing to DB")
    args = parser.parse_args()

    if args.start and args.end:
        start_d = date.fromisoformat(args.start)
        end_d   = date.fromisoformat(args.end)
        logger.info("Range sync: %s to %s", start_d, end_d)
        sync_date_range(start_d, end_d, args.dry_run)
    else:
        target = date.fromisoformat(args.date) if args.date else None
        sync_all_networks(target, args.dry_run)
