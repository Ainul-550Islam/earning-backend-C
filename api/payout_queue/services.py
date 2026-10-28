"""
payout_queue/services.py  ← v8 PRODUCTION UPDATE (built on DRY v7 + v6)

CHANGES v8 (Production Gap #2 — account_number encryption):

  ① Duplicate detection now uses account_number_hash

     Before:  PayoutItem.objects.filter(..., account_number=account_number.strip())
              This worked when account_number was stored as plaintext.
              After field-level encryption (models.py v8), the DB column stores
              ciphertext — each encryption of the same plaintext produces a
              DIFFERENT ciphertext (random IV), so this filter would NEVER match,
              silently allowing unlimited duplicate payouts to the same account.

     After:   PayoutItem.objects.filter(..., account_number_hash=compute_account_hash(...))
              The hash is deterministic (same input + same key = same hash),
              so exact-match duplicate detection still works correctly.

All DRY v7 + v6 changes preserved unchanged.
"""

from __future__ import annotations

import logging
import time
import uuid
from decimal import Decimal
from typing import Any, Optional, Sequence

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q, Sum
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
    MAX_SINGLE_GATEWAY_PAYOUT,
    PAYOUT_STATS_CACHE_TTL,
    MAX_BATCH_SIZE,
    MAX_CONCURRENT_BATCHES,
    MAX_RETRY_ATTEMPTS,
    MIN_PAYOUT_AMOUNT,
    MAX_PAYOUT_AMOUNT,
)
from .exceptions import (
    BulkProcessLogNotFoundError,
    InsufficientFundsError,
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
    GatewayError,
    GatewayTimeoutError,
)
from .models import PayoutBatch, PayoutItem, WithdrawalPriority, BulkProcessLog
from .utils.fee_calculator import FeeCalculator, FeeCalculationError
# v8: import hash helper for account_number duplicate detection
from .utils.encryption import compute_account_hash

logger = logging.getLogger(__name__)
User = get_user_model()
_fee_calculator = FeeCalculator()

# ---------------------------------------------------------------------------
# Generic _get_or_raise helper
# ---------------------------------------------------------------------------

def _get_or_raise(model_class, error_class, **kwargs):
    try:
        return model_class.objects.get(**kwargs)
    except model_class.DoesNotExist:
        field, value = next(iter(kwargs.items()))
        raise error_class(f"{model_class.__name__} {field}={value!r} does not exist.")
    except (ValueError, TypeError) as exc:
        field, value = next(iter(kwargs.items()))
        raise PayoutQueueError(f"Invalid {field}={value!r} for {model_class.__name__}: {exc}") from exc

# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------

def _get_user_or_raise(user_id: Any) -> Any:
    if user_id is None:
        raise UserNotFoundError("user_id must not be None.")
    return _get_or_raise(User, UserNotFoundError, pk=user_id)

def _get_batch_or_raise(batch_id: Any) -> PayoutBatch:
    if batch_id is None:
        raise PayoutBatchNotFoundError("batch_id must not be None.")
    return _get_or_raise(PayoutBatch, PayoutBatchNotFoundError, pk=batch_id)

def _get_item_or_raise(item_id: Any) -> PayoutItem:
    if item_id is None:
        raise PayoutItemNotFoundError("item_id must not be None.")
    return _get_or_raise(PayoutItem, PayoutItemNotFoundError, pk=item_id)

# ---------------------------------------------------------------------------
# DRY v7: locked-fetch helpers
# ---------------------------------------------------------------------------

def _get_batch_locked(batch_id: Any) -> PayoutBatch:
    """DRY v7: SELECT FOR UPDATE fetch or raise. Replaced 5 inline patterns."""
    if batch_id is None:
        raise PayoutBatchNotFoundError("batch_id must not be None.")
    try:
        return PayoutBatch.objects.select_for_update().get(pk=batch_id)
    except PayoutBatch.DoesNotExist:
        raise PayoutBatchNotFoundError(f"PayoutBatch pk={batch_id!r} does not exist.")

def _get_item_locked(item_id: Any) -> PayoutItem:
    """DRY v7: SELECT FOR UPDATE fetch or raise. Replaced 2 inline patterns."""
    if item_id is None:
        raise PayoutItemNotFoundError("item_id must not be None.")
    try:
        return PayoutItem.objects.select_for_update().get(pk=item_id)
    except PayoutItem.DoesNotExist:
        raise PayoutItemNotFoundError(f"PayoutItem pk={item_id!r} does not exist.")

