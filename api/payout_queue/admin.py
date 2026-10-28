"""
payout_queue/admin.py  ← v9 PRODUCTION FIX

CHANGES v9 (Remaining Gap #1 — PII in Admin):

  ① PayoutItemAdmin.search_fields removed "account_number"

     Before:  search_fields = ["account_number", "gateway_reference", ...]
              Django admin uses icontains which runs SQL LIKE on the DB column.
              After v8 encryption the column stores ciphertext — LIKE on ciphertext
              never matches anything, making the search silently return no results.

     After:   Custom get_search_results() override hashes the search term and
              filters by account_number_hash (exact match) when the term looks
              like a phone number. All other terms still search gateway_reference
              and internal_reference normally.

  ② masked_account_number column added to PayoutItemAdmin and PayoutItemInline

     Before:  list_display and inline showed raw account_number.
              After v8 the field decrypts transparently so the value was visible
              in plaintext to any admin user — a PII risk.

     After:   masked_account_number() shows only the last 4 characters
              (e.g. "01700123456" → "•••••••3456").
              Full account number is not shown anywhere in the list view.
              Detail view readonly_fields shows account_number (staff-only page,
              acceptable for support workflows — protected by IsStaffOrSuperuser).

  ③ account_number removed from PayoutItemInline.fields

     Inline now shows masked_account_number() instead.

v2 logic preserved: cancel_payout_batch via services wrapper, all admin actions.
"""
from __future__ import annotations

import logging
from django.contrib import admin, messages
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import PayoutBatch, PayoutItem, WithdrawalPriority, BulkProcessLog
from . import services

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helper: mask account number for safe display
# ---------------------------------------------------------------------------

def _mask_account(value: str, visible: int = 4) -> str:
    """
    Return a masked version showing only the last `visible` characters.
    "01700123456" → "•••••••3456"
    Empty/short values returned as-is.
    """
    if not value or len(value) <= visible:
        return value or "—"
    return "•" * (len(value) - visible) + value[-visible:]

# ---------------------------------------------------------------------------
# Inlines
# ---------------------------------------------------------------------------

class PayoutItemInline(admin.TabularInline):
    model = PayoutItem
    extra = 0
    readonly_fields = [
        "id", "masked_account_number_display", "status", "fee_amount",
        "net_amount", "gateway_reference", "retry_count", "error_code",
        "processed_at",
    ]
    # v9: account_number replaced with masked display to avoid PII exposure in inline
    fields = [
        "user", "masked_account_number_display", "gross_amount", "fee_amount",
        "net_amount", "status", "gateway_reference", "retry_count", "error_code",
    ]
    can_delete = False

    @admin.display(description=_("Account Number"))
    def masked_account_number_display(self, obj) -> str:
        return _mask_account(str(obj.account_number or ""))

class BulkProcessLogInline(admin.TabularInline):
    model         = BulkProcessLog
    extra         = 0
    readonly_fields = [
        "status", "task_id", "items_attempted", "items_succeeded",
        "items_failed", "duration_ms", "error_summary", "created_at",
    ]
    can_delete = False

# ---------------------------------------------------------------------------
# PayoutBatchAdmin
# ---------------------------------------------------------------------------

