from django.contrib import admin
from django.utils.html import format_html
from ..models import SmartLink, SmartLinkGroup, SmartLinkTag, SmartLinkTagging, SmartLinkVersion, SmartLinkFallback, SmartLinkRotation


@admin.register(SmartLink)
class SmartLinkAdmin(admin.ModelAdmin):
    list_display = [
        'slug', 'name', 'publisher', 'type', 'is_active',
        'total_clicks', 'total_conversions', 'total_revenue_display',
        'epc_display', 'last_click_at', 'created_at',
    ]
    list_filter = ['type', 'is_active', 'is_archived', 'redirect_type', 'rotation_method', 'created_at']
    search_fields = ['slug', 'name', 'publisher__username', 'publisher__email']
    readonly_fields = [
        'uuid', 'total_clicks', 'total_unique_clicks',
        'total_conversions', 'total_revenue', 'last_click_at',
        'created_at', 'updated_at', 'full_url_display',
    ]
    list_per_page = 50
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    raw_id_fields = ['publisher', 'group']
    actions = ['activate_selected', 'deactivate_selected', 'archive_selected', 'invalidate_cache_selected']

    fieldsets = (
        ('Basic Info', {
            'fields': ('uuid', 'publisher', 'group', 'slug', 'name', 'description', 'type', 'full_url_display'),
        }),
        ('Redirect Config', {
            'fields': ('redirect_type', 'rotation_method'),
        }),
        ('Features', {
            'fields': ('is_active', 'is_archived', 'enable_ab_test', 'enable_fraud_filter', 'enable_bot_filter', 'enable_unique_click'),
        }),
        ('Stats (Read-only)', {
            'fields': ('total_clicks', 'total_unique_clicks', 'total_conversions', 'total_revenue', 'last_click_at'),
            'classes': ('collapse',),
        }),
        ('Notes & Timestamps', {
            'fields': ('notes', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def total_revenue_display(self, obj):
        return f"${obj.total_revenue:,.4f}"
    total_revenue_display.short_description = 'Revenue'

    def epc_display(self, obj):
        if obj.total_clicks == 0:
            return '$0.0000'
        return f"${float(obj.total_revenue) / obj.total_clicks:.4f}"
    epc_display.short_description = 'EPC'

    def full_url_display(self, obj):
        url = obj.full_url
        return format_html('<a href="{}" target="_blank">{}</a>', url, url)
    full_url_display.short_description = 'Full URL'

    @admin.action(description='✅ Activate selected SmartLinks')
    def activate_selected(self, request, queryset):
        updated = queryset.update(is_active=True, is_archived=False)
        self.message_user(request, f'{updated} SmartLinks activated.')

    @admin.action(description='⏸ Deactivate selected SmartLinks')
    def deactivate_selected(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} SmartLinks deactivated.')

    @admin.action(description='🗄 Archive selected SmartLinks')
    def archive_selected(self, request, queryset):
        updated = queryset.update(is_active=False, is_archived=True)
        self.message_user(request, f'{updated} SmartLinks archived.')

    @admin.action(description='🔄 Invalidate Redis cache for selected')
    def invalidate_cache_selected(self, request, queryset):
        from ..services.core.SmartLinkCacheService import SmartLinkCacheService
        svc = SmartLinkCacheService()
        for sl in queryset:
            svc.invalidate_smartlink(sl.slug)
        self.message_user(request, f'Cache invalidated for {queryset.count()} SmartLinks.')


@admin.register(SmartLinkGroup)
class SmartLinkGroupAdmin(admin.ModelAdmin):
    list_display = ['name', 'publisher', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name', 'publisher__username']


@admin.register(SmartLinkTag)
class SmartLinkTagAdmin(admin.ModelAdmin):
    list_display = ['name', 'color', 'created_at']
    search_fields = ['name']


@admin.register(SmartLinkVersion)
class SmartLinkVersionAdmin(admin.ModelAdmin):
    list_display = ['smartlink', 'name', 'traffic_split', 'is_control', 'is_winner', 'clicks', 'conversions']
    list_filter = ['is_control', 'is_winner', 'is_active']
    search_fields = ['smartlink__slug', 'name']


@admin.register(SmartLinkFallback)
class SmartLinkFallbackAdmin(admin.ModelAdmin):
    list_display = ['smartlink', 'url', 'is_active']
    search_fields = ['smartlink__slug', 'url']
