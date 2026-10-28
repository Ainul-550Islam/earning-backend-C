"""
# payout_queue/viewsets.py  ← v9 PRODUCTION FIX (built on v6)

# CHANGES v9 (Remaining Gap #3 — PII exposure in API surfaces):

# PayoutItemViewSet.search_fields: "account_number" removed
#       After v8 encryption, account_number stores ciphertext.
#       DRF SearchFilter uses icontains which never matches ciphertext.
#       Searches silently returned 0 results — broken without errors.
#       Fix: removed from search_fields. Use AccountHashFilter in filterset
#       for exact-match account lookups (?account_number=<full_number>).

# export_csv: account_number column now masked (last 4 chars only)
#       Was: writing full plaintext "01700123456" to CSV file.
#       Risk: CSV files saved to disk, emailed, or uploaded to cloud storage
#       would expose all recipient mobile wallet/bank numbers.
#       Fix: column renamed "account_number_masked", value = "****3456".
#       Full number still accessible via authenticated detail API endpoint.

# validate_account response: account_number masked
#       Was: returning {"account_number": "01700123456", "is_valid": true}.
#       Fix: returns {"account_number_masked": "****3456", "is_valid": true}.
#       The caller knows the number they sent — no need to echo it back.

# v6 changes preserved: audit_trail, wallet_balance, CancelPayoutItemSerializer.
"""

# CancelPayoutItemSerializer wired for POST /items/{id}/cancel/
#       Previously the cancel action parsed reason directly from request.data
#       without schema validation.  AuditTrailQuerySerializer and
#       BatchWalletBalanceSerializer also added to imports.

# v4 changes preserved:
#   - Exception HTTP semantics:
#       InvalidAccountNumberError → 422 Unprocessable Entity
#       DuplicatePayoutError      → 409 Conflict
#       FeeCalculationError       → 400 Bad Request  (was unhandled 500)
#   - Service-layer delegation for hold/resume/cancel/release-lock/refresh-totals/skip.
#   - _tenant_filter() on all 4 viewsets' get_queryset().
#   - All 32 original endpoints preserved.

# v3 changes preserved:
#   - GatewayAuthError, GatewayTimeoutError imports (runtime fix)
#   - throttle_classes on all viewsets
#   - ProcessBatchThrottle on process/retry actions
#   - SkipPayoutItemSerializer wired
#   - get_permissions() with IsTenantMember on item detail/mutation actions
# removed stray triple-quote
from __future__ import annotations

import csv
import io
import logging
import uuid as _uuid
from decimal import Decimal
from typing import Any

from django.conf import settings as _settings
from django.http import StreamingHttpResponse
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from .choices import PaymentGateway, PayoutBatchStatus
from .exceptions import (
    PayoutQueueError,
    PayoutBatchNotFoundError,
    PayoutBatchStateError,
    PayoutBatchLockedError,
    PayoutBatchLimitError,
    PayoutItemNotFoundError,
    PayoutItemStateError,
    InvalidPayoutAmountError,
    UserNotFoundError,
    GatewayError,
    GatewayAuthError,
    GatewayTimeoutError,
    InvalidAccountNumberError,
    DuplicatePayoutError,
)
from .filters import PayoutBatchFilter, PayoutItemFilter, BulkProcessLogFilter
from .models import PayoutBatch, PayoutItem, WithdrawalPriority, BulkProcessLog
from .permissions import IsStaffOrSuperuser, IsOwnerOrStaff, IsTenantMember
from .serializers import (
    PayoutBatchSerializer, CreatePayoutBatchSerializer,
    PayoutItemSerializer,
    WithdrawalPrioritySerializer, BulkProcessLogSerializer,
    SetWithdrawalPrioritySerializer,
    ValidateAccountSerializer,
    SkipPayoutItemSerializer,
    # v6: new action serializers
    CancelPayoutItemSerializer,
    AuditTrailQuerySerializer,
    BatchWalletBalanceSerializer,
)
from .throttles import (
    PayoutBurstThrottle,
    PayoutSustainedThrottle,
    ProcessBatchThrottle,
)
from . import services
# FIX v4: FeeCalculationError imported for explicit 400 handling
from .utils.fee_calculator import FeeCalculationError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _err(exc: Exception, http_status=status.HTTP_400_BAD_REQUEST) -> Response:
    return Response(
        {"detail": str(exc), "error_type": type(exc).__name__},
        status=http_status,
    )

