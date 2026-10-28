# api/support/admin/sla_admin.py  — WORLD #1
from django.contrib import admin
from api.support.models import SLAPolicy, SLABreach, BusinessHours, Holiday

@admin.register(SLAPolicy)
class SLAPolicyAdmin(admin.ModelAdmin):
    list_display  = ['name','priority_level','first_response_hours','resolution_hours','business_hours_only','is_active']
    list_filter   = ['priority_level','is_active','business_hours_only']
    search_fields = ['name']

@admin.register(SLABreach)
class SLABreachAdmin(admin.ModelAdmin):
    list_display  = ['ticket','breach_type','overdue_hours','resolved','notified_agent','breached_at']
    list_filter   = ['breach_type','resolved']
    search_fields = ['ticket__ticket_id']
    readonly_fields = ['breached_at']

@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):
    list_display  = ['name','date','affects_sla','is_active']
    list_filter   = ['is_active','affects_sla']