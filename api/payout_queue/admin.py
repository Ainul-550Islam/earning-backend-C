"""Payout Queue Admin"""
from __future__ import annotations
import logging
from django.contrib import admin, messages
from django.utils.translation import gettext_lazy as _
from .models import PayoutBatch, PayoutItem, WithdrawalPriority, BulkProcessLog
from . import services

logger = logging.getLogger(__name__)


class PayoutItemInline(admin.TabularInline):
    model = PayoutItem
    extra = 0
    readonly_fields = ["id", "status", "fee_amount", "net_amount", "gateway_reference",
                       "retry_count", "error_code", "processed_at"]
    fields = ["user", "account_number", "gross_amount", "fee_amount", "net_amount",
              "status", "gateway_reference", "retry_count", "error_code"]
    can_delete = False


class BulkProcessLogInline(admin.TabularInline):
    model = BulkProcessLog
    extra = 0
    readonly_fields = ["status", "task_id", "items_attempted", "items_succeeded",
                       "items_failed", "duration_ms", "created_at"]
    can_delete = False


@admin.register(PayoutBatch)
class PayoutBatchAdmin(admin.ModelAdmin):
    list_display = [
        "name", "gateway", "status", "priority", "item_count",
        "success_count", "failure_count", "total_amount", "net_amount",
        "scheduled_at", "created_at",
    ]
    list_filter = ["status", "gateway", "priority"]
    search_fields = ["name", "id"]
    readonly_fields = [
        "id", "status", "total_amount", "total_fee", "net_amount",
        "item_count", "success_count", "failure_count",
        "locked_at", "locked_by", "started_at", "completed_at",
        "created_at", "updated_at",
    ]
    inlines = [PayoutItemInline, BulkProcessLogInline]
    actions = ["process_selected_batches"]

    @admin.action(description=_("Process selected batches (async)"))
    def process_selected_batches(self, request, queryset):
        for batch in queryset:
            try:
                from .tasks import process_batch_async
                task = process_batch_async.delay(str(batch.id), actor_id=str(request.user.pk))
                self.message_user(
                    request, _(f"Queued '{batch.name}' (task={task.id})")
                )
            except Exception as exc:
                self.message_user(
                    request, _(f"Error for '{batch.name}': {exc}"),
                    level=messages.ERROR,
                )


@admin.register(PayoutItem)
class PayoutItemAdmin(admin.ModelAdmin):
    list_display = [
        "id", "batch", "user", "gateway", "status",
        "gross_amount", "fee_amount", "net_amount",
        "retry_count", "gateway_reference", "processed_at",
    ]
    list_filter = ["status", "gateway"]
    search_fields = ["account_number", "gateway_reference", "internal_reference"]
    readonly_fields = [
        "id", "status", "fee_amount", "net_amount", "gateway_reference",
        "internal_reference", "retry_count", "next_retry_at",
        "error_code", "error_message", "gateway_response",
        "processed_at", "created_at", "updated_at",
    ]
    raw_id_fields = ["batch", "user"]


@admin.register(WithdrawalPriority)
class WithdrawalPriorityAdmin(admin.ModelAdmin):
    list_display = ["user", "priority", "reason", "is_active", "expires_at", "created_at"]
    list_filter = ["priority", "reason", "is_active"]
    search_fields = ["user__username"]
    readonly_fields = [f.name for f in WithdrawalPriority._meta.fields]


@admin.register(BulkProcessLog)
class BulkProcessLogAdmin(admin.ModelAdmin):
    list_display = [
        "batch", "status", "task_id", "items_attempted",
        "items_succeeded", "items_failed", "duration_ms", "created_at",
    ]
    list_filter = ["status"]
    search_fields = ["task_id", "batch__name"]
    readonly_fields = [f.name for f in BulkProcessLog._meta.fields]


# Force register all models
from django.apps import apps as _apps
_app_label = __name__.split(chr(46))[1]
for _model in _apps.get_app_config(_app_label).get_models():
    try:
        admin.site.register(_model)
    except admin.sites.AlreadyRegistered:
        pass
