# api/offer_inventory/serializers.py
from rest_framework import serializers
from django.utils import timezone
from decimal import Decimal
from .models import (
    Offer, OfferNetwork, OfferCategory, OfferCreative, OfferTag,
    Click, Conversion, ConversionStatus,
    WithdrawalRequest, PaymentMethod, WalletTransaction, WalletAudit,
    UserProfile, UserKYC, UserReferral, Achievement, UserAchievement,
    Notification, BlacklistedIP, FraudAttempt, UserRiskProfile,
    DailyStat, NetworkStat, SmartLink, Campaign,
    DirectAdvertiser, SubID, OfferCap, OfferLog, MasterSwitch,
    FeedbackTicket, SystemSetting, ABTestGroup,
)
from .validators import validate_withdrawal_amount, validate_positive_decimal
from .constants import MIN_WITHDRAWAL_BDT, MAX_WITHDRAWAL_BDT


# ══════════════════════════════════════════════════════
# BASE
# ══════════════════════════════════════════════════════

class TimestampMixin(serializers.ModelSerializer):
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)


# ══════════════════════════════════════════════════════
# OFFER SERIALIZERS
# ══════════════════════════════════════════════════════

class OfferNetworkSerializer(serializers.ModelSerializer):
    class Meta:
        model  = OfferNetwork
        fields = ['id', 'name', 'slug', 'status', 'priority', 'revenue_share_pct', 'is_s2s_enabled']
        read_only_fields = ['id']


class OfferCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model  = OfferCategory
        fields = ['id', 'name', 'slug', 'icon_url', 'description', 'is_active', 'sort_order']
        read_only_fields = ['id']


class OfferTagSerializer(serializers.ModelSerializer):
    class Meta:
        model  = OfferTag
        fields = ['id', 'name', 'slug', 'color']


class OfferCapSerializer(serializers.ModelSerializer):
    is_reached = serializers.BooleanField(read_only=True)

    class Meta:
        model  = OfferCap
        fields = ['id', 'cap_type', 'cap_limit', 'current_count', 'is_reached', 'pause_on_hit']


class OfferCreativeSerializer(serializers.ModelSerializer):
    class Meta:
        model  = OfferCreative
        fields = ['id', 'creative_type', 'asset_url', 'width', 'height', 'is_approved']


class OfferListSerializer(serializers.ModelSerializer):
    """অফার list-এর জন্য — lightweight।"""
    network_name   = serializers.CharField(source='network.name', read_only=True, default='')
    category_name  = serializers.CharField(source='category.name', read_only=True, default='')
    tags           = OfferTagSerializer(many=True, read_only=True)
    is_available   = serializers.BooleanField(read_only=True)

    class Meta:
        model  = Offer
        fields = [
            'id', 'title', 'image_url', 'reward_type', 'reward_amount',
            'estimated_time', 'difficulty', 'is_featured', 'status',
            'network_name', 'category_name', 'tags', 'is_available',
            'conversion_rate', 'expires_at',
        ]


class OfferDetailSerializer(serializers.ModelSerializer):
    """অফার detail-এর জন্য — full।"""
    network    = OfferNetworkSerializer(read_only=True)
    category   = OfferCategorySerializer(read_only=True)
    tags       = OfferTagSerializer(many=True, read_only=True)
    creatives  = OfferCreativeSerializer(many=True, read_only=True)
    caps       = OfferCapSerializer(many=True, read_only=True)
    is_available = serializers.BooleanField(read_only=True)

    class Meta:
        model  = Offer
        fields = [
            'id', 'title', 'description', 'instructions',
            'image_url', 'offer_url', 'status',
            'reward_type', 'reward_amount',
            'estimated_time', 'difficulty',
            'is_featured', 'is_recurring',
            'starts_at', 'expires_at',
            'max_completions', 'total_completions', 'conversion_rate',
            'network', 'category', 'tags', 'creatives', 'caps',
            'is_available', 'created_at',
        ]


