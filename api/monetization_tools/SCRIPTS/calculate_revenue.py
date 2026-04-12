#!/usr/bin/env python3
"""
SCRIPTS/calculate_revenue.py
==============================
Recalculates and rebuilds RevenueDailySummary from raw ImpressionLog,
ClickLog, ConversionLog, InAppPurchase, and UserSubscription data.

Usage:
    python api/monetization_tools/SCRIPTS/calculate_revenue.py --date 2024-01-15
    python api/monetization_tools/SCRIPTS/calculate_revenue.py --start 2024-01-01 --end 2024-01-31
    python api/monetization_tools/SCRIPTS/calculate_revenue.py --today
    python api/monetization_tools/SCRIPTS/calculate_revenue.py --yesterday
    python api/monetization_tools/SCRIPTS/calculate_revenue.py --mtd
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
logger = logging.getLogger("calculate_revenue")


def calculate_ad_revenue_for_date(target_date: date, tenant=None) -> dict:
    """
    Aggregate ImpressionLog revenue into AdPerformanceDaily rows
    and rebuild RevenueDailySummary for a given date.
    """
    from api.monetization_tools.models import (
        ImpressionLog, ClickLog, ConversionLog, AdPerformanceDaily,
        RevenueDailySummary, AdNetwork,
    )
    from django.db.models import Sum, Count, Avg
    from django.utils import timezone as tz

    logger.info("Calculating ad revenue for: %s", target_date)

    # ── Step 1: Aggregate ImpressionLog by (ad_unit, ad_network, country, device_type) ──
    imp_qs = ImpressionLog.objects.filter(
        logged_at__date=target_date, is_bot=False
    )
    if tenant:
        imp_qs = imp_qs.filter(tenant=tenant)

    imp_groups = imp_qs.values(
        "ad_unit_id", "ad_network_id", "country", "device_type"
    ).annotate(
        impressions=Count("id"),
        revenue=Sum("revenue"),
        avg_ecpm=Avg("ecpm"),
        viewable=Count("id", filter=__import__("django.db.models", fromlist=["Q"]).Q(is_viewable=True)),
    )

    # ── Step 2: Aggregate ClickLog ─────────────────────────────────────────────
    clk_qs = ClickLog.objects.filter(
        clicked_at__date=target_date, is_valid=True
    )
    if tenant:
        clk_qs = clk_qs.filter(tenant=tenant)

    clk_map = {}
    for row in clk_qs.values("ad_unit_id", "country", "device_type").annotate(
        clicks=Count("id"), click_rev=Sum("revenue")
    ):
        key = (row["ad_unit_id"], row["country"] or "", row["device_type"] or "")
        clk_map[key] = {"clicks": row["clicks"], "click_rev": row["click_rev"] or Decimal("0")}

    # ── Step 3: Aggregate ConversionLog ────────────────────────────────────────
    cnv_qs = ConversionLog.objects.filter(
        converted_at__date=target_date, is_verified=True
    )
    if tenant:
        cnv_qs = cnv_qs.filter(tenant=tenant)

    cnv_map = {}
    for row in cnv_qs.values("campaign__ad_units__id", "country", "device_type").annotate(
        conversions=Count("id"), cnv_payout=Sum("payout")
    ):
        unit_id = row.get("campaign__ad_units__id")
        if unit_id:
            key = (unit_id, row["country"] or "", row["device_type"] or "")
            cnv_map[key] = {
                "conversions": row["conversions"],
                "cnv_payout":  row["cnv_payout"] or Decimal("0"),
            }

    # ── Step 4: Upsert AdPerformanceDaily ─────────────────────────────────────
    perf_rows_created = 0
    perf_rows_updated = 0

    for row in imp_groups:
        ad_unit_id  = row["ad_unit_id"]
        ad_net_id   = row["ad_network_id"]
        country     = row["country"] or ""
        device_type = row["device_type"] or ""
        impressions = row["impressions"] or 0
        imp_revenue = row["revenue"] or Decimal("0")
        ecpm        = row["avg_ecpm"] or Decimal("0")

        key         = (ad_unit_id, country, device_type)
        clicks      = clk_map.get(key, {}).get("clicks", 0)
        click_rev   = clk_map.get(key, {}).get("click_rev", Decimal("0"))
        conversions = cnv_map.get(key, {}).get("conversions", 0)
        cnv_rev     = cnv_map.get(key, {}).get("cnv_payout", Decimal("0"))

        total_revenue = (imp_revenue + click_rev + cnv_rev).quantize(Decimal("0.000001"))
        ctr = (Decimal(clicks) / impressions * 100).quantize(Decimal("0.0001")) if impressions else Decimal("0")
        cvr = (Decimal(conversions) / clicks * 100).quantize(Decimal("0.0001")) if clicks else Decimal("0")

        # Get campaign from ad_unit
        try:
            from api.monetization_tools.models import AdUnit
            ad_unit   = AdUnit.objects.select_related("campaign").get(pk=ad_unit_id)
            campaign  = ad_unit.campaign
        except Exception:
            campaign = None

        _, created = AdPerformanceDaily.objects.update_or_create(
            ad_unit_id=ad_unit_id,
            ad_network_id=ad_net_id,
            campaign=campaign,
            date=target_date,
            country=country,
            device_type=device_type,
            defaults={
                "impressions":    impressions,
                "clicks":         clicks,
                "conversions":    conversions,
                "total_revenue":  total_revenue,
                "revenue_cpm":    imp_revenue,
                "revenue_cpc":    click_rev,
                "revenue_cpa":    cnv_rev,
                "ecpm":           ecpm,
                "ctr":            ctr,
                "cvr":            cvr,
                "tenant":         tenant,
            },
        )
        if created:
            perf_rows_created += 1
        else:
            perf_rows_updated += 1

    logger.info("AdPerformanceDaily: created=%d updated=%d",
                perf_rows_created, perf_rows_updated)

    # ── Step 5: Rebuild RevenueDailySummary ────────────────────────────────────
    perf_agg = AdPerformanceDaily.objects.filter(date=target_date)
    if tenant:
        perf_agg = perf_agg.filter(tenant=tenant)

    agg = perf_agg.aggregate(
        total_revenue=Sum("total_revenue"),
        revenue_cpm=Sum("revenue_cpm"),
        revenue_cpc=Sum("revenue_cpc"),
        revenue_cpa=Sum("revenue_cpa"),
        impressions=Sum("impressions"),
        clicks=Sum("clicks"),
        conversions=Sum("conversions"),
        avg_ecpm=Avg("ecpm"),
        avg_ctr=Avg("ctr"),
        avg_fill=Avg("fill_rate"),
    )

    total_rev  = agg["total_revenue"] or Decimal("0")
    total_imp  = agg["impressions"]   or 0
    total_clk  = agg["clicks"]        or 0
    avg_ecpm   = agg["avg_ecpm"]      or Decimal("0")
    avg_ctr    = agg["avg_ctr"]       or Decimal("0")
    avg_fill   = agg["avg_fill"]      or Decimal("0")

    summary, created = RevenueDailySummary.objects.update_or_create(
        date=target_date,
        tenant=tenant,
        defaults={
            "total_revenue":  total_rev,
            "revenue_cpm":    agg["revenue_cpm"]  or Decimal("0"),
            "revenue_cpc":    agg["revenue_cpc"]  or Decimal("0"),
            "revenue_cpa":    agg["revenue_cpa"]  or Decimal("0"),
            "impressions":    total_imp,
            "clicks":         total_clk,
            "conversions":    agg["conversions"]  or 0,
            "ecpm":           avg_ecpm,
            "ctr":            avg_ctr,
            "fill_rate":      avg_fill,
        },
    )

    logger.info(
        "RevenueDailySummary %s: date=%s rev=%s imp=%d ecpm=%s ctr=%s",
        "created" if created else "updated",
        target_date, total_rev, total_imp, avg_ecpm, avg_ctr,
    )

    return {
        "date":              str(target_date),
        "total_revenue":     str(total_rev),
        "impressions":       total_imp,
        "clicks":            total_clk,
        "avg_ecpm":          str(avg_ecpm),
        "avg_ctr":           str(avg_ctr),
        "perf_rows_created": perf_rows_created,
        "perf_rows_updated": perf_rows_updated,
        "summary_created":   created,
    }


def calculate_subscription_revenue(target_date: date, tenant=None) -> Decimal:
    """Sum subscription payments for a date."""
    from api.monetization_tools.models import PaymentTransaction
    from django.db.models import Sum

    qs = PaymentTransaction.objects.filter(
        status="success",
        purpose="subscription",
        completed_at__date=target_date,
    )
    if tenant:
        qs = qs.filter(tenant=tenant)
    return qs.aggregate(t=Sum("amount"))["t"] or Decimal("0")


def calculate_iap_revenue(target_date: date, tenant=None) -> Decimal:
    """Sum in-app purchase revenue for a date."""
    from api.monetization_tools.models import InAppPurchase
    from django.db.models import Sum

    qs = InAppPurchase.objects.filter(
        status="completed",
        purchased_at__date=target_date,
    )
    if tenant:
        qs = qs.filter(tenant=tenant)
    return qs.aggregate(t=Sum("amount"))["t"] or Decimal("0")


def calculate_revenue_date_range(start: date, end: date, tenant=None) -> dict:
    """Recalculate revenue for a range of dates."""
    current = start
    results = []
    total   = Decimal("0")

    while current <= end:
        logger.info("Processing: %s", current)
        result = calculate_ad_revenue_for_date(current, tenant)
        sub_rev = calculate_subscription_revenue(current, tenant)
        iap_rev = calculate_iap_revenue(current, tenant)

        day_total = (
            Decimal(result["total_revenue"]) + sub_rev + iap_rev
        ).quantize(Decimal("0.000001"))

        result["subscription_revenue"] = str(sub_rev)
        result["iap_revenue"]          = str(iap_rev)
        result["grand_total"]          = str(day_total)
        results.append(result)
        total  += day_total
        current += timedelta(days=1)

    logger.info("Range calculation complete: %s to %s | total=%s", start, end, total)
    return {
        "start":       str(start),
        "end":         str(end),
        "days":        len(results),
        "grand_total": str(total),
        "daily":       results,
    }


def print_summary(result: dict):
    """Pretty-print calculation result."""
    logger.info("=" * 60)
    if "daily" in result:
        logger.info("RANGE: %s to %s (%d days)", result["start"], result["end"], result["days"])
        logger.info("GRAND TOTAL: %s", result["grand_total"])
        for day in result["daily"]:
            logger.info("  %s | rev=%s | imp=%d | ecpm=%s",
                        day["date"], day["total_revenue"],
                        day["impressions"], day["avg_ecpm"])
    else:
        logger.info("DATE:         %s", result["date"])
        logger.info("AD REVENUE:   %s", result["total_revenue"])
        logger.info("IMPRESSIONS:  %d", result["impressions"])
        logger.info("CLICKS:       %d", result["clicks"])
        logger.info("AVG ECPM:     %s", result["avg_ecpm"])
        logger.info("AVG CTR:      %s%%", result["avg_ctr"])
    logger.info("=" * 60)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Calculate and rebuild revenue summaries")
    parser.add_argument("--date",      default=None, help="Single date YYYY-MM-DD")
    parser.add_argument("--start",     default=None, help="Range start YYYY-MM-DD")
    parser.add_argument("--end",       default=None, help="Range end YYYY-MM-DD")
    parser.add_argument("--today",     action="store_true", help="Calculate for today")
    parser.add_argument("--yesterday", action="store_true", help="Calculate for yesterday")
    parser.add_argument("--mtd",       action="store_true", help="Month-to-date recalculation")
    parser.add_argument("--dry-run",   action="store_true", help="Log what would be done without writing")
    args = parser.parse_args()

    if args.today:
        target = date.today()
        result = calculate_ad_revenue_for_date(target)
        print_summary(result)

    elif args.yesterday:
        target = date.today() - timedelta(days=1)
        result = calculate_ad_revenue_for_date(target)
        print_summary(result)

    elif args.mtd:
        today = date.today()
        start = today.replace(day=1)
        result = calculate_revenue_date_range(start, today)
        print_summary(result)

    elif args.date:
        result = calculate_ad_revenue_for_date(date.fromisoformat(args.date))
        print_summary(result)

    elif args.start and args.end:
        result = calculate_revenue_date_range(
            date.fromisoformat(args.start),
            date.fromisoformat(args.end),
        )
        print_summary(result)

    else:
        # Default: yesterday
        target = date.today() - timedelta(days=1)
        logger.info("No date specified, defaulting to yesterday: %s", target)
        result = calculate_ad_revenue_for_date(target)
        print_summary(result)
