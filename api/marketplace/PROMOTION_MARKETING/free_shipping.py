"""
PROMOTION_MARKETING/free_shipping.py — Free Shipping Rules Engine
==================================================================
Rules (checked in priority order):
  1. Seller offers free shipping for their products
  2. Coupon with free_shipping type
  3. Order amount >= threshold (global or category-specific)
  4. Loyalty tier (Gold/Platinum always free shipping)
  5. First-order free shipping
  6. Promotional campaign includes free shipping
"""
from decimal import Decimal
from django.db import models
from django.utils import timezone

FREE_SHIPPING_GLOBAL_THRESHOLD = Decimal("500")  # BDT


class FreeShippingRule(models.Model):
    tenant      = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True,
                                     related_name="free_shipping_rules_tenant")
    name        = models.CharField(max_length=200)
    rule_type   = models.CharField(max_length=20, choices=[
        ("global_threshold", "Global Order Threshold"),
        ("category",         "Category-based"),
        ("seller",           "Seller Offers Free Shipping"),
        ("loyalty_tier",     "Loyalty Tier"),
        ("first_order",      "First Order"),
        ("coupon",           "Coupon Applied"),
    ])
    min_order_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    applicable_tiers  = models.CharField(max_length=50, blank=True, help_text="gold,platinum")
    is_active         = models.BooleanField(default=True)
    valid_from        = models.DateTimeField(null=True, blank=True)
    valid_until       = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "marketplace"
        db_table  = "marketplace_free_shipping_rule"

    def __str__(self):
        return f"{self.name} ({self.rule_type})"


class FreeShippingEngine:

    def __init__(self, tenant, user=None):
        self.tenant = tenant
        self.user   = user

    def is_free(self, order_amount: Decimal, coupon=None, seller=None,
                is_first_order: bool = False) -> dict:
        """
        Returns {"is_free": bool, "reason": str, "standard_rate": Decimal}
        """
        from api.marketplace.constants import DEFAULT_SHIPPING_RATE
        standard = Decimal(str(DEFAULT_SHIPPING_RATE))

        # 1. Global threshold
        if order_amount >= FREE_SHIPPING_GLOBAL_THRESHOLD:
            return {"is_free": True, "reason": f"Order over {FREE_SHIPPING_GLOBAL_THRESHOLD} BDT", "standard_rate": standard}

        # 2. Coupon free shipping
        if coupon and hasattr(coupon, "coupon_type") and coupon.coupon_type == "free_shipping":
            return {"is_free": True, "reason": f"Coupon: {coupon.code}", "standard_rate": standard}

        # 3. Seller free shipping
        if seller and hasattr(seller, "offers_free_shipping") and seller.offers_free_shipping:
            return {"is_free": True, "reason": f"{seller.store_name} offers free shipping", "standard_rate": standard}

        # 4. Loyalty tier
        if self.user:
            try:
                from api.marketplace.PROMOTION_MARKETING.loyalty_reward import LoyaltyAccount
                acc = LoyaltyAccount.objects.get(user=self.user, tenant=self.tenant)
                if acc.tier in ("gold", "platinum"):
                    return {"is_free": True, "reason": f"{acc.tier.title()} member perk", "standard_rate": standard}
            except Exception:
                pass

        # 5. First order
        if is_first_order:
            return {"is_free": True, "reason": "Free shipping on first order", "standard_rate": standard}

        # 6. DB rules
        now = timezone.now()
        for rule in FreeShippingRule.objects.filter(
            tenant=self.tenant, is_active=True,
            rule_type="global_threshold",
            min_order_amount__lte=order_amount,
        ).filter(
            models.Q(valid_until__isnull=True) | models.Q(valid_until__gte=now)
        ):
            return {"is_free": True, "reason": rule.name, "standard_rate": standard}

        return {"is_free": False, "reason": None, "standard_rate": standard}

    def calculate(self, order_amount: Decimal, **kwargs) -> Decimal:
        result = self.is_free(order_amount, **kwargs)
        return Decimal("0.00") if result["is_free"] else result["standard_rate"]
