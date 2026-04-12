"""
PRODUCT_MANAGEMENT/product_model.py — Product Model Helpers & Business Logic
=============================================================================
"""
from decimal import Decimal
from django.db.models import Q
from api.marketplace.models import Product, ProductVariant, ProductAttribute, ProductInventory
from api.marketplace.enums import ProductStatus, ProductCondition


# ── Create ────────────────────────────────────────────────────────────────────
def create_product(seller, tenant, category, name: str, description: str,
                   base_price: Decimal, **kwargs) -> Product:
    from api.marketplace.utils import unique_slugify
    slug = unique_slugify(Product, name)
    return Product.objects.create(
        seller=seller, tenant=tenant, category=category,
        name=name, slug=slug, description=description,
        base_price=base_price, status=ProductStatus.DRAFT, **kwargs
    )


def publish_product(product: Product) -> Product:
    """Activate a draft product after validation."""
    errors = validate_for_publish(product)
    if errors:
        raise ValueError(f"Cannot publish: {'; '.join(errors)}")
    product.status = ProductStatus.ACTIVE
    product.save(update_fields=["status"])
    return product


def validate_for_publish(product: Product) -> list:
    errors = []
    if not product.name.strip():
        errors.append("Product name is required")
    if not product.description.strip():
        errors.append("Description is required")
    if product.base_price <= 0:
        errors.append("Price must be greater than 0")
    if not product.category:
        errors.append("Category is required")
    if not product.variants.filter(is_active=True).exists():
        errors.append("At least one active variant is required")
    if not product.variants.filter(is_active=True, inventory__quantity__gte=0).exists():
        errors.append("Inventory must be set for all variants")
    return errors


# ── Read ──────────────────────────────────────────────────────────────────────
def get_product_detail(product_id: int, tenant) -> Product:
    return Product.objects.prefetch_related(
        "attributes","variants__inventory","variants__product"
    ).select_related("category","seller").get(pk=product_id, tenant=tenant)


def get_active_products(tenant, category=None, limit: int = None):
    qs = Product.objects.filter(tenant=tenant, status=ProductStatus.ACTIVE).select_related("category","seller")
    if category:
        qs = qs.filter(category=category)
    if limit:
        qs = qs[:limit]
    return qs


def search_products(tenant, query: str, filters: dict = None):
    qs = Product.objects.filter(tenant=tenant, status=ProductStatus.ACTIVE)
    if query:
        qs = qs.filter(
            Q(name__icontains=query) | Q(description__icontains=query) | Q(tags__icontains=query)
        )
    if filters:
        if filters.get("min_price"):
            qs = qs.filter(base_price__gte=filters["min_price"])
        if filters.get("max_price"):
            qs = qs.filter(base_price__lte=filters["max_price"])
        if filters.get("min_rating"):
            qs = qs.filter(average_rating__gte=filters["min_rating"])
        if filters.get("in_stock"):
            qs = qs.filter(variants__inventory__quantity__gt=0).distinct()
    return qs


# ── Update ────────────────────────────────────────────────────────────────────
def update_product_status(product: Product, status: str) -> Product:
    if status not in ProductStatus.values:
        raise ValueError(f"Invalid status: {status}")
    product.status = status
    product.save(update_fields=["status"])
    return product


def duplicate_product(product: Product, new_name: str = None) -> Product:
    """Create a copy of an existing product as draft."""
    from api.marketplace.utils import unique_slugify
    name = new_name or f"Copy of {product.name}"
    slug = unique_slugify(Product, name)
    new_product = Product.objects.create(
        tenant=product.tenant, seller=product.seller, category=product.category,
        name=name, slug=slug, description=product.description,
        short_description=product.short_description,
        base_price=product.base_price, sale_price=product.sale_price,
        condition=product.condition, tags=product.tags,
        status=ProductStatus.DRAFT,
    )
    # Copy attributes
    for attr in product.attributes.all():
        ProductAttribute.objects.create(
            tenant=product.tenant, product=new_product,
            name=attr.name, value=attr.value, unit=attr.unit,
        )
    return new_product


# ── Stats ─────────────────────────────────────────────────────────────────────
def product_stats(product: Product) -> dict:
    from api.marketplace.models import OrderItem
    from django.db.models import Sum, Count
    orders = OrderItem.objects.filter(variant__product=product)
    agg = orders.aggregate(total_units=Sum("quantity"), total_revenue=Sum("subtotal"))
    return {
        "total_sales":    product.total_sales,
        "total_revenue":  str(agg["total_revenue"] or 0),
        "units_sold":     agg["total_units"] or 0,
        "average_rating": str(product.average_rating),
        "review_count":   product.review_count,
        "variants_count": product.variants.count(),
        "in_stock":       any(
            v.inventory.available_quantity > 0
            for v in product.variants.all()
            if hasattr(v, "inventory")
        ),
    }


__all__ = [
    "Product","ProductVariant","ProductAttribute","ProductInventory",
    "ProductStatus","ProductCondition",
    "create_product","publish_product","validate_for_publish",
    "get_product_detail","get_active_products","search_products",
    "update_product_status","duplicate_product","product_stats",
]
