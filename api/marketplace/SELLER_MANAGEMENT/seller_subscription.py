"""seller_subscription.py — Seller plan/subscription (basic/pro/enterprise)"""
from django.db import models
from api.marketplace.models import SellerProfile
from api.tenants.models import Tenant


class SellerSubscription(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.SET_NULL, null=True,
                               related_name="marketplace_seller_subscriptions_tenant")
    seller = models.OneToOneField(SellerProfile, on_delete=models.CASCADE,
                                  related_name="subscription")
    plan = models.CharField(max_length=20, choices=[
        ("basic", "Basic"), ("pro", "Pro"), ("enterprise", "Enterprise")
    ], default="basic")
    started_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        app_label = "marketplace"
        db_table = "marketplace_seller_subscription"

    def __str__(self):
        return f"{self.seller.store_name} — {self.plan}"
