#!/usr/bin/env python3
"""
SCRIPTS/update_ad_config.py
============================
Updates ad configuration at runtime:
  - Floor prices per network / country / format
  - Waterfall priorities
  - Campaign daily budgets
  - MonetizationConfig feature flags
  - FloorPriceConfig bulk updates

Usage:
    python api/monetization_tools/SCRIPTS/update_ad_config.py --action floor_price \
           --network admob --country US --format rewarded_video --ecpm 3.50
    python api/monetization_tools/SCRIPTS/update_ad_config.py --action waterfall \
           --unit 42 --priorities "admob:1,ironsource:2,facebook:3"
    python api/monetization_tools/SCRIPTS/update_ad_config.py --action feature \
           --flag spin_wheel_enabled --value true
    python api/monetization_tools/SCRIPTS/update_ad_config.py --action auto_optimize
"""
import os
import sys
import logging
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
logger = logging.getLogger("update_ad_config")


# ── Action: Update floor price ────────────────────────────────────────────────
def update_floor_price(network_type: str, ecpm: Decimal,
                        country: str = None, ad_format: str = None,
                        device_type: str = None, tenant=None) -> dict:
    """
    Set or update floor eCPM for a network, optionally scoped to
    country, ad_format, and device_type.
    """
    from api.monetization_tools.models import AdNetwork, FloorPriceConfig

    try:
        network = AdNetwork.objects.get(network_type=network_type, is_active=True)
    except AdNetwork.DoesNotExist:
        logger.error("Network not found: %s", network_type)
        return {"success": False, "error": f"Network not found: {network_type}"}
    except AdNetwork.MultipleObjectsReturned:
        network = AdNetwork.objects.filter(network_type=network_type, is_active=True).first()

    obj, created = FloorPriceConfig.objects.update_or_create(
        ad_network=network,
        country=country or "",
        ad_format=ad_format or "",
        device_type=device_type or "",
        defaults={
            "floor_ecpm": ecpm,
            "is_active":  True,
            "tenant":     tenant or network.tenant,
        },
    )

    action = "Created" if created else "Updated"
    logger.info(
        "%s floor price: network=%s country=%s format=%s device=%s ecpm=%s",
        action, network_type, country or "ALL", ad_format or "ALL",
        device_type or "ALL", ecpm,
    )
    return {
        "success":    True,
        "action":     action.lower(),
        "network":    network.display_name,
        "country":    country or "ALL",
        "ad_format":  ad_format or "ALL",
        "device_type": device_type or "ALL",
        "floor_ecpm": str(ecpm),
    }


def bulk_update_floor_prices(rules: list) -> dict:
    """
    Bulk-update floor prices.
    rules = [{"network": "admob", "country": "US", "ecpm": 3.50}, ...]
    """
    results = []
    for rule in rules:
        result = update_floor_price(
            network_type=rule["network"],
            ecpm=Decimal(str(rule["ecpm"])),
            country=rule.get("country"),
            ad_format=rule.get("format"),
            device_type=rule.get("device_type"),
        )
        results.append(result)
    success = sum(1 for r in results if r["success"])
    logger.info("Bulk floor price update: %d/%d succeeded", success, len(results))
    return {"total": len(results), "success": success, "results": results}


# ── Action: Update waterfall priority ────────────────────────────────────────
def update_waterfall(ad_unit_id: int, priorities: dict) -> dict:
    """
    Update waterfall network priorities for an ad unit.
    priorities = {"admob": 1, "ironsource": 2, "facebook": 3}
    """
    from api.monetization_tools.models import AdNetwork, WaterfallConfig

    updated = []
    errors  = []

    for network_type, priority in priorities.items():
        try:
            network = AdNetwork.objects.get(network_type=network_type)
        except AdNetwork.DoesNotExist:
            errors.append(f"Network not found: {network_type}")
            continue

        count = WaterfallConfig.objects.filter(
            ad_unit_id=ad_unit_id, ad_network=network
        ).update(priority=int(priority))

        if count:
            logger.info("Waterfall updated: unit=%d network=%s priority=%d",
                        ad_unit_id, network_type, priority)
            updated.append({"network": network_type, "priority": priority})
        else:
            logger.warning("Waterfall entry not found: unit=%d network=%s",
                           ad_unit_id, network_type)
            errors.append(f"Waterfall entry not found: unit={ad_unit_id} network={network_type}")

    return {"success": len(errors) == 0, "updated": updated, "errors": errors}


