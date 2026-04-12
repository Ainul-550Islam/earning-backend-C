#!/usr/bin/env python3
"""
SCRIPTS/health_check.py
========================
Comprehensive health check for the monetization_tools app.
Verifies DB connectivity, cache, Celery, ad networks, model counts,
revenue pipeline, and fraud detection systems.

Exit codes:
  0 = All checks passed
  1 = One or more checks failed
  2 = Critical failure (DB or cache unreachable)

Usage:
    python api/monetization_tools/SCRIPTS/health_check.py
    python api/monetization_tools/SCRIPTS/health_check.py --verbose
    python api/monetization_tools/SCRIPTS/health_check.py --json
    python api/monetization_tools/SCRIPTS/health_check.py --check db cache celery
"""
import os
import sys
import json
import time
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
logger = logging.getLogger("health_check")


# ── Individual health checks ──────────────────────────────────────────────────

def check_database() -> dict:
    """Verify DB connectivity and basic ORM operations."""
    start = time.perf_counter()
    try:
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()

        # Check each model
        from api.monetization_tools.models import (
            AdNetwork, AdCampaign, AdUnit, Offer, MonetizationConfig
        )
        counts = {
            "ad_networks":  AdNetwork.objects.count(),
            "ad_campaigns": AdCampaign.objects.count(),
            "ad_units":     AdUnit.objects.count(),
            "offers":       Offer.objects.count(),
            "configs":      MonetizationConfig.objects.count(),
        }
        elapsed = (time.perf_counter() - start) * 1000

        return {
            "status":   "ok",
            "latency_ms": round(elapsed, 2),
            "counts":   counts,
        }
    except Exception as exc:
        return {"status": "fail", "error": str(exc)}


def check_cache() -> dict:
    """Verify cache backend connectivity and read/write."""
    from django.core.cache import cache
    start  = time.perf_counter()
    try:
        test_key = "mt:health_check_test"
        cache.set(test_key, "ok_value", 30)
        val     = cache.get(test_key)
        cache.delete(test_key)
        elapsed = (time.perf_counter() - start) * 1000
        if val != "ok_value":
            return {"status": "fail", "error": "Cache read/write mismatch"}
        return {"status": "ok", "latency_ms": round(elapsed, 2)}
    except Exception as exc:
        return {"status": "fail", "error": str(exc)}


def check_celery() -> dict:
    """Verify Celery task broker connectivity."""
    try:
        from celery import current_app
        inspector = current_app.control.inspect(timeout=5.0)
        active    = inspector.active()
        if active is None:
            return {"status": "warn", "message": "No Celery workers responding"}
        worker_count = len(active)
        return {
            "status":       "ok",
            "worker_count": worker_count,
            "workers":      list(active.keys()),
        }
    except Exception as exc:
        return {"status": "warn", "error": str(exc),
                "message": "Celery broker may be unavailable"}


def check_ad_networks() -> dict:
    """Check active ad networks configuration."""
    try:
        from api.monetization_tools.models import AdNetwork, WaterfallConfig
        networks  = AdNetwork.objects.filter(is_active=True)
        net_data  = []
        warnings  = []

        for network in networks:
            wf_count = WaterfallConfig.objects.filter(
                ad_network=network, is_active=True
            ).count()
            entry = {
                "name":       network.display_name,
                "type":       network.network_type,
                "priority":   network.priority,
                "floor_ecpm": str(network.floor_ecpm),
                "bidding":    network.is_bidding,
                "waterfall_entries": wf_count,
            }
            if not network.api_key and not network.app_id:
                warnings.append(f"{network.display_name}: no API key or app ID configured")
            net_data.append(entry)

        return {
            "status":          "ok" if not warnings else "warn",
            "active_count":    networks.count(),
            "networks":        net_data,
            "warnings":        warnings,
        }
    except Exception as exc:
        return {"status": "fail", "error": str(exc)}


