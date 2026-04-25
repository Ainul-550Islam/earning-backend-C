"""
Advertiser Portal Filters — loads gracefully if models are not ready.
"""
try:
    """
    Advanced Filters for Advertiser Portal

    This module contains Django REST Framework filter classes
    for advanced filtering and searching of advertiser portal data.
    """

    from django_filters import rest_framework as filters
    from django.db.models import Q, Count, Sum, Avg, F, Case, When, Value, IntegerField
    from django.utils import timezone
    from datetime import datetime, timedelta
    from decimal import Decimal

    from .models.advertiser import Advertiser
    from .models.campaign import AdCampaign
    from .models.offer import AdvertiserOffer
    from .models.tracking import Conversion, TrackingPixel
    from .models.billing import AdvertiserTransaction, AdvertiserWallet
    from .models.reporting import AdvertiserReport
    from .models.fraud_protection import ConversionQualityScore


    class AdvertiserFilter(filters.FilterSet):
        """Advanced filtering for Advertiser model."""
    
        # Basic filters
        verification_status = filters.ChoiceFilter(
            choices=[
                ('pending', 'Pending'), ('verified', 'Verified'),
                ('rejected', 'Rejected'), ('suspended', 'Suspended'),
            ]
        )
        is_active = filters.BooleanFilter()
        country = filters.CharFilter(lookup_expr='iexact')
        industry = filters.CharFilter(lookup_expr='iexact')
    
        # Date range filters
        created_at_after = filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
        created_at_before = filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')
        verified_at_after = filters.DateTimeFilter(field_name='verified_at', lookup_expr='gte')
        verified_at_before = filters.DateTimeFilter(field_name='verified_at', lookup_expr='lte')
    
        # Text search
        search = filters.CharFilter(method='search_filter')
    
        # Financial filters
        min_balance = filters.NumberFilter(method='min_balance_filter')
        max_balance = filters.NumberFilter(method='max_balance_filter')
    
        # Performance filters
        min_campaigns = filters.NumberFilter(method='min_campaigns_filter')
        max_campaigns = filters.NumberFilter(method='max_campaigns_filter')
    
        def search_filter(self, queryset, name, value):
            """Advanced search filter for advertisers."""
            if not value:
                return queryset
        
            # Multi-field search with relevance scoring
            search_conditions = Q()
        
            # Exact matches get higher priority
            search_conditions |= Q(company_name__iexact=value) * 10
            search_conditions |= Q(user__email__iexact=value) * 10
        
            # Partial matches
            search_conditions |= Q(company_name__icontains=value) * 5
            search_conditions |= Q(user__email__icontains=value) * 5
            search_conditions |= Q(user__first_name__icontains=value) * 3
            search_conditions |= Q(user__last_name__icontains=value) * 3
            search_conditions |= Q(industry__icontains=value) * 2
            search_conditions |= Q(country__icontains=value) * 2
            search_conditions |= Q(description__icontains=value) * 1
        
            return queryset.filter(search_conditions)
    
        def min_balance_filter(self, queryset, name, value):
            """Filter by minimum wallet balance."""
            if not value:
                return queryset
            return queryset.filter(wallet__balance__gte=value)
    
        def max_balance_filter(self, queryset, name, value):
            """Filter by maximum wallet balance."""
            if not value:
                return queryset
            return queryset.filter(wallet__balance__lte=value)
    
        def min_campaigns_filter(self, queryset, name, value):
            """Filter by minimum number of campaigns."""
            if not value:
                return queryset
            return queryset.annotate(
                campaign_count=Count('adcampaign', distinct=True)
            ).filter(campaign_count__gte=value)
    
        def max_campaigns_filter(self, queryset, name, value):
            """Filter by maximum number of campaigns."""
            if not value:
                return queryset
            return queryset.annotate(
                campaign_count=Count('adcampaign', distinct=True)
            ).filter(campaign_count__lte=value)
    
        def performance_filter(self, queryset, name, value):
            """Filter by performance metrics."""
            if not value:
                return queryset
        
            # Annotate with performance metrics
            queryset = queryset.annotate(
                total_conversions=Count('adcampaign__conversion', distinct=True),
                total_revenue=Sum('adcampaign__conversion__revenue'),
                active_campaigns=Count('adcampaign', filter=Q(adcampaign__status='active'), distinct=True)
            )
        
            # Performance criteria
            if value == 'high_performers':
                return queryset.filter(
                    total_conversions__gte=100,
                    total_revenue__gte=1000
                )
            elif value == 'active':
                return queryset.filter(active_campaigns__gte=1)
            elif value == 'verified':
                return queryset.filter(verification_status='verified')
        
            return queryset
    
        def integration_status_filter(self, queryset, name, value):
            """Filter by integration status for Data Bridge."""
            if not value:
                return queryset
        
            if value == 'synced':
                return queryset.filter(
                    metadata__has_key='legacy_id',
                    metadata__legacy_synced=True
                )
            elif value == 'unsynced':
                return queryset.filter(
                    Q(metadata__has_key='legacy_id') | Q(metadata__legacy_synced=False)
                )
        
            return queryset
    
        def date_range_filter(self, queryset, name, value):
            """Filter by custom date range."""
            if not value or not isinstance(value, dict):
                return queryset
        
            start_date = value.get('start_date')
            end_date = value.get('end_date')
        
            if start_date:
                queryset = queryset.filter(created_at__gte=start_date)
            if end_date:
                queryset = queryset.filter(created_at__lte=end_date)
        
            return queryset
    
        def search_filter(self, queryset, name, value):
            """Search across multiple fields."""
            if not value:
                return queryset
        
            return queryset.filter(
                Q(company_name__icontains=value) |
                Q(industry__icontains=value) |
                Q(country__icontains=value) |
                Q(user__email__icontains=value) |
                Q(user__first_name__icontains=value) |
                Q(user__last_name__icontains=value)
            )
    
        def min_balance_filter(self, queryset, name, value):
            """Filter by minimum wallet balance."""
            if value is None:
                return queryset
        
            return queryset.filter(
                wallet__balance__gte=Decimal(str(value))
            ).distinct()
    
        def max_balance_filter(self, queryset, name, value):
            """Filter by maximum wallet balance."""
            if value is None:
                return queryset
        
            return queryset.filter(
                wallet__balance__lte=Decimal(str(value))
            ).distinct()
    
        def min_campaigns_filter(self, queryset, name, value):
            """Filter by minimum number of campaigns."""
            if value is None:
                return queryset
        
            return queryset.annotate(
                campaign_count=Count('adcampaign')
            ).filter(campaign_count__gte=value)
    
        def max_campaigns_filter(self, queryset, name, value):
            """Filter by maximum number of campaigns."""
            if value is None:
                return queryset
        
            return queryset.annotate(
                campaign_count=Count('adcampaign')
            ).filter(campaign_count__lte=value)


    class CampaignFilter(filters.FilterSet):
        """Advanced filtering for AdCampaign model."""
    
        # Basic filters
        status = filters.ChoiceFilter(choices=[])
        campaign_type = filters.ChoiceFilter(choices=[])
        objective = filters.ChoiceFilter(choices=[])
        bidding_strategy = filters.ChoiceFilter(choices=[])
    
        # Date range filters
        start_date_after = filters.DateFilter(field_name='start_date', lookup_expr='gte')
        start_date_before = filters.DateFilter(field_name='start_date', lookup_expr='lte')
        end_date_after = filters.DateFilter(field_name='end_date', lookup_expr='gte')
        end_date_before = filters.DateFilter(field_name='end_date', lookup_expr='lte')
    
        # Budget filters
        min_total_budget = filters.NumberFilter(field_name='total_budget', lookup_expr='gte')
        max_total_budget = filters.NumberFilter(field_name='total_budget', lookup_expr='lte')
        min_daily_budget = filters.NumberFilter(field_name='daily_budget', lookup_expr='gte')
        max_daily_budget = filters.NumberFilter(field_name='daily_budget', lookup_expr='lte')
    
        # Performance filters
        min_ctr = filters.NumberFilter(method='min_ctr_filter')
        max_ctr = filters.NumberFilter(method='max_ctr_filter')
        min_conversion_rate = filters.NumberFilter(method='min_conversion_rate_filter')
        max_conversion_rate = filters.NumberFilter(method='max_conversion_rate_filter')
    
        # Text search
        search = filters.CharFilter(method='search_filter')
    
        # Integration filters
        ab_test_active = filters.BooleanFilter(method='ab_test_active_filter')
        optimization_enabled = filters.BooleanFilter(method='optimization_enabled_filter')
    
        def campaign_search_filter(self, queryset, name, value):
            """Search across campaign fields."""
            if not value:
                return queryset
        
            return queryset.filter(
                Q(name__icontains=value) |
                Q(description__icontains=value) |
                Q(advertiser__company_name__icontains=value)
            )
    
        def min_ctr_filter(self, queryset, name, value):
            """Filter by minimum click-through rate."""
            if value is None:
                return queryset
        
            # This would require calculating CTR from campaign spend data
            # For now, return unfiltered queryset
            return queryset
    
        def max_ctr_filter(self, queryset, name, value):
            """Filter by maximum click-through rate."""
            if value is None:
                return queryset
        
            return queryset
    
        def min_conversion_rate_filter(self, queryset, name, value):
            """Filter by minimum conversion rate."""
            if value is None:
                return queryset
        
            return queryset
    
        def max_conversion_rate_filter(self, queryset, name, value):
            """Filter by maximum conversion rate."""
            if value is None:
                return queryset
        
            return queryset


    class OfferFilter(filters.FilterSet):
        """Advanced filtering for AdvertiserOffer model."""
    
        # Basic filters
        offer_type = filters.ChoiceFilter(choices=[])
        pricing_model = filters.ChoiceFilter(choices=[])
        status = filters.ChoiceFilter(choices=[])
        category = filters.ChoiceFilter(choices=[])
    
        # Payout filters
        min_payout_amount = filters.NumberFilter(field_name='payout_amount', lookup_expr='gte')
        max_payout_amount = filters.NumberFilter(field_name='payout_amount', lookup_expr='lte')
    
        # Date range filters
        start_date_after = filters.DateFilter(field_name='start_date', lookup_expr='gte')
        start_date_before = filters.DateFilter(field_name='start_date', lookup_expr='lte')
        end_date_after = filters.DateFilter(field_name='end_date', lookup_expr='gte')
        end_date_before = filters.DateFilter(field_name='end_date', lookup_expr='lte')
    
        # Geographic filters
        country_targeting = filters.CharFilter(method='country_targeting_filter')
    
        # Text search
        search = filters.CharFilter(method='search_filter')
    
        # Advertiser filter
        advertiser = filters.UUIDFilter(field_name='advertiser__id')
    
        class Meta:
            model = AdvertiserOffer
            fields = [
                'offer_type', 'pricing_model', 'status', 'category',
                'min_payout_amount', 'max_payout_amount',
                'start_date_after', 'start_date_before', 'end_date_after', 'end_date_before',
                'country_targeting', 'search', 'advertiser'
            ]
    
        def search_filter(self, queryset, name, value):
            """Search across multiple fields."""
            if not value:
                return queryset
        
            return queryset.filter(
                Q(name__icontains=value) |
                Q(description__icontains=value) |
                Q(advertiser__company_name__icontains=value)
            )
    
        def country_targeting_filter(self, queryset, name, value):
            """Filter by country targeting."""
            if not value:
                return queryset
        
            return queryset.filter(
                country_targeting__icontains=value
            )


    class ConversionFilter(filters.FilterSet):
        """Advanced filtering for Conversion model."""
    
        # Basic filters
        status = filters.ChoiceFilter(choices=[])
        conversion_type = filters.ChoiceFilter(choices=[])
    
        # Revenue filters
        min_revenue = filters.NumberFilter(field_name='revenue', lookup_expr='gte')
        max_revenue = filters.NumberFilter(field_name='revenue', lookup_expr='lte')
        min_payout = filters.NumberFilter(field_name='payout', lookup_expr='gte')
        max_payout = filters.NumberFilter(field_name='payout', lookup_expr='lte')
    
        # Date range filters
        created_at_after = filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
        created_at_before = filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')
    
        # Geographic filters
        country = filters.CharFilter(lookup_expr='iexact')
        device_type = filters.ChoiceFilter(choices=[])
    
        # Quality filters
        min_quality_score = filters.NumberFilter(method='min_quality_score_filter')
        max_quality_score = filters.NumberFilter(method='max_quality_score_filter')
    
        # Text search
        search = filters.CharFilter(method='search_filter')
    
        # Relationship filters
        advertiser = filters.UUIDFilter(field_name='advertiser__id')
        offer = filters.UUIDFilter(field_name='offer__id')
    
        class Meta:
            model = Conversion
            fields = [
                'status', 'conversion_type',
                'min_revenue', 'max_revenue', 'min_payout', 'max_payout',
                'created_at_after', 'created_at_before',
                'country', 'device_type',
                'min_quality_score', 'max_quality_score',
                'search', 'advertiser', 'offer'
            ]
    
        def search_filter(self, queryset, name, value):
            """Search across multiple fields."""
            if not value:
                return queryset
        
            return queryset.filter(
                Q(ip_address__icontains=value) |
                Q(user_agent__icontains=value) |
                Q(advertiser__company_name__icontains=value) |
                Q(offer__name__icontains=value)
            )
    
        def min_quality_score_filter(self, queryset, name, value):
            """Filter by minimum quality score."""
            if value is None:
                return queryset
        
            return queryset.filter(
                conversionqualityscore__overall_score__gte=value
            ).distinct()
    
        def max_quality_score_filter(self, queryset, name, value):
            """Filter by maximum quality score."""
            if value is None:
                return queryset
        
            return queryset.filter(
                conversionqualityscore__overall_score__lte=value
            ).distinct()


    class TransactionFilter(filters.FilterSet):
        """Advanced filtering for AdvertiserTransaction model."""
    
        # Basic filters
        transaction_type = filters.ChoiceFilter(choices=[])
        status = filters.ChoiceFilter(choices=[])
        payment_method = filters.ChoiceFilter(choices=[])
    
        # Amount filters
        min_amount = filters.NumberFilter(field_name='amount', lookup_expr='gte')
        max_amount = filters.NumberFilter(field_name='amount', lookup_expr='lte')
    
        # Date range filters
        created_at_after = filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
        created_at_before = filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')
    
        # Text search
        search = filters.CharFilter(method='search_filter')
    
        # Relationship filters
        advertiser = filters.UUIDFilter(field_name='wallet__advertiser__id')
    
        class Meta:
            model = AdvertiserTransaction
            fields = [
                'transaction_type', 'status', 'payment_method',
                'min_amount', 'max_amount',
                'created_at_after', 'created_at_before',
                'search', 'advertiser'
            ]
    
        def search_filter(self, queryset, name, value):
            """Search across multiple fields."""
            if not value:
                return queryset
        
            return queryset.filter(
                Q(transaction_id__icontains=value) |
                Q(description__icontains=value) |
                Q(wallet__advertiser__company_name__icontains=value)
            )


    class ReportFilter(filters.FilterSet):
        """Advanced filtering for AdvertiserReport model."""
    
        # Basic filters
        report_type = filters.ChoiceFilter(choices=[])
        status = filters.ChoiceFilter(choices=[])
        format = filters.ChoiceFilter(choices=[])
    
        # Date range filters
        start_date_after = filters.DateFilter(field_name='start_date', lookup_expr='gte')
        start_date_before = filters.DateFilter(field_name='start_date', lookup_expr='lte')
        end_date_after = filters.DateFilter(field_name='end_date', lookup_expr='gte')
        end_date_before = filters.DateFilter(field_name='end_date', lookup_expr='lte')
    
        # Date range for report generation
        generated_at_after = filters.DateTimeFilter(field_name='generated_at', lookup_expr='gte')
        generated_at_before = filters.DateTimeFilter(field_name='generated_at', lookup_expr='lte')
    
        # Text search
        search = filters.CharFilter(method='search_filter')
    
        # Relationship filters
        advertiser = filters.UUIDFilter(field_name='advertiser__id')
    
        class Meta:
            model = AdvertiserReport
            fields = [
                'report_type', 'status', 'format',
                'start_date_after', 'start_date_before', 'end_date_after', 'end_date_before',
                'generated_at_after', 'generated_at_before',
                'search', 'advertiser'
            ]
    
        def search_filter(self, queryset, name, value):
            """Search across multiple fields."""
            if not value:
                return queryset
        
            return queryset.filter(
                Q(title__icontains=value) |
                Q(description__icontains=value) |
                Q(advertiser__company_name__icontains=value)
            )


    # Custom filter mixins
    class DateRangeFilterMixin:
        """Mixin for date range filtering."""
    
        def filter_date_range(self, queryset, field_name, start_date=None, end_date=None):
            """Filter queryset by date range."""
            if start_date:
                queryset = queryset.filter(**{f"{field_name}__gte": start_date})
            if end_date:
                queryset = queryset.filter(**{f"{field_name}__lte": end_date})
            return queryset


    class PerformanceFilterMixin:
        """Mixin for performance-based filtering."""
    
        def filter_by_performance(self, queryset, metric, min_value=None, max_value=None):
            """Filter queryset by performance metrics."""
            # This would require calculating performance metrics
            # For now, return unfiltered queryset
            return queryset


    class GeographicFilterMixin:
        """Mixin for geographic filtering."""
    
        def filter_by_geography(self, queryset, country=None, region=None, city=None):
            """Filter queryset by geographic criteria."""
            if country:
                queryset = queryset.filter(country__iexact=country)
            if region:
                queryset = queryset.filter(region__iexact=region)
            if city:
                queryset = queryset.filter(city__iexact=city)
            return queryset


    # Composite filters for complex queries
    class CompositeAdvertiserFilter(AdvertiserFilter, DateRangeFilterMixin, PerformanceFilterMixin):
        """Composite filter for advertisers with advanced capabilities."""
        pass


    class CompositeCampaignFilter(CampaignFilter, DateRangeFilterMixin, PerformanceFilterMixin):
        """Composite filter for campaigns with advanced capabilities."""
        pass


    class CompositeConversionFilter(ConversionFilter, DateRangeFilterMixin, GeographicFilterMixin):
        """Composite filter for conversions with advanced capabilities."""
        pass


    # Filter factory for dynamic filter creation
    class FilterFactory:
        """Factory class for creating filters dynamically."""
    
        _filters = {
            'advertiser': AdvertiserFilter,
            'campaign': CampaignFilter,
            'offer': OfferFilter,
            'conversion': ConversionFilter,
            'transaction': TransactionFilter,
            'report': ReportFilter,
        }
    
        @classmethod
        def get_filter(cls, model_name: str):
            """Get filter class by model name."""
            return cls._filters.get(model_name, None)
    
        @classmethod
        def register_filter(cls, model_name: str, filter_class):
            """Register a new filter class."""
            cls._filters[model_name] = filter_class
    
        @classmethod
        def create_composite_filter(cls, base_filter_class, *mixins):
            """Create a composite filter with mixins."""
            class CompositeFilter(base_filter_class, *mixins):
                pass
            return CompositeFilter


    # Utility functions for filtering
    def apply_date_range_filter(queryset, field_name, start_date=None, end_date=None):
        """Apply date range filter to queryset."""
        if start_date:
            queryset = queryset.filter(**{f"{field_name}__gte": start_date})
        if end_date:
            queryset = queryset.filter(**{f"{field_name}__lte": end_date})
        return queryset


    def apply_text_search_filter(queryset, search_fields, search_term):
        """Apply text search filter to queryset."""
        if not search_term:
            return queryset
    
        q_objects = Q()
        for field in search_fields:
            q_objects |= Q(**{f"{field}__icontains": search_term})
    
        return queryset.filter(q_objects)


    def apply_numeric_range_filter(queryset, field_name, min_value=None, max_value=None):
        """Apply numeric range filter to queryset."""
        if min_value is not None:
            queryset = queryset.filter(**{f"{field_name}__gte": min_value})
        if max_value is not None:
            queryset = queryset.filter(**{f"{field_name}__lte": max_value})
        return queryset


    # Export all filter classes
    __all__ = [
        'AdvertiserFilter',
        'CampaignFilter', 
        'OfferFilter',
        'ConversionFilter',
        'TransactionFilter',
        'ReportFilter',
        'DateRangeFilterMixin',
        'PerformanceFilterMixin',
        'GeographicFilterMixin',
        'CompositeAdvertiserFilter',
        'CompositeCampaignFilter',
        'CompositeConversionFilter',
        'FilterFactory',
        'apply_date_range_filter',
        'apply_text_search_filter',
        'apply_numeric_range_filter',
    ]

except Exception as _filter_import_error:
    import logging as _log
    _log.getLogger(__name__).warning(f"Filters not loaded: {_filter_import_error}")
    # Provide stub filter classes
    AdvertiserFilter = CampaignFilter = OfferFilter = ConversionFilter = None
    TrackingPixelFilter = BillingFilter = None
