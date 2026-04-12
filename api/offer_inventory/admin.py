# api/offer_inventory/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from api.users.models import UserDevice, LoginHistory as UserLoginHistory
from .models import (
    Offer, OfferNetwork, OfferCategory, OfferCap, OfferLog,
    OfferCreative, OfferTag, SmartLink, Campaign, DirectAdvertiser,
    Click, Conversion, ConversionStatus, PostbackLog, SubID,
    BlacklistedIP, FraudRule, FraudAttempt, UserRiskProfile,
    DeviceFingerprint, HoneypotLog, UserAgentBlacklist,
    WithdrawalRequest, PaymentMethod, WalletTransaction, WalletAudit,
    RevenueShare, TaxRecord, ReferralCommission, PayoutBatch, Invoice,
    UserProfile, UserKYC, Achievement, UserReferral, LoyaltyLevel,
    DailyStat, NetworkStat, Notification, SystemSetting, MasterSwitch,
    FeedbackTicket, AuditLog, ErrorLog, BackupLog, ABTestGroup, TaskQueue,
    BidLog, DSPConfig, PublisherConfig,
    Publisher, PublisherApp, AppPlacement, PublisherPayout, PublisherRevenue,
)


# ── Inlines ──────────────────────────────────────────────────────

class OfferCapInline(admin.TabularInline):
    model  = OfferCap
    extra  = 1
    fields = ['cap_type', 'cap_limit', 'current_count', 'pause_on_hit']


class OfferCreativeInline(admin.TabularInline):
    model  = OfferCreative
    extra  = 1
    fields = ['creative_type', 'asset_url', 'width', 'height', 'is_approved']


class OfferLogInline(admin.TabularInline):
    model  = OfferLog
    extra  = 0
    readonly_fields = ['old_status', 'new_status', 'note', 'changed_by', 'created_at']
    can_delete      = False


class PostbackLogInline(admin.TabularInline):
    model      = PostbackLog
    extra      = 0
    readonly_fields = ['url', 'method', 'response_code', 'is_success', 'retry_count', 'created_at']
    can_delete = False


# ══════════════════════════════════════════════════════
# OFFER & NETWORK
# ══════════════════════════════════════════════════════

@admin.register(OfferNetwork)
class OfferNetworkAdmin(admin.ModelAdmin):
    list_display  = ['name', 'slug', 'status', 'priority', 'revenue_share_pct', 'is_s2s_enabled']
    list_filter   = ['status', 'is_s2s_enabled']
    search_fields = ['name', 'slug']
    ordering      = ['priority', 'name']


@admin.register(OfferCategory)
class OfferCategoryAdmin(admin.ModelAdmin):
    list_display  = ['name', 'slug', 'is_active', 'sort_order']
    list_filter   = ['is_active']
    search_fields = ['name']


@admin.register(Offer)
class OfferAdmin(admin.ModelAdmin):
    list_display   = [
        'title', 'status', 'reward_type', 'reward_amount',
        'network', 'category', 'is_featured', 'total_completions',
        'conversion_rate', 'expires_at',
    ]
    list_filter    = ['status', 'reward_type', 'is_featured', 'network', 'category']
    search_fields  = ['title', 'external_offer_id']
    ordering       = ['-created_at']
    list_editable  = ['status', 'is_featured']
    inlines        = [OfferCapInline, OfferCreativeInline, OfferLogInline]
    readonly_fields= ['total_completions', 'conversion_rate', 'created_at', 'updated_at']
    fieldsets = [
        ('Basic', {'fields': ['title', 'description', 'instructions', 'image_url', 'offer_url']}),
        ('Network', {'fields': ['network', 'category', 'external_offer_id']}),
        ('Reward', {'fields': ['reward_type', 'reward_amount', 'payout_amount']}),
        ('Settings', {'fields': ['status', 'is_featured', 'is_recurring', 'difficulty', 'estimated_time']}),
        ('Schedule', {'fields': ['starts_at', 'expires_at', 'max_completions']}),
        ('Stats', {'fields': ['total_completions', 'conversion_rate'], 'classes': ['collapse']}),
    ]

    actions = ['activate_offers', 'pause_offers', 'expire_offers']

    def activate_offers(self, request, qs):
        qs.update(status='active')
    activate_offers.short_description = '✅ অফার সক্রিয় করো'

    def pause_offers(self, request, qs):
        qs.update(status='paused')
    pause_offers.short_description = '⏸ অফার pause করো'

    def expire_offers(self, request, qs):
        qs.update(status='expired')
    expire_offers.short_description = '⌛ অফার expire করো'


