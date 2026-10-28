# api/djoyalty/filters.py
"""
Djoyalty -- django-filter FilterSet classes।
django-filter installed থাকলে use করো, নাইলে query_params manually filter করো।
"""
import logging

logger = logging.getLogger(__name__)

try:
    import django_filters


    class CustomerFilter(django_filters.FilterSet):
        """Customer queryset filter।"""
        code = django_filters.CharFilter(lookup_expr='icontains')
        email = django_filters.CharFilter(lookup_expr='icontains')
        city = django_filters.CharFilter(lookup_expr='icontains')
        is_active = django_filters.BooleanFilter()
        newsletter = django_filters.BooleanFilter()
        created_after = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
        created_before = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')

        class Meta:
            from ..models.core import Customer
            model = Customer
            fields = ['code', 'email', 'city', 'is_active', 'newsletter']


    class PointsLedgerFilter(django_filters.FilterSet):
        """PointsLedger queryset filter।"""
        txn_type = django_filters.CharFilter()
        source = django_filters.CharFilter()
        created_after = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
        created_before = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')
        min_points = django_filters.NumberFilter(field_name='points', lookup_expr='gte')
        max_points = django_filters.NumberFilter(field_name='points', lookup_expr='lte')

        class Meta:
            from ..models.points import PointsLedger
            model = PointsLedger
            fields = ['txn_type', 'source', 'customer']


    class EarnRuleFilter(django_filters.FilterSet):
        """EarnRule filter।"""
        is_active = django_filters.BooleanFilter()
        trigger = django_filters.CharFilter()
        rule_type = django_filters.CharFilter()

        class Meta:
            from ..models.earn_rules import EarnRule
            model = EarnRule
            fields = ['is_active', 'trigger', 'rule_type']


    class CampaignFilter(django_filters.FilterSet):
        """Campaign filter।"""
        status = django_filters.CharFilter()
        campaign_type = django_filters.CharFilter()
        start_after = django_filters.DateTimeFilter(field_name='start_date', lookup_expr='gte')
        end_before = django_filters.DateTimeFilter(field_name='end_date', lookup_expr='lte')

        class Meta:
            from ..models.campaigns import LoyaltyCampaign
            model = LoyaltyCampaign
            fields = ['status', 'campaign_type']


    class RedemptionFilter(django_filters.FilterSet):
        """RedemptionRequest filter।"""
        status = django_filters.CharFilter()
        redemption_type = django_filters.CharFilter()
        created_after = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
        created_before = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')

        class Meta:
            from ..models.redemption import RedemptionRequest
            model = RedemptionRequest
            fields = ['status', 'redemption_type', 'customer']


except ImportError:
    # django-filter not installed -- use DRF built-in filters
    logger.debug('django-filter not installed -- using DRF filters only')

    CustomerFilter = None
    PointsLedgerFilter = None
    EarnRuleFilter = None
    CampaignFilter = None
    RedemptionFilter = None
