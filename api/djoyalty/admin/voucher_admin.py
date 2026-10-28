# api/djoyalty/admin/voucher_admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from ..models.redemption import Voucher, VoucherRedemption, GiftCard


class VoucherRedemptionInline(admin.TabularInline):
    model = VoucherRedemption
    extra = 0
    readonly_fields = ['customer', 'order_reference', 'discount_applied', 'used_at']
    can_delete = False


@admin.register(Voucher)
class VoucherAdmin(admin.ModelAdmin):
    list_display = ['code', 'customer', 'voucher_type', 'discount_value', 'status_badge', 'expires_at', 'created_at']
    list_filter = ['status', 'voucher_type', 'created_at']
    search_fields = ['code', 'customer__code', 'customer__email', 'merchant']
    readonly_fields = ['code', 'created_at', 'updated_at', 'used_at']
    inlines = [VoucherRedemptionInline]
    fieldsets = [
        ('Voucher Info', {'fields': ['code', 'customer', 'voucher_type', 'discount_value', 'points_cost']}),
        ('Status & Validity', {'fields': ['status', 'expires_at', 'is_used', 'used_at']}),
        ('Details', {'fields': ['merchant', 'minimum_order', 'terms']}),
        ('Timestamps', {'fields': ['created_at', 'updated_at']}),
    ]

    def status_badge(self, obj):
        colors = {'active': '#10b981', 'used': '#3b82f6', 'expired': '#ef4444', 'cancelled': '#6b7280'}
        color = colors.get(obj.status, '#6b7280')
        return format_html('<span style="background:{};color:#fff;padding:2px 8px;border-radius:4px;">{}</span>', color, obj.status)
    status_badge.short_description = 'Status'

    actions = ['expire_selected']

    def expire_selected(self, request, queryset):
        count = queryset.filter(status='active').update(status='expired')
        self.message_user(request, f'{count} vouchers expired.')
    expire_selected.short_description = 'Expire selected active vouchers'


@admin.register(VoucherRedemption)
class VoucherRedemptionAdmin(admin.ModelAdmin):
    list_display = ['voucher', 'customer', 'discount_applied', 'order_reference', 'used_at']
    list_filter = ['used_at']
    search_fields = ['voucher__code', 'customer__code', 'order_reference']
    readonly_fields = ['voucher', 'customer', 'discount_applied', 'used_at']


@admin.register(GiftCard)
class GiftCardAdmin(admin.ModelAdmin):
    list_display = ['code', 'issued_to', 'initial_value', 'remaining_value', 'status_badge', 'expires_at', 'created_at']
    list_filter = ['status', 'currency', 'created_at']
    search_fields = ['code', 'issued_to__code']
    readonly_fields = ['code', 'created_at', 'updated_at', 'used_at']
    fieldsets = [
        ('Gift Card Info', {'fields': ['code', 'issued_to', 'initial_value', 'remaining_value', 'currency']}),
        ('Status', {'fields': ['status', 'is_active', 'expires_at', 'used_at']}),
        ('Admin', {'fields': ['issued_by', 'note']}),
        ('Timestamps', {'fields': ['created_at', 'updated_at']}),
    ]

    def status_badge(self, obj):
        colors = {'active': '#10b981', 'used': '#3b82f6', 'expired': '#ef4444', 'cancelled': '#6b7280'}
        color = colors.get(obj.status, '#6b7280')
        return format_html('<span style="background:{};color:#fff;padding:2px 8px;border-radius:4px;">{}</span>', color, obj.status)
    status_badge.short_description = 'Status'

    actions = ['issue_new_gift_card']

    def issue_new_gift_card(self, request, queryset):
        self.message_user(request, 'Use the API or management command to issue gift cards.')
    issue_new_gift_card.short_description = 'Issue new gift cards (use API)'