def _get_processor(gateway: str):
    """Lazy-load gateway processor registry to avoid circular imports."""
    from .processors.bkash import BkashProcessor
    from .processors.nagad import NagadProcessor
    from .processors.rocket import RocketProcessor
    from .processors.bank import BankProcessor
    from .processors.manual import ManualProcessor
    from .utils.payment_gateway import PaymentGatewayRegistry
    from django.conf import settings

    registry   = PaymentGatewayRegistry()
    gw_configs = getattr(settings, "PAYMENT_GATEWAY_CONFIGS", {})

    processor_map = {
        PaymentGateway.BKASH:  BkashProcessor,
        PaymentGateway.NAGAD:  NagadProcessor,
        PaymentGateway.ROCKET: RocketProcessor,
        PaymentGateway.BANK:   BankProcessor,
        PaymentGateway.MANUAL: ManualProcessor,
    }
    cls = processor_map.get(gateway)
    if cls is None:
        raise GatewayError(f"No processor available for gateway '{gateway}'.")
    config    = gw_configs.get(gateway, {})
    processor = cls(config)
    registry.register(gateway, processor)
    return registry.get(gateway)

# ---------------------------------------------------------------------------
# DRY v7: shared batch-transition core
# ---------------------------------------------------------------------------

@transaction.atomic
def _do_transition_batch(
    *,
    batch_id: Any,
    new_status: str,
    actor_id: Optional[Any],
    note: str,
    default_note: str,
    log_prefix: str,
) -> PayoutBatch:
    """
    DRY v7: Shared body for hold/resume. cancel calls this then adds refund logic.
    Replaced 3 identical 6-line bodies.
    """
    batch = _get_batch_locked(batch_id)
    batch.transition_to(new_status, actor=actor_id, note=note or default_note)
    logger.info("%s: batch=%s actor=%s.", log_prefix, batch_id, actor_id)
    return batch

# ---------------------------------------------------------------------------
# v6: Wallet refund helper
# ---------------------------------------------------------------------------

def _refund_batch_wallet(*, batch: PayoutBatch, final_status: str) -> None:
    """
    FIX v6: Refund the platform wallet for failed or partially-failed batches.
    FAILED → full refund. PARTIALLY_COMPLETED → refund only permanently-FAILED items.
    COMPLETED → no refund. Never raises.
    """
    from django.conf import settings as _settings
    if not getattr(_settings, "PAYOUT_WALLET_CHECK_ENABLED", True):
        return
    if not batch.tenant_id:
        return

    try:
        from api.wallet.payout_integration import refund_payout_wallet
    except ImportError:
        logger.warning("_refund_batch_wallet: api.wallet.payout_integration not available.")
        return

    try:
        if final_status == PayoutBatchStatus.FAILED:
            refund_amount = batch.total_amount
            reason        = f"Batch {batch.id} fully FAILED — all {batch.item_count} items failed. Full refund."
        elif final_status == PayoutBatchStatus.PARTIALLY_COMPLETED:
            failed_sum    = (PayoutItem.objects.filter(batch=batch, status=PayoutItemStatus.FAILED)
                             .aggregate(total=Sum("gross_amount"))["total"] or Decimal("0.00"))
            refund_amount = failed_sum
            reason        = f"Batch {batch.id} PARTIALLY_COMPLETED — {batch.failure_count} item(s) failed. Partial refund."
        else:
            return

        if refund_amount <= Decimal("0.00"):
            return

        refund_payout_wallet(tenant_id=batch.tenant_id, amount=refund_amount,
                             reference=str(batch.id), reason=reason)
        logger.info("_refund_batch_wallet: refunded %s BDT to tenant=%s for batch=%s status=%s.",
                    refund_amount, batch.tenant_id, batch.id, final_status)
    except Exception as exc:
        logger.error("_refund_batch_wallet: FAILED for batch=%s: %s. Manual reconciliation required.",
                     batch.id, exc)

# ---------------------------------------------------------------------------
# PayoutBatch Services — Core CRUD
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
    """Create a new PayoutBatch in PENDING status."""
    if not name or not isinstance(name, str) or not name.strip():
        raise PayoutQueueError("name must be a non-empty string.")
    if gateway not in PaymentGateway.values:
        raise PayoutQueueError(f"Invalid gateway '{gateway}'. Valid: {PaymentGateway.values}")
    if priority not in PriorityLevel.values:
        raise PayoutQueueError(f"Invalid priority '{priority}'. Valid: {PriorityLevel.values}")
    if scheduled_at is not None and scheduled_at <= timezone.now():
        raise PayoutQueueError("scheduled_at must be in the future.")

    creator = None
    if created_by_id is not None:
        creator = _get_user_or_raise(created_by_id)
        if not creator.is_staff:
            raise PayoutQueueError(f"User pk={created_by_id!r} is not staff and cannot create payout batches.")

    batch = PayoutBatch(
        name=name.strip(), gateway=gateway, priority=priority,
        scheduled_at=scheduled_at, created_by=creator,
        note=(note or "").strip(),
        metadata=metadata if isinstance(metadata, dict) else {},
    )
    batch.full_clean()
    batch.save()
    logger.info("create_payout_batch: id=%s name=%r gateway=%s priority=%s.", batch.id, batch.name, gateway, priority)
    return batch

