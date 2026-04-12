"""
marketplace/dependencies.py — DRF / FastAPI-style dependency helpers
"""

from rest_framework.exceptions import PermissionDenied, NotFound
from .models import SellerProfile, Product, Order
from .enums import SellerStatus


def get_seller_or_403(user, tenant) -> SellerProfile:
    """Return seller profile or raise 403."""
    try:
        seller = SellerProfile.objects.get(user=user, tenant=tenant)
    except SellerProfile.DoesNotExist:
        raise PermissionDenied("You do not have a seller profile.")
    if seller.status != SellerStatus.ACTIVE:
        raise PermissionDenied(f"Seller account is {seller.status}.")
    return seller


def get_product_or_404(tenant, pk) -> Product:
    try:
        return Product.objects.get(pk=pk, tenant=tenant)
    except Product.DoesNotExist:
        raise NotFound("Product not found.")


def get_order_or_404(user, tenant, pk) -> Order:
    try:
        return Order.objects.get(pk=pk, tenant=tenant, user=user)
    except Order.DoesNotExist:
        raise NotFound("Order not found.")


def require_admin(user):
    if not user.is_staff:
        raise PermissionDenied("Admin access required.")
