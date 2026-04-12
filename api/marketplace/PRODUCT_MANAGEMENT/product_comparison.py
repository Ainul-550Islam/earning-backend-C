"""
PRODUCT_MANAGEMENT/product_comparison.py — Compare products side-by-side
"""
from typing import List
from api.marketplace.models import Product, ProductAttribute


def compare_products(product_ids: List[int]) -> dict:
    products = Product.objects.filter(pk__in=product_ids).prefetch_related("attributes")
    all_attr_names = set()
    product_attrs = {}
    for p in products:
        attrs = {a.name: f"{a.value} {a.unit}".strip() for a in p.attributes.all()}
        product_attrs[p.id] = attrs
        all_attr_names.update(attrs.keys())

    return {
        "products": [{"id": p.id, "name": p.name, "price": str(p.effective_price)} for p in products],
        "attributes": {
            attr: {p.id: product_attrs[p.id].get(attr, "—") for p in products}
            for attr in sorted(all_attr_names)
        },
    }
