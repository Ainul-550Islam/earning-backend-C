# api/djoyalty/admin/redemption_admin.py
from django.contrib import admin
from django.utils.html import format_html
from ..models.redemption import RedemptionRule, RedemptionRequest, RedemptionHistory


class RedemptionHistoryInline(admin.TabularInline):
    model = RedemptionHistory
    extra = 0
    readonly_fields = ['from_status', 'to_status', 'changed_by', 'note', 'changed_at']
    can_delete = False


@admin.register(RedemptionRule)
class RedemptionRuleAdmin(admin.ModelAdmin):
    list_display = ['name', 'reward_type', 'points_required', 'cash_value', 'is_active', 'created_at']
    list_filter = ['reward_type', 'is_active', 'approval_required']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = [
        ('Rule Info', {'fields': ['name', 'description', 'reward_type', 'is_active']}),
        ('Points Config', {'fields': ['points_required', 'cash_value', 'min_points', 'max_per_user_per_day']}),
        ('Restrictions', {'fields': ['min_tier', 'approval_required', 'valid_from', 'valid_until']}),
        ('Content', {'fields': ['image', 'terms']}),
        ('Timestamps', {'fields': ['created_at', 'updated_at']}),
    ]


@admin.register(RedemptionRequest)
class RedemptionRequestAdmin(admin.ModelAdmin):
    list_display = ['id', 'customer', 'points_used', 'redemption_type', 'reward_value', 'status_badge', 'created_at']
    list_filter = ['status', 'redemption_type', 'created_at']
    search_fields = ['customer__code', 'customer__email', 'reference']
    readonly_fields = ['created_at', 'updated_at', 'reviewed_at', 'fulfilled_at']
    inlines = [RedemptionHistoryInline]
    fieldsets = [
        ('Request Info', {'fields': ['customer', 'rule', 'points_used', 'redemption_type', 'reward_value']}),
        ('Status', {'fields': ['status', 'reviewed_by', 'reviewed_at', 'fulfilled_at', 'note', 'reference']}),
        ('Timestamps', {'fields': ['created_at', 'updated_at']}),
    ]

    def status_badge(self, obj):
        colors = {
            'pending': '#f59e0b', 'approved': '#10b981',
            'rejected': '#ef4444', 'fulfilled': '#3b82f6', 'cancelled': '#6b7280',
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html('<span style="background:{};color:#fff;padding:2px 8px;border-radius:4px;">{}</span>', color, obj.status)
    status_badge.short_description = 'Status'

    actions = ['approve_selected', 'reject_selected']

    def approve_selected(self, request, queryset):
        from ..services.redemption.RedemptionService import RedemptionService
        count = 0
        for req in queryset.filter(status='pending'):
            try:
                RedemptionService.approve(req.id, reviewed_by=str(request.user))
                count += 1
            except Exception:
                pass
        self.message_user(request, f'{count} redemptions approved.')
    approve_selected.short_description = 'Approve selected pending redemptions'

    def reject_selected(self, request, queryset):
        from ..services.redemption.RedemptionService import RedemptionService
        count = 0
        for req in queryset.filter(status='pending'):
            try:
                RedemptionService.reject(req.id, reason='Bulk admin reject', reviewed_by=str(request.user))
                count += 1
            except Exception:
                pass
        self.message_user(request, f'{count} redemptions rejected.')
    reject_selected.short_description = 'Reject selected pending redemptions'


@admin.register(RedemptionHistory)
class RedemptionHistoryAdmin(admin.ModelAdmin):
    list_display = ['request', 'from_status', 'to_status', 'changed_by', 'changed_at']
    list_filter = ['from_status', 'to_status']
    readonly_fields = ['request', 'from_status', 'to_status', 'changed_by', 'note', 'changed_at']
    search_fields = ['request__id', 'changed_by']
