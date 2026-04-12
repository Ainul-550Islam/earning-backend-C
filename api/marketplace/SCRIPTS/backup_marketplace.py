"""
SCRIPTS/backup_marketplace.py — Export marketplace data as JSON for backup
Usage: python manage.py shell < api/marketplace/SCRIPTS/backup_marketplace.py
"""
import os, django, json
from datetime import datetime
os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
django.setup()

from api.marketplace.models import Product, Category, SellerProfile
from api.tenants.models import Tenant

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

for tenant in Tenant.objects.filter(is_active=True):
    data = {
        "exported_at":  datetime.now().isoformat(),
        "tenant":       tenant.slug,
        "products":     Product.objects.filter(tenant=tenant).count(),
        "categories":   Category.objects.filter(tenant=tenant).count(),
        "sellers":      SellerProfile.objects.filter(tenant=tenant).count(),
    }
    filename = f"backup_{tenant.slug}_{timestamp}.json"
    with open(filename, "w") as f:
        json.dump(data, f, indent=2)
    print(f"✅ Backup created: {filename}")
