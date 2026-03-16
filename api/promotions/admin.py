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
