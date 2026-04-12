"""
SCRIPTS/seed_database.py — Seed initial marketplace data

Usage:
    python manage.py shell < api/marketplace/SCRIPTS/seed_database.py
"""
import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from decimal import Decimal
from django.contrib.auth import get_user_model
from api.tenants.models import Tenant
from api.marketplace.models import (
    Category, CommissionConfig, SellerProfile, Product,
    ProductVariant, ProductInventory,
)
from api.marketplace.utils import unique_slugify, generate_sku

User = get_user_model()

print("🌱 Seeding marketplace data...")

# ── Tenant ──────────────────────────────────────
tenant, _ = Tenant.objects.get_or_create(
    slug="demo",
    defaults={"name": "Demo Marketplace", "domain": "demo.localhost", "is_active": True}
)
print(f"  ✅ Tenant: {tenant.name}")

# ── Global Commission ────────────────────────────
cfg, _ = CommissionConfig.objects.get_or_create(
    tenant=tenant, category=None,
    defaults={"rate": Decimal("10.00"), "flat_fee": Decimal("5.00")}
)
print(f"  ✅ Global Commission: {cfg.rate}%")

# ── Categories ───────────────────────────────────
CATEGORIES = [
    ("Electronics", "electronics"),
    ("Fashion", "fashion"),
    ("Home & Living", "home-living"),
    ("Books", "books"),
    ("Sports", "sports"),
]
categories = {}
for name, slug in CATEGORIES:
    cat, _ = Category.objects.get_or_create(
        tenant=tenant, slug=slug,
        defaults={"name": name, "is_active": True}
    )
    categories[slug] = cat
    CommissionConfig.objects.get_or_create(
        tenant=tenant, category=cat,
        defaults={"rate": Decimal("12.00")}
    )
print(f"  ✅ {len(categories)} categories created")

# ── Seller ───────────────────────────────────────
seller_user, _ = User.objects.get_or_create(
    username="demo_seller",
    defaults={"email": "seller@demo.com", "is_active": True}
)
seller_user.set_password("Demo@1234")
seller_user.save()

seller, _ = SellerProfile.objects.get_or_create(
    user=seller_user, tenant=tenant,
    defaults={
        "store_name": "Demo Store",
        "store_slug": "demo-store",
        "phone": "+8801700000001",
        "status": "active",
        "city": "Dhaka",
        "country": "Bangladesh",
    }
)
print(f"  ✅ Seller: {seller.store_name}")

# ── Products ─────────────────────────────────────
PRODUCTS = [
    ("Samsung Galaxy A54", "electronics", 35000, 32000),
    ("Cotton T-Shirt", "fashion", 800, 650),
    ("Python Programming Book", "books", 500, 450),
    ("Yoga Mat", "sports", 1200, 999),
    ("Ceramic Mug", "home-living", 250, None),
]

for name, cat_slug, base, sale in PRODUCTS:
    slug = unique_slugify(Product, name)
    p, created = Product.objects.get_or_create(
        tenant=tenant, slug=slug,
        defaults={
            "seller": seller,
            "category": categories[cat_slug],
            "name": name,
            "description": f"High quality {name}.",
            "base_price": Decimal(str(base)),
            "sale_price": Decimal(str(sale)) if sale else None,
            "status": "active",
        }
    )
    if created:
        v = ProductVariant.objects.create(
            tenant=tenant, product=p,
            name="Default", sku=generate_sku(name),
        )
        ProductInventory.objects.create(tenant=tenant, variant=v, quantity=100)
print(f"  ✅ {len(PRODUCTS)} products seeded")

print("\n🎉 Seed complete!")
