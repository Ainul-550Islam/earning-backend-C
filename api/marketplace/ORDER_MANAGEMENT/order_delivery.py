"""ORDER_MANAGEMENT/order_delivery.py — Delivery Confirmation & Proof"""
from django.db import models
from django.conf import settings
from api.marketplace.models import Order
from api.tenants.models import Tenant
from django.utils import timezone


class DeliveryProof(models.Model):
    """Photo/signature proof of delivery."""
    tenant      = models.ForeignKey(Tenant, on_delete=models.SET_NULL, null=True,
                                    related_name="marketplace_delivery_proofs_tenant")
    order       = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="delivery_proof")
    photo       = models.ImageField(upload_to="marketplace/delivery/photos/", null=True, blank=True)
    signature   = models.ImageField(upload_to="marketplace/delivery/signatures/", null=True, blank=True)
    otp_verified= models.BooleanField(default=False)
    delivered_by= models.CharField(max_length=100, blank=True)
    notes       = models.TextField(blank=True)
    delivered_at= models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "marketplace"
        db_table  = "marketplace_delivery_proof"

    def __str__(self):
        return f"Proof: {self.order.order_number}"


def confirm_delivery_with_otp(order: Order, otp: str) -> bool:
    """Verify OTP sent to customer and mark delivered."""
    from django.core.cache import cache
    stored_otp = cache.get(f"delivery_otp:{order.pk}")
    if str(stored_otp) != str(otp):
        return False
    from api.marketplace.services import mark_order_delivered
    mark_order_delivered(order)
    cache.delete(f"delivery_otp:{order.pk}")
    return True


def generate_delivery_otp(order: Order) -> str:
    """Generate a 6-digit OTP for delivery confirmation."""
    import random
    from django.core.cache import cache
    otp = str(random.randint(100000, 999999))
    cache.set(f"delivery_otp:{order.pk}", otp, timeout=600)  # 10 min
    return otp
