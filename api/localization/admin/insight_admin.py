# admin/insight_admin.py
from django.contrib import admin
from ..models.analytics import LocalizationInsight, LanguageUsageStat, GeoInsight

@admin.register(LocalizationInsight)
class LocalizationInsightAdmin(admin.ModelAdmin):
    list_display = ['date', 'language', 'country', 'total_requests', 'cache_hit_rate', 'translation_hit_rate']
    list_filter = ['language', 'country']
    date_hierarchy = 'date'
    ordering = ['-date']
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False

@admin.register(GeoInsight)
class GeoInsightAdmin(admin.ModelAdmin):
    list_display = ['date', 'country', 'country_code', 'region_name', 'total_users', 'total_requests']
    list_filter = ['country']
    date_hierarchy = 'date'
    ordering = ['-date', '-total_users']
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
