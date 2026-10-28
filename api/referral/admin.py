# api/referral/admin.py
# Django admin — পুরনো সব admin classes preserved + নতুন models registered
# ============================================================

from django.contrib import admin
from django.contrib.admin import ModelAdmin, TabularInline, StackedInline
from django.utils.html import format_html
from django.utils import timezone
from django.db.models import Count, Sum, Q
from django.core.exceptions import ValidationError
from django import forms
from django.http import HttpResponse
from django.contrib import messages
from decimal import Decimal
import csv
import io

from .models import (
    ReferralSettings, Referral, ReferralEarning, ReferralChain,
    ReferralLeaderboard, ReferralLink, ReferralCode,
    ReferralRelationship, ReferralTree, ReferralLevel,
    CommissionRule, CommissionLog, CommissionPayout,
    CommissionHold, CommissionClawback,
    ReferralCampaign, ReferralBonus, ReferralBonusClaim,
    ReferralContest, ReferralReward, ContestEntry,
    ReferralFraudRule, ReferralFraudLog, ReferralBlacklist,
    SuspiciousReferral,
    ReferralInsight, ReferralConversionRate, TopReferrer, ReferralLTV,
)


# ══════════════════════════════════════════════════════════════
# FORMS
# ══════════════════════════════════════════════════════════════

class ReferralSettingsForm(forms.ModelForm):
    class Meta:
        model = ReferralSettings
        fields = '__all__'
        widgets = {
            'direct_signup_bonus': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'referrer_signup_bonus': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'level1_commission_rate': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'max': '100'}),
            'level2_commission_rate': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'max': '100'}),
            'level3_commission_rate': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'max': '100'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        for field in ['level1_commission_rate', 'level2_commission_rate', 'level3_commission_rate']:
            rate = cleaned_data.get(field)
            if rate is not None:
                if rate < 0:
                    raise ValidationError({field: 'Commission rate cannot be negative.'})
                if rate > 100:
                    raise ValidationError({field: 'Commission rate cannot exceed 100%.'})
        return cleaned_data


class ReferralForm(forms.ModelForm):
    class Meta:
        model = Referral
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()
        referrer = cleaned_data.get('referrer')
        referred_user = cleaned_data.get('referred_user')
        if referrer and referred_user and referrer == referred_user:
            raise ValidationError('A user cannot refer themselves.')
        if referrer and referred_user:
            existing = Referral.objects.filter(
                referrer=referrer, referred_user=referred_user
            ).exists()
            if existing and not self.instance.pk:
                raise ValidationError('This referral relationship already exists.')
        return cleaned_data


# ══════════════════════════════════════════════════════════════
# INLINES
# ══════════════════════════════════════════════════════════════

class ReferralEarningInline(TabularInline):
    model = ReferralEarning
    extra = 0
    readonly_fields = ('level', 'amount', 'commission_rate', 'source_type', 'status', 'created_at')
    fields = ('level', 'referred_user', 'amount', 'commission_rate', 'source_type', 'status', 'created_at')
    can_delete = False
    max_num = 20


class CommissionLogInline(TabularInline):
    model = CommissionLog
    extra = 0
    readonly_fields = ('level', 'amount', 'action_type', 'status', 'created_at')
    fields = ('level', 'referred_user', 'amount', 'action_type', 'status', 'created_at')
    can_delete = False
    max_num = 10


class ReferralBonusInline(TabularInline):
    model = ReferralBonus
    extra = 1
    fields = ('milestone_type', 'milestone_value', 'bonus_amount', 'reward_type', 'is_active')


class ReferralRewardInline(TabularInline):
    model = ReferralReward
    extra = 3
    fields = ('rank', 'rank_to', 'reward_type', 'reward_value', 'reward_description', 'status')


class SuspiciousReferralInline(StackedInline):
    model = SuspiciousReferral
    extra = 0
    readonly_fields = ('fraud_score', 'flags', 'evidence', 'status', 'detected_at')
    can_delete = False
    max_num = 1


# ══════════════════════════════════════════════════════════════
# ADMIN CLASSES
# ══════════════════════════════════════════════════════════════

