"""
payout_queue/models.py  ← v8 PRODUCTION UPDATE (built on DRY v7)

CHANGES v8 (Production Gap #2 — Security: account_number encryption):

  ① account_number field changed from CharField → EncryptedCharField

     Before:  account_number was stored as plaintext in the database.
              A DB dump, a misconfigured backup, or a SQL injection would
              expose all recipient wallet/bank numbers.
              Bangladesh PDPA and BFIU guidelines require financial PII
              to be encrypted at rest.

     After:   EncryptedCharField (from utils/encryption.py) transparently
              encrypts the value with Fernet (AES-128-CBC + HMAC-SHA256)
              before writing to DB, and decrypts on read.
              Application code still reads item.account_number as plaintext
              — zero change to processors, validators, or views.

  ② account_number_hash field added (HMAC-SHA256 of plaintext)

     Problem: Encrypted fields cannot be used in filter() — ciphertext is
              different for each write (random IV), so two identical account
              numbers have different ciphertexts.
              The duplicate detection in services._create_single_payout_item
              used filter(account_number=...) — this would silently break.

     Solution: A deterministic one-way hash (HMAC-SHA256) of the plaintext
              account number is stored alongside the encrypted value.
              Same plaintext + same key = same 64-char hex hash → searchable.
              services.py and admin.py use account_number_hash for lookups.

  ③ PayoutItem.save() now auto-computes account_number_hash before write.

  ④ New index: pq_pi_acct_hash_idx on account_number_hash for fast lookups.

DRY v7 changes preserved:
  - AppendOnlyModel mixin (WithdrawalPriority + BulkProcessLog)
  - _LOCK_RELEASE_FIELDS constant on PayoutBatch
"""

from __future__ import annotations

import json
import logging
import uuid
from decimal import Decimal, InvalidOperation
from typing import Optional

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import Q, F, Sum, CheckConstraint, UniqueConstraint
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .choices import (
    PayoutBatchStatus,
    PayoutItemStatus,
    PaymentGateway,
    PriorityLevel,
    BulkProcessLogStatus,
    WithdrawalPriorityReason,
)
from .constants import (
    MIN_PAYOUT_AMOUNT,
    MAX_PAYOUT_AMOUNT,
    MAX_BATCH_SIZE,
    MAX_BATCH_NAME_LENGTH,
    MAX_ACCOUNT_NUMBER_LENGTH,
    MAX_REFERENCE_LENGTH,
    MAX_NOTE_LENGTH,
    MAX_ERROR_MESSAGE_LENGTH,
    MAX_RETRY_ATTEMPTS,
)
from .exceptions import (
    PayoutBatchStateError,
    PayoutItemStateError,
)
from .managers import (
    PayoutBatchManager,
    PayoutItemManager,
    WithdrawalPriorityManager,
    BulkProcessLogManager,
)
# v8: import encryption field and hash helper
from .utils.encryption import EncryptedCharField, compute_account_hash

logger = logging.getLogger(__name__)
User = get_user_model()

_MAX_META_BYTES = 32_768  # 32 KB

# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class TimestampedModel(models.Model):

    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name=_("ID"),
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name=_("Created At"),
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Updated At"),
    )

    class Meta:
        abstract = True
        ordering = ["-created_at"]

    def __repr__(self) -> str:  # pragma: no cover
        return f"<{self.__class__.__name__} id={self.id}>"

    def _validate_json_field(self, value: dict, field_name: str = "metadata") -> None:
        if not isinstance(value, dict):
            raise ValidationError({field_name: [_("Must be a JSON object.")]})
        try:
            encoded = json.dumps(value).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise ValidationError({field_name: [_(f"Not serialisable: {exc}")]})
        if len(encoded) > _MAX_META_BYTES:
            raise ValidationError(
                {field_name: [_(f"Exceeds maximum size of {_MAX_META_BYTES} bytes.")]}
            )

# ---------------------------------------------------------------------------
# DRY v7: AppendOnlyModel mixin
# ---------------------------------------------------------------------------