@admin.register(SmartLink)
class SmartLinkAdmin(admin.ModelAdmin):
    list_display  = ['slug', 'algorithm', 'is_active', 'click_count']
    list_filter   = ['is_active', 'algorithm']
    filter_horizontal = ['offers']


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ['name', 'status', 'budget', 'spent', 'goal', 'starts_at', 'ends_at']
    list_filter  = ['status', 'goal']
    search_fields= ['name']


# ══════════════════════════════════════════════════════
# CLICK & CONVERSION
# ══════════════════════════════════════════════════════

@admin.register(Click)
class ClickAdmin(admin.ModelAdmin):
    list_display  = ['click_token_short', 'offer', 'user', 'ip_address', 'country_code', 'device_type', 'is_fraud', 'converted', 'created_at']
    list_filter   = ['is_fraud', 'converted', 'device_type', 'country_code']
    search_fields = ['click_token', 'ip_address', 'user__username']
    readonly_fields=['click_token', 'created_at']

    def click_token_short(self, obj):
        return obj.click_token[:16] + '...'
    click_token_short.short_description = 'Token'


@admin.register(Conversion)
class ConversionAdmin(admin.ModelAdmin):
    list_display   = ['id_short', 'offer', 'user', 'status', 'payout_amount', 'reward_amount', 'postback_sent', 'created_at']
    list_filter    = ['status', 'postback_sent', 'is_duplicate']
    search_fields  = ['transaction_id', 'user__username', 'offer__title']
    readonly_fields= ['created_at', 'updated_at']
    inlines        = [PostbackLogInline]

    def id_short(self, obj):
        return str(obj.id)[:8] + '...'
    id_short.short_description = 'ID'

    actions = ['approve_conversions', 'reject_conversions']

    def approve_conversions(self, request, qs):
        from .services import ConversionService
        for conv in qs.filter(status__name='pending'):
            ConversionService.approve_conversion(str(conv.id))
    approve_conversions.short_description = '✅ Approve করো'

    def reject_conversions(self, request, qs):
        from .repository import ConversionRepository
        for conv in qs.filter(status__name='pending'):
            ConversionRepository.reject_conversion(str(conv.id), 'Admin bulk reject')
    reject_conversions.short_description = '❌ Reject করো'


# ══════════════════════════════════════════════════════
# FRAUD & SECURITY
# ══════════════════════════════════════════════════════

@admin.register(BlacklistedIP)
class BlacklistedIPAdmin(admin.ModelAdmin):
    list_display  = ['ip_address', 'reason', 'source', 'is_permanent', 'expires_at', 'created_at']
    list_filter   = ['is_permanent', 'source']
    search_fields = ['ip_address', 'reason']
    actions       = ['make_permanent']

    def make_permanent(self, request, qs):
        qs.update(is_permanent=True, expires_at=None)
    make_permanent.short_description = '🔒 Permanent block করো'


@admin.register(FraudRule)
class FraudRuleAdmin(admin.ModelAdmin):
    list_display = ['name', 'action', 'severity', 'is_active', 'trigger_count']
    list_filter  = ['action', 'is_active']
    list_editable= ['is_active']


@admin.register(FraudAttempt)
class FraudAttemptAdmin(admin.ModelAdmin):
    list_display  = ['rule', 'user', 'ip_address', 'action_taken', 'is_resolved', 'created_at']
    list_filter   = ['is_resolved', 'action_taken']
    search_fields = ['user__username', 'ip_address']
    readonly_fields=['created_at', 'evidence']


