"""
Payout Queue Services — Core business logic layer.

All public functions are the ONLY authorised entry-points for mutating
payout state. Views, tasks, and signals must go through this layer.

Design:
- Every public function is @transaction.atomic.
- All inputs validated before any DB write.
- Domain-specific exceptions only.
- BulkProcessLog written as append-only audit trail.
- Advisory lock pattern on PayoutBatch for concurrent task safety.
"""

from __future__ import annotations

import logging
import time
import uuid
from decimal import Decimal
from typing import Any, Optional, Sequence

from django.contrib.auth import get_user_model
from django.db import transaction, IntegrityError
from django.db.models import Q
from django.utils import timezone

from .choices import (
    PayoutBatchStatus,
    PayoutItemStatus,
    PaymentGateway,
    PriorityLevel,
    BulkProcessLogStatus,
    WithdrawalPriorityReason,
)
from .constants import (
    MAX_BATCH_SIZE,
    MAX_CONCURRENT_BATCHES,
    MAX_RETRY_ATTEMPTS,
    MIN_PAYOUT_AMOUNT,
    MAX_PAYOUT_AMOUNT,
)
from .exceptions import (
    PayoutQueueError,
    PayoutBatchNotFoundError,
    PayoutBatchStateError,
    PayoutBatchLockedError,
    PayoutBatchLimitError,
    PayoutItemNotFoundError,
    PayoutItemStateError,
    InvalidPayoutAmountError,
    DuplicatePayoutError,
    InvalidAccountNumberError,
    UserNotFoundError,
    RetryExhaustedError,
    GatewayError,
    GatewayTimeoutError,
)
from .models import PayoutBatch, PayoutItem, WithdrawalPriority, BulkProcessLog
from .utils.fee_calculator import FeeCalculator

logger = logging.getLogger(__name__)
User = get_user_model()
_fee_calculator = FeeCalculator()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_user_or_raise(user_id: Any) -> Any:
    if user_id is None:
        raise UserNotFoundError("user_id must not be None.")
    try:
        return User.objects.get(pk=user_id)
    except User.DoesNotExist:
        raise UserNotFoundError(f"User pk={user_id!r} does not exist.")
    except (ValueError, TypeError) as exc:
        raise PayoutQueueError(f"Invalid user_id={user_id!r}: {exc}") from exc


def _get_batch_or_raise(batch_id: Any) -> PayoutBatch:
    if batch_id is None:
        raise PayoutBatchNotFoundError("batch_id must not be None.")
    try:
        return PayoutBatch.objects.get(pk=batch_id)
    except PayoutBatch.DoesNotExist:
        raise PayoutBatchNotFoundError(
            f"PayoutBatch pk={batch_id!r} does not exist."
        )
    except (ValueError, TypeError) as exc:
        raise PayoutQueueError(f"Invalid batch_id={batch_id!r}: {exc}") from exc


def _get_item_or_raise(item_id: Any) -> PayoutItem:
    if item_id is None:
        raise PayoutItemNotFoundError("item_id must not be None.")
    try:
        return PayoutItem.objects.get(pk=item_id)
    except PayoutItem.DoesNotExist:
        raise PayoutItemNotFoundError(
            f"PayoutItem pk={item_id!r} does not exist."
        )
    except (ValueError, TypeError) as exc:
        raise PayoutQueueError(f"Invalid item_id={item_id!r}: {exc}") from exc


def _get_processor(gateway: str):
    """
    Lazy-load the gateway processor registry to avoid circular imports.
    Returns a configured processor for the given gateway.
    """
    from .processors.bkash import BkashProcessor
    from .processors.nagad import NagadProcessor
    from .processors.rocket import RocketProcessor
    from .utils.payment_gateway import PaymentGatewayRegistry
    from django.conf import settings

    registry = PaymentGatewayRegistry()
    gw_configs = getattr(settings, "PAYMENT_GATEWAY_CONFIGS", {})

    processor_map = {
        PaymentGateway.BKASH: BkashProcessor,
        PaymentGateway.NAGAD: NagadProcessor,
        PaymentGateway.ROCKET: RocketProcessor,
    }
    cls = processor_map.get(gateway)
    if cls is None:
        raise GatewayError(
            f"No processor available for gateway '{gateway}'."
        )
    config = gw_configs.get(gateway, {})
    processor = cls(config)
    registry.register(gateway, processor)
    return registry.get(gateway)


