# FILE 86 of 257 — fraud/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import FraudAlert, BlockedIP, RiskRule

@admin.register(FraudAlert)
class FraudAlertAdmin(admin.ModelAdmin):
    list_display  = ('id','user','gateway','amount','risk_badge','action_badge','resolved','created_at')
    list_filter   = ('risk_level','action','gateway','resolved')
    search_fields = ('user__email','ip_address')
    readonly_fields=('user','gateway','amount','ip_address','risk_score','risk_level',
                     'action','reasons','metadata','created_at')
    actions = ['mark_resolved']

    def risk_badge(self, obj):
        c = {'low':'#10B981','medium':'#F59E0B','high':'#F97316','critical':'#EF4444'}
        return format_html('<span style="background:{};color:#fff;padding:2px 8px;border-radius:10px;font-size:11px">{}</span>',
                           c.get(obj.risk_level,'#6B7280'), obj.risk_level.upper())
    risk_badge.short_description = 'Risk'

    def action_badge(self, obj):
        c = {'allow':'#10B981','flag':'#F59E0B','verify':'#3B82F6','block':'#EF4444'}
        return format_html('<span style="background:{};color:#fff;padding:2px 8px;border-radius:10px;font-size:11px">{}</span>',
                           c.get(obj.action,'#6B7280'), obj.action.upper())
    action_badge.short_description = 'Action'

    @admin.action(description='Mark selected alerts as resolved')
    def mark_resolved(self, request, queryset):
        queryset.update(resolved=True, resolved_by=request.user, resolved_at=timezone.now())

@admin.register(BlockedIP)
class BlockedIPAdmin(admin.ModelAdmin):
    list_display  = ('ip_address','reason','is_active','blocked_by','created_at')
    list_filter   = ('is_active',)
    search_fields = ('ip_address',)
    actions       = ['unblock_selected']

    @admin.action(description='Unblock selected IPs')
    def unblock_selected(self, request, queryset):
        from django.core.cache import cache
        for ip in queryset:
            cache.delete(f'fraud:ip:{ip.ip_address}')
        queryset.update(is_active=False)

@admin.register(RiskRule)
class RiskRuleAdmin(admin.ModelAdmin):
    list_display  = ('name','condition_type','condition_value','score','priority','is_active')
    list_filter   = ('is_active','condition_type')
    list_editable = ('score','priority','is_active')
