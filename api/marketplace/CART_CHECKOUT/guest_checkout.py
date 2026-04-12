"""
CART_CHECKOUT/guest_checkout.py — Guest Checkout (no login required)
"""
import uuid
from django.utils import timezone
from datetime import timedelta
from api.marketplace.models import Cart


def get_or_create_guest_cart(session_key: str, tenant) -> Cart:
    if not session_key:
        session_key = str(uuid.uuid4())

    cart, _ = Cart.objects.get_or_create(
        session_key=session_key,
        tenant=tenant,
        user=None,
        is_active=True,
        defaults={"expires_at": timezone.now() + timedelta(days=7)}
    )
    return cart


def merge_guest_cart_to_user(session_key: str, user, tenant) -> Cart:
    """Called when guest logs in — merge guest cart into user's cart."""
    try:
        guest_cart = Cart.objects.get(session_key=session_key, tenant=tenant, user=None, is_active=True)
    except Cart.DoesNotExist:
        return Cart.objects.filter(user=user, tenant=tenant, is_active=True).first()

    user_cart, _ = Cart.objects.get_or_create(
        user=user, tenant=tenant, is_active=True,
        defaults={"expires_at": timezone.now() + timedelta(days=30)}
    )

    # Move items from guest to user cart
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


def guest_checkout_summary(session_key: str, tenant) -> dict:
    try:
        cart = Cart.objects.get(session_key=session_key, tenant=tenant, is_active=True)
    except Cart.DoesNotExist:
        return {"items": [], "total": "0"}

    from api.marketplace.CART_CHECKOUT.cart_item import get_cart_summary
    return get_cart_summary(cart)
