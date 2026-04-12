"""
PRODUCT_MANAGEMENT/product_inventory.py — Race-Condition-Safe Inventory Manager
=================================================================================
Problem: Two users buying the last 1 item simultaneously MUST NOT both succeed.
Solution: PostgreSQL row-level lock via select_for_update() inside an atomic transaction.

Flow (checkout):
  1. BEGIN TRANSACTION
  2. SELECT * FROM inventory WHERE variant_id=X FOR UPDATE   ← locks the row
  3. Check available_quantity >= requested
  4. If yes: reserved_quantity += qty
  5. COMMIT  ← lock released
  If two requests hit simultaneously, the second one WAITS for the first
  to commit, then re-reads the updated reserved_quantity.

Additional features:
  - Backorder support (configurable per variant)
  - Low-stock threshold alerts
  - Reservation timeout (auto-release if order not paid within N minutes)
  - Batch restock with audit log
  - Deduct on delivery (not on order, to support cancellations)
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import List, Optional

from django.db import transaction, DatabaseError
from django.utils import timezone

from api.marketplace.models import ProductInventory, ProductVariant
from api.marketplace.exceptions import OutOfStockException, InsufficientStockException

logger = logging.getLogger(__name__)

RESERVATION_TIMEOUT_MINUTES = 30  # Auto-release if order not confirmed


# ─────────────────────────────────────────────────────────────────────────────
# Custom exceptions
# ─────────────────────────────────────────────────────────────────────────────

class InventoryLockError(InsufficientStockException):
    default_detail = "Could not acquire inventory lock. Please retry."
    default_code   = "inventory_lock_failed"


class BackorderNotAllowed(OutOfStockException):
    default_detail = "This product does not allow backorders."
    default_code   = "backorder_not_allowed"


# ─────────────────────────────────────────────────────────────────────────────
# Core inventory manager
# ─────────────────────────────────────────────────────────────────────────────

class InventoryManager:
    """
    All inventory mutations must go through this class.
    DO NOT call inventory.save() directly from views or services.
    """

    # ── 1. Reserve (checkout) ─────────────────────────────────────────────────
    @classmethod
    @transaction.atomic
    def reserve(cls, variant_id: int, quantity: int) -> ProductInventory:
        """
        Reserve `quantity` units for a pending order.
        Uses SELECT FOR UPDATE to prevent race conditions.

        Raises:
          OutOfStockException       — if quantity=0 and backorder not allowed
          InsufficientStockException — if qty > available and backorder not allowed
          InventoryLockError        — if DB lock cannot be acquired
        """
        if quantity <= 0:
            raise ValueError(f"Quantity must be positive, got {quantity}")

        try:
            # ← THE CRITICAL LINE: locks this row exclusively
            inv = (
                ProductInventory.objects
                .select_for_update(nowait=False)  # nowait=False: wait for lock
                .get(variant_id=variant_id)
            )
        except ProductInventory.DoesNotExist:
            raise OutOfStockException(detail=f"Inventory not found for variant #{variant_id}")
        except DatabaseError as e:
            logger.error("[Inventory] Lock acquisition failed for variant#%s: %s", variant_id, e)
            raise InventoryLockError()

        available = inv.quantity - inv.reserved_quantity

        if available <= 0:
            if not inv.allow_backorder:
                raise OutOfStockException(
                    detail=f"'{inv.variant.name}' is out of stock."
                )
            # Backorder allowed → proceed (no quantity check)
            logger.info(
                "[Inventory] Backorder: variant#%s qty=%s (stock=%s)",
                variant_id, quantity, inv.quantity,
            )
        elif available < quantity:
            if not inv.allow_backorder:
                raise InsufficientStockException(
                    detail=(
                        f"Only {available} unit(s) available for '{inv.variant.name}'. "
                        f"Requested: {quantity}."
                    )
                )

        # Safely increment reserved quantity
        inv.reserved_quantity = inv.reserved_quantity + quantity
        inv.save(update_fields=["reserved_quantity"])

        logger.info(
            "[Inventory] Reserved %s units of variant#%s | "
            "stock=%s reserved=%s available_after=%s",
            quantity, variant_id,
            inv.quantity, inv.reserved_quantity,
            inv.quantity - inv.reserved_quantity,
        )
        return inv

    # ── 2. Release reservation (order cancelled / expired) ───────────────────
    @classmethod
    @transaction.atomic
    def release_reservation(cls, variant_id: int, quantity: int) -> ProductInventory:
        """
        Release a reservation (when order is cancelled / payment times out).
        """
        try:
            inv = (
                ProductInventory.objects
                .select_for_update(nowait=False)
                .get(variant_id=variant_id)
            )
        except ProductInventory.DoesNotExist:
            logger.error("[Inventory] variant#%s not found on release", variant_id)
            return None

        inv.reserved_quantity = max(0, inv.reserved_quantity - quantity)
        inv.save(update_fields=["reserved_quantity"])

        logger.info(
            "[Inventory] Released %s reserved units for variant#%s | new_reserved=%s",
            quantity, variant_id, inv.reserved_quantity,
        )
        return inv

    # ── 3. Deduct (after delivery confirmed) ─────────────────────────────────
    @classmethod
    @transaction.atomic
    def deduct(cls, variant_id: int, quantity: int) -> ProductInventory:
        """
        Permanently deduct stock after delivery is confirmed.
        Also removes from reserved_quantity (it was reserved at checkout).
        """
        try:
            inv = (
                ProductInventory.objects
                .select_for_update(nowait=False)
                .get(variant_id=variant_id)
            )
        except ProductInventory.DoesNotExist:
            logger.error("[Inventory] variant#%s not found on deduct", variant_id)
            return None

        inv.quantity          = max(0, inv.quantity - quantity)
        inv.reserved_quantity = max(0, inv.reserved_quantity - quantity)
        inv.save(update_fields=["quantity", "reserved_quantity"])

        # Check low-stock threshold
        if inv.is_low_stock:
            cls._emit_low_stock_alert(inv)

        logger.info(
            "[Inventory] Deducted %s units from variant#%s | "
            "remaining_stock=%s",
            quantity, variant_id, inv.quantity,
        )
        return inv

    # ── 4. Batch reserve (for multi-item cart checkout) ───────────────────────
    @classmethod
    @transaction.atomic
    def reserve_batch(cls, items: List[dict]) -> List[ProductInventory]:
        """
        Reserve multiple items atomically.
        items = [{"variant_id": int, "quantity": int}, ...]
        If ANY item fails, ALL reservations are rolled back (atomic transaction).
        """
        results = []
        for item in items:
            inv = cls.reserve(item["variant_id"], item["quantity"])
            results.append(inv)
        return results

    # ── 5. Restock ───────────────────────────────────────────────────────────
    @classmethod
    @transaction.atomic
    def restock(cls, variant_id: int, quantity: int, note: str = "") -> ProductInventory:
        """
        Add stock (e.g. new shipment arrived).
        """
        try:
            inv = (
                ProductInventory.objects
                .select_for_update(nowait=False)
                .get(variant_id=variant_id)
            )
        except ProductInventory.DoesNotExist:
            raise OutOfStockException(detail=f"Inventory not found for variant #{variant_id}")

        old_qty = inv.quantity
        inv.quantity          += quantity
        inv.last_restocked_at  = timezone.now()
        inv.save(update_fields=["quantity", "last_restocked_at"])

        logger.info(
            "[Inventory] Restocked variant#%s: %s → %s (added %s) | note: %s",
            variant_id, old_qty, inv.quantity, quantity, note,
        )
        return inv

    # ── 6. Adjust (admin correction) ─────────────────────────────────────────
    @classmethod
    @transaction.atomic
    def adjust(
        cls,
        variant_id: int,
        new_quantity: int,
        reason: str,
        adjusted_by=None,
    ) -> ProductInventory:
        """
        Set absolute quantity (stock take / admin correction).
        Logs the adjustment for audit.
        """
        try:
            inv = (
                ProductInventory.objects
                .select_for_update(nowait=False)
                .get(variant_id=variant_id)
            )
        except ProductInventory.DoesNotExist:
            raise OutOfStockException(detail=f"Inventory not found for variant #{variant_id}")

        old_qty = inv.quantity
        inv.quantity = max(0, new_quantity)
        inv.save(update_fields=["quantity"])

        # Audit log
        InventoryAuditLog.log(
            variant_id=variant_id,
            action="adjust",
            old_quantity=old_qty,
            new_quantity=inv.quantity,
            reason=reason,
            adjusted_by=adjusted_by,
        )

        logger.info(
            "[Inventory] Adjusted variant#%s: %s → %s | reason: %s | by: %s",
            variant_id, old_qty, inv.quantity, reason, adjusted_by,
        )
        return inv

    # ── 7. Auto-release expired reservations ──────────────────────────────────
    @classmethod
    def release_expired_reservations(cls, tenant) -> int:
        """
        Release reservations for unpaid orders older than RESERVATION_TIMEOUT_MINUTES.
        Called by Celery periodic task.
        """
        from api.marketplace.models import Order, OrderItem
        from api.marketplace.enums import OrderStatus
        from datetime import timedelta

        cutoff = timezone.now() - timedelta(minutes=RESERVATION_TIMEOUT_MINUTES)
        stale_orders = Order.objects.filter(
            tenant=tenant,
            status=OrderStatus.PENDING,
            is_paid=False,
            created_at__lt=cutoff,
        )

        released_count = 0
        for order in stale_orders:
            for item in order.items.filter(variant__isnull=False):
                try:
                    cls.release_reservation(item.variant_id, item.quantity)
                    released_count += 1
                except Exception as e:
                    logger.error(
                        "[Inventory] Failed to release reservation for OrderItem#%s: %s",
                        item.pk, e,
                    )
            # Cancel the stale order
            order.status = OrderStatus.CANCELLED
            order.cancelled_at = timezone.now()
            order.cancellation_reason = "Auto-cancelled: payment timeout"
            order.save(update_fields=["status", "cancelled_at", "cancellation_reason"])

        logger.info("[Inventory] Released %s expired reservations.", released_count)
        return released_count

    # ── Private helpers ───────────────────────────────────────────────────────
    @staticmethod
    def _emit_low_stock_alert(inv: ProductInventory):
        """Fire a low-stock event for notification system."""
        try:
            from api.marketplace.events import emit, LOW_STOCK
            emit(LOW_STOCK, inventory=inv)
        except Exception as e:
            logger.error("[Inventory] Failed to emit LOW_STOCK event: %s", e)


# ─────────────────────────────────────────────────────────────────────────────
# Audit log (lightweight — no separate model needed)
# ─────────────────────────────────────────────────────────────────────────────

class InventoryAuditLog:
    """Simple in-DB audit trail for inventory adjustments."""

    @staticmethod
    def log(variant_id: int, action: str, old_quantity: int,
            new_quantity: int, reason: str = "", adjusted_by=None):
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO marketplace_inventory_audit
                        (variant_id, action, old_quantity, new_quantity, reason, adjusted_by_id, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT DO NOTHING
                """, [
                    variant_id, action, old_quantity, new_quantity, reason,
                    getattr(adjusted_by, "pk", None),
                ])
        except Exception:
            # Table may not exist yet — just log to file
            logger.info(
                "[InventoryAudit] variant#%s | %s | %s→%s | %s",
                variant_id, action, old_quantity, new_quantity, reason,
            )


