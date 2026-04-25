"""
api/ad_networks/filters.py
Django filters for ad networks module
SaaS-ready with tenant support
"""

import django_filters
from django_filters import rest_framework as filters
from django.db.models import Q, Count, Sum, Avg
from django.utils import timezone
from datetime import timedelta, datetime
from decimal import Decimal

from api.ad_networks.models import (
    AdNetwork, Offer, UserOfferEngagement, OfferConversion,
    OfferCategory, NetworkAPILog, NetworkHealthCheck
)
from api.ad_networks.choices import (
    NetworkCategory, CountrySupport, NetworkStatus,
    OfferStatus, ConversionStatus, EngagementStatus
)
from api.ad_networks.constants import SUPPORTED_NETWORKS


class AdNetworkFilter(filters.FilterSet):
    """
    Filter for AdNetwork model
    category, status, country_support, min_payout
    """
    
    # Basic filters
    name = filters.CharFilter(
        field_name='name',
        lookup_expr='icontains',
        help_text='Search by network name'
    )
    
    network_type = filters.MultipleChoiceFilter(
        field_name='network_type',
        choices=AdNetwork.NETWORK_TYPES,
        help_text='Filter by network type'
    )
    
    category = filters.ChoiceFilter(
        field_name='category',
        choices=NetworkCategory.CHOICES,
        help_text='Filter by network category'
    )
    
    status = filters.BooleanFilter(
        field_name='is_active',
        help_text='Filter by active status'
    )
    
    country_support = filters.ChoiceFilter(
        field_name='country_support',
        choices=CountrySupport.CHOICES,
        help_text='Filter by country support'
    )
    
    # Financial filters
    min_payout = filters.NumberFilter(
        field_name='min_payout',
        lookup_expr='gte',
        help_text='Minimum payout amount'
    )
    
    max_payout = filters.NumberFilter(
        field_name='max_payout',
        lookup_expr='lte',
        help_text='Maximum payout amount'
    )
    
    commission_rate_min = filters.NumberFilter(
        field_name='commission_rate',
        lookup_expr='gte',
        help_text='Minimum commission rate (%)'
    )
    
    commission_rate_max = filters.NumberFilter(
        field_name='commission_rate',
        lookup_expr='lte',
        help_text='Maximum commission rate (%)'
    )
    
    # Performance filters
    min_rating = filters.NumberFilter(
        field_name='rating',
        lookup_expr='gte',
        help_text='Minimum rating'
    )
    
    max_rating = filters.NumberFilter(
        field_name='rating',
        lookup_expr='lte',
        help_text='Maximum rating'
    )
    
    min_trust_score = filters.NumberFilter(
        field_name='trust_score',
        lookup_expr='gte',
        help_text='Minimum trust score'
    )
    
    max_trust_score = filters.NumberFilter(
        field_name='trust_score',
        lookup_expr='lte',
        help_text='Maximum trust score'
    )
    
    # Feature filters
    supports_postback = filters.BooleanFilter(
        field_name='supports_postback',
        help_text='Supports postback'
    )
    
    supports_webhook = filters.BooleanFilter(
        field_name='supports_webhook',
        help_text='Supports webhook'
    )
    
    supports_offers = filters.BooleanFilter(
        field_name='supports_offers',
        help_text='Supports offers'
    )
    
    supports_surveys = filters.BooleanFilter(
        field_name='supports_surveys',
        help_text='Supports surveys'
    )
    
    supports_video = filters.BooleanFilter(
        field_name='supports_video',
        help_text='Supports video'
    )
    
    supports_gaming = filters.BooleanFilter(
        field_name='supports_gaming',
        help_text='Supports gaming'
    )
    
    supports_app_install = filters.BooleanFilter(
        field_name='supports_app_install',
        help_text='Supports app install'
    )
    
    # Verification filters
    is_verified = filters.BooleanFilter(
        field_name='is_verified',
        help_text='Is verified network'
    )
    
    is_testing = filters.BooleanFilter(
        field_name='is_testing',
        help_text='Is in testing phase'
    )
    
    # Date filters
    created_after = filters.DateTimeFilter(
        field_name='created_at',
        lookup_expr='gte',
        help_text='Created after date'
    )
    
    created_before = filters.DateTimeFilter(
        field_name='created_at',
        lookup_expr='lte',
        help_text='Created before date'
    )
    
    last_sync_after = filters.DateTimeFilter(
        field_name='last_sync',
        lookup_expr='gte',
        help_text='Last sync after date'
    )
    
    last_sync_before = filters.DateTimeFilter(
        field_name='last_sync',
        lookup_expr='lte',
        help_text='Last sync before date'
    )
    
    # Custom method filters
    def filter_high_performing(self, queryset, name, value):
        """Filter high performing networks (rating >= 4.0, trust_score >= 70)"""
        if value:
            return queryset.filter(
                rating__gte=4.0,
                trust_score__gte=70
            )
        return queryset
    
    def filter_has_recent_activity(self, queryset, name, value):
        """Filter networks with recent activity (last sync within 24 hours)"""
        if value:
            recent = timezone.now() - timedelta(hours=24)
            return queryset.filter(
                last_sync__gte=recent
            )
        return queryset
    
    def filter_top_tier(self, queryset, name, value):
        """Filter top tier networks (priority >= 80)"""
        if value:
            return queryset.filter(
                priority__gte=80
            )
        return queryset
    
    # Register custom filters
    high_performing = filters.BooleanFilter(
        method='filter_high_performing',
        help_text='High performing networks only'
    )
    
    has_recent_activity = filters.BooleanFilter(
        method='filter_has_recent_activity',
        help_text='Networks with recent activity only'
    )
    
    top_tier = filters.BooleanFilter(
        method='filter_top_tier',
        help_text='Top tier networks only'
    )
    
    class Meta:
        model = AdNetwork
        fields = [
            'name', 'network_type', 'category', 'is_active',
            'country_support', 'min_payout', 'max_payout',
            'rating', 'trust_score', 'is_verified'
        ]


