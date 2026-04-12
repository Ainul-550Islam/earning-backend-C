"""
marketplace/services.py — Business Logic Layer
================================================
Pure Python service functions. No Django views / serializers here.
Each function accepts validated data and returns a model instance or raises
a marketplace exception.
"""

from __future__ import annotations

from decimal import Decimal
from django.db import transaction
from django.utils import timezone

from .models import (
    Cart, CartItem, Order, OrderItem, OrderTracking,
    Product, ProductVariant, ProductInventory,
    SellerProfile, SellerVerification, SellerPayout,
    EscrowHolding, PaymentTransaction, RefundRequest,
    Coupon,
)
from .enums import (
    OrderStatus, TrackingEvent, PaymentStatus, EscrowStatus,
    RefundStatus, SellerStatus, PayoutStatus,
)
from .exceptions import (
    OutOfStockException, InsufficientStockException, CartEmptyException,
    CouponInvalidException, PaymentFailedException, RefundWindowExpiredException,
    SellerNotVerifiedException, InsufficientPayoutBalanceException,
)
from .constants import ESCROW_RELEASE_DAYS, REVIEW_WINDOW_DAYS


# ──────────────────────────────────────────────
# CART SERVICES
# ──────────────────────────────────────────────

def add_to_cart(cart: Cart, variant: ProductVariant, quantity: int = 1) -> CartItem:
    """Add / update CartItem, enforcing stock limits."""
    inventory: ProductInventory = variant.inventory
    if inventory.is_out_of_stock and not inventory.allow_backorder:
        raise OutOfStockException()

    item, created = CartItem.objects.get_or_create(
        cart=cart,
        variant=variant,
        defaults={"unit_price": variant.effective_price, "quantity": 0,
                  "tenant": cart.tenant},
    )

    new_qty = item.quantity + quantity
    if inventory.available_quantity < new_qty and not inventory.allow_backorder:
        raise InsufficientStockException(
            detail=f"Only {inventory.available_quantity} unit(s) available."
        )

    item.quantity = new_qty
    item.unit_price = variant.effective_price   # refresh price
    item.save()
    return item


def remove_from_cart(cart: Cart, variant_id: int) -> None:
    CartItem.objects.filter(cart=cart, variant_id=variant_id).delete()


def apply_coupon_to_cart(cart: Cart, code: str) -> Coupon:
    try:
        coupon = Coupon.objects.get(code=code, tenant=cart.tenant)
    except Coupon.DoesNotExist:
        raise CouponInvalidException()
    if not coupon.is_valid:
        raise CouponInvalidException()
    cart.coupon = coupon
    cart.save(update_fields=["coupon"])
    return coupon


# ──────────────────────────────────────────────
# ORDER SERVICES
# ──────────────────────────────────────────────

@transaction.atomic
def create_order_from_cart(cart: Cart, payment_method: str, shipping_data: dict) -> Order:
    """Convert a cart into an Order, reserve inventory."""
    items = cart.items.select_related("variant__product", "variant__inventory").all()
    if not items.exists():
        raise CartEmptyException()

    # Calculate totals
    subtotal = sum(item.subtotal for item in items)
    coupon = cart.coupon
    discount = coupon.calculate_discount(subtotal) if coupon and coupon.is_valid else Decimal("0.00")
    shipping = _calculate_shipping(items, subtotal)
    tax = _calculate_tax(subtotal - discount)
    total = subtotal - discount + shipping + tax

    order = Order.objects.create(
        tenant=cart.tenant,
        user=cart.user,
        coupon=coupon,
        coupon_code=coupon.code if coupon else "",
        subtotal=subtotal,
        discount_amount=discount,
        shipping_charge=shipping,
        tax_amount=tax,
        total_price=total,
        payment_method=payment_method,
        **shipping_data,
    )

    # Create order items & reserve inventory
    for ci in items:
        variant = ci.variant
        inventory = variant.inventory
        inventory.reserve(ci.quantity)

        commission_config = _get_commission(variant.product)
        commission = commission_config.calculate(ci.subtotal)
        seller_net = ci.subtotal - commission

        OrderItem.objects.create(
            tenant=order.tenant,
            order=order,
            seller=variant.product.seller,
            variant=variant,
            product_name=variant.product.name,
            variant_name=variant.name,
            sku=variant.sku,
            quantity=ci.quantity,
            unit_price=ci.unit_price,
            subtotal=ci.subtotal,
            commission_rate=commission_config.rate,
            commission_amount=commission,
            seller_net=seller_net,
        )

    # Increment coupon usage
    if coupon:
        Coupon.objects.filter(pk=coupon.pk).update(used_count=coupon.used_count + 1)

    # Add initial tracking
    OrderTracking.objects.create(
        tenant=order.tenant,
        order=order,
        event=TrackingEvent.ORDER_PLACED,
        description="Order has been placed successfully.",
    )

    # Clear cart
    cart.items.all().delete()
    cart.coupon = None
    cart.save(update_fields=["coupon"])

    return order


def confirm_order(order: Order, confirmed_by=None) -> Order:
    order.status = OrderStatus.CONFIRMED
    order.save(update_fields=["status"])
    OrderTracking.objects.create(
        tenant=order.tenant, order=order,
        event=TrackingEvent.SELLER_CONFIRMED,
        description="Order confirmed by seller.",
        created_by=confirmed_by,
    )
    return order


