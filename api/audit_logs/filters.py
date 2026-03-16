"""
Django FilterSet classes for filtering audit logs
"""

import django_filters
from django_filters import rest_framework as filters
from django.db.models import Q
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from .models import AuditLog, AuditLogAction, AuditLogLevel

User = get_user_model()


class AuditLogFilter(filters.FilterSet):
    """
    FilterSet for AuditLog model with advanced filtering capabilities
    """
    
    # Basic filters
    action = filters.MultipleChoiceFilter(
        choices=AuditLogAction.choices,
        field_name='action',
        label='Action Type',
        help_text='Filter by action type (multiple allowed)'
    )
    
    level = filters.MultipleChoiceFilter(
        choices=AuditLogLevel.choices,
        field_name='level',
        label='Log Level',
        help_text='Filter by log level (multiple allowed)'
    )
    
    user = filters.ModelMultipleChoiceFilter(
        queryset=User.objects.all(),
        field_name='user',
        label='User',
        help_text='Filter by specific users'
    )
    
    user_email = filters.CharFilter(
        field_name='user__email',
        lookup_expr='icontains',
        label='User Email',
        help_text='Filter by user email (contains)'
    )
    
    user_username = filters.CharFilter(
        field_name='user__username',
        lookup_expr='icontains',
        label='Username',
        help_text='Filter by username (contains)'
    )
    
    user_ip = filters.CharFilter(
        field_name='user_ip',
        lookup_expr='exact',
        label='IP Address',
        help_text='Filter by exact IP address'
    )
    
    user_ip_range = filters.CharFilter(
        method='filter_user_ip_range',
        label='IP Range',
        help_text='Filter by IP range (CIDR notation, e.g., 192.168.1.0/24)'
    )
    
    resource_type = filters.CharFilter(
        field_name='resource_type',
        lookup_expr='icontains',
        label='Resource Type',
        help_text='Filter by resource type (contains)'
    )
    
    resource_id = filters.CharFilter(
        field_name='resource_id',
        lookup_expr='exact',
        label='Resource ID',
        help_text='Filter by exact resource ID'
    )
    
    success = filters.BooleanFilter(
        field_name='success',
        label='Success Status',
        help_text='Filter by success status'
    )
    
    status_code = filters.NumberFilter(
        field_name='status_code',
        label='Status Code',
        help_text='Filter by HTTP status code'
    )
    
    status_code_range = filters.RangeFilter(
        field_name='status_code',
        label='Status Code Range',
        help_text='Filter by status code range (e.g., min=400&max=499)'
    )
    
    # Date filters
    timestamp = filters.DateTimeFromToRangeFilter(
        field_name='timestamp',
        label='Timestamp Range',
        help_text='Filter by timestamp range (e.g., timestamp_after=2023-01-01&timestamp_before=2023-12-31)'
    )
    
    created_at = filters.DateTimeFromToRangeFilter(
        field_name='created_at',
        label='Created At Range',
        help_text='Filter by creation date range'
    )
    
    # Relative time filters
    last_hours = filters.NumberFilter(
        method='filter_last_hours',
        label='Last N Hours',
        help_text='Filter logs from last N hours'
    )
    
    last_days = filters.NumberFilter(
        method='filter_last_days',
        label='Last N Days',
        help_text='Filter logs from last N days'
    )
    
    today = filters.BooleanFilter(
        method='filter_today',
        label='Today Only',
        help_text='Filter logs from today only'
    )
    
    this_week = filters.BooleanFilter(
        method='filter_this_week',
        label='This Week',
        help_text='Filter logs from this week (Monday to Sunday)'
    )
    
    this_month = filters.BooleanFilter(
        method='filter_this_month',
        label='This Month',
        help_text='Filter logs from this month'
    )
    
    # Response time filters
    response_time_ms = filters.RangeFilter(
        field_name='response_time_ms',
        label='Response Time Range (ms)',
        help_text='Filter by response time in milliseconds'
    )
    
    slow_requests = filters.NumberFilter(
        method='filter_slow_requests',
        label='Slow Requests',
        help_text='Filter requests slower than N milliseconds'
    )
    
    # Search filters
    search = filters.CharFilter(
        method='filter_search',
        label='Search',
        help_text='Search across multiple fields (message, user info, error message, etc.)'
    )
    
    message = filters.CharFilter(
        field_name='message',
        lookup_expr='icontains',
        label='Message Contains',
        help_text='Filter by message content (contains)'
    )
    
    error_message = filters.CharFilter(
        field_name='error_message',
        lookup_expr='icontains',
        label='Error Message Contains',
        help_text='Filter by error message content (contains)'
    )
    
    # Request/Response filters
    request_method = filters.MultipleChoiceFilter(
        choices=[
            ('GET', 'GET'),
            ('POST', 'POST'),
            ('PUT', 'PUT'),
            ('PATCH', 'PATCH'),
            ('DELETE', 'DELETE'),
            ('HEAD', 'HEAD'),
            ('OPTIONS', 'OPTIONS'),
        ],
        field_name='request_method',
        label='HTTP Method',
        help_text='Filter by HTTP request method'
    )
    
    request_path = filters.CharFilter(
        field_name='request_path',
        lookup_expr='icontains',
        label='Request Path',
        help_text='Filter by request path (contains)'
    )
    
    request_path_startswith = filters.CharFilter(
        field_name='request_path',
        lookup_expr='istartswith',
        label='Request Path Starts With',
        help_text='Filter by request path starting with'
    )
    
    # Location filters
    country = filters.CharFilter(
        field_name='country',
        lookup_expr='iexact',
        label='Country',
        help_text='Filter by exact country name'
    )
    
    city = filters.CharFilter(
        field_name='city',
        lookup_expr='icontains',
        label='City',
        help_text='Filter by city name (contains)'
    )
    
    # Correlation and session
    correlation_id = filters.UUIDFilter(
        field_name='correlation_id',
        label='Correlation ID',
        help_text='Filter by exact correlation ID'
    )
    
    session_id = filters.CharFilter(
        field_name='session_id',
        lookup_expr='exact',
        label='Session ID',
        help_text='Filter by exact session ID'
    )
    
    device_id = filters.CharFilter(
        field_name='device_id',
        lookup_expr='exact',
        label='Device ID',
        help_text='Filter by exact device ID'
    )
    
    # Metadata filters
    metadata_key = filters.CharFilter(
        method='filter_metadata_key',
        label='Metadata Key',
        help_text='Filter logs that have a specific metadata key'
    )
    
    metadata_value = filters.CharFilter(
        method='filter_metadata_value',
        label='Metadata Value',
        help_text='Filter logs with specific metadata key-value pair'
    )
    
    # Advanced filters
    has_error = filters.BooleanFilter(
        method='filter_has_error',
        label='Has Error',
        help_text='Filter logs that have an error message'
    )
    
    has_stack_trace = filters.BooleanFilter(
        method='filter_has_stack_trace',
        label='Has Stack Trace',
        help_text='Filter logs that have a stack trace'
    )
    
    has_request_body = filters.BooleanFilter(
        method='filter_has_request_body',
        label='Has Request Body',
        help_text='Filter logs that have request body data'
    )
    
    has_response_body = filters.BooleanFilter(
        method='filter_has_response_body',
        label='Has Response Body',
        help_text='Filter logs that have response body data'
    )
    
    # Ordering
    order_by = filters.OrderingFilter(
        fields=(
            ('timestamp', 'timestamp'),
            ('created_at', 'created_at'),
            ('response_time_ms', 'response_time'),
            ('status_code', 'status_code'),
            ('level', 'level'),
            ('user__email', 'user_email'),
        ),
        field_labels={
            'timestamp': 'Timestamp',
            'created_at': 'Created At',
            'response_time_ms': 'Response Time',
            'status_code': 'Status Code',
            'level': 'Level',
            'user__email': 'User Email',
        },
        label='Order By',
        help_text='Order results by field (prefix with - for descending)'
    )
    
    class Meta:
        model = AuditLog
        fields = {
            'action': ['exact', 'in'],
            'level': ['exact', 'in'],
            'user_ip': ['exact', 'contains'],
            'resource_type': ['exact', 'contains'],
            'resource_id': ['exact', 'contains'],
            'status_code': ['exact', 'gte', 'lte'],
            'response_time_ms': ['exact', 'gte', 'lte'],
        }
    
    def filter_user_ip_range(self, queryset, name, value):
        """
        Filter by IP range using CIDR notation
        """
        try:
            import ipaddress
            
            # Parse CIDR notation
            network = ipaddress.ip_network(value, strict=False)
            
            # For IPv4
            if network.version == 4:
                # Convert to integer range for database query
                # Note: This assumes PostgreSQL with ipaddress conversion
                # For other databases, you might need a different approach
                start_ip = int(network[0])
                end_ip = int(network[-1])
                
                # This is a simplified approach - in production, you'd use
                # database-specific IP address functions
                return queryset.filter(
                    user_ip__startswith=str(network.network_address).rsplit('.', 1)[0] + '.'
                )
            
            # For IPv6 (simplified)
            elif network.version == 6:
                return queryset.filter(
                    user_ip__startswith=str(network.network_address).split(':')[0]
                )
            
        except (ValueError, ipaddress.AddressValueError):
            # If invalid CIDR, return original queryset
            pass
        
        return queryset
    
    def filter_last_hours(self, queryset, name, value):
        """
        Filter logs from last N hours
        """
        try:
            hours = int(value)
            cutoff = timezone.now() - timezone.timedelta(hours=hours)
            return queryset.filter(timestamp__gte=cutoff)
        except (ValueError, TypeError):
            return queryset
    
    def filter_last_days(self, queryset, name, value):
        """
        Filter logs from last N days
        """
        try:
            days = int(value)
            cutoff = timezone.now() - timezone.timedelta(days=days)
            return queryset.filter(timestamp__gte=cutoff)
        except (ValueError, TypeError):
            return queryset
    
    def filter_today(self, queryset, name, value):
        """
        Filter logs from today
        """
        if value:
            today = timezone.now().date()
            return queryset.filter(timestamp__date=today)
        return queryset
    
    def filter_this_week(self, queryset, name, value):
        """
        Filter logs from this week (Monday to Sunday)
        """
        if value:
            from datetime import timedelta
            
            today = timezone.now().date()
            # Get Monday of this week
            monday = today - timedelta(days=today.weekday())
            # Get Sunday of this week
            sunday = monday + timedelta(days=6)
            
            return queryset.filter(timestamp__date__range=[monday, sunday])
        return queryset
    
    def filter_this_month(self, queryset, name, value):
        """
        Filter logs from this month
        """
        if value:
            today = timezone.now().date()
            first_day = today.replace(day=1)
            # Get last day of month
            if today.month == 12:
                last_day = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                last_day = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
            
            return queryset.filter(timestamp__date__range=[first_day, last_day])
        return queryset
    
    def filter_slow_requests(self, queryset, name, value):
        """
        Filter requests slower than N milliseconds
        """
        try:
            threshold = int(value)
            return queryset.filter(response_time_ms__gte=threshold)
        except (ValueError, TypeError):
            return queryset
    
    def filter_search(self, queryset, name, value):
        """
        Search across multiple fields
        """
        if value:
            search_query = Q()
            
            # Basic text fields
            text_fields = [
                'message', 'error_message', 'user__email',
                'user__username', 'resource_id', 'request_path'
            ]
            
            for field in text_fields:
                search_query |= Q(**{f'{field}__icontains': value})
            
            # Also search in JSON fields
            search_query |= Q(metadata__contains=value)
            search_query |= Q(old_data__contains=value)
            search_query |= Q(new_data__contains=value)
            
            return queryset.filter(search_query)
        
        return queryset
    
    def filter_metadata_key(self, queryset, name, value):
        """
        Filter logs that have a specific metadata key
        """
        if value:
            return queryset.filter(metadata__has_key=value)
        return queryset
    
    def filter_metadata_value(self, queryset, name, value):
        """
        Filter logs with specific metadata key-value pair
        """
        if ':' in value:
            key, val = value.split(':', 1)
            return queryset.filter(metadata__contains={key.strip(): val.strip()})
        return queryset
    
    def filter_has_error(self, queryset, name, value):
        """
        Filter logs that have an error message
        """
        if value is True:
            return queryset.exclude(error_message__isnull=True).exclude(error_message='')
        elif value is False:
            return queryset.filter(Q(error_message__isnull=True) | Q(error_message=''))
        return queryset
    
    def filter_has_stack_trace(self, queryset, name, value):
        """
        Filter logs that have a stack trace
        """
        if value is True:
            return queryset.exclude(stack_trace__isnull=True).exclude(stack_trace='')
        elif value is False:
            return queryset.filter(Q(stack_trace__isnull=True) | Q(stack_trace=''))
        return queryset
    
    def filter_has_request_body(self, queryset, name, value):
        """
        Filter logs that have request body data
        """
        if value is True:
            return queryset.exclude(request_body__isnull=True)
        elif value is False:
            return queryset.filter(request_body__isnull=True)
        return queryset
    
    def filter_has_response_body(self, queryset, name, value):
        """
        Filter logs that have response body data
        """
        if value is True:
            return queryset.exclude(response_body__isnull=True)
        elif value is False:
            return queryset.filter(response_body__isnull=True)
        return queryset


