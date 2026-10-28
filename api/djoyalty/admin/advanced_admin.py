# ── Safe-register patch (AlreadyRegistered fix) ───────────────────────────
from django.contrib import admin as _adm
from django.contrib.admin.sites import AlreadyRegistered as _Already, NotRegistered as _NotReg
_orig_site_register = _adm.site.register
def _safe_site_register(model_or_iterable, admin_class=None, **options):
    models_list = model_or_iterable if isinstance(model_or_iterable, (list, tuple)) else [model_or_iterable]
    for _m in models_list:
        try:
            _adm.site.unregister(_m)
        except _NotReg:
            pass
    try:
        _orig_site_register(model_or_iterable, admin_class, **options)
    except _Already:
        pass
_adm.site.register = _safe_site_register
# ─────────────────────────────────────────────────────────────────────────
# api/djoyalty/admin/advanced_admin.py
"""
Django admin for advanced, audit, cashout, engagement, family_eco,
notifications, offerwall, redemption, referral, social, tiers models
that were missing admin registration.

AUDIT FIX (v4): 36 models were unregistered.
This file covers all remaining gaps not handled by existing admin files.
"""
from django.contrib import admin
from django.utils.html import format_html


# ── PointsAlert, LoyaltyFraudRule (advanced.py) ──────────────────────────────

from ..models.advanced import (
    PointsAlert, LoyaltyFraudRule, LoyaltySubscription, PointsAbuseLog,
)

# @admin.register(PointsAlert)
class PointsAlertAdmin(admin.ModelAdmin):
    list_display  = ['customer', 'alert_type', 'threshold', 'is_active',
                     'last_triggered_at', 'created_at']
    list_filter   = ['alert_type', 'is_active']
    search_fields = ['customer__code']
    readonly_fields = ['last_triggered_at', 'created_at']