# ---------------------------------------------------------------------------
# PayoutBatch Services
# ---------------------------------------------------------------------------

@transaction.atomic
def create_payout_batch(
    *,
    name: str,
    gateway: str,
    priority: str = PriorityLevel.NORMAL,
    scheduled_at=None,
    created_by_id: Optional[Any] = None,
    note: str = "",
    metadata: Optional[dict] = None,
) -> PayoutBatch:
    """
    Create a new PayoutBatch in PENDING status.

    Args:
        name:           Descriptive batch name.
        gateway:        PaymentGateway choice.
        priority:       PriorityLevel choice.
        scheduled_at:   Optional future datetime for delayed execution.
        created_by_id:  PK of the admin creating the batch.
        note:           Optional audit note.
        metadata:       Arbitrary extra data.

    Returns:
        The new PayoutBatch instance.

    Raises:
        UserNotFoundError:     If created_by_id does not exist.
        PayoutBatchStateError: On validation failure.
    """
    if not name or not isinstance(name, str) or not name.strip():
        raise PayoutQueueError("name must be a non-empty string.")
    if gateway not in PaymentGateway.values:
        raise PayoutQueueError(
            f"Invalid gateway '{gateway}'. Valid: {PaymentGateway.values}"
        )
    if priority not in PriorityLevel.values:
        raise PayoutQueueError(
            f"Invalid priority '{priority}'. Valid: {PriorityLevel.values}"
        )
    if scheduled_at is not None and scheduled_at <= timezone.now():
        raise PayoutQueueError("scheduled_at must be in the future.")

    creator = None
    if created_by_id is not None:
        creator = _get_user_or_raise(created_by_id)
        if not creator.is_staff:
            raise PayoutQueueError(
                f"User pk={created_by_id!r} is not staff and cannot create payout batches."
            )

    batch = PayoutBatch(
        name=name.strip(),
        gateway=gateway,
        priority=priority,
        scheduled_at=scheduled_at,
        created_by=creator,
        note=(note or "").strip(),
        metadata=metadata if isinstance(metadata, dict) else {},
    )
    batch.full_clean()
    batch.save()

    logger.info(
        "create_payout_batch: id=%s name=%r gateway=%s priority=%s.",
        batch.id, batch.name, gateway, priority,
    )
    return batch


@transaction.atomic
def add_payout_items(
    *,
    batch_id: Any,
    items: Sequence[dict],
    validate_accounts: bool = True,
) -> list[PayoutItem]:
    """
    Add payout items to a PENDING batch.

    Each item dict must contain:
        user_id, account_number, gross_amount

    Fee is calculated automatically via FeeCalculator.

    Args:
        batch_id:         PK of the target PayoutBatch.
        items:            List of item dicts.
        validate_accounts: If True, validates account numbers via the gateway processor.

    Returns:
        List of created PayoutItem instances.

    Raises:
        PayoutBatchNotFoundError:  If batch does not exist.
        PayoutBatchStateError:     If batch is not PENDING.
        InvalidPayoutAmountError:  If any amount is out of range.
        InvalidAccountNumberError: If any account number fails validation.
        PayoutQueueError:          On other validation failures.
    """
    if not isinstance(items, (list, tuple)) or not items:
        raise PayoutQueueError("items must be a non-empty list.")

    batch = PayoutBatch.objects.select_for_update().get(pk=batch_id) \
        if batch_id else None
    if batch is None:
        raise PayoutBatchNotFoundError(f"PayoutBatch pk={batch_id!r} does not exist.")

    if batch.status != PayoutBatchStatus.PENDING:
        raise PayoutBatchStateError(
            f"Cannot add items to batch in status '{batch.status}'. Must be PENDING."
        )

    current_count = batch.items.count()
    if current_count + len(items) > MAX_BATCH_SIZE:
        raise PayoutQueueError(
            f"Adding {len(items)} items would exceed max batch size of {MAX_BATCH_SIZE}. "
            f"Current: {current_count}."
        )

    # Lazy-load processor for account validation
    processor = None
    if validate_accounts:
        try:
            processor = _get_processor(batch.gateway)
        except Exception as exc:
            logger.warning(
                "add_payout_items: could not load processor for validation: %s", exc
            )

    created_items = []
    errors = []

    for idx, item in enumerate(items):
        try:
            created = _create_single_payout_item(
                batch=batch,
                item_dict=item,
                processor=processor,
                validate_accounts=validate_accounts,
            )
            created_items.append(created)
        except Exception as exc:
            errors.append(f"Item {idx}: {exc}")

    if errors:
        # Rollback entire batch item addition on any validation error
        raise PayoutQueueError(
            f"Failed to add {len(errors)} item(s):\n" + "\n".join(errors)
        )

    # Refresh batch totals
    batch.refresh_financial_totals()

    logger.info(
        "add_payout_items: added %d items to batch %s. Totals refreshed.",
        len(created_items), batch_id,
    )
    return created_items