@admin.register(ReferralSettings)
class ReferralSettingsAdmin(ModelAdmin):
    form = ReferralSettingsForm
    list_display = (
        '__str__', 'level1_commission_rate', 'level2_commission_rate',
        'level3_commission_rate', 'commission_hold_days',
        'active_campaign', 'is_active',
    )
    fieldsets = (
        ('Signup Bonuses', {
            'fields': ('direct_signup_bonus', 'referrer_signup_bonus')
        }),
        ('Commission Rates', {
            'fields': (
                'level1_commission_rate', 'level2_commission_rate',
                'level3_commission_rate', 'commission_hold_days',
            )
        }),
        ('Active Campaign', {
            'fields': ('active_campaign',)
        }),
        ('Settings', {
            'fields': (
                'is_active', 'max_referral_depth',
                'min_payout_threshold', 'referral_cookie_days',
                'allow_self_referral',
            )
        }),
        ('Team Bonus', {
            'fields': (
                'team_bonus_enabled', 'team_bonus_min_referrals', 'team_bonus_rate'
            ),
            'classes': ('collapse',)
        }),
    )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        from django.core.cache import cache
        cache.delete('referral_settings')
        cache.delete('referral_active_campaign')
        messages.success(request, 'Settings saved and cache cleared.')


@admin.register(Referral)
class ReferralAdmin(ModelAdmin):
    form = ReferralForm
    list_display = (
        'id', 'referrer', 'referred_user', 'level',
        'signup_bonus_given', 'total_commission_earned',
        'is_suspicious', 'created_at',
    )
    list_filter = ('signup_bonus_given', 'is_suspicious', 'level')
    search_fields = ('referrer__username', 'referred_user__username', 'registration_ip')
    readonly_fields = ('total_commission_earned', 'created_at')
    inlines = [ReferralEarningInline, SuspiciousReferralInline]
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    list_per_page = 50
    actions = ['mark_not_suspicious', 'export_csv']

    def mark_not_suspicious(self, request, queryset):
        queryset.update(is_suspicious=False)
        messages.success(request, f'{queryset.count()} referrals marked as not suspicious.')
    mark_not_suspicious.short_description = "Mark selected as NOT suspicious"

    def export_csv(self, request, queryset):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="referrals.csv"'
        writer = csv.writer(response)
        writer.writerow(['ID', 'Referrer', 'Referred User', 'Commission', 'Suspicious', 'Date'])
        for r in queryset:
            writer.writerow([
                r.id, r.referrer.username, r.referred_user.username,
                float(r.total_commission_earned), r.is_suspicious,
                r.created_at.strftime('%Y-%m-%d'),
            ])
        return response
    export_csv.short_description = "Export selected to CSV"


@admin.register(ReferralEarning)
class ReferralEarningAdmin(ModelAdmin):
    list_display = (
        'id', 'referrer', 'referred_user', 'level',
        'amount', 'commission_rate', 'source_type',
        'status', 'campaign_multiplier', 'created_at',
    )
    list_filter = ('level', 'source_type', 'status')
    search_fields = ('referrer__username', 'referred_user__username')
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    list_per_page = 50


@admin.register(ReferralChain)
class ReferralChainAdmin(ModelAdmin):
    list_display = ('id', 'beneficiary', 'earner', 'level', 'created_at')
    list_filter = ('level',)
    search_fields = ('beneficiary__username', 'earner__username')
    readonly_fields = ('created_at',)


@admin.register(ReferralLeaderboard)
class ReferralLeaderboardAdmin(ModelAdmin):
    list_display = ('id', 'user', 'period', 'rank', 'total_referrals', 'total_commission', 'period_start')
    list_filter = ('period',)
    search_fields = ('user__username',)


# ── New Model Admins ───────────────────────────────────────────────────────────

@admin.register(ReferralCode)
class ReferralCodeAdmin(ModelAdmin):
    list_display = (
        'id', 'user', 'code', 'custom_code', 'source_tag',
        'clicks', 'conversions', 'is_primary', 'is_active',
    )
    list_filter = ('is_primary', 'is_active')
    search_fields = ('user__username', 'code', 'custom_code')
    readonly_fields = ('clicks', 'unique_clicks', 'conversions', 'revenue_generated', 'created_at')


@admin.register(ReferralLink)
class ReferralLinkAdmin(ModelAdmin):
    list_display = (
        'id', 'user', 'code', 'custom_alias',
        'total_clicks', 'total_signups', 'is_active',
    )
    search_fields = ('user__username', 'code', 'custom_alias')


@admin.register(ReferralRelationship)
class ReferralRelationshipAdmin(ModelAdmin):
    list_display = (
        'id', 'referrer', 'referred', 'level',
        'total_commission_earned', 'is_active', 'joined_at',
    )
    list_filter = ('level', 'is_active')
    search_fields = ('referrer__username', 'referred__username')
    readonly_fields = ('joined_at',)


