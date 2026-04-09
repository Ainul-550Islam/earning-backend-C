# api/djoyalty/admin/partner_admin.py
from django.contrib import admin
from django.utils.html import format_html
from ..models.campaigns import PartnerMerchant

@admin.register(PartnerMerchant)
class PartnerMerchantAdmin(admin.ModelAdmin):
    list_display = ['name', 'earn_rate', 'burn_rate', 'active_badge', 'last_sync_at', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name']
    readonly_fields = ['created_at', 'last_sync_at']

    def active_badge(self, obj):
        if obj.is_active:
            return format_html('<span style="background:#dcfce7;color:#166534;padding:2px 8px;border-radius:8px;font-size:11px;">🟢 Active</span>')
        return format_html('<span style="background:#fee2e2;color:#991b1b;padding:2px 8px;border-radius:8px;font-size:11px;">🔴 Inactive</span>')
    active_badge.short_description = 'Status'
