#!/usr/bin/env python3
"""
SCRIPTS/generate_reports.py
============================
Generates daily, weekly, and monthly analytics reports and optionally
emails them to admins or exports to CSV/JSON.

Usage:
    python api/monetization_tools/SCRIPTS/generate_reports.py --type daily
    python api/monetization_tools/SCRIPTS/generate_reports.py --type weekly
    python api/monetization_tools/SCRIPTS/generate_reports.py --type monthly --month 2024-01
    python api/monetization_tools/SCRIPTS/generate_reports.py --type custom --start 2024-01-01 --end 2024-01-31
"""
import os
import sys
import json
import csv
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
logger = logging.getLogger("generate_reports")


class DecimalEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles Decimal and date types."""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)
        if isinstance(obj, (date,)):
            return obj.isoformat()
        return super().default(obj)


def generate_daily_report(report_date: date = None) -> dict:
    """Generate complete daily revenue + performance report."""
    from api.monetization_tools.ANALYTICS_REPORTING.daily_summary import DailySummaryReport
    from api.monetization_tools.ANALYTICS_REPORTING.ad_performance_report import AdPerformanceReport
    from api.monetization_tools.ANALYTICS_REPORTING.revenue_report import RevenueReport

    report_date = report_date or (date.today() - timedelta(days=1))
    logger.info("Generating daily report for: %s", report_date)

    summary     = DailySummaryReport.generate(report_date)
    by_unit     = AdPerformanceReport.by_unit(start=report_date, end=report_date)
    by_network  = RevenueReport.by_network(start=report_date, end=report_date)

    report = {
        "report_type":  "daily",
        "date":         str(report_date),
        "summary":      summary,
        "by_ad_unit":   by_unit[:20],
        "by_network":   by_network,
    }
    logger.info("Daily report: revenue=%s impressions=%s",
                summary.get("total_revenue"), summary.get("total_impressions"))
    return report


def generate_weekly_report(week_offset: int = 1) -> dict:
    """Generate weekly performance summary."""
    from api.monetization_tools.ANALYTICS_REPORTING.weekly_report import WeeklyReport

    logger.info("Generating weekly report (offset=%d weeks)", week_offset)
    report = WeeklyReport.generate(week_offset)
    report["report_type"] = "weekly"
    logger.info("Weekly report: revenue=%s", report.get("total_revenue"))
    return report


def generate_monthly_report(year: int = None, month: int = None) -> dict:
    """Generate monthly revenue and KPI report."""
    from api.monetization_tools.ANALYTICS_REPORTING.monthly_report import MonthlyReport

    today = date.today()
    year  = year or (today.year if today.month > 1 else today.year - 1)
    month = month or (today.month - 1 if today.month > 1 else 12)

    logger.info("Generating monthly report for: %04d-%02d", year, month)
    report = MonthlyReport.generate(year, month)
    report["report_type"] = "monthly"
    logger.info("Monthly report: ad_rev=%s iap_rev=%s subs=%s",
                report.get("ad_revenue"), report.get("iap_revenue"), report.get("new_subscribers"))
    return report


def generate_custom_report(start: date, end: date,
                            dimensions: list = None, metrics: list = None) -> dict:
    """Generate custom date-range report with flexible dimensions."""
    from api.monetization_tools.ANALYTICS_REPORTING.custom_report_builder import CustomReportBuilder
    from api.monetization_tools.ANALYTICS_REPORTING.revenue_report import RevenueReport

    dims    = dimensions or ["date", "network"]
    metrics = metrics or ["revenue", "impressions", "ecpm", "ctr"]

    logger.info("Generating custom report: %s to %s | dims=%s", start, end, dims)

    errors = CustomReportBuilder.validate(dims, metrics)
    if errors:
        logger.error("Invalid report params: %s", errors)
        return {"error": errors}

    rows    = CustomReportBuilder.build(dims, metrics, start=start, end=end)
    summary = RevenueReport.generate(start=start, end=end)

    return {
        "report_type": "custom",
        "start":       str(start),
        "end":         str(end),
        "dimensions":  dims,
        "metrics":     metrics,
        "rows":        rows,
        "summary":     summary.get("totals", {}),
    }


def export_to_json(report: dict, output_path: str):
    """Export report to a JSON file."""
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, cls=DecimalEncoder, indent=2, ensure_ascii=False)
    logger.info("Exported JSON: %s", output_path)


def export_to_csv(rows: list, output_path: str, fieldnames: list = None):
    """Export tabular rows to a CSV file."""
    if not rows:
        logger.warning("No rows to export to CSV.")
        return
    fieldnames = fieldnames or list(rows[0].keys())
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: str(v) if isinstance(v, Decimal) else v for k, v in row.items()})
    logger.info("Exported CSV: %s (%d rows)", output_path, len(rows))


def send_report_email(report: dict, recipients: list):
    """Send report summary email to admin recipients."""
    from django.core.mail import send_mail
    from django.conf import settings

    subject = f"[MonetizationTools] {report.get('report_type', 'Analytics').title()} Report"
    body    = json.dumps(report, cls=DecimalEncoder, indent=2, ensure_ascii=False)[:5000]
    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@example.com"),
            recipient_list=recipients,
            fail_silently=False,
        )
        logger.info("Report email sent to: %s", recipients)
    except Exception as exc:
        logger.error("Failed to send report email: %s", exc)


def run(report_type: str, output_dir: str = "/tmp", email: bool = False,
        report_date_str: str = None, month_str: str = None,
        start_str: str = None, end_str: str = None) -> dict:
    """Main entry point for report generation."""

    os.makedirs(output_dir, exist_ok=True)

    if report_type == "daily":
        target = date.fromisoformat(report_date_str) if report_date_str else None
        report = generate_daily_report(target)

    elif report_type == "weekly":
        report = generate_weekly_report(week_offset=1)

    elif report_type == "monthly":
        if month_str:
            parts = month_str.split("-")
            report = generate_monthly_report(int(parts[0]), int(parts[1]))
        else:
            report = generate_monthly_report()

    elif report_type == "custom":
        if not start_str or not end_str:
            raise ValueError("--start and --end required for custom report")
        report = generate_custom_report(
            date.fromisoformat(start_str), date.fromisoformat(end_str)
        )
    else:
        raise ValueError(f"Unknown report type: {report_type}")

    # Export JSON
    from django.utils import timezone as tz
    ts           = tz.now().strftime("%Y%m%d_%H%M%S")
    json_path    = os.path.join(output_dir, f"monetization_{report_type}_{ts}.json")
    export_to_json(report, json_path)

    # Export CSV (for tabular reports)
    rows = report.get("by_ad_unit") or report.get("rows", [])
    if rows:
        csv_path = os.path.join(output_dir, f"monetization_{report_type}_{ts}.csv")
        export_to_csv(rows, csv_path)

    # Email
    if email:
        from django.conf import settings
        admins = [a[1] for a in getattr(settings, "ADMINS", [])]
        if admins:
            send_report_email(report, admins)
        else:
            logger.warning("No ADMINS configured for email delivery.")

    return report


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate monetization analytics reports")
    parser.add_argument("--type",   required=True,
                        choices=["daily", "weekly", "monthly", "custom"],
                        help="Report type")
    parser.add_argument("--date",   default=None,
                        help="Date for daily report (YYYY-MM-DD)")
    parser.add_argument("--month",  default=None,
                        help="Month for monthly report (YYYY-MM)")
    parser.add_argument("--start",  default=None,
                        help="Start date for custom report (YYYY-MM-DD)")
    parser.add_argument("--end",    default=None,
                        help="End date for custom report (YYYY-MM-DD)")
    parser.add_argument("--output", default="/tmp",
                        help="Output directory for exported files")
    parser.add_argument("--email",  action="store_true",
                        help="Email report to ADMINS")
    args = parser.parse_args()

    run(
        report_type=args.type,
        output_dir=args.output,
        email=args.email,
        report_date_str=args.date,
        month_str=args.month,
        start_str=args.start,
        end_str=args.end,
    )