@admin.register(ReferralTree)
class ReferralTreeAdmin(ModelAdmin):
    list_display = (
        'root_user', 'depth', 'total_members',
        'level1_count', 'level2_count', 'level3_count',
        'total_earned', 'last_rebuilt_at',
    )
    search_fields = ('root_user__username',)
    readonly_fields = ('last_rebuilt_at', 'updated_at', 'created_at')
    actions = ['rebuild_trees']

    def rebuild_trees(self, request, queryset):
        from api.referral.services.ReferralTreeService import ReferralTreeService
        for tree in queryset:
            ReferralTreeService.rebuild_tree(tree.root_user)
        messages.success(request, f'{queryset.count()} trees rebuilt.')
    rebuild_trees.short_description = "Rebuild selected trees"


@admin.register(ReferralLevel)
class ReferralLevelAdmin(ModelAdmin):
    list_display = ('level_number', 'name', 'commission_rate', 'is_active')
    ordering = ('level_number',)


@admin.register(CommissionRule)
class CommissionRuleAdmin(ModelAdmin):
    list_display = (
        'id', 'level', 'action_type', 'rate_type',
        'rate_value', 'priority', 'is_active',
    )
    list_filter = ('level', 'action_type', 'rate_type', 'is_active')
    ordering = ('-priority', 'level')


@admin.register(CommissionLog)
class CommissionLogAdmin(ModelAdmin):
    list_display = (
        'id', 'user', 'referred_user', 'level',
        'amount', 'action_type', 'status', 'created_at',
    )
    list_filter = ('level', 'action_type', 'status')
    search_fields = ('user__username', 'referred_user__username')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'created_at'
    actions = ['release_held']

    def release_held(self, request, queryset):
        from api.referral.services.CommissionService import CommissionService
        released = 0
        for log in queryset.filter(status='held'):
            result = CommissionService.release_held_commission(
                log.id, admin_user=request.user
            )
            if result['success']:
                released += 1
        messages.success(request, f'{released} commissions released.')
    release_held.short_description = "Release held commissions"


@admin.register(CommissionPayout)
class CommissionPayoutAdmin(ModelAdmin):
    list_display = (
        'id', 'user', 'total_amount', 'period', 'status', 'paid_at',
    )
    list_filter = ('period', 'status')
    search_fields = ('user__username',)
    readonly_fields = ('created_at', 'updated_at', 'paid_at')


@admin.register(CommissionHold)
class CommissionHoldAdmin(ModelAdmin):
    list_display = (
        'id', 'commission', 'hold_days', 'release_at',
        'reason', 'is_released',
    )
    list_filter = ('reason', 'is_released')
    readonly_fields = ('created_at',)


@admin.register(CommissionClawback)
class CommissionClawbackAdmin(ModelAdmin):
    list_display = (
        'id', 'commission', 'clawback_amount', 'reason',
        'status', 'approved_by', 'created_at',
    )
    list_filter = ('reason', 'status')
    readonly_fields = ('created_at', 'clawed_back_at')
    actions = ['approve_clawbacks', 'reject_clawbacks']

    def approve_clawbacks(self, request, queryset):
        from api.referral.services.CommissionClawbackService import CommissionClawbackService
        approved = 0
        for cb in queryset.filter(status='pending'):
            result = CommissionClawbackService.approve_clawback(cb.id, request.user)
            if result['success']:
                approved += 1
        messages.success(request, f'{approved} clawbacks approved.')
    approve_clawbacks.short_description = "Approve selected clawbacks"

    def reject_clawbacks(self, request, queryset):
        from api.referral.services.CommissionClawbackService import CommissionClawbackService
        rejected = 0
        for cb in queryset.filter(status='pending'):
            result = CommissionClawbackService.reject_clawback(cb.id, request.user)
            if result['success']:
                rejected += 1
        messages.success(request, f'{rejected} clawbacks rejected.')
    reject_clawbacks.short_description = "Reject selected clawbacks"


@admin.register(ReferralCampaign)
class ReferralCampaignAdmin(ModelAdmin):
    list_display = (
        'id', 'name', 'bonus_multiplier', 'start_date', 'end_date',
        'current_referrals', 'current_spend', 'is_active', 'is_featured',
    )
    list_filter = ('is_active', 'is_featured')
    search_fields = ('name', 'slug')
    readonly_fields = ('slug', 'current_spend', 'current_referrals', 'created_at', 'updated_at')
    inlines = [ReferralBonusInline]
    actions = ['activate_campaign', 'deactivate_campaign']

    def activate_campaign(self, request, queryset):
        from api.referral.services.ReferralCampaignService import ReferralCampaignService
        for c in queryset:
            ReferralCampaignService.start_campaign(c.id)
        messages.success(request, f'{queryset.count()} campaigns activated.')
    activate_campaign.short_description = "Activate selected campaigns"

    def deactivate_campaign(self, request, queryset):
        from api.referral.services.ReferralCampaignService import ReferralCampaignService
        for c in queryset:
            ReferralCampaignService.end_campaign(c.id)
        messages.success(request, f'{queryset.count()} campaigns deactivated.')
    deactivate_campaign.short_description = "Deactivate selected campaigns"


