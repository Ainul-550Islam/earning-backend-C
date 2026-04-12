"""
api/monetization_tools/serializers.py
=======================================
DRF Serializers for all monetization_tools models.
"""

from decimal import Decimal, InvalidOperation
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

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

class SafeDecimalField(serializers.DecimalField):
    def to_internal_value(self, data):
        try:
            if isinstance(data, str):
                data = data.strip().replace(',', '')
            return Decimal(str(data))
        except (InvalidOperation, ValueError, TypeError) as e:
            raise serializers.ValidationError(f"Invalid decimal value: {e}")

    def to_representation(self, value):
        return str(value) if value is not None else None


# ===========================================================================
# 1. AD CAMPAIGN & UNIT
# ===========================================================================

class AdCampaignListSerializer(serializers.ModelSerializer):
    remaining_budget = serializers.ReadOnlyField()
    ctr = serializers.ReadOnlyField()

    class Meta:
        model = AdCampaign
        fields = [
            'id', 'campaign_id', 'name', 'status', 'pricing_model',
            'total_budget', 'spent_budget', 'remaining_budget',
            'start_date', 'end_date',
            'total_impressions', 'total_clicks', 'total_conversions',
            'ctr', 'created_at',
        ]
        read_only_fields = ['id', 'campaign_id', 'spent_budget', 'total_impressions',
                            'total_clicks', 'total_conversions', 'created_at']


class AdCampaignDetailSerializer(serializers.ModelSerializer):
    remaining_budget = serializers.ReadOnlyField()
    ctr = serializers.ReadOnlyField()

    class Meta:
        model = AdCampaign
        fields = '__all__'
        read_only_fields = ['id', 'campaign_id', 'spent_budget', 'total_impressions',
                            'total_clicks', 'total_conversions', 'created_at', 'updated_at']

    def validate(self, attrs):
        start = attrs.get('start_date', getattr(self.instance, 'start_date', None))
        end   = attrs.get('end_date',   getattr(self.instance, 'end_date', None))
        if end and start and end <= start:
            raise serializers.ValidationError({'end_date': _("End date must be after start date.")})
        daily = attrs.get('daily_budget', getattr(self.instance, 'daily_budget', None))
        total = attrs.get('total_budget', getattr(self.instance, 'total_budget', None))
        if daily and total and daily > total:
            raise serializers.ValidationError({'daily_budget': _("Daily budget cannot exceed total budget.")})
        return attrs


class AdUnitSerializer(serializers.ModelSerializer):
    campaign_name = serializers.CharField(source='campaign.name', read_only=True)

    class Meta:
        model = AdUnit
        fields = '__all__'
        read_only_fields = ['id', 'unit_id', 'created_at', 'updated_at']


# ===========================================================================
# 2. AD NETWORK & PLACEMENT
# ===========================================================================

class AdNetworkSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdNetwork
        fields = [
            'id', 'network_type', 'display_name', 'app_id',
            'is_active', 'priority', 'floor_price', 'created_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
        extra_kwargs = {
            'api_key': {'write_only': True},
            'secret_key': {'write_only': True},
            'reporting_api_key': {'write_only': True},
        }


class AdPlacementSerializer(serializers.ModelSerializer):
    ad_unit_name    = serializers.CharField(source='ad_unit.name', read_only=True)
    ad_network_name = serializers.CharField(source='ad_network.display_name', read_only=True)

    class Meta:
        model = AdPlacement
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


# ===========================================================================
# 3. OFFERWALL & OFFER
# ===========================================================================

class OfferwallSerializer(serializers.ModelSerializer):
    network_name = serializers.CharField(source='network.display_name', read_only=True)

    class Meta:
        model = Offerwall
        fields = [
            'id', 'network', 'network_name', 'name', 'slug',
            'description', 'logo_url', 'embed_url',
            'is_active', 'is_featured', 'sort_order', 'created_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class OfferListSerializer(serializers.ModelSerializer):
    is_available = serializers.ReadOnlyField()
    offerwall_name = serializers.CharField(source='offerwall.name', read_only=True)

    class Meta:
        model = Offer
        fields = [
            'id', 'external_offer_id', 'offerwall_name',
            'title', 'offer_type', 'status',
            'point_value', 'payout_usd',
            'is_featured', 'is_hot', 'is_available',
            'thumbnail_url', 'expiry_date',
        ]


class OfferDetailSerializer(serializers.ModelSerializer):
    is_available = serializers.ReadOnlyField()

    class Meta:
        model = Offer
        fields = '__all__'
        read_only_fields = ['id', 'total_completions', 'conversion_rate', 'created_at', 'updated_at']


class OfferCompletionSerializer(serializers.ModelSerializer):
    offer_title = serializers.CharField(source='offer.title', read_only=True)
    username    = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = OfferCompletion
        fields = '__all__'
        read_only_fields = [
            'id', 'transaction_id', 'fraud_score', 'fraud_reason',
            'approved_at', 'credited_at', 'created_at', 'updated_at'
        ]


class OfferCompletionAdminSerializer(serializers.ModelSerializer):
    """Admin-facing serializer with all fields."""
    class Meta:
        model = OfferCompletion
        fields = '__all__'


class RewardTransactionSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = RewardTransaction
        fields = '__all__'
        read_only_fields = ['id', 'transaction_id', 'created_at']


# ===========================================================================
# 4. REVENUE TRACKING
# ===========================================================================

class ImpressionLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImpressionLog
        fields = '__all__'
        read_only_fields = ['id', 'logged_at']


class ClickLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClickLog
        fields = '__all__'
        read_only_fields = ['id', 'clicked_at']


class ConversionLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConversionLog
        fields = '__all__'
        read_only_fields = ['id', 'converted_at']


class RevenueDailySummarySerializer(serializers.ModelSerializer):
    ad_network_name = serializers.CharField(source='ad_network.display_name', read_only=True)
    campaign_name   = serializers.CharField(source='campaign.name', read_only=True)

    class Meta:
        model = RevenueDailySummary
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


# ===========================================================================
# 5. SUBSCRIPTION & PAYMENT
# ===========================================================================

class SubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = [
            'id', 'plan_id', 'name', 'slug', 'description',
            'price', 'currency', 'interval', 'trial_days',
            'features', 'is_active', 'is_popular', 'sort_order',
        ]
        read_only_fields = ['id', 'plan_id', 'created_at', 'updated_at']


class UserSubscriptionSerializer(serializers.ModelSerializer):
    plan_name   = serializers.CharField(source='plan.name', read_only=True)
    is_active   = serializers.ReadOnlyField()
    username    = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = UserSubscription
        fields = '__all__'
        read_only_fields = ['id', 'subscription_id', 'created_at', 'updated_at']
        extra_kwargs = {
            'gateway_subscription_id': {'write_only': True},
        }


class InAppPurchaseSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = InAppPurchase
        fields = '__all__'
        read_only_fields = ['id', 'purchase_id', 'purchased_at', 'fulfilled_at']


class PaymentTransactionSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = PaymentTransaction
        fields = '__all__'
        read_only_fields = ['id', 'txn_id', 'initiated_at', 'completed_at']
        extra_kwargs = {
            'gateway_response': {'write_only': True},
        }


class PaymentTransactionPublicSerializer(serializers.ModelSerializer):
    """Minimal public-facing transaction info (no gateway_response)."""
    class Meta:
        model = PaymentTransaction
        fields = ['id', 'txn_id', 'gateway', 'amount', 'currency', 'status', 'purpose', 'initiated_at']


class RecurringBillingSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecurringBilling
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'last_attempt', 'attempt_count']


# ===========================================================================
# 6. GAMIFICATION
# ===========================================================================

class UserLevelSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    level_progress_pct = serializers.SerializerMethodField()

    class Meta:
        model = UserLevel
        fields = '__all__'
        read_only_fields = ['id', 'updated_at']

    def get_level_progress_pct(self, obj):
        if obj.xp_to_next_level:
            return round((obj.current_xp / obj.xp_to_next_level) * 100, 1)
        return 100.0


class AchievementSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = Achievement
        fields = '__all__'
        read_only_fields = ['id', 'unlocked_at']


class LeaderboardRankSerializer(serializers.ModelSerializer):
    username      = serializers.CharField(source='user.username', read_only=True)
    profile_picture = serializers.ImageField(source='user.profile_picture', read_only=True)

    class Meta:
        model = LeaderboardRank
        fields = '__all__'
        read_only_fields = ['id', 'calculated_at']


class SpinWheelLogSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = SpinWheelLog
        fields = '__all__'
        read_only_fields = ['id', 'played_at']


# ===========================================================================
# 7. A/B TESTING & OPTIMIZATION
# ===========================================================================

class ABTestSerializer(serializers.ModelSerializer):
    class Meta:
        model = ABTest
        fields = '__all__'
        read_only_fields = ['id', 'test_id', 'winner_variant', 'results_summary',
                            'started_at', 'ended_at', 'created_at', 'updated_at']

    def validate_variants(self, value):
        if len(value) < 2:
            raise serializers.ValidationError(_("At least 2 variants are required."))
        total_weight = sum(v.get('weight', 0) for v in value)
        if total_weight != 100:
            raise serializers.ValidationError(_("Variant weights must sum to 100."))
        return value


class WaterfallConfigSerializer(serializers.ModelSerializer):
    ad_unit_name    = serializers.CharField(source='ad_unit.name', read_only=True)
    ad_network_name = serializers.CharField(source='ad_network.display_name', read_only=True)

    class Meta:
        model = WaterfallConfig
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class FloorPriceConfigSerializer(serializers.ModelSerializer):
    ad_network_name = serializers.CharField(source='ad_network.display_name', read_only=True)

    class Meta:
        model = FloorPriceConfig
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


# ============================================================================
# NEW MODEL SERIALIZERS  (Phase-2 models)
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


class AdPerformanceHourlySerializer(serializers.ModelSerializer):
    ad_unit_name    = serializers.CharField(source='ad_unit.name', read_only=True)
    ad_network_name = serializers.CharField(source='ad_network.display_name', read_only=True)

    class Meta:
        model  = AdPerformanceHourly
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class AdPerformanceDailySerializer(serializers.ModelSerializer):
    ad_unit_name    = serializers.CharField(source='ad_unit.name', read_only=True)
    ad_network_name = serializers.CharField(source='ad_network.display_name', read_only=True)
    campaign_name   = serializers.CharField(source='campaign.name', read_only=True)

    class Meta:
        model  = AdPerformanceDaily
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class AdNetworkDailyStatSerializer(serializers.ModelSerializer):
    ad_network_name = serializers.CharField(source='ad_network.display_name', read_only=True)

    class Meta:
        model  = AdNetworkDailyStat
        fields = '__all__'
        read_only_fields = ['id', 'fetched_at', 'created_at', 'updated_at']


class PointLedgerSnapshotSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model  = PointLedgerSnapshot
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class ABTestAssignmentSerializer(serializers.ModelSerializer):
    username  = serializers.CharField(source='user.username', read_only=True)
    test_name = serializers.CharField(source='test.name', read_only=True)

    class Meta:
        model  = ABTestAssignment
        fields = '__all__'
        read_only_fields = ['id', 'assigned_at', 'created_at', 'updated_at']


class MonetizationConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model  = MonetizationConfig
        fields = '__all__'
        read_only_fields = ['id', 'tenant', 'created_at', 'updated_at']
        extra_kwargs = {'postback_secret': {'write_only': True}}


class AdCreativeListSerializer(serializers.ModelSerializer):
    ad_unit_name = serializers.CharField(source='ad_unit.name', read_only=True)
    ctr          = serializers.ReadOnlyField()

    class Meta:
        model  = AdCreative
        fields = [
            'id', 'creative_id', 'ad_unit_name', 'name', 'creative_type',
            'status', 'width', 'height', 'asset_url', 'preview_url',
            'ctr', 'impressions', 'clicks', 'revenue', 'is_active', 'created_at',
        ]
        read_only_fields = ['id', 'creative_id', 'impressions', 'clicks', 'revenue', 'created_at']


class AdCreativeDetailSerializer(serializers.ModelSerializer):
    ctr = serializers.ReadOnlyField()

    class Meta:
        model  = AdCreative
        fields = '__all__'
        read_only_fields = ['id', 'creative_id', 'impressions', 'clicks', 'revenue',
                            'created_at', 'updated_at']


class UserSegmentSerializer(serializers.ModelSerializer):
    class Meta:
        model  = UserSegment
        fields = '__all__'
        read_only_fields = ['id', 'member_count', 'last_computed', 'created_at', 'updated_at']


class UserSegmentMembershipSerializer(serializers.ModelSerializer):
    username      = serializers.CharField(source='user.username', read_only=True)
    segment_name  = serializers.CharField(source='segment.name', read_only=True)

    class Meta:
        model  = UserSegmentMembership
        fields = '__all__'
        read_only_fields = ['id', 'added_at', 'created_at', 'updated_at']


class PostbackLogSerializer(serializers.ModelSerializer):
    ad_network_name = serializers.CharField(source='ad_network.display_name', read_only=True)

    class Meta:
        model  = PostbackLog
        fields = '__all__'
        read_only_fields = ['id', 'postback_id', 'received_at', 'processed_at',
                            'created_at', 'updated_at']


class PostbackLogListSerializer(serializers.ModelSerializer):
    """Slim version for list views — excludes raw payload fields."""
    ad_network_name = serializers.CharField(source='ad_network.display_name', read_only=True)

    class Meta:
        model  = PostbackLog
        fields = [
            'id', 'postback_id', 'ad_network_name', 'network_name',
            'status', 'source_ip', 'signature_valid',
            'reward_amount', 'payout_usd', 'received_at', 'processing_time_ms',
        ]


class PayoutMethodSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model  = PayoutMethod
        fields = '__all__'
        read_only_fields = ['id', 'is_verified', 'verified_at', 'created_at', 'updated_at']


class PayoutRequestSerializer(serializers.ModelSerializer):
    username            = serializers.CharField(source='user.username', read_only=True)
    payout_method_type  = serializers.CharField(source='payout_method.method_type', read_only=True)
    payout_account      = serializers.CharField(source='payout_method.account_number', read_only=True)

    class Meta:
        model  = PayoutRequest
        fields = '__all__'
        read_only_fields = [
            'id', 'request_id', 'net_amount', 'status',
            'reviewed_by', 'reviewed_at', 'paid_at',
            'gateway_reference', 'created_at', 'updated_at',
        ]


class PayoutRequestAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model  = PayoutRequest
        fields = '__all__'


class ReferralProgramSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ReferralProgram
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class ReferralLinkSerializer(serializers.ModelSerializer):
    username     = serializers.CharField(source='user.username', read_only=True)
    program_name = serializers.CharField(source='program.name', read_only=True)

    class Meta:
        model  = ReferralLink
        fields = '__all__'
        read_only_fields = [
            'id', 'code', 'total_clicks', 'total_signups',
            'total_conversions', 'total_earned', 'created_at', 'updated_at',
        ]


class ReferralCommissionSerializer(serializers.ModelSerializer):
    referrer_name = serializers.CharField(source='referrer.username', read_only=True)
    referee_name  = serializers.CharField(source='referee.username', read_only=True)

    class Meta:
        model  = ReferralCommission
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class DailyStreakSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model  = DailyStreak
        fields = '__all__'
        read_only_fields = [
            'id', 'current_streak', 'longest_streak', 'last_login_date',
            'streak_start_date', 'total_logins', 'today_claimed',
            'milestone_7', 'milestone_14', 'milestone_30', 'milestone_60',
            'milestone_90', 'milestone_180', 'milestone_365',
            'total_streak_coins', 'last_reward_date',
            'created_at', 'updated_at',
        ]


class SpinWheelConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model  = SpinWheelConfig
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class PrizeConfigSerializer(serializers.ModelSerializer):
    wheel_name = serializers.CharField(source='wheel_config.name', read_only=True)

    class Meta:
        model  = PrizeConfig
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class FlashSaleListSerializer(serializers.ModelSerializer):
    is_live = serializers.ReadOnlyField()

    class Meta:
        model  = FlashSale
        fields = [
            'id', 'name', 'slug', 'sale_type', 'is_live',
            'multiplier', 'bonus_coins', 'discount_pct', 'extra_spins',
            'starts_at', 'ends_at', 'is_active', 'total_participants',
        ]


class FlashSaleDetailSerializer(serializers.ModelSerializer):
    is_live = serializers.ReadOnlyField()

    class Meta:
        model  = FlashSale
        fields = '__all__'
        read_only_fields = ['id', 'total_participants', 'total_coins_given',
                            'created_at', 'updated_at']

    def validate(self, attrs):
        if attrs.get('ends_at') and attrs.get('starts_at'):
            if attrs['ends_at'] <= attrs['starts_at']:
                raise serializers.ValidationError({'ends_at': _("Must be after starts_at.")})
        return attrs


class CouponSerializer(serializers.ModelSerializer):
    is_valid = serializers.ReadOnlyField()

    class Meta:
        model  = Coupon
        fields = '__all__'
        read_only_fields = ['id', 'current_uses', 'created_at', 'updated_at']


class CouponPublicSerializer(serializers.ModelSerializer):
    """Minimal public view — hides usage limits."""
    is_valid = serializers.ReadOnlyField()

    class Meta:
        model  = Coupon
        fields = [
            'id', 'code', 'name', 'description', 'coupon_type',
            'coin_amount', 'discount_pct', 'free_days', 'multiplier',
            'valid_until', 'is_valid',
        ]


class CouponUsageSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    coupon_code = serializers.CharField(source='coupon.code', read_only=True)

    class Meta:
        model  = CouponUsage
        fields = '__all__'
        read_only_fields = ['id', 'used_at', 'created_at', 'updated_at']


class FraudAlertSerializer(serializers.ModelSerializer):
    username     = serializers.CharField(source='user.username', read_only=True)
    resolved_by_name = serializers.CharField(source='resolved_by.username', read_only=True)

    class Meta:
        model  = FraudAlert
        fields = '__all__'
        read_only_fields = ['id', 'alert_id', 'created_at', 'updated_at']


class RevenueGoalSerializer(serializers.ModelSerializer):
    progress_pct = serializers.ReadOnlyField()
    is_achieved  = serializers.ReadOnlyField()

    class Meta:
        model  = RevenueGoal
        fields = '__all__'
        read_only_fields = ['id', 'current_value', 'created_at', 'updated_at']

    def validate(self, attrs):
        if attrs.get('period_end') and attrs.get('period_start'):
            if attrs['period_end'] <= attrs['period_start']:
                raise serializers.ValidationError({'period_end': _("Must be after period_start.")})
        return attrs


class PublisherAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model  = PublisherAccount
        fields = '__all__'
        read_only_fields = [
            'id', 'account_id', 'total_spend_usd', 'total_revenue_usd',
            'current_balance_usd', 'verified_at', 'created_at', 'updated_at',
        ]


class MonetizationNotificationTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = MonetizationNotificationTemplate
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']
