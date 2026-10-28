"""
Rate Limit Filters

Django filter classes for rate limiting models.
"""
from django.utils.translation import gettext_lazy as _

import django_filters
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta

from api.rate_limit.models import RateLimitLog, RateLimitConfig, AbuseReport, IPBlockList, RateLimitInsight


class RateLimitLogFilter(django_filters.FilterSet):
    """
    Filter set for RateLimitLog model.
    
    Provides filtering capabilities for:
    - Date ranges
    - User filtering
    - Endpoint filtering
    - Block status filtering
    - IP address filtering
    - Request method filtering
    """
    
    # Date range filters
    date_from = django_filters.DateFilter(
        field_name='timestamp',
        lookup_expr='gte',
        label=_('Date From')
    )
    
    date_to = django_filters.DateFilter(
        field_name='timestamp',
        lookup_expr='lte',
        label=_('Date To')
    )
    
    datetime_from = django_filters.DateTimeFilter(
        field_name='timestamp',
        lookup_expr='gte',
        label=_('Datetime From')
    )
    
    datetime_to = django_filters.DateTimeFilter(
        field_name='timestamp',
        lookup_expr='lte',
        label=_('Datetime To')
    )
    
    # Time period presets
    last_hour = django_filters.BooleanFilter(
        method='filter_last_hour',
        label=_('Last Hour')
    )
    
    last_24h = django_filters.BooleanFilter(
        method='filter_last_24h',
        label=_('Last 24 Hours')
    )
    
    last_7d = django_filters.BooleanFilter(
        method='filter_last_7d',
        label=_('Last 7 Days')
    )
    
    last_30d = django_filters.BooleanFilter(
        method='filter_last_30d',
        label=_('Last 30 Days')
    )
    
    # User filters
    user = django_filters.ModelChoiceFilter(
        field_name='user',
        lookup_expr='exact',
        label=_('User')
    )
    
    user_id = django_filters.NumberFilter(
        field_name='user__id',
        lookup_expr='exact',
        label=_('User ID')
    )
    
    username = django_filters.CharFilter(
        field_name='user__username',
        lookup_expr='icontains',
        label=_('Username')
    )
    
    # IP address filters
    ip_address = django_filters.CharFilter(
        field_name='ip_address',
        lookup_expr='exact',
        label=_('IP Address')
    )
    
    ip_address_contains = django_filters.CharFilter(
        field_name='ip_address',
        lookup_expr='icontains',
        label=_('IP Address Contains')
    )
    
    ip_network = django_filters.CharFilter(
        method='filter_ip_network',
        label=_('IP Network (CIDR)')
    )
    
    # Endpoint filters
    endpoint = django_filters.CharFilter(
        field_name='endpoint',
        lookup_expr='exact',
        label=_('Endpoint')
    )
    
    endpoint_contains = django_filters.CharFilter(
        field_name='endpoint',
        lookup_expr='icontains',
        label=_('Endpoint Contains')
    )
    
    endpoint_regex = django_filters.CharFilter(
        field_name='endpoint',
        lookup_expr='regex',
        label=_('Endpoint Regex')
    )
    
    # Status filters
    status = django_filters.ChoiceFilter(
        field_name='status',
        lookup_expr='exact',
        choices=RateLimitLog.STATUS_CHOICES,
        label=_('Status')
    )
    
    is_blocked = django_filters.BooleanFilter(
        method='filter_is_blocked',
        label=_('Is Blocked')
    )
    
    is_allowed = django_filters.BooleanFilter(
        method='filter_is_allowed',
        label=_('Is Allowed')
    )
    
    # Request method filters
    request_method = django_filters.ChoiceFilter(
        field_name='request_method',
        lookup_expr='exact',
        choices=[
            ('GET', 'GET'),
            ('POST', 'POST'),
            ('PUT', 'PUT'),
            ('DELETE', 'DELETE'),
            ('PATCH', 'PATCH'),
            ('HEAD', 'HEAD'),
            ('OPTIONS', 'OPTIONS'),
        ],
        label=_('Request Method')
    )
    
    # Suspicion score filters
    suspicion_score_min = django_filters.NumberFilter(
        field_name='suspicion_score',
        lookup_expr='gte',
        label=_('Min Suspicion Score')
    )
    
    suspicion_score_max = django_filters.NumberFilter(
        field_name='suspicion_score',
        lookup_expr='lte',
        label=_('Max Suspicion Score')
    )
    
    high_suspicion = django_filters.BooleanFilter(
        method='filter_high_suspicion',
        label=_('High Suspicion (>70)')
    )
    
    # Request count filters
    requests_count_min = django_filters.NumberFilter(
        field_name='requests_count',
        lookup_expr='gte',
        label=_('Min Requests Count')
    )
    
    requests_count_max = django_filters.NumberFilter(
        field_name='requests_count',
        lookup_expr='lte',
        label=_('Max Requests Count')
    )
    
    high_volume = django_filters.BooleanFilter(
        method='filter_high_volume',
        label=_('High Volume (>50 requests)')
    )
    
    # Config filters
    config = django_filters.ModelChoiceFilter(
        field_name='config',
        lookup_expr='exact',
        label=_('Rate Limit Config')
    )
    
    config_name = django_filters.CharFilter(
        field_name='config__name',
        lookup_expr='icontains',
        label=_('Config Name')
    )
    
    # Earning app specific filters
    task_id = django_filters.CharFilter(
        field_name='task_id',
        lookup_expr='exact',
        label=_('Task ID')
    )
    
    offer_id = django_filters.CharFilter(
        field_name='offer_id',
        lookup_expr='exact',
        label=_('Offer ID')
    )
    
    referral_code = django_filters.CharFilter(
        field_name='referral_code',
        lookup_expr='exact',
        label=_('Referral Code')
    )
    
    # User agent filters
    user_agent = django_filters.CharFilter(
        field_name='user_agent',
        lookup_expr='icontains',
        label=_('User Agent Contains')
    )
    
    bot_user_agent = django_filters.BooleanFilter(
        method='filter_bot_user_agent',
        label=_('Bot User Agent')
    )
    
    class Meta:
        model = RateLimitLog
        fields = [
            'user', 'ip_address', 'endpoint', 'status', 'request_method',
            'config', 'task_id', 'offer_id', 'referral_code'
        ]
    
    def filter_last_hour(self, queryset, name, value):
        """Filter logs from the last hour."""
        if value:
            since = timezone.now() - timedelta(hours=1)
            return queryset.filter(timestamp__gte=since)
        return queryset
    
    def filter_last_24h(self, queryset, name, value):
        """Filter logs from the last 24 hours."""
        if value:
            since = timezone.now() - timedelta(hours=24)
            return queryset.filter(timestamp__gte=since)
        return queryset
    
    def filter_last_7d(self, queryset, name, value):
        """Filter logs from the last 7 days."""
        if value:
            since = timezone.now() - timedelta(days=7)
            return queryset.filter(timestamp__gte=since)
        return queryset
    
    def filter_last_30d(self, queryset, name, value):
        """Filter logs from the last 30 days."""
        if value:
            since = timezone.now() - timedelta(days=30)
            return queryset.filter(timestamp__gte=since)
        return queryset
    
    def filter_is_blocked(self, queryset, name, value):
        """Filter by blocked status."""
        if value is True:
            return queryset.filter(status='blocked')
        elif value is False:
            return queryset.filter(status='allowed')
        return queryset
    
    def filter_is_allowed(self, queryset, name, value):
        """Filter by allowed status."""
        if value is True:
            return queryset.filter(status='allowed')
        elif value is False:
            return queryset.filter(status='blocked')
        return queryset
    
    def filter_ip_network(self, queryset, name, value):
        """Filter by IP network (CIDR notation)."""
        if value:
            try:
                import ipaddress
                network = ipaddress.ip_network(value, strict=False)
                
                # Filter IPs within the network
                filtered_ips = []
                for log in queryset:
                    try:
                        ip = ipaddress.ip_address(log.ip_address)
                        if ip in network:
                            filtered_ips.append(log.id)
                    except ValueError:
                        continue
                
                return queryset.filter(id__in=filtered_ips)
            except ValueError:
                return queryset.none()
        return queryset
    
    def filter_high_suspicion(self, queryset, name, value):
        """Filter logs with high suspicion scores."""
        if value:
            return queryset.filter(suspicion_score__gt=70)
        return queryset
    
    def filter_high_volume(self, queryset, name, value):
        """Filter logs with high request counts."""
        if value:
            return queryset.filter(requests_count__gt=50)
        return queryset
    
    def filter_bot_user_agent(self, queryset, name, value):
        """Filter logs with bot-like user agents."""
        if value:
            bot_patterns = [
                'bot', 'crawler', 'spider', 'scraper', 'curl', 'wget',
                'python-requests', 'python-urllib', 'httpclient', 'axios'
            ]
            
            q_objects = Q()
            for pattern in bot_patterns:
                q_objects |= Q(user_agent__icontains=pattern)
            
            return queryset.filter(q_objects)
        return queryset