@admin.register(UserRiskProfile)
class UserRiskProfileAdmin(admin.ModelAdmin):
    list_display  = ['user', 'risk_score', 'risk_level', 'total_flags', 'is_suspended']
    list_filter   = ['risk_level', 'is_suspended']
    search_fields = ['user__username']
    list_editable = ['is_suspended']
    ordering      = ['-risk_score']


@admin.register(HoneypotLog)
class HoneypotLogAdmin(admin.ModelAdmin):
    list_display = ['ip_address', 'trap_url', 'is_bot', 'blocked', 'created_at']
    list_filter  = ['is_bot', 'blocked']
    readonly_fields = ['created_at']


# ══════════════════════════════════════════════════════
# FINANCE
# ══════════════════════════════════════════════════════

@admin.register(WithdrawalRequest)
class WithdrawalRequestAdmin(admin.ModelAdmin):
    list_display  = ['reference_no', 'user', 'amount', 'fee', 'net_amount', 'status', 'created_at']
    list_filter   = ['status', 'currency']
    search_fields = ['reference_no', 'user__username']
    readonly_fields=['net_amount', 'created_at']
    actions       = ['approve_bulk']

    def approve_bulk(self, request, qs):
        from .services import WithdrawalService
        for wr in qs.filter(status='pending'):
            try:
                WithdrawalService.approve_withdrawal(str(wr.id), request.user)
            except Exception:
                pass
    approve_bulk.short_description = '✅ Approve করো'


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ['user', 'provider', 'is_primary', 'is_verified', 'last_used_at']
    list_filter  = ['provider', 'is_verified']


@admin.register(PayoutBatch)
class PayoutBatchAdmin(admin.ModelAdmin):
    list_display = ['batch_ref', 'status', 'total_amount', 'total_requests', 'processed_count', 'failed_count']
    list_filter  = ['status', 'payment_provider']


@admin.register(WalletAudit)
class WalletAuditAdmin(admin.ModelAdmin):
    list_display    = ['user', 'transaction_type', 'amount', 'balance_before', 'balance_after', 'created_at']
    list_filter     = ['transaction_type']
    search_fields   = ['user__username']
    readonly_fields = ['created_at']


# ══════════════════════════════════════════════════════
# USER
# ══════════════════════════════════════════════════════

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display  = ['user', 'loyalty_level', 'total_points', 'total_offers', 'is_verified']
    list_filter   = ['loyalty_level', 'is_verified']
    search_fields = ['user__username']


@admin.register(UserKYC)
class UserKYCAdmin(admin.ModelAdmin):
    list_display  = ['user', 'status', 'id_type', 'reviewed_at']
    list_filter   = ['status', 'id_type']
    search_fields = ['user__username', 'id_number']
    actions       = ['approve_kyc', 'reject_kyc']

    def approve_kyc(self, request, qs):
        qs.update(status='approved', reviewed_by=request.user, reviewed_at=timezone.now())
    approve_kyc.short_description = '✅ KYC অনুমোদন করো'

    def reject_kyc(self, request, qs):
        qs.update(status='rejected', reviewed_by=request.user, reviewed_at=timezone.now())
    reject_kyc.short_description = '❌ KYC বাতিল করো'


@admin.register(Achievement)
class AchievementAdmin(admin.ModelAdmin):
    list_display = ['name', 'points_award', 'is_active', 'is_hidden']
    list_editable= ['is_active']


@admin.register(LoyaltyLevel)
class LoyaltyLevelAdmin(admin.ModelAdmin):
    list_display = ['level_order', 'name', 'min_points', 'payout_bonus_pct']
    ordering     = ['level_order']


# ══════════════════════════════════════════════════════
# ANALYTICS & SYSTEM
# ══════════════════════════════════════════════════════

@admin.register(DailyStat)
class DailyStatAdmin(admin.ModelAdmin):
    list_display = ['date', 'total_clicks', 'total_conversions', 'total_revenue', 'active_users', 'fraud_attempts']
    ordering     = ['-date']
    readonly_fields = list_display