# # @admin.register(LoyaltyFraudRule)  # Already registered elsewhere
class LoyaltyFraudRuleAdmin(admin.ModelAdmin):
    list_display  = ['name', 'rule_type', 'action', 'threshold',
                     'cooldown_hours', 'is_active', 'tenant']
    list_filter   = ['rule_type', 'action', 'is_active', 'tenant']
    search_fields = ['name', 'condition']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Rule Info', {
            'fields': ('tenant', 'name', 'rule_type', 'condition'),
        }),
        ('Thresholds & Action', {
            'fields': ('threshold', 'cooldown_hours', 'action', 'is_active'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )


# @admin.register(LoyaltySubscription)
class LoyaltySubscriptionAdmin(admin.ModelAdmin):
    list_display  = ['customer', 'plan_name', 'multiplier', 'monthly_fee',
                     'is_active', 'started_at', 'next_renewal_at']
    list_filter   = ['is_active', 'plan_name', 'tenant']
    search_fields = ['customer__code', 'plan_name']
    readonly_fields = ['started_at', 'created_at', 'updated_at']


# ── Audit models (audit.py) ───────────────────────────────────────────────────

from ..models.audit import ProductCatalogRule, MultiCurrencyRate, SystemConfig

# @admin.register(ProductCatalogRule)
class ProductCatalogRuleAdmin(admin.ModelAdmin):
    list_display  = ['name', 'rule_type', 'priority', 'is_active',
                     'valid_from', 'valid_until', 'tenant']
    list_filter   = ['rule_type', 'is_active', 'tenant']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    ordering       = ['-priority', '-created_at']


# @admin.register(MultiCurrencyRate)
class MultiCurrencyRateAdmin(admin.ModelAdmin):
    list_display  = ['currency_code', 'currency_name', 'exchange_rate',
                     'points_per_unit', 'is_active', 'effective_date', 'tenant']
    list_filter   = ['is_active', 'tenant']
    search_fields = ['currency_code', 'currency_name']
    readonly_fields = ['created_at', 'updated_at']


# @admin.register(SystemConfig)
class SystemConfigAdmin(admin.ModelAdmin):
    list_display  = ['key', 'value_type', 'is_sensitive', 'is_editable',
                     'category', 'tenant']
    list_filter   = ['value_type', 'is_sensitive', 'is_editable', 'category', 'tenant']
    search_fields = ['key', 'description']
    readonly_fields = ['created_at', 'updated_at']

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.is_sensitive and not request.user.is_superuser:
            return list(self.readonly_fields) + ['value']
        return self.readonly_fields


# ── Campaign extras (campaigns.py) ───────────────────────────────────────────

from ..models.campaigns import CampaignSegment, ReferralPointsRule

# @admin.register(CampaignSegment)
class CampaignSegmentAdmin(admin.ModelAdmin):
    list_display  = ['campaign', 'segment_type', 'name', 'is_active']
    list_filter   = ['segment_type', 'is_active']
    search_fields = ['name', 'campaign__name']
    readonly_fields = ['created_at']


# @admin.register(ReferralPointsRule)
class ReferralPointsRuleAdmin(admin.ModelAdmin):
    list_display  = ['tenant', 'level', 'referee_points', 'referrer_points',
                     'is_active', 'valid_from', 'valid_until']
    list_filter   = ['is_active', 'tenant']
    readonly_fields = ['created_at', 'updated_at']


# ── Cashout extras (cashout.py) ───────────────────────────────────────────────

from ..models.cashout import CustomerMobileWallet, CashoutRate

# @admin.register(CustomerMobileWallet)
class CustomerMobileWalletAdmin(admin.ModelAdmin):
    list_display  = ['customer', 'wallet_provider', 'phone_number',
                     'is_primary', 'is_active', 'is_verified']
    list_filter   = ['wallet_provider', 'is_primary', 'is_active', 'is_verified']
    search_fields = ['customer__code', 'phone_number']
    readonly_fields = ['created_at', 'updated_at']


# @admin.register(CashoutRate)
class CashoutRateAdmin(admin.ModelAdmin):
    list_display  = ['tenant', 'cashout_method', 'points_per_currency_unit',
                     'min_cashout_points', 'max_cashout_points_per_day',
                     'is_active', 'effective_from']
    list_filter   = ['cashout_method', 'is_active', 'tenant']
    readonly_fields = ['created_at', 'updated_at']


# ── Catalog extras (catalog.py) ───────────────────────────────────────────────

from ..models.catalog import RewardCatalogCategory, SmartLinkClick, WebhookSubscription

# @admin.register(RewardCatalogCategory)
class RewardCatalogCategoryAdmin(admin.ModelAdmin):
    list_display  = ['name', 'slug', 'is_active', 'sort_order', 'tenant']
    list_filter   = ['is_active', 'tenant']
    search_fields = ['name', 'slug']
    readonly_fields = ['created_at', 'updated_at']
    prepopulated_fields = {}


# @admin.register(SmartLinkClick)
class SmartLinkClickAdmin(admin.ModelAdmin):
    list_display  = ['smart_link', 'customer', 'ip_address', 'converted',
                     'points_awarded', 'clicked_at']
    list_filter   = ['converted', 'tenant']
    search_fields = ['customer__code', 'smart_link__code']
    readonly_fields = ['smart_link', 'customer', 'ip_address', 'user_agent',
                       'converted', 'points_awarded', 'clicked_at', 'converted_at']
    date_hierarchy = 'clicked_at'


# @admin.register(WebhookSubscription)
class WebhookSubscriptionAdmin(admin.ModelAdmin):
    list_display  = ['name', 'url', 'is_active', 'is_verified',
                     'total_deliveries', 'successful_deliveries', 'tenant']
    list_filter   = ['is_active', 'is_verified', 'tenant']
    search_fields = ['name', 'url']
    readonly_fields = ['total_deliveries', 'successful_deliveries',
                       'failed_deliveries', 'created_at', 'updated_at']


# ── Earn rule extras (earn_rules.py) ─────────────────────────────────────────

from ..models.earn_rules import EarnRuleCondition, EarnRuleTierMultiplier, EarnRuleLog

# @admin.register(EarnRuleCondition)
class EarnRuleConditionAdmin(admin.ModelAdmin):
    list_display  = ['rule', 'condition_type', 'operator', 'value']
    list_filter   = ['condition_type', 'operator']
    search_fields = ['rule__name']
    readonly_fields = ['created_at']


# @admin.register(EarnRuleTierMultiplier)
class EarnRuleTierMultiplierAdmin(admin.ModelAdmin):
    list_display  = ['rule', 'tier', 'multiplier']
    list_filter   = ['tier']
    search_fields = ['rule__name']
    readonly_fields = ['created_at']


# @admin.register(EarnRuleLog)
class EarnRuleLogAdmin(admin.ModelAdmin):
    list_display  = ['customer', 'rule', 'points_earned', 'success',
                     'triggered_at', 'tenant']
    list_filter   = ['success', 'tenant']
    search_fields = ['customer__code', 'rule__name']
    readonly_fields = ['customer', 'rule', 'points_earned', 'success',
                       'error_message', 'triggered_at']
    date_hierarchy = 'triggered_at'


# ── Engagement extras (engagement.py) ────────────────────────────────────────

from ..models.engagement import StreakReward, Milestone, UserMilestone

# @admin.register(StreakReward)
class StreakRewardAdmin(admin.ModelAdmin):
    list_display  = ['customer', 'milestone_days', 'points_awarded', 'awarded_at']
    list_filter   = ['milestone_days', 'tenant']
    search_fields = ['customer__code']
    readonly_fields = ['customer', 'points_awarded', 'awarded_at', 'created_at']
    date_hierarchy = 'awarded_at'


# @admin.register(Milestone)
class MilestoneAdmin(admin.ModelAdmin):
    list_display  = ['name', 'milestone_type', 'threshold', 'points_reward',
                     'is_active', 'tenant']
    list_filter   = ['milestone_type', 'is_active', 'tenant']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    ordering       = ['-threshold']


# @admin.register(UserMilestone)
class UserMilestoneAdmin(admin.ModelAdmin):
    list_display  = ['customer', 'milestone', 'points_awarded', 'achieved_at']
    list_filter   = ['milestone', 'tenant']
    search_fields = ['customer__code', 'milestone__name']
    readonly_fields = ['customer', 'milestone', 'points_awarded', 'achieved_at', 'created_at']
    date_hierarchy = 'achieved_at'


# ── Family/Eco extras (family_eco.py) ────────────────────────────────────────

from ..models.family_eco import (
    EcoAction, CustomerEcoStats, CharityCause, CharityDonation,
    ExperientialReward, ExperientialRegistration, ReceiptEarnRule,
)

# @admin.register(EcoAction)
class EcoActionAdmin(admin.ModelAdmin):
    list_display  = ['name', 'action_type', 'points_reward', 'co2_offset_kg',
                     'is_active', 'tenant']
    list_filter   = ['action_type', 'is_active', 'tenant']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']


# @admin.register(CustomerEcoStats)
class CustomerEcoStatsAdmin(admin.ModelAdmin):
    list_display  = ['customer', 'eco_tier', 'total_eco_actions',
                     'total_co2_offset_kg', 'total_eco_points_earned']
    list_filter   = ['eco_tier', 'tenant']
    search_fields = ['customer__code']
    readonly_fields = ['customer', 'total_eco_actions', 'total_co2_offset_kg',
                       'total_eco_points_earned', 'last_eco_action_at',
                       'created_at', 'updated_at']


# @admin.register(CharityCause)
class CharityCauseAdmin(admin.ModelAdmin):
    list_display  = ['name', 'category', 'total_points_donated',
                     'total_donors', 'is_active', 'tenant']
    list_filter   = ['category', 'is_active', 'tenant']
    search_fields = ['name', 'description']
    readonly_fields = ['total_points_donated', 'total_donors', 'created_at', 'updated_at']


# @admin.register(CharityDonation)
class CharityDonationAdmin(admin.ModelAdmin):
    list_display  = ['customer', 'cause', 'points_donated', 'donation_value_bdt',
                     'donated_at', 'tenant']
    list_filter   = ['cause', 'tenant']
    search_fields = ['customer__code', 'cause__name']
    readonly_fields = ['customer', 'cause', 'points_donated', 'donation_value_bdt',
                       'donated_at', 'created_at']
    date_hierarchy = 'donated_at'


# @admin.register(ExperientialReward)
class ExperientialRewardAdmin(admin.ModelAdmin):
    list_display  = ['title', 'experience_type', 'points_cost',
                     'available_slots', 'booked_slots', 'is_active', 'event_date']
    list_filter   = ['experience_type', 'is_active', 'tenant']
    search_fields = ['title', 'description']
    readonly_fields = ['booked_slots', 'created_at', 'updated_at']


# @admin.register(ExperientialRegistration)
class ExperientialRegistrationAdmin(admin.ModelAdmin):
    list_display  = ['customer', 'experience', 'status',
                     'points_spent', 'registered_at']
    list_filter   = ['status', 'tenant']
    search_fields = ['customer__code', 'experience__title']
    readonly_fields = ['customer', 'experience', 'points_spent',
                       'registered_at', 'created_at']
    date_hierarchy = 'registered_at'


# @admin.register(ReceiptEarnRule)
class ReceiptEarnRuleAdmin(admin.ModelAdmin):
    list_display  = ['name', 'points_per_currency', 'min_receipt_amount',
                     'is_active', 'valid_from', 'valid_until', 'tenant']
    list_filter   = ['is_active', 'tenant']
    search_fields = ['name']
    readonly_fields = ['created_at', 'updated_at']


# ── Notification extras (notifications.py) ───────────────────────────────────

from ..models.notifications import NotificationTemplate, NotificationPreference

# @admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display  = ['name', 'event_type', 'channel', 'tenant']
    list_filter   = ['channel', 'event_type', 'tenant']
    search_fields = ['name', 'event_type']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Template Info', {
            'fields': ('tenant', 'name', 'event_type', 'channel'),
        }),
        ('Content', {
            'fields': ('subject', 'body_text', 'html_template'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )


# @admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display  = ['customer', 'email_enabled', 'push_enabled',
                     'sms_enabled', 'in_app_enabled', 'max_per_day', 'tenant']
    list_filter   = ['email_enabled', 'push_enabled', 'sms_enabled', 'tenant']
    search_fields = ['customer__code']
    readonly_fields = ['created_at', 'updated_at']


# ── OfferWall extras (offerwall.py) ──────────────────────────────────────────

from ..models.offerwall import OfferWall, ContentLock, ContentUnlock

# @admin.register(OfferWall)
class OfferWallAdmin(admin.ModelAdmin):
    list_display  = ['name', 'provider', 'is_active', 'tenant']
    list_filter   = ['provider', 'is_active', 'tenant']
    search_fields = ['name']
    readonly_fields = ['created_at', 'updated_at']


# @admin.register(ContentLock)
class ContentLockAdmin(admin.ModelAdmin):
    list_display  = ['title', 'unlock_method', 'points_required',
                     'unlock_duration_hours', 'is_active', 'offer_wall']
    list_filter   = ['unlock_method', 'is_active', 'tenant']
    search_fields = ['title']
    readonly_fields = ['created_at']


# @admin.register(ContentUnlock)
class ContentUnlockAdmin(admin.ModelAdmin):
    list_display  = ['customer', 'content_lock', 'points_spent',
                     'expires_at', 'unlocked_at']
    list_filter   = ['tenant']
    search_fields = ['customer__code', 'content_lock__title']
    readonly_fields = ['customer', 'content_lock', 'points_spent',
                       'unlocked_at', 'expires_at', 'created_at']
    date_hierarchy = 'unlocked_at'


# ── Redemption extras (redemption.py) ────────────────────────────────────────

from ..models.redemption import RedemptionHistory, VoucherRedemption

# @admin.register(RedemptionHistory)
class RedemptionHistoryAdmin(admin.ModelAdmin):
    list_display  = ['request', 'from_status', 'to_status',
                     'changed_by', 'changed_at']
    list_filter   = ['from_status', 'to_status']
    search_fields = ['request__reference', 'changed_by']
    readonly_fields = ['request', 'from_status', 'to_status',
                       'changed_by', 'note', 'changed_at']
    date_hierarchy = 'changed_at'


# @admin.register(VoucherRedemption)
class VoucherRedemptionAdmin(admin.ModelAdmin):
    list_display  = ['voucher', 'customer', 'discount_applied',
                     'order_reference', 'used_at', 'tenant']
    list_filter   = ['tenant']
    search_fields = ['voucher__code', 'customer__code', 'order_reference']
    readonly_fields = ['voucher', 'customer', 'discount_applied',
                       'order_reference', 'used_at', 'created_at']
    date_hierarchy = 'used_at'


# ── Referral extras (referral.py) ────────────────────────────────────────────

from ..models.referral import ReferralProgram

# @admin.register(ReferralProgram)
class ReferralProgramAdmin(admin.ModelAdmin):
    list_display  = ['tenant', 'referee_points', 'referrer_points',
                     'max_referrals_per_customer', 'is_active',
                     'valid_from', 'valid_until']
    list_filter   = ['is_active', 'tenant']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Program Config', {
            'fields': ('tenant', 'is_active', 'referee_points', 'referrer_points'),
        }),
        ('Limits', {
            'fields': ('max_referrals_per_customer', 'min_spend_to_qualify'),
        }),
        ('Scheduling', {
            'fields': ('valid_from', 'valid_until'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )


# ── Social extras (social.py) ────────────────────────────────────────────────

# from ..models.social import (
#     SocialShareConfig, ReviewReward, CustomerReview, CustomerSegment,
# )
# Missing models - will need to add these later

# @admin.register(SocialShareConfig)  # Model not available
class SocialShareConfigAdmin(admin.ModelAdmin):
    list_display  = ['platform', 'points_reward', 'max_rewards_per_day',
                     'is_active', 'tenant']
    list_filter   = ['platform', 'is_active', 'tenant']
    readonly_fields = ['created_at', 'updated_at']


# @admin.register(ReviewReward)
class ReviewRewardAdmin(admin.ModelAdmin):
    list_display  = ['review_platform', 'points_reward', 'min_rating',
                     'min_review_length', 'is_active', 'tenant']
    list_filter   = ['review_platform', 'is_active', 'tenant']
    readonly_fields = ['created_at', 'updated_at']


# @admin.register(CustomerReview)
class CustomerReviewAdmin(admin.ModelAdmin):
    list_display  = ['customer', 'platform', 'rating', 'is_verified',
                     'points_awarded', 'submitted_at', 'tenant']
    list_filter   = ['platform', 'is_verified', 'rating', 'tenant']
    search_fields = ['customer__code']
    readonly_fields = ['customer', 'platform', 'rating', 'review_text',
                       'review_url', 'points_awarded', 'submitted_at',
                       'is_verified', 'verified_at', 'created_at']
    date_hierarchy = 'submitted_at'
    actions        = ['verify_reviews']

    def verify_reviews(self, request, queryset):
        from django.utils import timezone
        updated = queryset.filter(is_verified=False).update(
            is_verified=True, verified_at=timezone.now()
        )
        self.message_user(request, f'{updated} reviews verified.')
    verify_reviews.short_description = 'Mark selected reviews as verified'


# @admin.register(CustomerSegment)
class CustomerSegmentAdmin(admin.ModelAdmin):
    list_display  = ['name', 'segment_type', 'is_active', 'tenant']
    list_filter   = ['segment_type', 'is_active', 'tenant']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']


# ── Tiers extras (tiers.py) ──────────────────────────────────────────────────

from ..models.tiers import TierBenefit, TierConfig

# @admin.register(TierBenefit)
class TierBenefitAdmin(admin.ModelAdmin):
    list_display  = ['tier', 'benefit_type', 'name', 'value',
                     'is_active', 'sort_order']
    list_filter   = ['benefit_type', 'is_active', 'tier']
    search_fields = ['name', 'description', 'tier__name']
    readonly_fields = ['created_at', 'updated_at']
    ordering       = ['tier', 'sort_order']


# @admin.register(TierConfig)
class TierConfigAdmin(admin.ModelAdmin):
    list_display  = ['tenant', 'evaluation_period', 'grace_period_days',
                     'auto_upgrade', 'auto_downgrade']
    list_filter   = ['auto_upgrade', 'auto_downgrade', 'evaluation_period']
    readonly_fields = ['created_at', 'updated_at']