class AuditLogAdvancedFilter(filters.FilterSet):
    """
    Advanced FilterSet with complex query building capabilities
    """
    
    query = filters.CharFilter(
        method='filter_by_query',
        label='Advanced Query',
        help_text='JSON query for advanced filtering. Example: {"and": [{"field": "level", "operator": "equals", "value": "ERROR"}, {"field": "action", "operator": "in", "value": ["LOGIN", "API_CALL"]}]}'
    )
    
    group_by = filters.CharFilter(
        method='filter_group_by',
        label='Group By',
        help_text='Group results by field (e.g., action, level, user)'
    )
    
    aggregate = filters.CharFilter(
        method='filter_aggregate',
        label='Aggregate',
        help_text='Apply aggregation (count, avg, sum, min, max)'
    )
    
    class Meta:
        model = AuditLog
        fields = []
    
    def filter_by_query(self, queryset, name, value):
        """
        Parse and apply advanced JSON query
        """
        if not value:
            return queryset
        
        try:
            import json
            query_data = json.loads(value)
            return self._apply_advanced_query(queryset, query_data)
        except json.JSONDecodeError:
            # If invalid JSON, return original queryset
            return queryset
    
    def _apply_advanced_query(self, queryset, query_data):
        """
        Apply advanced query structure
        """
        from .services.AuditQuery import AuditQuery
        
        query_builder = AuditQuery()
        filter_query = query_builder.build_query(query_data)
        
        return queryset.filter(filter_query)
    
    def filter_group_by(self, queryset, name, value):
        """
        Group results by specified field
        """
        # Note: This is a simplified implementation
        # In a real scenario, you'd return aggregated data
        return queryset.order_by(value).distinct(value)
    
    def filter_aggregate(self, queryset, name, value):
        """
        Apply aggregation
        """
        # This would typically modify the queryset to return aggregates
        # For now, we'll just return the queryset
        # In production, you might use Django's aggregation features
        return queryset