@admin.register(MasterSwitch)
class MasterSwitchAdmin(admin.ModelAdmin):
    list_display  = ['feature', 'is_enabled', 'toggled_by', 'toggled_at']
    list_editable = ['is_enabled']
    search_fields = ['feature']


@admin.register(SystemSetting)
class SystemSettingAdmin(admin.ModelAdmin):
    list_display  = ['key', 'value_type', 'is_public']
    search_fields = ['key']


@admin.register(FeedbackTicket)
class FeedbackTicketAdmin(admin.ModelAdmin):
    list_display  = ['ticket_no', 'user', 'subject', 'priority', 'status', 'created_at']
    list_filter   = ['priority', 'status']
    search_fields = ['ticket_no', 'user__username', 'subject']
    list_editable = ['status']


@admin.register(ErrorLog)
class ErrorLogAdmin(admin.ModelAdmin):
    list_display  = ['level', 'logger_name', 'message_short', 'is_resolved', 'created_at']
    list_filter   = ['level', 'is_resolved']
    readonly_fields=['traceback', 'created_at']

    def message_short(self, obj):
        return obj.message[:80]
    message_short.short_description = 'Message'


@admin.register(ABTestGroup)
class ABTestGroupAdmin(admin.ModelAdmin):
    list_display = ['name', 'status', 'traffic_split', 'winner', 'started_at', 'ended_at']
    list_filter  = ['status']


@admin.register(TaskQueue)
class TaskQueueAdmin(admin.ModelAdmin):
    list_display   = ['task_name', 'status', 'retry_count', 'started_at', 'completed_at']
    list_filter    = ['status', 'task_name']
    readonly_fields= ['task_id', 'args', 'kwargs', 'result', 'created_at']


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'notif_type', 'title', 'is_read', 'created_at']
    list_filter  = ['notif_type', 'is_read']
    search_fields= ['user__username', 'title']


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display   = ['user', 'action', 'model_name', 'object_id', 'ip_address', 'created_at']
    list_filter    = ['action', 'model_name']
    search_fields  = ['user__username', 'action']
    readonly_fields= ['changes', 'metadata', 'created_at']


@admin.register(BackupLog)
class BackupLogAdmin(admin.ModelAdmin):
    list_display = ['backup_type', 'status', 'file_size', 'duration_secs', 'created_at']
    list_filter  = ['backup_type', 'status']


# ══════════════════════════════════════════════════════
# MISSING MODEL REGISTRATIONS
# ══════════════════════════════════════════════════════

from api.users.models import UserDevice, LoginHistory as UserLoginHistory
from .models import (
    RevenueShare, TaxRecord, ReferralCommission, CommissionTier,
    ExpenseLog, BonusWallet, WalletTransaction, RefundRecord,
    UserSegment, ActivityHeatmap, UserFeedback, UserAchievement,
    ChurnRecord, UserInterest, UserLanguage, LoyaltyLevel,
    GeoData, ISPInfo,
    NetworkPinger, OfferRating, OfferQuestionnaire, OfferTag,
    OfferVisibilityRule, OfferSchedule, IncentiveLevel, OfferDraft,
    OfferLandingPage, Campaign, DirectAdvertiser, SmartLink, OfferCap,
    TrafficSource, TrackingDomain, SubID, Click, Impression,
    PostbackLog, ConversionReversal, ClickSignature, S2SRequest,
    RedirectLog, LeadQualityScore, DuplicateConversionFilter,
    ProxyList, VPNProvider, BotSignature, IPCluster, SecurityIncident,
    DeviceFingerprint, HoneypotLog, UserAgentBlacklist,
    AccountLink, SuspiciousActivity, RateLimitLog,
    PayoutBatch, Invoice, CurrencyRate, PaymentMethod,
    PushSubscription, EmailLog, DocumentationSnippet,
    WebhookConfig, CacheObject, PerformanceMetric,
    UserReferral, Achievement,
)