@transaction.atomic
def add_payout_items(
    *,
    batch_id: Any,
    items: Sequence[dict],
    validate_accounts: bool = True,
) -> list[PayoutItem]:
    """Add payout items to a PENDING batch."""
    if not isinstance(items, (list, tuple)) or not items:
        raise PayoutQueueError("items must be a non-empty list.")

    # DRY v7: _get_batch_locked
    batch = _get_batch_locked(batch_id)

    if batch.status != PayoutBatchStatus.PENDING:
        raise PayoutBatchStateError(
            f"Cannot add items to batch in status '{batch.status}'. Must be PENDING."
        )

    current_count = batch.items.count()
    if current_count + len(items) > MAX_BATCH_SIZE:
        raise PayoutQueueError(
            f"Adding {len(items)} items would exceed max batch size of {MAX_BATCH_SIZE}. Current: {current_count}."
        )

    processor = None
    if validate_accounts:
        try:
            processor = _get_processor(batch.gateway)
        except Exception as exc:
            logger.warning("add_payout_items: could not load processor for validation: %s", exc)

    # GUARD ①: KYC check
    from django.conf import settings as _settings
    if getattr(_settings, "PAYOUT_KYC_CHECK_ENABLED", True):
        try:
            from api.kyc.payout_integration import is_user_kyc_verified
            unverified = [item_dict.get("user_id") for item_dict in items
                          if item_dict.get("user_id") and not is_user_kyc_verified(item_dict.get("user_id"))]
            if unverified:
                raise PayoutQueueError(
                    f"KYC not verified for {len(unverified)} user(s): {unverified[:10]}. Payout blocked (BFIU compliance)."
                )
        except ImportError:
            logger.warning("add_payout_items: api.kyc.payout_integration not found. Set PAYOUT_KYC_CHECK_ENABLED=False.")

    created_items = []
    errors        = []
    for idx, item in enumerate(items):
        try:
            created = _create_single_payout_item(
                batch=batch, item_dict=item,
                processor=processor, validate_accounts=validate_accounts,
            )
            created_items.append(created)
        except Exception as exc:
            errors.append(f"Item {idx}: {exc}")

    if errors:
        raise PayoutQueueError(f"Failed to add {len(errors)} item(s):\n" + "\n".join(errors))

    batch.refresh_financial_totals()
    logger.info("add_payout_items: added %d items to batch %s.", len(created_items), batch_id)
    return created_items

