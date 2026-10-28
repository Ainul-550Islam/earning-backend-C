# api/djoyalty/admin/earn_rule_admin.py
from django.contrib import admin
from django.utils.html import format_html
from ..models.earn_rules import EarnRule, EarnRuleCondition, EarnRuleTierMultiplier, EarnTransaction, BonusEvent, EarnRuleLog


class EarnRuleConditionInline(admin.TabularInline):
    model = EarnRuleCondition
    extra = 1
    fields = ['condition_type', 'operator', 'value', 'is_active']


class EarnRuleTierMultiplierInline(admin.TabularInline):
    model = EarnRuleTierMultiplier
    extra = 1
    fields = ['tier', 'multiplier']


@admin.register(EarnRule)
class EarnRuleAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'trigger', 'rule_type', 'points_value',
        'multiplier', 'min_spend', 'max_earn_per_txn',
        'priority', 'is_active', 'valid_from', 'valid_until',
    ]
    list_filter = ['trigger', 'rule_type', 'is_active', 'tenant']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-priority', '-created_at']
    inlines = [EarnRuleConditionInline, EarnRuleTierMultiplierInline]
    fieldsets = (
        ('Basic Info', {
            'fields': ('tenant', 'name', 'description', 'trigger', 'rule_type'),
        }),
        ('Points Config', {
            'fields': ('points_value', 'multiplier', 'min_spend', 'max_earn_per_txn', 'max_per_day'),
        }),
        ('Targeting', {
            'fields': ('applicable_tiers',),
        }),
        ('Validity', {
            'fields': ('valid_from', 'valid_until', 'is_active', 'priority'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    actions = ['activate_rules', 'deactivate_rules']

    @admin.action(description='Activate selected rules')
    def activate_rules(self, request, queryset):
        count = queryset.update(is_active=True)
        self.message_user(request, f'{count} rule(s) activated.')

    @admin.action(description='Deactivate selected rules')
    def deactivate_rules(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(request, f'{count} rule(s) deactivated.')


@admin.register(BonusEvent)
class BonusEventAdmin(admin.ModelAdmin):
    list_display = [
        'customer_code', 'points', 'reason_short',
        'triggered_by', 'campaign', 'created_at',
    ]
    list_filter = ['tenant', 'triggered_by']
    search_fields = ['customer__code', 'reason', 'triggered_by']
    readonly_fields = ['created_at']
    ordering = ['-created_at']

    @admin.display(description='Customer')
    def customer_code(self, obj):
        return obj.customer.code

    @admin.display(description='Reason')
    def reason_short(self, obj):
        return obj.reason[:60] + ('...' if len(obj.reason) > 60 else '')


@admin.register(EarnTransaction)
class EarnTransactionAdmin(admin.ModelAdmin):
    list_display = [
        'customer_code', 'rule', 'spend_amount',
        'points_earned', 'source', 'created_at',
    ]
    list_filter = ['source', 'tenant']
    search_fields = ['customer__code', 'source_id']
    readonly_fields = ['created_at']
    ordering = ['-created_at']
    date_hierarchy = 'created_at'

    @admin.display(description='Customer')
    def customer_code(self, obj):
        return obj.customer.code
