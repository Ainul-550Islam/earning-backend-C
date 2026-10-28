# api/djoyalty/admin/fraud_admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from ..models.advanced import PointsAbuseLog, LoyaltyFraudRule


@admin.register(LoyaltyFraudRule)
class LoyaltyFraudRuleAdmin(admin.ModelAdmin):
    list_display = ['name', 'rule_type', 'action', 'threshold', 'cooldown_hours', 'is_active']
    list_filter = ['rule_type', 'action', 'is_active']
    search_fields = ['name', 'condition']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = [
        ('Rule Info', {'fields': ['name', 'rule_type', 'condition', 'is_active']}),
        ('Action Config', {'fields': ['action', 'threshold', 'cooldown_hours']}),
        ('Timestamps', {'fields': ['created_at', 'updated_at']}),
    ]


@admin.register(PointsAbuseLog)
class PointsAbuseLogAdmin(admin.ModelAdmin):
    list_display = ['customer', 'risk_level_badge', 'action_taken', 'points_reversed', 'is_resolved', 'detected_at']
    list_filter = ['risk_level', 'action_taken', 'is_resolved', 'detected_at']
    search_fields = ['customer__code', 'description']
    readonly_fields = ['customer', 'rule', 'risk_level', 'action_taken', 'description',
                       'points_reversed', 'detected_at', 'created_at']
    fieldsets = [
        ('Detection Info', {'fields': ['customer', 'rule', 'risk_level', 'action_taken', 'description', 'points_reversed']}),
        ('Resolution', {'fields': ['is_resolved', 'resolved_at', 'resolved_by', 'resolution_note']}),
        ('Metadata', {'fields': ['metadata', 'detected_at', 'created_at']}),
    ]

    def risk_level_badge(self, obj):
        colors = {'low': '#10b981', 'medium': '#f59e0b', 'high': '#ef4444', 'critical': '#7c3aed'}
        color = colors.get(obj.risk_level, '#6b7280')
        return format_html('<span style="background:{};color:#fff;padding:2px 8px;border-radius:4px;font-weight:bold;">{}</span>',
                           color, obj.risk_level.upper())
    risk_level_badge.short_description = 'Risk Level'

    actions = ['mark_resolved', 'mark_unresolved']

    def mark_resolved(self, request, queryset):
        count = queryset.filter(is_resolved=False).update(
            is_resolved=True, resolved_at=timezone.now(), resolved_by=str(request.user)
        )
        self.message_user(request, f'{count} fraud logs marked as resolved.')
    mark_resolved.short_description = 'Mark selected as resolved'

    def mark_unresolved(self, request, queryset):
        count = queryset.filter(is_resolved=True).update(is_resolved=False, resolved_at=None)
        self.message_user(request, f'{count} fraud logs marked as unresolved.')
    mark_unresolved.short_description = 'Mark selected as unresolved'
