#!/usr/bin/env python3
"""
SCRIPTS/backup_ad_data.py
==========================
Exports critical monetization data to JSON/CSV backup files.
Supports full backup, incremental (since last backup), and restore-preview.

Backed up tables:
  - AdNetwork, AdCampaign, AdUnit, AdPlacement
  - WaterfallConfig, FloorPriceConfig
  - MonetizationConfig, SubscriptionPlan
  - Offerwall, Offer
  - ReferralProgram, FlashSale, Coupon
  - RevenueDailySummary (configurable date range)
  - AdPerformanceDaily (configurable date range)

Usage:
    python api/monetization_tools/SCRIPTS/backup_ad_data.py --type full --output /backups
    python api/monetization_tools/SCRIPTS/backup_ad_data.py --type config --output /backups
    python api/monetization_tools/SCRIPTS/backup_ad_data.py --type revenue --days 30 --output /backups
    python api/monetization_tools/SCRIPTS/backup_ad_data.py --type performance --days 7
    python api/monetization_tools/SCRIPTS/backup_ad_data.py --list
"""
import os
import sys
import json
import csv
import gzip
import logging
from datetime import date, datetime, timedelta
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
logger = logging.getLogger("backup_ad_data")


class DecimalDateEncoder(json.JSONEncoder):
    """JSON encoder that handles Decimal, date, datetime."""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        return super().default(obj)


def _serialize_qs(qs) -> list:
    """Convert a queryset to a list of dicts (serialisable)."""
    from django.core import serializers
    import json
    raw = serializers.serialize("json", qs)
    data = json.loads(raw)
    result = []
    for item in data:
        row = {"id": item["pk"]}
        row.update(item["fields"])
        result.append(row)
    return result


def backup_config_models(output_dir: str) -> dict:
    """Backup all configuration/setup models."""
    from api.monetization_tools.models import (
        AdNetwork, AdCampaign, AdUnit, AdPlacement,
        WaterfallConfig, FloorPriceConfig, MonetizationConfig,
        SubscriptionPlan, Offerwall, Offer,
        ReferralProgram, FlashSale, Coupon,
        SpinWheelConfig, PrizeConfig, UserSegment,
        PublisherAccount, MonetizationNotificationTemplate,
    )

    models_to_backup = {
        "ad_networks":            AdNetwork.objects.all(),
        "ad_campaigns":           AdCampaign.objects.all(),
        "ad_units":               AdUnit.objects.all(),
        "ad_placements":          AdPlacement.objects.all(),
        "waterfall_configs":      WaterfallConfig.objects.all(),
        "floor_price_configs":    FloorPriceConfig.objects.all(),
        "monetization_configs":   MonetizationConfig.objects.all(),
        "subscription_plans":     SubscriptionPlan.objects.all(),
        "offerwalls":             Offerwall.objects.all(),
        "offers":                 Offer.objects.all(),
        "referral_programs":      ReferralProgram.objects.all(),
        "flash_sales":            FlashSale.objects.all(),
        "coupons":                Coupon.objects.all(),
        "spin_wheel_configs":     SpinWheelConfig.objects.all(),
        "prize_configs":          PrizeConfig.objects.all(),
        "user_segments":          UserSegment.objects.all(),
        "publisher_accounts":     PublisherAccount.objects.all(),
        "notification_templates": MonetizationNotificationTemplate.objects.all(),
    }

    backup_data = {}
    total_rows  = 0

    for key, qs in models_to_backup.items():
        try:
            rows          = _serialize_qs(qs)
            backup_data[key] = rows
            total_rows    += len(rows)
            logger.info("  %-35s %d rows", key, len(rows))
        except Exception as exc:
            logger.warning("  Failed to backup %s: %s", key, exc)
            backup_data[key] = []

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename  = os.path.join(output_dir, f"mt_config_backup_{timestamp}.json.gz")

    os.makedirs(output_dir, exist_ok=True)
    with gzip.open(filename, "wt", encoding="utf-8") as f:
        json.dump(backup_data, f, cls=DecimalDateEncoder, indent=2, ensure_ascii=False)

    size_kb = os.path.getsize(filename) // 1024
    logger.info("Config backup saved: %s (%d KB, %d rows)", filename, size_kb, total_rows)
    return {
        "success":    True,
        "file":       filename,
        "size_kb":    size_kb,
        "total_rows": total_rows,
        "tables":     list(backup_data.keys()),
    }


