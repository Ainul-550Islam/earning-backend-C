"""
CART_CHECKOUT/cart_model.py — Cart Session Management
======================================================
Handles cart creation, retrieval, expiry and session management.
"""
from __future__ import annotations
import uuid
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from api.marketplace.models import Cart, CartItem
from api.marketplace.constants import CART_EXPIRY_DAYS, MAX_CART_ITEMS


def get_or_create_user_cart(user, tenant) -> Cart:
    """Get active cart for logged-in user or create one."""
    cart = Cart.objects.filter(user=user, tenant=tenant, is_active=True).first()
    if not cart:
        cart = Cart.objects.create(
            user=user, tenant=tenant, is_active=True,
            expires_at=timezone.now() + timedelta(days=CART_EXPIRY_DAYS),
        )
    return cart


def get_or_create_guest_cart(session_key: str, tenant) -> Cart:
    """Get or create a cart for guest (unauthenticated) user."""
    if not session_key:
        session_key = str(uuid.uuid4())
    cart = Cart.objects.filter(session_key=session_key, tenant=tenant, user=None, is_active=True).first()
    if not cart:
        cart = Cart.objects.create(
            session_key=session_key, tenant=tenant, is_active=True,
            expires_at=timezone.now() + timedelta(days=7),
        )
    return cart, session_key


def get_cart_by_id(cart_id: int, tenant) -> Cart:
    try:
        return Cart.objects.get(pk=cart_id, tenant=tenant, is_active=True)
    except Cart.DoesNotExist:
        return None


@transaction.atomic
def merge_carts(guest_cart: Cart, user_cart: Cart) -> Cart:
    """Merge guest cart into user cart when user logs in."""
    for item in guest_cart.items.all():
        existing = user_cart.items.filter(variant=item.variant).first()
        if existing:
            existing.quantity += item.quantity
            existing.save(update_fields=["quantity"])
        else:
            item.cart = user_cart
            item.save(update_fields=["cart"])
    guest_cart.is_active = False
    guest_cart.save(update_fields=["is_active"])
    return user_cart


def expire_old_carts(tenant) -> int:
    """Deactivate carts that have passed their expiry date."""
    count = Cart.objects.filter(
        tenant=tenant, is_active=True, expires_at__lt=timezone.now()
    ).update(is_active=False)
    return count


def refresh_cart_expiry(cart: Cart):
    """Reset expiry time on cart activity."""
    cart.expires_at = timezone.now() + timedelta(days=CART_EXPIRY_DAYS)
    cart.save(update_fields=["expires_at"])


def cart_item_count(cart: Cart) -> int:
    from django.db.models import Sum
    return cart.items.aggregate(total=Sum("quantity"))["total"] or 0


def is_cart_over_limit(cart: Cart) -> bool:
    return cart_item_count(cart) >= MAX_CART_ITEMS


def cart_total_weight(cart: Cart) -> int:
    """Total weight in grams for shipping calculation."""
    total = 0
    for item in cart.items.select_related("variant").all():
        weight = item.variant.weight_grams if item.variant else 200
        total += weight * item.quantity
    return total


def validate_cart_items(cart: Cart) -> dict:
    """
    Validate all cart items before checkout:
    - Check product still active
    - Check sufficient stock
    - Refresh prices
    Returns: {"valid": bool, "errors": list, "refreshed_count": int}
    """
    errors = []
    refreshed = 0
    for item in cart.items.select_related("variant__product","variant__inventory").all():
        product = item.variant.product
        if product.status != "active":
            errors.append(f"'{product.name}' is no longer available.")
            continue
        inv = item.variant.inventory
        if not inv.allow_backorder and inv.available_quantity < item.quantity:
            errors.append(
                f"Only {inv.available_quantity} unit(s) of '{product.name}' available."
            )
            continue
        # Refresh price
        new_price = item.variant.effective_price
        if new_price != item.unit_price:
            item.unit_price = new_price
            item.save(update_fields=["unit_price"])
            refreshed += 1
    return {"valid": len(errors) == 0, "errors": errors, "refreshed_count": refreshed}
