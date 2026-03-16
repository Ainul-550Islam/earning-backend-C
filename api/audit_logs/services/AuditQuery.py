"""
Advanced querying and analytics for audit logs
"""

import re
import json
import operator
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from django.db.models import Q, Count, Avg, Max, Min, F, Value, CharField
from django.db.models.functions import TruncDate, TruncHour, Concat
from django.utils import timezone
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.contrib.postgres.aggregates import StringAgg

from ..models import AuditLog, AuditLogAction, AuditLogLevel
from ..serializers import AuditLogSerializer


class AuditQuery:
    """
    Advanced query builder for audit logs with analytics capabilities
    """
    
    OPERATOR_MAP = {
        'equals': 'exact',
        'not_equals': 'exact',
        'contains': 'icontains',
        'starts_with': 'istartswith',
        'ends_with': 'iendswith',
        'greater_than': 'gt',
        'greater_than_equal': 'gte',
        'less_than': 'lt',
        'less_than_equal': 'lte',
        'in': 'in',
        'not_in': 'in',
        'is_null': 'isnull',
        'is_not_null': 'isnull',
        'regex': 'regex',
    }
    
    def __init__(self, user=None):
        self.user = user
        self.base_queryset = AuditLog.objects.all()
        
        # Apply user permissions
        if user and not user.is_staff:
            self.base_queryset = self.base_queryset.filter(
                Q(user=user) | Q(user__isnull=True)
            )
    
    def build_query(self, filters: Dict) -> Q:
        """
        Build Django Q object from complex filters
        
        Args:
            filters: Dictionary of filter conditions
        
        Returns:
            Django Q object
        """
        if not filters:
            return Q()
        
        query = Q()
        
        # Handle logical operators (AND/OR)
        if 'and' in filters:
            and_query = Q()
            for condition in filters['and']:
                and_query &= self._build_condition(condition)
            query &= and_query
        
        elif 'or' in filters:
            or_query = Q()
            for condition in filters['or']:
                or_query |= self._build_condition(condition)
            query &= or_query
        
        else:
            # Single condition
            query &= self._build_condition(filters)
        
        return query
    
    def _build_condition(self, condition: Dict) -> Q:
        """Build Q object from a single condition"""
        field = condition.get('field')
        operator = condition.get('operator')
        value = condition.get('value')
        
        if not field or operator not in self.OPERATOR_MAP:
            return Q()
        
        django_operator = self.OPERATOR_MAP[operator]
        
        # Handle special fields
        if field == 'timestamp':
            if isinstance(value, str):
                try:
                    value = datetime.fromisoformat(value.replace('Z', '+00:00'))
                except ValueError:
                    pass
        
        # Handle JSON fields
        if field in ['metadata', 'old_data', 'new_data']:
            return self._build_json_condition(field, operator, value)
        
        # Build the lookup
        lookup = {f"{field}__{django_operator}": value}
        
        # Handle negation operators
        if operator in ['not_equals', 'not_in', 'is_not_null']:
            return ~Q(**lookup)
        
        return Q(**lookup)
    
    def _build_json_condition(self, field: str, operator: str, value: Any) -> Q:
        """Build condition for JSON fields"""
        # For JSON fields, we need to use special lookups
        if operator == 'contains':
            # Check if JSON contains key-value pair
            if isinstance(value, dict):
                query = Q()
                for key, val in value.items():
                    query &= Q(**{f"{field}__{key}": val})
                return query
        
        # Default: use contains for JSON fields
        return Q(**{f"{field}__contains": value})
    
    def search(self, search_text: str, fields=None) -> Q:
        """
        Full-text search across multiple fields
        
        Args:
            search_text: Text to search for
            fields: List of fields to search (default: all text fields)
        
        Returns:
            Q object for search
        """
        if not search_text:
            return Q()
        
        if fields is None:
            fields = ['message', 'user__email', 'user__username', 
                     'user_ip', 'resource_id', 'error_message']
        
        query = Q()
        
        # Simple text search across fields
        for field in fields:
            lookup = {f"{field}__icontains": search_text}
            query |= Q(**lookup)
        
        # Also search in JSON fields
        json_query = Q(metadata__contains=search_text)
        json_query |= Q(old_data__contains=search_text)
        json_query |= Q(new_data__contains=search_text)
        
        query |= json_query
        
        return query
    
    def advanced_search(self, query: Dict, page: int = 1, page_size: int = 50, 
                       sort_by: str = '-timestamp') -> Tuple[List[AuditLog], int]:
        """
        Perform advanced search with pagination
        
        Args:
            query: Search query dictionary
            page: Page number
            page_size: Items per page
            sort_by: Sort field
        
        Returns:
            Tuple of (results, total_count)
        """
        # Build filter query
        filter_query = self.build_query(query.get('filters', {}))
        
        # Build search query
        search_query = self.search(query.get('search', ''), query.get('fields'))
        
        # Combine queries
        final_query = filter_query & search_query
        
        # Apply to queryset
        queryset = self.base_queryset.filter(final_query)
        
        # Get total count
        total = queryset.count()
        
        # Apply sorting
        if sort_by.startswith('-'):
            field = sort_by[1:]
            order_by = F(field).desc(nulls_last=True)
        else:
            field = sort_by
            order_by = F(field).asc(nulls_first=True)
        
        # Special handling for related fields
        if '__' in field:
            queryset = queryset.order_by(sort_by)
        else:
            queryset = queryset.order_by(order_by)
        
        # Apply pagination
        start = (page - 1) * page_size
        end = start + page_size
        
        results = list(queryset[start:end])
        
        return results, total
    
    def get_time_series(self, start_date=None, end_date=None, interval='hour', 
                       group_by=None, filters=None):
        """
        Get time series data for audit logs
        
        Args:
            start_date: Start date
            end_date: End date
            interval: Time interval ('hour', 'day', 'week', 'month')
            group_by: Additional grouping field
            filters: Additional filters
        
        Returns:
            Time series data
        """
        # Set default date range
        if not end_date:
            end_date = timezone.now()
        if not start_date:
            start_date = end_date - timedelta(days=7)
        
        # Build base queryset
        queryset = self.base_queryset.filter(
            timestamp__range=(start_date, end_date)
        )
        
        # Apply filters
        if filters:
            filter_query = self.build_query(filters)
            queryset = queryset.filter(filter_query)
        
        # Choose truncation function based on interval
        if interval == 'hour':
            trunc_func = TruncHour('timestamp')
            time_format = '%Y-%m-%d %H:00'
        elif interval == 'day':
            trunc_func = TruncDate('timestamp')
            time_format = '%Y-%m-%d'
        elif interval == 'week':
            # Django doesn't have TruncWeek, so we'll use TruncDate with grouping
            trunc_func = TruncDate('timestamp')
            time_format = '%Y-W%W'  # Year-Week number
        elif interval == 'month':
            trunc_func = TruncDate('timestamp')
            time_format = '%Y-%m'
        else:
            trunc_func = TruncHour('timestamp')
            time_format = '%Y-%m-%d %H:00'
        
        # Annotate with time group
        queryset = queryset.annotate(time_group=trunc_func)
        
        # Group by time and optionally other fields
        if group_by:
            # Group by time and additional field
            groups = queryset.values('time_group', group_by).annotate(
                count=Count('id'),
                avg_response_time=Avg('response_time_ms'),
                success_rate=Count('id', filter=Q(success=True)) * 100.0 / Count('id')
            ).order_by('time_group', group_by)
        else:
            # Group only by time
            groups = queryset.values('time_group').annotate(
                count=Count('id'),
                avg_response_time=Avg('response_time_ms'),
                success_rate=Count('id', filter=Q(success=True)) * 100.0 / Count('id')
            ).order_by('time_group')
        
        # Format results
        results = []
        for group in groups:
            result = {
                'time_group': group['time_group'].strftime(time_format) if group['time_group'] else None,
                'count': group['count'],
                'avg_response_time': group['avg_response_time'] or 0,
                'success_rate': group['success_rate'] or 0,
            }
            
            if group_by:
                result[group_by] = group[group_by]
            
            results.append(result)
        
        return results
    
    def get_aggregated_stats(self, start_date=None, end_date=None, filters=None):
        """
        Get aggregated statistics
        
        Args:
            start_date: Start date
            end_date: End date
            filters: Additional filters
        
        Returns:
            Aggregated statistics
        """
        # Build base queryset
        queryset = self.base_queryset
        
        if start_date:
            queryset = queryset.filter(timestamp__gte=start_date)
        if end_date:
            queryset = queryset.filter(timestamp__lte=end_date)
        
        # Apply filters
        if filters:
            filter_query = self.build_query(filters)
            queryset = queryset.filter(filter_query)
        
        # Calculate statistics
        stats = queryset.aggregate(
            total=Count('id'),
            unique_users=Count('user', distinct=True),
            unique_ips=Count('user_ip', distinct=True),
            avg_response_time=Avg('response_time_ms'),
            max_response_time=Max('response_time_ms'),
            min_response_time=Min('response_time_ms'),
            success_count=Count('id', filter=Q(success=True)),
            error_count=Count('id', filter=Q(level='ERROR')),
            warning_count=Count('id', filter=Q(level='WARNING')),
        )
        
        # Calculate success rate
        stats['success_rate'] = (
            stats['success_count'] / stats['total'] * 100
            if stats['total'] > 0 else 0
        )
        
        # Get top actions
        top_actions = queryset.values('action').annotate(
            count=Count('id'),
            avg_time=Avg('response_time_ms')
        ).order_by('-count')[:10]
        
        stats['top_actions'] = list(top_actions)
        
        # Get top users
        top_users = queryset.filter(user__isnull=False).values(
            'user__id', 'user__email', 'user__username'
        ).annotate(
            count=Count('id'),
            last_activity=Max('timestamp')
        ).order_by('-count')[:10]
        
        stats['top_users'] = list(top_users)
        
        # Get top IPs
        top_ips = queryset.exclude(user_ip__isnull=True).values('user_ip').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        stats['top_ips'] = list(top_ips)
        
        # Get error distribution
        error_distribution = queryset.filter(level='ERROR').values(
            'action'
        ).annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        stats['error_distribution'] = list(error_distribution)
        
        return stats
    
    def get_activity_heatmap(self, start_date=None, end_date=None, filters=None):
        """
        Get activity heatmap data (hour vs day of week)
        
        Args:
            start_date: Start date
            end_date: End date
            filters: Additional filters
        
        Returns:
            Heatmap data
        """
        if not end_date:
            end_date = timezone.now()
        if not start_date:
            start_date = end_date - timedelta(days=30)
        
        # Build base queryset
        queryset = self.base_queryset.filter(
            timestamp__range=(start_date, end_date)
        )
        
        # Apply filters
        if filters:
            filter_query = self.build_query(filters)
            queryset = queryset.filter(filter_query)
        
        # Extract hour and day of week
        from django.db.models.functions import ExtractHour, ExtractWeekDay
        
        heatmap_data = queryset.annotate(
            hour=ExtractHour('timestamp'),
            day_of_week=ExtractWeekDay('timestamp')
        ).values('hour', 'day_of_week').annotate(
            count=Count('id')
        ).order_by('day_of_week', 'hour')
        
        # Format into matrix
        matrix = {}
        for item in heatmap_data:
            day = item['day_of_week']
            hour = item['hour']
            count = item['count']
            
            if day not in matrix:
                matrix[day] = {}
            
            matrix[day][hour] = count
        
        return matrix
    
    def get_user_behavior_patterns(self, user_id, start_date=None, end_date=None):
        """
        Analyze user behavior patterns
        
        Args:
            user_id: User ID
            start_date: Start date
            end_date: End date
        
        Returns:
            User behavior patterns
        """
        # Build user-specific queryset
        queryset = self.base_queryset.filter(
            Q(user_id=user_id) | Q(anonymous_id=user_id)
        )
        
        if start_date:
            queryset = queryset.filter(timestamp__gte=start_date)
        if end_date:
            queryset = queryset.filter(timestamp__lte=end_date)
        
        # Get activity by hour of day
        from django.db.models.functions import ExtractHour
        
        hourly_activity = queryset.annotate(
            hour=ExtractHour('timestamp')
        ).values('hour').annotate(
            count=Count('id')
        ).order_by('hour')
        
        # Get preferred actions
        preferred_actions = queryset.values('action').annotate(
            count=Count('id')
        ).order_by('-count')[:5]
        
        # Get success rate by action
        success_by_action = []
        for action in preferred_actions:
            action_name = action['action']
            action_queryset = queryset.filter(action=action_name)
            total = action_queryset.count()
            success = action_queryset.filter(success=True).count()
            
            success_by_action.append({
                'action': action_name,
                'total': total,
                'success': success,
                'success_rate': success / total * 100 if total > 0 else 0
            })
        
        # Get common error patterns
        error_patterns = queryset.filter(
            success=False
        ).values(
            'action', 'error_message'
        ).annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        return {
            'hourly_activity': list(hourly_activity),
            'preferred_actions': list(preferred_actions),
            'success_by_action': success_by_action,
            'error_patterns': list(error_patterns),
            'total_actions': queryset.count(),
            'first_activity': queryset.earliest('timestamp').timestamp if queryset.exists() else None,
            'last_activity': queryset.latest('timestamp').timestamp if queryset.exists() else None,
        }
    
    def detect_anomalies(self, start_date=None, end_date=None, threshold=3):
        """
        Detect anomalous activity patterns
        
        Args:
            start_date: Start date
            end_date: End date
            threshold: Standard deviation threshold
        
        Returns:
            List of anomalies
        """
        if not end_date:
            end_date = timezone.now()
        if not start_date:
            start_date = end_date - timedelta(days=7)
        
        # Get baseline statistics from previous period
        baseline_start = start_date - (end_date - start_date)
        baseline_end = start_date
        
        # Current period stats
        current_stats = self.get_aggregated_stats(start_date, end_date)
        
        # Baseline stats
        baseline_stats = self.get_aggregated_stats(baseline_start, baseline_end)
        
        anomalies = []
        
        # Check for significant changes
        metrics = ['total', 'error_count', 'avg_response_time']
        
        for metric in metrics:
            current = current_stats.get(metric, 0)
            baseline = baseline_stats.get(metric, 0)
            
            # Avoid division by zero
            if baseline == 0:
                baseline = 1
            
            change_percent = ((current - baseline) / baseline) * 100
            
            # If change exceeds threshold, flag as anomaly
            if abs(change_percent) > threshold * 100:  # threshold in standard deviations
                anomalies.append({
                    'metric': metric,
                    'current': current,
                    'baseline': baseline,
                    'change_percent': change_percent,
                    'severity': 'high' if abs(change_percent) > 500 else 'medium',
                    'period': f"{start_date.date()} to {end_date.date()}",
                    'baseline_period': f"{baseline_start.date()} to {baseline_end.date()}"
                })
        
        # Check for unusual IP addresses
        current_ips = self.base_queryset.filter(
            timestamp__range=(start_date, end_date)
        ).values('user_ip').annotate(
            count=Count('id')
        ).order_by('-count')
        
        baseline_ips = self.base_queryset.filter(
            timestamp__range=(baseline_start, baseline_end)
        ).values('user_ip').annotate(
            count=Count('id')
        )
        
        baseline_ip_set = {ip['user_ip'] for ip in baseline_ips}
        
        for ip in current_ips[:20]:  # Check top 20 IPs
            ip_address = ip['user_ip']
            count = ip['count']
            
            # If IP wasn't in baseline or count is unusually high
            if ip_address not in baseline_ip_set and count > 100:
                anomalies.append({
                    'metric': 'new_ip_high_activity',
                    'ip_address': ip_address,
                    'count': count,
                    'severity': 'high',
                    'description': f"New IP address with high activity: {ip_address}"
                })
        
        return anomalies
    
    def test_alert_rule(self, rule):
        """
        Test an alert rule against recent logs
        
        Args:
            rule: AuditAlertRule instance
        
        Returns:
            Test results
        """
        # Get logs from last 24 hours
        end_date = timezone.now()
        start_date = end_date - timedelta(hours=24)
        
        queryset = self.base_queryset.filter(
            timestamp__range=(start_date, end_date)
        )
        
        # Apply rule condition
        condition_query = self.build_query(rule.condition)
        matching_logs = queryset.filter(condition_query)
        
        results = {
            'rule_id': rule.id,
            'rule_name': rule.name,
            'test_period': f"{start_date} to {end_date}",
            'total_logs_in_period': queryset.count(),
            'matching_logs': matching_logs.count(),
            'sample_matches': [],
            'would_trigger': matching_logs.count() > 0,
        }
        
        # Add sample matches
        if matching_logs.exists():
            samples = matching_logs[:5]
            serializer = AuditLogSerializer(samples, many=True)
            results['sample_matches'] = serializer.data
        
        return results
    
    def export_query(self, query: Dict, format='json', include_related=False):
        """
        Export query results
        
        Args:
            query: Search query
            format: Export format
            include_related: Include related objects
        
        Returns:
            Export data
        """
        from .LogExporter import LogExporter
        
        # Get results
        results, _ = self.advanced_search(query, page=1, page_size=10000)
        
        # Convert to queryset
        log_ids = [log.id for log in results]
        queryset = AuditLog.objects.filter(id__in=log_ids)
        
        # Export
        exporter = LogExporter()
        return exporter.export(queryset, format, include_related=include_related)


# Helper functions
def get_audit_query(user=None):
    """Get AuditQuery instance for user"""
    return AuditQuery(user)