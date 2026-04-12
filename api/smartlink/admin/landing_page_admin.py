from django.contrib import admin
from ..models import LandingPage, PreLander


@admin.register(LandingPage)
class LandingPageAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'smartlink', 'url_short', 'is_active',
        'is_default', 'traffic_split', 'views', 'clicks_through', 'ctr_display',
    ]
    list_filter = ['is_active', 'is_default']
    search_fields = ['name', 'smartlink__slug', 'url']
    raw_id_fields = ['smartlink']

    def url_short(self, obj):
        return obj.url[:60] + '...' if len(obj.url) > 60 else obj.url
    url_short.short_description = 'URL'

    def ctr_display(self, obj):
        return f"{obj.ctr}%"
    ctr_display.short_description = 'CTR'


@admin.register(PreLander)
class PreLanderAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'smartlink', 'type', 'is_active',
        'pass_through_params', 'views', 'pass_through_count', 'ptr_display',
    ]
    list_filter = ['type', 'is_active', 'pass_through_params']
    search_fields = ['name', 'smartlink__slug']
    raw_id_fields = ['smartlink']

    def ptr_display(self, obj):
        return f"{obj.pass_through_rate}%"
    ptr_display.short_description = 'Pass-Through Rate'
