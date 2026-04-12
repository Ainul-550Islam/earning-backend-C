from django.contrib import admin
from ..models import SmartLinkStat, SmartLinkDailyStat, GeoPerformanceStat, DevicePerformanceStat


@admin.register(SmartLinkDailyStat)
class SmartLinkDailyStatAdmin(admin.ModelAdmin):
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

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(SmartLinkStat)
class SmartLinkStatAdmin(admin.ModelAdmin):
    list_display = ['smartlink', 'hour', 'country', 'device_type', 'clicks', 'conversions', 'revenue', 'epc']
    list_filter = ['country', 'device_type']
    search_fields = ['smartlink__slug']
    ordering = ['-hour']
    readonly_fields = ['smartlink', 'hour', 'country', 'device_type', 'clicks', 'unique_clicks',
                       'bot_clicks', 'fraud_clicks', 'conversions', 'revenue', 'epc', 'conversion_rate']

    def has_add_permission(self, request):
        return False


@admin.register(GeoPerformanceStat)
class GeoPerformanceStatAdmin(admin.ModelAdmin):
    list_display = ['smartlink', 'country', 'date', 'clicks', 'conversions', 'revenue', 'epc']
    list_filter = ['country', 'date']
    search_fields = ['smartlink__slug', 'country']
    ordering = ['-date', '-epc']


@admin.register(DevicePerformanceStat)
class DevicePerformanceStatAdmin(admin.ModelAdmin):
    list_display = ['smartlink', 'device_type', 'date', 'clicks', 'conversions', 'revenue', 'epc']
    list_filter = ['device_type', 'date']
    search_fields = ['smartlink__slug']
    ordering = ['-date', '-epc']