@admin.register(RevenueShare)
class RevenueShareAdmin(admin.ModelAdmin):
    list_display  = ['conversion', 'gross_revenue', 'platform_cut', 'user_share', 'referral_share', 'created_at']
    list_filter   = ['created_at']
    readonly_fields = ['created_at']


@admin.register(TaxRecord)
class TaxRecordAdmin(admin.ModelAdmin):
    list_display  = ['user', 'tax_type', 'rate', 'base_amount', 'tax_amount', 'fiscal_year']
    list_filter   = ['tax_type', 'fiscal_year']
    search_fields = ['user__username']


@admin.register(ReferralCommission)
class ReferralCommissionAdmin(admin.ModelAdmin):
    list_display  = ['referrer', 'referred_user', 'commission_pct', 'amount', 'is_paid', 'paid_at']
    list_filter   = ['is_paid']
    search_fields = ['referrer__username', 'referred_user__username']


@admin.register(CommissionTier)
class CommissionTierAdmin(admin.ModelAdmin):
    list_display  = ['name', 'min_referrals', 'commission_rate', 'is_active']
    list_editable = ['is_active']


@admin.register(ExpenseLog)
class ExpenseLogAdmin(admin.ModelAdmin):
    list_display  = ['category', 'amount', 'currency', 'invoice_ref', 'created_at']
    list_filter   = ['category', 'currency']


@admin.register(BonusWallet)
class BonusWalletAdmin(admin.ModelAdmin):
    list_display  = ['user', 'balance', 'source', 'expires_at', 'is_expired']
    list_filter   = ['is_expired']
    search_fields = ['user__username']


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display  = ['user', 'tx_type', 'amount', 'currency', 'source', 'balance_snapshot', 'created_at']
    list_filter   = ['tx_type', 'currency', 'source']
    search_fields = ['user__username']
    readonly_fields = ['created_at']


@admin.register(UserSegment)
class UserSegmentAdmin(admin.ModelAdmin):
    list_display  = ['name', 'user_count', 'is_dynamic', 'last_computed']
    list_editable = ['is_dynamic']


@admin.register(UserFeedback)
class UserFeedbackAdmin(admin.ModelAdmin):
    list_display  = ['user', 'feedback_type', 'subject', 'rating', 'is_resolved']
    list_filter   = ['feedback_type', 'is_resolved']
    list_editable = ['is_resolved']
    search_fields = ['user__username', 'subject']


@admin.register(ChurnRecord)
class ChurnRecordAdmin(admin.ModelAdmin):
    list_display  = ['user', 'churn_probability', 'days_inactive', 'is_churned', 'reactivation_sent']
    list_filter   = ['is_churned', 'reactivation_sent']
    ordering      = ['-churn_probability']


@admin.register(NetworkPinger)
class NetworkPingerAdmin(admin.ModelAdmin):
    list_display  = ['network', 'response_code', 'response_time', 'is_up', 'created_at']
    list_filter   = ['is_up', 'network']
    readonly_fields = ['created_at']


@admin.register(OfferRating)
class OfferRatingAdmin(admin.ModelAdmin):
    list_display  = ['offer', 'user', 'score', 'is_visible', 'created_at']
    list_filter   = ['score', 'is_visible']
    list_editable = ['is_visible']


@admin.register(OfferVisibilityRule)
class OfferVisibilityRuleAdmin(admin.ModelAdmin):
    list_display  = ['offer', 'rule_type', 'operator', 'is_active', 'priority']
    list_filter   = ['rule_type', 'operator', 'is_active']
    list_editable = ['is_active']


@admin.register(OfferSchedule)
class OfferScheduleAdmin(admin.ModelAdmin):
    list_display  = ['offer', 'action', 'scheduled_at', 'is_executed', 'executed_at']
    list_filter   = ['action', 'is_executed']


