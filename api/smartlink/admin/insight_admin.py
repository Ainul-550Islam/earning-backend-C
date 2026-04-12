from django.contrib import admin
from ..models import OfferScoreCache, OfferPerformanceStat


@admin.register(OfferPerformanceStat)
class OfferPerformanceStatAdmin(admin.ModelAdmin):
    list_display = [
        'smartlink', 'offer', 'date', 'country', 'device_type',
        'clicks', 'conversions', 'revenue', 'epc', 'conversion_rate',
    ]
    list_filter = ['date', 'country', 'device_type']
    search_fields = ['smartlink__slug', 'offer__name']
    ordering = ['-date', '-epc']
    date_hierarchy = 'date'
    readonly_fields = [
        'smartlink', 'offer', 'date', 'country', 'device_type',
        'clicks', 'unique_clicks', 'conversions', 'revenue', 'epc', 'conversion_rate',
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
