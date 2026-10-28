# api/referral/filters.py
# Django-filter based filters for referral API viewsets
# Install: pip install django-filter
# ============================================================

from django.utils import timezone
from datetime import timedelta

try:
    import django_filters
    from django_filters import rest_framework as filters

    class ReferralFilter(filters.FilterSet):
        """Filter for Referral model."""
        referrer = filters.NumberFilter(field_name='referrer__id')
        referrer_username = filters.CharFilter(
            field_name='referrer__username', lookup_expr='icontains'
        )
        referred_username = filters.CharFilter(
            field_name='referred_user__username', lookup_expr='icontains'
        )
        level = filters.NumberFilter()
        is_suspicious = filters.BooleanFilter()
        signup_bonus_given = filters.BooleanFilter()
        date_from = filters.DateFilter(field_name='created_at', lookup_expr='date__gte')
        date_to = filters.DateFilter(field_name='created_at', lookup_expr='date__lte')

        class Meta:
            from api.referral.models import Referral
            model = Referral
            fields = [
                'referrer', 'referrer_username', 'referred_username',
                'level', 'is_suspicious', 'signup_bonus_given',
                'date_from', 'date_to',
            ]


    class ReferralEarningFilter(filters.FilterSet):
        """Filter for ReferralEarning model."""
        referrer = filters.NumberFilter(field_name='referrer__id')
        level = filters.NumberFilter()
        source_type = filters.CharFilter(lookup_expr='exact')
        status = filters.CharFilter(lookup_expr='exact')
        min_amount = filters.NumberFilter(field_name='amount', lookup_expr='gte')
        max_amount = filters.NumberFilter(field_name='amount', lookup_expr='lte')
        date_from = filters.DateFilter(field_name='created_at', lookup_expr='date__gte')
        date_to = filters.DateFilter(field_name='created_at', lookup_expr='date__lte')

        class Meta:
            from api.referral.models import ReferralEarning
            model = ReferralEarning
            fields = [
                'referrer', 'level', 'source_type', 'status',
                'min_amount', 'max_amount', 'date_from', 'date_to',
            ]


    class CommissionLogFilter(filters.FilterSet):
        """Filter for CommissionLog model."""
        user = filters.NumberFilter(field_name='user__id')
        level = filters.NumberFilter()
        action_type = filters.CharFilter(lookup_expr='exact')
        status = filters.CharFilter(lookup_expr='exact')
        min_amount = filters.NumberFilter(field_name='amount', lookup_expr='gte')
        date_from = filters.DateFilter(field_name='created_at', lookup_expr='date__gte')
        date_to = filters.DateFilter(field_name='created_at', lookup_expr='date__lte')

        class Meta:
            from api.referral.models import CommissionLog
            model = CommissionLog
            fields = [
                'user', 'level', 'action_type', 'status',
                'min_amount', 'date_from', 'date_to',
            ]


    class SuspiciousReferralFilter(filters.FilterSet):
        """Filter for SuspiciousReferral."""
        status = filters.CharFilter(lookup_expr='exact')
        min_fraud_score = filters.NumberFilter(
            field_name='fraud_score', lookup_expr='gte'
        )
        referrer_username = filters.CharFilter(
            field_name='referral__referrer__username', lookup_expr='icontains'
        )
        date_from = filters.DateFilter(
            field_name='detected_at', lookup_expr='date__gte'
        )

        class Meta:
            from api.referral.models import SuspiciousReferral
            model = SuspiciousReferral
            fields = ['status', 'min_fraud_score', 'referrer_username', 'date_from']


    class ReferralCampaignFilter(filters.FilterSet):
        """Filter for ReferralCampaign."""
        is_active = filters.BooleanFilter()
        is_featured = filters.BooleanFilter()
        name = filters.CharFilter(lookup_expr='icontains')
        active_now = filters.BooleanFilter(method='filter_active_now')

        def filter_active_now(self, queryset, name, value):
            now = timezone.now()
            if value:
                return queryset.filter(
                    is_active=True,
                    start_date__lte=now,
                    end_date__gte=now,
                )
            return queryset

        class Meta:
            from api.referral.models import ReferralCampaign
            model = ReferralCampaign
            fields = ['is_active', 'is_featured', 'name']


    class ReferralLTVFilter(filters.FilterSet):
        """Filter for ReferralLTV."""
        churn_risk = filters.CharFilter(lookup_expr='exact')
        value_category = filters.CharFilter(lookup_expr='exact')
        min_ltv = filters.NumberFilter(field_name='lifetime_value', lookup_expr='gte')
        referred_by = filters.NumberFilter(field_name='referred_by__id')

        class Meta:
            from api.referral.models import ReferralLTV
            model = ReferralLTV
            fields = ['churn_risk', 'value_category', 'min_ltv', 'referred_by']


    class TopReferrerFilter(filters.FilterSet):
        """Filter for TopReferrer snapshots."""
        period = filters.CharFilter(lookup_expr='exact')
        date = filters.DateFilter(lookup_expr='exact')
        min_rank = filters.NumberFilter(field_name='rank', lookup_expr='lte')

        class Meta:
            from api.referral.models import TopReferrer
            model = TopReferrer
            fields = ['period', 'date', 'min_rank']


    FILTERS_AVAILABLE = True

except ImportError:
    # django-filter not installed — provide dummy classes
    FILTERS_AVAILABLE = False

    class ReferralFilter: pass
    class ReferralEarningFilter: pass
    class CommissionLogFilter: pass
    class SuspiciousReferralFilter: pass
    class ReferralCampaignFilter: pass
    class ReferralLTVFilter: pass
    class TopReferrerFilter: pass