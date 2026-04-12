# admin/localization_config_admin.py
from django.contrib import admin
from ..models.settings import LocalizationConfig, DateTimeFormat, NumberFormat, AddressFormat

@admin.register(LocalizationConfig)
class LocalizationConfigAdmin(admin.ModelAdmin):
    list_display = ['tenant_id', 'default_language', 'default_currency', 'detect_from_browser', 'detect_from_ip', 'auto_translate', 'is_active']
    search_fields = ['tenant_id']
    list_filter = ['is_active', 'detect_language_from_browser', 'auto_translate_missing']

    def detect_from_browser(self, obj):
        return obj.detect_language_from_browser
    detect_from_browser.boolean = True

    def detect_from_ip(self, obj):
        return obj.detect_language_from_ip
    detect_from_ip.boolean = True

    def auto_translate(self, obj):
        return obj.auto_translate_missing
    auto_translate.boolean = True


@admin.register(DateTimeFormat)
class DateTimeFormatAdmin(admin.ModelAdmin):
    list_display = ['language', 'country', 'calendar_system', 'date_short', 'time_short', 'first_day_of_week']
    list_filter = ['calendar_system', 'use_native_numerals']
    search_fields = ['language__code', 'country__code']


@admin.register(NumberFormat)
class NumberFormatAdmin(admin.ModelAdmin):
    list_display = ['language', 'country', 'decimal_symbol', 'grouping_symbol', 'grouping_size', 'secondary_grouping']
    list_filter = ['use_grouping']
    search_fields = ['language__code', 'country__code']


@admin.register(AddressFormat)
class AddressFormatAdmin(admin.ModelAdmin):
    list_display = ['country', 'postal_code_label', 'uses_state', 'uses_district', 'uses_postal_code']
    search_fields = ['country__code', 'country__name']
