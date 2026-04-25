# api/payment_gateways/refunds/admin.py
# FILE 63 of 257

from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import RefundRequest, RefundPolicy, RefundAuditLog


class RefundAuditLogInline(admin.TabularInline):
    model          = RefundAuditLog
    extra          = 0
    readonly_fields = ('previous_status', 'new_status', 'changed_by', 'note', 'created_at')
    can_delete     = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(RefundRequest)
class RefundRequestAdmin(admin.ModelAdmin):
    list_display   = ('reference_id', 'gateway_badge', 'user', 'amount', 'status_badge', 'reason', 'created_at')
    list_filter    = ('status', 'gateway', 'reason')
    search_fields  = ('reference_id', 'gateway_refund_id', 'user__email', 'user__username')
    readonly_fields = (
        'reference_id', 'gateway_refund_id', 'original_transaction',
        'user', 'gateway', 'amount', 'completed_at', 'failed_at', 'created_at',
    )
    ordering       = ('-created_at',)
    inlines        = [RefundAuditLogInline]
    actions        = ['mark_completed', 'mark_failed']

    fieldsets = (
        ('Refund Info', {
            'fields': ('reference_id', 'gateway', 'gateway_refund_id', 'original_transaction'),
        }),
        ('User & Amount', {
            'fields': ('user', 'amount', 'reason'),
        }),
        ('Status', {
            'fields': ('status', 'initiated_by', 'completed_at', 'failed_at'),
        }),
        ('Notes & Metadata', {
            'fields': ('notes', 'metadata'),
            'classes': ('collapse',),
        }),
    )

    def status_badge(self, obj):
        colors = {
            'pending':    '#F59E0B',
            'processing': '#3B82F6',
            'completed':  '#10B981',
            'failed':     '#EF4444',
            'cancelled':  '#6B7280',
        }
        color = colors.get(obj.status, '#6B7280')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 10px;border-radius:12px;font-size:11px">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'

    def gateway_badge(self, obj):
        colors = {
            'bkash': '#E2136E', 'nagad': '#F7941D', 'sslcommerz': '#0072BC',
            'amarpay': '#00AEEF', 'upay': '#005BAA', 'shurjopay': '#6A0DAD',
            'stripe': '#635BFF', 'paypal': '#003087',
        }
        color = colors.get(obj.gateway, '#6B7280')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:8px;font-size:11px">{}</span>',
            color, obj.get_gateway_display()
        )
    gateway_badge.short_description = 'Gateway'

    @admin.action(description='Mark selected refunds as completed')
    def mark_completed(self, request, queryset):
        queryset.filter(status__in=('pending', 'processing')).update(
            status='completed', completed_at=timezone.now()
        )

    @admin.action(description='Mark selected refunds as failed')
    def mark_failed(self, request, queryset):
        queryset.filter(status__in=('pending', 'processing')).update(
            status='failed', failed_at=timezone.now()
        )


@admin.register(RefundPolicy)
class RefundPolicyAdmin(admin.ModelAdmin):
    list_display  = ('gateway', 'auto_approve', 'max_refund_days', 'max_refund_amount', 'allow_partial_refund', 'is_active')
    list_filter   = ('gateway', 'auto_approve', 'is_active')
    list_editable = ('auto_approve', 'is_active')


@admin.register(RefundAuditLog)
class RefundAuditLogAdmin(admin.ModelAdmin):
    list_display  = ('refund_request', 'previous_status', 'new_status', 'changed_by', 'created_at')
    list_filter   = ('new_status', 'previous_status')
    readonly_fields = '__all__'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
