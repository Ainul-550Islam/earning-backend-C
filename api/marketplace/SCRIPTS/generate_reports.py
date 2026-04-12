"""
SCRIPTS/generate_reports.py — Generate periodic business reports
Usage: python manage.py shell < api/marketplace/SCRIPTS/generate_reports.py
"""
import os, django
from datetime import date, timedelta
os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
django.setup()

from api.tenants.models import Tenant
from api.marketplace.MARKETPLACE_ANALYTICS.sales_analytics import sales_summary
from api.marketplace.MARKETPLACE_ANALYTICS.marketplace_health import get_health_report
from api.marketplace.PAYMENT_SETTLEMENT.settlement_report import generate_settlement_summary

today    = date.today()
last_30d = today - timedelta(days=30)

for tenant in Tenant.objects.filter(is_active=True):
    print(f"\n📊 === {tenant.name} ===")
    health = get_health_report(tenant)
    print(f"  Health Score: {health['health_score']}/10 ({health['status']})")
    summary = sales_summary(tenant, last_30d, today)
    print(f"  Orders (30d): {summary['total_orders']} | Revenue: {summary['total_revenue']} BDT")
    settlement = generate_settlement_summary(tenant, last_30d, today)
    print(f"  Commission: {settlement['platform_commission']} BDT")
print("\n✅ Reports generated!")