def _create_single_payout_item(
    *, batch: PayoutBatch, item_dict: dict, processor, validate_accounts: bool
) -> PayoutItem:
    """Create one PayoutItem. Raises on any validation failure."""
    user_id = item_dict.get("user_id")
    account_number = item_dict.get("account_number", "")
    gross_amount = item_dict.get("gross_amount")

    if user_id is None:
        raise PayoutQueueError("user_id is required.")
    if not account_number or not isinstance(account_number, str):
        raise InvalidAccountNumberError("account_number must be a non-empty string.")

    # Coerce gross_amount to Decimal
    try:
        gross_amount = Decimal(str(gross_amount))
    except (InvalidOperation := __import__("decimal").InvalidOperation, TypeError, ValueError) as exc:
        raise InvalidPayoutAmountError(
            f"gross_amount '{gross_amount}' is not a valid decimal: {exc}"
        )

    if gross_amount < MIN_PAYOUT_AMOUNT or gross_amount > MAX_PAYOUT_AMOUNT:
        raise InvalidPayoutAmountError(
            f"gross_amount {gross_amount} is out of range "
            f"[{MIN_PAYOUT_AMOUNT}, {MAX_PAYOUT_AMOUNT}]."
        )

    # Validate account number via processor
    if validate_accounts and processor is not None:
        if not processor.validate_account(account_number):
            raise InvalidAccountNumberError(
                f"account_number '{account_number}' failed gateway validation "
                f"for {batch.gateway}."
            )

    # Calculate fee
    fee_result = _fee_calculator.calculate(
        gateway=batch.gateway, gross_amount=gross_amount
    )
    fee_amount = fee_result["fee"]
    net_amount = fee_result["net"]

    # Generate unique internal reference
    internal_reference = str(uuid.uuid4())

    # Check duplicate (same user + gross_amount + batch)
    if PayoutItem.objects.filter(
        batch=batch, user_id=user_id, gross_amount=gross_amount,
        account_number=account_number.strip(),
    ).exists():
        raise DuplicatePayoutError(
            f"Duplicate payout for user={user_id} amount={gross_amount} "
            f"account={account_number} in batch {batch.id}."
        )

    item = PayoutItem(
        batch=batch,
        user_id=user_id,
        gateway=batch.gateway,
        account_number=account_number.strip(),
        gross_amount=gross_amount,
        fee_amount=fee_amount,
        net_amount=net_amount,
        internal_reference=internal_reference,
        metadata=item_dict.get("metadata", {}) if isinstance(item_dict.get("metadata"), dict) else {},
        note=str(item_dict.get("note", ""))[:2000],
    )
    item.full_clean()
    item.save()
    return item


# ---------------------------------------------------------------------------
# Batch Processing
# ---------------------------------------------------------------------------

