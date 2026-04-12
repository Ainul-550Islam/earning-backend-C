from django.contrib import admin
from django.utils.html import format_html
from ..models import ClickFraudFlag


@admin.register(ClickFraudFlag)
class ClickFraudFlagAdmin(admin.ModelAdmin):
    list_display = ['click', 'score', 'action_taken', 'signals_display', 'is_reviewed', 'created_at']
    list_filter = ['action_taken', 'is_reviewed', 'created_at']
    search_fields = ['click__ip', 'click__smartlink__slug']
    readonly_fields = ['click', 'score', 'signals', 'action_taken', 'created_at']
    actions = ['mark_reviewed', 'approve_clicks', 'block_ips']

    def signals_display(self, obj):
        return ', '.join(obj.signals) if obj.signals else '—'
    signals_display.short_description = 'Signals'

    @admin.action(description='✅ Mark selected as reviewed')
    def mark_reviewed(self, request, queryset):
        from django.utils import timezone
        queryset.update(is_reviewed=True, reviewed_by=request.user, reviewed_at=timezone.now())
        self.message_user(request, f'{queryset.count()} flags marked reviewed.')

    @admin.action(description='🚫 Block IPs for selected fraud flags')
    def block_ips(self, request, queryset):
        from django.core.cache import cache
        blocked = 0
        for flag in queryset:
            ip = flag.click.ip
            cache.set(f"fraud:blocked:{ip}", '1', 86400)
            blocked += 1
        self.message_user(request, f'{blocked} IPs blocked for 24 hours.')
