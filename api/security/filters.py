"""
Enhanced Security Filters Module
Comprehensive filtering for security models
Author: System Security Team
Version: 2.0.0
"""

import django_filters
from django_filters import FilterSet, CharFilter, NumberFilter, DateTimeFilter, BooleanFilter, ChoiceFilter, DateFilter, DateRangeFilter
from django.db.models import Q
from django.utils import timezone
from datetime import datetime, timedelta
from rest_framework.exceptions import ValidationError

from .models import (
    SecurityLog, SecurityIncident, IPBlacklist, ThreatIntelligence,
    RiskScore, DeviceInfo, TrustedDevice, PasswordHistory, SecurityPolicy,
    SecurityInsight, UserBan, GeolocationLog, CountryBlockRule
)


class SecurityLogFilter(FilterSet):
    """
    Advanced filter for SecurityLog model
    Filters by event_type, risk_level, date_range, user
    """
    
    # Basic filters
    event_type = CharFilter(method='filter_event_type', lookup_expr='icontains')
    risk_level = CharFilter(method='filter_risk_level')
    user = CharFilter(method='filter_user')
    ip_address = CharFilter(lookup_expr='icontains')
    country = CharFilter(lookup_expr='iexact')
    city = CharFilter(lookup_expr='icontains')
    user_agent = CharFilter(lookup_expr='icontains')
    
    # Date range filters
    created_at = DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_at_lte = DateTimeFilter(field_name='created_at', lookup_expr='lte')
    date_range = DateRangeFilter(field_name='created_at')
    
    # Severity filters
    severity = ChoiceFilter(choices=[
        ('debug', 'Debug'),
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('error', 'Error'),
        ('critical', 'Critical'),
        ('security', 'Security')
    ])
    
    # Boolean filters
    is_suspicious = BooleanFilter(method='filter_is_suspicious')
    is_high_risk = BooleanFilter(method='filter_is_high_risk')
    
    # Numeric filters
    min_risk_score = NumberFilter(method='filter_min_risk_score')
    max_risk_score = NumberFilter(method='filter_max_risk_score')
    
    class Meta:
        model = SecurityLog
        fields = [
            'event_type', 'severity', 'ip_address', 'country', 'city',
            'created_at', 'created_at_lte', 'date_range', 'is_suspicious',
            'is_high_risk'
        ]
    
    def filter_event_type(self, queryset, name, value):
        """Filter by event type with partial matching"""
        if value:
            return queryset.filter(event_type__icontains=value)
        return queryset
    
    def filter_risk_level(self, queryset, name, value):
        """Filter by risk level (custom logic)"""
        if value == 'high':
            return queryset.filter(severity__in=['error', 'critical', 'security'])
        elif value == 'medium':
            return queryset.filter(severity__in=['warning', 'error'])
        elif value == 'low':
            return queryset.filter(severity__in=['debug', 'info'])
        return queryset
    
    def filter_user(self, queryset, name, value):
        """Filter by user (username or ID)"""
        if value:
            # Try to filter by username first
            user_filter = Q(user__username__icontains=value)
            # Try to filter by user ID if value is numeric
            if value.isdigit():
                user_filter |= Q(user_id=int(value))
            return queryset.filter(user_filter)
        return queryset
    
    def filter_is_suspicious(self, queryset, name, value):
        """Filter for suspicious activity"""
        if value:
            # Define suspicious patterns
            suspicious_patterns = [
                'login_failure', 'vpn_detected', 'proxy_detected',
                'suspicious_activity', 'security_violation'
            ]
            return queryset.filter(event_type__in=suspicious_patterns)
        return queryset
    
    def filter_is_high_risk(self, queryset, name, value):
        """Filter for high risk events"""
        if value:
            return queryset.filter(
                severity__in=['critical', 'security']
            )
        return queryset
    
    def filter_min_risk_score(self, queryset, name, value):
        """Filter by minimum risk score (custom logic)"""
        if value is not None:
            # This would require a risk_score field or custom logic
            # For now, filter by severity as proxy for risk
            if value >= 80:
                return queryset.filter(severity='critical')
            elif value >= 60:
                return queryset.filter(severity__in=['critical', 'security'])
            elif value >= 40:
                return queryset.filter(severity__in=['error', 'critical', 'security'])
        return queryset
    
    def filter_max_risk_score(self, queryset, name, value):
        """Filter by maximum risk score (custom logic)"""
        if value is not None:
            # This would require a risk_score field or custom logic
            # For now, filter by severity as proxy for risk
            if value < 40:
                return queryset.filter(severity__in=['debug', 'info'])
            elif value < 60:
                return queryset.filter(severity__in=['debug', 'info', 'warning'])
            elif value < 80:
                return queryset.filter(severity__in=['debug', 'info', 'warning', 'error'])
        return queryset