@admin.register(PayoutBatch)
class PayoutBatchAdmin(admin.ModelAdmin):
    list_display = [
        "name", "gateway", "status", "priority", "item_count",
        "success_count", "failure_count", "total_amount", "net_amount",
        "scheduled_at", "created_at",
    ]
    list_filter    = ["status", "gateway", "priority", "created_at"]
    search_fields  = ["name", "id"]
    ordering       = ["-created_at"]
    date_hierarchy = "created_at"
    list_per_page  = 50
    readonly_fields = [
        "id", "status", "total_amount", "total_fee", "net_amount",
        "item_count", "success_count", "failure_count",
        "locked_at", "locked_by", "started_at", "completed_at",
        "created_at", "updated_at",
    ]
    inlines = [PayoutItemInline, BulkProcessLogInline]
    actions = [
        "process_selected_batches_async",
        "process_selected_batches_sync",
        "cancel_selected_batches",
    ]

    @admin.action(description=_("Process selected batches (async via Celery)"))
    def process_selected_batches_async(self, request, queryset):
        for batch in queryset:
            try:
                from .tasks import process_batch_async
                task = process_batch_async.delay(str(batch.id), actor_id=str(request.user.pk))
                self.message_user(request, _(f"Queued '{batch.name}' (task={task.id})"))
            except Exception as exc:
                self.message_user(request, _(f"Error queuing '{batch.name}': {exc}"), level=messages.ERROR)

    @admin.action(description=_("Process selected batches (sync, blocking)"))
    def process_selected_batches_sync(self, request, queryset):
        import uuid as _uuid
        for batch in queryset:
            worker_id = f"admin-sync-{str(_uuid.uuid4())[:8]}"
            try:
                result = services.process_batch(
                    batch_id=batch.pk, worker_id=worker_id, actor_id=request.user.pk,
                )
                self.message_user(request, _(
                    f"'{batch.name}' done: status={result['status']} "
                    f"success={result['success_count']} failed={result['failure_count']} "
                    f"({result['duration_ms']}ms)"
                ))
            except Exception as exc:
                self.message_user(request, _(f"Error processing '{batch.name}': {exc}"), level=messages.ERROR)

    @admin.action(description=_("Cancel selected batches"))
    def cancel_selected_batches(self, request, queryset):
        """FIX v2: delegates to services.cancel_payout_batch() — not direct transition."""
        cancelled = 0
        errors    = 0
        for batch in queryset:
            try:
                services.cancel_payout_batch(
                    batch_id=batch.pk, actor_id=request.user.pk,
                    note=f"Cancelled via admin by {request.user}",
                )
                cancelled += 1
            except Exception as exc:
                self.message_user(request, _(f"Cannot cancel '{batch.name}': {exc}"), level=messages.WARNING)
                errors += 1
        if cancelled:
            self.message_user(request, _(f"Cancelled {cancelled} batch(es). {errors} skipped."))

# ---------------------------------------------------------------------------
# PayoutItemAdmin
# ---------------------------------------------------------------------------

@admin.register(PayoutItem)
class PayoutItemAdmin(admin.ModelAdmin):
    list_display = [
        "id", "batch", "user", "gateway",
        # v9: masked column instead of raw account_number
        "masked_account_number",
        "status", "gross_amount", "fee_amount", "net_amount",
        "retry_count", "gateway_reference", "processed_at",
    ]
    list_filter    = ["status", "gateway", "created_at"]
    # v9: account_number removed — icontains on encrypted field never matches.
    # Hash-based search handled in get_search_results() below.
    search_fields  = ["gateway_reference", "internal_reference"]
    ordering       = ["-created_at"]
    date_hierarchy = "created_at"
    list_per_page  = 100
    readonly_fields = [
        "id", "status", "account_number", "account_number_hash",
        "fee_amount", "net_amount", "gateway_reference",
        "internal_reference", "retry_count", "next_retry_at",
        "error_code", "error_message", "gateway_response",
        "processed_at", "created_at", "updated_at",
    ]
    raw_id_fields = ["batch", "user"]
    actions = ["cancel_selected_items", "skip_selected_items"]

    @admin.display(description=_("Account Number"), ordering="account_number_hash")
    def masked_account_number(self, obj) -> str:
        """
        v9: Shows last 4 characters only to protect PII in list view.
        Staff can see the full account_number in the detail page (readonly field).
        """
        return _mask_account(str(obj.account_number or ""))

    def get_search_results(self, request, queryset, search_term):
        """
        v9: Custom search to support account number lookup after encryption.

        Django admin's default search uses icontains on DB columns.
        After v8 encryption, account_number stores ciphertext — icontains
        never matches plaintext searches.

        Fix: if the search term looks like a phone number (digits only, 8-13 chars),
        hash it and filter by account_number_hash (exact match).
        Otherwise, delegate to the default search (gateway_reference, internal_reference).
        """
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)
        if search_term and search_term.strip().lstrip("+").isdigit() and 8 <= len(search_term.strip()) <= 16:
            try:
                from .utils.encryption import compute_account_hash
                acct_hash = compute_account_hash(search_term.strip())
                hash_qs   = self.model.objects.filter(account_number_hash=acct_hash)
                # Merge with existing queryset (OR logic)
                from django.db.models import Q
                queryset = (queryset | hash_qs).distinct()
                use_distinct = True
            except Exception as exc:
                logger.warning("PayoutItemAdmin.get_search_results: hash lookup failed: %s", exc)
        return queryset, use_distinct

    @admin.action(description=_("Cancel selected payout items"))
    def cancel_selected_items(self, request, queryset):
        cancelled = 0
        skipped   = 0
        for item in queryset:
            try:
                services.cancel_payout_item(
                    item_id=item.pk, reason=f"Cancelled via admin by {request.user}",
                    actor_id=request.user.pk,
                )
                cancelled += 1
            except Exception as exc:
                logger.warning("Admin cancel item %s: %s", item.pk, exc)
                skipped += 1
        self.message_user(request, _(f"Cancelled {cancelled} item(s). {skipped} skipped (already terminal)."))

    @admin.action(description=_("Skip selected payout items (no retry)"))
    def skip_selected_items(self, request, queryset):
        skipped = 0
        errors  = 0
        for item in queryset:
            try:
                services.skip_payout_item(
                    item_id=item.pk, reason=f"Skipped via admin by {request.user}",
                    actor_id=request.user.pk,
                )
                skipped += 1
            except Exception as exc:
                logger.warning("Admin skip item %s: %s", item.pk, exc)
                errors += 1
        self.message_user(request, _(f"Skipped {skipped} item(s). {errors} failed."))