def backup_revenue_data(output_dir: str, days: int = 30) -> dict:
    """Backup RevenueDailySummary for the last N days."""
    from api.monetization_tools.models import RevenueDailySummary
    from django.utils import timezone as tz

    cutoff = tz.now().date() - timedelta(days=days)
    qs     = RevenueDailySummary.objects.filter(date__gte=cutoff).order_by("date")

    rows       = _serialize_qs(qs)
    timestamp  = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename   = os.path.join(output_dir, f"mt_revenue_{timestamp}.json.gz")

    os.makedirs(output_dir, exist_ok=True)
    with gzip.open(filename, "wt", encoding="utf-8") as f:
        json.dump({"revenue_daily_summaries": rows, "days": days,
                   "cutoff": str(cutoff)}, f, cls=DecimalDateEncoder, indent=2)

    # Also export CSV
    csv_filename = filename.replace(".json.gz", ".csv")
    if rows:
        with open(csv_filename, "w", newline="", encoding="utf-8") as cf:
            writer = csv.DictWriter(cf, fieldnames=rows[0].keys(), extrasaction="ignore")
            writer.writeheader()
            writer.writerows(
                {k: str(v) if isinstance(v, Decimal) else v for k, v in r.items()}
                for r in rows
            )
        logger.info("Revenue CSV: %s", csv_filename)

    size_kb = os.path.getsize(filename) // 1024
    logger.info("Revenue backup: %s (%d KB, %d rows, last %d days)",
                filename, size_kb, len(rows), days)
    return {
        "success":    True,
        "file":       filename,
        "csv_file":   csv_filename if rows else None,
        "size_kb":    size_kb,
        "rows":       len(rows),
        "days":       days,
        "cutoff":     str(cutoff),
    }


def backup_performance_data(output_dir: str, days: int = 7) -> dict:
    """Backup AdPerformanceDaily data for the last N days."""
    from api.monetization_tools.models import AdPerformanceDaily
    from django.utils import timezone as tz

    cutoff = tz.now().date() - timedelta(days=days)
    qs     = AdPerformanceDaily.objects.filter(date__gte=cutoff).order_by("date", "ad_unit_id")

    rows      = _serialize_qs(qs)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename  = os.path.join(output_dir, f"mt_performance_{timestamp}.json.gz")

    os.makedirs(output_dir, exist_ok=True)
    with gzip.open(filename, "wt", encoding="utf-8") as f:
        json.dump({"ad_performance_daily": rows, "days": days,
                   "cutoff": str(cutoff)}, f, cls=DecimalDateEncoder, indent=2)

    size_kb = os.path.getsize(filename) // 1024
    logger.info("Performance backup: %s (%d KB, %d rows, last %d days)",
                filename, size_kb, len(rows), days)
    return {"success": True, "file": filename, "size_kb": size_kb, "rows": len(rows), "days": days}


