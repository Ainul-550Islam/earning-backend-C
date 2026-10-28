# api/djoyalty/admin/campaign_admin.py
from django.contrib import admin
from django.utils.html import format_html
from ..models.campaigns import LoyaltyCampaign, CampaignSegment, CampaignParticipant, ReferralPointsRule, PartnerMerchant


class CampaignSegmentInline(admin.TabularInline):
    model = CampaignSegment
    extra = 1
    fields = ['segment_type', 'condition_value', 'is_active']


class CampaignParticipantInline(admin.TabularInline):
    model = CampaignParticipant
    extra = 0
    readonly_fields = ['customer', 'points_earned_in_campaign', 'joined_at']
    can_delete = False


@admin.register(LoyaltyCampaign)
class LoyaltyCampaignAdmin(admin.ModelAdmin):
    list_display = ['name', 'campaign_type', 'multiplier', 'bonus_points', 'status_badge', 'start_date', 'end_date', 'is_featured']
    list_filter = ['status', 'campaign_type', 'segment_target', 'is_featured']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at', 'points_issued']
    inlines = [CampaignSegmentInline, CampaignParticipantInline]
    fieldsets = [
        ('Campaign Info', {'fields': ['name', 'description', 'campaign_type', 'status', 'is_featured']}),
        ('Points Config', {'fields': ['multiplier', 'bonus_points', 'budget_points', 'points_issued']}),
        ('Targeting', {'fields': ['segment_target', 'max_participants']}),
        ('Schedule', {'fields': ['start_date', 'end_date']}),
        ('Content', {'fields': ['image', 'terms']}),
        ('Timestamps', {'fields': ['created_at', 'updated_at']}),
    ]

    def status_badge(self, obj):
        colors = {'draft': '#f59e0b', 'active': '#10b981', 'ended': '#6b7280', 'paused': '#3b82f6'}
        color = colors.get(obj.status, '#6b7280')
        return format_html('<span style="background:{};color:#fff;padding:2px 8px;border-radius:4px;">{}</span>', color, obj.status)
    status_badge.short_description = 'Status'

    actions = ['activate_campaigns', 'end_campaigns']

    def activate_campaigns(self, request, queryset):
        count = queryset.filter(status='draft').update(status='active')
        self.message_user(request, f'{count} campaigns activated.')
    activate_campaigns.short_description = 'Activate selected draft campaigns'

    def end_campaigns(self, request, queryset):
        count = queryset.filter(status='active').update(status='ended')
        self.message_user(request, f'{count} campaigns ended.')
    end_campaigns.short_description = 'End selected active campaigns'


@admin.register(CampaignParticipant)
class CampaignParticipantAdmin(admin.ModelAdmin):
    list_display = ['campaign', 'customer', 'points_earned_in_campaign', 'is_active', 'joined_at']
    list_filter = ['is_active', 'joined_at']
    search_fields = ['campaign__name', 'customer__code']
    readonly_fields = ['joined_at', 'created_at']


@admin.register(PartnerMerchant)
class PartnerMerchantAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'earn_rate', 'burn_rate', 'is_active', 'last_sync_at']
    list_filter = ['is_active', 'category']
    search_fields = ['name', 'api_key']
    readonly_fields = ['created_at', 'updated_at', 'last_sync_at']
    fieldsets = [
        ('Merchant Info', {'fields': ['name', 'description', 'category', 'logo', 'website', 'is_active']}),
        ('Points Config', {'fields': ['earn_rate', 'burn_rate']}),
        ('API Config', {'fields': ['api_key', 'webhook_url', 'webhook_secret']}),
        ('Sync', {'fields': ['last_sync_at']}),
        ('Timestamps', {'fields': ['created_at', 'updated_at']}),
    ]


@admin.register(ReferralPointsRule)
class ReferralPointsRuleAdmin(admin.ModelAdmin):
    list_display = ['level', 'points_on_signup', 'points_on_first_offer', 'multiplier', 'is_active']
    list_filter = ['level', 'is_active']
    readonly_fields = ['created_at']
