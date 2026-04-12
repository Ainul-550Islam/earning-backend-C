# =============================================================================
# api/promotions/admin.py
# Django Admin — সব model এর জন্য full admin configuration
# =============================================================================

from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.db.models import Count, Sum

from .models import (
    PromotionCategory, Platform, RewardPolicy, AdCreative, CurrencyRate,
    Campaign, TargetingCondition, TaskStep, TaskLimit, BonusPolicy, CampaignSchedule,
    TaskSubmission, SubmissionProof, VerificationLog, Dispute,
    PromotionTransaction, EscrowWallet, AdminCommissionLog, ReferralCommissionLog,
    UserReputation, FraudReport, DeviceFingerprint, Blacklist, CampaignAnalytics,
)


# ─── Inlines ─────────────────────────────────────────────────────────────────

class TaskStepInline(admin.TabularInline):
    model  = TaskStep
    extra  = 1
    fields = ['step_order', 'instruction', 'proof_type', 'is_required']
    ordering = ['step_order']


class TargetingConditionInline(admin.StackedInline):
    model  = TargetingCondition
    extra  = 0
    fields = ['countries', 'devices', 'os_types', 'min_user_level', 'max_user_level', 'min_reputation_score']


class TaskLimitInline(admin.StackedInline):
    model  = TaskLimit
    extra  = 0
    fields = ['max_per_ip', 'max_per_device', 'max_per_user', 'cooldown_hours']


class CampaignScheduleInline(admin.StackedInline):
    model  = CampaignSchedule
    extra  = 0


class BonusPolicyInline(admin.TabularInline):
    model  = BonusPolicy
    extra  = 0
    fields = ['condition_type', 'threshold_value', 'bonus_percent', 'is_active']


class SubmissionProofInline(admin.TabularInline):
    model     = SubmissionProof
    extra     = 0
    readonly_fields = ['proof_type', 'content', 'file_size_kb', 'uploaded_at']
    can_delete = False


class VerificationLogInline(admin.TabularInline):
    model     = VerificationLog
    extra     = 0
    readonly_fields = ['verified_by', 'ai_confidence_score', 'decision', 'reason', 'verified_at']
    can_delete = False


# ─── System Foundation ───────────────────────────────────────────────────────

@admin.register(PromotionCategory)
class PromotionCategoryAdmin(admin.ModelAdmin):
    list_display  = ['name', 'is_active', 'sort_order', 'created_at']
    list_filter   = ['is_active']
    search_fields = ['name']
    ordering      = ['sort_order']


@admin.register(Platform)
class PlatformAdmin(admin.ModelAdmin):
    list_display  = ['name', 'base_url', 'is_active']
    list_filter   = ['is_active']
    search_fields = ['name']


@admin.register(RewardPolicy)
class RewardPolicyAdmin(admin.ModelAdmin):
    list_display  = ['country_code', 'category', 'rate_usd', 'min_payout_usd', 'is_active']
    list_filter   = ['is_active', 'category', 'country_code']
    search_fields = ['country_code']
    ordering      = ['country_code']


@admin.register(CurrencyRate)
class CurrencyRateAdmin(admin.ModelAdmin):
    list_display  = ['from_currency', 'to_currency', 'rate', 'source', 'fetched_at']
    list_filter   = ['from_currency', 'to_currency', 'source']
    ordering      = ['-fetched_at']
    readonly_fields = ['fetched_at']


# ─── Campaign ────────────────────────────────────────────────────────────────

