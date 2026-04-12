#!/usr/bin/env python3
"""
SCRIPTS/clean_ad_cache.py
==========================
Clears stale monetization caches across all cache backends.
Supports targeted cache invalidation (by type, tenant, or pattern)
and full cache flush with safety guards.

Usage:
    python api/monetization_tools/SCRIPTS/clean_ad_cache.py --type all
    python api/monetization_tools/SCRIPTS/clean_ad_cache.py --type waterfall
    python api/monetization_tools/SCRIPTS/clean_ad_cache.py --type floor_prices
    python api/monetization_tools/SCRIPTS/clean_ad_cache.py --type offerwall
    python api/monetization_tools/SCRIPTS/clean_ad_cache.py --type subscriptions
    python api/monetization_tools/SCRIPTS/clean_ad_cache.py --type flash_sales
    python api/monetization_tools/SCRIPTS/clean_ad_cache.py --type config
    python api/monetization_tools/SCRIPTS/clean_ad_cache.py --type leaderboard
    python api/monetization_tools/SCRIPTS/clean_ad_cache.py --type user --user-id 42
    python api/monetization_tools/SCRIPTS/clean_ad_cache.py --list-patterns
"""
import os
import sys
import logging
from typing import Optional

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
logger = logging.getLogger("clean_ad_cache")

from django.core.cache import cache


# ── Cache key pattern registry ────────────────────────────────────────────────
CACHE_PATTERNS = {
    "waterfall":      ["mt:waterfall:*"],
    "floor_prices":   ["mt:floor:*"],
    "offerwall":      ["mt:ow_list:*", "mt:ow_active:*"],
    "subscriptions":  ["mt:sub_plans:*", "mt:user_sub:*"],
    "flash_sales":    ["mt:flash_sales:*", "mt:active_multiplier:*"],
    "config":         ["mt:config_*", "mt_config_*"],
    "leaderboard":    ["mt:leaderboard:*"],
    "spin_wheel":     ["mt:spin_config:*", "mt:spin_count:*"],
    "fraud_scores":   ["mt:fraud_score:*"],
    "referral":       ["mt:ref_link:*", "mt:ref_summary:*", "mt:ref_program:*"],
    "streak":         ["mt:streak:*"],
    "coupon":         ["mt:coupon:*"],
    "segment":        ["mt:seg_members:*"],
    "publisher":      ["mt:publisher:*"],
    "postback_dedup": ["mt:pb_dedup:*"],
    "real_time":      ["mt:rt_metrics:*", "mt:active_users_now"],
    "ad_unit":        ["mt:ad_unit:*"],
    "revenue_goals":  ["mt:rev_goal:*"],
}

ALL_PATTERNS = list(CACHE_PATTERNS.keys())


def _try_delete_pattern(pattern: str) -> int:
    """
    Try to delete keys matching pattern using Redis SCAN if available,
    otherwise fall back to individual key deletion.
    Returns number of keys deleted.
    """
    deleted = 0
    try:
        # Try Redis client via django-redis
        from django.core.cache import cache as c
        client = c.client.get_client()
        keys   = list(client.scan_iter(pattern))
        if keys:
            client.delete(*keys)
            deleted = len(keys)
            logger.info("Deleted %d keys matching: %s", deleted, pattern)
        else:
            logger.debug("No keys found for pattern: %s", pattern)
    except (AttributeError, ImportError, Exception) as exc:
        logger.debug("Pattern delete not supported (%s), trying direct keys", exc)
        # Fallback: try known key formats
        deleted = _fallback_delete(pattern)
    return deleted


def _fallback_delete(pattern: str) -> int:
    """
    Fallback key deletion for backends that don't support SCAN.
    Tries common key suffixes derived from the pattern.
    """
    from api.monetization_tools.models import AdUnit, AdNetwork
    deleted = 0
    prefix  = pattern.rstrip("*")

    if "mt:waterfall:" in prefix:
        units = AdUnit.objects.values_list("id", flat=True)
        for uid in units:
            cache.delete(f"mt:waterfall:{uid}")
            deleted += 1

    elif "mt:floor:" in prefix:
        nets = AdNetwork.objects.values_list("id", flat=True)
        for nid in nets:
            cache.delete(f"mt:floor:{nid}")
            deleted += 1

    elif "mt:config" in prefix:
        cache.delete("mt:config_none")
        deleted += 1

    return deleted


def clear_by_type(cache_type: str) -> dict:
    """Clear caches for a specific type."""
    if cache_type not in CACHE_PATTERNS:
        return {"success": False, "error": f"Unknown cache type: {cache_type}",
                "valid_types": list(CACHE_PATTERNS.keys())}

    patterns = CACHE_PATTERNS[cache_type]
    total    = 0
    for pattern in patterns:
        total += _try_delete_pattern(pattern)

    logger.info("Cache cleared: type=%s patterns=%d keys_deleted=%d",
                cache_type, len(patterns), total)
    return {"success": True, "type": cache_type, "patterns": patterns, "keys_deleted": total}


def clear_all_monetization_caches() -> dict:
    """Clear all monetization tool caches."""
    logger.info("Clearing ALL monetization caches...")
    total   = 0
    details = {}

    for cache_type, patterns in CACHE_PATTERNS.items():
        type_deleted = 0
        for pattern in patterns:
            type_deleted += _try_delete_pattern(pattern)
        details[cache_type] = type_deleted
        total += type_deleted

    # Also clear view cache keys
    view_keys = [
        "mt:view:offerwall_list", "mt:view:subscription_plans",
        "mt:view:leaderboard_global", "mt:view:flash_sales_live",
    ]
    for key in view_keys:
        cache.delete(key)
        total += 1

    logger.info("All monetization caches cleared. Total keys: %d", total)
    return {
        "success":       True,
        "total_deleted": total,
        "by_type":       details,
    }


