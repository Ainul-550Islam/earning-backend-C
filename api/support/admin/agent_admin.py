# api/support/admin/agent_admin.py  — WORLD #1
from django.contrib import admin
from api.support.models import SupportAgent, AgentStatus, AgentPerformance, AgentShift, AgentSkill

class AgentShiftInline(admin.TabularInline):
    model = AgentShift
    extra = 0

class AgentSkillInline(admin.TabularInline):
    model = AgentSkill
    extra = 0

@admin.register(SupportAgent)
class SupportAgentAdmin(admin.ModelAdmin):
    list_display  = ['user','role','department','is_active','is_available','max_concurrent_tickets','max_concurrent_chats','created_at']
    list_filter   = ['role','is_active','is_available','department']
    search_fields = ['user__username','user__email']
    inlines       = [AgentShiftInline, AgentSkillInline]

@admin.register(AgentStatus)
class AgentStatusAdmin(admin.ModelAdmin):
    list_display  = ['agent','status','last_seen','status_message']
    list_filter   = ['status']
    readonly_fields = ['last_seen','changed_at']