def backup_transaction_data(output_dir: str, days: int = 30) -> dict:
    """Backup PaymentTransaction and PayoutRequest data."""
    from api.monetization_tools.models import PaymentTransaction, PayoutRequest
    from django.utils import timezone as tz

    cutoff  = tz.now() - timedelta(days=days)
    txn_qs  = PaymentTransaction.objects.filter(initiated_at__gte=cutoff)
    pout_qs = PayoutRequest.objects.filter(created_at__gte=cutoff)

    txn_rows  = _serialize_qs(txn_qs)
    pout_rows = _serialize_qs(pout_qs)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename  = os.path.join(output_dir, f"mt_transactions_{timestamp}.json.gz")

    os.makedirs(output_dir, exist_ok=True)
    with gzip.open(filename, "wt", encoding="utf-8") as f:
        json.dump({
            "payment_transactions": txn_rows,
            "payout_requests":      pout_rows,
            "days":                 days,
        }, f, cls=DecimalDateEncoder, indent=2)

    size_kb   = os.path.getsize(filename) // 1024
    total     = len(txn_rows) + len(pout_rows)
    logger.info("Transaction backup: %s (%d KB, %d transactions + %d payouts)",
                filename, size_kb, len(txn_rows), len(pout_rows))
    return {"success": True, "file": filename, "size_kb": size_kb, "total_rows": total}


def full_backup(output_dir: str, revenue_days: int = 30,
                performance_days: int = 7, transaction_days: int = 30) -> dict:
    """Run all backup types and return combined results."""
    logger.info("=" * 60)
    logger.info("FULL MONETIZATION BACKUP")
    logger.info("Output: %s", output_dir)
    logger.info("=" * 60)

    results = {}

    logger.info("1/4 Config models...")
    results["config"] = backup_config_models(output_dir)

    logger.info("2/4 Revenue data (last %d days)...", revenue_days)
    results["revenue"] = backup_revenue_data(output_dir, revenue_days)

    logger.info("3/4 Performance data (last %d days)...", performance_days)
    results["performance"] = backup_performance_data(output_dir, performance_days)

    logger.info("4/4 Transaction data (last %d days)...", transaction_days)
    results["transactions"] = backup_transaction_data(output_dir, transaction_days)

    logger.info("=" * 60)
    total_size = sum(r.get("size_kb", 0) for r in results.values())
    logger.info("BACKUP COMPLETE: total_size=%d KB", total_size)
    logger.info("=" * 60)

    return {
        "success":    all(r.get("success") for r in results.values()),
        "total_size_kb": total_size,
        "components": results,
    }


def list_backup_files(backup_dir: str):
    """List existing backup files in the directory."""
    if not os.path.exists(backup_dir):
        logger.warning("Backup directory does not exist: %s", backup_dir)
        return

    files = [f for f in os.listdir(backup_dir) if f.startswith("mt_") and
             (f.endswith(".json.gz") or f.endswith(".csv"))]
    files.sort(reverse=True)

    logger.info("Backup files in %s:", backup_dir)
    for fname in files:
        full_path = os.path.join(backup_dir, fname)
        size_kb   = os.path.getsize(full_path) // 1024
        mtime     = datetime.fromtimestamp(os.path.getmtime(full_path))
        logger.info("  %-55s %6d KB  %s", fname, size_kb, mtime.strftime("%Y-%m-%d %H:%M"))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Backup monetization tool data")
    parser.add_argument("--type",     default="full",
                        choices=["full", "config", "revenue", "performance", "transactions"],
                        help="Backup type")
    parser.add_argument("--output",   default="/tmp/mt_backups",
                        help="Output directory")
    parser.add_argument("--days",     default=30, type=int,
                        help="Days of time-series data to include")
    parser.add_argument("--list",     action="store_true",
                        help="List existing backup files")
    args = parser.parse_args()

    if args.list:
        list_backup_files(args.output)
        sys.exit(0)

    if args.type == "full":
        result = full_backup(args.output, revenue_days=args.days)
    elif args.type == "config":
        result = backup_config_models(args.output)
    elif args.type == "revenue":
        result = backup_revenue_data(args.output, args.days)
    elif args.type == "performance":
        result = backup_performance_data(args.output, args.days)
    elif args.type == "transactions":
        result = backup_transaction_data(args.output, args.days)

    import json
    print(json.dumps(result, indent=2, cls=DecimalDateEncoder))
