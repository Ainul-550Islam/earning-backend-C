"""
services.py – Inventory module business logic.

All public functions are atomic where mutations occur.
SELECT FOR UPDATE is used on stock rows to prevent oversell under high concurrency.
Never import from views/serializers here.
"""
import logging
import secrets
import string
from typing import List, Optional

from django.db import transaction
from django.utils import timezone

from .choices import (
    CodeStatus,
    DeliveryMethod,
    InventoryStatus,
    ItemStatus,
    StockEventType,
)
from .constants import (
    DELIVERY_RETRY_DELAY_SECONDS,
    MAX_DELIVERY_RETRY_ATTEMPTS,
    REDEMPTION_CODE_CHARSET,
    REDEMPTION_CODE_LENGTH,
    STOCK_RESERVATION_TTL_SECONDS,
    UNLIMITED_STOCK,
)
from .exceptions import (
    BulkImportException,
    CodeAlreadyRedeemedException,
    CodeExpiredException,
    CodeVoidedException,
    DeliveryFailedException,
    InsufficientStockException,
    InvalidCodeException,
    ItemNotActiveException,
    ItemNotFoundException,
    ItemQuantityLimitExceededException,
    NoCodesAvailableException,
    StockAdjustmentException,
    UserInventoryNotFoundException,
)
from .models import RedemptionCode, RewardItem, StockEvent, StockManager, UserInventory
from .signals import (
    code_redeemed,
    inventory_created,
    item_delivered,
    item_delivery_failed,
    item_revoked,
    low_stock_alert,
    stock_depleted,
    stock_replenished,
)
from .validators import (
    validate_bulk_code_count,
    validate_redemption_code_format,
    validate_user_item_quantity_limit,
)

logger = logging.getLogger(__name__)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _generate_code() -> str:
    return "".join(secrets.choice(REDEMPTION_CODE_CHARSET) for _ in range(REDEMPTION_CODE_LENGTH))


def _record_stock_event(
    item: RewardItem,
    event_type: str,
    delta: int,
    stock_before: int,
    stock_after: int,
    reference_id: str = "",
    performed_by=None,
    note: str = "",
) -> StockEvent:
    return StockEvent.objects.create(
        item=item,
        event_type=event_type,
        quantity_delta=delta,
        stock_before=stock_before,
        stock_after=stock_after,
        reference_id=str(reference_id),
        performed_by=performed_by,
        note=note,
    )


def _check_and_fire_stock_alerts(item: RewardItem) -> None:
    """Evaluate stock level and fire signals / update alert flags."""
    try:
        sm = item.stock_manager
    except StockManager.DoesNotExist:
        return

    changed = sm.update_alert_level()
    if changed and sm.alert_level != "none":
        low_stock_alert.send(sender=RewardItem, instance=item, alert_level=sm.alert_level)
        sm.alert_sent = True
        sm.alert_sent_at = timezone.now()
        sm.save(update_fields=["alert_sent", "alert_sent_at", "updated_at"])

    if item.current_stock == 0:
        stock_depleted.send(sender=RewardItem, instance=item)


# ── RewardItem helpers ────────────────────────────────────────────────────────

def get_active_items(item_type: Optional[str] = None):
    qs = RewardItem.objects.active().in_stock().with_stock_manager()
    if item_type:
        qs = qs.filter(item_type=item_type)
    return qs.order_by("sort_order", "name")


def get_item_or_raise(item_id) -> RewardItem:
    return RewardItem.objects.get_active_or_raise(item_id)


# ── Stock Management ──────────────────────────────────────────────────────────

@transaction.atomic
def restock_item(
    item_id,
    quantity: int,
    performed_by=None,
    note: str = "",
) -> RewardItem:
    """Add stock to a RewardItem. Records audit event and fires signals."""
    if quantity <= 0:
        raise StockAdjustmentException(detail=f"Restock quantity must be positive. Got {quantity}.")

    item = RewardItem.objects.select_for_update().get(pk=item_id)
    stock_before = item.current_stock

    item.increment_stock(quantity)

    _record_stock_event(
        item=item,
        event_type=StockEventType.RESTOCK,
        delta=quantity,
        stock_before=stock_before,
        stock_after=item.current_stock,
        performed_by=performed_by,
        note=note,
    )
    stock_replenished.send(sender=RewardItem, instance=item, qty=quantity)
    _check_and_fire_stock_alerts(item)
    logger.info("Restocked '%s' by %d (now %d)", item.name, quantity, item.current_stock)
    return item