class AppendOnlyModel(TimestampedModel):
    """
    Abstract mixin for immutable append-only records.
    Eliminates the duplicate save() guard that was in WithdrawalPriority
    and BulkProcessLog (DRY v7).
    """

    _append_only_label: str = "This record"

    class Meta:
        abstract = True

    def save(self, *args, **kwargs) -> None:
        if self.pk:
            raise ValidationError(
                {"__all__": [
                    _(
                        f"{self._append_only_label} records are append-only "
                        f"and cannot be updated."
                    )
                ]}
            )
        self.full_clean()
        super().save(*args, **kwargs)

# ---------------------------------------------------------------------------
# PayoutBatch
# ---------------------------------------------------------------------------

class PayoutBatch(TimestampedModel):
    """
    A named batch of payout items to be processed together via a payment gateway.
    """

    # DRY v7: single source of truth for advisory-lock field clearing.
    _LOCK_RELEASE_FIELDS: dict = {"locked_at": None, "locked_by": ""}

    VALID_TRANSITIONS: dict[str, list[str]] = {
        PayoutBatchStatus.PENDING: [
            PayoutBatchStatus.PROCESSING,
            PayoutBatchStatus.CANCELLED,
            PayoutBatchStatus.ON_HOLD,
        ],
        PayoutBatchStatus.PROCESSING: [
            PayoutBatchStatus.COMPLETED,
            PayoutBatchStatus.PARTIALLY_COMPLETED,
            PayoutBatchStatus.FAILED,
            PayoutBatchStatus.ON_HOLD,
        ],
        PayoutBatchStatus.ON_HOLD: [
            PayoutBatchStatus.PENDING,
            PayoutBatchStatus.CANCELLED,
        ],
        PayoutBatchStatus.COMPLETED:           [],
        PayoutBatchStatus.PARTIALLY_COMPLETED: [],
        PayoutBatchStatus.FAILED:              [PayoutBatchStatus.PENDING],
        PayoutBatchStatus.CANCELLED:           [],
    }

    name = models.CharField(
        max_length=MAX_BATCH_NAME_LENGTH,
        verbose_name=_("Batch Name"),
    )
    gateway = models.CharField(
        max_length=10,
        choices=PaymentGateway.choices,
        db_index=True,
        verbose_name=_("Payment Gateway"),
    )
    status = models.CharField(
        max_length=25,
        choices=PayoutBatchStatus.choices,
        default=PayoutBatchStatus.PENDING,
        db_index=True,
        verbose_name=_("Status"),
    )
    priority = models.CharField(
        max_length=10,
        choices=PriorityLevel.choices,
        default=PriorityLevel.NORMAL,
        db_index=True,
        verbose_name=_("Priority"),
    )
    total_amount = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        verbose_name=_("Total Amount (BDT)"),
    )
    total_fee = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        verbose_name=_("Total Fee (BDT)"),
    )
    net_amount = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        verbose_name=_("Net Amount (BDT)"),
    )
    item_count    = models.PositiveIntegerField(default=0, verbose_name=_("Item Count"))
    success_count = models.PositiveIntegerField(default=0, verbose_name=_("Success Count"))
    failure_count = models.PositiveIntegerField(default=0, verbose_name=_("Failure Count"))
    locked_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Locked At"))
    locked_by = models.CharField(
        max_length=255, blank=True, default="", verbose_name=_("Locked By"),
    )
    scheduled_at = models.DateTimeField(null=True, blank=True, db_index=True, verbose_name=_("Scheduled At"))
    started_at   = models.DateTimeField(null=True, blank=True, verbose_name=_("Started At"))
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Completed At"))
    created_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="created_payout_batches", verbose_name=_("Created By"),
    )
    note = models.TextField(blank=True, default="", max_length=MAX_NOTE_LENGTH, verbose_name=_("Note"))
    error_summary = models.TextField(blank=True, default="", max_length=MAX_ERROR_MESSAGE_LENGTH, verbose_name=_("Error Summary"))
    metadata = models.JSONField(default=dict, blank=True, verbose_name=_("Metadata"))

    objects: PayoutBatchManager = PayoutBatchManager()

    class Meta(TimestampedModel.Meta):
        verbose_name        = _("Payout Batch")
        verbose_name_plural = _("Payout Batches")
        indexes = [
            models.Index(fields=["status", "priority", "scheduled_at"], name="pq_pb_status_pri_sched_idx"),
            models.Index(fields=["gateway", "status"],    name="pq_pb_gateway_status_idx"),
            models.Index(fields=["created_by", "status"], name="pq_pb_creator_status_idx"),
            models.Index(fields=["locked_at"],            name="pq_pb_locked_at_idx"),
        ]
        constraints = [
            CheckConstraint(check=Q(total_fee__lte=F("total_amount")),   name="pq_pb_fee_lte_amount"),
            CheckConstraint(check=Q(success_count__lte=F("item_count")), name="pq_pb_success_lte_count"),
            CheckConstraint(check=Q(failure_count__lte=F("item_count")), name="pq_pb_failure_lte_count"),
        ]

    def __str__(self) -> str:
        return f"{self.name} [{self.gateway} | {self.get_status_display()}]"

    @property
    def is_terminal(self) -> bool:
        return self.status in (
            PayoutBatchStatus.COMPLETED,
            PayoutBatchStatus.PARTIALLY_COMPLETED,
            PayoutBatchStatus.CANCELLED,
        )

    @property
    def is_locked(self) -> bool:
        return bool(self.locked_at)

    @property
    def success_rate(self) -> Optional[float]:
        if self.item_count == 0:
            return None
        return round((self.success_count / self.item_count) * 100, 2)

    @property
    def computed_net_amount(self) -> Decimal:
        return self.total_amount - self.total_fee

    def clean(self) -> None:
        errors: dict = {}
        if not self.name or not self.name.strip():
            errors.setdefault("name", []).append(_("name must not be empty."))
        if self.gateway not in PaymentGateway.values:
            errors.setdefault("gateway", []).append(_(f"Invalid gateway '{self.gateway}'."))
        if self.total_amount is not None and self.total_fee is not None:
            if self.total_fee > self.total_amount:
                errors.setdefault("total_fee", []).append(_("total_fee cannot exceed total_amount."))
        if (self.success_count is not None and self.item_count is not None
                and self.success_count > self.item_count):
            errors.setdefault("success_count", []).append(_("success_count cannot exceed item_count."))
        if self.started_at and self.completed_at:
            if self.completed_at < self.started_at:
                errors.setdefault("completed_at", []).append(_("completed_at cannot be before started_at."))
        if self.pk and self.is_terminal:
            try:
                original = PayoutBatch.objects.get(pk=self.pk)
                if original.is_terminal:
                    for field in ("total_amount", "total_fee", "net_amount", "gateway"):
                        if getattr(original, field) != getattr(self, field):
                            errors.setdefault(field, []).append(_(f"'{field}' cannot be changed on a terminal batch."))
            except PayoutBatch.DoesNotExist:
                pass
        self._validate_json_field(self.metadata)
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        super().save(*args, **kwargs)

    def transition_to(self, new_status: str, *, actor=None, note: str = "") -> None:
        if new_status not in PayoutBatchStatus.values:
            raise PayoutBatchStateError(f"Unknown batch status '{new_status}'.")
        allowed = self.VALID_TRANSITIONS.get(self.status, [])
        if new_status not in allowed:
            raise PayoutBatchStateError(
                f"Cannot transition PayoutBatch from '{self.status}' to '{new_status}'. Allowed: {allowed}"
            )
        old = self.status
        self.status = new_status
        now = timezone.now()
        update_fields = {"status": new_status, "updated_at": now}
        if new_status == PayoutBatchStatus.PROCESSING:
            self.started_at = now
            update_fields["started_at"] = now
        elif new_status in (PayoutBatchStatus.COMPLETED, PayoutBatchStatus.PARTIALLY_COMPLETED, PayoutBatchStatus.FAILED):
            self.completed_at = now
            update_fields["completed_at"] = now
            update_fields.update(self._LOCK_RELEASE_FIELDS)
            self.locked_at = None
            self.locked_by = ""
        if note:
            update_fields["note"] = (self.note + f"\n[{now.isoformat()}] {note}").strip()
            self.note = update_fields["note"]
        PayoutBatch.objects.filter(pk=self.pk).update(**update_fields)
        logger.info("PayoutBatch %s: %s → %s (actor=%s)", self.id, old, new_status, getattr(actor, "pk", "system"))

    def acquire_lock(self, worker_id: str) -> bool:
        if not worker_id or not isinstance(worker_id, str):
            raise ValueError("worker_id must be a non-empty string.")
        now = timezone.now()
        updated = PayoutBatch.objects.filter(
            pk=self.pk, locked_at__isnull=True, status=PayoutBatchStatus.PENDING,
        ).update(locked_at=now, locked_by=worker_id, updated_at=now)
        if updated == 1:
            self.locked_at = now
            self.locked_by = worker_id
            logger.debug("PayoutBatch %s locked by %s.", self.id, worker_id)
            return True
        logger.warning("PayoutBatch %s: lock acquisition failed for worker %s.", self.id, worker_id)
        return False

    def release_lock(self) -> None:
        PayoutBatch.objects.filter(pk=self.pk).update(
            **self._LOCK_RELEASE_FIELDS, updated_at=timezone.now(),
        )
        self.locked_at = None
        self.locked_by = ""
        logger.debug("PayoutBatch %s lock released.", self.id)

    def mark_failed_with_release(self, error_summary: str = "") -> None:
        now = timezone.now()
        update_fields: dict = {**self._LOCK_RELEASE_FIELDS, "updated_at": now}
        allowed = self.VALID_TRANSITIONS.get(self.status, [])
        if PayoutBatchStatus.FAILED in allowed:
            update_fields["status"]       = PayoutBatchStatus.FAILED
            update_fields["completed_at"] = now
            if error_summary:
                combined = (self.error_summary + f"\n[{now.isoformat()}] {error_summary}").strip()
                update_fields["error_summary"] = combined[:MAX_ERROR_MESSAGE_LENGTH]
        else:
            logger.warning(
                "PayoutBatch %s: mark_failed_with_release — FAILED not allowed from '%s'. Lock only.",
                self.id, self.status,
            )
        PayoutBatch.objects.filter(pk=self.pk).update(**update_fields)
        self.locked_at = None
        self.locked_by = ""
        if "status" in update_fields:
            self.status       = PayoutBatchStatus.FAILED
            self.completed_at = now
        logger.error("PayoutBatch %s: mark_failed_with_release. summary=%r", self.id, (error_summary or "")[:200])

    def refresh_financial_totals(self) -> None:
        agg = self.items.aggregate(
            total_amount=Sum("gross_amount"),
            total_fee=Sum("fee_amount"),
            item_count=models.Count("id"),
            success_count=models.Count("id", filter=Q(status=PayoutItemStatus.SUCCESS)),
            failure_count=models.Count("id", filter=Q(status=PayoutItemStatus.FAILED)),
        )
        total_amount = agg["total_amount"] or Decimal("0.00")
        total_fee    = agg["total_fee"]    or Decimal("0.00")
        net_amount   = total_amount - total_fee
        PayoutBatch.objects.filter(pk=self.pk).update(
            total_amount=total_amount, total_fee=total_fee, net_amount=net_amount,
            item_count=agg["item_count"] or 0,
            success_count=agg["success_count"] or 0,
            failure_count=agg["failure_count"] or 0,
            updated_at=timezone.now(),
        )
        self.total_amount  = total_amount
        self.total_fee     = total_fee
        self.net_amount    = net_amount
        self.item_count    = agg["item_count"] or 0
        self.success_count = agg["success_count"] or 0
        self.failure_count = agg["failure_count"] or 0
        logger.debug("PayoutBatch %s totals refreshed: amount=%s fee=%s net=%s items=%s",
                     self.id, total_amount, total_fee, net_amount, self.item_count)

