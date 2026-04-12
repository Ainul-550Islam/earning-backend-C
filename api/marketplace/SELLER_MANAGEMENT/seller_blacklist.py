"""seller_blacklist.py — Blacklist fraudulent sellers"""
from django.db import models
from api.tenants.models import Tenant
from django.conf import settings


class SellerBlacklist(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.SET_NULL, null=True,
                               related_name="marketplace_seller_blacklist_tenant")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="marketplace_blacklist_entries")
    reason = models.TextField()
    blacklisted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                       null=True, related_name="marketplace_blacklisted_sellers")
    created_at = models.DateTimeField(auto_now_add=True)
    is_permanent = models.BooleanField(default=False)

    class Meta:
        app_label = "marketplace"
        db_table = "marketplace_seller_blacklist"

    def __str__(self):
        return f"Blacklist: {self.user.username}"
