from django.contrib import admin
from ..models import TargetingRule, GeoTargeting, DeviceTargeting, OSTargeting, BrowserTargeting, TimeTargeting, ISPTargeting, LanguageTargeting


@admin.register(TargetingRule)
class TargetingRuleAdmin(admin.ModelAdmin):
    list_display = ['smartlink', 'logic', 'is_active', 'priority', 'created_at']
    list_filter = ['logic', 'is_active']
    search_fields = ['smartlink__slug']
    raw_id_fields = ['smartlink']


@admin.register(GeoTargeting)
class GeoTargetingAdmin(admin.ModelAdmin):
    list_display = ['rule', 'mode', 'countries_display']
    list_filter = ['mode']

    def countries_display(self, obj):
        return ', '.join(obj.countries[:5]) + ('...' if len(obj.countries) > 5 else '')
    countries_display.short_description = 'Countries'


@admin.register(DeviceTargeting)
class DeviceTargetingAdmin(admin.ModelAdmin):
    list_display = ['rule', 'mode', 'device_types']
    list_filter = ['mode']


@admin.register(OSTargeting)
class OSTargetingAdmin(admin.ModelAdmin):
    list_display = ['rule', 'mode', 'os_types']
    list_filter = ['mode']


@admin.register(TimeTargeting)
class TimeTargetingAdmin(admin.ModelAdmin):
    list_display = ['rule', 'days_of_week', 'start_hour', 'end_hour', 'timezone_name']


@admin.register(ISPTargeting)
class ISPTargetingAdmin(admin.ModelAdmin):
    list_display = ['rule', 'mode', 'isps']
    list_filter = ['mode']


@admin.register(LanguageTargeting)
class LanguageTargetingAdmin(admin.ModelAdmin):
    list_display = ['rule', 'mode', 'languages']
    list_filter = ['mode']
