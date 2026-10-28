# =============================================================================
# fraud_detection/filters.py
# =============================================================================
"""
Fraud Detection Filters.

Django REST Framework filters for fraud detection models with
comprehensive filtering capabilities for fraud attempts, user risk profiles,
and IP reputation data.
"""

from __future__ import annotations

import django_filters
from django.db import models
from django.utils import timezone
from datetime import timedelta

from api.fraud_detection.models import (
    FraudAttempt, UserRiskProfile, IPReputation,
    FraudCase, FraudAlert, DeviceFingerprint
)
from api.fraud_detection.choices import (
    FraudAttemptStatus, FraudAttemptType, SeverityLevel,
    CaseStatus, AlertPriority
)


class FraudAttemptFilter(django_filters.FilterSet):
    """
    Advanced filtering for FraudAttempt model.
    
    Provides comprehensive filtering options for fraud attempts including
    severity, rule type, date ranges, and status filtering.
    """
    
    # Basic filters
    id = django_filters.UUIDFilter(field_name='id')
    attempt_id = django_filters.CharFilter(field_name='attempt_id', lookup_expr='icontains')
    user_id = django_filters.NumberFilter(field_name='user__id')
    username = django_filters.CharFilter(field_name='user__username', lookup_expr='icontains')
    
    # Fraud attempt specific filters
    attempt_type = django_filters.ChoiceFilter(field_name='attempt_type', choices=FraudAttemptType.choices)
    status = django_filters.ChoiceFilter(field_name='status', choices=FraudAttemptStatus.choices)
    detected_by = django_filters.CharFilter(field_name='detected_by', lookup_expr='icontains')
    
    # Score and amount filters
    fraud_score = django_filters.NumberFilter(field_name='fraud_score')
    fraud_score_min = django_filters.NumberFilter(field_name='fraud_score', lookup_expr='gte')
    fraud_score_max = django_filters.NumberFilter(field_name='fraud_score', lookup_expr='lte')
    confidence_score = django_filters.NumberFilter(field_name='confidence_score')
    confidence_score_min = django_filters.NumberFilter(field_name='confidence_score', lookup_expr='gte')
    confidence_score_max = django_filters.NumberFilter(field_name='confidence_score', lookup_expr='lte')
    amount_involved = django_filters.NumberFilter(field_name='amount_involved')
    amount_min = django_filters.NumberFilter(field_name='amount_involved', lookup_expr='gte')
    amount_max = django_filters.NumberFilter(field_name='amount_involved', lookup_expr='lte')
    
    # Date range filters
    created_at = django_filters.DateTimeFilter(field_name='created_at')
    created_at_after = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_at_before = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')
    created_at_date = django_filters.DateFilter(field_name='created_at__date')
    created_at_date_after = django_filters.DateFilter(field_name='created_at__date', lookup_expr='gte')
    created_at_date_before = django_filters.DateFilter(field_name='created_at__date', lookup_expr='lte')
    
    # Predefined date range filters
    last_hour = django_filters.BooleanFilter(method='filter_last_hour')
    last_24h = django_filters.BooleanFilter(method='filter_last_24h')
    last_7d = django_filters.BooleanFilter(method='filter_last_7d')
    last_30d = django_filters.BooleanFilter(method='filter_last_30d')
    
    # Evidence-based filters
    has_ip_address = django_filters.BooleanFilter(method='filter_has_ip_address')
    ip_address = django_filters.CharFilter(method='filter_by_ip_address')
    has_device_hash = django_filters.BooleanFilter(method='filter_has_device_hash')
    device_hash = django_filters.CharFilter(method='filter_by_device_hash')
    
    # Geographic filters
    country = django_filters.CharFilter(method='filter_by_country')
    region = django_filters.CharFilter(method='filter_by_region')
    city = django_filters.CharFilter(method='filter_by_city')
    
    # Custom range filters
    custom_date_range = django_filters.CharFilter(method='filter_custom_date_range')
    score_range = django_filters.CharFilter(method='filter_score_range')
    amount_range = django_filters.CharFilter(method='filter_amount_range')
    
    class Meta:
        model = FraudAttempt
        fields = [
            'id', 'attempt_id', 'user_id', 'username', 'attempt_type', 'status',
            'fraud_score', 'confidence_score', 'amount_involved', 'detected_by',
            'created_at'
        ]
    
    def filter_last_hour(self, queryset, name, value):
        """Filter attempts from the last hour."""
        if value:
            cutoff = timezone.now() - timedelta(hours=1)
            return queryset.filter(created_at__gte=cutoff)
        return queryset
    
    def filter_last_24h(self, queryset, name, value):
        """Filter attempts from the last 24 hours."""
        if value:
            cutoff = timezone.now() - timedelta(hours=24)
            return queryset.filter(created_at__gte=cutoff)
        return queryset
    
    def filter_last_7d(self, queryset, name, value):
        """Filter attempts from the last 7 days."""
        if value:
            cutoff = timezone.now() - timedelta(days=7)
            return queryset.filter(created_at__gte=cutoff)
        return queryset
    
    def filter_last_30d(self, queryset, name, value):
        """Filter attempts from the last 30 days."""
        if value:
            cutoff = timezone.now() - timedelta(days=30)
            return queryset.filter(created_at__gte=cutoff)
        return queryset
    
    def filter_has_ip_address(self, queryset, name, value):
        """Filter attempts that have IP address evidence."""
        if value is True:
            return queryset.filter(evidence_data__icontains='ip_address')
        elif value is False:
            return queryset.exclude(evidence_data__icontains='ip_address')
        return queryset
    
    def filter_by_ip_address(self, queryset, name, value):
        """Filter attempts by specific IP address."""
        if value:
            return queryset.filter(evidence_data__icontains=f'"ip_address":"{value}"')
        return queryset
    
    def filter_has_device_hash(self, queryset, name, value):
        """Filter attempts that have device fingerprint evidence."""
        if value is True:
            return queryset.filter(evidence_data__icontains='device_hash')
        elif value is False:
            return queryset.exclude(evidence_data__icontains='device_hash')
        return queryset
    
    def filter_by_device_hash(self, queryset, name, value):
        """Filter attempts by specific device hash."""
        if value:
            return queryset.filter(evidence_data__icontains=f'"device_hash":"{value}"')
        return queryset
    
    def filter_by_country(self, queryset, name, value):
        """Filter attempts by country from evidence data."""
        if value:
            return queryset.filter(evidence_data__icontains=f'"country":"{value}"')
        return queryset
    
    def filter_by_region(self, queryset, name, value):
        """Filter attempts by region from evidence data."""
        if value:
            return queryset.filter(evidence_data__icontains=f'"region":"{value}"')
        return queryset
    
    def filter_by_city(self, queryset, name, value):
        """Filter attempts by city from evidence data."""
        if value:
            return queryset.filter(evidence_data__icontains=f'"city":"{value}"')
        return queryset
    
    def filter_custom_date_range(self, queryset, name, value):
        """Filter by custom date range (format: YYYY-MM-DD,YYYY-MM-DD)."""
        if value and ',' in value:
            try:
                start_date, end_date = value.split(',')
                start_date = timezone.datetime.strptime(start_date.strip(), '%Y-%m-%d').date()
                end_date = timezone.datetime.strptime(end_date.strip(), '%Y-%m-%d').date()
                
                # Convert to datetime
                start_datetime = timezone.make_aware(timezone.datetime.combine(start_date, timezone.datetime.min.time()))
                end_datetime = timezone.make_aware(timezone.datetime.combine(end_date, timezone.datetime.max.time()))
                
                return queryset.filter(created_at__range=[start_datetime, end_datetime])
            except ValueError:
                pass  # Invalid format, return unfiltered queryset
        return queryset
    
    def filter_score_range(self, queryset, name, value):
        """Filter by score range (format: min,max)."""
        if value and ',' in value:
            try:
                min_score, max_score = value.split(',')
                min_score = float(min_score.strip())
                max_score = float(max_score.strip())
                return queryset.filter(fraud_score__range=[min_score, max_score])
            except ValueError:
                pass  # Invalid format, return unfiltered queryset
        return queryset
    
    def filter_amount_range(self, queryset, name, value):
        """Filter by amount range (format: min,max)."""
        if value and ',' in value:
            try:
                min_amount, max_amount = value.split(',')
                min_amount = float(min_amount.strip())
                max_amount = float(max_amount.strip())
                return queryset.filter(amount_involved__range=[min_amount, max_amount])
            except ValueError:
                pass  # Invalid format, return unfiltered queryset
        return queryset


