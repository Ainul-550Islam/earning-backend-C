"""
SCRIPTS/cleanup_old_orders.py — Archive and clean up old data
Usage: python manage.py shell < api/marketplace/SCRIPTS/cleanup_old_orders.py
"""
import os, django
from datetime import timedelta
os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
django.setup()

from django.utils import timezone
from api.marketplace.models import Order
from api.marketplace.enums import OrderStatus

cutoff = timezone.now() - timedelta(days=180)

# Cancel very old pending orders
stale = Order.objects.filter(status=OrderStatus.PENDING, is_paid=False, created_at__lt=cutoff)
count = stale.count()
stale.update(status=OrderStatus.CANCELLED, cancelled_at=timezone.now(),
             cancellation_reason="Auto-cancelled: 180+ days pending")
print(f"✅ Cancelled {count} stale pending orders")

# Report
delivered = Order.objects.filter(status=OrderStatus.DELIVERED, created_at__lt=cutoff).count()
print(f"ℹ️  {delivered} old delivered orders (archivable)")
print("✅ Cleanup complete!")
