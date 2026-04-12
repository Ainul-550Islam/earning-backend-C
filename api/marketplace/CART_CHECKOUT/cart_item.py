"""
CART_CHECKOUT/cart_item.py — Cart Item Business Logic
"""
from decimal import Decimal
from api.marketplace.models import Cart, CartItem, ProductVariant
from api.marketplace.exceptions import OutOfStockException, InsufficientStockException


def add_item(cart: Cart, variant_id: int, quantity: int = 1) -> CartItem:
    from api.marketplace.PRODUCT_MANAGEMENT.product_inventory import check_availability
    availability = check_availability(variant_id, quantity)
    if not availability["available"]:
        raise OutOfStockException(detail=f"Only {availability['available_quantity']} unit(s) available.")

    try:
        variant = ProductVariant.objects.get(pk=variant_id, tenant=cart.tenant, is_active=True)
    except ProductVariant.DoesNotExist:
        raise OutOfStockException(detail="Product variant not found or inactive.")

    item, created = CartItem.objects.get_or_create(
        cart=cart, variant=variant,
        defaults={"unit_price": variant.effective_price, "quantity": 0, "tenant": cart.tenant}
    )
    new_qty = item.quantity + quantity
    recheck = check_availability(variant_id, new_qty)
    if not recheck["available"]:
        raise InsufficientStockException(
            detail=f"Cannot add {new_qty} total. Only {recheck['available_quantity']} available."
        )
    item.quantity   = new_qty
    item.unit_price = variant.effective_price  # refresh price
    item.save()
    return item


def update_quantity(cart: Cart, variant_id: int, quantity: int) -> CartItem:
    if quantity <= 0:
        CartItem.objects.filter(cart=cart, variant_id=variant_id).delete()
        return None
    from api.marketplace.PRODUCT_MANAGEMENT.product_inventory import check_availability
    if not check_availability(variant_id, quantity)["available"]:
        raise InsufficientStockException()
    item = CartItem.objects.get(cart=cart, variant_id=variant_id)
    item.quantity = quantity
    item.save(update_fields=["quantity"])
    return item


def remove_item(cart: Cart, variant_id: int):
    CartItem.objects.filter(cart=cart, variant_id=variant_id).delete()


def clear_cart(cart: Cart):
    cart.items.all().delete()
    cart.coupon = None
    cart.save(update_fields=["coupon"])


def get_cart_summary(cart: Cart) -> dict:
    items     = cart.items.select_related("variant__product","variant__inventory").all()
    subtotal  = cart.total
    coupon    = cart.coupon
    discount  = coupon.calculate_discount(subtotal) if coupon and coupon.is_valid else Decimal("0")
    shipping  = _estimate_shipping(subtotal)
    tax       = _estimate_tax(subtotal - discount)
    return {
        "item_count":  cart.item_count,
        "subtotal":    str(subtotal),
        "discount":    str(discount),
        "coupon_code": coupon.code if coupon else None,
        "shipping":    str(shipping),
        "tax":         str(tax),
        "total":       str(subtotal - discount + shipping + tax),
    }


def _estimate_shipping(subtotal: Decimal) -> Decimal:
    from api.marketplace.constants import FREE_SHIPPING_THRESHOLD, DEFAULT_SHIPPING_RATE
    return Decimal("0") if subtotal >= Decimal(str(FREE_SHIPPING_THRESHOLD)) else Decimal(str(DEFAULT_SHIPPING_RATE))

def _estimate_tax(taxable: Decimal) -> Decimal:
    from api.marketplace.constants import DEFAULT_VAT_RATE
    return (taxable * Decimal(str(DEFAULT_VAT_RATE))).quantize(Decimal("0.01"))