def _create_single_payout_item(
    *, batch: PayoutBatch, item_dict: dict, processor, validate_accounts: bool
) -> PayoutItem:
    """
    Create one PayoutItem.
    FIX v4: FeeCalculationError → InvalidPayoutAmountError (400 not 500).
    FIX v6: record_payout_attempt() called for velocity tracking.
    FIX v8: duplicate detection uses account_number_hash (not plaintext filter).
    """
    from decimal import InvalidOperation

    user_id        = item_dict.get("user_id")
    account_number = item_dict.get("account_number", "")
    gross_amount   = item_dict.get("gross_amount")

    if user_id is None:
        raise PayoutQueueError("user_id is required.")
    if not account_number or not isinstance(account_number, str):
        raise InvalidAccountNumberError("account_number must be a non-empty string.")

    try:
        gross_amount = Decimal(str(gross_amount))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise InvalidPayoutAmountError(f"gross_amount '{gross_amount}' is not a valid decimal: {exc}")

    if gross_amount < MIN_PAYOUT_AMOUNT or gross_amount > MAX_PAYOUT_AMOUNT:
        raise InvalidPayoutAmountError(
            f"gross_amount {gross_amount} is out of range [{MIN_PAYOUT_AMOUNT}, {MAX_PAYOUT_AMOUNT}]."
        )
    if gross_amount > MAX_SINGLE_GATEWAY_PAYOUT:
        raise InvalidPayoutAmountError(
            f"gross_amount {gross_amount} exceeds single-payout limit of {MAX_SINGLE_GATEWAY_PAYOUT} BDT."
        )

    if validate_accounts and processor is not None:
        if not processor.validate_account(account_number):
            raise InvalidAccountNumberError(
                f"account_number '{account_number}' failed gateway validation for {batch.gateway}."
            )

    # GUARD ②: Fraud score check
    from django.conf import settings as _settings
    if getattr(_settings, "PAYOUT_FRAUD_CHECK_ENABLED", True):
        try:
            from api.fraud_detection.payout_integration import get_payout_risk_score
            score     = get_payout_risk_score(user_id, gross_amount, account_number)
            threshold = getattr(_settings, "PAYOUT_FRAUD_RISK_THRESHOLD", 0.75)
            if score > threshold:
                logger.error("_create_single_payout_item: FRAUD BLOCKED user=%s score=%.3f threshold=%.3f",
                             user_id, score, threshold)
                raise PayoutQueueError(
                    f"Payout blocked: fraud risk score {score:.3f} exceeds threshold {threshold} for user={user_id}."
                )
        except ImportError:
            logger.warning("_create_single_payout_item: api.fraud_detection not found.")

    try:
        fee_result = _fee_calculator.calculate(gateway=batch.gateway, gross_amount=gross_amount)
    except FeeCalculationError as exc:
        raise InvalidPayoutAmountError(f"Fee calculation failed for gateway '{batch.gateway}': {exc}") from exc

    fee_amount         = fee_result["fee"]
    net_amount         = fee_result["net"]
    internal_reference = str(uuid.uuid4())

    # ── v8: Duplicate detection using account_number_hash ────────────────────
    # Before v8: filter(account_number=account_number.strip())
    # After v8:  filter(account_number_hash=compute_account_hash(...))
    #
    # Reason: account_number is now stored encrypted (EncryptedCharField).
    # Each encryption uses a random IV, so identical account numbers produce
    # different ciphertexts. The plaintext filter would NEVER match, silently
    # allowing unlimited duplicate payouts.
    # The hash is deterministic: same plaintext + same key = same hash.
    acct_hash = compute_account_hash(account_number.strip())
    if PayoutItem.objects.filter(
        batch=batch,
        user_id=user_id,
        gross_amount=gross_amount,
        account_number_hash=acct_hash,
    ).exists():
        raise DuplicatePayoutError(
            f"Duplicate payout: user={user_id} amount={gross_amount} "
            f"account=<hash:{acct_hash[:8]}...> in batch {batch.id}."
        )
    # ─────────────────────────────────────────────────────────────────────────

    item = PayoutItem(
        batch=batch,
        user_id=user_id,
        gateway=batch.gateway,
        account_number=account_number.strip(),   # EncryptedCharField encrypts on save
        gross_amount=gross_amount,
        fee_amount=fee_amount,
        net_amount=net_amount,
        internal_reference=internal_reference,
        metadata=(item_dict.get("metadata", {}) if isinstance(item_dict.get("metadata"), dict) else {}),
        note=str(item_dict.get("note", ""))[:2000],
    )
    item.full_clean()
    item.save()  # PayoutItem.save() auto-computes account_number_hash

    # FIX v6: Record payout attempt for velocity tracking
    if getattr(_settings, "PAYOUT_FRAUD_CHECK_ENABLED", True):
        try:
            from api.fraud_detection.payout_integration import record_payout_attempt
            record_payout_attempt(user_id=user_id, amount=gross_amount, account_number=account_number.strip())
        except ImportError:
            pass
        except Exception as exc:
            logger.warning("_create_single_payout_item: record_payout_attempt failed for user=%s: %s", user_id, exc)

    return item

# ---------------------------------------------------------------------------
# Batch Processing
# ---------------------------------------------------------------------------

def _setup_batch_for_processing(batch: PayoutBatch, worker_id: str, actor_id: Optional[Any]) -> Any:
    """Acquire lock, check limits, transition to PROCESSING, load processor."""
    processing_count = PayoutBatch.objects.processing().count()
    if processing_count >= MAX_CONCURRENT_BATCHES:
        raise PayoutBatchLimitError(
            f"Cannot process: {processing_count} batches already PROCESSING (limit: {MAX_CONCURRENT_BATCHES})."
        )
    if not batch.acquire_lock(worker_id):
        raise PayoutBatchLockedError(f"PayoutBatch {batch.id} is already locked by '{batch.locked_by}'.")

    try:
        batch.transition_to(PayoutBatchStatus.PROCESSING, actor=actor_id)
    except PayoutBatchStateError:
        batch.release_lock()
        raise

    from django.conf import settings as _settings
    if getattr(_settings, "PAYOUT_WALLET_CHECK_ENABLED", True) and batch.tenant_id:
        try:
            from api.wallet.payout_integration import deduct_payout_wallet
            deduct_payout_wallet(tenant_id=batch.tenant_id, amount=batch.total_amount, reference=str(batch.id))
            logger.info("_setup_batch_for_processing: wallet deducted %s BDT for batch=%s tenant=%s",
                        batch.total_amount, batch.id, batch.tenant_id)
        except InsufficientFundsError:
            batch.mark_failed_with_release("Insufficient wallet balance.")
            raise
        except ImportError:
            logger.warning("_setup_batch_for_processing: api.wallet.payout_integration not found.")
        except Exception as exc:
            logger.error("_setup_batch_for_processing: wallet deduction failed: %s. Releasing lock.", exc)
            batch.mark_failed_with_release(f"Wallet deduction error: {exc}")
            raise InsufficientFundsError(str(exc)) from exc

    try:
        return _get_processor(batch.gateway)
    except GatewayError as exc:
        logger.error("_setup_batch_for_processing: cannot load processor for %s: %s", batch.gateway, exc)
        batch.mark_failed_with_release(str(exc))
        raise