@transaction.atomic
def process_batch(
    *,
    batch_id: Any,
    worker_id: str,
    actor_id: Optional[Any] = None,
) -> dict:
    """
    Process all QUEUED items in a PayoutBatch.

    This function:
    1. Acquires advisory lock on the batch.
    2. Transitions batch to PROCESSING.
    3. Iterates QUEUED items, calls gateway processor per item.
    4. Creates BulkProcessLog for audit.
    5. Transitions batch to COMPLETED/PARTIALLY_COMPLETED/FAILED.

    Args:
        batch_id:  PK of the PayoutBatch.
        worker_id: Unique task/worker identifier (for advisory lock).
        actor_id:  PK of the triggering user (for logging).

    Returns:
        Dict with success_count, failure_count, duration_ms.

    Raises:
        PayoutBatchNotFoundError: If batch does not exist.
        PayoutBatchLockedError:   If another worker already holds the lock.
        PayoutBatchStateError:    If batch is not in a processable state.
    """
    if not worker_id or not isinstance(worker_id, str):
        raise PayoutQueueError("worker_id must be a non-empty string.")

    batch = PayoutBatch.objects.select_for_update().get(pk=batch_id) \
        if batch_id else None
    if batch is None:
        raise PayoutBatchNotFoundError(f"PayoutBatch pk={batch_id!r} does not exist.")

    # Check concurrent batch limit
    processing_count = PayoutBatch.objects.processing().count()
    if processing_count >= MAX_CONCURRENT_BATCHES:
        raise PayoutBatchLimitError(
            f"Cannot process batch: {processing_count} batches already PROCESSING "
            f"(limit: {MAX_CONCURRENT_BATCHES})."
        )

    # Acquire advisory lock
    if not batch.acquire_lock(worker_id):
        raise PayoutBatchLockedError(
            f"PayoutBatch {batch_id} is already locked by '{batch.locked_by}'."
        )

    # Transition to PROCESSING
    try:
        batch.transition_to(PayoutBatchStatus.PROCESSING, actor=actor_id)
    except PayoutBatchStateError:
        batch.release_lock()
        raise

    start_time = time.monotonic()
    success_count = 0
    failure_count = 0
    skipped_count = 0
    total_amount_processed = Decimal("0.00")
    error_details = []

    try:
        processor = _get_processor(batch.gateway)
    except GatewayError as exc:
        logger.error("process_batch: cannot load processor for gateway %s: %s", batch.gateway, exc)
        batch.mark_failed_with_release(str(exc))
        raise

    queued_items = list(
        PayoutItem.objects.for_batch(batch_id).queued().select_for_update(skip_locked=True)
    )

    logger.info(
        "process_batch: batch=%s gateway=%s items=%d worker=%s",
        batch_id, batch.gateway, len(queued_items), worker_id,
    )

    for item in queued_items:
        # Mark as PROCESSING
        PayoutItem.objects.filter(pk=item.pk).update(
            status=PayoutItemStatus.PROCESSING,
            updated_at=timezone.now(),
        )

        try:
            result = processor.send_payout(
                account_number=item.account_number,
                amount=item.net_amount,
                reference=item.internal_reference,
            )
        except GatewayTimeoutError as exc:
            item.mark_failed(error_code="TIMEOUT", error_message=str(exc))
            failure_count += 1
            error_details.append(f"item={item.id}: TIMEOUT: {exc}")
            continue
        except GatewayError as exc:
            item.mark_failed(error_code="GATEWAY_ERROR", error_message=str(exc))
            failure_count += 1
            error_details.append(f"item={item.id}: GATEWAY_ERROR: {exc}")
            continue
        except Exception as exc:
            logger.exception(
                "process_batch: unexpected error processing item %s: %s", item.id, exc
            )
            item.mark_failed(error_code="INTERNAL_ERROR", error_message=str(exc))
            failure_count += 1
            error_details.append(f"item={item.id}: INTERNAL_ERROR: {exc}")
            continue

        if result.success:
            item.mark_success(
                gateway_reference=result.gateway_reference,
                gateway_response=result.raw_response,
            )
            success_count += 1
            total_amount_processed += item.net_amount
        else:
            item.mark_failed(
                error_code=result.error_code,
                error_message=result.error_message,
                gateway_response=result.raw_response,
            )
            failure_count += 1
            error_details.append(
                f"item={item.id}: {result.error_code}: {result.error_message}"
            )

    duration_ms = int((time.monotonic() - start_time) * 1000)

    # Refresh batch totals
    batch.refresh_financial_totals()

    # Determine final batch status
    if failure_count == 0:
        final_status = PayoutBatchStatus.COMPLETED
    elif success_count == 0:
        final_status = PayoutBatchStatus.FAILED
    else:
        final_status = PayoutBatchStatus.PARTIALLY_COMPLETED

    batch.transition_to(final_status, actor=actor_id)

    # Write audit log
    _write_process_log(
        batch=batch,
        status=(
            BulkProcessLogStatus.SUCCESS if final_status == PayoutBatchStatus.COMPLETED
            else BulkProcessLogStatus.PARTIAL if final_status == PayoutBatchStatus.PARTIALLY_COMPLETED
            else BulkProcessLogStatus.FAILED
        ),
        actor_id=actor_id,
        worker_id=worker_id,
        items_attempted=len(queued_items),
        items_succeeded=success_count,
        items_failed=failure_count,
        items_skipped=skipped_count,
        duration_ms=duration_ms,
        total_amount_processed=total_amount_processed,
        error_summary="\n".join(error_details[:50]),
    )

    logger.info(
        "process_batch: batch=%s DONE status=%s success=%d failed=%d duration=%dms",
        batch_id, final_status, success_count, failure_count, duration_ms,
    )
    return {
        "batch_id": str(batch_id),
        "status": final_status,
        "success_count": success_count,
        "failure_count": failure_count,
        "skipped_count": skipped_count,
        "total_amount_processed": str(total_amount_processed),
        "duration_ms": duration_ms,
    }