def check_revenue_pipeline() -> dict:
    """Verify revenue calculation pipeline integrity."""
    try:
        from api.monetization_tools.models import (
            RevenueDailySummary, AdPerformanceDaily, ImpressionLog
        )
        from django.utils import timezone as tz
        today     = tz.now().date()
        yesterday = today - timedelta(days=1)

        summary_exists   = RevenueDailySummary.objects.filter(date=yesterday).exists()
        perf_exists      = AdPerformanceDaily.objects.filter(date=yesterday).exists()
        impressions_today = ImpressionLog.objects.filter(logged_at__date=today).count()

        warnings = []
        if not summary_exists:
            warnings.append(f"No RevenueDailySummary for {yesterday} — check calculate_revenue.py")
        if not perf_exists:
            warnings.append(f"No AdPerformanceDaily for {yesterday} — check aggregation tasks")

        return {
            "status":             "ok" if not warnings else "warn",
            "yesterday_summary":  summary_exists,
            "yesterday_perf":     perf_exists,
            "impressions_today":  impressions_today,
            "warnings":           warnings,
        }
    except Exception as exc:
        return {"status": "fail", "error": str(exc)}


def check_fraud_system() -> dict:
    """Check fraud detection system status."""
    try:
        from api.monetization_tools.models import FraudAlert
        from django.utils import timezone as tz
        from django.db.models import Count

        open_alerts    = FraudAlert.objects.filter(resolution="open").count()
        critical_open  = FraudAlert.objects.filter(resolution="open", severity="critical").count()
        today_alerts   = FraudAlert.objects.filter(created_at__date=tz.now().date()).count()

        warnings = []
        if critical_open > 0:
            warnings.append(f"{critical_open} CRITICAL fraud alerts open — immediate review required")
        if open_alerts > 50:
            warnings.append(f"{open_alerts} open fraud alerts — consider bulk review")

        return {
            "status":        "ok" if not warnings else "warn",
            "open_alerts":   open_alerts,
            "critical_open": critical_open,
            "today_alerts":  today_alerts,
            "warnings":      warnings,
        }
    except Exception as exc:
        return {"status": "fail", "error": str(exc)}


def check_payout_system() -> dict:
    """Check payout processing status."""
    try:
        from api.monetization_tools.models import PayoutRequest
        from django.utils import timezone as tz

        pending     = PayoutRequest.objects.filter(status="pending").count()
        approved    = PayoutRequest.objects.filter(status="approved").count()
        failed      = PayoutRequest.objects.filter(status="failed").count()
        today_count = PayoutRequest.objects.filter(created_at__date=tz.now().date()).count()

        warnings = []
        if pending > 100:
            warnings.append(f"{pending} pending payout requests — process queue may be backed up")
        if failed > 10:
            warnings.append(f"{failed} failed payout requests — review gateway errors")

        return {
            "status":   "ok" if not warnings else "warn",
            "pending":  pending,
            "approved": approved,
            "failed":   failed,
            "today":    today_count,
            "warnings": warnings,
        }
    except Exception as exc:
        return {"status": "fail", "error": str(exc)}


def check_offerwall() -> dict:
    """Check offerwall configuration and offer availability."""
    try:
        from api.monetization_tools.models import Offerwall, Offer
        from django.utils import timezone as tz

        active_walls  = Offerwall.objects.filter(is_active=True).count()
        active_offers = Offer.objects.filter(status="active").count()
        featured      = Offer.objects.filter(status="active", is_featured=True).count()
        expiring_soon = Offer.objects.filter(
            status="active",
            expiry_date__lte=tz.now() + timedelta(hours=24),
            expiry_date__gt=tz.now(),
        ).count()

        warnings = []
        if active_walls == 0:
            warnings.append("No active offerwalls — users cannot see offers")
        if active_offers == 0:
            warnings.append("No active offers — check offer status and expiry")
        if expiring_soon > 0:
            warnings.append(f"{expiring_soon} offers expiring in next 24 hours")

        return {
            "status":        "ok" if not warnings else "warn",
            "active_walls":  active_walls,
            "active_offers": active_offers,
            "featured":      featured,
            "expiring_24h":  expiring_soon,
            "warnings":      warnings,
        }
    except Exception as exc:
        return {"status": "fail", "error": str(exc)}


def check_subscriptions() -> dict:
    """Check subscription system status."""
    try:
        from api.monetization_tools.models import SubscriptionPlan, UserSubscription
        from django.utils import timezone as tz

        active_plans   = SubscriptionPlan.objects.filter(is_active=True).count()
        active_subs    = UserSubscription.objects.filter(
            status__in=["trial", "active"],
            current_period_end__gt=tz.now(),
        ).count()
        expiring_48h   = UserSubscription.objects.filter(
            status="active",
            current_period_end__lte=tz.now() + timedelta(hours=48),
            current_period_end__gt=tz.now(),
        ).count()

        warnings = []
        if active_plans == 0:
            warnings.append("No active subscription plans configured")

        return {
            "status":       "ok" if not warnings else "warn",
            "active_plans": active_plans,
            "active_subs":  active_subs,
            "expiring_48h": expiring_48h,
            "warnings":     warnings,
        }
    except Exception as exc:
        return {"status": "fail", "error": str(exc)}


