# admin/country_admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from ..models.core import Country
from ..models.geo import Region, CountryLanguage, CountryCurrency, GeoIPMapping, PhoneFormat

@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ['code_badge', 'flag_display', 'name', 'phone_code', 'is_eu_badge', 'active_badge', 'created_at']
    list_filter = ['is_active']
    search_fields = ['code', 'name', 'native_name', 'capital']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['name']
    list_per_page = 50

    def code_badge(self, obj):
        return format_html('<span style="background:#6c757d;color:white;padding:2px 8px;border-radius:8px;font-size:12px;font-weight:bold;">{}</span>', obj.code)
    code_badge.short_description = _('Code')

    def flag_display(self, obj):
        return obj.flag_emoji or '🏳️'
    flag_display.short_description = _('Flag')

    def is_eu_badge(self, obj):
        if obj.is_eu_member:
            return format_html('<span style="background:#003399;color:#ffcc00;padding:2px 6px;border-radius:8px;font-size:11px;">EU</span>')
        return ''
    is_eu_badge.short_description = _('EU')

    def active_badge(self, obj):
        if obj.is_active:
            return format_html('<span style="color:#28a745;">✓</span>')
        return format_html('<span style="color:#dc3545;">✗</span>')
    active_badge.short_description = _('Active')


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ['name', 'region_type', 'country', 'parent', 'population', 'is_active']
    list_filter = ['region_type', 'is_active', 'country']
    search_fields = ['name', 'native_name', 'code']
    raw_id_fields = ['parent', 'country', 'timezone']


@admin.register(CountryLanguage)
class CountryLanguageAdmin(admin.ModelAdmin):
    list_display = ['country', 'language', 'status', 'speaker_percentage', 'is_official', 'is_taught_in_schools']
    list_filter = ['is_official', 'is_national', 'status']
    search_fields = ['country__code', 'country__name', 'language__code', 'language__name']
    raw_id_fields = ['country', 'language']


@admin.register(GeoIPMapping)
class GeoIPMappingAdmin(admin.ModelAdmin):
    list_display = ['ip_start', 'ip_end', 'country_code', 'city_name', 'isp', 'is_vpn', 'is_proxy', 'source']
    list_filter = ['source', 'is_vpn', 'is_proxy', 'is_datacenter', 'is_tor']
    search_fields = ['ip_start', 'ip_end', 'country_code', 'city_name', 'isp']


@admin.register(PhoneFormat)
class PhoneFormatAdmin(admin.ModelAdmin):
    list_display = ['country', 'country_dial_code', 'mobile_length', 'example_mobile']
    search_fields = ['country__code', 'country__name', 'country_dial_code']