def _process_batch_items(
    batch: PayoutBatch, processor, queued_items: list
) -> tuple[int, int, int, Decimal, list[str]]:
    """
    Iterate queued items, call gateway, mark success/failure.
    FIX v6: per-item DB exception safety prevents single bad item from
    rolling back all previous successes (double-payment risk on retry).
    """
    success_count          = 0
    failure_count          = 0
    skipped_count          = 0
    total_amount_processed = Decimal("0.00")
    error_details: list[str] = []

    _INSUF_CODES = frozenset({"INSUFFICIENT_BALANCE", "INSUFFICIENT_FUNDS", "2033", "2034", "WALLET_LIMIT_EXCEEDED"})

    for item in queued_items:
        # Step 1: Mark PROCESSING
        try:
            PayoutItem.objects.filter(pk=item.pk).update(status=PayoutItemStatus.PROCESSING, updated_at=timezone.now())
        except Exception as exc:
            logger.error("_process_batch_items: failed to mark item=%s PROCESSING: %s", item.id, exc)
            failure_count += 1
            error_details.append(f"item={item.id}: DB_UPDATE_PROCESSING_ERROR: {exc}")
            continue

        # Step 2: Call gateway
        try:
            result = processor.send_payout(
                account_number=item.account_number,  # EncryptedCharField decrypts transparently
                amount=item.net_amount,
                reference=item.internal_reference,
            )
        except GatewayTimeoutError as exc:
            try:
                item.mark_failed(error_code="TIMEOUT", error_message=str(exc))
            except Exception as me:
                logger.error("_process_batch_items: mark_failed DB error item=%s: %s", item.id, me)
            failure_count += 1
            error_details.append(f"item={item.id}: TIMEOUT: {exc}")
            continue
        except GatewayError as exc:
            try:
                item.mark_failed(error_code="GATEWAY_ERROR", error_message=str(exc))
            except Exception as me:
                logger.error("_process_batch_items: mark_failed DB error item=%s: %s", item.id, me)
            failure_count += 1
            error_details.append(f"item={item.id}: GATEWAY_ERROR: {exc}")
            continue
        except Exception as exc:
            logger.exception("_process_batch_items: unexpected error on item %s: %s", item.id, exc)
            try:
                item.mark_failed(error_code="INTERNAL_ERROR", error_message=str(exc))
            except Exception as me:
                logger.error("_process_batch_items: mark_failed DB error item=%s: %s", item.id, me)
            failure_count += 1
            error_details.append(f"item={item.id}: INTERNAL_ERROR: {exc}")
            continue

        # Step 3: Record outcome
        if result.success:
            try:
                item.mark_success(gateway_reference=result.gateway_reference, gateway_response=result.raw_response)
            except Exception as exc:
                logger.error(
                    "_process_batch_items: mark_success DB error item=%s: %s. Gateway ref=%s ISSUED — MANUAL RECONCILIATION REQUIRED.",
                    item.id, exc, result.gateway_reference,
                )
                failure_count += 1
                error_details.append(f"item={item.id}: DB_MARK_SUCCESS_ERROR (gw_ref={result.gateway_reference}): {exc}")
                continue
            success_count          += 1
            total_amount_processed += item.net_amount
            try:
                from .signals import payout_item_succeeded
                payout_item_succeeded.send(sender=PayoutItem, item=item)
            except Exception as _se:
                logger.warning("payout_item_succeeded signal: %s", _se)
        else:
            if result.error_code in _INSUF_CODES:
                raise InsufficientFundsError(
                    f"Gateway account has insufficient funds (code={result.error_code}). Halting batch {batch.id}."
                )
            try:
                item.mark_failed(error_code=result.error_code, error_message=result.error_message,
                                 gateway_response=result.raw_response)
            except Exception as exc:
                logger.error("_process_batch_items: mark_failed DB error item=%s: %s", item.id, exc)
            failure_count += 1
            error_details.append(f"item={item.id}: {result.error_code}: {result.error_message}")
            if item.status == PayoutItemStatus.FAILED:
                try:
                    from .signals import payout_item_permanently_failed
                    payout_item_permanently_failed.send(sender=PayoutItem, item=item)
                except Exception as _se:
                    logger.warning("payout_item_permanently_failed signal: %s", _se)

    return success_count, failure_count, skipped_count, total_amount_processed, error_details