def mark_order_shipped(order: Order, courier: str, tracking_number: str, created_by=None) -> Order:
    order.status = OrderStatus.SHIPPED
    order.save(update_fields=["status"])
    OrderTracking.objects.create(
        tenant=order.tenant, order=order,
        event=TrackingEvent.PICKED_UP,
        description=f"Picked up by {courier}. Tracking: {tracking_number}",
        courier_name=courier,
        tracking_number=tracking_number,
        created_by=created_by,
    )
    return order


@transaction.atomic
def mark_order_delivered(order: Order, created_by=None) -> Order:
    order.status = OrderStatus.DELIVERED
    order.save(update_fields=["status"])

    OrderTracking.objects.create(
        tenant=order.tenant, order=order,
        event=TrackingEvent.DELIVERED,
        description="Package delivered to customer.",
        created_by=created_by,
    )

    # Deduct inventory, create escrow holdings
    for item in order.items.all():
        if item.variant:
            item.variant.inventory.deduct(item.quantity)
        release_after = timezone.now() + timezone.timedelta(days=ESCROW_RELEASE_DAYS)
        EscrowHolding.objects.get_or_create(
            order_item=item,
            defaults={
                "tenant": order.tenant,
                "seller": item.seller,
                "gross_amount": item.subtotal,
                "commission_deducted": item.commission_amount,
                "net_amount": item.seller_net,
                "release_after": release_after,
            },
        )
    return order


# ──────────────────────────────────────────────
# PAYMENT SERVICES
# ──────────────────────────────────────────────

def create_payment_transaction(order: Order, method: str, ip: str = "") -> PaymentTransaction:
    return PaymentTransaction.objects.create(
        tenant=order.tenant,
        order=order,
        user=order.user,
        method=method,
        amount=order.total_price,
        ip_address=ip or None,
    )


def process_payment_success(tx: PaymentTransaction, gateway_id: str, response: dict) -> Order:
    tx.mark_success(gateway_id=gateway_id, response=response)
    order = tx.order
    order.is_paid = True
    order.paid_at = timezone.now()
    order.status = OrderStatus.CONFIRMED
    order.save(update_fields=["is_paid", "paid_at", "status"])
    OrderTracking.objects.create(
        tenant=order.tenant, order=order,
        event=TrackingEvent.PAYMENT_CONFIRMED,
        description="Payment confirmed.",
    )
    return order


# ──────────────────────────────────────────────
# REFUND SERVICES
# ──────────────────────────────────────────────

def request_refund(
    order_item: OrderItem, user, reason: str, description: str, amount: Decimal
) -> RefundRequest:
    days_since = (timezone.now() - order_item.order.created_at).days
    if days_since > REVIEW_WINDOW_DAYS:
        raise RefundWindowExpiredException()

    return RefundRequest.objects.create(
        tenant=order_item.tenant,
        order_item=order_item,
        user=user,
        reason=reason,
        description=description,
        amount_requested=amount,
    )


@transaction.atomic
def approve_refund(refund: RefundRequest, amount: Decimal, reviewed_by) -> RefundRequest:
    refund.status = RefundStatus.APPROVED
    refund.amount_approved = amount
    refund.reviewed_by = reviewed_by
    refund.reviewed_at = timezone.now()
    refund.save()

    # Freeze escrow if exists
    try:
        escrow = refund.order_item.escrow
        escrow.status = EscrowStatus.REFUNDED
        escrow.save(update_fields=["status"])
    except EscrowHolding.DoesNotExist:
        pass

    return refund


# ──────────────────────────────────────────────
# PAYOUT SERVICES
# ──────────────────────────────────────────────

@transaction.atomic
def release_escrow_and_credit(escrow: EscrowHolding) -> SellerPayout:
    escrow.release()
    seller = escrow.seller
    payout = SellerPayout.objects.create(
        tenant=seller.tenant,
        seller=seller,
        amount=escrow.net_amount,
        account_number=seller.phone,
        status=PayoutStatus.PENDING,
        balance_before=seller.total_revenue,
        note=f"Auto-release from escrow for order item #{escrow.order_item_id}",
    )
    seller.total_revenue += escrow.net_amount
    seller.save(update_fields=["total_revenue"])
    return payout


# ──────────────────────────────────────────────
# PRIVATE HELPERS
# ──────────────────────────────────────────────

def _calculate_shipping(items, subtotal: Decimal) -> Decimal:
    from .constants import FREE_SHIPPING_THRESHOLD, DEFAULT_SHIPPING_RATE
    if subtotal >= Decimal(str(FREE_SHIPPING_THRESHOLD)):
        return Decimal("0.00")
    return Decimal(str(DEFAULT_SHIPPING_RATE))


def _calculate_tax(taxable: Decimal) -> Decimal:
    from .constants import DEFAULT_VAT_RATE
    return (taxable * Decimal(str(DEFAULT_VAT_RATE))).quantize(Decimal("0.01"))


def _get_commission(product: Product):
    from .models import CommissionConfig
    try:
        return CommissionConfig.objects.get(category=product.category, is_active=True)
    except CommissionConfig.DoesNotExist:
        try:
            return CommissionConfig.objects.get(category__isnull=True, is_active=True)
        except CommissionConfig.DoesNotExist:
            # Fallback object — won't be saved to DB
            cfg = CommissionConfig()
            return cfg
