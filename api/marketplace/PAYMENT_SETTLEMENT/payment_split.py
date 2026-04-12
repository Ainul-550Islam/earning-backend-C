"""
PAYMENT_SETTLEMENT/payment_split.py — Multi-Vendor Payment Split Engine
========================================================================
Handles splitting a single customer payment across multiple sellers,
deducting platform commission, calculating tax, and queuing payouts.

Flow:
  Customer pays ₹ Total
    └─► Platform escrow receives full amount
    └─► For each OrderItem:
          gross          = item.subtotal
          commission     = CommissionCalculator.calculate(gross, category)
          tax_collected  = TaxCalculator.calculate(gross)
          seller_net     = gross - commission - tax_collected
          → EscrowHolding created
    └─► Platform fee = Σ commission
    └─► Seller payout queued after escrow release
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import List

from django.db import transaction

from api.marketplace.models import Order, OrderItem, EscrowHolding
from api.marketplace.PAYMENT_SETTLEMENT.commission_calculator import CommissionCalculator
from api.marketplace.PAYMENT_SETTLEMENT.tax_calculator import calculate_vat
from api.marketplace.PAYMENT_SETTLEMENT.escrow_manager import EscrowManager

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Data structures
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ItemSplit:
    order_item_id: int
    seller_id: int
    seller_name: str
    gross_amount: Decimal
    commission_rate: Decimal
    commission_amount: Decimal
    tax_amount: Decimal
    seller_net: Decimal
    escrow_id: int = 0


@dataclass
class OrderSplit:
    order_id: int
    order_number: str
    total_paid: Decimal
    platform_commission: Decimal   # Σ commissions
    total_tax: Decimal
    total_seller_net: Decimal
    items: List[ItemSplit] = field(default_factory=list)

    @property
    def platform_revenue(self) -> Decimal:
        """Platform keeps commission + tax."""
        return self.platform_commission + self.total_tax

    def to_dict(self) -> dict:
        return {
            "order_number": self.order_number,
            "total_paid": str(self.total_paid),
            "platform_commission": str(self.platform_commission),
            "total_tax": str(self.total_tax),
            "platform_revenue": str(self.platform_revenue),
            "total_seller_net": str(self.total_seller_net),
            "splits": [
                {
                    "order_item_id": s.order_item_id,
                    "seller": s.seller_name,
                    "gross": str(s.gross_amount),
                    "commission_rate": f"{s.commission_rate}%",
                    "commission": str(s.commission_amount),
                    "tax": str(s.tax_amount),
                    "seller_net": str(s.seller_net),
                    "escrow_id": s.escrow_id,
                }
                for s in self.items
            ],
        }


# ─────────────────────────────────────────────────────────────────────────────
# Core splitter
# ─────────────────────────────────────────────────────────────────────────────

class PaymentSplitEngine:
    """
    Executes the full payment split for an order.
    Creates EscrowHolding for each OrderItem atomically.
    """

    def __init__(self):
        self.commission_calc = CommissionCalculator()

    @transaction.atomic
    def split(self, order: Order) -> OrderSplit:
        """
        Split `order.total_price` into per-seller escrow holdings.
        Must be called immediately after payment is confirmed (is_paid=True).

        Returns an OrderSplit summary for logging / API response.
        """
        items = (
            OrderItem.objects
            .select_related("variant__product__category", "seller")
            .filter(order=order)
        )

        if not items.exists():
            raise ValueError(f"Order #{order.order_number} has no items to split.")

        order_split = OrderSplit(
            order_id=order.pk,
            order_number=order.order_number,
            total_paid=order.total_price,
            platform_commission=Decimal("0.00"),
            total_tax=Decimal("0.00"),
            total_seller_net=Decimal("0.00"),
        )

        for item in items:
            item_split = self._split_item(item)
            order_split.items.append(item_split)
            order_split.platform_commission += item_split.commission_amount
            order_split.total_tax           += item_split.tax_amount
            order_split.total_seller_net    += item_split.seller_net

        logger.info(
            "[PaymentSplit] Order#%s | Total: %s | Commission: %s | Net to sellers: %s",
            order.order_number,
            order_split.total_paid,
            order_split.platform_commission,
            order_split.total_seller_net,
        )
        return order_split

    def _split_item(self, item: OrderItem) -> ItemSplit:
        category = (
            item.variant.product.category if item.variant else None
        )
        gross = item.subtotal

        # Commission (category-aware, multi-level)
        commission_rate, commission_amount = self.commission_calc.calculate(
            amount=gross,
            category=category,
            tenant=item.tenant,
        )

        # Tax collected by platform
        tax_amount = calculate_vat(gross - commission_amount)

        seller_net = gross - commission_amount - tax_amount
        if seller_net < Decimal("0"):
            seller_net = Decimal("0.00")
            logger.warning(
                "[PaymentSplit] seller_net negative for OrderItem#%s — floored to 0",
                item.pk,
            )

        # Persist to OrderItem for record-keeping
        OrderItem.objects.filter(pk=item.pk).update(
            commission_rate=commission_rate,
            commission_amount=commission_amount,
            seller_net=seller_net,
        )

        # Create escrow holding
        escrow = EscrowManager.create_for_order_item(
            order_item=item,
            gross_amount=gross,
            commission_amount=commission_amount,
        )

        return ItemSplit(
            order_item_id=item.pk,
            seller_id=item.seller_id,
            seller_name=item.seller.store_name if item.seller else "—",
            gross_amount=gross,
            commission_rate=commission_rate,
            commission_amount=commission_amount,
            tax_amount=tax_amount,
            seller_net=seller_net,
            escrow_id=escrow.pk,
        )


# ── Convenience function ──────────────────────────────────────────────────────
_engine = PaymentSplitEngine()


def execute_payment_split(order: Order) -> OrderSplit:
    """
    Entry point called from services.process_payment_success().
    Thread-safe — each item uses select_for_update inside EscrowManager.
    """
    return _engine.split(order)


def get_split_summary(order: Order) -> dict:
    """Return existing split data from DB (no recalculation)."""
    items = OrderItem.objects.filter(order=order).select_related("seller")
    from django.db.models import Sum
    agg = items.aggregate(
        total_commission=Sum("commission_amount"),
        total_net=Sum("seller_net"),
        total_gross=Sum("subtotal"),
    )
    return {
        "order_number": order.order_number,
        "gross_revenue": str(agg["total_gross"] or 0),
        "platform_commission": str(agg["total_commission"] or 0),
        "total_seller_net": str(agg["total_net"] or 0),
        "items": [
            {
                "seller": item.seller.store_name if item.seller else "—",
                "gross": str(item.subtotal),
                "commission": str(item.commission_amount),
                "seller_net": str(item.seller_net),
            }
            for item in items
        ],
    }