def clear_user_caches(user_id: int) -> dict:
    """Clear all cache entries related to a specific user."""
    keys = [
        f"mt:user_sub:{user_id}",
        f"mt:streak:{user_id}",
        f"mt:fraud_score:{user_id}",
        f"mt:payout_pending:{user_id}",
        f"mt:ref_summary:{user_id}",
        f"mt:ref_link:{user_id}:*",
    ]
    deleted = 0
    for key in keys:
        if key.endswith("*"):
            deleted += _try_delete_pattern(key)
        else:
            cache.delete(key)
            deleted += 1

    # Also clear spin wheel daily counts
    from django.utils import timezone as tz
    date_str = tz.now().date().isoformat()
    for wtype in ("spin_wheel", "scratch_card"):
        cache.delete(f"mt:spin_count:{user_id}:{date_str}:{wtype}")
        deleted += 1

    logger.info("User caches cleared: user_id=%d keys=%d", user_id, deleted)
    return {"success": True, "user_id": user_id, "keys_deleted": deleted}


def clear_tenant_caches(tenant_id) -> dict:
    """Clear all cache entries for a specific tenant."""
    patterns = [
        f"mt:flash_sales:{tenant_id}",
        f"mt:active_multiplier:{tenant_id}",
        f"mt:spin_config:{tenant_id}",
        f"mt:rev_goal:{tenant_id}:*",
        f"mt:rt_metrics:{tenant_id}",
        f"mt_config_{tenant_id}",
    ]
    deleted = 0
    for pattern in patterns:
        if pattern.endswith("*"):
            deleted += _try_delete_pattern(pattern)
        else:
            cache.delete(pattern)
            deleted += 1

    logger.info("Tenant caches cleared: tenant=%s keys=%d", tenant_id, deleted)
    return {"success": True, "tenant_id": str(tenant_id), "keys_deleted": deleted}


def warm_critical_caches() -> dict:
    """
    Pre-warm frequently accessed caches after clearing.
    Loads active offerwalls, subscription plans, and waterfall configs into cache.
    """
    logger.info("Warming critical caches...")
    warmed = []

    try:
        from api.monetization_tools.cache import (
            get_active_offerwalls, get_subscription_plans, get_waterfall_config
        )

        # Offerwall list
        offerwalls = get_active_offerwalls()
        warmed.append(f"offerwall_list ({len(offerwalls)} walls)")

        # Subscription plans
        plans = get_subscription_plans()
        warmed.append(f"subscription_plans ({len(plans)} plans)")

        # Waterfall configs for active units
        from api.monetization_tools.models import AdUnit
        units = AdUnit.objects.filter(is_active=True)[:20]  # limit to first 20
        for unit in units:
            get_waterfall_config(unit.id)
        warmed.append(f"waterfall configs ({units.count()} units)")

    except Exception as exc:
        logger.warning("Cache warming partially failed: %s", exc)

    logger.info("Cache warming complete: %s", ", ".join(warmed))
    return {"success": True, "warmed": warmed}


def list_patterns():
    """Print all registered cache patterns."""
    logger.info("Registered monetization cache patterns:")
    for cache_type, patterns in CACHE_PATTERNS.items():
        for p in patterns:
            logger.info("  %-20s %s", cache_type, p)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Clean monetization tool caches")
    parser.add_argument("--type",          default=None,
                        help=f"Cache type: {', '.join(ALL_PATTERNS)}, all")
    parser.add_argument("--user-id",       default=None, type=int,
                        help="Clear caches for specific user ID")
    parser.add_argument("--tenant-id",     default=None,
                        help="Clear caches for specific tenant ID")
    parser.add_argument("--warm",          action="store_true",
                        help="Warm critical caches after clearing")
    parser.add_argument("--list-patterns", action="store_true",
                        help="List all registered cache patterns")
    parser.add_argument("--dry-run",       action="store_true",
                        help="Show what would be cleared without deleting")
    args = parser.parse_args()

    if args.list_patterns:
        list_patterns()
        sys.exit(0)

    if args.dry_run:
        logger.info("DRY RUN mode — no caches will be deleted")
        list_patterns()
        sys.exit(0)

    results = {}

    if args.user_id:
        results["user"] = clear_user_caches(args.user_id)

    if args.tenant_id:
        results["tenant"] = clear_tenant_caches(args.tenant_id)

    if args.type:
        if args.type == "all":
            results["all"] = clear_all_monetization_caches()
        elif args.type in CACHE_PATTERNS:
            results[args.type] = clear_by_type(args.type)
        else:
            logger.error("Unknown cache type: %s", args.type)
            logger.info("Valid types: %s", ", ".join(["all"] + ALL_PATTERNS))
            sys.exit(1)

    if not any([args.user_id, args.tenant_id, args.type]):
        logger.info("No action specified. Use --type, --user-id, or --tenant-id")
        logger.info("Use --list-patterns to see all cache patterns")
        parser.print_help()
        sys.exit(0)

    if args.warm:
        results["warm"] = warm_critical_caches()

    import json
    from decimal import Decimal
    class _Enc(json.JSONEncoder):
        def default(self, o):
            if isinstance(o, Decimal):
                return str(o)
            return super().default(o)

    print(json.dumps(results, indent=2, cls=_Enc))
