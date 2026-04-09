# api/djoyalty/admin/tier_admin.py
from django.contrib import admin
from django.utils.html import format_html
from ..models.tiers import LoyaltyTier, UserTier, TierBenefit, TierHistory

class TierBenefitInline(admin.TabularInline):
    model = TierBenefit
    extra = 1

@admin.register(LoyaltyTier)
class LoyaltyTierAdmin(admin.ModelAdmin):
    list_display = ['tier_badge', 'label', 'min_points', 'max_points', 'earn_multiplier', 'rank', 'is_active']
    list_filter = ['is_active']
    ordering = ['rank']
    inlines = [TierBenefitInline]

    def tier_badge(self, obj):
        return format_html('<span style="background:{};color:white;padding:3px 10px;border-radius:12px;font-size:12px;">{} {}</span>', obj.color, obj.icon, obj.name.title())
    tier_badge.short_description = 'Tier'

@admin.register(UserTier)
class UserTierAdmin(admin.ModelAdmin):
    list_display = ['customer', 'tier', 'is_current', 'assigned_at', 'points_at_assignment']
    list_filter = ['is_current', 'tier']
    search_fields = ['customer__code']
    readonly_fields = ['assigned_at']
