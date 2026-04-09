# api/djoyalty/admin/earn_rule_admin.py
from django.contrib import admin
from django.utils.html import format_html
from ..models.earn_rules import EarnRule, EarnRuleCondition, EarnRuleTierMultiplier

class EarnRuleConditionInline(admin.TabularInline):
    model = EarnRuleCondition
    extra = 1

class EarnRuleTierMultiplierInline(admin.TabularInline):
    model = EarnRuleTierMultiplier
    extra = 0

@admin.register(EarnRule)
class EarnRuleAdmin(admin.ModelAdmin):
    list_display = ['name', 'rule_type', 'trigger', 'points_value', 'multiplier', 'priority', 'active_badge', 'created_at']
    list_filter = ['rule_type', 'trigger', 'is_active']
    search_fields = ['name']
    ordering = ['-priority']
    inlines = [EarnRuleConditionInline, EarnRuleTierMultiplierInline]

    def active_badge(self, obj):
        if obj.is_active:
            return format_html('<span style="background:#dcfce7;color:#166534;padding:2px 8px;border-radius:8px;font-size:11px;">✅ Active</span>')
        return format_html('<span style="background:#fee2e2;color:#991b1b;padding:2px 8px;border-radius:8px;font-size:11px;">❌ Inactive</span>')
    active_badge.short_description = 'Status'