@admin.register(ReferralBonus)
class ReferralBonusAdmin(ModelAdmin):
    list_display = (
        'id', 'campaign', 'milestone_type', 'milestone_value',
        'bonus_amount', 'reward_type', 'is_active',
    )
    list_filter = ('campaign', 'milestone_type', 'reward_type', 'is_active')


@admin.register(ReferralBonusClaim)
class ReferralBonusClaimAdmin(ModelAdmin):
    list_display = ('id', 'user', 'bonus', 'amount_paid', 'status', 'claimed_at')
    list_filter = ('status',)
    readonly_fields = ('claimed_at',)


@admin.register(ReferralContest)
class ReferralContestAdmin(ModelAdmin):
    list_display = (
        'id', 'title', 'contest_type', 'prize_pool',
        'start_date', 'end_date', 'status', 'is_public',
    )
    list_filter = ('contest_type', 'status', 'is_public')
    search_fields = ('title', 'slug')
    readonly_fields = ('slug', 'created_at', 'updated_at')
    inlines = [ReferralRewardInline]
    actions = ['finalize_contests', 'update_leaderboards']

    def finalize_contests(self, request, queryset):
        from api.referral.services.ReferralContestService import ReferralContestService
        finalized = 0
        for contest in queryset:
            result = ReferralContestService.finalize_contest(contest.id)
            if result.get('success'):
                finalized += 1
        messages.success(request, f'{finalized} contests finalized.')
    finalize_contests.short_description = "Finalize selected contests"

    def update_leaderboards(self, request, queryset):
        from api.referral.services.ReferralContestService import ReferralContestService
        for contest in queryset:
            ReferralContestService.update_leaderboard(contest.id)
        messages.success(request, f'{queryset.count()} leaderboards updated.')
    update_leaderboards.short_description = "Update leaderboards"


@admin.register(ContestEntry)
class ContestEntryAdmin(ModelAdmin):
    list_display = (
        'id', 'contest', 'user', 'current_rank',
        'referral_count', 'commission_earned',
    )
    list_filter = ('contest',)
    search_fields = ('user__username',)


@admin.register(ReferralReward)
class ReferralRewardAdmin(ModelAdmin):
    list_display = (
        'id', 'contest', 'rank', 'reward_type',
        'reward_value', 'winner', 'status',
    )
    list_filter = ('reward_type', 'status')


@admin.register(ReferralFraudRule)
class ReferralFraudRuleAdmin(ModelAdmin):
    list_display = (
        'rule_type', 'action', 'fraud_score_points',
        'threshold', 'is_active', 'priority',
    )
    list_filter = ('action', 'is_active')
    ordering = ('-priority',)


@admin.register(ReferralFraudLog)
class ReferralFraudLogAdmin(ModelAdmin):
    list_display = (
        'id', 'referral', 'rule', 'fraud_score',
        'action_taken', 'detected_at',
    )
    list_filter = ('rule', 'action_taken')
    readonly_fields = ('detected_at',)
    date_hierarchy = 'detected_at'


@admin.register(ReferralBlacklist)
class ReferralBlacklistAdmin(ModelAdmin):
    list_display = (
        'id', 'pattern_type', 'pattern_value', 'severity',
        'hit_count', 'is_active', 'created_at',
    )
    list_filter = ('pattern_type', 'severity', 'is_active')
    search_fields = ('pattern_value', 'reason')
    readonly_fields = ('hit_count', 'last_hit_at', 'created_at')


@admin.register(SuspiciousReferral)
class SuspiciousReferralAdmin(ModelAdmin):
    list_display = (
        'id', 'referral', 'fraud_score', 'status',
        'reviewed_by', 'detected_at',
    )
    list_filter = ('status',)
    search_fields = (
        'referral__referrer__username',
        'referral__referred_user__username',
    )
    readonly_fields = ('detected_at', 'reviewed_at', 'flags', 'evidence')
    ordering = ('-fraud_score', '-detected_at')
    actions = ['clear_selected', 'mark_as_fraud']

    def clear_selected(self, request, queryset):
        cleared = 0
        for sr in queryset.filter(status='pending'):
            sr.clear(admin_user=request.user, notes='Bulk cleared by admin')
            cleared += 1
        messages.success(request, f'{cleared} referrals cleared.')
    clear_selected.short_description = "Clear selected (mark as legitimate)"

    def mark_as_fraud(self, request, queryset):
        marked = 0
        for sr in queryset.filter(status='pending'):
            sr.mark_fraud(admin_user=request.user, notes='Bulk fraud by admin')
            marked += 1
        messages.success(request, f'{marked} referrals marked as fraud.')
    mark_as_fraud.short_description = "Mark selected as confirmed fraud"