@admin.register(DirectAdvertiser)
class DirectAdvertiserAdmin(admin.ModelAdmin):
    list_display  = ['company_name', 'contact_email', 'agreed_rev_share', 'is_verified', 'is_active']
    list_filter   = ['is_verified', 'is_active']
    list_editable = ['is_verified', 'is_active']
    search_fields = ['company_name', 'contact_email']


@admin.register(TrafficSource)
class TrafficSourceAdmin(admin.ModelAdmin):
    list_display  = ['name', 'source_key', 'is_paid']
    list_editable = ['is_paid']


@admin.register(Impression)
class ImpressionAdmin(admin.ModelAdmin):
    list_display  = ['offer', 'user', 'ip_address', 'country', 'device', 'is_viewable', 'created_at']
    list_filter   = ['is_viewable', 'device']


@admin.register(PostbackLog)
class PostbackLogAdmin(admin.ModelAdmin):
    list_display  = ['conversion', 'url_short', 'method', 'response_code', 'is_success', 'retry_count', 'created_at']
    list_filter   = ['is_success', 'method']
    readonly_fields = ['created_at']

    def url_short(self, obj):
        return obj.url[:60]
    url_short.short_description = 'URL'


@admin.register(ClickSignature)
class ClickSignatureAdmin(admin.ModelAdmin):
    list_display  = ['click', 'algorithm', 'is_valid', 'verified_at']
    list_filter   = ['is_valid', 'algorithm']
    readonly_fields = ['created_at']


@admin.register(S2SRequest)
class S2SRequestAdmin(admin.ModelAdmin):
    list_display  = ['offer', 'source_ip', 'method', 'response_status', 'processed', 'created_at']
    list_filter   = ['processed', 'method']
    search_fields = ['source_ip']


@admin.register(LeadQualityScore)
class LeadQualityScoreAdmin(admin.ModelAdmin):
    list_display  = ['conversion', 'score', 'grade', 'calculated_at']
    list_filter   = ['grade']


@admin.register(DuplicateConversionFilter)
class DuplicateConversionFilterAdmin(admin.ModelAdmin):
    list_display  = ['offer', 'user', 'fingerprint_short', 'attempt_count', 'is_blocked', 'last_attempt']
    list_filter   = ['is_blocked']

    def fingerprint_short(self, obj):
        return obj.fingerprint[:16] + '...'
    fingerprint_short.short_description = 'Fingerprint'


@admin.register(ProxyList)
class ProxyListAdmin(admin.ModelAdmin):
    list_display  = ['ip_range', 'provider', 'proxy_type', 'risk_score', 'is_active']
    list_filter   = ['proxy_type', 'is_active']
    list_editable = ['is_active']


@admin.register(VPNProvider)
class VPNProviderAdmin(admin.ModelAdmin):
    list_display  = ['name', 'risk_level', 'is_active']
    list_editable = ['is_active']


@admin.register(BotSignature)
class BotSignatureAdmin(admin.ModelAdmin):
    list_display  = ['name', 'signature_type', 'severity', 'is_active', 'detections']
    list_editable = ['is_active']


@admin.register(IPCluster)
class IPClusterAdmin(admin.ModelAdmin):
    list_display  = ['label', 'isp', 'country', 'risk_score', 'is_flagged']
    list_filter   = ['is_flagged']
    list_editable = ['is_flagged']


@admin.register(SecurityIncident)
class SecurityIncidentAdmin(admin.ModelAdmin):
    list_display  = ['title', 'severity', 'is_resolved', 'created_at']
    list_filter   = ['severity', 'is_resolved']
    search_fields = ['title']
    list_editable = ['is_resolved']


@admin.register(DeviceFingerprint)
class DeviceFingerprintAdmin(admin.ModelAdmin):
    list_display  = ['user', 'fingerprint_short', 'is_flagged']
    list_filter   = ['is_flagged']
    search_fields = ['user__username']

    def fingerprint_short(self, obj):
        return obj.fingerprint[:16] + '...'
    fingerprint_short.short_description = 'Fingerprint'


