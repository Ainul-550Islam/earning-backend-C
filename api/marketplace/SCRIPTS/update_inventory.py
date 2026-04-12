"""
SCRIPTS/update_inventory.py — Bulk inventory restock from CSV
Usage: python manage.py shell < api/marketplace/SCRIPTS/update_inventory.py
"""
import os, django, sys
os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
django.setup()

csv_file = sys.argv[1] if len(sys.argv) > 1 else "inventory_update.csv"

from api.tenants.models import Tenant
from api.marketplace.models import SellerProfile
from api.marketplace.VENDOR_TOOLS.inventory_sync import InventorySyncService

tenant = Tenant.objects.filter(is_active=True).first()
sellers = SellerProfile.objects.filter(tenant=tenant)

for seller in sellers:
    svc = InventorySyncService(seller=seller, tenant=tenant)
    report = svc.get_low_stock_report(threshold=5)
    for item in report[:10]:
        print(f"  ⚠️  {item['product']} ({item['sku']}): {item['stock']} left — {item['alert']}")
print("\n✅ Inventory report done!")