@transaction.atomic
def adjust_stock(
    item_id,
    delta: int,
    performed_by=None,
    note: str = "",
) -> RewardItem:
    """
    Manual stock adjustment (positive or negative).
    Raises StockAdjustmentException if result would be negative.
    """
    from .validators import validate_stock_adjustment_will_not_go_negative
    item = RewardItem.objects.select_for_update().get(pk=item_id)

    if item.is_unlimited and delta < 0:
        raise StockAdjustmentException(detail="Cannot reduce stock on an unlimited item.")

    validate_stock_adjustment_will_not_go_negative(item, delta)

    stock_before = item.current_stock
    new_stock = stock_before + delta
    item.current_stock = new_stock
    item.save(update_fields=["current_stock", "updated_at"])

    _record_stock_event(
        item=item,
        event_type=StockEventType.ADJUSTMENT,
        delta=delta,
        stock_before=stock_before,
        stock_after=new_stock,
        performed_by=performed_by,
        note=note,
    )
    _check_and_fire_stock_alerts(item)
    logger.info("Adjusted '%s' by %+d (now %d)", item.name, delta, new_stock)
    return item


# ── RedemptionCode Management ─────────────────────────────────────────────────

@transaction.atomic
def bulk_import_codes(
    item_id,
    codes: List[str],
    batch_id: str = "",
    expires_at=None,
    performed_by=None,
) -> int:
    """
    Bulk-import a list of redemption codes for an item.
    Validates format, checks for duplicates, and records a stock event.
    Returns the count of successfully imported codes.
    """
    validate_bulk_code_count(len(codes))

    try:
        item = RewardItem.objects.select_for_update().get(pk=item_id)
    except RewardItem.DoesNotExist:
        raise ItemNotFoundException()

    errors = []
    valid_codes = []
    seen = set()

    for i, raw_code in enumerate(codes, start=1):
        code = raw_code.strip().upper().replace("-", "").replace(" ", "")
        if code in seen:
            errors.append(f"Row {i}: duplicate within batch – {code}")
            continue
        try:
            validate_redemption_code_format(code)
        except Exception as exc:
            errors.append(f"Row {i}: {exc}")
            continue
        seen.add(code)
        valid_codes.append(code)

    if errors:
        raise BulkImportException(errors=errors)

    # Filter out codes that already exist in the DB
    existing = set(
        RedemptionCode.objects.filter(code__in=valid_codes).values_list("code", flat=True)
    )
    new_codes = [c for c in valid_codes if c not in existing]
    duplicates_in_db = len(valid_codes) - len(new_codes)
    if duplicates_in_db:
        logger.warning("%d code(s) already exist in DB – skipped.", duplicates_in_db)

    if not new_codes:
        raise BulkImportException(errors=["All provided codes already exist in the database."])

    objs = [
        RedemptionCode(
            item=item,
            code=code,
            batch_id=batch_id,
            expires_at=expires_at,
        )
        for code in new_codes
    ]
    RedemptionCode.objects.bulk_create(objs, batch_size=500)

    # Update stock if item uses codes as stock proxy
    if item.current_stock != UNLIMITED_STOCK:
        stock_before = item.current_stock
        item.current_stock += len(new_codes)
        item.save(update_fields=["current_stock", "updated_at"])
        _record_stock_event(
            item=item,
            event_type=StockEventType.RESTOCK,
            delta=len(new_codes),
            stock_before=stock_before,
            stock_after=item.current_stock,
            performed_by=performed_by,
            note=f"Bulk code import – batch {batch_id or 'N/A'}",
        )

    logger.info("Imported %d codes for item '%s'", len(new_codes), item.name)
    return len(new_codes)


def generate_and_import_codes(item_id, count: int, **kwargs) -> int:
    """Generate `count` random codes and import them for item_id."""
    codes = []
    existing_codes: set = set(
        RedemptionCode.objects.filter(item_id=item_id).values_list("code", flat=True)
    )
    attempts = 0
    while len(codes) < count:
        attempts += 1
        if attempts > count * 10:
            raise RuntimeError("Could not generate enough unique codes. Try again.")
        candidate = _generate_code()
        if candidate not in existing_codes:
            codes.append(candidate)
            existing_codes.add(candidate)
    return bulk_import_codes(item_id, codes, **kwargs)


# ── Award / Fulfilment ────────────────────────────────────────────────────────