@admin.register(UserAgentBlacklist)
class UserAgentBlacklistAdmin(admin.ModelAdmin):
    list_display  = ['pattern_short', 'is_regex', 'is_active', 'match_count']
    list_editable = ['is_active']

    def pattern_short(self, obj):
        return obj.pattern[:60]
    pattern_short.short_description = 'Pattern'


@admin.register(AccountLink)
class AccountLinkAdmin(admin.ModelAdmin):
    list_display  = ['primary_user', 'linked_user', 'link_method', 'confidence', 'is_confirmed', 'is_blocked']
    list_filter   = ['link_method', 'is_confirmed', 'is_blocked']
    list_editable = ['is_blocked']


@admin.register(SuspiciousActivity)
class SuspiciousActivityAdmin(admin.ModelAdmin):
    list_display  = ['user', 'activity', 'risk_score', 'ip_address', 'reviewed', 'created_at']
    list_filter   = ['reviewed']
    list_editable = ['reviewed']


@admin.register(RateLimitLog)
class RateLimitLogAdmin(admin.ModelAdmin):
    list_display  = ['ip_address', 'user', 'endpoint', 'request_count', 'blocked', 'created_at']
    list_filter   = ['blocked']


@admin.register(CurrencyRate)
class CurrencyRateAdmin(admin.ModelAdmin):
    list_display  = ['from_currency', 'to_currency', 'rate', 'source', 'fetched_at']
    list_filter   = ['source']


@admin.register(GeoData)
class GeoDataAdmin(admin.ModelAdmin):
    list_display  = ['ip_address', 'country_code', 'city', 'isp', 'is_vpn', 'is_proxy']
    list_filter   = ['country_code', 'is_vpn', 'is_proxy']
    search_fields = ['ip_address', 'city']


@admin.register(ISPInfo)
class ISPInfoAdmin(admin.ModelAdmin):
    list_display  = ['asn', 'name', 'country', 'is_mobile', 'is_hosting', 'risk_level']
    list_filter   = ['is_mobile', 'is_hosting', 'risk_level']


@admin.register(UserReferral)
class UserReferralAdmin(admin.ModelAdmin):
    list_display  = ['referrer', 'referred', 'referral_code', 'is_converted', 'total_earnings_generated', 'created_at']
    list_filter   = ['is_converted']
    search_fields = ['referrer__username', 'referred__username', 'referral_code']


@admin.register(PushSubscription)
class PushSubscriptionAdmin(admin.ModelAdmin):
    list_display  = ['user', 'is_active', 'user_agent_short', 'last_used']
    list_filter   = ['is_active']
    search_fields = ['user__username']

    def user_agent_short(self, obj):
        return obj.user_agent[:60]
    user_agent_short.short_description = 'UA'


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    list_display  = ['recipient', 'subject_short', 'status', 'sent_at', 'opened_at']
    list_filter   = ['status']
    search_fields = ['recipient', 'subject']

    def subject_short(self, obj):
        return obj.subject[:60]
    subject_short.short_description = 'Subject'


@admin.register(WebhookConfig)
class WebhookConfigAdmin(admin.ModelAdmin):
    list_display  = ['name', 'url_short', 'is_active', 'retry_count', 'last_status']
    list_editable = ['is_active']

    def url_short(self, obj):
        return obj.url[:60]
    url_short.short_description = 'URL'


@admin.register(PerformanceMetric)
class PerformanceMetricAdmin(admin.ModelAdmin):
    list_display  = ['endpoint', 'method', 'avg_ms', 'p95_ms', 'error_rate', 'request_count', 'recorded_at']
    list_filter   = ['method']
    ordering      = ['-recorded_at']


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display  = ['invoice_no', 'advertiser', 'amount', 'currency', 'is_paid', 'due_at', 'paid_at']
    list_filter   = ['is_paid', 'currency']
    search_fields = ['invoice_no', 'advertiser__company_name']
    list_editable = ['is_paid']


@admin.register(OfferDraft)
class OfferDraftAdmin(admin.ModelAdmin):
    list_display  = ['title', 'created_by', 'is_submitted', 'last_edited']
    list_filter   = ['is_submitted']


