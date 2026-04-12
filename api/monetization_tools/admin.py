"""
api/monetization_tools/admin.py
=================================
Django Admin registration for all monetization_tools models.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.db.models import Sum

from .models import (
    AdCampaign, AdUnit, AdNetwork, AdPlacement,
    Offerwall, Offer, OfferCompletion, RewardTransaction,
    ImpressionLog, ClickLog, ConversionLog, RevenueDailySummary,
    SubscriptionPlan, UserSubscription, InAppPurchase,
    PaymentTransaction, RecurringBilling,
    UserLevel, Achievement, LeaderboardRank, SpinWheelLog,
    ABTest, WaterfallConfig, FloorPriceConfig,
)


# ===========================================================================
# Helpers
# ===========================================================================

class TenantFilter(admin.SimpleListFilter):
    title = _('Tenant')
    parameter_name = 'tenant'

    def lookups(self, request, model_admin):
        from api.tenants.models import Tenant
        return [(t.id, str(t)) for t in Tenant.objects.all()]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(tenant_id=self.value())
        return queryset


# ===========================================================================
# 1. AD CAMPAIGN & UNIT
# ===========================================================================

@admin.register(AdCampaign)
class AdCampaignAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'status', 'pricing_model',
        'total_budget', 'spent_budget', 'remaining_budget_display',
        'total_impressions', 'total_clicks', 'ctr_display', 'start_date',
    ]
    list_filter  = ['status', 'pricing_model', TenantFilter]
    search_fields = ['name', 'advertiser_name', 'advertiser_email']
    readonly_fields = ['campaign_id', 'spent_budget', 'total_impressions',
                       'total_clicks', 'total_conversions', 'created_at', 'updated_at']
    date_hierarchy = 'start_date'

    def remaining_budget_display(self, obj):
        return f"${obj.remaining_budget:,.2f}"
    remaining_budget_display.short_description = _('Remaining')

    def ctr_display(self, obj):
        return f"{obj.ctr}%"
    ctr_display.short_description = 'CTR'

    fieldsets = (
        (_('Identity'), {'fields': ('campaign_id', 'name', 'description', 'advertiser_name', 'advertiser_email')}),
        (_('Budget'),   {'fields': ('total_budget', 'daily_budget', 'spent_budget', 'pricing_model', 'bid_amount')}),
        (_('Targeting'),{'fields': ('target_countries', 'target_cities', 'target_languages', 'target_devices', 'target_os')}),
        (_('Duration'), {'fields': ('start_date', 'end_date', 'status')}),
        (_('Stats'),    {'fields': ('total_impressions', 'total_clicks', 'total_conversions')}),
        (_('Meta'),     {'fields': ('tenant', 'created_at', 'updated_at')}),
    )


@admin.register(AdUnit)
class AdUnitAdmin(admin.ModelAdmin):
    list_display  = ['name', 'campaign', 'ad_format', 'is_active', 'created_at']
    list_filter   = ['ad_format', 'is_active', TenantFilter]
    search_fields = ['name', 'campaign__name']
    raw_id_fields = ['campaign']


# ===========================================================================
# 2. AD NETWORK & PLACEMENT
# ===========================================================================

@admin.register(AdNetwork)
class AdNetworkAdmin(admin.ModelAdmin):
    list_display  = ['display_name', 'network_type', 'is_active', 'priority']
    list_filter   = ['is_active', 'network_type']
    search_fields = ['display_name', 'network_type']
    ordering      = ['priority']


@admin.register(AdPlacement)
class AdPlacementAdmin(admin.ModelAdmin):
    list_display  = ['screen_name', 'position', 'ad_unit', 'ad_network', 'is_active']
    list_filter   = ['position', 'is_active', TenantFilter]
    search_fields = ['screen_name']
    raw_id_fields = ['ad_unit', 'ad_network']


# ===========================================================================
# 3. OFFERWALL & OFFER
# ===========================================================================

@admin.register(Offerwall)
class OfferwallAdmin(admin.ModelAdmin):
    list_display  = ['name', 'network', 'is_active', 'is_featured', 'sort_order']
    list_filter   = ['is_active', 'is_featured', TenantFilter]
    search_fields = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Offer)
class OfferAdmin(admin.ModelAdmin):
    list_display  = [
        'title', 'offerwall', 'offer_type', 'status',
        'point_value', 'payout_usd', 'total_completions',
        'is_featured', 'is_hot', 'expiry_date',
    ]
    list_filter   = ['offer_type', 'status', 'is_featured', 'is_hot', TenantFilter]
    search_fields = ['title', 'external_offer_id']
    readonly_fields = ['total_completions', 'conversion_rate', 'created_at', 'updated_at']
    raw_id_fields = ['offerwall']
    date_hierarchy = 'created_at'


@admin.register(OfferCompletion)
class OfferCompletionAdmin(admin.ModelAdmin):
    list_display  = [
        'transaction_id_short', 'user', 'offer', 'status',
        'reward_amount', 'fraud_score', 'clicked_at',
    ]
    list_filter   = ['status', TenantFilter]
    search_fields = ['user__username', 'offer__title', 'transaction_id', 'ip_address']
    readonly_fields = [
        'transaction_id', 'fraud_score', 'fraud_reason',
        'created_at', 'updated_at',
    ]
    raw_id_fields = ['user', 'offer']
    actions       = ['approve_selected', 'reject_selected']

    def transaction_id_short(self, obj):
        return str(obj.transaction_id)[:8] + '...'
    transaction_id_short.short_description = 'Txn ID'

    @admin.action(description=_('Approve selected completions'))
    def approve_selected(self, request, queryset):
        from .services import OfferService
        count = 0
        for c in queryset.filter(status='pending'):
            try:
                OfferService.approve_completion(c)
                count += 1
            except Exception:
                pass
        self.message_user(request, f"{count} completions approved.")

    @admin.action(description=_('Reject selected completions'))
    def reject_selected(self, request, queryset):
        from .services import OfferService
        for c in queryset.filter(status='pending'):
            OfferService.reject_completion(c, 'Bulk admin rejection')
        self.message_user(request, "Selected completions rejected.")


@admin.register(RewardTransaction)
class RewardTransactionAdmin(admin.ModelAdmin):
    list_display  = ['user', 'transaction_type', 'amount', 'balance_after', 'created_at']
    list_filter   = ['transaction_type', TenantFilter]
    search_fields = ['user__username', 'transaction_id']
    readonly_fields = ['transaction_id', 'created_at']
    raw_id_fields = ['user']


# ===========================================================================
# 4. REVENUE TRACKING
# ===========================================================================

@admin.register(ImpressionLog)
class ImpressionLogAdmin(admin.ModelAdmin):
    list_display  = ['ad_unit', 'country', 'ecpm', 'revenue', 'is_viewable', 'logged_at']
    list_filter   = ['is_viewable', 'country']
    date_hierarchy = 'logged_at'
    raw_id_fields = ['ad_unit', 'user']


@admin.register(ClickLog)
class ClickLogAdmin(admin.ModelAdmin):
    list_display  = ['ad_unit', 'country', 'revenue', 'is_valid', 'clicked_at']
    list_filter   = ['is_valid', 'country']
    date_hierarchy = 'clicked_at'


@admin.register(ConversionLog)
class ConversionLogAdmin(admin.ModelAdmin):
    list_display  = ['campaign', 'conversion_type', 'payout', 'is_verified', 'converted_at']
    list_filter   = ['conversion_type', 'is_verified']
    date_hierarchy = 'converted_at'


@admin.register(RevenueDailySummary)
class RevenueDailySummaryAdmin(admin.ModelAdmin):
    list_display  = [
        'date', 'ad_network', 'country',
        'impressions', 'clicks', 'conversions',
        'total_revenue', 'ecpm', 'ctr',
    ]
    list_filter   = ['ad_network', 'country', TenantFilter]
    date_hierarchy = 'date'
    readonly_fields = ['created_at', 'updated_at']


# ===========================================================================
# 5. SUBSCRIPTION & PAYMENT
# ===========================================================================

@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display  = ['name', 'price', 'currency', 'interval', 'trial_days', 'is_active', 'is_popular']
    list_filter   = ['interval', 'is_active', 'is_popular']
    search_fields = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display  = ['user', 'plan', 'status', 'current_period_end', 'is_auto_renew']
    list_filter   = ['status', 'is_auto_renew', TenantFilter]
    search_fields = ['user__username', 'subscription_id']
    readonly_fields = ['subscription_id', 'created_at', 'updated_at']
    raw_id_fields = ['user', 'plan']


@admin.register(InAppPurchase)
class InAppPurchaseAdmin(admin.ModelAdmin):
    list_display  = ['user', 'product_name', 'amount', 'currency', 'status', 'purchased_at']
    list_filter   = ['status', 'gateway', TenantFilter]
    search_fields = ['user__username', 'product_id', 'purchase_id']
    readonly_fields = ['purchase_id', 'purchased_at', 'fulfilled_at']


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display  = ['user', 'gateway', 'amount', 'currency', 'status', 'purpose', 'initiated_at']
    list_filter   = ['gateway', 'status', 'purpose', TenantFilter]
    search_fields = ['user__username', 'txn_id', 'gateway_txn_id']
    readonly_fields = ['txn_id', 'initiated_at', 'completed_at']
    raw_id_fields = ['user']


@admin.register(RecurringBilling)
class RecurringBillingAdmin(admin.ModelAdmin):
    list_display  = ['subscription', 'scheduled_at', 'amount', 'status', 'attempt_count']
    list_filter   = ['status', TenantFilter]
    date_hierarchy = 'scheduled_at'


# ===========================================================================
# 6. GAMIFICATION
# ===========================================================================

@admin.register(UserLevel)
class UserLevelAdmin(admin.ModelAdmin):
    list_display  = ['user', 'current_level', 'current_xp', 'total_xp_earned']
    search_fields = ['user__username']
    readonly_fields = ['updated_at']


@admin.register(Achievement)
class AchievementAdmin(admin.ModelAdmin):
    list_display  = ['user', 'title', 'category', 'xp_reward', 'coin_reward', 'unlocked_at']
    list_filter   = ['category', TenantFilter]
    search_fields = ['user__username', 'achievement_key', 'title']
    readonly_fields = ['unlocked_at']


@admin.register(LeaderboardRank)
class LeaderboardRankAdmin(admin.ModelAdmin):
    list_display  = ['rank', 'user', 'scope', 'board_type', 'score', 'period_label', 'calculated_at']
    list_filter   = ['scope', 'board_type']
    search_fields = ['user__username']
    ordering      = ['rank']


@admin.register(SpinWheelLog)
class SpinWheelLogAdmin(admin.ModelAdmin):
    list_display  = ['user', 'log_type', 'prize_type', 'prize_value', 'is_credited', 'played_at']
    list_filter   = ['log_type', 'prize_type', 'is_credited', TenantFilter]
    search_fields = ['user__username']
    readonly_fields = ['played_at']


# ===========================================================================
# 7. A/B TESTING & OPTIMIZATION
# ===========================================================================

@admin.register(ABTest)
class ABTestAdmin(admin.ModelAdmin):
    list_display  = ['name', 'status', 'winner_criteria', 'traffic_split', 'started_at', 'ended_at']
    list_filter   = ['status', 'winner_criteria', TenantFilter]
    search_fields = ['name', 'test_id']
    readonly_fields = ['test_id', 'started_at', 'ended_at', 'winner_variant',
                       'results_summary', 'created_at', 'updated_at']


@admin.register(WaterfallConfig)
class WaterfallConfigAdmin(admin.ModelAdmin):
    list_display  = ['ad_unit', 'ad_network', 'priority', 'floor_ecpm', 'timeout_ms', 'is_active']
    list_filter   = ['is_active', 'ad_network']
    raw_id_fields = ['ad_unit', 'ad_network']
    ordering      = ['ad_unit', 'priority']


@admin.register(FloorPriceConfig)
class FloorPriceConfigAdmin(admin.ModelAdmin):
    list_display  = ['ad_network', 'ad_unit', 'country', 'device_type', 'ad_format', 'floor_ecpm', 'is_active']
    list_filter   = ['is_active', 'ad_network', 'country']
    search_fields = ['country', 'device_type']
    raw_id_fields = ['ad_network', 'ad_unit']


# ============================================================================
# NEW ADMIN REGISTRATIONS  (Phase-2 models)
# ============================================================================

from .models import (
    AdPerformanceHourly, AdPerformanceDaily, AdNetworkDailyStat,
    PointLedgerSnapshot, ABTestAssignment, MonetizationConfig, AdCreative,
    UserSegment, UserSegmentMembership, PostbackLog,
    PayoutMethod, PayoutRequest, ReferralProgram, ReferralLink, ReferralCommission,
    DailyStreak, SpinWheelConfig, PrizeConfig, FlashSale,
    Coupon, CouponUsage, FraudAlert, RevenueGoal, PublisherAccount,
    MonetizationNotificationTemplate,
)


@admin.register(AdPerformanceHourly)
class AdPerformanceHourlyAdmin(admin.ModelAdmin):
    list_display  = ['ad_unit', 'ad_network', 'hour_bucket', 'country',
                     'impressions', 'clicks', 'revenue_usd', 'ecpm', 'fill_rate', 'ctr']
    list_filter   = ['ad_network', 'country', 'device_type']
    search_fields = ['ad_unit__name']
    date_hierarchy = None
    readonly_fields = ['created_at', 'updated_at']


@admin.register(AdPerformanceDaily)
class AdPerformanceDailyAdmin(admin.ModelAdmin):
    list_display  = ['date', 'ad_unit', 'ad_network', 'country',
                     'impressions', 'clicks', 'total_revenue', 'ecpm', 'fill_rate', 'ctr']
    list_filter   = ['ad_network', 'country', 'device_type']
    search_fields = ['ad_unit__name', 'campaign__name']
    date_hierarchy = 'date'
    readonly_fields = ['created_at', 'updated_at']


@admin.register(AdNetworkDailyStat)
class AdNetworkDailyStatAdmin(admin.ModelAdmin):
    list_display  = ['date', 'ad_network', 'reported_revenue', 'reported_ecpm',
                     'reported_impressions', 'fill_rate', 'discrepancy_pct']
    list_filter   = ['ad_network']
    date_hierarchy = 'date'
    readonly_fields = ['fetched_at', 'created_at', 'updated_at']


@admin.register(PointLedgerSnapshot)
class PointLedgerSnapshotAdmin(admin.ModelAdmin):
    list_display  = ['user', 'snapshot_date', 'balance', 'total_earned', 'total_spent']
    list_filter   = ['snapshot_date']
    search_fields = ['user__username']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(ABTestAssignment)
class ABTestAssignmentAdmin(admin.ModelAdmin):
    list_display  = ['test', 'user', 'variant_name', 'converted', 'assigned_at']
    list_filter   = ['test', 'variant_name', 'converted']
    search_fields = ['user__username', 'test__name']
    readonly_fields = ['assigned_at', 'created_at', 'updated_at']


@admin.register(MonetizationConfig)
class MonetizationConfigAdmin(admin.ModelAdmin):
    list_display  = ['tenant', 'offerwall_enabled', 'subscription_enabled',
                     'spin_wheel_enabled', 'referral_enabled', 'coins_per_usd']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        (_('Tenant'),       {'fields': ('tenant',)}),
        (_('Coin Economy'), {'fields': ('coins_per_usd', 'min_withdrawal_coins',
                                        'max_withdrawal_coins', 'min_withdrawal_usd',
                                        'coin_expiry_days', 'default_currency')}),
        (_('Feature Flags'), {'fields': ('offerwall_enabled', 'subscription_enabled',
                                          'spin_wheel_enabled', 'scratch_card_enabled',
                                          'referral_enabled', 'ab_testing_enabled',
                                          'flash_sale_enabled', 'coupon_enabled',
                                          'daily_streak_enabled')}),
        (_('Limits'),       {'fields': ('max_offers_per_day', 'spin_wheel_daily_limit',
                                         'scratch_card_daily_limit', 'max_pending_withdrawals',
                                         'max_devices_per_user')}),
        (_('Fraud'),        {'fields': ('fraud_auto_reject_score', 'fraud_flag_score',
                                         'postback_secret')}),
        (_('Referral'),     {'fields': ('referral_commission_pct', 'referral_bonus_coins',
                                         'referral_max_levels')}),
    )


@admin.register(AdCreative)
class AdCreativeAdmin(admin.ModelAdmin):
    list_display  = ['name', 'ad_unit', 'creative_type', 'status',
                     'impressions', 'clicks', 'is_active', 'created_at']
    list_filter   = ['creative_type', 'status', 'is_active', TenantFilter]
    search_fields = ['name', 'ad_unit__name']
    readonly_fields = ['creative_id', 'impressions', 'clicks', 'revenue', 'created_at', 'updated_at']
    actions = ['approve_creatives', 'reject_creatives']

    @admin.action(description=_('Approve selected creatives'))
    def approve_creatives(self, request, queryset):
        queryset.update(status='approved', reviewed_by=request.user)

    @admin.action(description=_('Reject selected creatives'))
    def reject_creatives(self, request, queryset):
        queryset.update(status='rejected', reviewed_by=request.user)


@admin.register(UserSegment)
class UserSegmentAdmin(admin.ModelAdmin):
    list_display  = ['name', 'segment_type', 'member_count', 'is_active', 'is_dynamic', 'last_computed']
    list_filter   = ['segment_type', 'is_active', 'is_dynamic']
    search_fields = ['name', 'slug']
    readonly_fields = ['member_count', 'last_computed', 'created_at', 'updated_at']


@admin.register(UserSegmentMembership)
class UserSegmentMembershipAdmin(admin.ModelAdmin):
    list_display  = ['user', 'segment', 'score', 'added_at', 'expires_at']
    list_filter   = ['segment']
    search_fields = ['user__username', 'segment__name']
    readonly_fields = ['added_at', 'created_at', 'updated_at']


@admin.register(PostbackLog)
class PostbackLogAdmin(admin.ModelAdmin):
    list_display  = ['postback_id_short', 'network_name', 'status', 'source_ip',
                     'signature_valid', 'reward_amount', 'received_at', 'processing_time_ms']
    list_filter   = ['status', 'network_name', 'signature_valid']
    search_fields = ['network_txn_id', 'source_ip', 'postback_id']
    readonly_fields = ['postback_id', 'received_at', 'processed_at', 'created_at', 'updated_at']
    date_hierarchy = None

    def postback_id_short(self, obj):
        return str(obj.postback_id)[:8] + '...'
    postback_id_short.short_description = 'ID'


@admin.register(PayoutMethod)
class PayoutMethodAdmin(admin.ModelAdmin):
    list_display  = ['user', 'method_type', 'account_number', 'currency',
                     'is_default', 'is_verified', 'is_active']
    list_filter   = ['method_type', 'is_verified', 'is_active', TenantFilter]
    search_fields = ['user__username', 'account_number', 'account_name']
    readonly_fields = ['verified_at', 'created_at', 'updated_at']

    @admin.action(description=_('Verify selected payout methods'))
    def verify_methods(self, request, queryset):
        from django.utils import timezone
        queryset.update(is_verified=True, verified_at=timezone.now())


@admin.register(PayoutRequest)
class PayoutRequestAdmin(admin.ModelAdmin):
    list_display  = ['request_id_short', 'user', 'amount_local', 'currency',
                     'net_amount', 'status', 'created_at']
    list_filter   = ['status', TenantFilter]
    search_fields = ['user__username', 'request_id', 'gateway_reference']
    readonly_fields = ['request_id', 'reviewed_by', 'reviewed_at', 'paid_at',
                        'created_at', 'updated_at']
    date_hierarchy = 'created_at'
    actions = ['approve_payouts', 'reject_payouts']

    def request_id_short(self, obj):
        return str(obj.request_id)[:8] + '...'
    request_id_short.short_description = 'Request ID'

    @admin.action(description=_('Approve selected payout requests'))
    def approve_payouts(self, request, queryset):
        from django.utils import timezone
        queryset.filter(status='pending').update(
            status='approved', reviewed_by=request.user, reviewed_at=timezone.now()
        )

    @admin.action(description=_('Reject selected payout requests'))
    def reject_payouts(self, request, queryset):
        from django.utils import timezone
        queryset.filter(status='pending').update(
            status='rejected', reviewed_by=request.user, reviewed_at=timezone.now()
        )


@admin.register(ReferralProgram)
class ReferralProgramAdmin(admin.ModelAdmin):
    list_display  = ['name', 'is_active', 'l1_commission_pct', 'referrer_bonus_coins',
                     'referee_bonus_coins', 'max_levels']
    list_filter   = ['is_active', TenantFilter]
    search_fields = ['name', 'slug']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(ReferralLink)
class ReferralLinkAdmin(admin.ModelAdmin):
    list_display  = ['user', 'program', 'code', 'total_clicks', 'total_signups',
                     'total_conversions', 'total_earned', 'is_active']
    list_filter   = ['program', 'is_active', TenantFilter]
    search_fields = ['user__username', 'code']
    readonly_fields = ['code', 'total_clicks', 'total_signups', 'total_conversions',
                        'total_earned', 'created_at', 'updated_at']


@admin.register(ReferralCommission)
class ReferralCommissionAdmin(admin.ModelAdmin):
    list_display  = ['referrer', 'referee', 'level', 'commission_type',
                     'commission_coins', 'is_paid', 'created_at']
    list_filter   = ['level', 'commission_type', 'is_paid', TenantFilter]
    search_fields = ['referrer__username', 'referee__username']
    readonly_fields = ['created_at', 'updated_at']
    actions = ['mark_paid']

    @admin.action(description=_('Mark selected commissions as paid'))
    def mark_paid(self, request, queryset):
        from django.utils import timezone
        queryset.filter(is_paid=False).update(is_paid=True, paid_at=timezone.now())


@admin.register(DailyStreak)
class DailyStreakAdmin(admin.ModelAdmin):
    list_display  = ['user', 'current_streak', 'longest_streak', 'last_login_date',
                     'total_logins', 'today_claimed', 'total_streak_coins']
    list_filter   = ['today_claimed', TenantFilter]
    search_fields = ['user__username']
    readonly_fields = ['current_streak', 'longest_streak', 'last_login_date',
                        'streak_start_date', 'total_logins', 'today_claimed',
                        'total_streak_coins', 'last_reward_date', 'created_at', 'updated_at']


@admin.register(SpinWheelConfig)
class SpinWheelConfigAdmin(admin.ModelAdmin):
    list_display  = ['name', 'wheel_type', 'is_active', 'daily_limit', 'cost_per_spin',
                     'valid_from', 'valid_until']
    list_filter   = ['wheel_type', 'is_active', TenantFilter]
    search_fields = ['name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(PrizeConfig)
class PrizeConfigAdmin(admin.ModelAdmin):
    list_display  = ['label', 'wheel_config', 'prize_type', 'prize_value',
                     'weight', 'is_jackpot', 'is_active']
    list_filter   = ['wheel_config', 'prize_type', 'is_jackpot', 'is_active']
    search_fields = ['label']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(FlashSale)
class FlashSaleAdmin(admin.ModelAdmin):
    list_display  = ['name', 'sale_type', 'multiplier', 'bonus_coins', 'discount_pct',
                     'starts_at', 'ends_at', 'is_active', 'total_participants']
    list_filter   = ['sale_type', 'is_active', TenantFilter]
    search_fields = ['name', 'slug']
    readonly_fields = ['total_participants', 'total_coins_given', 'created_at', 'updated_at']
    date_hierarchy = 'starts_at'
    filter_horizontal = ['target_segments']


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display  = ['code', 'name', 'coupon_type', 'coin_amount', 'discount_pct',
                     'current_uses', 'max_uses', 'is_active', 'valid_until']
    list_filter   = ['coupon_type', 'is_active', TenantFilter]
    search_fields = ['code', 'name']
    readonly_fields = ['current_uses', 'created_at', 'updated_at']


@admin.register(CouponUsage)
class CouponUsageAdmin(admin.ModelAdmin):
    list_display  = ['user', 'coupon', 'coins_granted', 'discount_applied', 'used_at']
    list_filter   = ['coupon__coupon_type', TenantFilter]
    search_fields = ['user__username', 'coupon__code']
    readonly_fields = ['used_at', 'created_at', 'updated_at']


@admin.register(FraudAlert)
class FraudAlertAdmin(admin.ModelAdmin):
    list_display  = ['alert_id_short', 'user', 'alert_type', 'severity', 'resolution',
                     'fraud_score', 'user_blocked', 'created_at']
    list_filter   = ['alert_type', 'severity', 'resolution', TenantFilter]
    search_fields = ['user__username', 'alert_id']
    readonly_fields = ['alert_id', 'resolved_by', 'resolved_at', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'
    actions = ['mark_confirmed', 'mark_cleared']

    def alert_id_short(self, obj):
        return str(obj.alert_id)[:8] + '...'
    alert_id_short.short_description = 'Alert ID'

    @admin.action(description=_('Mark as confirmed fraud'))
    def mark_confirmed(self, request, queryset):
        from django.utils import timezone
        queryset.update(resolution='confirmed', resolved_by=request.user, resolved_at=timezone.now())

    @admin.action(description=_('Mark as cleared (false positive)'))
    def mark_cleared(self, request, queryset):
        from django.utils import timezone
        queryset.update(resolution='cleared', resolved_by=request.user, resolved_at=timezone.now())


@admin.register(RevenueGoal)
class RevenueGoalAdmin(admin.ModelAdmin):
    list_display  = ['name', 'period', 'goal_type', 'target_value', 'current_value',
                     'currency', 'period_start', 'period_end', 'is_active']
    list_filter   = ['period', 'goal_type', 'is_active', TenantFilter]
    search_fields = ['name']
    readonly_fields = ['current_value', 'created_at', 'updated_at']
    date_hierarchy = 'period_start'


@admin.register(PublisherAccount)
class PublisherAccountAdmin(admin.ModelAdmin):
    list_display  = ['company_name', 'account_type', 'status', 'email', 'country',
                     'is_verified', 'total_spend_usd', 'total_revenue_usd', 'created_at']
    list_filter   = ['account_type', 'status', 'is_verified', TenantFilter]
    search_fields = ['company_name', 'email', 'account_id']
    readonly_fields = ['account_id', 'total_spend_usd', 'total_revenue_usd',
                        'current_balance_usd', 'verified_at', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'
    actions = ['verify_accounts', 'suspend_accounts']

    @admin.action(description=_('Verify and activate selected accounts'))
    def verify_accounts(self, request, queryset):
        from django.utils import timezone
        queryset.update(is_verified=True, status='active', verified_at=timezone.now())

    @admin.action(description=_('Suspend selected accounts'))
    def suspend_accounts(self, request, queryset):
        queryset.update(status='suspended')


@admin.register(MonetizationNotificationTemplate)
class MonetizationNotificationTemplateAdmin(admin.ModelAdmin):
    list_display  = ['name', 'event_type', 'channel', 'language', 'is_active']
    list_filter   = ['event_type', 'channel', 'language', 'is_active', TenantFilter]
    search_fields = ['name', 'event_type']
    readonly_fields = ['created_at', 'updated_at']



def _force_register_monetization_tools():
    try:
        from api.admin_panel.admin import admin_site as modern_site
        if modern_site is None:
            return
        from django.contrib import admin as default_admin
        pairs = [
            (AdCampaign, AdCampaignAdmin),(AdUnit, AdUnitAdmin),(AdNetwork, AdNetworkAdmin),
            (AdPlacement, AdPlacementAdmin),(Offerwall, OfferwallAdmin),(Offer, OfferAdmin),
            (OfferCompletion, OfferCompletionAdmin),(RewardTransaction, RewardTransactionAdmin),
            (ImpressionLog, ImpressionLogAdmin),(ClickLog, ClickLogAdmin),
            (ConversionLog, ConversionLogAdmin),(RevenueDailySummary, RevenueDailySummaryAdmin),
            (SubscriptionPlan, SubscriptionPlanAdmin),(UserSubscription, UserSubscriptionAdmin),
            (InAppPurchase, InAppPurchaseAdmin),(PaymentTransaction, PaymentTransactionAdmin),
            (RecurringBilling, RecurringBillingAdmin),(UserLevel, UserLevelAdmin),
            (Achievement, AchievementAdmin),(LeaderboardRank, LeaderboardRankAdmin),
            (SpinWheelLog, SpinWheelLogAdmin),(ABTest, ABTestAdmin),
            (WaterfallConfig, WaterfallConfigAdmin),(FloorPriceConfig, FloorPriceConfigAdmin),
            (AdPerformanceHourly, AdPerformanceHourlyAdmin),(AdPerformanceDaily, AdPerformanceDailyAdmin),
            (AdNetworkDailyStat, AdNetworkDailyStatAdmin),(PointLedgerSnapshot, PointLedgerSnapshotAdmin),
            (ABTestAssignment, ABTestAssignmentAdmin),(MonetizationConfig, MonetizationConfigAdmin),
            (AdCreative, AdCreativeAdmin),(UserSegment, UserSegmentAdmin),
            (UserSegmentMembership, UserSegmentMembershipAdmin),(PostbackLog, PostbackLogAdmin),
            (PayoutMethod, PayoutMethodAdmin),(PayoutRequest, PayoutRequestAdmin),
            (ReferralProgram, ReferralProgramAdmin),(ReferralLink, ReferralLinkAdmin),
            (ReferralCommission, ReferralCommissionAdmin),(DailyStreak, DailyStreakAdmin),
            (SpinWheelConfig, SpinWheelConfigAdmin),(PrizeConfig, PrizeConfigAdmin),
            (FlashSale, FlashSaleAdmin),(Coupon, CouponAdmin),(CouponUsage, CouponUsageAdmin),
            (FraudAlert, FraudAlertAdmin),(RevenueGoal, RevenueGoalAdmin),
            (PublisherAccount, PublisherAccountAdmin),
            (MonetizationNotificationTemplate, MonetizationNotificationTemplateAdmin),
        ]
        registered=0
        for model, model_admin in pairs:
            try:
                if model not in modern_site._registry:
                    modern_site.register(model, model_admin)
                    registered+=1
            except Exception as ex:
                print(f"[WARN] Could not register {model.__name__}: {ex}")
        print(f"[OK] Monetization Tools registered {registered} models")
    except Exception as e:
        print(f"[WARN] Monetization Tools force-register: {e}")