class OfferFilter(filters.FilterSet):
    """
    Filter for Offer model
    network, category, status, country, payout_type
    """
    
    # Basic filters
    title = filters.CharFilter(
        field_name='title',
        lookup_expr='icontains',
        help_text='Search by offer title'
    )
    
    description = filters.CharFilter(
        field_name='description',
        lookup_expr='icontains',
        help_text='Search by description'
    )
    
    network = filters.ModelMultipleChoiceFilter(
        field_name='ad_network',
        queryset=AdNetwork.objects.filter(is_active=True),
        help_text='Filter by network'
    )
    
    network_type = filters.MultipleChoiceFilter(
        field_name='ad_network__network_type',
        choices=AdNetwork.NETWORK_TYPES,
        help_text='Filter by network type'
    )
    
    category = filters.ModelMultipleChoiceFilter(
        field_name='category',
        queryset=OfferCategory.objects.filter(is_active=True),
        help_text='Filter by category'
    )
    
    status = filters.ChoiceFilter(
        field_name='status',
        choices=OfferStatus.CHOICES,
        help_text='Filter by offer status'
    )
    
    # Financial filters
    min_reward = filters.NumberFilter(
        field_name='reward_amount',
        lookup_expr='gte',
        help_text='Minimum reward amount'
    )
    
    max_reward = filters.NumberFilter(
        field_name='reward_amount',
        lookup_expr='lte',
        help_text='Maximum reward amount'
    )
    
    min_network_payout = filters.NumberFilter(
        field_name='network_payout',
        lookup_expr='gte',
        help_text='Minimum network payout'
    )
    
    max_network_payout = filters.NumberFilter(
        field_name='network_payout',
        lookup_expr='lte',
        help_text='Maximum network payout'
    )
    
    # Difficulty and time filters
    difficulty = filters.MultipleChoiceFilter(
        field_name='difficulty',
        choices=Offer.DIFFICULTY_LEVELS,
        help_text='Filter by difficulty'
    )
    
    min_estimated_time = filters.NumberFilter(
        field_name='estimated_time',
        lookup_expr='gte',
        help_text='Minimum estimated time (minutes)'
    )
    
    max_estimated_time = filters.NumberFilter(
        field_name='estimated_time',
        lookup_expr='lte',
        help_text='Maximum estimated time (minutes)'
    )
    
    # Geographic filters
    countries = filters.CharFilter(
        field_name='countries',
        method='filter_countries',
        help_text='Filter by available countries (comma-separated)'
    )
    
    platforms = filters.MultipleChoiceFilter(
        field_name='platforms',
        choices=[
            ('android', 'Android'),
            ('ios', 'iOS'),
            ('web', 'Web'),
            ('desktop', 'Desktop'),
        ],
        help_text='Filter by platforms'
    )
    
    device_type = filters.ChoiceFilter(
        field_name='device_type',
        choices=Offer.DEVICE_TYPES,
        help_text='Filter by device type'
    )
    
    # Targeting filters
    min_age = filters.NumberFilter(
        field_name='min_age',
        lookup_expr='lte',
        help_text='Maximum minimum age requirement'
    )
    
    max_age = filters.NumberFilter(
        field_name='max_age',
        lookup_expr='gte',
        help_text='Minimum maximum age requirement'
    )
    
    gender_targeting = filters.ChoiceFilter(
        field_name='gender_targeting',
        choices=Offer.GENDER_TARGETING,
        help_text='Filter by gender targeting'
    )
    
    # Feature filters
    is_featured = filters.BooleanFilter(
        field_name='is_featured',
        help_text='Featured offers only'
    )
    
    is_hot = filters.BooleanFilter(
        field_name='is_hot',
        help_text='Hot offers only'
    )
    
    is_new = filters.BooleanFilter(
        field_name='is_new',
        help_text='New offers only'
    )
    
    is_exclusive = filters.BooleanFilter(
        field_name='is_exclusive',
        help_text='Exclusive offers only'
    )
    
    requires_approval = filters.BooleanFilter(
        field_name='requires_approval',
        help_text='Requires approval only'
    )
    
    # Performance filters
    min_conversion_rate = filters.NumberFilter(
        field_name='conversion_rate',
        lookup_expr='gte',
        help_text='Minimum conversion rate (%)'
    )
    
    max_conversion_rate = filters.NumberFilter(
        field_name='conversion_rate',
        lookup_expr='lte',
        help_text='Maximum conversion rate (%)'
    )
    
    min_quality_score = filters.NumberFilter(
        field_name='quality_score',
        lookup_expr='gte',
        help_text='Minimum quality score'
    )
    
    max_quality_score = filters.NumberFilter(
        field_name='quality_score',
        lookup_expr='lte',
        help_text='Maximum quality score'
    )
    
    # Date filters
    expires_after = filters.DateTimeFilter(
        field_name='expires_at',
        lookup_expr='gte',
        help_text='Expires after date'
    )
    
    expires_before = filters.DateTimeFilter(
        field_name='expires_at',
        lookup_expr='lte',
        help_text='Expires before date'
    )
    
    starts_after = filters.DateTimeFilter(
        field_name='starts_at',
        lookup_expr='gte',
        help_text='Starts after date'
    )
    
    starts_before = filters.DateTimeFilter(
        field_name='starts_at',
        lookup_expr='lte',
        help_text='Starts before date'
    )
    
    # Custom method filters
    def filter_countries(self, queryset, name, value):
        """Filter by countries (comma-separated list)"""
        if value:
            countries = [c.strip().upper() for c in value.split(',') if c.strip()]
            return queryset.filter(
                countries__overlap=countries
            )
        return queryset
    
    def filter_available_now(self, queryset, name, value):
        """Filter offers available right now"""
        if value:
            now = timezone.now()
            return queryset.filter(
                Q(expires_at__isnull=True) | Q(expires_at__gt=now),
                Q(starts_at__isnull=True) | Q(starts_at__lte=now),
                status='active'
            )
        return queryset
    
    def filter_high_value(self, queryset, name, value):
        """Filter high value offers (reward >= 5.00)"""
        if value:
            return queryset.filter(
                reward_amount__gte=Decimal('5.00')
            )
        return queryset
    
    def filter_easy_offers(self, queryset, name, value):
        """Filter easy difficulty offers"""
        if value:
            return queryset.filter(
                difficulty__in=['very_easy', 'easy']
            )
        return queryset
    
    def filter_quick_offers(self, queryset, name, value):
        """Filter quick offers (estimated_time <= 5 minutes)"""
        if value:
            return queryset.filter(
                estimated_time__lte=5
            )
        return queryset
    
    # Register custom filters
    available_now = filters.BooleanFilter(
        method='filter_available_now',
        help_text='Available right now only'
    )
    
    high_value = filters.BooleanFilter(
        method='filter_high_value',
        help_text='High value offers only (>= $5)'
    )
    
    easy_offers = filters.BooleanFilter(
        method='filter_easy_offers',
        help_text='Easy difficulty offers only'
    )
    
    quick_offers = filters.BooleanFilter(
        method='filter_quick_offers',
        help_text='Quick offers only (<= 5 min)'
    )
    
    class Meta:
        model = Offer
        fields = [
            'title', 'description', 'ad_network', 'category', 'status',
            'reward_amount', 'difficulty', 'countries', 'platforms',
            'is_featured', 'is_hot', 'is_new'
        ]


