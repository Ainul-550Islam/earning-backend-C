"""
PRODUCT_MANAGEMENT/product_bundle.py — Product Bundle / Combo Deals
====================================================================
A bundle = 2+ products sold together at a discounted combined price.
"""
from __future__ import annotations
from decimal import Decimal
from typing import List
from django.db import models
from django.conf import settings
from api.marketplace.models import Product
from api.tenants.models import Tenant


class ProductBundle(models.Model):
    tenant         = models.ForeignKey(Tenant, on_delete=models.SET_NULL, null=True,
                                        related_name="product_bundles_tenant")
    name           = models.CharField(max_length=200)
    description    = models.TextField(blank=True)
    products       = models.ManyToManyField(Product, related_name="bundles")
    discount_type  = models.CharField(max_length=10, choices=[("percent","Percent"),("fixed","Fixed")], default="percent")
    discount_value = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("10"))
    is_active      = models.BooleanField(default=True)
    max_uses       = models.PositiveIntegerField(null=True, blank=True)
    used_count     = models.PositiveIntegerField(default=0)
    starts_at      = models.DateTimeField(null=True, blank=True)
    ends_at        = models.DateTimeField(null=True, blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "marketplace"
        db_table  = "marketplace_product_bundle"

    def __str__(self):
        return self.name

    @property
    def is_live(self) -> bool:
        from django.utils import timezone
        now = timezone.now()
        if not self.is_active:
            return False
        if self.max_uses and self.used_count >= self.max_uses:
            return False
        if self.starts_at and now < self.starts_at:
            return False
        if self.ends_at and now > self.ends_at:
            return False
        return True


# ── Calculation ────────────────────────────────────────────────────────────────

def calculate_bundle_price(products: List[Product], discount_percent: Decimal) -> Decimal:
    """Calculate discounted bundle price."""
    total    = sum(p.effective_price for p in products)
    discount = total * discount_percent / 100
    return (total - discount).quantize(Decimal("0.01"))


def bundle_savings(products: List[Product], bundle: "ProductBundle") -> dict:
    """Show how much the user saves with a bundle."""
    total     = sum(p.effective_price for p in products)
    if bundle.discount_type == "percent":
        discount = total * bundle.discount_value / 100
    else:
        discount = bundle.discount_value
    discount  = min(discount, total)
    final     = total - discount
    return {
        "total_individual": str(total.quantize(Decimal("0.01"))),
        "bundle_price":     str(final.quantize(Decimal("0.01"))),
        "you_save":         str(discount.quantize(Decimal("0.01"))),
        "savings_percent":  round(discount / total * 100, 1) if total else 0,
    }


def get_active_bundles(tenant, product=None) -> list:
    qs = ProductBundle.objects.filter(tenant=tenant, is_active=True)
    if product:
        qs = qs.filter(products=product)
    from django.utils import timezone
    now = timezone.now()
    qs  = qs.filter(
        models.Q(starts_at__isnull=True) | models.Q(starts_at__lte=now)
    ).filter(
        models.Q(ends_at__isnull=True) | models.Q(ends_at__gte=now)
    )
    return list(qs.prefetch_related("products"))


def validate_bundle(product_ids: list, tenant) -> dict:
    """Check all products in bundle are active and available."""
    products = Product.objects.filter(pk__in=product_ids, tenant=tenant)
    errors   = []
    for p in products:
        if p.status != "active":
            errors.append(f"'{p.name}' is not active")
    missing = set(product_ids) - {p.pk for p in products}
    if missing:
        errors.append(f"Products not found: {missing}")
    return {"valid": len(errors) == 0, "errors": errors}