def _write_process_log(
    *,
    batch: PayoutBatch,
    status: str,
    actor_id: Any,
    worker_id: str,
    items_attempted: int,
    items_succeeded: int,
    items_failed: int,
    items_skipped: int,
    duration_ms: int,
    total_amount_processed: Decimal,
    error_summary: str,
) -> None:
    """Create a BulkProcessLog record. Never raises — logs errors silently."""
    try:
        BulkProcessLog.objects.create(
            batch=batch,
            status=status,
            triggered_by_id=actor_id,
            task_id=worker_id,
            items_attempted=items_attempted,
            items_succeeded=items_succeeded,
            items_failed=items_failed,
            items_skipped=items_skipped,
            duration_ms=duration_ms,
            total_amount_processed=total_amount_processed,
            error_summary=error_summary[:4096],
            extra_data={"worker_id": worker_id},
        )
    except Exception as exc:
        logger.error("_write_process_log: failed to write audit log: %s", exc)


# ---------------------------------------------------------------------------
# Retry Services
# ---------------------------------------------------------------------------

@transaction.atomic
def retry_failed_items(
    *,
    batch_id: Optional[Any] = None,
    item_ids: Optional[list] = None,
    worker_id: str,
) -> dict:
    """
    Retry RETRYING items that are due for re-processing.

    Args:
        batch_id:  If set, only retry items in this batch.
        item_ids:  If set, only retry these specific item PKs.
        worker_id: Worker identifier for lock/logging.

    Returns:
        Dict with retried_count, success_count, failure_count.

    Raises:
        PayoutQueueError: On invalid arguments.
    """
    if not worker_id:
        raise PayoutQueueError("worker_id is required.")

    qs = PayoutItem.objects.due_for_retry()
    if batch_id is not None:
        qs = qs.for_batch(batch_id)
    if item_ids is not None:
        if not isinstance(item_ids, list):
            raise PayoutQueueError("item_ids must be a list.")
        qs = qs.filter(pk__in=item_ids)

    items = list(qs.select_for_update(skip_locked=True)[:100])  # Process max 100 at a time

    if not items:
        logger.info("retry_failed_items: no items due for retry.")
        return {"retried_count": 0, "success_count": 0, "failure_count": 0}

    # Group by gateway for processor reuse
    from itertools import groupby
    items_by_gateway = {}
    for item in items:
        items_by_gateway.setdefault(item.gateway, []).append(item)

    success_count = 0
    failure_count = 0

    for gateway, gateway_items in items_by_gateway.items():
        try:
            processor = _get_processor(gateway)
        except GatewayError as exc:
            logger.error("retry_failed_items: no processor for %s: %s", gateway, exc)
            failure_count += len(gateway_items)
            continue

        for item in gateway_items:
            PayoutItem.objects.filter(pk=item.pk).update(
                status=PayoutItemStatus.PROCESSING,
                updated_at=timezone.now(),
            )
            try:
                result = processor.send_payout(
                    account_number=item.account_number,
                    amount=item.net_amount,
                    reference=item.internal_reference,
                )
            except Exception as exc:
                item.mark_failed(error_code="RETRY_ERROR", error_message=str(exc))
                failure_count += 1
                continue

            if result.success:
                item.mark_success(
                    gateway_reference=result.gateway_reference,
                    gateway_response=result.raw_response,
                )
                success_count += 1
            else:
                item.mark_failed(
                    error_code=result.error_code,
                    error_message=result.error_message,
                    gateway_response=result.raw_response,
                )
                failure_count += 1

    logger.info(
        "retry_failed_items: retried=%d success=%d failed=%d",
        len(items), success_count, failure_count,
    )
    return {
        "retried_count": len(items),
        "success_count": success_count,
        "failure_count": failure_count,
    }


