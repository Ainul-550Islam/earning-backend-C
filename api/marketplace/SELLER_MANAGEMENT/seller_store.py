"""seller_store.py — Store page helpers"""
from api.marketplace.models import SellerProfile, Product
from api.marketplace.enums import ProductStatus


def store_products(seller: SellerProfile, active_only=True):
    qs = seller.products.all()
    if active_only:
        qs = qs.filter(status=ProductStatus.ACTIVE)
    return qs.order_by("-created_at")


def store_info(seller: SellerProfile) -> dict:
    return {
        "store_name": seller.store_name,
        "store_logo": seller.store_logo.url if seller.store_logo else None,
        "description": seller.store_description,
        "rating": str(seller.average_rating),
        "total_reviews": seller.total_reviews,
        "total_products": store_products(seller).count(),
    }