# ---------------------------------------------------------------------------
# PayoutItem
# ---------------------------------------------------------------------------

class PayoutItem(TimestampedModel):

    batch = models.ForeignKey(PayoutBatch, on_delete=models.PROTECT, related_name="items", db_index=True, verbose_name=_("Batch"))
    user  = models.ForeignKey(User, on_delete=models.PROTECT, related_name="payout_items", db_index=True, verbose_name=_("User"))
    status = models.CharField(max_length=15, choices=PayoutItemStatus.choices, default=PayoutItemStatus.QUEUED, db_index=True, verbose_name=_("Status"))
    gateway = models.CharField(max_length=10, choices=PaymentGateway.choices, db_index=True, verbose_name=_("Gateway"))

    # v8: account_number is now encrypted at rest using Fernet AES-128-CBC.
    # Application code reads/writes plaintext — encryption is transparent.
    # CANNOT be used in filter() — use account_number_hash for lookups.
    account_number = EncryptedCharField(
        verbose_name=_("Recipient Account Number (encrypted)"),
        help_text=_(
            "Stored encrypted (Fernet AES-128-CBC). "
            "Requires PAYOUT_ENCRYPTION_KEY in .env. "
            "Use account_number_hash for DB filtering."
        ),
    )

    # v8: HMAC-SHA256 of plaintext account_number.
    # Deterministic (same plaintext + same key = same hash).
    # Used for duplicate detection and admin search.
    # 64-char lowercase hex string (SHA-256 output).
    account_number_hash = models.CharField(
        max_length=64,
        blank=True,
        default="",
        db_index=True,
        verbose_name=_("Account Number Hash"),
        help_text=_(
            "HMAC-SHA256 of account_number. Auto-computed on save. "
            "Used for duplicate detection and admin search."
        ),
    )

    gross_amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))], verbose_name=_("Gross Amount (BDT)"))
    fee_amount   = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"), validators=[MinValueValidator(Decimal("0.00"))], verbose_name=_("Fee Amount (BDT)"))
    net_amount   = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"), validators=[MinValueValidator(Decimal("0.00"))], verbose_name=_("Net Amount (BDT)"))

    gateway_reference = models.CharField(max_length=MAX_REFERENCE_LENGTH, blank=True, default="", db_index=True, verbose_name=_("Gateway Reference"))
    internal_reference = models.CharField(max_length=MAX_REFERENCE_LENGTH, blank=True, default="", unique=True, verbose_name=_("Internal Reference"))

    retry_count   = models.PositiveSmallIntegerField(default=0, verbose_name=_("Retry Count"))
    next_retry_at = models.DateTimeField(null=True, blank=True, db_index=True, verbose_name=_("Next Retry At"))
    processed_at  = models.DateTimeField(null=True, blank=True, verbose_name=_("Processed At"))

    error_code    = models.CharField(max_length=50, blank=True, default="", verbose_name=_("Error Code"))
    error_message = models.TextField(blank=True, default="", max_length=MAX_ERROR_MESSAGE_LENGTH, verbose_name=_("Error Message"))
    gateway_response = models.JSONField(default=dict, blank=True, verbose_name=_("Gateway Response"))

    note     = models.TextField(blank=True, default="", max_length=MAX_NOTE_LENGTH, verbose_name=_("Note"))
    metadata = models.JSONField(default=dict, blank=True, verbose_name=_("Metadata"))

    objects: PayoutItemManager = PayoutItemManager()

    class Meta(TimestampedModel.Meta):
        verbose_name        = _("Payout Item")
        verbose_name_plural = _("Payout Items")
        indexes = [
            models.Index(fields=["batch", "status"],              name="pq_pi_batch_status_idx"),
            models.Index(fields=["user", "status", "created_at"], name="pq_pi_user_status_crt_idx"),
            models.Index(fields=["gateway", "status"],            name="pq_pi_gateway_status_idx"),
            models.Index(fields=["next_retry_at", "status"],      name="pq_pi_retry_idx"),
            models.Index(fields=["gateway_reference"],            name="pq_pi_gw_ref_idx"),
            # v8: index on hash field for duplicate detection + admin search
            models.Index(fields=["account_number_hash"],          name="pq_pi_acct_hash_idx"),
        ]
        constraints = [
            CheckConstraint(check=Q(fee_amount__lte=F("gross_amount")), name="pq_pi_fee_lte_gross"),
            CheckConstraint(check=Q(retry_count__lte=3),               name="pq_pi_retry_count_max"),
        ]

    def __str__(self) -> str:
        return (
            f"Payout {self.gross_amount} BDT → [encrypted] "
            f"[{self.gateway} | {self.get_status_display()}]"
        )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_terminal(self) -> bool:
        return self.status in (PayoutItemStatus.SUCCESS, PayoutItemStatus.CANCELLED, PayoutItemStatus.SKIPPED)

    @property
    def can_retry(self) -> bool:
        return self.status == PayoutItemStatus.FAILED and self.retry_count < MAX_RETRY_ATTEMPTS

    @property
    def computed_net_amount(self) -> Decimal:
        gross = self.gross_amount or Decimal("0.00")
        fee   = self.fee_amount   or Decimal("0.00")
        return max(Decimal("0.00"), gross - fee)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def clean(self) -> None:
        errors: dict = {}

        if self.gross_amount is not None:
            if self.gross_amount < MIN_PAYOUT_AMOUNT:
                errors.setdefault("gross_amount", []).append(_(f"gross_amount must be at least {MIN_PAYOUT_AMOUNT} BDT."))
            if self.gross_amount > MAX_PAYOUT_AMOUNT:
                errors.setdefault("gross_amount", []).append(_(f"gross_amount cannot exceed {MAX_PAYOUT_AMOUNT} BDT."))

        if (self.fee_amount is not None and self.gross_amount is not None
                and self.fee_amount > self.gross_amount):
            errors.setdefault("fee_amount", []).append(_("fee_amount cannot exceed gross_amount."))

        if (self.gross_amount is not None and self.fee_amount is not None
                and self.net_amount is not None):
            expected_net = self.gross_amount - self.fee_amount
            if abs(self.net_amount - expected_net) > Decimal("0.01"):
                errors.setdefault("net_amount", []).append(
                    _(f"net_amount ({self.net_amount}) does not match gross_amount - fee_amount ({expected_net}).")
                )

        if not self.account_number or not str(self.account_number).strip():
            errors.setdefault("account_number", []).append(_("account_number must not be empty."))

        if self.retry_count is not None and self.retry_count > MAX_RETRY_ATTEMPTS:
            errors.setdefault("retry_count", []).append(_(f"retry_count cannot exceed {MAX_RETRY_ATTEMPTS}."))

        if self.pk and self.is_terminal:
            try:
                original = PayoutItem.objects.get(pk=self.pk)
                if original.is_terminal:
                    for field in ("gross_amount", "fee_amount", "net_amount", "user_id"):
                        if getattr(original, field) != getattr(self, field):
                            errors.setdefault(field, []).append(_(f"'{field}' cannot be changed on a terminal item."))
            except PayoutItem.DoesNotExist:
                pass

        self._validate_json_field(self.metadata)
        self._validate_json_field(self.gateway_response, "gateway_response")

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs) -> None:
        # v8: auto-compute account_number_hash before every save.
        # This ensures the hash is always in sync with the plaintext
        # (which is encrypted transparently by EncryptedCharField).
        if self.account_number:
            self.account_number_hash = compute_account_hash(str(self.account_number))
        self.full_clean()
        super().save(*args, **kwargs)

    # ------------------------------------------------------------------
    # State mutation methods
    # ------------------------------------------------------------------

    def mark_success(self, *, gateway_reference: str, gateway_response: dict = None) -> None:
        if self.is_terminal:
            raise PayoutItemStateError(f"PayoutItem {self.id} is already '{self.status}' and cannot be marked SUCCESS.")
        if not gateway_reference or not isinstance(gateway_reference, str):
            raise ValueError("gateway_reference must be a non-empty string.")
        now = timezone.now()
        PayoutItem.objects.filter(pk=self.pk).update(
            status=PayoutItemStatus.SUCCESS,
            gateway_reference=gateway_reference.strip(),
            gateway_response=(gateway_response if isinstance(gateway_response, dict) else {}),
            processed_at=now,
            error_code="",
            error_message="",
            updated_at=now,
        )
        self.status            = PayoutItemStatus.SUCCESS
        self.gateway_reference = gateway_reference.strip()
        self.processed_at      = now
        logger.info("PayoutItem %s marked SUCCESS: gateway_ref=%s", self.id, gateway_reference)

    def mark_failed(self, *, error_code: str, error_message: str, gateway_response: dict = None) -> None:
        if self.is_terminal and self.status == PayoutItemStatus.SUCCESS:
            raise PayoutItemStateError(f"PayoutItem {self.id} is SUCCESS and cannot be marked FAILED.")
        from .constants import RETRY_BACKOFF_SECONDS
        now             = timezone.now()
        new_retry_count = self.retry_count + 1
        if new_retry_count <= MAX_RETRY_ATTEMPTS:
            new_status = PayoutItemStatus.RETRYING
            delay_idx  = min(new_retry_count - 1, len(RETRY_BACKOFF_SECONDS) - 1)
            from datetime import timedelta
            next_retry = now + timedelta(seconds=RETRY_BACKOFF_SECONDS[delay_idx])
        else:
            new_status = PayoutItemStatus.FAILED
            next_retry = None
            logger.critical(
                "PayoutItem %s: RETRIES EXHAUSTED after %d attempts. Final error: %s — %s.",
                self.id, new_retry_count, error_code, (error_message or "")[:100],
            )
        PayoutItem.objects.filter(pk=self.pk).update(
            status=new_status,
            retry_count=new_retry_count,
            next_retry_at=next_retry,
            error_code=(error_code or "")[:50],
            error_message=(error_message or "")[:MAX_ERROR_MESSAGE_LENGTH],
            gateway_response=(gateway_response if isinstance(gateway_response, dict) else {}),
            processed_at=now,
            updated_at=now,
        )
        self.status        = new_status
        self.retry_count   = new_retry_count
        self.next_retry_at = next_retry
        self.error_code    = (error_code or "")[:50]
        self.error_message = (error_message or "")[:MAX_ERROR_MESSAGE_LENGTH]
        if new_status == PayoutItemStatus.FAILED:
            logger.error("PayoutItem %s FAILED (retries exhausted): %s — %s", self.id, error_code, error_message)
        else:
            logger.warning("PayoutItem %s RETRYING (attempt %d/%d): %s — %s",
                           self.id, new_retry_count, MAX_RETRY_ATTEMPTS, error_code, error_message)

    def cancel(self, *, reason: str = "") -> None:
        if self.status == PayoutItemStatus.SUCCESS:
            raise PayoutItemStateError(f"PayoutItem {self.id} is already SUCCESS and cannot be cancelled.")
        if self.status == PayoutItemStatus.CANCELLED:
            return
        PayoutItem.objects.filter(pk=self.pk).update(
            status=PayoutItemStatus.CANCELLED,
            note=f"Cancelled: {reason}" if reason else "Cancelled",
            updated_at=timezone.now(),
        )
        self.status = PayoutItemStatus.CANCELLED
        logger.info("PayoutItem %s cancelled. Reason: %s", self.id, reason)

    def skip(self, *, reason: str = "") -> None:
        if self.status == PayoutItemStatus.SUCCESS:
            raise PayoutItemStateError(f"PayoutItem {self.id} is SUCCESS and cannot be skipped.")
        if self.status == PayoutItemStatus.SKIPPED:
            return
        PayoutItem.objects.filter(pk=self.pk).update(
            status=PayoutItemStatus.SKIPPED,
            note=(f"Skipped: {reason}" if reason else "Skipped"),
            updated_at=timezone.now(),
        )
        self.status = PayoutItemStatus.SKIPPED
        logger.info("PayoutItem %s skipped. Reason: %s", self.id, reason)