@transaction.atomic
def award_item_to_user(
    user,
    item_id,
    delivery_method: str = DeliveryMethod.EMAIL,
    postback_reference: str = "",
    expires_at=None,
    awarded_by=None,
) -> UserInventory:
    """
    Core fulfilment function: decrement stock, assign a code if applicable,
    create a UserInventory record, and trigger async delivery.
    """
    # Lock item row to prevent concurrent oversell
    try:
        item = RewardItem.objects.select_for_update().get(pk=item_id)
    except RewardItem.DoesNotExist:
        raise ItemNotFoundException()

    if item.status != ItemStatus.ACTIVE:
        raise ItemNotActiveException(detail=f"Item '{item.name}' is not active.")

    # Quantity limit check
    try:
        validate_user_item_quantity_limit(user, item)
    except Exception as exc:
        raise ItemQuantityLimitExceededException(detail=str(exc))

    # Assign redemption code first (before stock decrement) so we fail fast
    # if no codes are available for code-based items.
    redemption_code = None
    if item.uses_codes:
        redemption_code = RedemptionCode.objects.get_next_available(item)
        if redemption_code is None:
            raise NoCodesAvailableException(
                detail=f"No redemption codes available for '{item.name}'."
            )
        redemption_code.reserve(ttl_seconds=STOCK_RESERVATION_TTL_SECONDS)

    # Decrement stock (raises InsufficientStockException if needed)
    stock_before = item.current_stock
    item.decrement_stock(qty=1)

    _record_stock_event(
        item=item,
        event_type=StockEventType.SALE,
        delta=-1,
        stock_before=stock_before,
        stock_after=item.current_stock,
        performed_by=awarded_by,
        note=f"Awarded to user {user.pk} via {delivery_method}",
    )

    inventory = UserInventory.objects.create(
        user=user,
        item=item,
        redemption_code=redemption_code,
        status=InventoryStatus.PENDING,
        delivery_method=delivery_method,
        expires_at=expires_at,
        awarded_by_postback=postback_reference,
    )

    inventory_created.send(sender=UserInventory, instance=inventory)
    _check_and_fire_stock_alerts(item)

    logger.info(
        "Awarded item '%s' to user %s (inventory=%s)",
        item.name, user.pk, inventory.pk,
    )

    # Kick off async delivery
    from .tasks import deliver_inventory_item
    deliver_inventory_item.delay(str(inventory.pk))

    return inventory


# ── Delivery ──────────────────────────────────────────────────────────────────

def deliver_item(inventory_id) -> UserInventory:
    """
    Attempt to deliver an inventory item.
    Called by the Celery task – handles retries and signal dispatch.
    """
    try:
        inventory = UserInventory.objects.select_related(
            "user", "item", "redemption_code"
        ).get(pk=inventory_id)
    except UserInventory.DoesNotExist:
        logger.error("deliver_item: UserInventory %s not found.", inventory_id)
        raise UserInventoryNotFoundException()

    if inventory.status == InventoryStatus.DELIVERED:
        logger.info("Inventory %s already delivered – skipping.", inventory_id)
        return inventory

    delivery_method = inventory.item.delivery_method
    handler = _get_delivery_handler(delivery_method)

    try:
        handler(inventory)
        if inventory.redemption_code:
            inventory.redemption_code.mark_redeemed(inventory.user)
            code_redeemed.send(
                sender=RedemptionCode,
                code_instance=inventory.redemption_code,
                user=inventory.user,
            )
        inventory.mark_delivered()
        item_delivered.send(sender=UserInventory, instance=inventory)
        logger.info("Delivered inventory %s to user %s", inventory_id, inventory.user.pk)
    except Exception as exc:
        error_msg = str(exc)
        attempt = inventory.delivery_attempts + 1
        if attempt >= MAX_DELIVERY_RETRY_ATTEMPTS:
            inventory.mark_failed(error=error_msg, next_retry_at=None)
            item_delivery_failed.send(
                sender=UserInventory, instance=inventory, error=error_msg
            )
            logger.error(
                "Delivery permanently failed for inventory %s after %d attempts: %s",
                inventory_id, attempt, error_msg,
            )
        else:
            backoff = DELIVERY_RETRY_DELAY_SECONDS[min(attempt - 1, len(DELIVERY_RETRY_DELAY_SECONDS) - 1)]
            inventory.increment_delivery_attempt(error=error_msg, backoff_seconds=backoff)
            logger.warning(
                "Delivery attempt %d failed for inventory %s: %s. Next retry in %ds.",
                attempt, inventory_id, error_msg, backoff,
            )
        raise DeliveryFailedException(detail=error_msg) from exc

    return inventory