def _finalise_batch(
    batch, actor_id, worker_id,
    success_count, failure_count, skipped_count,
    total_amount_processed, duration_ms, items_attempted, error_details,
) -> str:
    """Refresh totals, determine final status, refund wallet (v6), fire signals, write log."""
    batch.refresh_financial_totals()
    if failure_count == 0:
        final_status = PayoutBatchStatus.COMPLETED
    elif success_count == 0:
        final_status = PayoutBatchStatus.FAILED
    else:
        final_status = PayoutBatchStatus.PARTIALLY_COMPLETED

    batch.transition_to(final_status, actor=actor_id)
    _refund_batch_wallet(batch=batch, final_status=final_status)  # FIX v6

    try:
        from .signals import payout_batch_completed, payout_batch_failed
        if final_status in (PayoutBatchStatus.COMPLETED, PayoutBatchStatus.PARTIALLY_COMPLETED):
            payout_batch_completed.send(sender=PayoutBatch, batch=batch)
        elif final_status == PayoutBatchStatus.FAILED:
            payout_batch_failed.send(sender=PayoutBatch, batch=batch, error_summary="\n".join(error_details[:50]))
    except Exception as _sig_exc:
        logger.warning("batch signal error: %s", _sig_exc)

    _write_process_log(
        batch=batch,
        status=(BulkProcessLogStatus.SUCCESS if final_status == PayoutBatchStatus.COMPLETED
                else BulkProcessLogStatus.PARTIAL if final_status == PayoutBatchStatus.PARTIALLY_COMPLETED
                else BulkProcessLogStatus.FAILED),
        actor_id=actor_id, worker_id=worker_id,
        items_attempted=items_attempted, items_succeeded=success_count,
        items_failed=failure_count, items_skipped=skipped_count,
        duration_ms=duration_ms, total_amount_processed=total_amount_processed,
        error_summary="\n".join(error_details[:50]),
    )
    return final_status

@transaction.atomic
def process_batch(*, batch_id: Any, worker_id: str, actor_id: Optional[Any] = None) -> dict:
    """Process all QUEUED items in a PayoutBatch."""
    if not worker_id or not isinstance(worker_id, str):
        raise PayoutQueueError("worker_id must be a non-empty string.")

    batch     = _get_batch_locked(batch_id)
    processor = _setup_batch_for_processing(batch, worker_id, actor_id)

    queued_items = list(PayoutItem.objects.for_batch(batch_id).queued().select_for_update(skip_locked=True))
    logger.info("process_batch: batch=%s gateway=%s items=%d worker=%s", batch_id, batch.gateway, len(queued_items), worker_id)

    start_time = time.monotonic()
    success_count, failure_count, skipped_count, total_amount_processed, error_details = \
        _process_batch_items(batch, processor, queued_items)
    duration_ms = int((time.monotonic() - start_time) * 1000)

    final_status = _finalise_batch(
        batch=batch, actor_id=actor_id, worker_id=worker_id,
        success_count=success_count, failure_count=failure_count, skipped_count=skipped_count,
        total_amount_processed=total_amount_processed, duration_ms=duration_ms,
        items_attempted=len(queued_items), error_details=error_details,
    )
    logger.info("process_batch: batch=%s DONE status=%s success=%d failed=%d duration=%dms",
                batch_id, final_status, success_count, failure_count, duration_ms)
    return {
        "batch_id": str(batch_id), "status": final_status,
        "success_count": success_count, "failure_count": failure_count,
        "skipped_count": skipped_count,
        "total_amount_processed": str(total_amount_processed), "duration_ms": duration_ms,
    }

def _write_process_log(
    *, batch, status, actor_id, worker_id,
    items_attempted, items_succeeded, items_failed, items_skipped,
    duration_ms, total_amount_processed, error_summary,
) -> None:
    try:
        BulkProcessLog.objects.create(
            batch=batch, status=status, triggered_by_id=actor_id, task_id=worker_id,
            items_attempted=items_attempted, items_succeeded=items_succeeded,
            items_failed=items_failed, items_skipped=items_skipped,
            duration_ms=duration_ms, total_amount_processed=total_amount_processed,
            error_summary=error_summary[:4096], extra_data={"worker_id": worker_id},
        )
    except Exception as exc:
        logger.error("_write_process_log: failed: %s", exc)

# ---------------------------------------------------------------------------
# Retry Services
# ---------------------------------------------------------------------------

