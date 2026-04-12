"""seller_bank_account.py — Bank account / mobile banking info"""
from django.db import models
from api.marketplace.models import SellerProfile
from api.tenants.models import Tenant


class SellerBankAccount(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.SET_NULL, null=True,
                               related_name="marketplace_seller_bank_accounts_tenant")
    seller = models.ForeignKey(SellerProfile, on_delete=models.CASCADE,
                               related_name="bank_accounts")
    account_type = models.CharField(max_length=20, choices=[
        ("bank", "Bank"), ("bkash", "bKash"), ("nagad", "Nagad"), ("rocket", "Rocket"),
    ])
    account_name = models.CharField(max_length=200)
    account_number = models.CharField(max_length=50)
    bank_name = models.CharField(max_length=200, blank=True)
    branch_name = models.CharField(max_length=200, blank=True)
    routing_number = models.CharField(max_length=20, blank=True)
    is_primary = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "marketplace"
        db_table = "marketplace_seller_bank_account"

    def __str__(self):
        return f"{self.seller.store_name} — {self.account_type}: {self.account_number}"
