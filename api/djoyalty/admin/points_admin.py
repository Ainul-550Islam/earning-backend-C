# api/djoyalty/admin/points_admin.py
from django.contrib import admin
from django.utils.html import format_html
from ..models.points import (
    LoyaltyPoints, PointsLedger, PointsExpiry,
    PointsAdjustment, PointsTransfer, PointsRate,
)


@admin.register(LoyaltyPoints)
class LoyaltyPointsAdmin(admin.ModelAdmin):
    list_display = [
        'customer_code', 'balance', 'lifetime_earned',
        'lifetime_redeemed', 'lifetime_expired',
        'pending_balance', 'frozen_balance', 'updated_at',
    ]
    list_filter = ['tenant']
    search_fields = ['customer__code', 'customer__email']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-balance']
    list_per_page = 50

    @admin.display(description='Customer Code', ordering='customer__code')
    def customer_code(self, obj):
        return obj.customer.code


@admin.register(PointsLedger)
class PointsLedgerAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'customer_code', 'txn_type_display', 'source',
        'points', 'balance_after', 'description_short',
        'expires_at', 'created_at',
    ]
    list_filter = ['txn_type', 'source', 'tenant', 'is_reversed']
    search_fields = ['customer__code', 'reference_id', 'description']
    readonly_fields = ['created_at']
    ordering = ['-created_at']
    list_per_page = 100
    date_hierarchy = 'created_at'

    @admin.display(description='Customer')
    def customer_code(self, obj):
        return obj.customer.code

    @admin.display(description='Type')
    def txn_type_display(self, obj):
        color = 'green' if obj.txn_type == 'credit' else 'red'
        icon = '▲' if obj.txn_type == 'credit' else '▼'
        return format_html('<span style="color:{}">{} {}</span>', color, icon, obj.txn_type)

    @admin.display(description='Description')
    def description_short(self, obj):
        if obj.description:
            return obj.description[:60] + ('...' if len(obj.description) > 60 else '')
        return '--'


@admin.register(PointsExpiry)
class PointsExpiryAdmin(admin.ModelAdmin):
    list_display = [
        'customer_code', 'points', 'earned_at', 'expires_at',
        'is_processed', 'warning_sent', 'processed_at',
    ]
    list_filter = ['is_processed', 'warning_sent', 'tenant']
    search_fields = ['customer__code']
    readonly_fields = ['created_at', 'processed_at']
    ordering = ['expires_at']
    date_hierarchy = 'expires_at'

    @admin.display(description='Customer')
    def customer_code(self, obj):
        return obj.customer.code

    actions = ['mark_as_processed']

    @admin.action(description='Mark selected as processed')
    def mark_as_processed(self, request, queryset):
        from django.utils import timezone
        count = queryset.filter(is_processed=False).update(
            is_processed=True, processed_at=timezone.now()
        )
        self.message_user(request, f'{count} expiry record(s) marked as processed.')


@admin.register(PointsAdjustment)
class PointsAdjustmentAdmin(admin.ModelAdmin):
    list_display = [
        'customer_code', 'points_display', 'reason_short',
        'adjusted_by', 'created_at',
    ]
    list_filter = ['tenant']
    search_fields = ['customer__code', 'reason', 'adjusted_by']
    readonly_fields = ['created_at']
    ordering = ['-created_at']

    @admin.display(description='Customer')
    def customer_code(self, obj):
        return obj.customer.code

    @admin.display(description='Points')
    def points_display(self, obj):
        color = 'green' if obj.points > 0 else 'red'
        sign = '+' if obj.points > 0 else ''
        return format_html('<b style="color:{}">{}{}</b>', color, sign, obj.points)

    @admin.display(description='Reason')
    def reason_short(self, obj):
        return obj.reason[:60] + ('...' if len(obj.reason) > 60 else '')


@admin.register(PointsTransfer)
class PointsTransferAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'from_customer_code', 'to_customer_code',
        'points', 'fee', 'status', 'created_at',
    ]
    list_filter = ['status', 'tenant']
    search_fields = ['from_customer__code', 'to_customer__code', 'reference']
    readonly_fields = ['created_at', 'completed_at']
    ordering = ['-created_at']

    @admin.display(description='From')
    def from_customer_code(self, obj):
        return obj.from_customer.code

    @admin.display(description='To')
    def to_customer_code(self, obj):
        return obj.to_customer.code


@admin.register(PointsRate)
class PointsRateAdmin(admin.ModelAdmin):
    list_display = ['tenant', 'earn_rate', 'point_value', 'currency', 'effective_date', 'is_active']
    list_filter = ['is_active', 'currency', 'tenant']
    readonly_fields = ['created_at']
    ordering = ['-effective_date']
