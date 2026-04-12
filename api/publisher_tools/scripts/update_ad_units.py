#!/usr/bin/env python
# api/publisher_tools/scripts/update_ad_units.py
"""
Update Ad Units — Ad unit data consistency ও metrics update।
Usage: python manage.py shell < scripts/update_ad_units.py
"""
import logging
from decimal import Decimal
from django.db.models import Avg, Sum
from django.utils import timezone

logger = logging.getLogger(__name__)


def update_ad_unit_metrics():
    """Ad units-এর calculated metrics update করে।"""
    from api.publisher_tools.models import AdUnit, PublisherEarning
    from datetime import timedelta
    start = timezone.now().date() - timedelta(days=30)
    units = AdUnit.objects.filter(status="active")
    updated = 0
    for unit in units:
        try:
            agg = PublisherEarning.objects.filter(
                ad_unit=unit, date__gte=start, impressions__gt=0,
            ).aggregate(
                total_rev=Sum("publisher_revenue"),
                total_imp=Sum("impressions"),
                total_clicks=Sum("clicks"),
                total_req=Sum("ad_requests"),
                avg_ecpm=Avg("ecpm"),
            )
            total_imp = agg.get("total_imp") or 0
            total_req = agg.get("total_req") or 0
            total_rev = agg.get("total_rev") or Decimal("0")
            ecpm = (total_rev / total_imp * 1000) if total_imp > 0 else Decimal("0")
            fill = (total_imp / total_req * 100) if total_req > 0 else Decimal("0")
            unit.avg_ecpm   = ecpm
            unit.fill_rate  = fill
            unit.save(update_fields=["avg_ecpm", "fill_rate", "updated_at"])
            updated += 1
        except Exception as e:
            logger.error(f"Ad unit metrics update error [{unit.unit_id}]: {e}")
    print(f"✅ Ad unit metrics updated: {updated} units")
    return {"updated": updated}


def archive_inactive_ad_units(days_inactive: int = 90):
    """Inactive ad units archive করে।"""
    from api.publisher_tools.models import AdUnit, PublisherEarning
    from datetime import timedelta
    cutoff = timezone.now().date() - timedelta(days=days_inactive)
    units = AdUnit.objects.filter(status="paused")
    archived = 0
    for unit in units:
        has_recent = PublisherEarning.objects.filter(ad_unit=unit, date__gte=cutoff).exists()
        if not has_recent:
            unit.status = "archived"
            unit.save(update_fields=["status", "updated_at"])
            archived += 1
    print(f"✅ Archived {archived} inactive ad units")
    return {"archived": archived}


def sync_ad_unit_revenue_totals():
    """Ad unit total_revenue ও total_impressions sync করে।"""
    from api.publisher_tools.models import AdUnit, PublisherEarning
    units = AdUnit.objects.all()
    updated = 0
    for unit in units:
        try:
            agg = PublisherEarning.objects.filter(ad_unit=unit).aggregate(
                rev=Sum("publisher_revenue"), imp=Sum("impressions"), clk=Sum("clicks"),
            )
            unit.total_revenue     = agg.get("rev") or Decimal("0")
            unit.total_impressions = agg.get("imp") or 0
            unit.total_clicks      = agg.get("clk") or 0
            unit.save(update_fields=["total_revenue","total_impressions","total_clicks","updated_at"])
            updated += 1
        except Exception as e:
            logger.error(f"Revenue sync error [{unit.unit_id}]: {e}")
    print(f"✅ Ad unit revenue totals synced: {updated}")
    return {"updated": updated}


def run():
    print(f"🔄 Starting ad unit update at {timezone.now()}")
    return {
        "metrics_updated": update_ad_unit_metrics(),
        "archived":        archive_inactive_ad_units(),
        "revenue_synced":  sync_ad_unit_revenue_totals(),
    }

if __name__ == "__main__":
    run()
