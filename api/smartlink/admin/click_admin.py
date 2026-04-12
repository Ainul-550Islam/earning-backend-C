from django.contrib import admin
from ..models import Click, ClickMetadata, UniqueClick, ClickHeatmap, BotClick, ClickSession


@admin.register(Click)
class ClickAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'smartlink', 'offer', 'country', 'device_type',
        'ip', 'is_unique', 'is_fraud', 'is_bot', 'is_converted',
        'fraud_score', 'payout', 'created_at',
    ]
    list_filter = ['is_unique', 'is_fraud', 'is_bot', 'is_converted', 'device_type', 'country']
    search_fields = ['smartlink__slug', 'ip', 'offer__name']
    readonly_fields = [
        'smartlink', 'offer', 'ip', 'country', 'region', 'city',
        'user_agent', 'device_type', 'os', 'browser',
        'is_unique', 'is_fraud', 'is_bot', 'is_converted',
        'fraud_score', 'payout', 'referrer', 'created_at',
    ]
    date_hierarchy = 'created_at'
    list_per_page = 100
    ordering = ['-created_at']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(BotClick)
class BotClickAdmin(admin.ModelAdmin):
    list_display = ['smartlink', 'ip', 'bot_type', 'detection_method', 'country', 'created_at']
    list_filter = ['bot_type', 'detection_method', 'country']
    search_fields = ['ip', 'user_agent', 'smartlink__slug']
    readonly_fields = ['smartlink', 'ip', 'user_agent', 'bot_type', 'detection_method', 'country', 'created_at']

    def has_add_permission(self, request):
        return False


@admin.register(UniqueClick)
class UniqueClickAdmin(admin.ModelAdmin):
    list_display = ['fingerprint_short', 'smartlink', 'offer', 'ip', 'date', 'click_count']
    list_filter = ['date']
    search_fields = ['ip', 'smartlink__slug']
    readonly_fields = ['fingerprint', 'smartlink', 'offer', 'ip', 'date', 'click_count', 'created_at']

    def fingerprint_short(self, obj):
        return obj.fingerprint[:16] + '...'
    fingerprint_short.short_description = 'Fingerprint'

    def has_add_permission(self, request):
        return False


@admin.register(ClickHeatmap)
class ClickHeatmapAdmin(admin.ModelAdmin):
    list_display = ['smartlink', 'country', 'date', 'click_count', 'conversion_count', 'revenue', 'epc']
    list_filter = ['country', 'date']
    search_fields = ['smartlink__slug', 'country']
    ordering = ['-date', '-click_count']
