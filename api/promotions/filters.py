# =============================================================================
# api/promotions/filters.py
# Django-Filter Classes — সব model এর জন্য flexible filtering
# =============================================================================

import django_filters
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from .models import (
    Campaign, TaskSubmission, Dispute, PromotionTransaction,
    FraudReport, Blacklist, CampaignAnalytics, ReferralCommissionLog,
    RewardPolicy, UserReputation,
)
from .choices import (
    CampaignStatus, SubmissionStatus, DisputeStatus,
    TransactionType, FraudType, FraudAction, BlacklistType, BlacklistSeverity,
    CommissionStatus,
)


# ─── Campaign ────────────────────────────────────────────────────────────────

class CampaignFilter(django_filters.FilterSet):
    title           = django_filters.CharFilter(lookup_expr='icontains', label=_('Title contains'))
    status          = django_filters.MultipleChoiceFilter(choices=CampaignStatus.choices)
    category        = django_filters.NumberFilter(field_name='category__id')
    platform        = django_filters.NumberFilter(field_name='platform__id')
    advertiser      = django_filters.NumberFilter(field_name='advertiser__id')

    # Budget range
    budget_min      = django_filters.NumberFilter(field_name='total_budget_usd', lookup_expr='gte')
    budget_max      = django_filters.NumberFilter(field_name='total_budget_usd', lookup_expr='lte')

    # Date range
    created_after   = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_before  = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')

    # Slot availability
    has_slots       = django_filters.BooleanFilter(method='filter_has_slots', label=_('Has available slots'))

    # Country targeting (JSON field)
    country         = django_filters.CharFilter(method='filter_by_country', label=_('Target country'))

    class Meta:
        model  = Campaign
        fields = ['status', 'category', 'platform', 'advertiser']

    def filter_has_slots(self, queryset, name, value):
        if value:
            return queryset.filter(filled_slots__lt=Q('total_slots'))
        return queryset.exclude(filled_slots__lt=Q('total_slots'))

    def filter_by_country(self, queryset, name, value):
        """JSON array field এ country code আছে কিনা filter।"""
        return queryset.filter(
            targeting__countries__contains=[value.upper()]
        )


# ─── Task Submission ──────────────────────────────────────────────────────────

class TaskSubmissionFilter(django_filters.FilterSet):
    campaign        = django_filters.NumberFilter(field_name='campaign__id')
    worker          = django_filters.NumberFilter(field_name='worker__id')
    status          = django_filters.MultipleChoiceFilter(choices=SubmissionStatus.choices)
    ip_address      = django_filters.CharFilter(lookup_expr='exact')
    reviewer        = django_filters.NumberFilter(field_name='reviewer__id')

    submitted_after  = django_filters.DateTimeFilter(field_name='submitted_at', lookup_expr='gte')
    submitted_before = django_filters.DateTimeFilter(field_name='submitted_at', lookup_expr='lte')
    reviewed_after   = django_filters.DateTimeFilter(field_name='reviewed_at', lookup_expr='gte')
    reviewed_before  = django_filters.DateTimeFilter(field_name='reviewed_at', lookup_expr='lte')

    reward_min      = django_filters.NumberFilter(field_name='reward_usd', lookup_expr='gte')
    reward_max      = django_filters.NumberFilter(field_name='reward_usd', lookup_expr='lte')

    # সন্দেহজনক: একই IP তে অনেক submission
    flagged_device  = django_filters.BooleanFilter(
        field_name='device_fingerprint__is_flagged',
        label=_('Device is flagged'),
    )

    class Meta:
        model  = TaskSubmission
        fields = ['campaign', 'worker', 'status', 'ip_address']


# ─── Dispute ─────────────────────────────────────────────────────────────────

class DisputeFilter(django_filters.FilterSet):
    status          = django_filters.MultipleChoiceFilter(choices=DisputeStatus.choices)
    worker          = django_filters.NumberFilter(field_name='worker__id')
    campaign        = django_filters.NumberFilter(field_name='submission__campaign__id')
    created_after   = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_before  = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')
    is_resolved     = django_filters.BooleanFilter(method='filter_resolved')

    class Meta:
        model  = Dispute
        fields = ['status', 'worker']

    def filter_resolved(self, queryset, name, value):
        if value:
            return queryset.filter(
                status__in=[DisputeStatus.RESOLVED_APPROVED, DisputeStatus.RESOLVED_REJECTED]
            )
        return queryset.filter(status__in=[DisputeStatus.OPEN, DisputeStatus.UNDER_REVIEW])


# ─── Transaction ─────────────────────────────────────────────────────────────