@admin.register(IncentiveLevel)
class IncentiveLevelAdmin(admin.ModelAdmin):
    list_display  = ['name', 'required_actions', 'bonus_amount', 'reward_type', 'is_active']
    list_editable = ['is_active']
    ordering      = ['required_actions']


@admin.register(ConversionReversal)
class ConversionReversalAdmin(admin.ModelAdmin):
    list_display  = ['conversion', 'reversed_by', 'amount_clawed', 'wallet_debited', 'created_at']
    list_filter   = ['wallet_debited']
    readonly_fields = ['created_at']


# ══════════════════════════════════════════════════════
# RTB ENGINE ADMIN
# ══════════════════════════════════════════════════════

@admin.register(BidLog)
class BidLogAdmin(admin.ModelAdmin):
    list_display  = ['request_id', 'publisher_id', 'ecpm', 'clearing_price', 'is_won', 'no_bid', 'response_ms', 'country', 'device_type', 'created_at']
    list_filter   = ['is_won', 'no_bid', 'device_type', 'country']
    search_fields = ['request_id', 'publisher_id', 'offer_id']
    readonly_fields = ['request_id', 'created_at']
    ordering      = ['-created_at']


@admin.register(DSPConfig)
class DSPConfigAdmin(admin.ModelAdmin):
    list_display  = ['name', 'endpoint_url', 'is_active', 'timeout_ms', 'revenue_share', 'created_at']
    list_filter   = ['is_active']
    search_fields = ['name']


@admin.register(PublisherConfig)
class PublisherConfigAdmin(admin.ModelAdmin):
    list_display  = ['publisher_id', 'is_active', 'created_at']
    search_fields = ['publisher_id']


# ══════════════════════════════════════════════════════
# PUBLISHER SDK ADMIN
# ══════════════════════════════════════════════════════

@admin.register(Publisher)
class PublisherAdmin(admin.ModelAdmin):
    list_display  = ['company_name', 'contact_email', 'app_type', 'status', 'revenue_share', 'total_earned', 'approved_at', 'created_at']
    list_filter   = ['status', 'app_type']
    search_fields = ['company_name', 'contact_email']
    readonly_fields = ['api_key', 'created_at', 'approved_at']
    actions       = ['approve_publishers']

    def approve_publishers(self, request, queryset):
        from django.utils import timezone
        queryset.update(status='active', approved_at=timezone.now(), approved_by=request.user)
        self.message_user(request, f'{queryset.count()} publishers approved.')
    approve_publishers.short_description = 'Approve selected publishers'


@admin.register(PublisherApp)
class PublisherAppAdmin(admin.ModelAdmin):
    list_display  = ['name', 'publisher', 'platform', 'bundle_id', 'status', 'total_revenue', 'created_at']
    list_filter   = ['platform', 'status']
    search_fields = ['name', 'bundle_id', 'publisher__company_name']
    readonly_fields = ['app_key']


@admin.register(AppPlacement)
class AppPlacementAdmin(admin.ModelAdmin):
    list_display  = ['name', 'app', 'placement_type', 'position', 'is_active', 'ecpm_floor']
    list_filter   = ['placement_type', 'is_active']
    search_fields = ['name', 'placement_id']


@admin.register(PublisherPayout)
class PublisherPayoutAdmin(admin.ModelAdmin):
    list_display  = ['publisher', 'amount', 'currency', 'method', 'status', 'paid_at', 'created_at']
    list_filter   = ['status', 'method', 'currency']
    search_fields = ['publisher__company_name', 'reference_no']
    readonly_fields = ['created_at']


@admin.register(PublisherRevenue)
class PublisherRevenueAdmin(admin.ModelAdmin):
    list_display  = ['publisher', 'app', 'date', 'impressions', 'gross_revenue', 'publisher_share', 'ecpm']
    list_filter   = ['date']
    search_fields = ['publisher__company_name']
    date_hierarchy = 'date'
