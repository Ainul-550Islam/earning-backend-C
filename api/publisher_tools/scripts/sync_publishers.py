#!/usr/bin/env python
# api/publisher_tools/scripts/sync_publishers.py
"""
Sync Publishers — Publisher data sync ও consistency check।
Usage: python manage.py shell < scripts/sync_publishers.py
"""
import logging
from decimal import Decimal
from django.db.models import Sum
from django.utils import timezone

logger = logging.getLogger(__name__)


def sync_publisher_revenue_totals():
    """সব publishers-এর revenue totals recalculate করে।"""
    from api.publisher_tools.models import Publisher, PublisherEarning
    publishers = Publisher.objects.filter(status="active")
    updated = 0
    errors  = 0
    for pub in publishers:
        try:
            agg = PublisherEarning.objects.filter(
                publisher=pub, status__in=["confirmed","finalized"],
            ).aggregate(total=Sum("publisher_revenue"))
            new_total = agg.get("total") or Decimal("0")
            if abs(pub.total_revenue - new_total) > Decimal("0.0001"):
                pub.total_revenue = new_total
                pub.save(update_fields=["total_revenue", "updated_at"])
                updated += 1
        except Exception as e:
            logger.error(f"Revenue sync error [{pub.publisher_id}]: {e}")
            errors += 1
    print(f"✅ Revenue totals synced: {updated} updated, {errors} errors")
    return {"updated": updated, "errors": errors}


def sync_publisher_status_consistency():
    """Publisher status ও inventory status consistency check করে।"""
    from api.publisher_tools.models import Publisher, Site, App, AdUnit
    issues = []
    for pub in Publisher.objects.filter(status="suspended"):
        active_sites = Site.objects.filter(publisher=pub, status="active").count()
        active_apps  = App.objects.filter(publisher=pub, status="active").count()
        active_units = AdUnit.objects.filter(publisher=pub, status="active").count()
        if active_sites > 0 or active_apps > 0 or active_units > 0:
            issues.append({
                "publisher_id":  pub.publisher_id,
                "active_sites":  active_sites,
                "active_apps":   active_apps,
                "active_units":  active_units,
            })
            Site.objects.filter(publisher=pub, status="active").update(status="suspended")
            App.objects.filter(publisher=pub, status="active").update(status="suspended")
            AdUnit.objects.filter(publisher=pub, status="active").update(status="paused")
    print(f"✅ Status consistency: {len(issues)} issues fixed")
    return {"fixed": len(issues), "details": issues}


def sync_publisher_payout_schedules():
    """Payout schedule next_payout_date update করে।"""
    from api.publisher_tools.publisher_management.publisher_payout import PayoutSchedule
    schedules = PayoutSchedule.objects.filter(is_automatic=True, is_paused=False)
    updated = 0
    for schedule in schedules:
        schedule.calculate_next_payout_date()
        updated += 1
    print(f"✅ Payout schedules updated: {updated}")
    return {"updated": updated}


def run_full_sync():
    """Full sync pipeline।"""
    print(f"🔄 Starting publisher sync at {timezone.now()}")
    results = {
        "revenue_totals":    sync_publisher_revenue_totals(),
        "status_consistency":sync_publisher_status_consistency(),
        "payout_schedules":  sync_publisher_payout_schedules(),
        "completed_at":      timezone.now().isoformat(),
    }
    print(f"✅ Publisher sync complete")
    return results


if __name__ == "__main__":
    run_full_sync()