@transaction.atomic
def retry_failed_items(*, batch_id=None, item_ids=None, worker_id: str, limit=100) -> dict:
    """Retry RETRYING items that are due for re-processing."""
    if not worker_id:
        raise PayoutQueueError("worker_id is required.")

    qs = PayoutItem.objects.due_for_retry()
    if batch_id is not None:
        qs = qs.for_batch(batch_id)
    if item_ids is not None:
        if not isinstance(item_ids, list):
            raise PayoutQueueError("item_ids must be a list.")
        qs = qs.filter(pk__in=item_ids)

    cap   = limit if limit is not None else 100
    items = list(qs.select_for_update(skip_locked=True)[:cap])

    if not items:
        return {"retried_count": 0, "success_count": 0, "failure_count": 0}

    items_by_gateway: dict = {}
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
            PayoutItem.objects.filter(pk=item.pk).update(status=PayoutItemStatus.PROCESSING, updated_at=timezone.now())
            try:
                result = processor.send_payout(
                    account_number=item.account_number,  # EncryptedCharField decrypts transparently
                    amount=item.net_amount,
                    reference=item.internal_reference,
                )
            except Exception as exc:
                item.mark_failed(error_code="RETRY_ERROR", error_message=str(exc))
                failure_count += 1
                continue
            if result.success:
                item.mark_success(gateway_reference=result.gateway_reference, gateway_response=result.raw_response)
                success_count += 1
            else:
                item.mark_failed(error_code=result.error_code, error_message=result.error_message,
                                 gateway_response=result.raw_response)
                failure_count += 1

    logger.info("retry_failed_items: retried=%d success=%d failed=%d", len(items), success_count, failure_count)
    return {"retried_count": len(items), "success_count": success_count, "failure_count": failure_count}

# ---------------------------------------------------------------------------
# Batch state-transition wrappers  (DRY v7)
# ---------------------------------------------------------------------------

@transaction.atomic
def hold_payout_batch(*, batch_id: Any, actor_id: Optional[Any] = None, note: str = "") -> PayoutBatch:
    """DRY v7: delegates to _do_transition_batch."""
    return _do_transition_batch(batch_id=batch_id, new_status=PayoutBatchStatus.ON_HOLD,
                                actor_id=actor_id, note=note, default_note="Batch placed on hold.",
                                log_prefix="hold_payout_batch")

@transaction.atomic
def resume_payout_batch(*, batch_id: Any, actor_id: Optional[Any] = None, note: str = "") -> PayoutBatch:
    """DRY v7: delegates to _do_transition_batch."""
    return _do_transition_batch(batch_id=batch_id, new_status=PayoutBatchStatus.PENDING,
                                actor_id=actor_id, note=note, default_note="Batch resumed.",
                                log_prefix="resume_payout_batch")

@transaction.atomic
def cancel_payout_batch(*, batch_id: Any, actor_id: Optional[Any] = None, note: str = "") -> PayoutBatch:
    """
    DRY v7: core uses _do_transition_batch.
    FIX v6: issues wallet refund if batch was previously PROCESSING (wallet was deducted).
    """
    batch = _do_transition_batch(batch_id=batch_id, new_status=PayoutBatchStatus.CANCELLED,
                                 actor_id=actor_id, note=note, default_note="Batch cancelled.",
                                 log_prefix="cancel_payout_batch")

    from django.conf import settings as _settings
    if (getattr(_settings, "PAYOUT_WALLET_CHECK_ENABLED", True)
            and batch.tenant_id and batch.started_at is not None):
        try:
            from api.wallet.payout_integration import refund_payout_wallet
            refund_payout_wallet(tenant_id=batch.tenant_id, amount=batch.total_amount,
                                 reference=str(batch.id),
                                 reason=f"Batch {batch.id} cancelled after wallet deduction (actor={actor_id}).")
            logger.info("cancel_payout_batch: wallet refund issued for batch=%s amount=%s tenant=%s.",
                        batch.id, batch.total_amount, batch.tenant_id)
        except ImportError:
            logger.warning("cancel_payout_batch: api.wallet.payout_integration not available.")
        except Exception as exc:
            logger.error("cancel_payout_batch: wallet refund FAILED for batch=%s: %s. Manual reconciliation required.", batch.id, exc)

    return batch

@transaction.atomic
def release_batch_lock(*, batch_id: Any, actor_id: Optional[Any] = None) -> PayoutBatch:
    """Forcibly release the advisory lock on a stuck PROCESSING batch."""
    batch = _get_batch_or_raise(batch_id)
    batch.release_lock()
    logger.warning("release_batch_lock: lock forcibly released on batch=%s by actor=%s.", batch_id, actor_id)
    return batch

@transaction.atomic
def refresh_batch_totals(*, batch_id: Any, actor_id: Optional[Any] = None) -> PayoutBatch:
    """Recompute and persist the financial totals for a batch from its items."""
    batch = _get_batch_or_raise(batch_id)
    batch.refresh_financial_totals()
    logger.info("refresh_batch_totals: batch=%s actor=%s totals updated.", batch_id, actor_id)
    return batch

# ---------------------------------------------------------------------------
# Item service wrappers  (DRY v7)
# ---------------------------------------------------------------------------

