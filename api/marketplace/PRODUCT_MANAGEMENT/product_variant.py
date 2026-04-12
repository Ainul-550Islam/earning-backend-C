"""
PRODUCT_MANAGEMENT/product_variant.py — Product Variant Management
"""
from decimal import Decimal
from django.db import transaction
from api.marketplace.models import ProductVariant, ProductInventory, Product
from api.marketplace.utils import generate_sku


@transaction.atomic
def create_variant(product: Product, name: str, color: str = "", size: str = "",
                   price_modifier: Decimal = Decimal("0"), stock: int = 0,
                   sku: str = None, weight_grams: int = 0, **kwargs) -> ProductVariant:
    """Create a variant with automatic SKU and inventory."""
    if not sku:
        from api.marketplace.PRODUCT_MANAGEMENT.product_sku import generate_unique_sku
        sku = generate_unique_sku(product.name, color, size)

    variant = ProductVariant.objects.create(
        tenant=product.tenant, product=product, name=name,
        color=color, size=size, sku=sku,
        price_modifier=price_modifier,
        weight_grams=weight_grams,
        is_active=True, **kwargs,
    )
    ProductInventory.objects.create(
        tenant=product.tenant, variant=variant, quantity=stock,
    )
    return variant


def update_variant(variant: ProductVariant, **data) -> ProductVariant:
    allowed = ["name","color","size","price_modifier","sale_price","weight_grams","is_active","material"]
    for field in allowed:
        if field in data:
            setattr(variant, field, data[field])
    variant.save()
    return variant


def get_variant_by_attributes(product: Product, color: str = "", size: str = "") -> ProductVariant:
    qs = ProductVariant.objects.filter(product=product, is_active=True)
    if color:
        qs = qs.filter(color__iexact=color)
    if size:
        qs = qs.filter(size__iexact=size)
    return qs.first()


def get_available_options(product: Product) -> dict:
    """Get all available color/size options for a product."""
    variants = ProductVariant.objects.filter(product=product, is_active=True)
    colors = sorted({v.color for v in variants if v.color})
    sizes  = sorted({v.size  for v in variants if v.size})
    return {"colors": colors, "sizes": sizes}


def clone_variant(variant: ProductVariant, new_color: str = None, new_size: str = None,
                   new_stock: int = 0) -> ProductVariant:
    """Duplicate a variant with a new color/size combination."""
    color = new_color or variant.color
    size  = new_size  or variant.size
    return create_variant(
        product=variant.product, name=f"{color} {size}".strip() or variant.name,
        color=color, size=size, price_modifier=variant.price_modifier,
        sale_price=variant.sale_price, weight_grams=variant.weight_grams,
        stock=new_stock,
    )


def deactivate_variant(variant: ProductVariant) -> ProductVariant:
    variant.is_active = False
    variant.save(update_fields=["is_active"])
    return variant


def variant_availability_matrix(product: Product) -> list:
    """Return a matrix of all color/size combos with availability."""
    variants = ProductVariant.objects.filter(product=product).select_related("inventory")
    matrix   = []
    for v in variants:
        try:
            available = v.inventory.available_quantity
        except Exception:
            available = 0
        matrix.append({
            "variant_id": v.pk,
            "color":      v.color,
            "size":       v.size,
            "sku":        v.sku,
            "price":      str(v.effective_price),
            "available":  available,
            "in_stock":   available > 0,
            "is_active":  v.is_active,
        })
    return matrix
