# api/djoyalty/admin/fraud_admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from ..models.advanced import PointsAbuseLog, LoyaltyFraudRule

@admin.register(PointsAbuseLog)
class PointsAbuseLogAdmin(admin.ModelAdmin):
    list_display = ['customer', 'risk_level_badge', 'action_taken', 'description_preview', 'is_resolved', 'created_at']
    list_filter = ['risk_level', 'is_resolved', 'action_taken']
    search_fields = ['customer__code', 'description']
    readonly_fields = ['created_at']
    ordering = ['-created_at']

    def risk_level_badge(self, obj):
        colors = {'low': ('#dcfce7', '#166534'), 'medium': ('#fef3c7', '#92400e'), 'high': ('#fed7aa', '#9a3412'), 'critical': ('#fee2e2', '#991b1b')}
        bg, fg = colors.get(obj.risk_level, ('#f3f4f6', '#374151'))
        return format_html('<span style="background:{};color:{};padding:2px 8px;border-radius:8px;font-size:11px;font-weight:600;">{}</span>', bg, fg, obj.risk_level.upper())
    risk_level_badge.short_description = 'Risk'

    def description_preview(self, obj):
        desc = (obj.description or '')[:60]
        return format_html('<span style="color:#555;font-size:12px;">{}</span>', desc)
    description_preview.short_description = 'Description'

    actions = ['mark_resolved']

    def mark_resolved(self, request, queryset):
        count = queryset.update(is_resolved=True, resolved_by=str(request.user), resolved_at=timezone.now())
        self.message_user(request, f'✅ {count} fraud logs resolved.')
    mark_resolved.short_description = 'Mark as resolved'

@admin.register(LoyaltyFraudRule)
class LoyaltyFraudRuleAdmin(admin.ModelAdmin):
    list_display = ['name', 'rule_type', 'risk_level', 'action', 'threshold_value', 'window_minutes', 'is_active']
    list_filter = ['risk_level', 'action', 'is_active']