@transaction.atomic
def skip_payout_item(*, item_id: Any, reason: str = "", actor_id: Optional[Any] = None) -> PayoutItem:
    """DRY v7: _get_item_locked replaces the inline try/except DoesNotExist."""
    item = _get_item_locked(item_id)
    item.skip(reason=reason or "")
    logger.info("skip_payout_item: item=%s skipped by actor=%s reason=%r", item_id, actor_id, reason)
    return item

@transaction.atomic
def cancel_payout_item(*, item_id: Any, reason: str, actor_id: Optional[Any] = None) -> PayoutItem:
    """DRY v7: _get_item_locked replaces the inline try/except DoesNotExist."""
    item = _get_item_locked(item_id)
    item.cancel(reason=reason or "")
    logger.info("cancel_payout_item: item=%s cancelled by actor=%s reason=%r", item_id, actor_id, reason)
    return item

# ---------------------------------------------------------------------------
# WithdrawalPriority service wrappers
# ---------------------------------------------------------------------------

@transaction.atomic
def deactivate_withdrawal_priority(*, priority_id: Any, actor_id: Optional[Any] = None) -> WithdrawalPriority:
    try:
        wp = WithdrawalPriority.objects.get(pk=priority_id)
    except WithdrawalPriority.DoesNotExist:
        raise PayoutQueueError(f"WithdrawalPriority pk={priority_id!r} does not exist.")
    wp.deactivate()
    logger.info("deactivate_withdrawal_priority: priority=%s actor=%s.", priority_id, actor_id)
    return wp

@transaction.atomic
def set_withdrawal_priority(
    *, user_id, priority, reason, payout_item_id=None, assigned_by_id=None, reason_note="", expires_at=None,
) -> WithdrawalPriority:
    if priority not in PriorityLevel.values:
        raise PayoutQueueError(f"Invalid priority '{priority}'.")
    if reason not in WithdrawalPriorityReason.values:
        raise PayoutQueueError(f"Invalid reason '{reason}'.")

    user              = _get_user_or_raise(user_id)
    current           = WithdrawalPriority.objects.get_active_for_user(user_id)
    previous_priority = current.priority if current else ""

    filter_kwargs: dict = {"user_id": user_id, "is_active": True}
    if payout_item_id is not None:
        filter_kwargs["payout_item_id"] = payout_item_id
    WithdrawalPriority.objects.filter(**filter_kwargs).update(is_active=False, updated_at=timezone.now())

    wp = WithdrawalPriority(
        user=user, priority=priority, previous_priority=previous_priority,
        reason=reason, reason_note=(reason_note or "").strip(),
        expires_at=expires_at, assigned_by_id=assigned_by_id, is_active=True,
    )
    if payout_item_id is not None:
        wp.payout_item_id = payout_item_id

    wp.full_clean()
    wp.pk = None
    super(WithdrawalPriority, wp).save()

    logger.info("set_withdrawal_priority: user=%s priority=%s reason=%s (prev=%s).", user_id, priority, reason, previous_priority)
    try:
        from .signals import withdrawal_priority_assigned
        withdrawal_priority_assigned.send(sender=WithdrawalPriority, priority=wp)
    except Exception as _se:
        logger.warning("withdrawal_priority_assigned signal: %s", _se)
    return wp

# ---------------------------------------------------------------------------
# Read-only helpers
# ---------------------------------------------------------------------------

def get_process_log(log_id: Any) -> BulkProcessLog:
    try:
        return BulkProcessLog.objects.get(pk=log_id)
    except BulkProcessLog.DoesNotExist:
        raise BulkProcessLogNotFoundError(f"BulkProcessLog {log_id} not found.")

def get_batch_statistics(batch_id: Any) -> dict:
    from django.core.cache import cache
    cache_key = f"pq:batch_stats:{batch_id}"
    cached    = cache.get(cache_key)
    if cached is not None:
        return cached

    batch = _get_batch_or_raise(batch_id)
    batch.refresh_from_db()

    result = {
        "batch_id":          str(batch.id),
        "name":              batch.name,
        "gateway":           batch.gateway,
        "status":            batch.status,
        "priority":          batch.priority,
        "item_count":        batch.item_count,
        "success_count":     batch.success_count,
        "failure_count":     batch.failure_count,
        "success_rate":      batch.success_rate,
        "total_amount":      str(batch.total_amount),
        "total_fee":         str(batch.total_fee),
        "net_amount":        str(batch.net_amount),
        "started_at":        batch.started_at.isoformat() if batch.started_at else None,
        "completed_at":      batch.completed_at.isoformat() if batch.completed_at else None,
        "process_log_count": batch.process_logs.count(),
    }
    if batch.is_terminal:
        cache.set(cache_key, result, timeout=PAYOUT_STATS_CACHE_TTL)
    return result