class RateLimitConfigFilter(django_filters.FilterSet):
    """
    Filter set for RateLimitConfig model.
    
    Provides filtering capabilities for:
    - Limit type filtering
    - Active/inactive status
    - User-specific configs
    - IP-specific configs
    - Endpoint-specific configs
    """
    
    # Basic filters
    name = django_filters.CharFilter(
        field_name='name',
        lookup_expr='icontains',
        label=_('Name')
    )
    
    rate_limit_type = django_filters.ChoiceFilter(
        field_name='rate_limit_type',
        lookup_expr='exact',
        choices=RateLimitConfig.RATE_LIMIT_TYPES,
        label=_('Rate Limit Type')
    )
    
    is_active = django_filters.BooleanFilter(
        field_name='is_active',
        lookup_expr='exact',
        label=_('Is Active')
    )
    
    # Target filters
    user = django_filters.ModelChoiceFilter(
        field_name='user',
        lookup_expr='exact',
        label=_('User')
    )
    
    user_id = django_filters.NumberFilter(
        field_name='user__id',
        lookup_expr='exact',
        label=_('User ID')
    )
    
    username = django_filters.CharFilter(
        field_name='user__username',
        lookup_expr='icontains',
        label=_('Username')
    )
    
    ip_address = django_filters.CharFilter(
        field_name='ip_address',
        lookup_expr='exact',
        label=_('IP Address')
    )
    
    endpoint = django_filters.CharFilter(
        field_name='endpoint',
        lookup_expr='icontains',
        label=_('Endpoint')
    )
    
    task_type = django_filters.CharFilter(
        field_name='task_type',
        lookup_expr='exact',
        label=_('Task Type')
    )
    
    offer_wall = django_filters.CharFilter(
        field_name='offer_wall',
        lookup_expr='exact',
        label=_('Offer Wall')
    )
    
    # Configuration filters
    requests_per_unit_min = django_filters.NumberFilter(
        field_name='requests_per_unit',
        lookup_expr='gte',
        label=_('Min Requests Per Unit')
    )
    
    requests_per_unit_max = django_filters.NumberFilter(
        field_name='requests_per_unit',
        lookup_expr='lte',
        label=_('Max Requests Per Unit')
    )
    
    time_unit = django_filters.ChoiceFilter(
        field_name='time_unit',
        lookup_expr='exact',
        choices=RateLimitConfig.TIME_UNITS,
        label=_('Time Unit')
    )
    
    time_value_min = django_filters.NumberFilter(
        field_name='time_value',
        lookup_expr='gte',
        label=_('Min Time Value')
    )
    
    time_value_max = django_filters.NumberFilter(
        field_name='time_value',
        lookup_expr='lte',
        label=_('Max Time Value')
    )
    
    # Statistics filters
    hit_count_min = django_filters.NumberFilter(
        field_name='hit_count',
        lookup_expr='gte',
        label=_('Min Hit Count')
    )
    
    hit_count_max = django_filters.NumberFilter(
        field_name='hit_count',
        lookup_expr='lte',
        label=_('Max Hit Count')
    )
    
    block_count_min = django_filters.NumberFilter(
        field_name='block_count',
        lookup_expr='gte',
        label=_('Min Block Count')
    )
    
    block_count_max = django_filters.NumberFilter(
        field_name='block_count',
        lookup_expr='lte',
        label=_('Max Block Count')
    )
    
    high_block_rate = django_filters.BooleanFilter(
        method='filter_high_block_rate',
        label=_('High Block Rate (>20%)')
    )
    
    # Time filters
    created_from = django_filters.DateFilter(
        field_name='created_at',
        lookup_expr='gte',
        label=_('Created From')
    )
    
    created_to = django_filters.DateFilter(
        field_name='created_at',
        lookup_expr='lte',
        label=_('Created To')
    )
    
    last_hit_from = django_filters.DateFilter(
        field_name='last_hit_at',
        lookup_expr='gte',
        label=_('Last Hit From')
    )
    
    last_hit_to = django_filters.DateFilter(
        field_name='last_hit_at',
        lookup_expr='lte',
        label=_('Last Hit To')
    )
    
    recently_hit = django_filters.BooleanFilter(
        method='filter_recently_hit',
        label=_('Recently Hit (last 24h)')
    )
    
    never_hit = django_filters.BooleanFilter(
        method='filter_never_hit',
        label=_('Never Hit')
    )
    
    # Health filters
    health_score_min = django_filters.NumberFilter(
        method='filter_health_score_min',
        label=_('Min Health Score')
    )
    
    health_score_max = django_filters.NumberFilter(
        method='filter_health_score_max',
        label=_('Max Health Score')
    )
    
    poor_health = django_filters.BooleanFilter(
        method='filter_poor_health',
        label=_('Poor Health (<50)')
    )
    
    excellent_health = django_filters.BooleanFilter(
        method='filter_excellent_health',
        label=_('Excellent Health (>80)')
    )
    
    # Preset filters
    global_configs = django_filters.BooleanFilter(
        method='filter_global_configs',
        label=_('Global Configs Only')
    )
    
    user_configs = django_filters.BooleanFilter(
        method='filter_user_configs',
        label=_('User Configs Only')
    )
    
    ip_configs = django_filters.BooleanFilter(
        method='filter_ip_configs',
        label=_('IP Configs Only')
    )
    
    endpoint_configs = django_filters.BooleanFilter(
        method='filter_endpoint_configs',
        label=_('Endpoint Configs Only')
    )
    
    # Whitelist/Blacklist filters
    has_whitelist = django_filters.BooleanFilter(
        method='filter_has_whitelist',
        label=_('Has Whitelist')
    )
    
    has_blacklist = django_filters.BooleanFilter(
        method='filter_has_blacklist',
        label=_('Has Blacklist')
    )
    
    has_bypass_keys = django_filters.BooleanFilter(
        method='filter_has_bypass_keys',
        label=_('Has Bypass Keys')
    )
    
    class Meta:
        model = RateLimitConfig
        fields = [
            'name', 'rate_limit_type', 'is_active', 'user', 'ip_address',
            'endpoint', 'task_type', 'offer_wall', 'time_unit'
        ]
    
    def filter_high_block_rate(self, queryset, name, value):
        """Filter configs with high block rates."""
        if value:
            return queryset.filter(
                hit_count__gt=0,
                block_count__gt=0
            ).extra(
                where=['(block_count::float / hit_count::float) * 100 > 20']
            )
        return queryset
    
    def filter_recently_hit(self, queryset, name, value):
        """Filter configs hit in the last 24 hours."""
        if value:
            since = timezone.now() - timedelta(hours=24)
            return queryset.filter(last_hit_at__gte=since)
        return queryset
    
    def filter_never_hit(self, queryset, name, value):
        """Filter configs that have never been hit."""
        if value:
            return queryset.filter(last_hit_at__isnull=True)
        return queryset
    
    def filter_health_score_min(self, queryset, name, value):
        """Filter by minimum health score."""
        if value:
            filtered_ids = []
            for config in queryset:
                if config.get_api_health() >= value:
                    filtered_ids.append(config.id)
            return queryset.filter(id__in=filtered_ids)
        return queryset
    
    def filter_health_score_max(self, queryset, name, value):
        """Filter by maximum health score."""
        if value:
            filtered_ids = []
            for config in queryset:
                if config.get_api_health() <= value:
                    filtered_ids.append(config.id)
            return queryset.filter(id__in=filtered_ids)
        return queryset
    
    def filter_poor_health(self, queryset, name, value):
        """Filter configs with poor health (<50)."""
        if value:
            filtered_ids = []
            for config in queryset:
                if config.get_api_health() < 50:
                    filtered_ids.append(config.id)
            return queryset.filter(id__in=filtered_ids)
        return queryset
    
    def filter_excellent_health(self, queryset, name, value):
        """Filter configs with excellent health (>80)."""
        if value:
            filtered_ids = []
            for config in queryset:
                if config.get_api_health() > 80:
                    filtered_ids.append(config.id)
            return queryset.filter(id__in=filtered_ids)
        return queryset
    
    def filter_global_configs(self, queryset, name, value):
        """Filter global configs only."""
        if value:
            return queryset.filter(rate_limit_type='global')
        return queryset
    
    def filter_user_configs(self, queryset, name, value):
        """Filter user configs only."""
        if value:
            return queryset.filter(rate_limit_type='user', user__isnull=False)
        return queryset
    
    def filter_ip_configs(self, queryset, name, value):
        """Filter IP configs only."""
        if value:
            return queryset.filter(rate_limit_type='ip', ip_address__isnull=False)
        return queryset
    
    def filter_endpoint_configs(self, queryset, name, value):
        """Filter endpoint configs only."""
        if value:
            return queryset.filter(rate_limit_type='endpoint', endpoint__isnull=False)
        return queryset
    
    def filter_has_whitelist(self, queryset, name, value):
        """Filter configs that have whitelist."""
        if value:
            return queryset.filter(whitelist__len__gt=0)
        return queryset
    
    def filter_has_blacklist(self, queryset, name, value):
        """Filter configs that have blacklist."""
        if value:
            return queryset.filter(blacklist__len__gt=0)
        return queryset
    
    def filter_has_bypass_keys(self, queryset, name, value):
        """Filter configs that have bypass keys."""
        if value:
            return queryset.filter(bypass_keys__len__gt=0)
        return queryset


