# api/djoyalty/admin/tier_admin.py
from django.contrib import admin
from django.utils.html import format_html
from ..models.tiers import LoyaltyTier, UserTier, TierBenefit, TierHistory, TierConfig


class TierBenefitInline(admin.TabularInline):
    model = TierBenefit
    extra = 1
    fields = ['title', 'benefit_type', 'value', 'is_active', 'sort_order']


@admin.register(LoyaltyTier)
class LoyaltyTierAdmin(admin.ModelAdmin):
    list_display = [
        'name_display', 'label', 'rank', 'min_points',
        'earn_multiplier', 'color_display', 'icon', 'is_active',
    ]
    list_filter = ['name', 'is_active', 'tenant']
    search_fields = ['name', 'label']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['rank']
    inlines = [TierBenefitInline]

    @admin.display(description='Tier Name')
    def name_display(self, obj):
        colors = {
            'bronze': '#cd7f32', 'silver': '#c0c0c0',
            'gold': '#ffd700', 'platinum': '#e5e4e2', 'diamond': '#b9f2ff',
        }
        color = colors.get(obj.name, '#888')
        return format_html(
            '<span style="background:{};padding:2px 8px;border-radius:4px;font-weight:bold">{}</span>',
            color, obj.name.title()
        )

    @admin.display(description='Color')
    def color_display(self, obj):
        return format_html(
            '<span style="background:{};padding:2px 10px;border-radius:3px">&nbsp;</span> {}',
            obj.color, obj.color
        )


@admin.register(UserTier)
class UserTierAdmin(admin.ModelAdmin):
    list_display = [
        'customer_code', 'tier_name', 'is_current',
        'points_at_assignment', 'assigned_at', 'expires_at',
    ]
    list_filter = ['tier__name', 'is_current', 'tenant']
    search_fields = ['customer__code', 'customer__email']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-assigned_at']

    @admin.display(description='Customer')
    def customer_code(self, obj):
        return obj.customer.code

    @admin.display(description='Tier')
    def tier_name(self, obj):
        return obj.tier.name if obj.tier else '--'


@admin.register(TierBenefit)
class TierBenefitAdmin(admin.ModelAdmin):
    list_display = ['tier', 'title', 'benefit_type', 'value', 'is_active', 'sort_order']
    list_filter = ['tier__name', 'benefit_type', 'is_active']
    search_fields = ['title', 'description']
    ordering = ['tier__rank', 'sort_order']


@admin.register(TierHistory)
class TierHistoryAdmin(admin.ModelAdmin):
    list_display = [
        'customer_code', 'from_tier_name', 'to_tier_name',
        'change_type', 'points_at_change', 'changed_at', 'reason_short',
    ]
    list_filter = ['change_type']
    search_fields = ['customer__code', 'reason']
    readonly_fields = ['created_at', 'changed_at']
    ordering = ['-changed_at']

    @admin.display(description='Customer')
    def customer_code(self, obj):
        return obj.customer.code

    @admin.display(description='From Tier')
    def from_tier_name(self, obj):
        return obj.from_tier.name if obj.from_tier else '--'

    @admin.display(description='To Tier')
    def to_tier_name(self, obj):
        return obj.to_tier.name if obj.to_tier else '--'

    @admin.display(description='Reason')
    def reason_short(self, obj):
        if obj.reason:
            return obj.reason[:60]
        return '--'


@admin.register(TierConfig)
class TierConfigAdmin(admin.ModelAdmin):
    list_display = [
        'tenant', 'evaluation_period', 'downgrade_grace_days',
        'downgrade_protection_months', 'freeze_enabled',
        'auto_upgrade', 'auto_downgrade',
    ]
    readonly_fields = ['created_at', 'updated_at']