# ---------------------------------------------------------------------------
# WithdrawalPriority  — DRY v7
# ---------------------------------------------------------------------------

class WithdrawalPriority(AppendOnlyModel):
    _append_only_label = "WithdrawalPriority"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="withdrawal_priorities", db_index=True, verbose_name=_("User"))
    payout_item = models.ForeignKey(PayoutItem, null=True, blank=True, on_delete=models.SET_NULL, related_name="priority_records", verbose_name=_("Payout Item"))
    priority = models.CharField(max_length=10, choices=PriorityLevel.choices, db_index=True, verbose_name=_("Priority"))
    previous_priority = models.CharField(max_length=10, choices=PriorityLevel.choices, blank=True, default="", verbose_name=_("Previous Priority"))
    reason = models.CharField(max_length=20, choices=WithdrawalPriorityReason.choices, verbose_name=_("Reason"))
    reason_note = models.TextField(blank=True, default="", max_length=MAX_NOTE_LENGTH, verbose_name=_("Reason Note"))
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True, verbose_name=_("Expires At"))
    assigned_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_withdrawal_priorities", verbose_name=_("Assigned By"))
    is_active = models.BooleanField(default=True, db_index=True, verbose_name=_("Is Active"))

    objects: WithdrawalPriorityManager = WithdrawalPriorityManager()

    class Meta(AppendOnlyModel.Meta):
        verbose_name        = _("Withdrawal Priority")
        verbose_name_plural = _("Withdrawal Priorities")
        indexes = [
            models.Index(fields=["user", "is_active", "priority"], name="pq_wp_user_active_pri_idx"),
            models.Index(fields=["payout_item", "is_active"],      name="pq_wp_item_active_idx"),
            models.Index(fields=["expires_at",  "is_active"],      name="pq_wp_exp_active_idx"),
        ]

    def __str__(self) -> str:
        return f"Priority {self.priority} for user={self.user_id} [{self.get_reason_display()}]"

    def clean(self) -> None:
        errors: dict = {}
        if self.priority not in PriorityLevel.values:
            errors.setdefault("priority", []).append(_(f"Invalid priority '{self.priority}'."))
        if self.reason not in WithdrawalPriorityReason.values:
            errors.setdefault("reason", []).append(_(f"Invalid reason '{self.reason}'."))
        if self.expires_at and self.expires_at <= timezone.now():
            errors.setdefault("expires_at", []).append(_("expires_at must be in the future."))
        if errors:
            raise ValidationError(errors)

    def deactivate(self) -> None:
        WithdrawalPriority.objects.filter(pk=self.pk).update(is_active=False, updated_at=timezone.now())
        self.is_active = False