class OfferWriteSerializer(serializers.ModelSerializer):
    """অফার create/update।"""
    class Meta:
        model  = Offer
        fields = [
            'title', 'description', 'instructions',
            'image_url', 'offer_url', 'status',
            'reward_type', 'reward_amount', 'payout_amount',
            'estimated_time', 'difficulty',
            'is_featured', 'is_recurring',
            'starts_at', 'expires_at', 'max_completions',
            'network', 'category',
        ]

    def validate(self, data):
        starts_at  = data.get('starts_at')
        expires_at = data.get('expires_at')
        from .validators import validate_offer_dates
        validate_offer_dates(starts_at, expires_at)
        return data


class OfferLogSerializer(serializers.ModelSerializer):
    changed_by_name = serializers.CharField(source='changed_by.username', read_only=True, default='')

    class Meta:
        model  = OfferLog
        fields = ['id', 'old_status', 'new_status', 'note', 'changed_by_name', 'created_at']


# ══════════════════════════════════════════════════════
# CLICK & CONVERSION SERIALIZERS
# ══════════════════════════════════════════════════════

class ClickSerializer(serializers.ModelSerializer):
    offer_title = serializers.CharField(source='offer.title', read_only=True, default='')

    class Meta:
        model  = Click
        fields = [
            'id', 'click_token', 'offer', 'offer_title',
            'ip_address', 'country_code', 'device_type', 'os', 'browser',
            'is_unique', 'is_fraud', 'fraud_reason', 'converted',
            'created_at',
        ]
        read_only_fields = ['id', 'click_token', 'is_fraud', 'converted']


class ConversionStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ConversionStatus
        fields = ['name', 'description', 'is_terminal']


class ConversionSerializer(serializers.ModelSerializer):
    offer_title  = serializers.CharField(source='offer.title', read_only=True, default='')
    status_name  = serializers.CharField(source='status.name', read_only=True, default='')
    user_username= serializers.CharField(source='user.username', read_only=True, default='')

    class Meta:
        model  = Conversion
        fields = [
            'id', 'offer', 'offer_title', 'user', 'user_username',
            'status', 'status_name',
            'payout_amount', 'reward_amount',
            'transaction_id', 'ip_address', 'country_code',
            'postback_sent', 'postback_at',
            'approved_at', 'rejected_at', 'reject_reason',
            'is_duplicate', 'created_at',
        ]
        read_only_fields = ['id', 'postback_sent']


class PostbackInputSerializer(serializers.Serializer):
    """Network postback input।"""
    click_id       = serializers.CharField(max_length=64)
    transaction_id = serializers.CharField(max_length=255)
    payout         = serializers.DecimalField(max_digits=12, decimal_places=4)
    status         = serializers.ChoiceField(choices=['approved', 'rejected'])
    signature      = serializers.CharField(max_length=128, required=False, default='')
    s1             = serializers.CharField(max_length=255, required=False, default='')
    s2             = serializers.CharField(max_length=255, required=False, default='')

    def validate_payout(self, value):
        if value <= 0:
            raise serializers.ValidationError('Payout অবশ্যই positive হতে হবে।')
        return value


# ══════════════════════════════════════════════════════
# FINANCE SERIALIZERS
# ══════════════════════════════════════════════════════

class PaymentMethodSerializer(serializers.ModelSerializer):
    masked_account = serializers.SerializerMethodField()

    class Meta:
        model  = PaymentMethod
        fields = [
            'id', 'provider', 'account_name',
            'masked_account', 'is_primary', 'is_verified',
            'verified_at', 'last_used_at',
        ]

    def get_masked_account(self, obj):
        account = obj.account_number
        return '***' + account[-4:] if len(account) >= 4 else '****'


class PaymentMethodCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = PaymentMethod
        fields = ['provider', 'account_number', 'account_name', 'is_primary']

    def validate_account_number(self, value):
        from .validators import validate_no_sql_injection
        validate_no_sql_injection(value)
        return value