# ---------------------------------------------------------------------------
# WithdrawalPriorityAdmin
# ---------------------------------------------------------------------------

@admin.register(WithdrawalPriority)
class WithdrawalPriorityAdmin(admin.ModelAdmin):
    list_display    = ["user", "priority", "reason", "is_active", "expires_at", "created_at"]
    list_filter     = ["priority", "reason", "is_active"]
    search_fields   = ["user__username"]
    readonly_fields = [f.name for f in WithdrawalPriority._meta.fields]
    actions         = ["set_normal_priority", "deactivate_selected"]

    @admin.action(description=_("Reset selected priorities to NORMAL"))
    def set_normal_priority(self, request, queryset):
        from .choices import PriorityLevel, WithdrawalPriorityReason
        count = 0
        for wp in queryset.filter(is_active=True):
            try:
                services.set_withdrawal_priority(
                    user_id=wp.user_id, priority=PriorityLevel.NORMAL,
                    reason=WithdrawalPriorityReason.ADMIN_OVERRIDE,
                    assigned_by_id=request.user.pk,
                    reason_note=f"Reset to NORMAL by admin {request.user}",
                )
                count += 1
            except Exception as exc:
                logger.warning("Admin set_normal_priority user=%s: %s", wp.user_id, exc)
        self.message_user(request, _(f"Reset {count} priority record(s) to NORMAL."))

    @admin.action(description=_("Deactivate selected priorities"))
    def deactivate_selected(self, request, queryset):
        count = 0
        for wp in queryset.filter(is_active=True):
            try:
                services.deactivate_withdrawal_priority(priority_id=wp.pk, actor_id=request.user.pk)
                count += 1
            except Exception as exc:
                logger.warning("Admin deactivate priority %s: %s", wp.pk, exc)
        self.message_user(request, _(f"Deactivated {count} priority record(s)."))

# ---------------------------------------------------------------------------
# BulkProcessLogAdmin
# ---------------------------------------------------------------------------

@admin.register(BulkProcessLog)
class BulkProcessLogAdmin(admin.ModelAdmin):
    list_display    = ["batch", "status", "task_id", "items_attempted", "items_succeeded", "items_failed", "duration_ms", "created_at"]
    list_filter     = ["status", "created_at"]
    search_fields   = ["task_id", "batch__name"]
    ordering        = ["-created_at"]
    date_hierarchy  = "created_at"
    list_per_page   = 100
    readonly_fields = [f.name for f in BulkProcessLog._meta.fields]

# ---------------------------------------------------------------------------
# Force-register helper
# ---------------------------------------------------------------------------

from django.apps import apps as _apps

try:
    _app_config = _apps.get_app_config("payout_queue")
    for _model in _app_config.get_models():
        try:
            admin.site.register(_model)
        except admin.sites.AlreadyRegistered:
            pass
except Exception as _e:
    logger.warning("payout_queue admin auto-register: %s", _e)

def _force_register_payout_queue():
    """Register payout_queue models on a custom admin site if one exists."""
    try:
        modern_site = None
        for mod_path in ("api.payout_queue.admin_panel.admin", "api.admin_panel.admin", "core.admin_panel.admin"):
            try:
                import importlib
                mod         = importlib.import_module(mod_path)
                modern_site = getattr(mod, "admin_site", None)
                if modern_site is not None:
                    break
            except ImportError:
                continue
        if modern_site is None:
            return
        pairs = [
            (PayoutBatch,        PayoutBatchAdmin),
            (PayoutItem,         PayoutItemAdmin),
            (WithdrawalPriority, WithdrawalPriorityAdmin),
            (BulkProcessLog,     BulkProcessLogAdmin),
        ]
        registered = 0
        for model, model_admin_cls in pairs:
            try:
                if model not in modern_site._registry:
                    modern_site.register(model, model_admin_cls)
                    registered += 1
            except Exception:
                pass
        logger.info("[OK] payout_queue registered %d models on custom admin site", registered)
    except Exception as exc:
        logger.debug("payout_queue _force_register_payout_queue: %s", exc)