# ---------------------------------------------------------------------------
# BulkProcessLog  — DRY v7
# ---------------------------------------------------------------------------

class BulkProcessLog(AppendOnlyModel):
    _append_only_label = "BulkProcessLog"

    batch        = models.ForeignKey(PayoutBatch, on_delete=models.PROTECT, related_name="process_logs", db_index=True, verbose_name=_("Batch"))
    status       = models.CharField(max_length=10, choices=BulkProcessLogStatus.choices, db_index=True, verbose_name=_("Status"))
    triggered_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="bulk_process_logs", verbose_name=_("Triggered By"))
    task_id      = models.CharField(max_length=255, blank=True, default="", db_index=True, verbose_name=_("Task ID"))

    items_attempted = models.PositiveIntegerField(default=0, verbose_name=_("Items Attempted"))
    items_succeeded = models.PositiveIntegerField(default=0, verbose_name=_("Items Succeeded"))
    items_failed    = models.PositiveIntegerField(default=0, verbose_name=_("Items Failed"))
    items_skipped   = models.PositiveIntegerField(default=0, verbose_name=_("Items Skipped"))
    duration_ms     = models.PositiveIntegerField(null=True, blank=True, verbose_name=_("Duration (ms)"))

    total_amount_processed = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        verbose_name=_("Total Amount Processed (BDT)"),
    )
    error_summary = models.TextField(blank=True, default="", max_length=MAX_ERROR_MESSAGE_LENGTH, verbose_name=_("Error Summary"))
    extra_data    = models.JSONField(default=dict, blank=True, verbose_name=_("Extra Data"))

    objects: BulkProcessLogManager = BulkProcessLogManager()

    class Meta(AppendOnlyModel.Meta):
        verbose_name        = _("Bulk Process Log")
        verbose_name_plural = _("Bulk Process Logs")
        indexes = [
            models.Index(fields=["batch",  "created_at"], name="pq_bpl_batch_created_idx"),
            models.Index(fields=["status", "created_at"], name="pq_bpl_status_created_idx"),
            models.Index(fields=["task_id"],               name="pq_bpl_task_id_idx"),
        ]
        constraints = [
            CheckConstraint(check=Q(items_succeeded__lte=F("items_attempted")), name="pq_bpl_succeeded_lte_attempted"),
            CheckConstraint(check=Q(items_failed__lte=F("items_attempted")),    name="pq_bpl_failed_lte_attempted"),
        ]

    def __str__(self) -> str:
        return f"ProcessLog [{self.status}] batch={self.batch_id} task={self.task_id} @ {self.created_at:%Y-%m-%d %H:%M}"

    def clean(self) -> None:
        errors: dict = {}
        if self.items_succeeded > self.items_attempted:
            errors.setdefault("items_succeeded", []).append(_("items_succeeded cannot exceed items_attempted."))
        if self.items_failed > self.items_attempted:
            errors.setdefault("items_failed", []).append(_("items_failed cannot exceed items_attempted."))
        self._validate_json_field(self.extra_data, "extra_data")
        if errors:
            raise ValidationError(errors)
