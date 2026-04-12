"""
SCRIPTS/analytics_processor.py — Run analytics aggregations
Usage: python manage.py shell < api/marketplace/SCRIPTS/analytics_processor.py
"""
import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
django.setup()

from api.tenants.models import Tenant
from api.marketplace.REVIEW_RATING.product_rating_aggregator import bulk_recalculate as recalc_ratings
from api.marketplace.REVIEW_RATING.seller_rating_aggregator import bulk_recalculate as recalc_seller_ratings

for tenant in Tenant.objects.filter(is_active=True):
    print(f"\n📊 Processing {tenant.name}...")
    product_count = recalc_ratings(tenant)
    seller_count  = recalc_seller_ratings(tenant)
    print(f"  ✅ Product ratings updated: {product_count}")
    print(f"  ✅ Seller ratings updated:  {seller_count}")

print("\n✅ Analytics processing complete!")
