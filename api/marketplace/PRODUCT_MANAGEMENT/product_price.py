"""
PRODUCT_MANAGEMENT/product_price.py — Product Pricing Management
"""
from decimal import Decimal
from typing import Optional
from django.db import transaction
from api.marketplace.models import Product, ProductVariant


def update_product_price(product: Product, base_price: Decimal,
                          sale_price: Optional[Decimal] = None) -> Product:
    """Update base and sale price for a product."""
    if base_price <= 0:
        raise ValueError("Base price must be greater than 0")
    if sale_price and sale_price >= base_price:
        raise ValueError("Sale price must be less than base price")
    product.base_price = base_price
    product.sale_price = sale_price
    product.save(update_fields=["base_price","sale_price"])
    return product


def bulk_apply_discount(product_ids: list, percent: Decimal, tenant=None):
    """Apply a percentage discount to multiple products."""
    from api.marketplace.utils import calculate_discount_amount
    qs = Product.objects.filter(pk__in=product_ids)
    if tenant:
        qs = qs.filter(tenant=tenant)
    updated = 0
    for product in qs:
        disc = calculate_discount_amount(product.base_price, percent)
        product.sale_price = (product.base_price - disc).quantize(Decimal("0.01"))
        product.save(update_fields=["sale_price"])
        updated += 1
    return {"updated": updated, "discount_percent": str(percent)}


def remove_sale_price(product: Product) -> Product:
    product.sale_price = None
    product.save(update_fields=["sale_price"])
    return product


def bulk_remove_discounts(product_ids: list, tenant=None) -> int:
    qs = Product.objects.filter(pk__in=product_ids, sale_price__isnull=False)
    if tenant:
        qs = qs.filter(tenant=tenant)
    return qs.update(sale_price=None)


def price_history(product: Product) -> list:
    """Placeholder — integrate with price history model if needed."""
    return [{"price": str(product.base_price), "sale": str(product.sale_price or ""), "current": True}]


def get_price_range(tenant, category=None) -> dict:
    """Min/max prices in the marketplace or category."""
    from django.db.models import Min, Max
    qs = Product.objects.filter(tenant=tenant, status="active")
    if category:
        qs = qs.filter(category=category)
    agg = qs.aggregate(min_p=Min("base_price"), max_p=Max("base_price"))
    return {"min": str(agg["min_p"] or 0), "max": str(agg["max_p"] or 0)}


def compare_prices(product_ids: list, tenant=None) -> list:
    """Compare prices across multiple products."""
    qs = Product.objects.filter(pk__in=product_ids)
    if tenant:
        qs = qs.filter(tenant=tenant)
    return [
        {
            "id":               p.pk,
            "name":             p.name,
            "base_price":       str(p.base_price),
            "sale_price":       str(p.sale_price) if p.sale_price else None,
            "effective_price":  str(p.effective_price),
            "discount_percent": p.discount_percent,
        }
        for p in qs
    ]


def validate_pricing(base_price: Decimal, sale_price: Optional[Decimal] = None) -> dict:
    errors = []
    if base_price <= 0:
        errors.append("Base price must be positive")
    if base_price > Decimal("1000000"):
        errors.append("Base price exceeds maximum allowed (1,000,000 BDT)")
    if sale_price:
        if sale_price <= 0:
            errors.append("Sale price must be positive")
        if sale_price >= base_price:
            errors.append("Sale price must be lower than base price")
        discount_pct = (base_price - sale_price) / base_price * 100
        if discount_pct > 90:
            errors.append("Discount cannot exceed 90%")
    return {"valid": len(errors) == 0, "errors": errors}