class UserRiskProfileFilter(django_filters.FilterSet):
    """
    Advanced filtering for UserRiskProfile model.
    
    Provides filtering options for user risk profiles including risk levels,
    minimum scores, and geographic filtering.
    """
    
    # Basic filters
    id = django_filters.UUIDFilter(field_name='id')
    user_id = django_filters.NumberFilter(field_name='user__id')
    username = django_filters.CharFilter(field_name='user__username', lookup_expr='icontains')
    email = django_filters.CharFilter(field_name='user__email', lookup_expr='icontains')
    
    # Risk profile filters
    overall_risk_score = django_filters.NumberFilter(field_name='overall_risk_score')
    risk_score_min = django_filters.NumberFilter(field_name='overall_risk_score', lookup_expr='gte')
    risk_score_max = django_filters.NumberFilter(field_name='overall_risk_score', lookup_expr='lte')
    monitoring_level = django_filters.ChoiceFilter(field_name='monitoring_level')
    
    # Status filters
    is_flagged = django_filters.BooleanFilter(field_name='is_flagged')
    is_restricted = django_filters.BooleanFilter(field_name='is_restricted')
    is_active = django_filters.BooleanFilter(field_name='user__is_active')
    
    # Activity filters
    total_fraud_attempts = django_filters.NumberFilter(field_name='total_fraud_attempts')
    confirmed_fraud_attempts = django_filters.NumberFilter(field_name='confirmed_fraud_attempts')
    false_positives = django_filters.NumberFilter(field_name='false_positives')
    total_attempts_min = django_filters.NumberFilter(field_name='total_fraud_attempts', lookup_expr='gte')
    confirmed_attempts_min = django_filters.NumberFilter(field_name='confirmed_fraud_attempts', lookup_expr='gte')
    
    # Date filters
    created_at = django_filters.DateTimeFilter(field_name='created_at')
    created_at_after = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_at_before = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')
    last_risk_assessment = django_filters.DateTimeFilter(field_name='last_risk_assessment')
    last_risk_assessment_after = django_filters.DateTimeFilter(field_name='last_risk_assessment', lookup_expr='gte')
    last_risk_assessment_before = django_filters.DateTimeFilter(field_name='last_risk_assessment', lookup_expr='lte')
    
    # User activity filters
    last_login = django_filters.DateTimeFilter(field_name='user__last_login')
    last_login_after = django_filters.DateTimeFilter(field_name='user__last_login', lookup_expr='gte')
    last_login_before = django_filters.DateTimeFilter(field_name='user__last_login', lookup_expr='lte')
    date_joined = django_filters.DateTimeFilter(field_name='user__date_joined')
    date_joined_after = django_filters.DateTimeFilter(field_name='user__date_joined', lookup_expr='gte')
    date_joined_before = django_filters.DateTimeFilter(field_name='user__date_joined', lookup_expr='lte')
    
    # Geographic filters (based on recent activity)
    country = django_filters.CharFilter(method='filter_by_country')
    region = django_filters.CharFilter(method='filter_by_region')
    city = django_filters.CharFilter(method='filter_by_city')
    
    # Risk level filters
    risk_level = django_filters.ChoiceFilter(method='filter_by_risk_level')
    risk_level_min = django_filters.ChoiceFilter(method='filter_by_risk_level_min')
    
    # Custom filters
    has_recent_activity = django_filters.BooleanFilter(method='filter_has_recent_activity')
    high_risk_only = django_filters.BooleanFilter(method='filter_high_risk_only')
    staff_users = django_filters.BooleanFilter(method='filter_staff_users')
    custom_score_range = django_filters.CharFilter(method='filter_custom_score_range')
    
    class Meta:
        model = UserRiskProfile
        fields = [
            'id', 'user_id', 'username', 'email', 'overall_risk_score',
            'monitoring_level', 'is_flagged', 'is_restricted',
            'total_fraud_attempts', 'confirmed_fraud_attempts',
            'created_at', 'last_risk_assessment'
        ]
    
    def filter_by_country(self, queryset, name, value):
        """Filter users with recent activity from specific country."""
        if value:
            # Get users with recent fraud attempts from this country
            from .models import FraudAttempt
            cutoff = timezone.now() - timedelta(days=30)
            user_ids = FraudAttempt.objects.filter(
                created_at__gte=cutoff,
                evidence_data__icontains=f'"country":"{value}"'
            ).values_list('user_id', flat=True).distinct()
            
            return queryset.filter(user_id__in=user_ids)
        return queryset
    
    def filter_by_region(self, queryset, name, value):
        """Filter users with recent activity from specific region."""
        if value:
            from .models import FraudAttempt
            cutoff = timezone.now() - timedelta(days=30)
            user_ids = FraudAttempt.objects.filter(
                created_at__gte=cutoff,
                evidence_data__icontains=f'"region":"{value}"'
            ).values_list('user_id', flat=True).distinct()
            
            return queryset.filter(user_id__in=user_ids)
        return queryset
    
    def filter_by_city(self, queryset, name, value):
        """Filter users with recent activity from specific city."""
        if value:
            from .models import FraudAttempt
            cutoff = timezone.now() - timedelta(days=30)
            user_ids = FraudAttempt.objects.filter(
                created_at__gte=cutoff,
                evidence_data__icontains=f'"city":"{value}"'
            ).values_list('user_id', flat=True).distinct()
            
            return queryset.filter(user_id__in=user_ids)
        return queryset
    
    def filter_by_risk_level(self, queryset, name, value):
        """Filter by predefined risk levels."""
        risk_thresholds = {
            'low': (0, 39),
            'medium': (40, 59),
            'high': (60, 79),
            'critical': (80, 100)
        }
        
        if value in risk_thresholds:
            min_score, max_score = risk_thresholds[value]
            return queryset.filter(overall_risk_score__range=[min_score, max_score])
        return queryset
    
    def filter_by_risk_level_min(self, queryset, name, value):
        """Filter by minimum risk level."""
        risk_thresholds = {
            'low': 40,
            'medium': 60,
            'high': 80,
            'critical': 100
        }
        
        if value in risk_thresholds:
            min_score = risk_thresholds[value]
            return queryset.filter(overall_risk_score__gte=min_score)
        return queryset
    
    def filter_has_recent_activity(self, queryset, name, value):
        """Filter users with recent fraud attempts."""
        if value is True:
            cutoff = timezone.now() - timedelta(days=30)
            user_ids = FraudAttempt.objects.filter(
                created_at__gte=cutoff
            ).values_list('user_id', flat=True).distinct()
            
            return queryset.filter(user_id__in=user_ids)
        elif value is False:
            cutoff = timezone.now() - timedelta(days=30)
            user_ids = FraudAttempt.objects.filter(
                created_at__gte=cutoff
            ).values_list('user_id', flat=True).distinct()
            
            return queryset.exclude(user_id__in=user_ids)
        return queryset
    
    def filter_high_risk_only(self, queryset, name, value):
        """Filter only high-risk users (60+ score)."""
        if value is True:
            return queryset.filter(overall_risk_score__gte=60)
        return queryset
    
    def filter_staff_users(self, queryset, name, value):
        """Filter by staff user status."""
        if value is True:
            return queryset.filter(user__is_staff=True)
        elif value is False:
            return queryset.filter(user__is_staff=False)
        return queryset
    
    def filter_custom_score_range(self, queryset, name, value):
        """Filter by custom score range (format: min,max)."""
        if value and ',' in value:
            try:
                min_score, max_score = value.split(',')
                min_score = float(min_score.strip())
                max_score = float(max_score.strip())
                return queryset.filter(overall_risk_score__range=[min_score, max_score])
            except ValueError:
                pass  # Invalid format, return unfiltered queryset
        return queryset