# ─────────────────────────────────────────────────────────────────────────────
# Query helpers
# ─────────────────────────────────────────────────────────────────────────────

def get_low_stock_items(tenant, threshold: int = 10):
    """All inventory items below threshold."""
    return ProductInventory.objects.filter(
        variant__product__tenant=tenant,
        quantity__lte=threshold,
        track_quantity=True,
    ).select_related("variant__product__seller", "variant__product__category")


def get_out_of_stock(tenant):
    """All inventory items with zero available stock."""
    return ProductInventory.objects.filter(
        variant__product__tenant=tenant,
        quantity=0,
        allow_backorder=False,
        track_quantity=True,
    ).select_related("variant__product")


def check_availability(variant_id: int, quantity: int) -> dict:
    """
    Non-locking check (for display only — use reserve() at checkout).
    Returns {"available": bool, "quantity": int}.
    """
    try:
        inv = ProductInventory.objects.get(variant_id=variant_id)
        available = inv.quantity - inv.reserved_quantity
        return {
            "available": available >= quantity or inv.allow_backorder,
            "in_stock": inv.quantity > 0,
            "available_quantity": max(0, available),
            "allow_backorder": inv.allow_backorder,
            "is_low_stock": inv.is_low_stock,
        }
    except ProductInventory.DoesNotExist:
        return {"available": False, "in_stock": False, "available_quantity": 0}


# ── Module-level convenience wrappers ────────────────────────────────────────
def reserve(variant_id: int, quantity: int) -> ProductInventory:
    return InventoryManager.reserve(variant_id, quantity)

def release_reservation(variant_id: int, quantity: int) -> ProductInventory:
    return InventoryManager.release_reservation(variant_id, quantity)

def deduct(variant_id: int, quantity: int) -> ProductInventory:
    return InventoryManager.deduct(variant_id, quantity)

def restock(variant_id: int, quantity: int, note: str = "") -> ProductInventory:
    return InventoryManager.restock(variant_id, quantity, note)

def reserve_batch(items: list) -> list:
    return InventoryManager.reserve_batch(items)