# ---------------------------------------------------------------------------
# WithdrawalPriority Services
# ---------------------------------------------------------------------------

@transaction.atomic
def set_withdrawal_priority(
    *,
    user_id: Any,
    priority: str,
    reason: str,
    payout_item_id: Optional[Any] = None,
    assigned_by_id: Optional[Any] = None,
    reason_note: str = "",
    expires_at=None,
) -> WithdrawalPriority:
    """
    Assign or escalate a withdrawal priority for a user.

    Deactivates any existing active priority before creating the new one.

    Args:
        user_id:         PK of the user.
        priority:        PriorityLevel choice.
        reason:          WithdrawalPriorityReason choice.
        payout_item_id:  Optional payout item this priority applies to.
        assigned_by_id:  PK of the admin assigning the priority.
        reason_note:     Optional human-readable note.
        expires_at:      Optional expiry datetime.

    Returns:
        The new WithdrawalPriority record.
    """
    if priority not in PriorityLevel.values:
        raise PayoutQueueError(f"Invalid priority '{priority}'.")
    if reason not in WithdrawalPriorityReason.values:
        raise PayoutQueueError(f"Invalid reason '{reason}'.")

    user = _get_user_or_raise(user_id)

    # Resolve current priority for audit
    current = WithdrawalPriority.objects.get_active_for_user(user_id)
    previous_priority = current.priority if current else ""

    # Deactivate all current active priorities for this user/item
    filter_kwargs = {"user_id": user_id, "is_active": True}
    if payout_item_id is not None:
        filter_kwargs["payout_item_id"] = payout_item_id
    WithdrawalPriority.objects.filter(**filter_kwargs).update(
        is_active=False, updated_at=timezone.now()
    )

    wp = WithdrawalPriority(
        user=user,
        priority=priority,
        previous_priority=previous_priority,
        reason=reason,
        reason_note=(reason_note or "").strip(),
        expires_at=expires_at,
        assigned_by_id=assigned_by_id,
        is_active=True,
    )
    if payout_item_id is not None:
        wp.payout_item_id = payout_item_id

    wp.full_clean()
    # Bypass append-only guard on new instance
    wp.pk = None
    super(WithdrawalPriority, wp).save()

    logger.info(
        "set_withdrawal_priority: user=%s priority=%s reason=%s (prev=%s).",
        user_id, priority, reason, previous_priority,
    )
    return wp


@transaction.atomic
def cancel_payout_item(*, item_id: Any, reason: str, actor_id: Optional[Any] = None) -> PayoutItem:
    """
    Cancel a payout item. Only QUEUED or RETRYING items can be cancelled.

    Args:
        item_id:  PK of the PayoutItem.
        reason:   Cancellation reason.
        actor_id: PK of the actor performing the cancellation.

    Returns:
        The updated PayoutItem.

    Raises:
        PayoutItemNotFoundError: If item does not exist.
        PayoutItemStateError:    If item cannot be cancelled.
    """
    try:
        item = PayoutItem.objects.select_for_update().get(pk=item_id)
    except PayoutItem.DoesNotExist:
        raise PayoutItemNotFoundError(f"PayoutItem pk={item_id!r} does not exist.")

    item.cancel(reason=reason or "")
    logger.info(
        "cancel_payout_item: item=%s cancelled by actor=%s reason=%r",
        item_id, actor_id, reason,
    )
    return item


def get_batch_statistics(batch_id: Any) -> dict:
    """
    Return statistics for a batch without mutating state.

    Returns:
        Dict with counts, amounts, success_rate, process_logs summary.
    """
    batch = _get_batch_or_raise(batch_id)
    batch.refresh_from_db()

    return {
        "batch_id": str(batch.id),
        "name": batch.name,
        "gateway": batch.gateway,
        "status": batch.status,
        "priority": batch.priority,
        "item_count": batch.item_count,
        "success_count": batch.success_count,
        "failure_count": batch.failure_count,
        "success_rate": batch.success_rate,
        "total_amount": str(batch.total_amount),
        "total_fee": str(batch.total_fee),
        "net_amount": str(batch.net_amount),
        "started_at": batch.started_at.isoformat() if batch.started_at else None,
        "completed_at": batch.completed_at.isoformat() if batch.completed_at else None,
        "process_log_count": batch.process_logs.count(),
    }
