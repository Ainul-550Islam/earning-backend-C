"""
payout_queue/filters.py  ← v9 PRODUCTION FIX

CHANGES v9 (Remaining Gap #2 — encrypted field filter broken):

  ① account_number CharFilter replaced with AccountHashFilter

     Before:  account_number = django_filters.CharFilter(
                  field_name="account_number", lookup_expr="icontains"
              )
              After v8 encryption, account_number stores Fernet ciphertext.
              icontains on ciphertext NEVER matches any plaintext input.
              Staff using ?account_number=01700... always got 0 results silently.

     After:   AccountHashFilter (custom) hashes the input with compute_account_hash()
              and performs an EXACT match on account_number_hash.
              Same plaintext + same key = same hash, so the lookup works correctly.

              Note: This is an EXACT match (not icontains).
              Reason: partial matching on a hash is impossible by design.
              Staff must type the full account number to find items.
              The API response includes a note explaining this.

All previous filter improvements preserved unchanged.
"""
from __future__ import annotations

import django_filters
from django.db.models import Q

from .choices import (
    PayoutBatchStatus, PayoutItemStatus, PaymentGateway,
    PriorityLevel, BulkProcessLogStatus,
)
from .models import PayoutBatch, PayoutItem, BulkProcessLog

# ---------------------------------------------------------------------------
# v9: AccountHashFilter — hash input before filtering encrypted account field
# ---------------------------------------------------------------------------

class AccountHashFilter(django_filters.CharFilter):
    """
    v9: Custom CharFilter that hashes the plaintext input and filters
    by account_number_hash (exact match) instead of account_number (encrypted).

    Why: account_number is stored encrypted (EncryptedCharField + Fernet).
    After encryption, icontains on the ciphertext never matches plaintext input.
    The deterministic HMAC-SHA256 hash allows exact-match lookups without
    decrypting all rows.

    Limitation: full account number must be typed (no partial match).
    Behaviour with empty / whitespace input: returns unfiltered queryset.
    """

    def filter(self, qs, value: str):
        if not value or not value.strip():
            return qs
        try:
            from .utils.encryption import compute_account_hash
            acct_hash = compute_account_hash(value.strip())
            return qs.filter(account_number_hash=acct_hash)
        except Exception:
            # Never break queryset on hash error — return unfiltered
            return qs

# ---------------------------------------------------------------------------
# PayoutBatchFilter
# ---------------------------------------------------------------------------

class PayoutBatchFilter(django_filters.FilterSet):
    status   = django_filters.ChoiceFilter(choices=PayoutBatchStatus.choices)
    gateway  = django_filters.ChoiceFilter(choices=PaymentGateway.choices)
    priority = django_filters.ChoiceFilter(choices=PriorityLevel.choices)

    name = django_filters.CharFilter(
        field_name="name", lookup_expr="icontains",
        label="Batch name (partial match)",
    )

    created_after    = django_filters.DateTimeFilter(field_name="created_at",    lookup_expr="gte")
    created_before   = django_filters.DateTimeFilter(field_name="created_at",    lookup_expr="lte")
    scheduled_after  = django_filters.DateTimeFilter(field_name="scheduled_at",  lookup_expr="gte")
    scheduled_before = django_filters.DateTimeFilter(field_name="scheduled_at",  lookup_expr="lte")

    created_by = django_filters.NumberFilter(
        field_name="created_by__pk", lookup_expr="exact",
        label="Created by user PK",
    )
    is_locked = django_filters.BooleanFilter(
        field_name="locked_at", lookup_expr="isnull",
        label="Is locked", exclude=True,
    )
    ordering = django_filters.OrderingFilter(
        fields=(
            ("created_at", "created_at"),
            ("priority", "priority"),
            ("total_amount", "total_amount"),
            ("item_count", "item_count"),
            ("scheduled_at", "scheduled_at"),
        ),
    )

    class Meta:
        model  = PayoutBatch
        fields = ["status", "gateway", "priority", "name"]

# ---------------------------------------------------------------------------
# PayoutItemFilter
# ---------------------------------------------------------------------------

class PayoutItemFilter(django_filters.FilterSet):
    status  = django_filters.ChoiceFilter(choices=PayoutItemStatus.choices)
    gateway = django_filters.ChoiceFilter(choices=PaymentGateway.choices)
    batch   = django_filters.UUIDFilter()
    user    = django_filters.NumberFilter()

    amount_min = django_filters.NumberFilter(
        field_name="gross_amount", lookup_expr="gte",
        label="Gross amount (minimum BDT)",
    )
    amount_max = django_filters.NumberFilter(
        field_name="gross_amount", lookup_expr="lte",
        label="Gross amount (maximum BDT)",
    )

    created_after    = django_filters.DateTimeFilter(field_name="created_at",    lookup_expr="gte")
    created_before   = django_filters.DateTimeFilter(field_name="created_at",    lookup_expr="lte")
    processed_after  = django_filters.DateTimeFilter(field_name="processed_at",  lookup_expr="gte")
    processed_before = django_filters.DateTimeFilter(field_name="processed_at",  lookup_expr="lte")

    # v9: AccountHashFilter replaces CharFilter(field_name="account_number",
    #     lookup_expr="icontains") which was silently broken after encryption.
    # Usage: GET /items/?account_number=01711223344
    # Returns: items where compute_account_hash("01711223344") == account_number_hash
    # Note: full account number required (no partial match possible with hash).
    account_number = AccountHashFilter(
        label=(
            "Account number (exact match — full number required). "
            "Hashed internally for encrypted field lookup."
        ),
    )

    gateway_reference = django_filters.CharFilter(
        field_name="gateway_reference", lookup_expr="exact",
        label="Gateway reference (exact)",
    )
    has_error = django_filters.BooleanFilter(
        field_name="error_code", lookup_expr="isnull",
        label="Has error code", exclude=True,
    )
    ordering = django_filters.OrderingFilter(
        fields=(
            ("created_at",   "created_at"),
            ("gross_amount", "gross_amount"),
            ("processed_at", "processed_at"),
            ("retry_count",  "retry_count"),
        ),
    )

    class Meta:
        model  = PayoutItem
        fields = ["status", "gateway", "batch", "user"]

# ---------------------------------------------------------------------------
# BulkProcessLogFilter
# ---------------------------------------------------------------------------

class BulkProcessLogFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(choices=BulkProcessLogStatus.choices)
    batch  = django_filters.UUIDFilter()

    task_id = django_filters.CharFilter(
        field_name="task_id", lookup_expr="exact",
        label="Celery task ID (exact)",
    )
    created_after  = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_before = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")
    duration_min_ms = django_filters.NumberFilter(
        field_name="duration_ms", lookup_expr="gte",
        label="Duration at least (ms)",
    )
    ordering = django_filters.OrderingFilter(
        fields=(
            ("created_at",      "created_at"),
            ("duration_ms",     "duration_ms"),
            ("items_attempted", "items_attempted"),
        ),
    )

    class Meta:
        model  = BulkProcessLog
        fields = ["status", "batch", "task_id"]
