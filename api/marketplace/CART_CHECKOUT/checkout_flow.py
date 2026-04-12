"""
CART_CHECKOUT/checkout_flow.py — Full Checkout Flow Orchestrator
"""
from __future__ import annotations
import logging
from decimal import Decimal
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


class CheckoutFlow:
    """
    Multi-step checkout:
    Step 1: Validate cart (stock, seller status)
    Step 2: Apply coupon & calculate totals
    Step 3: Collect address & payment method
    Step 4: Create order (reserve inventory)
    Step 5: Initiate payment
    Step 6: On payment success → split & create escrow
    """

    def __init__(self, cart, user, tenant):
        self.cart   = cart
        self.user   = user
        self.tenant = tenant

    def validate(self) -> dict:
        """Step 1: Validate entire cart."""
        errors = []
        items  = self.cart.items.select_related(
            "variant__product__seller","variant__inventory"
        ).all()

        if not items.exists():
            return {"valid": False, "errors": ["Cart is empty"]}

        for item in items:
            # Check seller active
            seller = item.variant.product.seller
            if seller.status != "active":
                errors.append(f"'{seller.store_name}' is not accepting orders.")
            # Check stock
            inv = item.variant.inventory
            if inv.available_quantity < item.quantity and not inv.allow_backorder:
                errors.append(
                    f"Only {inv.available_quantity} unit(s) of '{item.variant.product.name}' available."
                )
            # Check product active
            if item.variant.product.status != "active":
                errors.append(f"'{item.variant.product.name}' is no longer available.")

        return {"valid": len(errors) == 0, "errors": errors}

    def calculate_totals(self, coupon_code: str = "") -> dict:
        """Step 2: Calculate pricing with coupon."""
        from api.marketplace.CART_CHECKOUT.cart_item import get_cart_summary
        summary = get_cart_summary(self.cart)

        if coupon_code:
            from api.marketplace.CART_CHECKOUT.cart_coupon import apply_coupon
            try:
                apply_coupon(self.cart, coupon_code, self.user)
                summary = get_cart_summary(self.cart)
            except Exception as e:
                summary["coupon_error"] = str(e)

        return summary

    @transaction.atomic
    def place_order(self, shipping_data: dict, payment_method: str) -> dict:
        """Steps 3-4: Create order + reserve inventory."""
        # Validate first
        validation = self.validate()
        if not validation["valid"]:
            return {"success": False, "errors": validation["errors"]}

        from api.marketplace.services import create_order_from_cart
        try:
            order = create_order_from_cart(self.cart, payment_method, shipping_data)
            logger.info("[Checkout] Order placed: %s | user: %s", order.order_number, self.user.username)
            return {
                "success":      True,
                "order_number": order.order_number,
                "order_id":     order.pk,
                "total":        str(order.total_price),
                "payment_method": order.payment_method,
            }
        except Exception as e:
            logger.error("[Checkout] Order creation failed: %s", e)
            return {"success": False, "errors": [str(e)]}

    def initiate_payment(self, order) -> dict:
        """Step 5: Start payment process."""
        from api.marketplace.services import create_payment_transaction
        tx = create_payment_transaction(order, order.payment_method)
        if order.payment_method == "cod":
            return {"method": "cod", "message": "Pay on delivery", "order_number": order.order_number}

        # For digital payments → call gateway
        from api.marketplace.PAYMENT_SETTLEMENT.payment_gateway import get_gateway
        from django.conf import settings
        try:
            creds = getattr(settings, "PAYMENT_CREDENTIALS", {}).get(order.payment_method, {})
            gateway = get_gateway(order.payment_method, creds)
            result  = gateway.create_payment(
                amount=float(order.total_price),
                phone=order.shipping_phone,
                reference=order.order_number,
            )
            return {"method": order.payment_method, "gateway_response": result,
                    "transaction_id": str(tx.transaction_id)}
        except Exception as e:
            logger.error("[Checkout] Payment initiation failed: %s", e)
            return {"success": False, "error": str(e)}