class WithdrawalRequestSerializer(serializers.ModelSerializer):
    payment_method_info = PaymentMethodSerializer(source='payment_method', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model  = WithdrawalRequest
        fields = [
            'id', 'user', 'username', 'amount', 'fee', 'net_amount',
            'currency', 'status', 'reference_no',
            'payment_method', 'payment_method_info',
            'note', 'rejected_reason',
            'processed_at', 'created_at',
        ]
        read_only_fields = ['id', 'fee', 'net_amount', 'status', 'reference_no']


class WithdrawalCreateSerializer(serializers.Serializer):
    amount            = serializers.DecimalField(max_digits=12, decimal_places=2)
    payment_method_id = serializers.UUIDField()

    def validate_amount(self, value):
        from .validators import validate_withdrawal_amount
        return validate_withdrawal_amount(value)


class WalletTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model  = WalletTransaction
        fields = [
            'id', 'tx_type', 'amount', 'currency',
            'description', 'source', 'source_id',
            'balance_snapshot', 'created_at',
        ]


class WalletAuditSerializer(serializers.ModelSerializer):
    class Meta:
        model  = WalletAudit
        fields = [
            'id', 'transaction_type', 'amount',
            'balance_before', 'balance_after',
            'reference_id', 'reference_type', 'note', 'created_at',
        ]


# ══════════════════════════════════════════════════════
# USER SERIALIZERS
# ══════════════════════════════════════════════════════

class UserProfileSerializer(serializers.ModelSerializer):
    loyalty_level_name = serializers.CharField(source='loyalty_level.name', read_only=True, default='')
    username = serializers.CharField(source='user.username', read_only=True)
    email    = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model  = UserProfile
        fields = [
            'id', 'username', 'email',
            'loyalty_level', 'loyalty_level_name',
            'total_points', 'total_offers', 'daily_offer_count',
            'preferred_currency', 'is_verified',
        ]


class UserKYCSerializer(serializers.ModelSerializer):
    class Meta:
        model  = UserKYC
        fields = [
            'id', 'status', 'id_type', 'id_number',
            'id_front_url', 'id_back_url', 'selfie_url',
            'reviewed_at', 'reject_reason',
        ]
        read_only_fields = ['id', 'status', 'reviewed_at', 'reject_reason']


class UserReferralSerializer(serializers.ModelSerializer):
    referred_username = serializers.CharField(source='referred.username', read_only=True)

    class Meta:
        model  = UserReferral
        fields = [
            'id', 'referred', 'referred_username', 'referral_code',
            'is_converted', 'converted_at', 'total_earnings_generated',
            'created_at',
        ]


class AchievementSerializer(serializers.ModelSerializer):
    is_earned = serializers.SerializerMethodField()

    class Meta:
        model  = Achievement
        fields = ['id', 'name', 'description', 'badge_url', 'points_award', 'is_hidden', 'is_earned']

    def get_is_earned(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        return UserAchievement.objects.filter(
            user=request.user, achievement=obj
        ).exists()


# ══════════════════════════════════════════════════════
# NOTIFICATION SERIALIZERS
# ══════════════════════════════════════════════════════

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Notification
        fields = [
            'id', 'notif_type', 'title', 'body',
            'action_url', 'is_read', 'read_at', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


# ══════════════════════════════════════════════════════
# FRAUD SERIALIZERS
# ══════════════════════════════════════════════════════

class UserRiskProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model  = UserRiskProfile
        fields = [
            'id', 'user', 'username', 'risk_score', 'risk_level',
            'total_flags', 'last_flagged_at', 'is_suspended', 'suspension_reason',
        ]


class BlacklistedIPSerializer(serializers.ModelSerializer):
    class Meta:
        model  = BlacklistedIP
        fields = [
            'id', 'ip_address', 'ip_range', 'reason', 'source',
            'is_permanent', 'expires_at', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class FraudAttemptSerializer(serializers.ModelSerializer):
    rule_name = serializers.CharField(source='rule.name', read_only=True, default='')
    username  = serializers.CharField(source='user.username', read_only=True, default='')

    class Meta:
        model  = FraudAttempt
        fields = [
            'id', 'rule', 'rule_name', 'user', 'username',
            'ip_address', 'description', 'evidence',
            'action_taken', 'is_resolved', 'resolved_at', 'created_at',
        ]


# ══════════════════════════════════════════════════════
# ANALYTICS SERIALIZERS
# ══════════════════════════════════════════════════════

class DailyStatSerializer(serializers.ModelSerializer):
    class Meta:
        model  = DailyStat
        fields = [
            'date', 'total_clicks', 'unique_clicks',
            'total_conversions', 'approved_conversions', 'rejected_conversions',
            'total_revenue', 'user_payouts', 'platform_profit',
            'new_users', 'active_users', 'fraud_attempts', 'cvr',
        ]


class NetworkStatSerializer(serializers.ModelSerializer):
    network_name = serializers.CharField(source='network.name', read_only=True)

    class Meta:
        model  = NetworkStat
        fields = [
            'date', 'network_name', 'clicks', 'conversions',
            'revenue', 'avg_payout', 'cvr', 'epc',
        ]


# ══════════════════════════════════════════════════════
# ADMIN / SYSTEM SERIALIZERS
# ══════════════════════════════════════════════════════

class MasterSwitchSerializer(serializers.ModelSerializer):
    toggled_by_name = serializers.CharField(source='toggled_by.username', read_only=True, default='')

    class Meta:
        model  = MasterSwitch
        fields = ['id', 'feature', 'is_enabled', 'description', 'toggled_by_name', 'toggled_at']
        read_only_fields = ['id', 'toggled_at']


class SystemSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model  = SystemSetting
        fields = ['id', 'key', 'value', 'value_type', 'description', 'is_public']
        read_only_fields = ['id']


class ABTestGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ABTestGroup
        fields = [
            'id', 'name', 'hypothesis', 'status',
            'variant_a', 'variant_b', 'traffic_split',
            'winner', 'started_at', 'ended_at', 'metric',
        ]


class FeedbackTicketSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model  = FeedbackTicket
        fields = [
            'id', 'ticket_no', 'user', 'username', 'subject', 'message',
            'priority', 'status', 'assigned_to',
            'resolved_at', 'resolution', 'created_at',
        ]
        read_only_fields = ['id', 'ticket_no', 'created_at']


class CampaignSerializer(serializers.ModelSerializer):
    remaining_budget = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )

    class Meta:
        model  = Campaign
        fields = [
            'id', 'name', 'status', 'budget', 'spent', 'remaining_budget',
            'daily_cap', 'starts_at', 'ends_at', 'goal',
            'advertiser', 'network', 'created_at',
        ]
        read_only_fields = ['id', 'spent', 'remaining_budget']


class SmartLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model  = SmartLink
        fields = [
            'id', 'slug', 'algorithm', 'is_active',
            'click_count', 'offers', 'custom_params', 'created_at',
        ]
        read_only_fields = ['id', 'click_count']


# ══════════════════════════════════════════════════════
# MARKETING SERIALIZERS
# ══════════════════════════════════════════════════════

class ReferralCommissionSerializer(serializers.ModelSerializer):
    referrer_name      = serializers.CharField(source='referrer.username', read_only=True)
    referred_user_name = serializers.CharField(source='referred_user.username', read_only=True)

    class Meta:
        from api.offer_inventory.models import ReferralCommission
        model  = ReferralCommission
        fields = [
            'id', 'referrer', 'referrer_name', 'referred_user', 'referred_user_name',
            'commission_pct', 'amount', 'is_paid', 'paid_at', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class UserReferralSerializer(serializers.ModelSerializer):
    referrer_name  = serializers.CharField(source='referrer.username',  read_only=True)
    referred_name  = serializers.CharField(source='referred.username',  read_only=True)

    class Meta:
        from api.offer_inventory.models import UserReferral
        model  = UserReferral
        fields = [
            'id', 'referrer', 'referrer_name', 'referred', 'referred_name',
            'referral_code', 'is_converted', 'converted_at',
            'total_earnings_generated', 'created_at',
        ]


class LoyaltyLevelSerializer(serializers.ModelSerializer):
    class Meta:
        from api.offer_inventory.models import LoyaltyLevel
        model  = LoyaltyLevel
        fields = [
            'id', 'name', 'level_order', 'min_points', 'max_points',
            'badge_url', 'payout_bonus_pct', 'perks',
        ]


class ChurnRecordSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        from api.offer_inventory.models import ChurnRecord
        model  = ChurnRecord
        fields = [
            'id', 'user', 'username', 'churn_probability', 'days_inactive',
            'last_active', 'is_churned', 'reactivation_sent', 'reactivated_at',
        ]


class UserSegmentSerializer(serializers.ModelSerializer):
    class Meta:
        from api.offer_inventory.models import UserSegment
        model  = UserSegment
        fields = [
            'id', 'name', 'description', 'criteria', 'is_dynamic',
            'user_count', 'last_computed',
        ]


class PromoCodeRedeemSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=20)

    def validate_code(self, value):
        return value.strip().upper()


class PushSubscriptionSerializer(serializers.Serializer):
    endpoint = serializers.CharField()
    p256dh   = serializers.CharField()
    auth     = serializers.CharField()


class LeaderboardEntrySerializer(serializers.Serializer):
    username       = serializers.CharField(source='user__username')
    total_points   = serializers.IntegerField()
    loyalty_level  = serializers.CharField(source='loyalty_level__name')
    total_offers   = serializers.IntegerField()


# ══════════════════════════════════════════════════════
# BUSINESS SERIALIZERS
# ══════════════════════════════════════════════════════

class DirectAdvertiserSerializer(serializers.ModelSerializer):
    class Meta:
        from api.offer_inventory.models import DirectAdvertiser
        model  = DirectAdvertiser
        fields = [
            'id', 'company_name', 'contact_name', 'contact_email',
            'website', 'agreed_rev_share', 'is_verified', 'is_active',
            'created_at',
        ]
        read_only_fields = ['id', 'is_verified', 'created_at']


class DirectAdvertiserWriteSerializer(serializers.ModelSerializer):
    class Meta:
        from api.offer_inventory.models import DirectAdvertiser
        model  = DirectAdvertiser
        fields = [
            'company_name', 'contact_name', 'contact_email',
            'website', 'agreed_rev_share',
        ]


class InvoiceSerializer(serializers.ModelSerializer):
    advertiser_name = serializers.CharField(source='advertiser.company_name', read_only=True)

    class Meta:
        from api.offer_inventory.models import Invoice
        model  = Invoice
        fields = [
            'id', 'invoice_no', 'advertiser', 'advertiser_name',
            'amount', 'currency', 'is_paid', 'issued_at', 'due_at', 'paid_at',
            'pdf_url', 'notes',
        ]
        read_only_fields = ['id', 'invoice_no', 'issued_at']


class RevenueShareSerializer(serializers.ModelSerializer):
    class Meta:
        from api.offer_inventory.models import RevenueShare
        model  = RevenueShare
        fields = [
            'id', 'offer', 'conversion', 'gross_revenue',
            'platform_cut', 'user_share', 'referral_share', 'currency',
        ]


class TaxRecordSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        from api.offer_inventory.models import TaxRecord
        model  = TaxRecord
        fields = [
            'id', 'user', 'username', 'tax_type', 'rate',
            'base_amount', 'tax_amount', 'fiscal_year', 'reference', 'created_at',
        ]


class GDPRExportSerializer(serializers.Serializer):
    """Response shape for GDPR data export."""
    user         = serializers.DictField()
    profile      = serializers.DictField(allow_null=True)
    kyc          = serializers.DictField(allow_null=True)
    clicks       = serializers.ListField()
    conversions  = serializers.ListField()
    withdrawals  = serializers.ListField()
    wallet_audit = serializers.ListField()
    referrals    = serializers.ListField()


class KPISummarySerializer(serializers.Serializer):
    """KPI dashboard response."""
    total_users        = serializers.IntegerField()
    new_users          = serializers.IntegerField()
    active_users       = serializers.IntegerField()
    dau                = serializers.IntegerField()
    mau                = serializers.IntegerField()
    retention_rate     = serializers.FloatField()
    total_clicks       = serializers.IntegerField()
    fraud_clicks       = serializers.IntegerField()
    fraud_rate_pct     = serializers.FloatField()
    total_conversions  = serializers.IntegerField()
    cvr_pct            = serializers.FloatField()
    gross_revenue      = serializers.FloatField()
    user_rewards       = serializers.FloatField()
    platform_revenue   = serializers.FloatField()
    epc                = serializers.FloatField()
    wd_requested       = serializers.FloatField()
    wd_paid            = serializers.FloatField()
    wd_pending_count   = serializers.IntegerField()
    period_days        = serializers.IntegerField()
    computed_at        = serializers.CharField()


class RevenueForecastSerializer(serializers.Serializer):
    avg_daily_revenue  = serializers.FloatField()
    trend_pct          = serializers.FloatField()
    projected_daily    = serializers.FloatField()
    projected_total    = serializers.FloatField()
    projected_low      = serializers.FloatField()
    projected_high     = serializers.FloatField()
    forecast_days      = serializers.IntegerField()
    based_on_days      = serializers.IntegerField()


# ══════════════════════════════════════════════════════
# BULK OPERATION SERIALIZERS
# ══════════════════════════════════════════════════════

class BulkOfferActionSerializer(serializers.Serializer):
    offer_ids = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1, max_length=500,
    )
    reason    = serializers.CharField(max_length=255, required=False, default='Bulk action')


class BulkConversionActionSerializer(serializers.Serializer):
    conversion_ids = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1, max_length=200,
    )


class BulkIPBlockSerializer(serializers.Serializer):
    ips    = serializers.ListField(child=serializers.IPAddressField(), min_length=1)
    reason = serializers.CharField(max_length=255, default='Bulk block')
    hours  = serializers.IntegerField(min_value=1, max_value=8760, default=72)


class BulkUserActionSerializer(serializers.Serializer):
    user_ids = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1, max_length=1000,
    )
    reason   = serializers.CharField(max_length=255, required=False, default='')