# ── Action: Update feature flag ───────────────────────────────────────────────
def update_feature_flag(flag_name: str, value: bool, tenant=None) -> dict:
    """
    Enable/disable a MonetizationConfig feature flag for a tenant.
    flag_name: e.g. 'spin_wheel_enabled', 'offerwall_enabled'
    """
    from api.monetization_tools.models import MonetizationConfig

    VALID_FLAGS = [
        "offerwall_enabled", "subscription_enabled", "spin_wheel_enabled",
        "scratch_card_enabled", "referral_enabled", "ab_testing_enabled",
        "flash_sale_enabled", "coupon_enabled", "daily_streak_enabled",
    ]

    if flag_name not in VALID_FLAGS:
        msg = f"Unknown flag: {flag_name}. Valid: {VALID_FLAGS}"
        logger.error(msg)
        return {"success": False, "error": msg}

    if tenant:
        configs = MonetizationConfig.objects.filter(tenant=tenant)
    else:
        configs = MonetizationConfig.objects.all()

    if not configs.exists():
        # Create default config
        cfg = MonetizationConfig.objects.create(tenant=tenant)
        configs = MonetizationConfig.objects.filter(pk=cfg.pk)

    count = configs.update(**{flag_name: value})

    # Invalidate config cache for all affected tenants
    from api.monetization_tools.services import MonetizationConfigService
    for cfg in configs:
        MonetizationConfigService.invalidate(cfg.tenant)

    logger.info("Feature flag updated: %s = %s (%d configs)", flag_name, value, count)
    return {"success": True, "flag": flag_name, "value": value, "configs_updated": count}


# ── Action: Auto-optimize floor prices ───────────────────────────────────────
def auto_optimize_floors(days: int = 7) -> dict:
    """
    Automatically adjust floor prices for all networks based on
    recent p25 eCPM performance data.
    """
    from api.monetization_tools.models import AdNetwork
    from api.monetization_tools.AD_NETWORKS.network_optimizer import NetworkOptimizer

    networks = AdNetwork.objects.filter(is_active=True)
    results  = []

    for network in networks:
        recommended = NetworkOptimizer.recommend_floor(network.id, days)
        if recommended <= 0:
            logger.debug("Skipping %s — insufficient data", network.display_name)
            continue

        # Only update if recommended floor is meaningfully different from current
        current = network.floor_ecpm or Decimal("0")
        if abs(recommended - current) < Decimal("0.05"):
            logger.debug("Floor unchanged for %s: %s", network.display_name, current)
            continue

        from api.monetization_tools.models import FloorPriceConfig
        FloorPriceConfig.objects.update_or_create(
            ad_network=network,
            country="", ad_format="", device_type="",
            defaults={"floor_ecpm": recommended, "is_active": True},
        )
        logger.info("Auto floor: %s %s -> %s", network.display_name, current, recommended)
        results.append({
            "network":  network.display_name,
            "old_floor": str(current),
            "new_floor": str(recommended),
        })

    # Also re-rank networks by recent eCPM performance
    updated_count = NetworkOptimizer.auto_adjust_priorities()
    logger.info("Network priorities re-ranked: %d networks", updated_count)

    return {
        "success":           True,
        "floors_updated":    len(results),
        "priority_rerankings": updated_count,
        "details":           results,
    }


