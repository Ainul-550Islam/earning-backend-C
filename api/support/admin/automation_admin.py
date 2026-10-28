# api/support/admin/automation_admin.py  — WORLD #1
from django.contrib import admin
from api.support.models import AutomationRule, AutomationCondition, AutomationAction, AutomationLog

class ConditionInline(admin.TabularInline):
    model = AutomationCondition
    extra = 1

class ActionInline(admin.TabularInline):
    model = AutomationAction
    extra = 1

@admin.register(AutomationRule)
class AutomationRuleAdmin(admin.ModelAdmin):
    list_display  = ['name','trigger','conditions_logic','is_active','priority','run_count','created_at']
    list_filter   = ['trigger','is_active']
    search_fields = ['name','description']
    readonly_fields = ['run_count','created_at','updated_at']
    inlines       = [ConditionInline, ActionInline]