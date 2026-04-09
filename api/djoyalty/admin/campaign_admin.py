# api/djoyalty/admin/campaign_admin.py
from django.contrib import admin
from django.utils.html import format_html
from ..models.campaigns import LoyaltyCampaign, CampaignParticipant, ReferralPointsRule, PartnerMerchant

@admin.register(LoyaltyCampaign)
class LoyaltyCampaignAdmin(admin.ModelAdmin):
    list_display = ['name', 'campaign_type', 'status_badge', 'multiplier', 'bonus_points', 'start_date', 'end_date']
    list_filter = ['status', 'campaign_type']
    search_fields = ['name']
    readonly_fields = ['created_at']

    def status_badge(self, obj):
        colors = {'draft': ('#f3f4f6', '#374151'), 'active': ('#dcfce7', '#166534'), 'paused': ('#fef3c7', '#92400e'), 'ended': ('#dbeafe', '#1e40af'), 'cancelled': ('#fee2e2', '#991b1b')}
        bg, fg = colors.get(obj.status, ('#f3f4f6', '#374151'))
        return format_html('<span style="background:{};color:{};padding:2px 8px;border-radius:8px;font-size:11px;">{}</span>', bg, fg, obj.status.title())
    status_badge.short_description = 'Status'