class IPReputationFilter(django_filters.FilterSet):
    """
    Advanced filtering for IPReputation model.
    
    Provides filtering options for IP reputation including VPN/proxy detection
    and risk score filtering.
    """
    
    # Basic filters
    id = django_filters.UUIDFilter(field_name='id')
    ip_address = django_filters.CharFilter(field_name='ip_address', lookup_expr='icontains')
    
    # Reputation score filters
    fraud_score = django_filters.NumberFilter(field_name='fraud_score')
    fraud_score_min = django_filters.NumberFilter(field_name='fraud_score', lookup_expr='gte')
    fraud_score_max = django_filters.NumberFilter(field_name='fraud_score', lookup_expr='lte')
    spam_score = django_filters.NumberFilter(field_name='spam_score')
    spam_score_min = django_filters.NumberFilter(field_name='spam_score', lookup_expr='gte')
    spam_score_max = django_filters.NumberFilter(field_name='spam_score', lookup_expr='lte')
    malware_score = django_filters.NumberFilter(field_name='malware_score')
    malware_score_min = django_filters.NumberFilter(field_name='malware_score', lookup_expr='gte')
    malware_score_max = django_filters.NumberFilter(field_name='malware_score', lookup_expr='lte')
    
    # Status filters
    is_blacklisted = django_filters.BooleanFilter(field_name='is_blacklisted')
    is_vpn = django_filters.BooleanFilter(field_name='is_vpn')
    is_proxy = django_filters.BooleanFilter(field_name='is_proxy')
    is_tor = django_filters.BooleanFilter(field_name='is_tor')
    is_anonymous = django_filters.BooleanFilter(method='filter_is_anonymous')
    
    # Geographic filters
    country = django_filters.CharFilter(field_name='country', lookup_expr='icontains')
    region = django_filters.CharFilter(field_name='region', lookup_expr='icontains')
    city = django_filters.CharFilter(field_name='city', lookup_expr='icontains')
    
    # Activity filters
    total_requests = django_filters.NumberFilter(field_name='total_requests')
    total_requests_min = django_filters.NumberFilter(field_name='total_requests', lookup_expr='gte')
    fraud_attempts = django_filters.NumberFilter(field_name='fraud_attempts')
    fraud_attempts_min = django_filters.NumberFilter(field_name='fraud_attempts', lookup_expr='gte')
    unique_users = django_filters.NumberFilter(field_name='unique_users')
    unique_users_min = django_filters.NumberFilter(field_name='unique_users', lookup_expr='gte')
    
    # Date filters
    created_at = django_filters.DateTimeFilter(field_name='created_at')
    created_at_after = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_at_before = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')
    last_seen = django_filters.DateTimeFilter(field_name='last_seen')
    last_seen_after = django_filters.DateTimeFilter(field_name='last_seen', lookup_expr='gte')
    last_seen_before = django_filters.DateTimeFilter(field_name='last_seen', lookup_expr='lte')
    
    # Blacklist filters
    blacklisted_at = django_filters.DateTimeFilter(field_name='blacklisted_at')
    blacklisted_after = django_filters.DateTimeFilter(field_name='blacklisted_at', lookup_expr='gte')
    blacklisted_before = django_filters.DateTimeFilter(field_name='blacklisted_at', lookup_expr='lte')
    blacklist_reason = django_filters.CharFilter(field_name='blacklist_reason', lookup_expr='icontains')
    
    # Custom filters
    has_recent_activity = django_filters.BooleanFilter(method='filter_has_recent_activity')
    high_risk_only = django_filters.BooleanFilter(method='filter_high_risk_only')
    suspicious_only = django_filters.BooleanFilter(method='filter_suspicious_only')
    custom_score_range = django_filters.CharFilter(method='filter_custom_score_range')
    
    class Meta:
        model = IPReputation
        fields = [
            'id', 'ip_address', 'fraud_score', 'spam_score', 'malware_score',
            'is_blacklisted', 'is_vpn', 'is_proxy', 'is_tor',
            'country', 'region', 'city', 'total_requests', 'fraud_attempts',
            'unique_users', 'created_at', 'last_seen', 'blacklisted_at'
        ]
    
    def filter_is_anonymous(self, queryset, name, value):
        """Filter for anonymous IPs (VPN, proxy, or Tor)."""
        if value is True:
            return queryset.filter(
                models.Q(is_vpn=True) | models.Q(is_proxy=True) | models.Q(is_tor=True)
            )
        elif value is False:
            return queryset.filter(
                is_vpn=False, is_proxy=False, is_tor=False
            )
        return queryset
    
    def filter_has_recent_activity(self, queryset, name, value):
        """Filter IPs with recent activity."""
        if value is True:
            cutoff = timezone.now() - timedelta(days=7)
            return queryset.filter(last_seen__gte=cutoff)
        elif value is False:
            cutoff = timezone.now() - timedelta(days=7)
            return queryset.filter(last_seen__lt=cutoff)
        return queryset
    
    def filter_high_risk_only(self, queryset, name, value):
        """Filter only high-risk IPs (70+ fraud score)."""
        if value is True:
            return queryset.filter(fraud_score__gte=70)
        return queryset
    
    def filter_suspicious_only(self, queryset, name, value):
        """Filter suspicious IPs (blacklisted, VPN, proxy, or Tor)."""
        if value is True:
            return queryset.filter(
                models.Q(is_blacklisted=True) |
                models.Q(is_vpn=True) |
                models.Q(is_proxy=True) |
                models.Q(is_tor=True) |
                models.Q(fraud_score__gte=60)
            )
        return queryset
    
    def filter_custom_score_range(self, queryset, name, value):
        """Filter by custom score range (format: min,max)."""
        if value and ',' in value:
            try:
                min_score, max_score = value.split(',')
                min_score = float(min_score.strip())
                max_score = float(max_score.strip())
                return queryset.filter(fraud_score__range=[min_score, max_score])
            except ValueError:
                pass  # Invalid format, return unfiltered queryset
        return queryset