class ConversionFilter(filters.FilterSet):
    """
    Filter for OfferConversion model
    status, date_range, user, offer
    """
    
    # Basic filters
    status = filters.ChoiceFilter(
        field_name='conversion_status',
        choices=ConversionStatus.CHOICES,
        help_text='Filter by conversion status'
    )
    
    risk_level = filters.ChoiceFilter(
        field_name='risk_level',
        choices=[
            ('low', 'Low Risk'),
            ('medium', 'Medium Risk'),
            ('high', 'High Risk'),
        ],
        help_text='Filter by risk level'
    )
    
    # User filters
    user = filters.ModelChoiceFilter(
        field_name='engagement__user',
        help_text='Filter by user'
    )
    
    user_id = filters.NumberFilter(
        field_name='engagement__user__id',
        help_text='Filter by user ID'
    )
    
    username = filters.CharFilter(
        field_name='engagement__user__username',
        lookup_expr='icontains',
        help_text='Filter by username'
    )
    
    # Offer filters
    offer = filters.ModelChoiceFilter(
        field_name='engagement__offer',
        help_text='Filter by offer'
    )
    
    offer_id = filters.NumberFilter(
        field_name='engagement__offer__id',
        help_text='Filter by offer ID'
    )
    
    offer_title = filters.CharFilter(
        field_name='engagement__offer__title',
        lookup_expr='icontains',
        help_text='Filter by offer title'
    )
    
    # Network filters
    network = filters.ModelChoiceFilter(
        field_name='engagement__offer__ad_network',
        queryset=AdNetwork.objects.filter(is_active=True),
        help_text='Filter by network'
    )
    
    network_type = filters.MultipleChoiceFilter(
        field_name='engagement__offer__ad_network__network_type',
        choices=AdNetwork.NETWORK_TYPES,
        help_text='Filter by network type'
    )
    
    # Financial filters
    min_payout = filters.NumberFilter(
        field_name='payout',
        lookup_expr='gte',
        help_text='Minimum payout amount'
    )
    
    max_payout = filters.NumberFilter(
        field_name='payout',
        lookup_expr='lte',
        help_text='Maximum payout amount'
    )
    
    min_fraud_score = filters.NumberFilter(
        field_name='fraud_score',
        lookup_expr='gte',
        help_text='Minimum fraud score'
    )
    
    max_fraud_score = filters.NumberFilter(
        field_name='fraud_score',
        lookup_expr='lte',
        help_text='Maximum fraud score'
    )
    
    # Currency filters
    currency = filters.CharFilter(
        field_name='network_currency',
        help_text='Filter by currency'
    )
    
    # Payment filters
    payment_method = filters.CharFilter(
        field_name='payment_method',
        help_text='Filter by payment method'
    )
    
    has_payment_reference = filters.BooleanFilter(
        field_name='payment_reference',
        lookup_expr='isnull',
        exclude=True,
        help_text='Has payment reference'
    )
    
    # Verification filters
    is_verified = filters.BooleanFilter(
        field_name='is_verified',
        help_text='Is verified conversion'
    )
    
    verified_by = filters.ModelChoiceFilter(
        field_name='verified_by',
        help_text='Filter by verifier'
    )
    
    # Chargeback filters
    is_chargeback = filters.BooleanFilter(
        method='filter_is_chargeback',
        help_text='Is chargeback conversion'
    )
    
    chargeback_processed = filters.BooleanFilter(
        field_name='chargeback_processed',
        help_text='Chargeback processed'
    )
    
    # Date range filters
    date_range = filters.ChoiceFilter(
        method='filter_date_range',
        choices=[
            ('today', 'Today'),
            ('yesterday', 'Yesterday'),
            ('last_7_days', 'Last 7 days'),
            ('last_30_days', 'Last 30 days'),
            ('this_month', 'This month'),
            ('last_month', 'Last month'),
            ('this_year', 'This year'),
            ('custom', 'Custom range'),
        ],
        help_text='Filter by date range'
    )
    
    created_after = filters.DateTimeFilter(
        field_name='created_at',
        lookup_expr='gte',
        help_text='Created after date'
    )
    
    created_before = filters.DateTimeFilter(
        field_name='created_at',
        lookup_expr='lte',
        help_text='Created before date'
    )
    
    verified_after = filters.DateTimeFilter(
        field_name='verified_at',
        lookup_expr='gte',
        help_text='Verified after date'
    )
    
    verified_before = filters.DateTimeFilter(
        field_name='verified_at',
        lookup_expr='lte',
        help_text='Verified before date'
    )
    
    payment_date_after = filters.DateTimeFilter(
        field_name='payment_date',
        lookup_expr='gte',
        help_text='Payment date after'
    )
    
    payment_date_before = filters.DateTimeFilter(
        field_name='payment_date',
        lookup_expr='lte',
        help_text='Payment date before'
    )
    
    # Custom method filters
    def filter_date_range(self, queryset, name, value):
        """Filter by predefined date ranges"""
        if not value:
            return queryset
        
        now = timezone.now()
        
        if value == 'today':
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            return queryset.filter(created_at__gte=start)
        
        elif value == 'yesterday':
            yesterday = now - timedelta(days=1)
            start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
            end = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
            return queryset.filter(created_at__range=[start, end])
        
        elif value == 'last_7_days':
            start = now - timedelta(days=7)
            return queryset.filter(created_at__gte=start)
        
        elif value == 'last_30_days':
            start = now - timedelta(days=30)
            return queryset.filter(created_at__gte=start)
        
        elif value == 'this_month':
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            return queryset.filter(created_at__gte=start)
        
        elif value == 'last_month':
            if now.month == 1:
                start = now.replace(year=now.year-1, month=12, day=1, hour=0, minute=0, second=0, microsecond=0)
                end = now.replace(year=now.year-1, month=12, day=31, hour=23, minute=59, second=59, microsecond=999999)
            else:
                start = now.replace(month=now.month-1, day=1, hour=0, minute=0, second=0, microsecond=0)
                # Calculate last day of previous month
                import calendar
                last_day = calendar.monthrange(now.year, now.month-1)[1]
                end = now.replace(month=now.month-1, day=last_day, hour=23, minute=59, second=59, microsecond=999999)
            return queryset.filter(created_at__range=[start, end])
        
        elif value == 'this_year':
            start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            return queryset.filter(created_at__gte=start)
        
        return queryset
    
    def filter_is_chargeback(self, queryset, name, value):
        """Filter chargeback conversions"""
        if value:
            return queryset.filter(
                conversion_status='chargeback'
            )
        return queryset
    
    # Register custom filters
    high_fraud_risk = filters.BooleanFilter(
        method='filter_high_fraud_risk',
        help_text='High fraud risk only (score >= 70)'
    )
    
    pending_verification = filters.BooleanFilter(
        method='filter_pending_verification',
        help_text='Pending verification only'
    )
    
    def filter_high_fraud_risk(self, queryset, name, value):
        """Filter high fraud risk conversions"""
        if value:
            return queryset.filter(
                fraud_score__gte=70
            )
        return queryset
    
    def filter_pending_verification(self, queryset, name, value):
        """Filter pending verification conversions"""
        if value:
            return queryset.filter(
                conversion_status='pending',
                is_verified=False
            )
        return queryset
    
    class Meta:
        model = OfferConversion
        fields = [
            'conversion_status', 'risk_level', 'engagement__user',
            'engagement__offer', 'payout', 'fraud_score',
            'is_verified', 'created_at'
        ]