def _get_delivery_handler(delivery_method: str):
    """Return the appropriate delivery handler function."""
    handlers = {
        DeliveryMethod.EMAIL: _deliver_via_email,
        DeliveryMethod.SMS: _deliver_via_sms,
        DeliveryMethod.IN_APP: _deliver_via_in_app,
        DeliveryMethod.API: _deliver_via_api_callback,
        DeliveryMethod.MANUAL: _deliver_manual,
        DeliveryMethod.PHYSICAL_SHIPMENT: _deliver_physical,
    }
    handler = handlers.get(delivery_method)
    if handler is None:
        raise NotImplementedError(f"No delivery handler for method '{delivery_method}'.")
    return handler


def _deliver_via_email(inventory: UserInventory) -> None:
    """Send reward code / details via email."""
    from django.core.mail import send_mail
    code = inventory.redemption_code.code if inventory.redemption_code else None
    body = inventory.item.delivery_template or (
        f"Hi {inventory.user.get_full_name() or inventory.user.username},\n\n"
        f"Your reward '{inventory.item.name}' is ready."
        + (f"\n\nYour code: {code}" if code else "")
    )
    send_mail(
        subject=f"Your reward: {inventory.item.name}",
        message=body,
        from_email=None,
        recipient_list=[inventory.user.email],
        fail_silently=False,
    )


def _deliver_via_sms(inventory: UserInventory) -> None:
    """Stub: integrate with SMS gateway (Twilio, etc.)."""
    logger.info("SMS delivery for inventory %s (stub)", inventory.pk)


def _deliver_via_in_app(inventory: UserInventory) -> None:
    """Mark as delivered – frontend polls inventory endpoint."""
    pass  # Delivery is instant; just marking records is enough.


def _deliver_via_api_callback(inventory: UserInventory) -> None:
    """POST to the item's callback URL with fulfilment details."""
    import json
    import urllib.request
    url = inventory.item.delivery_callback_url
    if not url:
        raise DeliveryFailedException(detail="API delivery method configured but no callback URL set.")
    payload = json.dumps({
        "inventory_id": str(inventory.pk),
        "user_id": str(inventory.user.pk),
        "item_id": str(inventory.item.pk),
        "code": inventory.redemption_code.code if inventory.redemption_code else None,
    }).encode()
    req = urllib.request.Request(url, data=payload, method="POST",
                                  headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
        if resp.status not in (200, 201, 202):
            raise DeliveryFailedException(detail=f"Callback returned HTTP {resp.status}.")


def _deliver_manual(inventory: UserInventory) -> None:
    """Manual fulfilment – just record, human handles delivery."""
    logger.info("Manual delivery queued for inventory %s", inventory.pk)


def _deliver_physical(inventory: UserInventory) -> None:
    """Stub: integrate with shipping API."""
    logger.info("Physical shipment queued for inventory %s (stub)", inventory.pk)


# ── Revocation ────────────────────────────────────────────────────────────────

@transaction.atomic
def revoke_inventory(inventory_id, reason: str, revoked_by=None) -> UserInventory:
    """
    Revoke a user's inventory entry and return the stock unit.
    """
    try:
        inventory = UserInventory.objects.select_related("item").get(pk=inventory_id)
    except UserInventory.DoesNotExist:
        raise UserInventoryNotFoundException()

    inventory.revoke(reason=reason, revoked_by=revoked_by)

    # Return stock
    item = RewardItem.objects.select_for_update().get(pk=inventory.item.pk)
    if not item.is_unlimited:
        stock_before = item.current_stock
        item.increment_stock(1)
        _record_stock_event(
            item=item,
            event_type=StockEventType.RETURN,
            delta=1,
            stock_before=stock_before,
            stock_after=item.current_stock,
            performed_by=revoked_by,
            note=f"Revocation of inventory {inventory_id}: {reason}",
        )

    # Release code if applicable
    if inventory.redemption_code and inventory.redemption_code.status == "redeemed":
        inventory.redemption_code.void(reason=f"Inventory revoked: {reason}")

    item_revoked.send(sender=UserInventory, instance=inventory, reason=reason)
    logger.info("Inventory %s revoked: %s", inventory_id, reason)
    return inventory
