#!/usr/bin/env python
# api/publisher_tools/scripts/generate_reports.py
"""
Generate Reports — Automated report generation ও distribution।
Daily, weekly, monthly reports সব publishers-দের জন্য।
"""
import logging
from datetime import date, timedelta
from django.utils import timezone

logger = logging.getLogger(__name__)


def generate_daily_reports_all():
    """সব publishers-এর daily report generate করে।"""
    from api.publisher_tools.models import Publisher
    from api.publisher_tools.performance_analytics.daily_report import generate_daily_report
    yesterday = timezone.now().date() - timedelta(days=1)
    publishers = Publisher.objects.filter(status="active")
    generated = 0
    for pub in publishers:
        try:
            report = generate_daily_report(pub, yesterday)
            print(f"  📊 Daily report [{pub.publisher_id}]: ${report.get('publisher_revenue', 0):.4f}")
            generated += 1
        except Exception as e:
            logger.error(f"Daily report error [{pub.publisher_id}]: {e}")
    print(f"✅ Daily reports generated: {generated}")
    return {"generated": generated, "date": str(yesterday)}


def generate_monthly_reports_all(year: int = None, month: int = None):
    """সব publishers-এর monthly report generate করে।"""
    from api.publisher_tools.models import Publisher
    from api.publisher_tools.performance_analytics.monthly_report import generate_monthly_report
    now = timezone.now()
    year  = year or (now.year if now.month > 1 else now.year - 1)
    month = month or (now.month - 1 if now.month > 1 else 12)
    publishers = Publisher.objects.filter(status="active")
    generated = 0
    for pub in publishers:
        try:
            report = generate_monthly_report(pub, year, month)
            print(f"  📊 Monthly report [{pub.publisher_id}]: ${report.get('publisher_revenue', 0):.4f}")
            generated += 1
        except Exception as e:
            logger.error(f"Monthly report error [{pub.publisher_id}]: {e}")
    print(f"✅ Monthly reports generated: {generated}")
    return {"generated": generated, "year": year, "month": month}


def generate_waterfall_reports():
    """Waterfall performance reports generate করে।"""
    from api.publisher_tools.models import Publisher
    from api.publisher_tools.mediation_management.mediation_reporting import generate_waterfall_report
    publishers = Publisher.objects.filter(status="active")
    start = (timezone.now() - timedelta(days=30)).date()
    end   = timezone.now().date()
    generated = 0
    for pub in publishers:
        try:
            report = generate_waterfall_report(pub, start, end)
            if report.get("groups"):
                print(f"  📊 Waterfall report [{pub.publisher_id}]: {len(report['groups'])} groups")
                generated += 1
        except Exception as e:
            logger.error(f"Waterfall report error [{pub.publisher_id}]: {e}")
    print(f"✅ Waterfall reports generated: {generated}")
    return {"generated": generated}


def generate_fraud_reports():
    """Fraud reports generate করে।"""
    from api.publisher_tools.models import Publisher
    from api.publisher_tools.fraud_prevention.fraud_report import generate_fraud_report
    publishers = Publisher.objects.filter(status="active")
    generated = 0
    high_risk = 0
    for pub in publishers:
        try:
            report = generate_fraud_report(pub, days=30)
            if report["summary"]["total_ivt_events"] > 0:
                print(f"  🛡 Fraud report [{pub.publisher_id}]: {report['summary']['total_ivt_events']} IVT events, risk: {report['risk_level']}")
                if report["risk_level"] in ("high","critical"):
                    high_risk += 1
                generated += 1
        except Exception as e:
            logger.error(f"Fraud report error [{pub.publisher_id}]: {e}")
    print(f"✅ Fraud reports: {generated} generated, {high_risk} high-risk publishers")
    return {"generated": generated, "high_risk": high_risk}


def run(report_type: str = "daily"):
    print(f"🔄 Report generation started at {timezone.now()} — type: {report_type}")
    results = {"report_type": report_type, "started_at": timezone.now().isoformat()}
    if report_type in ("daily", "all"):
        results["daily"] = generate_daily_reports_all()
    if report_type in ("monthly", "all"):
        results["monthly"] = generate_monthly_reports_all()
    if report_type in ("waterfall", "all"):
        results["waterfall"] = generate_waterfall_reports()
    if report_type in ("fraud", "all"):
        results["fraud"] = generate_fraud_reports()
    results["completed_at"] = timezone.now().isoformat()
    return results

if __name__ == "__main__":
    run("all")