class AuditLogExportFilter(AuditLogFilter):
    """
    Special filter for export operations with additional constraints
    """
    
    max_records = filters.NumberFilter(
        method='filter_max_records',
        label='Maximum Records',
        help_text='Limit export to maximum N records (for performance)'
    )
    
    include_archived = filters.BooleanFilter(
        field_name='archived',
        label='Include Archived',
        help_text='Include archived logs in export'
    )
    
    compression = filters.ChoiceFilter(
        method='filter_compression',
        label='Compression',
        choices=[
            ('none', 'None'),
            ('gzip', 'GZIP'),
            ('zip', 'ZIP')
        ],
        help_text='Compression method for export'
    )
    
    def filter_max_records(self, queryset, name, value):
        """
        Limit to maximum number of records
        """
        try:
            max_records = int(value)
            if max_records > 0:
                # We'll apply the limit later in the view
                return queryset
        except (ValueError, TypeError):
            pass
        
        return queryset
    
    def filter_compression(self, queryset, name, value):
        """
        Filter for compression method (no effect on queryset)
        """
        return queryset
    
    class Meta(AuditLogFilter.Meta):
        # Inherit all fields from AuditLogFilter
        pass


class AuditLogStatsFilter(filters.FilterSet):
    """
    FilterSet for statistics and analytics
    """
    
    interval = filters.ChoiceFilter(
        method='filter_interval',
        label='Time Interval',
        choices=[
            ('hour', 'Hour'),
            ('day', 'Day'),
            ('week', 'Week'),
            ('month', 'Month')
        ],
        help_text='Time interval for statistics grouping'
    )
    
    compare_with = filters.ChoiceFilter(
        method='filter_compare',
        label='Compare With',
        choices=[
            ('previous_period', 'Previous Period'),
            ('same_period_last_week', 'Same Period Last Week'),
            ('same_period_last_month', 'Same Period Last Month'),
            ('same_period_last_year', 'Same Period Last Year')
        ],
        help_text='Compare current period with another period'
    )
    
    metrics = filters.MultipleChoiceFilter(
        method='filter_metrics',
        label='Metrics',
        choices=[
            ('count', 'Total Count'),
            ('success_rate', 'Success Rate'),
            ('avg_response_time', 'Average Response Time'),
            ('error_count', 'Error Count'),
            ('unique_users', 'Unique Users'),
            ('unique_ips', 'Unique IPs')
        ],
        help_text='Metrics to include in statistics'
    )
    
    breakdown_by = filters.ChoiceFilter(
        method='filter_breakdown',
        label='Breakdown By',
        choices=[
            ('action', 'Action'),
            ('level', 'Level'),
            ('user', 'User'),
            ('resource_type', 'Resource Type'),
            ('country', 'Country'),
            ('request_method', 'HTTP Method')
        ],
        help_text='Breakdown statistics by field'
    )
    
    def filter_interval(self, queryset, name, value):
        """Filter by time interval (affects grouping)"""
        # This doesn't filter the queryset, just sets a parameter
        return queryset
    
    def filter_compare(self, queryset, name, value):
        """Filter for comparison period"""
        # This doesn't filter the queryset, just sets a parameter
        return queryset
    
    def filter_metrics(self, queryset, name, value):
        """Filter for metrics selection"""
        # This doesn't filter the queryset, just sets a parameter
        return queryset
    
    def filter_breakdown(self, queryset, name, value):
        """Filter for breakdown field"""
        # This doesn't filter the queryset, just sets a parameter
        return queryset
    
    class Meta:
        model = AuditLog
        fields = []


