from django.contrib import admin
from ..models import ABTestResult, SmartLinkVersion
from ..choices import ABTestStatus


class SmartLinkVersionInline(admin.TabularInline):
    model = SmartLinkVersion
    extra = 0
    fields = ['name', 'traffic_split', 'is_control', 'is_active', 'is_winner', 'clicks', 'conversions', 'revenue']
    readonly_fields = ['clicks', 'conversions', 'revenue']


@admin.register(ABTestResult)
class ABTestResultAdmin(admin.ModelAdmin):
    list_display = [
        'smartlink', 'status', 'winner_version', 'confidence_level',
        'uplift_percent', 'p_value', 'is_significant_display',
        'started_at', 'completed_at',
    ]
    list_filter = ['status', 'auto_applied']
    search_fields = ['smartlink__slug']
    readonly_fields = [
        'confidence_level', 'uplift_percent', 'control_cr', 'winner_cr',
        'control_clicks', 'winner_clicks', 'p_value',
        'started_at', 'completed_at', 'created_at', 'updated_at',
    ]
    raw_id_fields = ['smartlink', 'winner_version', 'control_version']
    actions = ['evaluate_significance', 'apply_winners']

    def is_significant_display(self, obj):
        from django.utils.html import format_html
        if obj.is_significant:
            return format_html('<span style="color:green;font-weight:bold;">✅ Significant</span>')
        return format_html('<span style="color:gray;">⏳ Not yet</span>')
    is_significant_display.short_description = 'Significant?'

    @admin.action(description='📊 Evaluate statistical significance')
    def evaluate_significance(self, request, queryset):
        from ..services.rotation.ABTestService import ABTestService
        svc = ABTestService()
        winners = 0
        for result in queryset.filter(status=ABTestStatus.RUNNING):
            data = svc.evaluate_significance(result)
            if data.get('significant'):
                winners += 1
        self.message_user(request, f'Evaluated {queryset.count()} tests. {winners} winners found.')

    @admin.action(description='🏆 Apply winners to SmartLinks')
    def apply_winners(self, request, queryset):
        from ..services.rotation.ABTestService import ABTestService
        svc = ABTestService()
        applied = 0
        for result in queryset.filter(status=ABTestStatus.WINNER_FOUND):
            try:
                svc.apply_winner(result)
                applied += 1
            except Exception as e:
                pass
        self.message_user(request, f'{applied} winners applied.')
