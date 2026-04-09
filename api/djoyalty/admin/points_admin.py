# api/djoyalty/admin/points_admin.py
from django.contrib import admin
from django.utils.html import format_html
from ..models.points import LoyaltyPoints, PointsLedger, PointsAdjustment

@admin.register(LoyaltyPoints)
class LoyaltyPointsAdmin(admin.ModelAdmin):
    list_display = ['customer', 'balance_display', 'lifetime_earned', 'lifetime_redeemed', 'lifetime_expired', 'updated_at']
    search_fields = ['customer__code', 'customer__email']
    readonly_fields = ['balance', 'lifetime_earned', 'lifetime_redeemed', 'lifetime_expired', 'updated_at', 'created_at']
    ordering = ['-balance']

    def balance_display(self, obj):
        return format_html('<span style="color:#7c3aed;font-weight:700;font-size:14px;">⭐ {}</span>', obj.balance)
    balance_display.short_description = 'Balance'

@admin.register(PointsLedger)
class PointsLedgerAdmin(admin.ModelAdmin):
    list_display = ['id', 'customer', 'txn_type_badge', 'source', 'points', 'balance_after', 'expires_at', 'created_at']
    list_filter = ['txn_type', 'source']
    search_fields = ['customer__code', 'reference_id']
    readonly_fields = ['created_at']
    ordering = ['-created_at']
    date_hierarchy = 'created_at'

    def txn_type_badge(self, obj):
        if obj.txn_type == 'credit':
            return format_html('<span style="background:#dcfce7;color:#166534;padding:2px 8px;border-radius:8px;font-size:11px;">➕ Credit</span>')
        return format_html('<span style="background:#fee2e2;color:#991b1b;padding:2px 8px;border-radius:8px;font-size:11px;">➖ Debit</span>')
    txn_type_badge.short_description = 'Type'

@admin.register(PointsAdjustment)
class PointsAdjustmentAdmin(admin.ModelAdmin):
    list_display = ['customer', 'points', 'reason', 'adjusted_by', 'created_at']
    search_fields = ['customer__code', 'reason', 'adjusted_by']
    readonly_fields = ['created_at']
