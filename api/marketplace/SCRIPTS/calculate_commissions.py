"""
SCRIPTS/calculate_commissions.py — Calculate pending commissions for a period

Usage:
    python manage.py shell < api/marketplace/SCRIPTS/calculate_commissions.py
"""
import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.db.models import Sum
from api.marketplace.models import OrderItem
from api.tenants.models import Tenant

for tenant in Tenant.objects.filter(is_active=True):
    agg = OrderItem.objects.filter(tenant=tenant).aggregate(
        gross=Sum("subtotal"),
        commission=Sum("commission_amount"),
        net=Sum("seller_net"),
    )
    print(f"\n📊 {tenant.name}:")
    print(f"   Gross GMV   : {agg['gross'] or 0:,.2f} BDT")
    print(f"   Commission  : {agg['commission'] or 0:,.2f} BDT")
    print(f"   Seller Net  : {agg['net'] or 0:,.2f} BDT")