# ══════════════════════════════════════════════════════
# REPORTING SERIALIZERS
# ══════════════════════════════════════════════════════

class ReportQuerySerializer(serializers.Serializer):
    days   = serializers.IntegerField(min_value=1, max_value=365, default=30)
    format = serializers.ChoiceField(choices=['json', 'csv'], default='json')
    status = serializers.CharField(max_length=20, required=False)


class NetworkROISerializer(serializers.Serializer):
    network         = serializers.CharField()
    slug            = serializers.CharField()
    clicks          = serializers.IntegerField()
    fraud_rate_pct  = serializers.FloatField()
    conversions     = serializers.IntegerField()
    cvr_pct         = serializers.FloatField()
    gross_revenue   = serializers.FloatField()
    user_rewards    = serializers.FloatField()
    platform_profit = serializers.FloatField()
    roi_pct         = serializers.FloatField()
    epc             = serializers.FloatField()
    revenue_share   = serializers.FloatField()


class MarketingCampaignSerializer(serializers.Serializer):
    title      = serializers.CharField(max_length=255)
    body       = serializers.CharField()
    channel    = serializers.ChoiceField(
        choices=['in_app', 'push', 'email'],
        default='in_app',
    )
    action_url = serializers.URLField(required=False, default='')
    criteria   = serializers.DictField(required=False, default=dict)


class CircuitStatusSerializer(serializers.Serializer):
    name          = serializers.CharField()
    state         = serializers.CharField()
    failure_count = serializers.IntegerField()
    threshold     = serializers.IntegerField()


class HealthCheckSerializer(serializers.Serializer):
    status    = serializers.CharField()
    checks    = serializers.DictField()
    timestamp = serializers.CharField()