def _tenant_filter(queryset, request):
    """
    FIX v4: Filter queryset by tenant when tenant info is on the user.
    Prevents cross-tenant data leakage. Falls back to unfiltered if the
    user model has no tenant_id (e.g. in tests or non-SaaS deployments).
    """
    tenant_id = getattr(request.user, "tenant_id", None)
    if tenant_id is not None:
        queryset = queryset.filter(tenant_id=tenant_id)
    return queryset


class PayoutQueuePagination(PageNumberPagination):
    page_size             = 20
    page_size_query_param = "page_size"
    max_page_size         = 100

# ---------------------------------------------------------------------------
# PayoutBatch ViewSet
# ---------------------------------------------------------------------------

class PayoutBatchViewSet(viewsets.ModelViewSet):
    """
    Full CRUD + processing actions for PayoutBatch.

    Endpoints:
      Standard:
        GET    /batches/                  — list (paginated, filtered)
        POST   /batches/                  — create (with optional inline items)
        GET    /batches/{id}/             — retrieve
        PUT    /batches/{id}/             — update (name/note/metadata only)
        PATCH  /batches/{id}/             — partial update
        DELETE /batches/{id}/             — destroy

      Processing:
        POST   /batches/{id}/process/        — sync processing
        POST   /batches/{id}/process-async/  — async via Celery

      State transitions:
        POST   /batches/{id}/add-items/      — add items to PENDING batch
        POST   /batches/{id}/cancel/         — cancel (+ wallet refund if needed)
        POST   /batches/{id}/hold/           — pause
        POST   /batches/{id}/resume/         — resume from ON_HOLD
        POST   /batches/{id}/release-lock/   — force-release stuck lock
        POST   /batches/{id}/refresh-totals/ — recompute financial totals

      Read-only stats & meta:
        GET    /batches/{id}/statistics/     — batch stats (cached for terminal)
        GET    /batches/{id}/audit-trail/    — [v6] compliance audit log
        GET    /batches/{id}/wallet-balance/ — [v6] available wallet balance
        GET    /batches/financial-summary/   — aggregate across all batches
        GET    /batches/gateways/            — available gateways + fee info
        GET    /batches/choices/             — all enum choices
    """
    serializer_class   = PayoutBatchSerializer
    permission_classes = [IsStaffOrSuperuser]
    throttle_classes   = [PayoutBurstThrottle, PayoutSustainedThrottle]
    filterset_class    = PayoutBatchFilter
    pagination_class   = PayoutQueuePagination
    filter_backends    = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields      = ["name", "id"]
    ordering_fields    = ["created_at", "priority", "total_amount", "item_count"]
    ordering           = ["-priority", "-created_at"]

    def get_queryset(self):
        qs = PayoutBatch.objects.select_related("created_by").prefetch_related(
            "process_logs"
        )
        return _tenant_filter(qs, self.request)

    def create(self, request: Request, *args, **kwargs) -> Response:
        """POST /batches/ — create a batch, optionally with inline items."""
        serializer = CreatePayoutBatchSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        data = serializer.validated_data
        try:
            batch = services.create_payout_batch(
                name=data["name"],
                gateway=data["gateway"],
                priority=data.get("priority"),
                scheduled_at=data.get("scheduled_at"),
                created_by_id=request.user.pk,
                note=data.get("note", ""),
                metadata=data.get("metadata", {}),
            )
            if data.get("items"):
                services.add_payout_items(
                    batch_id=batch.id,
                    items=data["items"],
                )
        except (InvalidAccountNumberError,) as exc:
            return _err(exc, status.HTTP_422_UNPROCESSABLE_ENTITY)
        except (DuplicatePayoutError,) as exc:
            return _err(exc, status.HTTP_409_CONFLICT)
        except (FeeCalculationError, InvalidPayoutAmountError) as exc:
            return _err(exc, status.HTTP_400_BAD_REQUEST)
        except PayoutQueueError as exc:
            return _err(exc)
        return Response(
            PayoutBatchSerializer(batch).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="add-items")
    def add_items(self, request: Request, pk: Any = None) -> Response:
        """POST /batches/{id}/add-items/"""
        items = request.data.get("items", [])
        if not isinstance(items, list) or not items:
            return Response(
                {"detail": "items must be a non-empty list."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            created = services.add_payout_items(
                batch_id=pk,
                items=items,
                validate_accounts=request.data.get("validate_accounts", True),
            )
        except PayoutBatchNotFoundError as exc:
            return _err(exc, status.HTTP_404_NOT_FOUND)
        except (InvalidAccountNumberError,) as exc:
            return _err(exc, status.HTTP_422_UNPROCESSABLE_ENTITY)
        except (DuplicatePayoutError,) as exc:
            return _err(exc, status.HTTP_409_CONFLICT)
        except (FeeCalculationError, InvalidPayoutAmountError) as exc:
            return _err(exc, status.HTTP_400_BAD_REQUEST)
        except PayoutQueueError as exc:
            return _err(exc)
        return Response(
            PayoutItemSerializer(created, many=True).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="process")
    def process(self, request: Request, pk: Any = None) -> Response:
        """POST /batches/{id}/process/ — synchronous processing."""
        self.throttle_classes = [ProcessBatchThrottle]
        self.check_throttles(request)
        worker_id = f"api-{str(_uuid.uuid4())[:8]}"
        try:
            result = services.process_batch(
                batch_id=pk,
                worker_id=worker_id,
                actor_id=request.user.pk,
            )
        except PayoutBatchNotFoundError as exc:
            return _err(exc, status.HTTP_404_NOT_FOUND)
        except PayoutBatchLockedError as exc:
            return _err(exc, status.HTTP_423_LOCKED)
        except (PayoutBatchStateError, PayoutBatchLimitError) as exc:
            return _err(exc, status.HTTP_409_CONFLICT)
        except PayoutQueueError as exc:
            return _err(exc)
        return Response(result)

    @action(detail=True, methods=["post"], url_path="process-async")
    def process_async(self, request: Request, pk: Any = None) -> Response:
        """POST /batches/{id}/process-async/ — async via Celery."""
        self.throttle_classes = [ProcessBatchThrottle]
        self.check_throttles(request)
        try:
            from .tasks import process_batch_async
            task_id = str(_uuid.uuid4())
            process_batch_async.apply_async(
                kwargs={
                    "batch_id":  str(pk),
                    "actor_id":  str(request.user.pk),
                },
                task_id=task_id,
            )
        except PayoutBatchNotFoundError as exc:
            return _err(exc, status.HTTP_404_NOT_FOUND)
        except Exception as exc:
            logger.error("process_async: failed to queue task: %s", exc)
            return _err(
                PayoutQueueError(f"Failed to queue processing task: {exc}"),
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return Response(
            {"status": "queued", "task_id": task_id},
            status=status.HTTP_202_ACCEPTED,
        )

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request: Request, pk: Any = None) -> Response:
        """
        POST /batches/{id}/cancel/

        FIX v6: services.cancel_payout_batch() now issues a wallet refund
        when the batch was previously in PROCESSING (started_at is set).
        """
        try:
            batch = services.cancel_payout_batch(
                batch_id=pk,
                actor_id=request.user.pk,
                note=request.data.get("note", ""),
            )
        except PayoutBatchNotFoundError as exc:
            return _err(exc, status.HTTP_404_NOT_FOUND)
        except PayoutBatchStateError as exc:
            return _err(exc, status.HTTP_409_CONFLICT)
        except PayoutQueueError as exc:
            return _err(exc)
        return Response(PayoutBatchSerializer(batch).data)

    @action(detail=True, methods=["post"], url_path="hold")
    def hold(self, request: Request, pk: Any = None) -> Response:
        """POST /batches/{id}/hold/ — pause PENDING or PROCESSING batch."""
        try:
            batch = services.hold_payout_batch(
                batch_id=pk,
                actor_id=request.user.pk,
                note=request.data.get("note", ""),
            )
        except PayoutBatchNotFoundError as exc:
            return _err(exc, status.HTTP_404_NOT_FOUND)
        except PayoutBatchStateError as exc:
            return _err(exc, status.HTTP_409_CONFLICT)
        except PayoutQueueError as exc:
            return _err(exc)
        return Response(PayoutBatchSerializer(batch).data)

    @action(detail=True, methods=["post"], url_path="resume")
    def resume(self, request: Request, pk: Any = None) -> Response:
        """POST /batches/{id}/resume/ — resume ON_HOLD batch."""
        try:
            batch = services.resume_payout_batch(
                batch_id=pk,
                actor_id=request.user.pk,
                note=request.data.get("note", ""),
            )
        except PayoutBatchNotFoundError as exc:
            return _err(exc, status.HTTP_404_NOT_FOUND)
        except PayoutBatchStateError as exc:
            return _err(exc, status.HTTP_409_CONFLICT)
        except PayoutQueueError as exc:
            return _err(exc)
        return Response(PayoutBatchSerializer(batch).data)

    @action(detail=True, methods=["post"], url_path="release-lock")
    def release_lock(self, request: Request, pk: Any = None) -> Response:
        """POST /batches/{id}/release-lock/ — force-release stuck lock."""
        try:
            batch = services.release_batch_lock(
                batch_id=pk,
                actor_id=request.user.pk,
            )
        except PayoutBatchNotFoundError as exc:
            return _err(exc, status.HTTP_404_NOT_FOUND)
        except PayoutQueueError as exc:
            return _err(exc)
        return Response(PayoutBatchSerializer(batch).data)

    @action(detail=True, methods=["post"], url_path="refresh-totals")
    def refresh_totals(self, request: Request, pk: Any = None) -> Response:
        """POST /batches/{id}/refresh-totals/ — recompute financial totals."""
        try:
            batch = services.refresh_batch_totals(
                batch_id=pk,
                actor_id=request.user.pk,
            )
        except PayoutBatchNotFoundError as exc:
            return _err(exc, status.HTTP_404_NOT_FOUND)
        except PayoutQueueError as exc:
            return _err(exc)
        return Response(PayoutBatchSerializer(batch).data)

    @action(detail=True, methods=["get"], url_path="statistics")
    def statistics(self, request: Request, pk: Any = None) -> Response:
        """GET /batches/{id}/statistics/"""
        try:
            result = services.get_batch_statistics(pk)
        except PayoutBatchNotFoundError as exc:
            return _err(exc, status.HTTP_404_NOT_FOUND)
        except PayoutQueueError as exc:
            return _err(exc)
        return Response(result)

    # ── FIX v6: New endpoints ────────────────────────────────────────────────

    @action(detail=True, methods=["get"], url_path="audit-trail")
    def audit_trail(self, request: Request, pk: Any = None) -> Response:
        """
        GET /batches/{id}/audit-trail/

        FIX v6: Exposes get_payout_audit_trail() from api.audit_logs.
        Previously this function was fully implemented but had no API endpoint.
        Compliance officers had no programmatic way to retrieve the audit log
        for a batch.

        Query params (all optional):
          page         — page number (default 1)
          page_size    — entries per page (default 50, max 200)
          action_filter — filter by audit action code, e.g. BATCH_CREATED,
                          ITEM_SUCCEEDED, ITEM_PERMANENTLY_FAILED

        Returns:
          200 — paginated audit trail entries
          404 — batch not found
          503 — audit_logs integration not installed
        """
        query_serializer = AuditTrailQuerySerializer(data=request.query_params)
        if not query_serializer.is_valid():
            return Response(
                query_serializer.errors, status=status.HTTP_400_BAD_REQUEST
            )
        params = query_serializer.validated_data

        try:
            batch = PayoutBatch.objects.get(pk=pk)
        except PayoutBatch.DoesNotExist:
            return _err(
                PayoutBatchNotFoundError(f"PayoutBatch {pk} not found."),
                status.HTTP_404_NOT_FOUND,
            )

        try:
            from api.audit_logs.payout_integration import get_payout_audit_trail
        except ImportError:
            return Response(
                {
                    "detail": (
                        "Audit log integration (api.audit_logs) is not installed. "
                        "Install it or set PAYOUT_AUDIT_LOG_ENABLED=False to suppress."
                    )
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        try:
            trail = get_payout_audit_trail(
                batch_id=str(batch.id),
                action_filter=params.get("action_filter") or None,
                page=params["page"],
                page_size=params["page_size"],
            )
        except Exception as exc:
            logger.error("audit_trail: failed for batch=%s: %s", pk, exc)
            return _err(
                PayoutQueueError(f"Audit trail retrieval failed: {exc}"),
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(trail)

    @action(detail=True, methods=["get"], url_path="wallet-balance")
    def wallet_balance(self, request: Request, pk: Any = None) -> Response:
        """
        GET /batches/{id}/wallet-balance/

        FIX v6: Exposes get_payout_wallet_balance() from api.wallet.
        Previously this function was defined in wallet/payout_integration.py
        but never called from any view.

        Operators can call this BEFORE processing to confirm the tenant wallet
        holds enough funds.  The UI should gate the "Process" button on
        is_sufficient=True.

        Returns:
          200 — {batch_id, tenant_id, batch_total_amount,
                 wallet_balance, is_sufficient, shortfall}
          200 (with message) — PAYOUT_WALLET_CHECK_ENABLED=False (dev mode)
          404 — batch not found
          503 — wallet integration not installed
        """
        try:
            batch = PayoutBatch.objects.get(pk=pk)
        except PayoutBatch.DoesNotExist:
            return _err(
                PayoutBatchNotFoundError(f"PayoutBatch {pk} not found."),
                status.HTTP_404_NOT_FOUND,
            )

        if not getattr(_settings, "PAYOUT_WALLET_CHECK_ENABLED", True):
            return Response(
                {
                    "detail": (
                        "PAYOUT_WALLET_CHECK_ENABLED is False. "
                        "Wallet balance check is disabled in this environment."
                    )
                },
                status=status.HTTP_200_OK,
            )

        if not batch.tenant_id:
            return Response(
                {
                    "detail": (
                        "This batch has no tenant_id. "
                        "Wallet balance check is not applicable."
                    )
                },
                status=status.HTTP_200_OK,
            )

        try:
            from api.wallet.payout_integration import get_payout_wallet_balance
        except ImportError:
            return Response(
                {
                    "detail": (
                        "Wallet integration (api.wallet) is not installed. "
                        "Set PAYOUT_WALLET_CHECK_ENABLED=False to suppress."
                    )
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        try:
            raw_balance = get_payout_wallet_balance(tenant_id=batch.tenant_id)
            balance     = Decimal(str(raw_balance))
        except Exception as exc:
            logger.error("wallet_balance: failed for batch=%s: %s", pk, exc)
            return _err(
                PayoutQueueError(f"Wallet balance retrieval failed: {exc}"),
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        batch_total  = batch.total_amount
        is_sufficient = balance >= batch_total
        shortfall    = (batch_total - balance) if not is_sufficient else None

        serializer = BatchWalletBalanceSerializer(
            {
                "batch_id":           batch.id,
                "tenant_id":          str(batch.tenant_id),
                "batch_total_amount": batch_total,
                "wallet_balance":     balance,
                "is_sufficient":      is_sufficient,
                "shortfall":          shortfall,
            }
        )
        return Response(serializer.data)

    # ── Existing list/detail read-only actions ───────────────────────────────

    @action(detail=False, methods=["get"], url_path="financial-summary")
    def financial_summary(self, request: Request) -> Response:
        """GET /batches/financial-summary/"""
        summary = PayoutBatch.objects.financial_summary()
        return Response(summary)

    @action(detail=False, methods=["get"], url_path="gateways")
    def gateways(self, request: Request) -> Response:
        """GET /batches/gateways/ — return available gateways and fee info."""
        from .utils.fee_calculator import FeeCalculator
        fc       = FeeCalculator()
        gateways = []
        for gw in PaymentGateway.values:
            try:
                summary = fc.get_fee_summary(gw)
            except Exception:
                summary = {}
            gateways.append({
                "value":       gw,
                "label":       PaymentGateway(gw).label,
                "fee_summary": summary,
            })
        return Response({"gateways": gateways})

    @action(detail=False, methods=["get"], url_path="choices")
    def choices(self, request: Request) -> Response:
        """GET /batches/choices/ — return all enum choices."""
        from .choices import (
            PayoutBatchStatus, PayoutItemStatus, PriorityLevel,
            PaymentGateway, WithdrawalPriorityReason, FeeType,
        )
        return Response({
            "batch_statuses":   list(PayoutBatchStatus.choices),
            "item_statuses":    list(PayoutItemStatus.choices),
            "priority_levels":  list(PriorityLevel.choices),
            "gateways":         list(PaymentGateway.choices),
            "priority_reasons": list(WithdrawalPriorityReason.choices),
            "fee_types":        list(FeeType.choices),
        })

# ---------------------------------------------------------------------------
# PayoutItem ViewSet
# ---------------------------------------------------------------------------

class PayoutItemViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ReadOnly base + mutating custom actions for PayoutItem.

    Endpoints:
      Standard:
        GET  /items/          — list (paginated, filtered)
        GET  /items/{id}/     — retrieve

      Actions:
        POST /items/{id}/cancel/          — cancel a non-SUCCESS item
        POST /items/{id}/skip/            — mark SKIPPED
        POST /items/{id}/retry/           — retry single item immediately
        POST /items/retry-due/            — retry all due items
        POST /items/{id}/verify/          — verify with gateway
        POST /items/validate-account/     — validate recipient account
        GET  /items/export-csv/           — streaming CSV export
    """
    serializer_class   = PayoutItemSerializer
    permission_classes = [IsStaffOrSuperuser]
    throttle_classes   = [PayoutBurstThrottle, PayoutSustainedThrottle]
    filterset_class    = PayoutItemFilter
    pagination_class   = PayoutQueuePagination
    filter_backends    = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    # v9: "account_number" removed — field is now encrypted (EncryptedCharField).
    # icontains on ciphertext never matches plaintext input → 0 results silently.
    # Use AccountHashFilter in filterset_class for exact-match account lookups.
    search_fields      = ["gateway_reference", "internal_reference"]
    ordering_fields    = ["created_at", "gross_amount", "processed_at", "retry_count"]
    ordering           = ["-created_at"]

    def get_queryset(self):
        qs = PayoutItem.objects.select_related("batch", "user")
        return _tenant_filter(qs, self.request)

    def get_permissions(self):
        """
        Apply object-level permissions for retrieve and mutating actions.
        list / non-detail: IsStaffOrSuperuser only (queryset limits scope).
        retrieve / detail actions: also check IsTenantMember.
        """
        if self.action in ("retrieve", "cancel", "skip", "retry", "verify"):
            return [IsStaffOrSuperuser(), IsTenantMember()]
        return [IsStaffOrSuperuser()]

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request: Request, pk: Any = None) -> Response:
        """
        POST /items/{id}/cancel/

        FIX v6: Now uses CancelPayoutItemSerializer to validate and document
        the reason field, instead of reading from raw request.data.
        """
        serializer = CancelPayoutItemSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        reason = serializer.validated_data["reason"]
        try:
            item = services.cancel_payout_item(
                item_id=pk,
                reason=reason,
                actor_id=request.user.pk,
            )
        except PayoutItemNotFoundError as exc:
            return _err(exc, status.HTTP_404_NOT_FOUND)
        except PayoutItemStateError as exc:
            return _err(exc, status.HTTP_409_CONFLICT)
        except PayoutQueueError as exc:
            return _err(exc)
        return Response(PayoutItemSerializer(item).data)

    @action(detail=True, methods=["post"], url_path="skip")
    def skip(self, request: Request, pk: Any = None) -> Response:
        """POST /items/{id}/skip/ — mark item SKIPPED, no retry."""
        serializer = SkipPayoutItemSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        reason = serializer.validated_data.get("reason", "")
        try:
            item = services.skip_payout_item(
                item_id=pk,
                reason=reason,
                actor_id=request.user.pk,
            )
        except PayoutItemNotFoundError as exc:
            return _err(exc, status.HTTP_404_NOT_FOUND)
        except PayoutItemStateError as exc:
            return _err(exc, status.HTTP_409_CONFLICT)
        except PayoutQueueError as exc:
            return _err(exc)
        return Response(PayoutItemSerializer(item).data)

    @action(detail=True, methods=["post"], url_path="retry")
    def retry(self, request: Request, pk: Any = None) -> Response:
        """POST /items/{id}/retry/ — retry a single item immediately."""
        self.throttle_classes = [ProcessBatchThrottle]
        self.check_throttles(request)
        worker_id = f"api-retry-{str(_uuid.uuid4())[:8]}"
        try:
            result = services.retry_failed_items(
                item_ids=[pk],
                worker_id=worker_id,
            )
        except PayoutItemNotFoundError as exc:
            return _err(exc, status.HTTP_404_NOT_FOUND)
        except PayoutQueueError as exc:
            return _err(exc)
        return Response(result)

    @action(detail=False, methods=["post"], url_path="retry-due")
    def retry_due(self, request: Request) -> Response:
        """POST /items/retry-due/ — retry all due items (batch operation)."""
        self.throttle_classes = [ProcessBatchThrottle]
        self.check_throttles(request)
        worker_id = f"api-retry-due-{str(_uuid.uuid4())[:8]}"
        limit = request.data.get("limit", 100)
        try:
            result = services.retry_failed_items(
                worker_id=worker_id,
                limit=int(limit),
            )
        except PayoutQueueError as exc:
            return _err(exc)
        return Response(result)

    @action(detail=True, methods=["post"], url_path="verify")
    def verify(self, request: Request, pk: Any = None) -> Response:
        """POST /items/{id}/verify/ — verify item status with gateway."""
        try:
            item = PayoutItem.objects.get(pk=pk)
        except PayoutItem.DoesNotExist:
            return _err(
                PayoutItemNotFoundError(f"Item {pk} not found."),
                status.HTTP_404_NOT_FOUND,
            )
        if not item.gateway_reference:
            return Response(
                {"detail": "No gateway_reference to verify against."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            processor = services._get_processor(item.gateway)
            result    = processor.verify_transaction(item.gateway_reference)
        except GatewayAuthError as exc:
            return _err(exc, status.HTTP_401_UNAUTHORIZED)
        except GatewayTimeoutError as exc:
            return _err(exc, status.HTTP_504_GATEWAY_TIMEOUT)
        except GatewayError as exc:
            return _err(exc, status.HTTP_502_BAD_GATEWAY)
        return Response({
            "item_id":           str(item.id),
            "gateway_reference": item.gateway_reference,
            "verified_success":  result.success,
            "error_code":        result.error_code,
            "error_message":     result.error_message,
            "raw_response":      result.raw_response,
        })

    @action(detail=False, methods=["post"], url_path="validate-account")
    def validate_account(self, request: Request) -> Response:
        """POST /items/validate-account/ — validate a recipient account."""
        serializer = ValidateAccountSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        gateway        = serializer.validated_data["gateway"]
        account_number = serializer.validated_data["account_number"]
        try:
            processor = services._get_processor(gateway)
            is_valid  = processor.validate_account(account_number)
        except GatewayError as exc:
            return _err(exc, status.HTTP_502_BAD_GATEWAY)
        return Response({
            "gateway":               gateway,
            # v9: masked — do not echo plaintext account number back in API response
            "account_number_masked": ("*" * max(0, len(account_number) - 4) + account_number[-4:]) if len(account_number) > 4 else account_number,
            "is_valid":              is_valid,
        })

    @action(detail=False, methods=["get"], url_path="export-csv")
    def export_csv(self, request: Request) -> Response:
        """
        GET /items/export-csv/ — streaming CSV export.

        v9: account_number column now shows masked value (last 4 chars only).
        Reason: CSV files may be saved to disk, emailed, or stored in cloud
        storage by staff — writing plaintext wallet/bank numbers to CSV is a
        PII/GDPR risk. The masked value (e.g. ****3456) is sufficient for
        most support workflows. Full account_number is available on the detail
        API endpoint for individual item lookups (staff-authenticated).
        """
        qs = self.filter_queryset(self.get_queryset())

        def _mask(val: str, visible: int = 4) -> str:
            """Return last `visible` chars, padded with asterisks."""
            s = str(val or "")
            return ("*" * max(0, len(s) - visible) + s[-visible:]) if len(s) > visible else s

        def stream_csv():
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow([
                "id", "batch_id", "user_id", "status", "gateway",
                # v9: masked — was full plaintext account_number
                "account_number_masked",
                "gross_amount", "fee_amount", "net_amount",
                "gateway_reference", "retry_count", "processed_at", "created_at",
            ])
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)

            batch_size = 500
            offset     = 0
            while True:
                chunk = list(qs[offset:offset + batch_size])
                if not chunk:
                    break
                for item in chunk:
                    writer.writerow([
                        str(item.id), str(item.batch_id), item.user_id,
                        item.status, item.gateway,
                        # v9: masked — EncryptedCharField decrypts transparently,
                        # but we only write last 4 digits to the CSV file.
                        _mask(str(item.account_number or "")),
                        item.gross_amount, item.fee_amount, item.net_amount,
                        item.gateway_reference, item.retry_count,
                        item.processed_at.isoformat() if item.processed_at else "",
                        item.created_at.isoformat() if item.created_at else "",
                    ])
                yield output.getvalue()
                output.seek(0)
                output.truncate(0)
                offset += batch_size

        filename = f"payout_items_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
        response = StreamingHttpResponse(stream_csv(), content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

# ---------------------------------------------------------------------------
# BulkProcessLog ViewSet
# ---------------------------------------------------------------------------

class BulkProcessLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only access to BulkProcessLog records.

    Endpoints:
      GET  /logs/                — list (paginated, filtered)
      GET  /logs/{id}/           — retrieve
      GET  /logs/{id}/detail/    — same as retrieve (alias for compatibility)
      GET  /logs/by-task/        — lookup by Celery task_id
    """
    serializer_class   = BulkProcessLogSerializer
    permission_classes = [IsStaffOrSuperuser]
    throttle_classes   = [PayoutBurstThrottle, PayoutSustainedThrottle]
    filterset_class    = BulkProcessLogFilter
    pagination_class   = PayoutQueuePagination
    filter_backends    = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields      = ["task_id", "status"]
    ordering_fields    = ["created_at", "duration_ms", "items_attempted"]
    ordering           = ["-created_at"]

    def get_queryset(self):
        qs = BulkProcessLog.objects.select_related("batch", "triggered_by")
        return _tenant_filter(qs, self.request)

    @action(detail=True, methods=["get"], url_path="detail")
    def detail_view(self, request: Request, pk: Any = None) -> Response:
        """GET /logs/{id}/detail/"""
        try:
            log = services.get_process_log(pk)
        except Exception as exc:
            return _err(exc, status.HTTP_404_NOT_FOUND)
        return Response(BulkProcessLogSerializer(log).data)

    @action(detail=False, methods=["get"], url_path="by-task")
    def by_task(self, request: Request) -> Response:
        """GET /logs/by-task/?task_id=<celery_task_id>"""
        task_id = request.query_params.get("task_id", "").strip()
        if not task_id:
            return Response(
                {"detail": "task_id query param is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        logs = BulkProcessLog.objects.by_task(task_id)
        return Response(BulkProcessLogSerializer(logs, many=True).data)

# ---------------------------------------------------------------------------
# WithdrawalPriority ViewSet
# ---------------------------------------------------------------------------

class WithdrawalPriorityViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only base + priority management actions.

    Endpoints:
      GET  /priorities/                     — list
      GET  /priorities/{id}/                — retrieve
      POST /priorities/set-priority/        — assign or escalate priority
      POST /priorities/{id}/deactivate/     — deactivate a priority record
      GET  /priorities/active-for-user/     — active priority for a user
    """
    serializer_class   = WithdrawalPrioritySerializer
    permission_classes = [IsStaffOrSuperuser]
    throttle_classes   = [PayoutBurstThrottle, PayoutSustainedThrottle]
    filter_backends    = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    ordering_fields    = ["created_at", "priority"]
    ordering           = ["-created_at"]

    def get_queryset(self):
        qs = WithdrawalPriority.objects.select_related(
            "user", "payout_item", "assigned_by"
        )
        return _tenant_filter(qs, self.request)

    @action(detail=False, methods=["post"], url_path="set-priority")
    def set_priority(self, request: Request) -> Response:
        """POST /priorities/set-priority/"""
        serializer = SetWithdrawalPrioritySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        data = serializer.validated_data
        try:
            wp = services.set_withdrawal_priority(
                user_id=data["user_id"],
                priority=data["priority"],
                reason=data["reason"],
                payout_item_id=data.get("payout_item_id"),
                assigned_by_id=request.user.pk,
                reason_note=data.get("reason_note", ""),
                expires_at=data.get("expires_at"),
            )
        except PayoutQueueError as exc:
            return _err(exc)
        return Response(
            WithdrawalPrioritySerializer(wp).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="deactivate")
    def deactivate(self, request: Request, pk: Any = None) -> Response:
        """POST /priorities/{id}/deactivate/"""
        try:
            wp = services.deactivate_withdrawal_priority(
                priority_id=pk,
                actor_id=request.user.pk,
            )
        except PayoutQueueError as exc:
            return _err(exc, status.HTTP_404_NOT_FOUND)
        return Response(WithdrawalPrioritySerializer(wp).data)

    @action(detail=False, methods=["get"], url_path="active-for-user")
    def active_for_user(self, request: Request) -> Response:
        """GET /priorities/active-for-user/?user_id=<id>"""
        user_id = request.query_params.get("user_id")
        if not user_id:
            return Response(
                {"detail": "user_id query param is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        wp = WithdrawalPriority.objects.get_active_for_user(user_id)
        if wp is None:
            return Response(
                {"detail": "No active priority found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(WithdrawalPrioritySerializer(wp).data)