class EngagementFilter(filters.FilterSet):
    """
    Filter for UserOfferEngagement model
    """
    
    # Basic filters
    status = filters.ChoiceFilter(
        field_name='status',
        choices=EngagementStatus.CHOICES,
        help_text='Filter by engagement status'
    )
    
    # User filters
    user = filters.ModelChoiceFilter(
        field_name='user',
        help_text='Filter by user'
    )
    
    user_id = filters.NumberFilter(
        field_name='user__id',
        help_text='Filter by user ID'
    )
    
    username = filters.CharFilter(
        field_name='user__username',
        lookup_expr='icontains',
        help_text='Filter by username'
    )
    
    # Offer filters
    offer = filters.ModelChoiceFilter(
        field_name='offer',
        help_text='Filter by offer'
    )
    
    offer_id = filters.NumberFilter(
        field_name='offer__id',
        help_text='Filter by offer ID'
    )
    
    offer_title = filters.CharFilter(
        field_name='offer__title',
        lookup_expr='icontains',
        help_text='Filter by offer title'
    )
    
    # Network filters
    network = filters.ModelChoiceFilter(
        field_name='offer__ad_network',
        queryset=AdNetwork.objects.filter(is_active=True),
        help_text='Filter by network'
    )
    
    # Financial filters
    min_reward = filters.NumberFilter(
        field_name='reward_earned',
        lookup_expr='gte',
        help_text='Minimum reward earned'
    )
    
    max_reward = filters.NumberFilter(
        field_name='reward_earned',
        lookup_expr='lte',
        help_text='Maximum reward earned'
    )
    
    has_reward = filters.BooleanFilter(
        field_name='reward_earned',
        lookup_expr='isnull',
        exclude=True,
        help_text='Has reward earned'
    )
    
    # Device and location filters
    ip_address = filters.CharFilter(
        field_name='ip_address',
        lookup_expr='icontains',
        help_text='Filter by IP address'
    )
    
    country = filters.CharFilter(
        field_name='location_data__country',
        lookup_expr='icontains',
        help_text='Filter by country'
    )
    
    device = filters.CharFilter(
        field_name='device_info__device',
        lookup_expr='icontains',
        help_text='Filter by device'
    )
    
    browser = filters.CharFilter(
        field_name='browser',
        lookup_expr='icontains',
        help_text='Filter by browser'
    )
    
    # Date filters
    clicked_after = filters.DateTimeFilter(
        field_name='clicked_at',
        lookup_expr='gte',
        help_text='Clicked after date'
    )
    
    clicked_before = filters.DateTimeFilter(
        field_name='clicked_at',
        lookup_expr='lte',
        help_text='Clicked before date'
    )
    
    completed_after = filters.DateTimeFilter(
        field_name='completed_at',
        lookup_expr='gte',
        help_text='Completed after date'
    )
    
    completed_before = filters.DateTimeFilter(
        field_name='completed_at',
        lookup_expr='lte',
        help_text='Completed before date'
    )
    
    class Meta:
        model = UserOfferEngagement
        fields = [
            'status', 'user', 'offer', 'reward_earned',
            'ip_address', 'clicked_at', 'completed_at'
        ]