def check_postback_queue() -> dict:
    """Check unprocessed postback log queue."""
    try:
        from api.monetization_tools.models import PostbackLog

        unprocessed = PostbackLog.objects.filter(status="received").count()
        error_count = PostbackLog.objects.filter(status="error").count()
        fraud_count = PostbackLog.objects.filter(status="fraud").count()

        warnings = []
        if unprocessed > 500:
            warnings.append(f"{unprocessed} unprocessed postbacks — celery task may be stuck")
        if error_count > 100:
            warnings.append(f"{error_count} postback errors — check network signatures")

        return {
            "status":       "ok" if not warnings else "warn",
            "unprocessed":  unprocessed,
            "errors":       error_count,
            "fraud":        fraud_count,
            "warnings":     warnings,
        }
    except Exception as exc:
        return {"status": "fail", "error": str(exc)}


# ── Master runner ─────────────────────────────────────────────────────────────

AVAILABLE_CHECKS = {
    "db":           check_database,
    "cache":        check_cache,
    "celery":       check_celery,
    "networks":     check_ad_networks,
    "revenue":      check_revenue_pipeline,
    "fraud":        check_fraud_system,
    "payouts":      check_payout_system,
    "offerwall":    check_offerwall,
    "subscriptions": check_subscriptions,
    "postback":     check_postback_queue,
}


def run_health_checks(checks: list = None, verbose: bool = False) -> dict:
    """Run the specified checks (or all if None) and return results."""
    checks_to_run = checks or list(AVAILABLE_CHECKS.keys())
    results       = {}
    overall_ok    = True
    has_critical  = False

    logger.info("=" * 60)
    logger.info("MONETIZATION TOOLS HEALTH CHECK")
    logger.info("Checks: %s", ", ".join(checks_to_run))
    logger.info("=" * 60)

    for name in checks_to_run:
        fn = AVAILABLE_CHECKS.get(name)
        if not fn:
            results[name] = {"status": "skip", "error": "Unknown check"}
            continue

        logger.info("Checking: %-20s ...", name)
        try:
            result = fn()
        except Exception as exc:
            result = {"status": "fail", "error": str(exc)}

        results[name] = result
        status        = result.get("status", "unknown")

        if status == "ok":
            indicator = "OK"
        elif status == "warn":
            indicator = "WARN"
            overall_ok = False
        elif status == "fail":
            indicator  = "FAIL"
            overall_ok = False
            if name in ("db", "cache"):
                has_critical = True
        else:
            indicator = "SKIP"

        logger.info("  [%s] %s", indicator, name)

        if verbose and status in ("warn", "fail"):
            for warning in result.get("warnings", []):
                logger.warning("       > %s", warning)
            if result.get("error"):
                logger.error("       > ERROR: %s", result["error"])

    logger.info("=" * 60)
    overall = "OK" if overall_ok else ("CRITICAL" if has_critical else "DEGRADED")
    logger.info("OVERALL STATUS: %s", overall)
    logger.info("=" * 60)

    return {
        "overall":       overall,
        "all_ok":        overall_ok,
        "has_critical":  has_critical,
        "checks":        results,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Monetization Tools Health Check")
    parser.add_argument("--check",   nargs="*", default=None,
                        help=f"Specific checks to run: {', '.join(AVAILABLE_CHECKS.keys())}")
    parser.add_argument("--verbose", action="store_true",
                        help="Show detailed warnings and errors")
    parser.add_argument("--json",    action="store_true",
                        help="Output results as JSON")
    parser.add_argument("--list",    action="store_true",
                        help="List available checks")
    args = parser.parse_args()

    if args.list:
        print("Available checks:")
        for name in AVAILABLE_CHECKS:
            print(f"  {name}")
        sys.exit(0)

    results = run_health_checks(args.check, args.verbose)

    if args.json:
        class _Enc(json.JSONEncoder):
            def default(self, o):
                if isinstance(o, Decimal):
                    return str(o)
                return super().default(o)
        print(json.dumps(results, indent=2, cls=_Enc))

    # Exit code
    if results["has_critical"]:
        sys.exit(2)
    elif not results["all_ok"]:
        sys.exit(1)
    else:
        sys.exit(0)