@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display   = [
        'id', 'title', 'advertiser', 'category', 'platform',
        'status_badge', 'budget_display', 'slot_display', 'created_at',
    ]
    list_filter    = ['status', 'category', 'platform', 'created_at']
    search_fields  = ['title', 'advertiser__username', 'uuid']
    readonly_fields = ['uuid', 'spent_usd', 'filled_slots', 'created_at', 'updated_at']
    inlines        = [
        TargetingConditionInline, TaskStepInline, TaskLimitInline,
        CampaignScheduleInline, BonusPolicyInline,
    ]
    actions        = ['approve_campaigns', 'pause_campaigns', 'cancel_campaigns']
    date_hierarchy = 'created_at'

    fieldsets = (
        (_('Basic Info'), {
            'fields': ('uuid', 'advertiser', 'title', 'description', 'category', 'platform', 'target_url')
        }),
        (_('Budget & Slots'), {
            'fields': ('total_budget_usd', 'spent_usd', 'profit_margin', 'total_slots', 'filled_slots')
        }),
        (_('Status'), {
            'fields': ('status', 'rejection_reason')
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def status_badge(self, obj):
        colors = {
            'draft': '#gray', 'pending': '#orange', 'active': '#green',
            'paused': '#blue', 'completed': '#purple', 'cancelled': '#red',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;border-radius:3px">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = _('Status')

    def budget_display(self, obj):
        return format_html('${} / ${}', obj.spent_usd, obj.total_budget_usd)
    budget_display.short_description = _('Spent / Budget')

    def slot_display(self, obj):
        return format_html('{} / {} ({}%)', obj.filled_slots, obj.total_slots, obj.fill_percentage)
    slot_display.short_description = _('Slots')

    @admin.action(description=_('Selected campaigns approve করুন'))
    def approve_campaigns(self, request, queryset):
        from .choices import CampaignStatus
        count = queryset.filter(status=CampaignStatus.PENDING).update(status=CampaignStatus.ACTIVE)
        self.message_user(request, _(f'{count} campaign(s) approved.'))

    @admin.action(description=_('Selected campaigns pause করুন'))
    def pause_campaigns(self, request, queryset):
        from .choices import CampaignStatus
        count = queryset.filter(status=CampaignStatus.ACTIVE).update(status=CampaignStatus.PAUSED)
        self.message_user(request, _(f'{count} campaign(s) paused.'))

    @admin.action(description=_('Selected campaigns cancel করুন'))
    def cancel_campaigns(self, request, queryset):
        from .choices import CampaignStatus
        count = queryset.exclude(
            status__in=[CampaignStatus.COMPLETED, CampaignStatus.CANCELLED]
        ).update(status=CampaignStatus.CANCELLED)
        self.message_user(request, _(f'{count} campaign(s) cancelled.'))


# ─── Task Submission ─────────────────────────────────────────────────────────

@admin.register(TaskSubmission)
class TaskSubmissionAdmin(admin.ModelAdmin):
    list_display   = [
        'id', 'worker', 'campaign', 'status_badge',
        'reward_usd', 'bonus_usd', 'ip_address', 'submitted_at',
    ]
    list_filter    = ['status', 'submitted_at', 'campaign__category']
    search_fields  = ['worker__username', 'ip_address', 'uuid']
    readonly_fields = ['uuid', 'worker', 'campaign', 'ip_address', 'submitted_at', 'created_at']
    inlines        = [SubmissionProofInline, VerificationLogInline]
    actions        = ['bulk_approve', 'bulk_reject']
    date_hierarchy = 'submitted_at'

    def status_badge(self, obj):
        colors = {
            'pending': 'orange', 'approved': 'green',
            'rejected': 'red', 'disputed': 'purple', 'expired': 'gray',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;border-radius:3px">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = _('Status')

    @admin.action(description=_('Selected submissions approve করুন'))
    def bulk_approve(self, request, queryset):
        from .choices import SubmissionStatus
        from django.utils import timezone
        count = queryset.filter(status=SubmissionStatus.PENDING).update(
            status=SubmissionStatus.APPROVED,
            reviewer=request.user,
            reviewed_at=timezone.now(),
            review_note='Bulk approved by admin.',
        )
        self.message_user(request, _(f'{count} submission(s) approved.'))

    @admin.action(description=_('Selected submissions reject করুন'))
    def bulk_reject(self, request, queryset):
        from .choices import SubmissionStatus
        from django.utils import timezone
        count = queryset.filter(status=SubmissionStatus.PENDING).update(
            status=SubmissionStatus.REJECTED,
            reviewer=request.user,
            reviewed_at=timezone.now(),
            review_note='Bulk rejected by admin.',
        )
        self.message_user(request, _(f'{count} submission(s) rejected.'))


@admin.register(Dispute)
class DisputeAdmin(admin.ModelAdmin):
    list_display  = ['id', 'worker', 'submission', 'status', 'created_at', 'resolved_at']
    list_filter   = ['status', 'created_at']
    search_fields = ['worker__username']
    readonly_fields = ['submission', 'worker', 'created_at']


# ─── Finance ─────────────────────────────────────────────────────────────────

@admin.register(PromotionTransaction)
class PromotionTransactionAdmin(admin.ModelAdmin):
    list_display  = ['id', 'type', 'user', 'amount_usd', 'currency_code', 'balance_after', 'created_at']
    list_filter   = ['type', 'currency_code', 'is_reversed', 'created_at']
    search_fields = ['user__username', 'uuid']
    readonly_fields = list(
        ['id', 'uuid', 'type', 'user', 'campaign', 'amount_usd', 'currency_code',
         'amount_local', 'balance_after', 'reference_id', 'note', 'is_reversed', 'created_at']
    )

    def has_add_permission(self, request):
        return False  # Transaction programmatically তৈরি হবে

    def has_delete_permission(self, request, obj=None):
        return False  # Transaction delete করা যাবে না


@admin.register(EscrowWallet)
class EscrowWalletAdmin(admin.ModelAdmin):
    list_display  = ['campaign', 'advertiser', 'locked_amount_usd', 'released_amount_usd', 'status']
    list_filter   = ['status']
    readonly_fields = ['campaign', 'advertiser', 'locked_amount_usd', 'locked_at']


@admin.register(AdminCommissionLog)
class AdminCommissionLogAdmin(admin.ModelAdmin):
    list_display  = ['submission', 'campaign', 'gross_amount_usd', 'worker_reward_usd', 'commission_usd', 'commission_rate', 'created_at']
    list_filter   = ['created_at']
    readonly_fields = ['submission', 'campaign', 'gross_amount_usd', 'worker_reward_usd', 'commission_usd', 'commission_rate', 'created_at']


# ─── Security ────────────────────────────────────────────────────────────────

@admin.register(FraudReport)
class FraudReportAdmin(admin.ModelAdmin):
    list_display  = ['id', 'user', 'fraud_type', 'confidence_score', 'action_taken', 'created_at']
    list_filter   = ['fraud_type', 'action_taken', 'created_at']
    search_fields = ['user__username']
    readonly_fields = ['user', 'submission', 'fraud_type', 'ai_model_version', 'confidence_score', 'evidence', 'created_at']
    actions       = ['mark_as_banned', 'mark_as_ignored']

    @admin.action(description=_('Selected users ban করুন'))
    def mark_as_banned(self, request, queryset):
        count = queryset.update(action_taken='banned', reviewed_by_admin=request.user)
        self.message_user(request, _(f'{count} fraud report(s) marked as banned.'))

    @admin.action(description=_('Selected reports ignore করুন'))
    def mark_as_ignored(self, request, queryset):
        count = queryset.update(action_taken='ignored', reviewed_by_admin=request.user)
        self.message_user(request, _(f'{count} fraud report(s) marked as ignored.'))


@admin.register(Blacklist)
class BlacklistAdmin(admin.ModelAdmin):
    list_display  = ['type', 'value', 'severity', 'is_active', 'expires_at', 'added_by', 'created_at']
    list_filter   = ['type', 'severity', 'is_active']
    search_fields = ['value', 'reason']
    readonly_fields = ['added_by', 'created_at']

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.added_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(UserReputation)
class UserReputationAdmin(admin.ModelAdmin):
    list_display  = ['user', 'trust_score', 'success_rate', 'level', 'total_submissions', 'is_verified_worker']
    list_filter   = ['is_verified_worker', 'level']
    search_fields = ['user__username']
    readonly_fields = [
        'total_submissions', 'approved_count', 'rejected_count',
        'disputed_count', 'success_rate', 'last_updated',
    ]


@admin.register(DeviceFingerprint)
class DeviceFingerprintAdmin(admin.ModelAdmin):
    list_display  = ['user', 'fingerprint_hash_short', 'device_type', 'os', 'is_flagged', 'linked_account_count', 'last_seen']
    list_filter   = ['is_flagged', 'device_type']
    search_fields = ['fingerprint_hash', 'user__username']
    readonly_fields = ['fingerprint_hash', 'first_seen', 'last_seen']

    def fingerprint_hash_short(self, obj):
        return obj.fingerprint_hash[:16] + '...'
    fingerprint_hash_short.short_description = _('Fingerprint')


@admin.register(CampaignAnalytics)
class CampaignAnalyticsAdmin(admin.ModelAdmin):
    list_display  = [
        'campaign', 'date', 'total_submissions', 'approved_count',
        'total_spent_usd', 'admin_commission_usd',
    ]
    list_filter   = ['date', 'campaign__category']
    date_hierarchy = 'date'
    readonly_fields = [f.name for f in CampaignAnalytics._meta.fields]


# Force register all models
from django.apps import apps as _apps
_app_label = __name__.split(chr(46))[1]
for _model in _apps.get_app_config(_app_label).get_models():
    try:
        admin.site.register(_model)
    except admin.sites.AlreadyRegistered:
        pass


def _force_register_promotions():
    try:
        from api.admin_panel.admin import admin_site as modern_site
        if modern_site is None:
            return
        pairs = [(PromotionCategory, PromotionCategoryAdmin), (Platform, PlatformAdmin), (RewardPolicy, RewardPolicyAdmin), (CurrencyRate, CurrencyRateAdmin), (Campaign, CampaignAdmin), (TaskSubmission, TaskSubmissionAdmin), (Dispute, DisputeAdmin), (PromotionTransaction, PromotionTransactionAdmin), (EscrowWallet, EscrowWalletAdmin), (AdminCommissionLog, AdminCommissionLogAdmin), (FraudReport, FraudReportAdmin), (Blacklist, BlacklistAdmin), (UserReputation, UserReputationAdmin), (DeviceFingerprint, DeviceFingerprintAdmin), (CampaignAnalytics, CampaignAnalyticsAdmin)]
        registered = 0
        for model, model_admin in pairs:
            try:
                if model not in modern_site._registry:
                    modern_site.register(model, model_admin)
                    registered += 1
            except Exception as ex:
                pass
        print(f"[OK] promotions registered {registered} models")
    except Exception as e:
        print(f"[WARN] promotions: {e}")


# =============================================================================
# NEW MODELS ADMIN REGISTRATION
# =============================================================================

from api.promotions.models import (
    PublisherProfile, AdvertiserProfile, APIKeyModel, WebhookConfigModel,
    VirtualCurrencyConfig, WhiteLabelConfig, EmailSubmitCampaign,
    EmailSubmitConversion, CPCCampaign, CPIAppCampaign, QuizCampaign,
    SmartLinkConfig, ContentLockModel, SubIDClick, PayoutBatch,
    IPBlacklistModel, TrackingDomain, SystemConfig,
)


@admin.register(PublisherProfile)
class PublisherProfileAdmin(admin.ModelAdmin):
    list_display  = ('user', 'tier', 'approval_status', 'country', 'total_earned', 'created_at')
    list_filter   = ('tier', 'approval_status', 'country')
    search_fields = ('user__username', 'user__email', 'website_url')
    readonly_fields = ('total_earned', 'total_withdrawn', 'created_at')
    actions       = ['approve_publishers', 'reject_publishers']

    @admin.action(description='Approve selected publishers')
    def approve_publishers(self, request, qs):
        from django.utils import timezone
        qs.update(approval_status='approved', approved_at=timezone.now())

    @admin.action(description='Reject selected publishers')
    def reject_publishers(self, request, qs):
        qs.update(approval_status='rejected')


@admin.register(AdvertiserProfile)
class AdvertiserProfileAdmin(admin.ModelAdmin):
    list_display  = ('user', 'company_name', 'country', 'total_deposited', 'total_spent', 'is_verified')
    list_filter   = ('is_verified', 'country')
    search_fields = ('user__username', 'user__email', 'company_name')


@admin.register(APIKeyModel)
class APIKeyModelAdmin(admin.ModelAdmin):
    list_display  = ('user', 'name', 'is_active', 'rate_limit', 'total_requests', 'last_used', 'created_at')
    list_filter   = ('is_active',)
    search_fields = ('user__username', 'name')
    readonly_fields = ('key_hash', 'total_requests', 'last_used')

    def has_add_permission(self, request):
        return False  # Keys generated via API only


@admin.register(WebhookConfigModel)
class WebhookConfigModelAdmin(admin.ModelAdmin):
    list_display  = ('publisher', 'event', 'method', 'is_active', 'total_fires', 'last_fired', 'last_status_code')
    list_filter   = ('event', 'method', 'is_active')
    search_fields = ('publisher__username', 'url')


@admin.register(VirtualCurrencyConfig)
class VirtualCurrencyConfigAdmin(admin.ModelAdmin):
    list_display  = ('publisher', 'currency_name', 'currency_icon', 'usd_to_vc_rate', 'is_active')
    list_filter   = ('is_active',)
    search_fields = ('publisher__username', 'currency_name')


@admin.register(WhiteLabelConfig)
class WhiteLabelConfigAdmin(admin.ModelAdmin):
    list_display  = ('publisher', 'brand_name', 'custom_domain', 'is_active', 'created_at')
    list_filter   = ('is_active',)
    search_fields = ('publisher__username', 'brand_name', 'custom_domain')


@admin.register(EmailSubmitCampaign)
class EmailSubmitCampaignAdmin(admin.ModelAdmin):
    list_display  = ('campaign_name', 'advertiser', 'opt_in_type', 'payout', 'daily_cap', 'today_submits', 'total_submits', 'status')
    list_filter   = ('opt_in_type', 'status', 'niche')
    search_fields = ('campaign_name', 'advertiser__username')
    readonly_fields = ('today_submits', 'total_submits', 'total_spent')
    list_editable   = ('status',)


@admin.register(EmailSubmitConversion)
class EmailSubmitConversionAdmin(admin.ModelAdmin):
    list_display  = ('campaign', 'publisher', 'country', 'is_confirmed', 'is_paid', 'payout_amount', 'created_at')
    list_filter   = ('is_confirmed', 'is_paid', 'country')
    readonly_fields = ('email_hash', 'ip_hash', 'payout_amount')


@admin.register(CPCCampaign)
class CPCCampaignAdmin(admin.ModelAdmin):
    list_display  = ('title', 'advertiser', 'payout_us', 'daily_cap', 'today_clicks', 'total_clicks', 'total_spent', 'status')
    list_filter   = ('status',)
    search_fields = ('title', 'advertiser__username')
    readonly_fields = ('today_clicks', 'total_clicks', 'total_spent')


@admin.register(CPIAppCampaign)
class CPIAppCampaignAdmin(admin.ModelAdmin):
    list_display  = ('app_name', 'advertiser', 'platform', 'payout_per_install', 'mmp_provider', 'daily_cap', 'today_installs', 'status')
    list_filter   = ('platform', 'mmp_provider', 'status')
    search_fields = ('app_name', 'bundle_id', 'advertiser__username')


@admin.register(QuizCampaign)
class QuizCampaignAdmin(admin.ModelAdmin):
    list_display  = ('title', 'advertiser', 'quiz_type', 'payout', 'daily_cap', 'today_completions', 'total_completions', 'status')
    list_filter   = ('quiz_type', 'status')
    search_fields = ('title', 'advertiser__username')


@admin.register(SmartLinkConfig)
class SmartLinkConfigAdmin(admin.ModelAdmin):
    list_display  = ('publisher', 'name', 'link_hash', 'total_clicks', 'total_earnings', 'is_active')
    list_filter   = ('is_active',)
    search_fields = ('publisher__username', 'name', 'link_hash')
    readonly_fields = ('link_hash', 'total_clicks', 'total_earnings')


@admin.register(ContentLockModel)
class ContentLockModelAdmin(admin.ModelAdmin):
    list_display  = ('publisher', 'lock_type', 'title', 'required_offers', 'total_views', 'total_unlocks', 'total_earnings', 'is_active')
    list_filter   = ('lock_type', 'is_active')
    search_fields = ('publisher__username', 'title', 'lock_token')
    readonly_fields = ('lock_token', 'total_views', 'total_unlocks', 'total_earnings')


@admin.register(SubIDClick)
class SubIDClickAdmin(admin.ModelAdmin):
    list_display  = ('publisher', 'click_id', 's1', 's2', 'country', 'device', 'is_converted', 'payout', 'created_at')
    list_filter   = ('is_converted', 'country', 'device')
    search_fields = ('click_id', 'publisher__username', 's1', 's2')
    readonly_fields = ('click_id', 'ip_hash')
    date_hierarchy  = 'created_at'


@admin.register(PayoutBatch)
class PayoutBatchAdmin(admin.ModelAdmin):
    list_display  = ('batch_id', 'publisher', 'amount', 'method', 'status', 'fee', 'net_amount', 'tx_hash', 'created_at')
    list_filter   = ('status', 'method')
    search_fields = ('publisher__username', 'tx_hash')
    readonly_fields = ('batch_id', 'fee', 'net_amount')
    list_editable   = ('status',)
    actions         = ['mark_completed', 'mark_failed']

    @admin.action(description='Mark selected payouts as completed')
    def mark_completed(self, request, qs):
        from django.utils import timezone
        qs.update(status='completed', processed_at=timezone.now(), processed_by=request.user)

    @admin.action(description='Mark selected payouts as failed')
    def mark_failed(self, request, qs):
        qs.update(status='failed')


@admin.register(IPBlacklistModel)
class IPBlacklistModelAdmin(admin.ModelAdmin):
    list_display  = ('ip_address', 'reason', 'severity', 'is_active', 'hit_count', 'last_hit', 'created_at')
    list_filter   = ('severity', 'is_active')
    search_fields = ('ip_address', 'reason', 'cidr')
    readonly_fields = ('hit_count', 'last_hit')


@admin.register(TrackingDomain)
class TrackingDomainAdmin(admin.ModelAdmin):
    list_display  = ('domain', 'publisher', 'is_verified', 'ssl_enabled', 'total_clicks', 'is_active')
    list_filter   = ('is_verified', 'ssl_enabled', 'is_active')
    search_fields = ('domain', 'publisher__username')
    actions       = ['verify_domains']

    @admin.action(description='Mark selected domains as verified')
    def verify_domains(self, request, qs):
        from django.utils import timezone
        qs.update(is_verified=True, verified_at=timezone.now())


@admin.register(SystemConfig)
class SystemConfigAdmin(admin.ModelAdmin):
    list_display  = ('key', 'value_type', 'is_public', 'updated_at', 'updated_by')
    list_filter   = ('value_type', 'is_public')
    search_fields = ('key', 'description')
    readonly_fields = ('updated_at',)

    def save_model(self, request, obj, form, change):
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
