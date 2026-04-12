# admin/currency_admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from ..models.core import Currency
from ..models.currency import ExchangeRate, ExchangeRateProvider, CurrencyFormat, CurrencyConversionLog

@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    list_display = ['code_badge', 'symbol', 'name', 'exchange_rate', 'rate_age', 'is_default_badge', 'active_badge']
    list_filter = ['is_active', 'is_default']
    search_fields = ['code', 'name', 'symbol']
    readonly_fields = ['exchange_rate_updated_at', 'created_at', 'updated_at']

    def code_badge(self, obj):
        return format_html('<span style="background:#28a745;color:white;padding:2px 8px;border-radius:8px;font-size:12px;font-weight:bold;">{}</span>', obj.code)
    code_badge.short_description = _('Code')

    def rate_age(self, obj):
        if not obj.exchange_rate_updated_at:
            return format_html('<span style="color:#dc3545;">Never updated</span>')
        from django.utils import timezone
        age = timezone.now() - obj.exchange_rate_updated_at
        hours = age.total_seconds() / 3600
        color = '#28a745' if hours < 24 else ('#ffc107' if hours < 72 else '#dc3545')
        return format_html('<span style="color:{};">{:.0f}h ago</span>', color, hours)
    rate_age.short_description = _('Rate Age')

    def is_default_badge(self, obj):
        if obj.is_default:
            return format_html('<span style="background:#ffc107;color:#212529;padding:2px 6px;border-radius:10px;font-size:11px;">★ Default</span>')
        return ''
    is_default_badge.short_description = _('Default')

    def active_badge(self, obj):
        if obj.is_active:
            return format_html('<span style="color:#28a745;">✓</span>')
        return format_html('<span style="color:#dc3545;">✗</span>')
    active_badge.short_description = _('Active')


@admin.register(ExchangeRate)
class ExchangeRateAdmin(admin.ModelAdmin):
    list_display = ['from_currency', 'to_currency', 'rate', 'date', 'source', 'is_official']
    list_filter = ['source', 'is_official', 'from_currency']
    search_fields = ['from_currency__code', 'to_currency__code']
    ordering = ['-date', '-created_at']
    list_per_page = 50


@admin.register(ExchangeRateProvider)
class ExchangeRateProviderAdmin(admin.ModelAdmin):
    list_display = ['name', 'provider_type', 'is_active', 'is_default', 'priority', 'last_success_at', 'total_requests', 'failed_requests']
    list_filter = ['is_active', 'is_default', 'provider_type']
    readonly_fields = ['last_fetch_at', 'last_success_at', 'total_requests', 'failed_requests', 'requests_this_month']


@admin.register(CurrencyConversionLog)
class CurrencyConversionLogAdmin(admin.ModelAdmin):
    list_display = ['from_currency', 'to_currency', 'amount', 'converted_amount', 'rate_used', 'was_cached', 'created_at']
    list_filter = ['from_currency', 'to_currency', 'was_cached']
    readonly_fields = ['created_at']
    ordering = ['-created_at']

    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
