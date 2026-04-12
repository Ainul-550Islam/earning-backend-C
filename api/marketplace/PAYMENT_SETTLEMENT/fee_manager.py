"""
PAYMENT_SETTLEMENT/fee_manager.py — Platform Fee Configuration & Management
"""
from decimal import Decimal
from django.db import models


class PlatformFeeConfig(models.Model):
    tenant        = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True,
                                       related_name="fee_configs_tenant")
    fee_type      = models.CharField(max_length=30, choices=[
        ("payment_processing","Payment Processing Fee"),
        ("listing",           "Product Listing Fee"),
        ("flash_sale",        "Flash Sale Participation Fee"),
        ("featured",          "Featured Product Fee"),
        ("subscription",      "Seller Subscription Fee"),
        ("withdrawal",        "Withdrawal Fee"),
    ])
    method        = models.CharField(max_length=20, blank=True, help_text="Payment method (blank=all)")
    rate          = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0"))
    flat_amount   = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0"))
    min_fee       = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0"))
    max_fee       = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    is_active     = models.BooleanField(default=True)

    class Meta:
        app_label = "marketplace"
        db_table  = "marketplace_platform_fee_config"

    def calculate(self, amount: Decimal) -> Decimal:
        fee = (amount * self.rate / 100) + self.flat_amount
        fee = max(fee, self.min_fee)
        if self.max_fee:
            fee = min(fee, self.max_fee)
        return fee.quantize(Decimal("0.01"))


PAYMENT_PROCESSING_FEES = {
    "bkash":  {"rate": Decimal("1.5"),  "flat": Decimal("0")},
    "nagad":  {"rate": Decimal("1.5"),  "flat": Decimal("0")},
    "rocket": {"rate": Decimal("1.8"),  "flat": Decimal("0")},
    "card":   {"rate": Decimal("2.5"),  "flat": Decimal("10")},
    "cod":    {"rate": Decimal("0"),    "flat": Decimal("0")},
}


def get_payment_processing_fee(method: str, amount: Decimal) -> Decimal:
    fees = PAYMENT_PROCESSING_FEES.get(method, {"rate": Decimal("2"), "flat": Decimal("0")})
    fee  = (amount * fees["rate"] / 100) + fees["flat"]
    return fee.quantize(Decimal("0.01"))


def get_withdrawal_fee(amount: Decimal, method: str = "bkash") -> Decimal:
    """Fee deducted when seller withdraws funds."""
    if amount < Decimal("500"):
        return Decimal("20")
    if amount < Decimal("2000"):
        return Decimal("30")
    return (amount * Decimal("1.5") / 100).quantize(Decimal("0.01"))


def listing_fee_for_category(category_slug: str) -> Decimal:
    """Some premium categories have listing fees."""
    premium_categories = {"electronics": Decimal("50"), "fashion": Decimal("20")}
    return premium_categories.get(category_slug, Decimal("0"))