# Additional filter classes for other models
class FraudCaseFilter(django_filters.FilterSet):
    """Filter for FraudCase model."""
    
    id = django_filters.UUIDFilter(field_name='id')
    case_number = django_filters.CharFilter(field_name='case_number', lookup_expr='icontains')
    user_id = django_filters.NumberFilter(field_name='user__id')
    username = django_filters.CharFilter(field_name='user__username', lookup_expr='icontains')
    title = django_filters.CharFilter(field_name='title', lookup_expr='icontains')
    status = django_filters.ChoiceFilter(field_name='status', choices=CaseStatus.choices)
    priority = django_filters.ChoiceFilter(field_name='priority', choices=SeverityLevel.choices)
    risk_score = django_filters.NumberFilter(field_name='risk_score')
    risk_score_min = django_filters.NumberFilter(field_name='risk_score', lookup_expr='gte')
    risk_score_max = django_filters.NumberFilter(field_name='risk_score', lookup_expr='lte')
    assigned_to_id = django_filters.NumberFilter(field_name='assigned_to__id')
    assigned_to_username = django_filters.CharFilter(field_name='assigned_to__username', lookup_expr='icontains')
    opened_at = django_filters.DateTimeFilter(field_name='opened_at')
    opened_at_after = django_filters.DateTimeFilter(field_name='opened_at', lookup_expr='gte')
    opened_at_before = django_filters.DateTimeFilter(field_name='opened_at', lookup_expr='lte')
    resolved_at = django_filters.DateTimeFilter(field_name='resolved_at')
    resolved_at_after = django_filters.DateTimeFilter(field_name='resolved_at', lookup_expr='gte')
    resolved_at_before = django_filters.DateTimeFilter(field_name='resolved_at', lookup_expr='lte')
    
    class Meta:
        model = FraudCase
        fields = [
            'id', 'case_number', 'user_id', 'username', 'title', 'status',
            'priority', 'risk_score', 'assigned_to_id', 'opened_at', 'resolved_at'
        ]


