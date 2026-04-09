# api/djoyalty/admin/redemption_admin.py
from django.contrib import admin
from django.utils.html import format_html
from ..models.redemption import RedemptionRequest, RedemptionRule, RedemptionHistory

class RedemptionHistoryInline(admin.TabularInline):
    model = RedemptionHistory
    extra = 0
    readonly_fields = ['from_status', 'to_status', 'changed_by', 'created_at']

@admin.register(RedemptionRequest)
class RedemptionRequestAdmin(admin.ModelAdmin):
    list_display = ['id', 'customer', 'redemption_type', 'points_used', 'reward_value', 'status_badge', 'reviewed_by', 'created_at']
    list_filter = ['status', 'redemption_type']
    search_fields = ['customer__code', 'customer__email']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [RedemptionHistoryInline]

    def status_badge(self, obj):
        colors = {'pending': ('#fef3c7', '#92400e'), 'approved': ('#dcfce7', '#166534'), 'rejected': ('#fee2e2', '#991b1b'), 'completed': ('#dbeafe', '#1e40af'), 'cancelled': ('#f3f4f6', '#374151')}
        bg, fg = colors.get(obj.status, ('#f3f4f6', '#374151'))
        return format_html('<span style="background:{};color:{};padding:2px 8px;border-radius:8px;font-size:11px;">{}</span>', bg, fg, obj.status.title())
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
        self.message_user(request, f'✅ {count} redemptions approved.')
    approve_selected.short_description = 'Approve selected redemptions'

    def reject_selected(self, request, queryset):
        from ..services.redemption.RedemptionService import RedemptionService
        count = 0
        for req in queryset.filter(status='pending'):
            try:
                RedemptionService.reject(req.id, reason='Bulk rejected', reviewed_by=str(request.user))
                count += 1
            except Exception:
                pass
        self.message_user(request, f'❌ {count} redemptions rejected.')
    reject_selected.short_description = 'Reject selected redemptions'

@admin.register(RedemptionRule)
class RedemptionRuleAdmin(admin.ModelAdmin):
    list_display = ['name', 'redemption_type', 'points_required', 'reward_value', 'is_active']
    list_filter = ['redemption_type', 'is_active']
