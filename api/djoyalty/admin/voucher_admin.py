# api/djoyalty/admin/voucher_admin.py
from django.contrib import admin
from django.utils.html import format_html
from ..models.redemption import Voucher, GiftCard

@admin.register(Voucher)
class VoucherAdmin(admin.ModelAdmin):
    list_display = ['code_display', 'customer', 'voucher_type', 'discount_value', 'status_badge', 'expires_at', 'created_at']
    list_filter = ['status', 'voucher_type']
    search_fields = ['code', 'customer__code']
    readonly_fields = ['created_at']

    def code_display(self, obj):
        return format_html('<code style="background:#f3f4f6;padding:2px 6px;border-radius:4px;">{}</code>', obj.code)
    code_display.short_description = 'Code'

    def status_badge(self, obj):
        colors = {'active': ('#dcfce7', '#166534'), 'used': ('#dbeafe', '#1e40af'), 'expired': ('#fee2e2', '#991b1b'), 'cancelled': ('#f3f4f6', '#374151')}
        bg, fg = colors.get(obj.status, ('#f3f4f6', '#374151'))
        return format_html('<span style="background:{};color:{};padding:2px 8px;border-radius:8px;font-size:11px;">{}</span>', bg, fg, obj.status.title())
    status_badge.short_description = 'Status'

@admin.register(GiftCard)
class GiftCardAdmin(admin.ModelAdmin):
    list_display = ['code', 'initial_value', 'remaining_value', 'status', 'issued_to', 'expires_at']
    list_filter = ['status']
    search_fields = ['code', 'issued_to__code']