class AlertRuleFilter(FilterSet):
    """
    Advanced filter for AlertRule model
    Filters by is_active, threat_category
    """
    
    # Basic filters
    name = CharFilter(lookup_expr='icontains')
    description = CharFilter(lookup_expr='icontains')
    threat_category = CharFilter(lookup_expr='iexact')
    
    # Boolean filters
    is_active = BooleanFilter()
    is_system = BooleanFilter()
    
    # Numeric filters
    priority = NumberFilter()
    min_priority = NumberFilter(field_name='priority', lookup_expr='gte')
    max_priority = NumberFilter(field_name='priority', lookup_expr='lte')
    
    # Date filters
    created_at = DateTimeFilter(field_name='created_at', lookup_expr='gte')
    updated_at = DateTimeFilter(field_name='updated_at', lookup_expr='lte')
    
    class Meta:
        model = SecurityIncident  # Assuming AlertRule is related to SecurityIncident
        fields = [
            'name', 'description', 'threat_category', 'is_active', 'is_system',
            'priority', 'min_priority', 'max_priority', 'created_at', 'updated_at'
        ]
    
    def filter_threat_category(self, queryset, name, value):
        """Filter by threat category"""
        if value:
            # Filter by incident_type as threat category proxy
            return queryset.filter(incident_type__iexact=value)
        return queryset


class GeolocationFilter(FilterSet):
    """
    Advanced filter for GeolocationLog model
    Filters by country, is_blocked
    """
    
    # Basic filters
    country = CharFilter(lookup_expr='iexact')
    country_code = CharFilter(lookup_expr='iexact')
    city = CharFilter(lookup_expr='icontains')
    region = CharFilter(lookup_expr='icontains')
    
    # IP address filters
    ip_address = CharFilter(lookup_expr='icontains')
    ip_range = CharFilter(method='filter_ip_range')
    
    # Boolean filters
    is_blocked = BooleanFilter(method='filter_is_blocked')
    is_suspicious = BooleanFilter(method='filter_is_suspicious')
    
    # Coordinate filters
    latitude_min = NumberFilter(field_name='latitude', lookup_expr='gte')
    latitude_max = NumberFilter(field_name='latitude', lookup_expr='lte')
    longitude_min = NumberFilter(field_name='longitude', lookup_expr='gte')
    longitude_max = NumberFilter(field_name='longitude', lookup_expr='lte')
    
    # Date filters
    created_at = DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_at_lte = DateTimeFilter(field_name='created_at', lookup_expr='lte')
    
    class Meta:
        model = GeolocationLog
        fields = [
            'country', 'country_code', 'city', 'region', 'ip_address',
            'is_blocked', 'is_suspicious', 'latitude_min', 'latitude_max',
            'longitude_min', 'longitude_max', 'created_at', 'created_at_lte'
        ]
    
    def filter_ip_range(self, queryset, name, value):
        """Filter by IP range (CIDR notation)"""
        if value:
            try:
                import ipaddress
                network = ipaddress.ip_network(value, strict=False)
                
                # Filter IPs within the range
                filtered_ips = []
                for log in queryset:
                    try:
                        ip = ipaddress.ip_address(log.ip_address)
                        if ip in network:
                            filtered_ips.append(log.id)
                    except (ValueError, AttributeError):
                        continue
                
                return queryset.filter(id__in=filtered_ips)
            except ValueError:
                raise ValidationError(f"Invalid IP range format: {value}")
        return queryset
    
    def filter_is_blocked(self, queryset, name, value):
        """Filter for blocked IPs"""
        if value:
            # Check if IP is in blacklist
            blocked_ips = IPBlacklist.objects.filter(
                is_active=True
            ).values_list('ip_address', flat=True)
            
            return queryset.filter(ip_address__in=blocked_ips)
        return queryset
    
    def filter_is_suspicious(self, queryset, name, value):
        """Filter for suspicious IPs"""
        if value:
            # Check for suspicious patterns
            suspicious_countries = ['CN', 'RU', 'KP', 'IR']  # Example suspicious countries
            return queryset.filter(country__in=suspicious_countries)
        return queryset


