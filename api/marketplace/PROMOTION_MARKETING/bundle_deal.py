"""
PROMOTION_MARKETING/bundle_deal.py — Product Bundle / Combo Deals
"""
from decimal import Decimal
from django.db import models
from django.utils import timezone


class BundleDeal(models.Model):
    tenant      = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True,
                                     related_name="bundle_deals_tenant")
    name        = models.CharField(max_length=200)
    products    = models.ManyToManyField("marketplace.Product", related_name="bundle_deals")
    bundle_price= models.DecimalField(max_digits=12, decimal_places=2, help_text="Price for the whole bundle")
    is_active   = models.BooleanField(default=True)
    starts_at   = models.DateTimeField(null=True, blank=True)
    ends_at     = models.DateTimeField(null=True, blank=True)
    max_quantity= models.PositiveIntegerField(default=1000)
    sold_count  = models.PositiveIntegerField(default=0)

    class Meta:
        app_label = "marketplace"
        db_table  = "marketplace_bundle_deal"

    @property
    def total_individual_price(self) -> Decimal:
        return sum(p.effective_price for p in self.products.all())

    @property
    def savings(self) -> Decimal:
        return self.total_individual_price - self.bundle_price

    @property
    def discount_percent(self) -> float:
        total = float(self.total_individual_price)
        if total == 0:
            return 0.0
        return round((1 - float(self.bundle_price) / total) * 100, 1)

    @property
    def is_live(self) -> bool:
        now = timezone.now()
        if not self.is_active:
            return False
        if self.starts_at and now < self.starts_at:
            return False
        if self.ends_at and now > self.ends_at:
            return False
        return self.sold_count < self.max_quantity


def get_active_bundles(tenant) -> list:
    now = timezone.now()
    qs = BundleDeal.objects.filter(tenant=tenant, is_active=True).prefetch_related("products")
    return [b for b in qs if b.is_live]


def calculate_bundle_savings(bundle: BundleDeal) -> dict:
    return {
        "individual_total": str(bundle.total_individual_price),
        "bundle_price":     str(bundle.bundle_price),
        "savings":          str(bundle.savings),
        "discount_percent": bundle.discount_percent,
    }
