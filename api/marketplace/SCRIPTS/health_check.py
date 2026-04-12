"""
SCRIPTS/health_check.py — Marketplace health check

Usage:
    python manage.py shell < api/marketplace/SCRIPTS/health_check.py
"""
import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from api.marketplace.models import (
    Product, Order, SellerProfile, Coupon, ProductInventory
)
from api.marketplace.enums import OrderStatus, EscrowStatus
from api.marketplace.models import EscrowHolding
from django.utils import timezone

print("🏥 Marketplace Health Check")
print("=" * 40)
print(f"  Active products     : {Product.objects.filter(status='active').count()}")
print(f"  Active sellers      : {SellerProfile.objects.filter(status='active').count()}")
print(f"  Pending orders      : {Order.objects.filter(status=OrderStatus.PENDING).count()}")
print(f"  Active coupons      : {Coupon.objects.filter(is_active=True, valid_until__gte=timezone.now()).count()}")
print(f"  Overdue escrows     : {EscrowHolding.objects.filter(status=EscrowStatus.HOLDING, release_after__lt=timezone.now()).count()}")
out_of_stock = ProductInventory.objects.filter(quantity=0, track_quantity=True).count()
print(f"  Out-of-stock items  : {out_of_stock}")
print("=" * 40)
print("✅ Health check complete")
