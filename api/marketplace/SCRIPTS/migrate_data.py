"""
SCRIPTS/migrate_data.py — Data migration utilities
"""
import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
django.setup()

from api.marketplace.models import Product, ProductVariant, ProductInventory
from api.tenants.models import Tenant

def ensure_inventory_for_all_variants():
    """Create missing ProductInventory records."""
    count = 0
    for v in ProductVariant.objects.all():
        _, created = ProductInventory.objects.get_or_create(
            variant=v, defaults={"tenant": v.product.tenant, "quantity": 0}
        )
        if created:
            count += 1
    print(f"✅ Created {count} missing inventory records")

def fix_missing_slugs():
    from api.marketplace.utils import unique_slugify
    from django.utils.text import slugify
    count = 0
    for p in Product.objects.filter(slug=""):
        p.slug = unique_slugify(Product, p.name)
        p.save(update_fields=["slug"])
        count += 1
    print(f"✅ Fixed {count} missing product slugs")

if __name__ == "__main__" or True:
    ensure_inventory_for_all_variants()
    fix_missing_slugs()
    print("✅ Migration complete")
