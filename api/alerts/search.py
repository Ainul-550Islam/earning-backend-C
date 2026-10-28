"""
Search functionality for alerts app
"""
from django.db.models import Q, Count, Avg
from django.utils import timezone
from datetime import timedelta
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)


class AlertSearchEngine:
    """Advanced search engine for alerts"""
    
    def __init__(self):
        self.search_fields = [
            'message', 'rule__name', 'rule__description',
            'rule__alert_type', 'details'
        ]
        self.facet_fields = [
            'rule__severity', 'rule__alert_type', 'is_resolved'
        ]
    
    def search(self, query: str, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Perform advanced search with faceting"""
        from .models import AlertLog
        
        filters = filters or {}
        queryset = AlertLog.objects.select_related('rule').order_by('-triggered_at')
        
        # Apply text search
        if query:
            queryset = self._apply_text_search(queryset, query)
        
        # Apply filters
        if filters:
            queryset = self._apply_filters(queryset, filters)
        
        # Get search results
        results = list(queryset[:100])  # Limit to 100 results
        
        # Generate facets
        facets = self._generate_facets(queryset, filters)
        
        # Generate suggestions
        suggestions = self._generate_suggestions(query)
        
        return {
            'query': query,
            'results': results,
            'total_count': queryset.count(),
            'facets': facets,
            'suggestions': suggestions,
            'search_time': timezone.now().isoformat()
        }
    
    def _apply_text_search(self, queryset, query: str):
        """Apply text search to queryset"""
        # Create Q objects for each field
        q_objects = []
        
        for field in self.search_fields:
            q_objects.append(Q(**{f'{field}__icontains': query}))
        
        # Combine with OR
        if q_objects:
            return queryset.filter(Q(*q_objects, _connector=Q.OR))
        
        return queryset
    
    def _apply_filters(self, queryset, filters: Dict[str, Any]):
        """Apply filters to queryset"""
        # Date range filter
        if 'start_date' in filters:
            queryset = queryset.filter(triggered_at__gte=filters['start_date'])
        
        if 'end_date' in filters:
            queryset = queryset.filter(triggered_at__lte=filters['end_date'])
        
        # Severity filter
        if 'severity' in filters:
            queryset = queryset.filter(rule__severity=filters['severity'])
        
        # Status filter
        if 'is_resolved' in filters:
            queryset = queryset.filter(is_resolved=filters['is_resolved'])
        
        # Alert type filter
        if 'alert_type' in filters:
            queryset = queryset.filter(rule__alert_type=filters['alert_type'])
        
        # Rule filter
        if 'rule_id' in filters:
            queryset = queryset.filter(rule_id=filters['rule_id'])
        
        return queryset
    
    def _generate_facets(self, queryset, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Generate search facets"""
        facets = {}
        
        # Severity facet
        severity_facet = {}
        for severity, label in [('critical', 'Critical'), ('high', 'High'), ('medium', 'Medium'), ('low', 'Low')]:
            count = queryset.filter(rule__severity=severity).count()
            severity_facet[severity] = {
                'label': label,
                'count': count,
                'selected': filters.get('severity') == severity
            }
        facets['severity'] = severity_facet
        
        # Alert type facet
        alert_type_facet = {}
        from .choices import ALERT_TYPES
        for alert_type, label in ALERT_TYPES:
            count = queryset.filter(rule__alert_type=alert_type).count()
            if count > 0:  # Only show types with alerts
                alert_type_facet[alert_type] = {
                    'label': label,
                    'count': count,
                    'selected': filters.get('alert_type') == alert_type
                }
        facets['alert_type'] = alert_type_facet
        
        # Status facet
        status_facet = {}
        for status, label in [('true', 'Resolved'), ('false', 'Unresolved')]:
            count = queryset.filter(is_resolved=(status == 'true')).count()
            status_facet[status] = {
                'label': label,
                'count': count,
                'selected': filters.get('is_resolved') == (status == 'true')
            }
        facets['status'] = status_facet
        
        return facets
    
    def _generate_suggestions(self, query: str) -> List[str]:
        """Generate search suggestions"""
        suggestions = []
        
        # Get similar alert messages
        from .models import AlertLog
        similar_messages = AlertLog.objects.filter(
            message__icontains=query
        ).values_list('message', flat=True).distinct()[:10]
        
        for message in similar_messages:
            if len(message) > 50:
                # Extract first sentence or phrase
                first_period = message.find('.')
                if first_period > 0:
                    suggestion = message[:first_period + 1].strip()
                else:
                    suggestion = message[:50].strip()
                
                if suggestion not in suggestions:
                    suggestions.append(suggestion)
        
        return suggestions


class AlertRuleSearchEngine:
    """Search engine for alert rules"""
    
    def __init__(self):
        self.search_fields = [
            'name', 'description', 'alert_type', 'severity'
        ]
    
    def search(self, query: str, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Search alert rules"""
        from .models import AlertRule
        
        queryset = AlertRule.objects.all().order_by('-created_at')
        
        # Apply text search
        if query:
            queryset = self._apply_text_search(queryset, query)
        
        # Apply filters
        if filters:
            queryset = self._apply_filters(queryset, filters)
        
        # Get results
        results = list(queryset[:50])
        
        return {
            'query': query,
            'results': results,
            'total_count': queryset.count(),
            'search_time': timezone.now().isoformat()
        }
    
    def _apply_text_search(self, queryset, query: str):
        """Apply text search to queryset"""
        q_objects = []
        
        for field in self.search_fields:
            q_objects.append(Q(**{f'{field}__icontains': query}))
        
        if q_objects:
            return queryset.filter(Q(*q_objects, _connector=Q.OR))
        
        return queryset
    
    def _apply_filters(self, queryset, filters: Dict[str, Any]):
        """Apply filters to queryset"""
        # Active status filter
        if 'is_active' in filters:
            queryset = queryset.filter(is_active=filters['is_active'])
        
        # Severity filter
        if 'severity' in filters:
            queryset = queryset.filter(severity=filters['severity'])
        
        # Alert type filter
        if 'alert_type' in filters:
            queryset = queryset.filter(alert_type=filters['alert_type'])
        
        # Created by filter
        if 'created_by' in filters:
            queryset = queryset.filter(created_by=filters['created_by'])
        
        return queryset


class NotificationSearchEngine:
    """Search engine for notifications"""
    
    def __init__(self):
        self.search_fields = [
            'recipient', 'subject', 'message', 'notification_type'
        ]
    
    def search(self, query: str, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Search notifications"""
        from .models import Notification
        
        queryset = Notification.objects.select_related('alert_log').order_by('-created_at')
        
        # Apply text search
        if query:
            queryset = self._apply_text_search(queryset, query)
        
        # Apply filters
        if filters:
            queryset = self._apply_filters(queryset, filters)
        
        # Get results
        results = list(queryset[:50])
        
        return {
            'query': query,
            'results': results,
            'total_count': queryset.count(),
            'search_time': timezone.now().isoformat()
        }
    
    def _apply_text_search(self, queryset, query: str):
        """Apply text search to queryset"""
        q_objects = []
        
        for field in self.search_fields:
            q_objects.append(Q(**{f'{field}__icontains': query}))
        
        if q_objects:
            return queryset.filter(Q(*q_objects, _connector=Q.OR))
        
        return queryset
    
    def _apply_filters(self, queryset, filters: Dict[str, Any]):
        """Apply filters to queryset"""
        # Status filter
        if 'status' in filters:
            queryset = queryset.filter(status=filters['status'])
        
        # Type filter
        if 'notification_type' in filters:
            queryset = queryset.filter(notification_type=filters['notification_type'])
        
        # Date range filter
        if 'start_date' in filters:
            queryset = queryset.filter(created_at__gte=filters['start_date'])
        
        if 'end_date' in filters:
            queryset = queryset.filter(created_at__lte=filters['end_date'])
        
        return queryset


class SearchAnalytics:
    """Analytics for search operations"""
    
    def __init__(self):
        self.search_logs = []
    
    def log_search(self, query: str, user_id: int = None, results_count: int = 0):
        """Log search operation"""
        log_entry = {
            'query': query,
            'user_id': user_id,
            'results_count': results_count,
            'timestamp': timezone.now().isoformat()
        }
        
        self.search_logs.append(log_entry)
        
        # Keep only last 1000 logs
        if len(self.search_logs) > 1000:
            self.search_logs = self.search_logs[-1000:]
    
    def get_popular_searches(self, limit: int = 10) -> List[str]:
        """Get most popular search queries"""
        from collections import Counter
        
        queries = [log['query'] for log in self.search_logs if log['query']]
        query_counts = Counter(queries)
        
        return [query for query, _ in query_counts.most_common(limit)]
    
    def get_search_stats(self) -> Dict[str, Any]:
        """Get search statistics"""
        if not self.search_logs:
            return {}
        
        total_searches = len(self.search_logs)
        searches_with_results = len([log for log in self.search_logs if log['results_count'] > 0])
        
        return {
            'total_searches': total_searches,
            'searches_with_results': searches_with_results,
            'average_results_per_search': sum(log['results_count'] for log in self.search_logs) / total_searches,
            'most_searched_term': self.get_popular_searches(1)[0] if self.get_popular_searches(1) else None
        }


class SearchSuggestionEngine:
    """Engine for generating search suggestions"""
    
    def __init__(self):
        self.suggestion_types = [
            'recent_searches',
            'popular_searches',
            'auto_complete',
            'did_you_mean'
        ]
    
    def get_suggestions(self, query: str, suggestion_type: str = 'auto_complete') -> List[str]:
        """Get search suggestions"""
        if suggestion_type == 'recent_searches':
            return self._get_recent_searches()
        elif suggestion_type == 'popular_searches':
            return self._get_popular_searches()
        elif suggestion_type == 'auto_complete':
            return self._auto_complete(query)
        elif suggestion_type == 'did_you_mean':
            return self._did_you_mean(query)
        
        return []
    
    def _get_recent_searches(self) -> List[str]:
        """Get recent search queries"""
        # This would typically come from user session or cache
        return []
    
    def _get_popular_searches(self) -> List[str]:
        """Get popular search queries"""
        analytics = SearchAnalytics()
        return analytics.get_popular_searches()
    
    def _auto_complete(self, query: str) -> List[str]:
        """Auto-complete suggestions based on partial query"""
        if len(query) < 2:
            return []
        
        from .models import AlertRule, AlertLog
        
        suggestions = []
        
        # Get alert rule names that start with query
        rule_names = AlertRule.objects.filter(
            name__istartswith=query
        ).values_list('name', flat=True)[:5]
        
        suggestions.extend(rule_names)
        
        # Get alert types that start with query
        from .choices import ALERT_TYPES
        for alert_type, label in ALERT_TYPES:
            if alert_type.lower().startswith(query.lower()):
                suggestions.append(label)
        
        return list(set(suggestions))[:10]
    
    def _did_you_mean(self, query: str) -> List[str]:
        """Generate "did you mean" suggestions"""
        from .models import AlertRule, AlertLog
        
        suggestions = []
        
        # Find similar alert rule names
        similar_rules = AlertRule.objects.filter(
            name__icontains=query
        ).values_list('name', flat=True)[:5]
        
        suggestions.extend(similar_rules)
        
        # Find similar alert messages
        similar_messages = AlertLog.objects.filter(
            message__icontains=query
        ).values_list('message', flat=True)[:5]
        
        for message in similar_messages:
            # Extract first few words
            words = message.split()[:3]
            suggestion = ' '.join(words)
            if suggestion not in suggestions:
                suggestions.append(suggestion)
        
        return suggestions[:5]


# Utility functions
def create_search_query(search_terms: List[str], operator: str = 'AND') -> Q:
    """Create complex search query from terms"""
    if not search_terms:
        return Q()
    
    q_objects = []
    
    for term in search_terms:
        if term:
            q_objects.append(
                Q(message__icontains=term) |
                Q(rule__name__icontains=term) |
                Q(rule__description__icontains=term)
            )
    
    if operator == 'AND':
        return Q(*q_objects, _connector=Q.AND)
    else:
        return Q(*q_objects, _connector=Q.OR)


def parse_search_filters(filters: Dict[str, Any]) -> Dict[str, Any]:
    """Parse and validate search filters"""
    parsed_filters = {}
    
    # Parse date range
    if 'date_range' in filters:
        date_range = filters['date_range']
        if date_range == 'today':
            parsed_filters['start_date'] = timezone.now().date()
            parsed_filters['end_date'] = timezone.now().date()
        elif date_range == 'week':
            end_date = timezone.now().date()
            start_date = end_date - timedelta(days=7)
            parsed_filters['start_date'] = start_date
            parsed_filters['end_date'] = end_date
        elif date_range == 'month':
            end_date = timezone.now().date()
            start_date = end_date - timedelta(days=30)
            parsed_filters['start_date'] = start_date
            parsed_filters['end_date'] = end_date
    
    # Parse severity
    if 'severity' in filters:
        severity = filters['severity']
        valid_severities = ['low', 'medium', 'high', 'critical']
        if severity in valid_severities:
            parsed_filters['severity'] = severity
    
    # Parse status
    if 'status' in filters:
        status = filters['status']
        if status.lower() in ['resolved', 'unresolved']:
            parsed_filters['is_resolved'] = status.lower() == 'resolved'
    
    return parsed_filters


def highlight_search_terms(text: str, search_terms: List[str]) -> str:
    """Highlight search terms in text"""
    highlighted_text = text
    
    for term in search_terms:
        if term.lower() in text.lower():
            # Wrap term in highlight span
            highlighted_text = highlighted_text.replace(
                term,
                f'<span class="search-highlight">{term}</span>',
                1  # Replace only first occurrence
            )
    
    return highlighted_text


def get_search_relevance_score(item: Dict[str, Any], query: str) -> float:
    """Calculate relevance score for search result"""
    score = 0.0
    
    # Exact match in title gets higher score
    if 'name' in item and query.lower() == item['name'].lower():
        score += 10.0
    
    # Partial match in title
    if 'name' in item and query.lower() in item['name'].lower():
        score += 5.0
    
    # Match in description
    if 'description' in item and query.lower() in item['description'].lower():
        score += 2.0
    
    # Match in message
    if 'message' in item and query.lower() in item['message'].lower():
        score += 1.0
    
    # Boost based on recency
    if 'created_at' in item or 'triggered_at' in item:
        timestamp = item.get('created_at', item.get('triggered_at'))
        if timestamp:
            days_old = (timezone.now() - timestamp).days
            if days_old < 1:
                score += 2.0
            elif days_old < 7:
                score += 1.0
    
    return score
