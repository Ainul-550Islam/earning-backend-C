"""
CART_CHECKOUT/cart_coupon.py — Cart Coupon Application
"""
from decimal import Decimal
from api.marketplace.models import Cart, Coupon
from api.marketplace.exceptions import CouponInvalidException, CouponExpiredException, CouponUsageLimitException


def apply_coupon(cart: Cart, code: str, user=None) -> dict:
    try:
        coupon = Coupon.objects.get(code=code.upper().strip(), tenant=cart.tenant)
    except Coupon.DoesNotExist:
        raise CouponInvalidException(detail="Coupon code not found.")

    if not coupon.is_active:
        raise CouponInvalidException(detail="This coupon is no longer active.")

    from django.utils import timezone
    now = timezone.now()
    if coupon.valid_from > now:
        raise CouponInvalidException(detail="Coupon is not yet valid.")
    if coupon.valid_until < now:
        raise CouponExpiredException()

    if coupon.used_count >= coupon.usage_limit:
        raise CouponUsageLimitException()

    # Check per-user limit
    if user and coupon.usage_per_user > 0:
        from api.marketplace.models import Order
        used_by_user = Order.objects.filter(user=user, coupon=coupon).count()
        if used_by_user >= coupon.usage_per_user:
            raise CouponUsageLimitException(detail="You have already used this coupon the maximum number of times.")

    # Check minimum order amount
    cart_total = cart.total
    if cart_total < coupon.min_order_amount:
        raise CouponInvalidException(
            detail=f"Minimum order amount for this coupon is {coupon.min_order_amount} BDT."
        )

    discount = coupon.calculate_discount(cart_total)
    cart.coupon = coupon
    cart.save(update_fields=["coupon"])

    return {
        "success":     True,
        "coupon_code": coupon.code,
        "coupon_type": coupon.coupon_type,
        "discount":    str(discount),
        "new_total":   str(cart_total - discount),
        "message":     f"Coupon applied! You saved {discount} BDT.",
    }


def remove_coupon(cart: Cart) -> dict:
    cart.coupon = None
    cart.save(update_fields=["coupon"])
    return {"success": True, "message": "Coupon removed."}


def validate_coupon_only(code: str, tenant, order_amount: Decimal) -> dict:
    """Validate without applying — for frontend preview."""
    try:
        coupon = Coupon.objects.get(code=code.upper().strip(), tenant=tenant)
        if not coupon.is_valid:
            return {"valid": False, "reason": "Coupon expired or limit reached"}
        if order_amount < coupon.min_order_amount:
            return {"valid": False, "reason": f"Min order: {coupon.min_order_amount} BDT"}
        discount = coupon.calculate_discount(order_amount)
        return {"valid": True, "discount": str(discount), "type": coupon.coupon_type}
    except Coupon.DoesNotExist:
        return {"valid": False, "reason": "Coupon not found"}