# Additional filters for other models
class AbuseReportFilter(django_filters.FilterSet):
    """Filter set for AbuseReport model."""
    
    # Date range filters
    created_from = django_filters.DateFilter(
        field_name='created_at',
        lookup_expr='gte',
        label=_('Created From')
    )
    
    created_to = django_filters.DateFilter(
        field_name='created_at',
        lookup_expr='lte',
        label=_('Created To')
    )
    
    last_seen_from = django_filters.DateFilter(
        field_name='last_seen',
        lookup_expr='gte',
        label=_('Last Seen From')
    )
    
    last_seen_to = django_filters.DateFilter(
        field_name='last_seen',
        lookup_expr='lte',
        label=_('Last Seen To')
    )
    
    # Basic filters
    ip_address = django_filters.CharFilter(
        field_name='ip_address',
        lookup_expr='exact',
        label=_('IP Address')
    )
    
    user = django_filters.ModelChoiceFilter(
        field_name='user',
        lookup_expr='exact',
        label=_('User')
    )
    
    abuse_type = django_filters.ChoiceFilter(
        field_name='abuse_type',
        lookup_expr='exact',
        choices=AbuseReport.ABUSE_TYPES,
        label=_('Abuse Type')
    )
    
    endpoint = django_filters.CharFilter(
        field_name='endpoint',
        lookup_expr='icontains',
        label=_('Endpoint')
    )
    
    pattern = django_filters.CharFilter(
        field_name='pattern',
        lookup_expr='icontains',
        label=_('Pattern')
    )
    
    # Status filters
    is_blocked = django_filters.BooleanFilter(
        field_name='is_blocked',
        lookup_expr='exact',
        label=_('Is Blocked')
    )
    
    is_investigated = django_filters.BooleanFilter(
        field_name='is_investigated',
        lookup_expr='exact',
        label=_('Is Investigated')
    )
    
    # Severity filters
    severity_min = django_filters.NumberFilter(
        field_name='severity',
        lookup_expr='gte',
        label=_('Min Severity')
    )
    
    severity_max = django_filters.NumberFilter(
        field_name='severity',
        lookup_expr='lte',
        label=_('Max Severity')
    )
    
    high_severity = django_filters.BooleanFilter(
        method='filter_high_severity',
        label=_('High Severity (4-5)')
    )
    
    # Count filters
    count_24h_min = django_filters.NumberFilter(
        field_name='count_24h',
        lookup_expr='gte',
        label=_('Min 24h Count')
    )
    
    count_7d_min = django_filters.NumberFilter(
        field_name='count_7d',
        lookup_expr='gte',
        label=_('Min 7d Count')
    )
    
    high_volume = django_filters.BooleanFilter(
        method='filter_high_volume',
        label=_('High Volume (>50 in 24h)')
    )
    
    class Meta:
        model = AbuseReport
        fields = [
            'ip_address', 'user', 'abuse_type', 'endpoint', 'pattern',
            'is_blocked', 'is_investigated', 'severity'
        ]
    
    def filter_high_severity(self, queryset, name, value):
        """Filter high severity reports."""
        if value:
            return queryset.filter(severity__gte=4)
        return queryset
    
    def filter_high_volume(self, queryset, name, value):
        """Filter high volume reports."""
        if value:
            return queryset.filter(count_24h__gt=50)
        return queryset