class SecurityIncidentFilter(FilterSet):
    """
    Advanced filter for SecurityIncident model
    """
    
    # Basic filters
    title = CharFilter(lookup_expr='icontains')
    description = CharFilter(lookup_expr='icontains')
    incident_type = CharFilter(lookup_expr='iexact')
    
    # Status and severity
    status = ChoiceFilter(choices=[
        ('open', 'Open'),
        ('investigating', 'Investigating'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed')
    ])
    severity = ChoiceFilter(choices=[
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical')
    ])
    
    # User filters
    user = CharFilter(method='filter_user')
    assigned_to = CharFilter(method='filter_assigned_to')
    
    # Date filters
    created_at = DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_at_lte = DateTimeFilter(field_name='created_at', lookup_expr='lte')
    resolved_at = DateTimeFilter(field_name='resolved_at', lookup_expr='gte')
    resolved_at_lte = DateTimeFilter(field_name='resolved_at', lookup_expr='lte')
    
    class Meta:
        model = SecurityIncident
        fields = [
            'title', 'description', 'incident_type', 'status', 'severity',
            'user', 'assigned_to', 'created_at', 'created_at_lte',
            'resolved_at', 'resolved_at_lte'
        ]
    
    def filter_user(self, queryset, name, value):
        """Filter by user (username or ID)"""
        if value:
            user_filter = Q(user__username__icontains=value)
            if value.isdigit():
                user_filter |= Q(user_id=int(value))
            return queryset.filter(user_filter)
        return queryset
    
    def filter_assigned_to(self, queryset, name, value):
        """Filter by assigned user (username or ID)"""
        if value:
            assigned_filter = Q(assigned_to__username__icontains=value)
            if value.isdigit():
                assigned_filter |= Q(assigned_to_id=int(value))
            return queryset.filter(assigned_filter)
        return queryset


class ThreatIntelligenceFilter(FilterSet):
    """
    Advanced filter for ThreatIntelligence model
    """
    
    # Basic filters
    threat_type = CharFilter(lookup_expr='iexact')
    indicator_type = CharFilter(lookup_expr='iexact')
    source = CharFilter(lookup_expr='icontains')
    description = CharFilter(lookup_expr='icontains')
    
    # Boolean filters
    is_active = BooleanFilter()
    is_false_positive = BooleanFilter()
    
    # Numeric filters
    confidence = NumberFilter()
    min_confidence = NumberFilter(field_name='confidence', lookup_expr='gte')
    max_confidence = NumberFilter(field_name='confidence', lookup_expr='lte')
    
    # Date filters
    created_at = DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_at_lte = DateTimeFilter(field_name='created_at', lookup_expr='lte')
    expires_at = DateTimeFilter(field_name='expires_at', lookup_expr='gte')
    expires_at_lte = DateTimeFilter(field_name='expires_at', lookup_expr='lte')
    
    # Indicator filters
    indicators = CharFilter(method='filter_indicators')
    
    class Meta:
        model = ThreatIntelligence
        fields = [
            'threat_type', 'indicator_type', 'source', 'description',
            'is_active', 'is_false_positive', 'confidence', 'min_confidence',
            'max_confidence', 'created_at', 'created_at_lte', 'expires_at',
            'expires_at_lte', 'indicators'
        ]
    
    def filter_indicators(self, queryset, name, value):
        """Filter by indicators (search in indicators array)"""
        if value:
            return queryset.filter(indicators__contains=[value])
        return queryset


class IPBlacklistFilter(FilterSet):
    """
    Advanced filter for IPBlacklist model
    """
    
    # Basic filters
    ip_address = CharFilter(lookup_expr='icontains')
    blacklist_type = CharFilter(lookup_expr='iexact')
    reason = CharFilter(lookup_expr='icontains')
    source = CharFilter(lookup_expr='icontains')
    
    # Boolean filters
    is_active = BooleanFilter()
    
    # Numeric filters
    confidence = NumberFilter()
    min_confidence = NumberFilter(field_name='confidence', lookup_expr='gte')
    max_confidence = NumberFilter(field_name='confidence', lookup_expr='lte')
    
    # Date filters
    created_at = DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_at_lte = DateTimeFilter(field_name='created_at', lookup_expr='lte')
    expires_at = DateTimeFilter(field_name='expires_at', lookup_expr='gte')
    expires_at_lte = DateTimeFilter(field_name='expires_at', lookup_expr='lte')
    
    class Meta:
        model = IPBlacklist
        fields = [
            'ip_address', 'blacklist_type', 'reason', 'source', 'is_active',
            'confidence', 'min_confidence', 'max_confidence', 'created_at',
            'created_at_lte', 'expires_at', 'expires_at_lte'
        ]


class DeviceInfoFilter(FilterSet):
    """
    Advanced filter for DeviceInfo model
    """
    
    # Basic filters
    device_name = CharFilter(lookup_expr='icontains')
    device_type = CharFilter(lookup_expr='iexact')
    platform = CharFilter(lookup_expr='iexact')
    browser = CharFilter(lookup_expr='iexact')
    ip_address = CharFilter(lookup_expr='icontains')
    
    # Boolean filters
    is_trusted = BooleanFilter()
    is_mobile = BooleanFilter(method='filter_is_mobile')
    
    # Numeric filters
    trust_score = NumberFilter()
    min_trust_score = NumberFilter(field_name='trust_score', lookup_expr='gte')
    max_trust_score = NumberFilter(field_name='trust_score', lookup_expr='lte')
    
    # Date filters
    created_at = DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_at_lte = DateTimeFilter(field_name='created_at', lookup_expr='lte')
    last_seen_at = DateTimeFilter(field_name='last_seen_at', lookup_expr='gte')
    last_seen_at_lte = DateTimeFilter(field_name='last_seen_at', lookup_expr='lte')
    
    # User filters
    user = CharFilter(method='filter_user')
    
    class Meta:
        model = DeviceInfo
        fields = [
            'device_name', 'device_type', 'platform', 'browser', 'ip_address',
            'is_trusted', 'is_mobile', 'trust_score', 'min_trust_score',
            'max_trust_score', 'created_at', 'created_at_lte', 'last_seen_at',
            'last_seen_at_lte', 'user'
        ]
    
    def filter_is_mobile(self, queryset, name, value):
        """Filter for mobile devices"""
        if value:
            mobile_platforms = ['android', 'ios', 'mobile', 'tablet']
            return queryset.filter(platform__in=mobile_platforms)
        return queryset
    
    def filter_user(self, queryset, name, value):
        """Filter by user (username or ID)"""
        if value:
            user_filter = Q(user__username__icontains=value)
            if value.isdigit():
                user_filter |= Q(user_id=int(value))
            return queryset.filter(user_filter)
        return queryset


class RiskScoreFilter(FilterSet):
    """
    Advanced filter for RiskScore model
    """
    
    # Numeric filters
    current_score = NumberFilter()
    min_current_score = NumberFilter(field_name='current_score', lookup_expr='gte')
    max_current_score = NumberFilter(field_name='current_score', lookup_expr='lte')
    
    # Date filters
    created_at = DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_at_lte = DateTimeFilter(field_name='created_at', lookup_expr='lte')
    expires_at = DateTimeFilter(field_name='expires_at', lookup_expr='gte')
    expires_at_lte = DateTimeFilter(field_name='expires_at', lookup_expr='lte')
    
    # User filters
    user = CharFilter(method='filter_user')
    
    class Meta:
        model = RiskScore
        fields = [
            'current_score', 'min_current_score', 'max_current_score',
            'created_at', 'created_at_lte', 'expires_at', 'expires_at_lte', 'user'
        ]
    
    def filter_user(self, queryset, name, value):
        """Filter by user (username or ID)"""
        if value:
            user_filter = Q(user__username__icontains=value)
            if value.isdigit():
                user_filter |= Q(user_id=int(value))
            return queryset.filter(user_filter)
        return queryset


class UserBanFilter(FilterSet):
    """
    Advanced filter for UserBan model
    """
    
    # Basic filters
    reason = CharFilter(lookup_expr='icontains')
    ban_type = CharFilter(lookup_expr='iexact')
    
    # Boolean filters
    is_active = BooleanFilter()
    
    # Date filters
    created_at = DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_at_lte = DateTimeFilter(field_name='created_at', lookup_expr='lte')
    expires_at = DateTimeFilter(field_name='expires_at', lookup_expr='gte')
    expires_at_lte = DateTimeFilter(field_name='expires_at', lookup_expr='lte')
    
    # User filters
    user = CharFilter(method='filter_user')
    created_by = CharFilter(method='filter_created_by')
    
    class Meta:
        model = UserBan
        fields = [
            'reason', 'ban_type', 'is_active', 'created_at', 'created_at_lte',
            'expires_at', 'expires_at_lte', 'user', 'created_by'
        ]
    
    def filter_user(self, queryset, name, value):
        """Filter by banned user (username or ID)"""
        if value:
            user_filter = Q(user__username__icontains=value)
            if value.isdigit():
                user_filter |= Q(user_id=int(value))
            return queryset.filter(user_filter)
        return queryset
    
    def filter_created_by(self, queryset, name, value):
        """Filter by creator (username or ID)"""
        if value:
            creator_filter = Q(created_by__username__icontains=value)
            if value.isdigit():
                creator_filter |= Q(created_by_id=int(value))
            return queryset.filter(creator_filter)
        return queryset


class SecurityPolicyFilter(FilterSet):
    """
    Advanced filter for SecurityPolicy model
    """
    
    # Basic filters
    policy_key = CharFilter(lookup_expr='icontains')
    description = CharFilter(lookup_expr='icontains')
    
    # Boolean filters
    is_active = BooleanFilter()
    
    # Date filters
    created_at = DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_at_lte = DateTimeFilter(field_name='created_at', lookup_expr='lte')
    updated_at = DateTimeFilter(field_name='updated_at', lookup_expr='gte')
    updated_at_lte = DateTimeFilter(field_name='updated_at', lookup_expr='lte')
    
    # User filters
    user = CharFilter(method='filter_user')
    
    class Meta:
        model = SecurityPolicy
        fields = [
            'policy_key', 'description', 'is_active', 'created_at',
            'created_at_lte', 'updated_at', 'updated_at_lte', 'user'
        ]
    
    def filter_user(self, queryset, name, value):
        """Filter by user (username or ID)"""
        if value:
            user_filter = Q(user__username__icontains=value)
            if value.isdigit():
                user_filter |= Q(user_id=int(value))
            return queryset.filter(user_filter)
        return queryset


class SecurityInsightFilter(FilterSet):
    """
    Advanced filter for SecurityInsight model
    """
    
    # Date filters
    insight_date = DateFilter(field_name='insight_date', lookup_expr='gte')
    insight_date_lte = DateFilter(field_name='insight_date', lookup_expr='lte')
    date_range = DateRangeFilter(field_name='insight_date')
    
    # Numeric filters
    total_security_events = NumberFilter()
    high_risk_events = NumberFilter()
    vpn_detections = NumberFilter()
    proxy_detections = NumberFilter()
    failed_logins = NumberFilter()
    successful_logins = NumberFilter()
    
    class Meta:
        model = SecurityInsight
        fields = [
            'insight_date', 'insight_date_lte', 'date_range',
            'total_security_events', 'high_risk_events', 'vpn_detections',
            'proxy_detections', 'failed_logins', 'successful_logins'
        ]


class PasswordHistoryFilter(FilterSet):
    """
    Advanced filter for PasswordHistory model
    """
    
    # Basic filters
    password_algorithm = CharFilter(lookup_expr='iexact')
    ip_address = CharFilter(lookup_expr='icontains')
    user_agent = CharFilter(lookup_expr='icontains')
    
    # Date filters
    created_at = DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_at_lte = DateTimeFilter(field_name='created_at', lookup_expr='lte')
    
    # User filters
    user = CharFilter(method='filter_user')
    
    class Meta:
        model = PasswordHistory
        fields = [
            'password_algorithm', 'ip_address', 'user_agent',
            'created_at', 'created_at_lte', 'user'
        ]
    
    def filter_user(self, queryset, name, value):
        """Filter by user (username or ID)"""
        if value:
            user_filter = Q(user__username__icontains=value)
            if value.isdigit():
                user_filter |= Q(user_id=int(value))
            return queryset.filter(user_filter)
        return queryset


class CountryBlockRuleFilter(FilterSet):
    """
    Advanced filter for CountryBlockRule model
    """
    
    # Basic filters
    country_code = CharFilter(lookup_expr='iexact')
    country_name = CharFilter(lookup_expr='icontains')
    reason = CharFilter(lookup_expr='icontains')
    
    # Boolean filters
    is_active = BooleanFilter()
    is_permanent = BooleanFilter()
    
    # Date filters
    created_at = DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_at_lte = DateTimeFilter(field_name='created_at', lookup_expr='lte')
    expires_at = DateTimeFilter(field_name='expires_at', lookup_expr='gte')
    expires_at_lte = DateTimeFilter(field_name='expires_at', lookup_expr='lte')
    
    class Meta:
        model = CountryBlockRule
        fields = [
            'country_code', 'country_name', 'reason', 'is_active',
            'is_permanent', 'created_at', 'created_at_lte', 'expires_at',
            'expires_at_lte'
        ]


# ==================== CUSTOM FILTER MIXINS ====================

class DateRangeMixin:
    """Mixin for custom date range filtering"""
    
    def filter_last_24_hours(self, queryset, name, value):
        """Filter for last 24 hours"""
        if value:
            cutoff = timezone.now() - timedelta(hours=24)
            return queryset.filter(created_at__gte=cutoff)
        return queryset
    
    def filter_last_7_days(self, queryset, name, value):
        """Filter for last 7 days"""
        if value:
            cutoff = timezone.now() - timedelta(days=7)
            return queryset.filter(created_at__gte=cutoff)
        return queryset
    
    def filter_last_30_days(self, queryset, name, value):
        """Filter for last 30 days"""
        if value:
            cutoff = timezone.now() - timedelta(days=30)
            return queryset.filter(created_at__gte=cutoff)
        return queryset


class UserFilterMixin:
    """Mixin for user filtering with username and ID support"""
    
    def filter_user(self, queryset, name, value):
        """Filter by user (username or ID)"""
        if value:
            user_filter = Q(user__username__icontains=value)
            if value.isdigit():
                user_filter |= Q(user_id=int(value))
            return queryset.filter(user_filter)
        return queryset


class IPFilterMixin:
    """Mixin for IP address filtering"""
    
    def filter_ip_address(self, queryset, name, value):
        """Filter by IP address (exact or partial)"""
        if value:
            return queryset.filter(ip_address__icontains=value)
        return queryset
    
    def filter_ip_network(self, queryset, name, value):
        """Filter by IP network/CIDR"""
        if value:
            try:
                import ipaddress
                network = ipaddress.ip_network(value, strict=False)
                
                filtered_ips = []
                for obj in queryset:
                    try:
                        ip = ipaddress.ip_address(obj.ip_address)
                        if ip in network:
                            filtered_ips.append(obj.id)
                    except (ValueError, AttributeError):
                        continue
                
                return queryset.filter(id__in=filtered_ips)
            except ValueError:
                raise ValidationError(f"Invalid IP network format: {value}")
        return queryset


# ==================== ENHANCED FILTERS WITH MIXINS ====================

class EnhancedSecurityLogFilter(DateRangeMixin, UserFilterMixin, IPFilterMixin, SecurityLogFilter):
    """Enhanced SecurityLog filter with mixins"""
    
    # Additional boolean filters
    last_24_hours = BooleanFilter(method='filter_last_24_hours')
    last_7_days = BooleanFilter(method='filter_last_7_days')
    last_30_days = BooleanFilter(method='filter_last_30_days')
    
    # IP network filtering
    ip_network = CharFilter(method='filter_ip_network')


class EnhancedSecurityIncidentFilter(DateRangeMixin, UserFilterMixin, SecurityIncidentFilter):
    """Enhanced SecurityIncident filter with mixins"""
    
    # Additional boolean filters
    last_24_hours = BooleanFilter(method='filter_last_24_hours')
    last_7_days = BooleanFilter(method='filter_last_7_days')
    last_30_days = BooleanFilter(method='filter_last_30_days')


class EnhancedDeviceInfoFilter(DateRangeMixin, UserFilterMixin, IPFilterMixin, DeviceInfoFilter):
    """Enhanced DeviceInfo filter with mixins"""
    
    # Additional boolean filters
    last_24_hours = BooleanFilter(method='filter_last_24_hours')
    last_7_days = BooleanFilter(method='filter_last_7_days')
    last_30_days = BooleanFilter(method='filter_last_30_days')
    
    # IP network filtering
    ip_network = CharFilter(method='filter_ip_network')