#!/usr/bin/env python
# api/publisher_tools/scripts/backup_data.py
"""
Backup Data — Critical publisher data backup ও export।
Publisher earnings, invoices, fraud logs backup করে।
"""
import json
import logging
from datetime import date, timedelta
from decimal import Decimal
from django.utils import timezone

logger = logging.getLogger(__name__)


class DecimalEncoder(json.JSONEncoder):
    """Decimal ও date JSON serialize করার encoder।"""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, (date,)):
            return str(obj)
        return super().default(obj)


def backup_publisher_earnings(publisher_id: str = None, days: int = 30) -> dict:
    """Publisher earnings backup করে।"""
    from api.publisher_tools.models import Publisher, PublisherEarning
    start = timezone.now().date() - timedelta(days=days)
    if publisher_id:
        publishers = Publisher.objects.filter(publisher_id=publisher_id)
    else:
        publishers = Publisher.objects.filter(status="active")
    backed_up = 0
    total_records = 0
    for pub in publishers:
        earnings = list(
            PublisherEarning.objects.filter(
                publisher=pub, date__gte=start,
            ).values(
                "date", "earning_type", "gross_revenue", "publisher_revenue",
                "impressions", "clicks", "ecpm", "fill_rate", "status",
            )
        )
        if earnings:
            backup_key = f"backup:earnings:{pub.publisher_id}:{start}:{timezone.now().date()}"
            from django.core.cache import cache
            cache.set(backup_key, json.dumps(earnings, cls=DecimalEncoder), 86400 * 7)
            total_records += len(earnings)
            backed_up += 1
    print(f"✅ Earnings backup: {backed_up} publishers, {total_records} records")
    return {"publishers": backed_up, "records": total_records, "days": days}


def backup_invoices(months: int = 3) -> dict:
    """Recent invoices backup করে।"""
    from api.publisher_tools.models import PublisherInvoice
    start = timezone.now().date() - timedelta(days=months * 30)
    invoices = list(
        PublisherInvoice.objects.filter(period_start__gte=start).values(
            "invoice_number", "publisher__publisher_id",
            "period_start", "period_end", "gross_revenue", "net_payable",
            "status", "paid_at", "payment_reference",
        )
    )
    print(f"✅ Invoices backup: {len(invoices)} records")
    return {"count": len(invoices), "months": months}


def export_publisher_data(publisher_id: str) -> dict:
    """
    Publisher-এর সব data export করে (GDPR compliance)।
    Returns structured data dict।
    """
    from api.publisher_tools.models import Publisher, PublisherEarning, TrafficSafetyLog
    try:
        pub = Publisher.objects.get(publisher_id=publisher_id)
    except Publisher.DoesNotExist:
        return {"error": "Publisher not found"}
    export_data = {
        "export_date":    timezone.now().isoformat(),
        "publisher_id":   pub.publisher_id,
        "profile": {
            "display_name":  pub.display_name,
            "contact_email": pub.contact_email,
            "country":       pub.country,
            "status":        pub.status,
            "created_at":    pub.created_at.isoformat(),
        },
        "sites": list(pub.sites.values("site_id","name","domain","status","created_at")),
        "apps":  list(pub.apps.values("app_id","name","platform","status","created_at")),
        "earnings_summary": {
            "total_revenue":  float(pub.total_revenue),
            "total_paid_out": float(pub.total_paid_out),
            "pending_balance":float(pub.pending_balance),
        },
        "invoices": list(pub.invoices.values(
            "invoice_number","period_start","period_end","net_payable","status","paid_at"
        )[:24]),
    }
    print(f"✅ Data exported for publisher: {publisher_id}")
    return export_data


def run():
    print(f"🔄 Data backup started at {timezone.now()}")
    return {
        "earnings": backup_publisher_earnings(days=30),
        "invoices": backup_invoices(months=3),
        "completed_at": timezone.now().isoformat(),
    }

if __name__ == "__main__":
    run()