class NetworkAPILogFilter(filters.FilterSet):
    """
    Filter for NetworkAPILog model
    """
    
    # Basic filters
    network = filters.ModelChoiceFilter(
        field_name='network',
        queryset=AdNetwork.objects.all(),
        help_text='Filter by network'
    )
    
    endpoint = filters.CharFilter(
        field_name='endpoint',
        lookup_expr='icontains',
        help_text='Filter by endpoint'
    )
    
    method = filters.ChoiceFilter(
        field_name='method',
        choices=[
            ('GET', 'GET'),
            ('POST', 'POST'),
            ('PUT', 'PUT'),
            ('DELETE', 'DELETE'),
        ],
        help_text='Filter by HTTP method'
    )
    
    # Status filters
    status_code = filters.NumberFilter(
        field_name='status_code',
        help_text='Filter by status code'
    )
    
    status_code_min = filters.NumberFilter(
        field_name='status_code',
        lookup_expr='gte',
        help_text='Minimum status code'
    )
    
    status_code_max = filters.NumberFilter(
        field_name='status_code',
        lookup_expr='lte',
        help_text='Maximum status code'
    )
    
    is_success = filters.BooleanFilter(
        field_name='is_success',
        help_text='Successful requests only'
    )
    
    is_error = filters.BooleanFilter(
        field_name='is_success',
        lookup_expr='exact',
        exclude=True,
        help_text='Error requests only'
    )
    
    # Performance filters
    min_latency = filters.NumberFilter(
        field_name='latency_ms',
        lookup_expr='gte',
        help_text='Minimum latency (ms)'
    )
    
    max_latency = filters.NumberFilter(
        field_name='latency_ms',
        lookup_expr='lte',
        help_text='Maximum latency (ms)'
    )
    
    is_timeout = filters.BooleanFilter(
        field_name='timeout',
        help_text='Timeout requests only'
    )
    
    # Error filters
    error_type = filters.CharFilter(
        field_name='error_type',
        lookup_expr='icontains',
        help_text='Filter by error type'
    )
    
    has_error = filters.BooleanFilter(
        field_name='error_message',
        lookup_expr='isnull',
        exclude=True,
        help_text='Has error message'
    )
    
    # Date filters
    request_timestamp_after = filters.DateTimeFilter(
        field_name='request_timestamp',
        lookup_expr='gte',
        help_text='Request timestamp after'
    )
    
    request_timestamp_before = filters.DateTimeFilter(
        field_name='request_timestamp',
        lookup_expr='lte',
        help_text='Request timestamp before'
    )
    
    class Meta:
        model = NetworkAPILog
        fields = [
            'network', 'endpoint', 'method', 'status_code',
            'is_success', 'latency_ms', 'request_timestamp'
        ]