class IPBlockListFilter(django_filters.FilterSet):
    """Filter set for IPBlockList model."""
    
    # Date range filters
    created_from = django_filters.DateFilter(
        field_name='created_at',
        lookup_expr='gte',
        label=_('Created From')
    )
    
    created_to = django_filters.DateFilter(
        field_name='created_at',
        lookup_expr='lte',
        label=_('Created To')
    )
    
    expires_from = django_filters.DateFilter(
        field_name='expires_at',
        lookup_expr='gte',
        label=_('Expires From')
    )
    
    expires_to = django_filters.DateFilter(
        field_name='expires_at',
        lookup_expr='lte',
        label=_('Expires To')
    )
    
    # Basic filters
    block_type = django_filters.ChoiceFilter(
        field_name='block_type',
        lookup_expr='exact',
        choices=IPBlockList.BLOCK_TYPES,
        label=_('Block Type')
    )
    
    reason = django_filters.ChoiceFilter(
        field_name='reason',
        lookup_expr='exact',
        choices=IPBlockList.BLOCK_REASONS,
        label=_('Reason')
    )
    
    blocked_by = django_filters.ModelChoiceFilter(
        field_name='blocked_by',
        lookup_expr='exact',
        label=_('Blocked By')
    )
    
    # IP filters
    ip_address = django_filters.CharFilter(
        field_name='ip_address',
        lookup_expr='exact',
        label=_('IP Address')
    )
    
    ip_range_start = django_filters.CharFilter(
        field_name='ip_range_start',
        lookup_expr='exact',
        label=_('IP Range Start')
    )
    
    ip_range_end = django_filters.CharFilter(
        field_name='ip_range_end',
        lookup_expr='exact',
        label=_('IP Range End')
    )
    
    subnet = django_filters.CharFilter(
        field_name='subnet',
        lookup_expr='exact',
        label=_('Subnet')
    )
    
    # Status filters
    is_active = django_filters.BooleanFilter(
        field_name='is_active',
        lookup_expr='exact',
        label=_('Is Active')
    )
    
    permanent = django_filters.BooleanFilter(
        field_name='permanent',
        lookup_expr='exact',
        label=_('Permanent')
    )
    
    expired = django_filters.BooleanFilter(
        method='filter_expired',
        label=_('Expired')
    )
    
    # Statistics filters
    block_count_min = django_filters.NumberFilter(
        field_name='block_count',
        lookup_expr='gte',
        label=_('Min Block Count')
    )
    
    block_count_max = django_filters.NumberFilter(
        field_name='block_count',
        lookup_expr='lte',
        label=_('Max Block Count')
    )
    
    high_activity = django_filters.BooleanFilter(
        method='filter_high_activity',
        label=_('High Activity (>100 blocks)')
    )
    
    recently_blocked = django_filters.BooleanFilter(
        method='filter_recently_blocked',
        label=_('Recently Blocked (last 24h)')
    )
    
    class Meta:
        model = IPBlockList
        fields = [
            'block_type', 'reason', 'blocked_by', 'ip_address',
            'ip_range_start', 'ip_range_end', 'subnet',
            'is_active', 'permanent'
        ]
    
    def filter_expired(self, queryset, name, value):
        """Filter expired blocks."""
        if value:
            now = timezone.now()
            return queryset.filter(
                permanent=False,
                expires_at__lt=now
            )
        return queryset
    
    def filter_high_activity(self, queryset, name, value):
        """Filter blocks with high activity."""
        if value:
            return queryset.filter(block_count__gt=100)
        return queryset
    
    def filter_recently_blocked(self, queryset, name, value):
        """Filter blocks with recent activity."""
        if value:
            since = timezone.now() - timedelta(hours=24)
            return queryset.filter(last_blocked_at__gte=since)
        return queryset