# ── Action: Update campaign budget ───────────────────────────────────────────
def update_campaign_budget(campaign_id: int, total_budget: Decimal = None,
                            daily_budget: Decimal = None) -> dict:
    """Update total and/or daily budget for a campaign."""
    from api.monetization_tools.models import AdCampaign

    try:
        campaign = AdCampaign.objects.get(pk=campaign_id)
    except AdCampaign.DoesNotExist:
        return {"success": False, "error": f"Campaign {campaign_id} not found"}

    updates = {}
    if total_budget is not None:
        updates["total_budget"] = total_budget
    if daily_budget is not None:
        updates["daily_budget"] = daily_budget

    if not updates:
        return {"success": False, "error": "No budget values provided"}

    AdCampaign.objects.filter(pk=campaign_id).update(**updates)
    logger.info("Budget updated: campaign=%d total=%s daily=%s",
                campaign_id, total_budget, daily_budget)
    return {
        "success":      True,
        "campaign_id":  campaign_id,
        "campaign_name": campaign.name,
        "total_budget": str(total_budget) if total_budget else "unchanged",
        "daily_budget": str(daily_budget) if daily_budget else "unchanged",
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Update monetization ad config at runtime")
    parser.add_argument("--action", required=True,
                        choices=["floor_price", "waterfall", "feature", "auto_optimize", "budget"],
                        help="Config action to perform")

    # Floor price args
    parser.add_argument("--network",  default=None, help="Network type (e.g. admob)")
    parser.add_argument("--country",  default=None, help="Country code (e.g. US)")
    parser.add_argument("--format",   default=None, help="Ad format (e.g. rewarded_video)")
    parser.add_argument("--device",   default=None, help="Device type (e.g. mobile)")
    parser.add_argument("--ecpm",     default=None, help="Floor eCPM value")

    # Waterfall args
    parser.add_argument("--unit",       default=None, type=int, help="Ad unit ID")
    parser.add_argument("--priorities", default=None,
                        help="Comma-separated network:priority pairs (e.g. admob:1,facebook:2)")

    # Feature flag args
    parser.add_argument("--flag",  default=None, help="Feature flag name")
    parser.add_argument("--value", default=None, help="Feature flag value (true/false)")

    # Campaign budget args
    parser.add_argument("--campaign",     default=None, type=int, help="Campaign ID")
    parser.add_argument("--total-budget", default=None, help="New total budget")
    parser.add_argument("--daily-budget", default=None, help="New daily budget")

    # Shared args
    parser.add_argument("--days", default=7, type=int, help="Days of data for auto-optimize")

    args = parser.parse_args()

    if args.action == "floor_price":
        if not args.network or not args.ecpm:
            parser.error("--network and --ecpm are required for floor_price action")
        result = update_floor_price(
            network_type=args.network,
            ecpm=Decimal(args.ecpm),
            country=args.country,
            ad_format=args.format,
            device_type=args.device,
        )
        print(result)

    elif args.action == "waterfall":
        if not args.unit or not args.priorities:
            parser.error("--unit and --priorities are required for waterfall action")
        prios = {}
        for part in args.priorities.split(","):
            net, pri = part.strip().split(":")
            prios[net.strip()] = int(pri.strip())
        result = update_waterfall(args.unit, prios)
        print(result)

    elif args.action == "feature":
        if not args.flag or not args.value:
            parser.error("--flag and --value are required for feature action")
        val    = args.value.lower() in ("true", "1", "yes", "on")
        result = update_feature_flag(args.flag, val)
        print(result)

    elif args.action == "auto_optimize":
        result = auto_optimize_floors(args.days)
        print(result)

    elif args.action == "budget":
        if not args.campaign:
            parser.error("--campaign required for budget action")
        result = update_campaign_budget(
            campaign_id=args.campaign,
            total_budget=Decimal(args.total_budget) if args.total_budget else None,
            daily_budget=Decimal(args.daily_budget) if args.daily_budget else None,
        )
        print(result)