class FraudAlertFilter(django_filters.FilterSet):
    """Filter for FraudAlert model."""
    
    id = django_filters.UUIDFilter(field_name='id')
    user_id = django_filters.NumberFilter(field_name='user__id')
    username = django_filters.CharFilter(field_name='user__username', lookup_expr='icontains')
    alert_type = django_filters.ChoiceFilter(field_name='alert_type')
    priority = django_filters.ChoiceFilter(field_name='priority', choices=AlertPriority.choices)
    title = django_filters.CharFilter(field_name='title', lookup_expr='icontains')
    description = django_filters.CharFilter(field_name='description', lookup_expr='icontains')
    is_resolved = django_filters.BooleanFilter(field_name='is_resolved')
    created_at = django_filters.DateTimeFilter(field_name='created_at')
    created_at_after = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_at_before = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')
    
    class Meta:
        model = FraudAlert
        fields = [
            'id', 'user_id', 'username', 'alert_type', 'priority',
            'title', 'description', 'is_resolved', 'created_at'
        ]


class DeviceFingerprintFilter(django_filters.FilterSet):
    """Filter for DeviceFingerprint model."""
    
    id = django_filters.UUIDFilter(field_name='id')
    device_hash = django_filters.CharFilter(field_name='device_hash', lookup_expr='icontains')
    user_id = django_filters.NumberFilter(field_name='user__id')
    username = django_filters.CharFilter(field_name='user__username', lookup_expr='icontains')
    device_type = django_filters.ChoiceFilter(field_name='device_type')
    trust_score = django_filters.NumberFilter(field_name='trust_score')
    trust_score_min = django_filters.NumberFilter(field_name='trust_score', lookup_expr='gte')
    trust_score_max = django_filters.NumberFilter(field_name='trust_score', lookup_expr='lte')
    is_vpn = django_filters.BooleanFilter(field_name='is_vpn')
    is_proxy = django_filters.BooleanFilter(field_name='is_proxy')
    is_tor = django_filters.BooleanFilter(field_name='is_tor')
    user_agent = django_filters.CharFilter(field_name='user_agent', lookup_expr='icontains')
    platform = django_filters.CharFilter(field_name='platform', lookup_expr='icontains')
    browser = django_filters.CharFilter(field_name='browser', lookup_expr='icontains')
    created_at = django_filters.DateTimeFilter(field_name='created_at')
    created_at_after = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_at_before = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')
    last_seen = django_filters.DateTimeFilter(field_name='last_seen')
    last_seen_after = django_filters.DateTimeFilter(field_name='last_seen', lookup_expr='gte')
    last_seen_before = django_filters.DateTimeFilter(field_name='last_seen', lookup_expr='lte')
    
    class Meta:
        model = DeviceFingerprint
        fields = [
            'id', 'device_hash', 'user_id', 'username', 'device_type',
            'trust_score', 'is_vpn', 'is_proxy', 'is_tor',
            'user_agent', 'platform', 'browser', 'created_at', 'last_seen'
        ]