class PromotionTransactionFilter(django_filters.FilterSet):
    type            = django_filters.MultipleChoiceFilter(choices=TransactionType.choices)
    user            = django_filters.NumberFilter(field_name='user__id')
    campaign        = django_filters.NumberFilter(field_name='campaign__id')
    currency_code   = django_filters.CharFilter(lookup_expr='iexact')

    amount_min      = django_filters.NumberFilter(field_name='amount_usd', lookup_expr='gte')
    amount_max      = django_filters.NumberFilter(field_name='amount_usd', lookup_expr='lte')

    created_after   = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_before  = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')

    is_reversed     = django_filters.BooleanFilter()

    class Meta:
        model  = PromotionTransaction
        fields = ['type', 'user', 'campaign', 'currency_code', 'is_reversed']


# ─── Fraud Report ─────────────────────────────────────────────────────────────

class FraudReportFilter(django_filters.FilterSet):
    fraud_type      = django_filters.MultipleChoiceFilter(choices=FraudType.choices)
    action_taken    = django_filters.MultipleChoiceFilter(choices=FraudAction.choices)
    user            = django_filters.NumberFilter(field_name='user__id')
    is_reviewed     = django_filters.BooleanFilter(
        method='filter_reviewed', label=_('Reviewed by admin')
    )
    confidence_min  = django_filters.NumberFilter(field_name='confidence_score', lookup_expr='gte')
    created_after   = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')

    class Meta:
        model  = FraudReport
        fields = ['fraud_type', 'action_taken', 'user']

    def filter_reviewed(self, queryset, name, value):
        if value:
            return queryset.filter(reviewed_by_admin__isnull=False)
        return queryset.filter(reviewed_by_admin__isnull=True)


# ─── Blacklist ────────────────────────────────────────────────────────────────

class BlacklistFilter(django_filters.FilterSet):
    type        = django_filters.MultipleChoiceFilter(choices=BlacklistType.choices)
    severity    = django_filters.MultipleChoiceFilter(choices=BlacklistSeverity.choices)
    is_active   = django_filters.BooleanFilter()
    value       = django_filters.CharFilter(lookup_expr='icontains')
    added_by    = django_filters.NumberFilter(field_name='added_by__id')
    is_expired  = django_filters.BooleanFilter(method='filter_expired')

    class Meta:
        model  = Blacklist
        fields = ['type', 'severity', 'is_active']

    def filter_expired(self, queryset, name, value):
        from django.utils import timezone
        now = timezone.now()
        if value:
            return queryset.filter(expires_at__lt=now)
        return queryset.filter(Q(expires_at__isnull=True) | Q(expires_at__gte=now))


# ─── Campaign Analytics ───────────────────────────────────────────────────────

class CampaignAnalyticsFilter(django_filters.FilterSet):
    campaign    = django_filters.NumberFilter(field_name='campaign__id')
    date_from   = django_filters.DateFilter(field_name='date', lookup_expr='gte')
    date_to     = django_filters.DateFilter(field_name='date', lookup_expr='lte')

    class Meta:
        model  = CampaignAnalytics
        fields = ['campaign']


# ─── Reward Policy ────────────────────────────────────────────────────────────

class RewardPolicyFilter(django_filters.FilterSet):
    country_code    = django_filters.CharFilter(lookup_expr='iexact')
    category        = django_filters.NumberFilter(field_name='category__id')
    is_active       = django_filters.BooleanFilter()
    rate_min        = django_filters.NumberFilter(field_name='rate_usd', lookup_expr='gte')
    rate_max        = django_filters.NumberFilter(field_name='rate_usd', lookup_expr='lte')

    class Meta:
        model  = RewardPolicy
        fields = ['country_code', 'category', 'is_active']


# ─── Referral Commission ──────────────────────────────────────────────────────

class ReferralCommissionFilter(django_filters.FilterSet):
    referrer    = django_filters.NumberFilter(field_name='referrer__id')
    referred    = django_filters.NumberFilter(field_name='referred__id')
    level       = django_filters.NumberFilter()
    status      = django_filters.MultipleChoiceFilter(choices=CommissionStatus.choices)
    created_after = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')

    class Meta:
        model  = ReferralCommissionLog
        fields = ['referrer', 'referred', 'level', 'status']


# ─── User Reputation ─────────────────────────────────────────────────────────

class UserReputationFilter(django_filters.FilterSet):
    trust_score_min = django_filters.NumberFilter(field_name='trust_score', lookup_expr='gte')
    trust_score_max = django_filters.NumberFilter(field_name='trust_score', lookup_expr='lte')
    level           = django_filters.NumberFilter()
    level_min       = django_filters.NumberFilter(field_name='level', lookup_expr='gte')
    is_verified     = django_filters.BooleanFilter(field_name='is_verified_worker')
    success_rate_min = django_filters.NumberFilter(field_name='success_rate', lookup_expr='gte')

    class Meta:
        model  = UserReputation
        fields = ['level', 'is_verified_worker']