class RateLimitInsightFilter(django_filters.FilterSet):
    """Filter set for RateLimitInsight model."""
    
    # Date filters
    date_from = django_filters.DateFilter(
        field_name='date',
        lookup_expr='gte',
        label=_('Date From')
    )
    
    date_to = django_filters.DateFilter(
        field_name='date',
        lookup_expr='lte',
        label=_('Date To')
    )
    
    hour = django_filters.NumberFilter(
        field_name='hour',
        lookup_expr='exact',
        label=_('Hour')
    )
    
    # Request statistics filters
    total_requests_min = django_filters.NumberFilter(
        field_name='total_requests',
        lookup_expr='gte',
        label=_('Min Total Requests')
    )
    
    total_requests_max = django_filters.NumberFilter(
        field_name='total_requests',
        lookup_expr='lte',
        label=_('Max Total Requests')
    )
    
    allowed_requests_min = django_filters.NumberFilter(
        field_name='allowed_requests',
        lookup_expr='gte',
        label=_('Min Allowed Requests')
    )
    
    allowed_requests_max = django_filters.NumberFilter(
        field_name='allowed_requests',
        lookup_expr='lte',
        label=_('Max Allowed Requests')
    )
    
    blocked_requests_min = django_filters.NumberFilter(
        field_name='blocked_requests',
        lookup_expr='gte',
        label=_('Min Blocked Requests')
    )
    
    blocked_requests_max = django_filters.NumberFilter(
        field_name='blocked_requests',
        lookup_expr='lte',
        label=_('Max Blocked Requests')
    )
    
    # Abuse statistics filters
    abuse_reports_min = django_filters.NumberFilter(
        field_name='abuse_reports_count',
        lookup_expr='gte',
        label=_('Min Abuse Reports')
    )
    
    abuse_reports_max = django_filters.NumberFilter(
        field_name='abuse_reports_count',
        lookup_expr='lte',
        label=_('Max Abuse Reports')
    )
    
    auto_blocks_min = django_filters.NumberFilter(
        field_name='auto_blocks_count',
        lookup_expr='gte',
        label=_('Min Auto Blocks')
    )
    
    auto_blocks_max = django_filters.NumberFilter(
        field_name='auto_blocks_count',
        lookup_expr='lte',
        label=_('Max Auto Blocks')
    )
    
    manual_blocks_min = django_filters.NumberFilter(
        field_name='manual_blocks_count',
        lookup_expr='gte',
        label=_('Min Manual Blocks')
    )
    
    manual_blocks_max = django_filters.NumberFilter(
        field_name='manual_blocks_count',
        lookup_expr='lte',
        label=_('Max Manual Blocks')
    )
    
    # Performance filters
    avg_response_time_min = django_filters.NumberFilter(
        field_name='avg_response_time',
        lookup_expr='gte',
        label=_('Min Avg Response Time')
    )
    
    avg_response_time_max = django_filters.NumberFilter(
        field_name='avg_response_time',
        lookup_expr='lte',
        label=_('Max Avg Response Time')
    )
    
    peak_requests_min = django_filters.NumberFilter(
        field_name='peak_requests_per_minute',
        lookup_expr='gte',
        label=_('Min Peak Requests')
    )
    
    peak_requests_max = django_filters.NumberFilter(
        field_name='peak_requests_per_minute',
        lookup_expr='lte',
        label=_('Max Peak Requests')
    )
    
    # User and IP filters
    unique_users_min = django_filters.NumberFilter(
        field_name='unique_users',
        lookup_expr='gte',
        label=_('Min Unique Users')
    )
    
    unique_users_max = django_filters.NumberFilter(
        field_name='unique_users',
        lookup_expr='lte',
        label=_('Max Unique Users')
    )
    
    unique_ips_min = django_filters.NumberFilter(
        field_name='unique_ips',
        lookup_expr='gte',
        label=_('Min Unique IPs')
    )
    
    unique_ips_max = django_filters.NumberFilter(
        field_name='unique_ips',
        lookup_expr='lte',
        label=_('Max Unique IPs')
    )
    
    # Error rate filters
    error_rate_min = django_filters.NumberFilter(
        field_name='error_rate',
        lookup_expr='gte',
        label=_('Min Error Rate')
    )
    
    error_rate_max = django_filters.NumberFilter(
        field_name='error_rate',
        lookup_expr='lte',
        label=_('Max Error Rate')
    )
    
    high_error_rate = django_filters.BooleanFilter(
        method='filter_high_error_rate',
        label=_('High Error Rate (>5%)')
    )
    
    high_block_rate = django_filters.BooleanFilter(
        method='filter_high_block_rate',
        label=_('High Block Rate (>10%)')
    )
    
    # Time period presets
    last_7d = django_filters.BooleanFilter(
        method='filter_last_7d',
        label=_('Last 7 Days')
    )
    
    last_30d = django_filters.BooleanFilter(
        method='filter_last_30d',
        label=_('Last 30 Days')
    )
    
    hourly_only = django_filters.BooleanFilter(
        method='filter_hourly_only',
        label=_('Hourly Insights Only')
    )
    
    daily_only = django_filters.BooleanFilter(
        method='filter_daily_only',
        label=_('Daily Insights Only')
    )
    
    class Meta:
        model = RateLimitInsight
        fields = [
            'date', 'hour', 'total_requests', 'allowed_requests',
            'blocked_requests', 'abuse_reports_count'
        ]
    
    def filter_high_error_rate(self, queryset, name, value):
        """Filter insights with high error rates."""
        if value:
            return queryset.filter(error_rate__gt=5.0)
        return queryset
    
    def filter_high_block_rate(self, queryset, name, value):
        """Filter insights with high block rates."""
        if value:
            return queryset.extra(
                where=['(blocked_requests::float / total_requests::float) * 100 > 10']
            )
        return queryset
    
    def filter_last_7d(self, queryset, name, value):
        """Filter insights from last 7 days."""
        if value:
            since = timezone.now().date() - timedelta(days=7)
            return queryset.filter(date__gte=since)
        return queryset
    
    def filter_last_30d(self, queryset, name, value):
        """Filter insights from last 30 days."""
        if value:
            since = timezone.now().date() - timedelta(days=30)
            return queryset.filter(date__gte=since)
        return queryset
    
    def filter_hourly_only(self, queryset, name, value):
        """Filter hourly insights only."""
        if value:
            return queryset.filter(hour__isnull=False)
        return queryset
    
    def filter_daily_only(self, queryset, name, value):
        """Filter daily insights only."""
        if value:
            return queryset.filter(hour__isnull=True)
        return queryset
