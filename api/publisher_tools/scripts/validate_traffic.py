#!/usr/bin/env python
# api/publisher_tools/scripts/validate_traffic.py
"""
Validate Traffic — Traffic quality validation ও IVT rate check।
Daily traffic validation pipeline।
"""
import logging
from decimal import Decimal
from datetime import timedelta
from django.db.models import Sum, Count, Avg
from django.utils import timezone

logger = logging.getLogger(__name__)


def calculate_publisher_ivt_rates(days: int = 7):
    """সব publishers-এর IVT rate calculate করে।"""
    from api.publisher_tools.models import Publisher, TrafficSafetyLog, PublisherEarning
    start = timezone.now().date() - timedelta(days=days)
    publishers = Publisher.objects.filter(status="active")
    results = []
    for pub in publishers:
        try:
            total_impressions = PublisherEarning.objects.filter(
                publisher=pub, date__gte=start,
            ).aggregate(t=Sum("impressions")).get("t") or 0

            affected_impressions = TrafficSafetyLog.objects.filter(
                publisher=pub, detected_at__date__gte=start, is_false_positive=False,
            ).aggregate(t=Sum("affected_impressions")).get("t") or 0

            ivt_rate = float(affected_impressions) / max(total_impressions, 1) * 100

            results.append({
                "publisher_id":   pub.publisher_id,
                "total_impressions": total_impressions,
                "ivt_impressions": affected_impressions,
                "ivt_rate_pct":   round(ivt_rate, 2),
                "risk_level":     "critical" if ivt_rate >= 40 else "high" if ivt_rate >= 20 else "medium" if ivt_rate >= 10 else "low",
            })
        except Exception as e:
            logger.error(f"IVT rate error [{pub.publisher_id}]: {e}")

    results.sort(key=lambda x: x["ivt_rate_pct"], reverse=True)
    high_risk = [r for r in results if r["risk_level"] in ("high","critical")]
    print(f"✅ IVT rates calculated: {len(results)} publishers, {len(high_risk)} high/critical risk")
    return {"total": len(results), "high_risk": len(high_risk), "details": results[:20]}


def flag_suspicious_publishers(threshold_pct: float = 20.0, auto_suspend: bool = False):
    """High IVT rate publishers flag ও optionally suspend করে।"""
    from api.publisher_tools.models import Publisher
    from api.publisher_tools.services import PublisherService
    from api.publisher_tools.fraud_prevention.fraud_alert import create_fraud_alert
    ivt_data = calculate_publisher_ivt_rates(days=7)
    warned    = 0
    suspended = 0
    for row in ivt_data.get("details", []):
        if row["ivt_rate_pct"] < threshold_pct:
            continue
        try:
            pub = Publisher.objects.get(publisher_id=row["publisher_id"])
            if row["risk_level"] == "critical" and auto_suspend:
                PublisherService.suspend_publisher(pub, f"IVT rate {row['ivt_rate_pct']:.1f}% exceeds critical threshold")
                suspended += 1
                print(f"  🔴 Suspended: {pub.publisher_id} — IVT {row['ivt_rate_pct']:.1f}%")
            else:
                create_fraud_alert(
                    pub, "high_ivt_rate", row["risk_level"],
                    f"High IVT Rate: {row['ivt_rate_pct']:.1f}%",
                    f"IVT rate of {row['ivt_rate_pct']:.1f}% detected over last 7 days.",
                    {"ivt_rate": row["ivt_rate_pct"], "threshold": threshold_pct},
                )
                warned += 1
                print(f"  ⚠️ Warned: {pub.publisher_id} — IVT {row['ivt_rate_pct']:.1f}%")
        except Exception as e:
            logger.error(f"Flag error [{row['publisher_id']}]: {e}")
    return {"warned": warned, "suspended": suspended}


def validate_ads_txt_all_sites():
    """সব active sites-এর ads.txt validate করে।"""
    from api.publisher_tools.models import Site
    from api.publisher_tools.services import SiteService
    sites = Site.objects.filter(status="active")
    verified = 0
    failed   = 0
    for site in sites:
        try:
            result = SiteService.refresh_ads_txt(site)
            if result:
                verified += 1
            else:
                failed += 1
        except Exception as e:
            logger.error(f"ads.txt validation error [{site.domain}]: {e}")
            failed += 1
    print(f"✅ ads.txt validation: {verified} verified, {failed} failed")
    return {"verified": verified, "failed": failed}


def run(auto_suspend: bool = False):
    print(f"🔄 Traffic validation started at {timezone.now()}")
    return {
        "ivt_rates":   calculate_publisher_ivt_rates(),
        "flagged":     flag_suspicious_publishers(auto_suspend=auto_suspend),
        "ads_txt":     validate_ads_txt_all_sites(),
        "completed_at":timezone.now().isoformat(),
    }

if __name__ == "__main__":
    run()
