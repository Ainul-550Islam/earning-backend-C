from django.contrib import admin
from .base_admin import ReadOnlyAdmin, SmartLinkAdminMixin
from api.smartlink.models import SmartLinkStat, SmartLinkDailyStat, GeoPerformanceStat, DevicePerformanceStat

@admin.register(SmartLinkDailyStat)
class SmartLinkDailyStatAdmin(SmartLinkAdminMixin, ReadOnlyAdmin):
    list_display = [
        'smartlink', 'date', 'clicks', 'unique_clicks',
        'conversions', 'revenue', 'epc', 'conversion_rate',
        'top_country', 'top_device',
    ]
    list_filter = ['date', 'top_country', 'top_device']
    search_fields = ['smartlink__slug']
    ordering = ['-date']
    date_hierarchy = 'date'
    readonly_fields = list_display

@admin.register(SmartLinkStat)
class SmartLinkStatAdmin(SmartLinkAdminMixin, ReadOnlyAdmin):
    list_display = ['smartlink', 'hour', 'country', 'device_type', 'clicks', 'conversions', 'revenue', 'epc']
    list_filter = ['country', 'device_type']
    search_fields = ['smartlink__slug']
    ordering = ['-hour']
    readonly_fields = ['smartlink', 'hour', 'country', 'device_type', 'clicks', 'unique_clicks',
                       'bot_clicks', 'fraud_clicks', 'conversions', 'revenue', 'epc', 'conversion_rate']

@admin.register(GeoPerformanceStat)
class GeoPerformanceStatAdmin(SmartLinkAdminMixin, ReadOnlyAdmin):
    list_display = ['smartlink', 'country', 'date', 'clicks', 'conversions', 'revenue', 'epc']
    list_filter = ['country', 'date']
    search_fields = ['smartlink__slug', 'country']
    ordering = ['-date', '-epc']

@admin.register(DevicePerformanceStat)
class DevicePerformanceStatAdmin(SmartLinkAdminMixin, ReadOnlyAdmin):
    list_display = ['smartlink', 'device_type', 'date', 'clicks', 'conversions', 'revenue', 'epc']
    list_filter = ['device_type', 'date']
    search_fields = ['smartlink__slug']
    ordering = ['-date', '-epc']