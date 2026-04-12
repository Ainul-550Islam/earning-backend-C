# api/offer_inventory/filters.py
import django_filters
from .models import (
    Offer, Conversion, WithdrawalRequest,
    FraudAttempt, Click, BlacklistedIP,
)


class OfferFilter(django_filters.FilterSet):
    status    = django_filters.CharFilter(field_name='status')
    category  = django_filters.CharFilter(field_name='category__slug')
    network   = django_filters.UUIDFilter(field_name='network__id')
    is_featured = django_filters.BooleanFilter()
    min_reward  = django_filters.NumberFilter(field_name='reward_amount', lookup_expr='gte')
    max_reward  = django_filters.NumberFilter(field_name='reward_amount', lookup_expr='lte')
    country   = django_filters.CharFilter(method='filter_country')

    class Meta:
        model  = Offer
        fields = ['status', 'category', 'network', 'is_featured']

    def filter_country(self, qs, name, value):
        return qs.filter(
            visibility_rules__rule_type='country',
            visibility_rules__operator='include',
            visibility_rules__values__contains=[value.upper()]
        ) | qs.filter(visibility_rules__isnull=True)


class ConversionFilter(django_filters.FilterSet):
    status      = django_filters.CharFilter(field_name='status__name')
    user        = django_filters.UUIDFilter(field_name='user__id')
    offer       = django_filters.UUIDFilter(field_name='offer__id')
    network     = django_filters.UUIDFilter(field_name='offer__network__id')
    date_from   = django_filters.DateFilter(field_name='created_at__date', lookup_expr='gte')
    date_to     = django_filters.DateFilter(field_name='created_at__date', lookup_expr='lte')
    postback_sent = django_filters.BooleanFilter()

    class Meta:
        model  = Conversion
        fields = ['status', 'user', 'offer', 'postback_sent']


class WithdrawalFilter(django_filters.FilterSet):
    status    = django_filters.CharFilter(field_name='status')
    provider  = django_filters.CharFilter(field_name='payment_method__provider')
    date_from = django_filters.DateFilter(field_name='created_at__date', lookup_expr='gte')
    date_to   = django_filters.DateFilter(field_name='created_at__date', lookup_expr='lte')
    min_amount= django_filters.NumberFilter(field_name='amount', lookup_expr='gte')

    class Meta:
        model  = WithdrawalRequest
        fields = ['status', 'provider']


class FraudAttemptFilter(django_filters.FilterSet):
    is_resolved = django_filters.BooleanFilter()
    user        = django_filters.UUIDFilter(field_name='user__id')
    ip_address  = django_filters.CharFilter()
    date_from   = django_filters.DateFilter(field_name='created_at__date', lookup_expr='gte')

    class Meta:
        model  = FraudAttempt
        fields = ['is_resolved', 'user', 'ip_address']


class ClickFilter(django_filters.FilterSet):
    is_fraud  = django_filters.BooleanFilter()
    converted = django_filters.BooleanFilter()
    country   = django_filters.CharFilter(field_name='country_code')
    device    = django_filters.CharFilter(field_name='device_type')

    class Meta:
        model  = Click
        fields = ['is_fraud', 'converted', 'country_code', 'device_type']