class UserAuditLogFilter(AuditLogFilter):
    """
    FilterSet for user-specific audit logs (with limited fields)
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Remove fields that users shouldn't filter by
        self.filters.pop('user', None)
        self.filters.pop('user_email', None)
        self.filters.pop('user_username', None)
        self.filters.pop('user_ip_range', None)
        
        # Add user-friendly labels
        self.filters['action'].label = 'Your Actions'
        self.filters['level'].label = 'Log Severity'
    
    class Meta(AuditLogFilter.Meta):
        # Inherit fields but with user context
        pass


class AdminAuditLogFilter(AuditLogFilter):
    """
    FilterSet for admin audit logs with additional administrative filters
    """
    
    suspicious_only = filters.BooleanFilter(
        method='filter_suspicious',
        label='Suspicious Only',
        help_text='Show only suspicious activities'
    )
    
    fraud_risk = filters.NumberFilter(
        method='filter_fraud_risk',
        label='Fraud Risk Score',
        help_text='Filter by fraud risk score (0-100)'
    )
    
    automated = filters.BooleanFilter(
        method='filter_automated',
        label='Automated Requests',
        help_text='Filter automated/bot requests'
    )
    
    def filter_suspicious(self, queryset, name, value):
        """
        Filter suspicious activities
        """
        if value:
            # Define what constitutes suspicious activity
            suspicious_actions = [
                'SUSPICIOUS_LOGIN',
                'BRUTE_FORCE_ATTEMPT',
                'IP_BLOCK',
                'SECURITY',
                'FRAUD_DETECTED'
            ]
            
            suspicious_ips = self._get_suspicious_ips()
            
            return queryset.filter(
                Q(action__in=suspicious_actions) |
                Q(user_ip__in=suspicious_ips) |
                Q(level='SECURITY') |
                Q(success=False, status_code__gte=400, status_code__lt=500)
            ).distinct()
        
        return queryset
    
    def _get_suspicious_ips(self):
        """
        Get list of suspicious IPs from recent logs
        """
        from datetime import timedelta
        
        # Get IPs with many failed logins in last hour
        hour_ago = timezone.now() - timedelta(hours=1)
        
        suspicious_ips = AuditLog.objects.filter(
            timestamp__gte=hour_ago,
            action='LOGIN',
            success=False
        ).values('user_ip').annotate(
            count=Count('id')
        ).filter(
            count__gte=5  # 5 or more failed logins
        ).values_list('user_ip', flat=True)
        
        return list(suspicious_ips)
    
    def filter_fraud_risk(self, queryset, name, value):
        """
        Filter by fraud risk score (from metadata)
        """
        try:
            risk_score = int(value)
            return queryset.filter(metadata__fraud_risk_score__gte=risk_score)
        except (ValueError, TypeError):
            return queryset
    
    def filter_automated(self, queryset, name, value):
        """
        Filter automated/bot requests
        """
        if value is True:
            # Look for bot user agents
            bot_indicators = [
                'bot', 'crawler', 'spider', 'scraper',
                'curl', 'wget', 'python', 'java',
                'Go-http-client', 'node'
            ]
            
            query = Q()
            for indicator in bot_indicators:
                query |= Q(user_agent__icontains=indicator)
            
            # Also look for high request rates
            return queryset.filter(query)
        
        elif value is False:
            # Exclude bots
            bot_indicators = [
                'bot', 'crawler', 'spider', 'scraper',
                'curl', 'wget', 'python', 'java',
                'Go-http-client', 'node'
            ]
            
            query = Q()
            for indicator in bot_indicators:
                query &= ~Q(user_agent__icontains=indicator)
            
            return queryset.filter(query)
        
        return queryset


class AuditLogDashboardFilter(filters.FilterSet):
    """
    FilterSet for audit log dashboard widgets
    """
    
    widget_type = filters.CharFilter(
        method='filter_widget_type',
        label='Widget Type',
        help_text='Type of widget (chart, table, metric, etc.)'
    )
    
    refresh_interval = filters.NumberFilter(
        label='Refresh Interval',
        help_text='Refresh interval in seconds'
    )
    
    time_range = filters.ChoiceFilter(
        method='filter_time_range',
        label='Time Range',
        choices=[
            ('last_hour', 'Last Hour'),
            ('last_24_hours', 'Last 24 Hours'),
            ('last_7_days', 'Last 7 Days'),
            ('last_30_days', 'Last 30 Days'),
            ('custom', 'Custom Range')
        ],
        help_text='Time range for dashboard data'
    )
    
    def filter_widget_type(self, queryset, name, value):
        """Filter by widget type"""
        # This doesn't filter the queryset, just sets a parameter
        return queryset
    
    def filter_time_range(self, queryset, name, value):
        """Filter by time range"""
        if value == 'last_hour':
            cutoff = timezone.now() - timezone.timedelta(hours=1)
            return queryset.filter(timestamp__gte=cutoff)
        
        elif value == 'last_24_hours':
            cutoff = timezone.now() - timezone.timedelta(days=1)
            return queryset.filter(timestamp__gte=cutoff)
        
        elif value == 'last_7_days':
            cutoff = timezone.now() - timezone.timedelta(days=7)
            return queryset.filter(timestamp__gte=cutdown)
        
        elif value == 'last_30_days':
            cutoff = timezone.now() - timezone.timedelta(days=30)
            return queryset.filter(timestamp__gte=cutoff)
        
        return queryset
    
    class Meta:
        model = AuditLog
        fields = []


# Factory function to get appropriate filter based on user role
def get_audit_log_filter(request=None, user=None):
    """
    Get appropriate filter class based on user role
    
    Args:
        request: HTTP request object
        user: User object
    
    Returns:
        FilterSet class
    """
    if user is None and request is not None:
        user = request.user
    
    if user is None:
        return AuditLogFilter
    
    if user.is_superuser:
        return AdminAuditLogFilter
    elif user.is_staff:
        return AuditLogFilter
    else:
        return UserAuditLogFilter