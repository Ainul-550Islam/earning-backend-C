"""
SCRIPTS/sync_products.py — Sync all products to Elasticsearch
==============================================================
Usage:
  python manage.py shell < api/marketplace/SCRIPTS/sync_products.py

Options via environment variables:
  TENANT_SLUG=demo     — only sync specific tenant
  BATCH_SIZE=200       — control batch size (default 200)
  DRY_RUN=true         — print counts without syncing
"""
import os
import django
import logging

os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
django.setup()

logger = logging.getLogger(__name__)

from api.tenants.models import Tenant
from api.marketplace.SEARCH_DISCOVERY.elasticsearch_sync import ElasticsearchSync

target_slug = os.environ.get("TENANT_SLUG")
batch_size  = int(os.environ.get("BATCH_SIZE","200"))
dry_run     = os.environ.get("DRY_RUN","").lower() == "true"

tenants = Tenant.objects.filter(is_active=True)
if target_slug:
    tenants = tenants.filter(slug=target_slug)

print(f"🔍 Syncing {tenants.count()} tenant(s) to Elasticsearch...")
if dry_run:
    print("⚠️  DRY RUN — no changes will be made\n")

total_indexed = 0
total_failed  = 0

for tenant in tenants:
    print(f"\n📦 {tenant.name} ({tenant.slug})")
    if not dry_run:
        # Create/verify index
        ElasticsearchSync.create_index(tenant)
        result = ElasticsearchSync.bulk_reindex(tenant, batch_size=batch_size)
        total_indexed += result.get("indexed",0)
        total_failed  += result.get("failed",0)
        print(f"  ✅ Indexed: {result.get('indexed',0)} | Failed: {result.get('failed',0)}")
    else:
        from api.marketplace.models import Product
        from api.marketplace.enums import ProductStatus
        count = Product.objects.filter(tenant=tenant, status=ProductStatus.ACTIVE).count()
        print(f"  📊 Would index: {count} active products")
        total_indexed += count

print(f"\n🎉 Sync complete!")
print(f"  Total indexed: {total_indexed}")
if total_failed:
    print(f"  ⚠️  Failed: {total_failed}")