@admin.register(ReferralInsight)
class ReferralInsightAdmin(ModelAdmin):
    list_display = (
        'date', 'new_referrals', 'commission_paid',
        'conversion_rate', 'active_referrers', 'flagged_referrals',
    )
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'date'
    ordering = ('-date',)


@admin.register(TopReferrer)
class TopReferrerAdmin(ModelAdmin):
    list_display = (
        'date', 'period', 'rank', 'user',
        'referral_count', 'commission_earned',
    )
    list_filter = ('period',)
    date_hierarchy = 'date'
    ordering = ('rank',)


@admin.register(ReferralLTV)
class ReferralLTVAdmin(ModelAdmin):
    list_display = (
        'user', 'referred_by', 'lifetime_value',
        'engagement_score', 'churn_risk', 'value_category',
    )
    list_filter = ('churn_risk', 'value_category')
    search_fields = ('user__username', 'referred_by__username')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('-lifetime_value',)


@admin.register(ReferralConversionRate)
class ReferralConversionRateAdmin(ModelAdmin):
    list_display = (
        'code', 'date', 'clicks', 'signups',
        'conversion_pct', 'commission_earned',
    )
    date_hierarchy = 'date'
    ordering = ('-date',)


# ══════════════════════════════════════════════════════════════
# FORCE REGISTER (backward compat helper used by apps.py)
# ══════════════════════════════════════════════════════════════

def _force_register_referral():
    """Register referral models in custom admin sites (e.g. admin_panel)."""
    try:
        from api.admin_panel.admin import admin_site as modern_site
        if modern_site is None:
            return
        from .models import (
            ReferralChain, ReferralLeaderboard, ReferralCode, ReferralLink,
            ReferralRelationship, ReferralTree, ReferralLevel,
            CommissionRule, CommissionPayout, CommissionHold, CommissionClawback,
            ReferralBonus, ReferralBonusClaim, ReferralContest, ReferralReward, ContestEntry,
            ReferralFraudRule, ReferralFraudLog, ReferralBlacklist,
            ReferralInsight, TopReferrer, ReferralLTV, ReferralConversionRate,
        )
        pairs = [
            (ReferralSettings, ReferralSettingsAdmin),
            (Referral, ReferralAdmin),
            (ReferralEarning, ReferralEarningAdmin),
            (ReferralCampaign, ReferralCampaignAdmin),
            (SuspiciousReferral, SuspiciousReferralAdmin),
            (CommissionLog, CommissionLogAdmin),
            (ReferralChain, ReferralChainAdmin),
            (ReferralLeaderboard, ReferralLeaderboardAdmin),
            (ReferralCode, ReferralCodeAdmin),
            (ReferralLink, ReferralLinkAdmin),
            (ReferralRelationship, ReferralRelationshipAdmin),
            (ReferralTree, ReferralTreeAdmin),
            (ReferralLevel, ReferralLevelAdmin),
            (CommissionRule, CommissionRuleAdmin),
            (CommissionPayout, CommissionPayoutAdmin),
            (CommissionHold, CommissionHoldAdmin),
            (CommissionClawback, CommissionClawbackAdmin),
            (ReferralBonus, ReferralBonusAdmin),
            (ReferralBonusClaim, ReferralBonusClaimAdmin),
            (ReferralContest, ReferralContestAdmin),
            (ReferralReward, ReferralRewardAdmin),
            (ContestEntry, ContestEntryAdmin),
            (ReferralFraudRule, ReferralFraudRuleAdmin),
            (ReferralFraudLog, ReferralFraudLogAdmin),
            (ReferralBlacklist, ReferralBlacklistAdmin),
            (ReferralInsight, ReferralInsightAdmin),
            (TopReferrer, TopReferrerAdmin),
            (ReferralLTV, ReferralLTVAdmin),
            (ReferralConversionRate, ReferralConversionRateAdmin),
        ]
        registered = 0
        for model, model_admin in pairs:
            try:
                if model not in modern_site._registry:
                    modern_site.register(model, model_admin)
                    registered += 1
            except Exception:
                pass
        if registered:
            print(f"[OK] referral: registered {registered} models in custom admin")
    except Exception as e:
        pass