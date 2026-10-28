# api/rate_limit/search.py
"""
Search functionality for rate limit module.

Provides search capabilities for rate limiting data.
"""
from difflib import SequenceMatcher

import logging
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Q, Count, Avg
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
from django.core.paginator import Paginator

from api.rate_limit.models import RateLimitLog, RateLimitConfig, UserRateLimitProfile, AbuseReport, IPBlockList

logger = logging.getLogger(__name__)


class RateLimitSearchEngine:
    """
    Search engine for rate limit data.
    """
    
    def __init__(self):
        self.search_fields = {
            'RateLimitLog': ['endpoint', 'request_method', 'user_agent', 'ip_address'],
            'RateLimitConfig': ['name', 'endpoint', 'rate_limit_type'],
            'UserRateLimitProfile': ['user__username', 'user__email'],
            'AbuseReport': ['description', 'abuse_type', 'ip_address'],
            'IPBlockList': ['ip_address', 'block_reason']
        }
    
    def search_logs(self, query: str, filters: Dict[str, Any] = None, 
                   page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """
        Search rate limit logs.
        
        Args:
            query: Search query
            filters: Additional filters
            page: Page number
            page_size: Page size
            
        Returns:
            Search results
        """
        try:
            queryset = RateLimitLog.objects.all()
            
            # Apply text search
            if query:
                queryset = self._apply_text_search(queryset, query, 'RateLimitLog')
            
            # Apply filters
            if filters:
                queryset = self._apply_log_filters(queryset, filters)
            
            # Order by relevance
            queryset = queryset.order_by('-timestamp')
            
            # Paginate
            paginator = Paginator(queryset, page_size)
            page_obj = paginator.get_page(page)
            
            results = []
            for log in page_obj:
                results.append({
                    'id': log.id,
                    'timestamp': log.timestamp.isoformat(),
                    'user': log.user.username if log.user else 'Anonymous',
                    'ip_address': log.ip_address,
                    'endpoint': log.endpoint,
                    'method': log.request_method,
                    'status': log.status,
                    'suspicion_score': log.suspicion_score,
                    'relevance': self._calculate_relevance(log, query)
                })
            
            return {
                'success': True,
                'query': query,
                'results': results,
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total_pages': paginator.num_pages,
                    'total_count': paginator.count,
                    'has_next': page_obj.has_next(),
                    'has_previous': page_obj.has_previous()
                }
            }
            
        except Exception as e:
            logger.error(f"Log search failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def search_configs(self, query: str, filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Search rate limit configurations.
        
        Args:
            query: Search query
            filters: Additional filters
            
        Returns:
            Search results
        """
        try:
            queryset = RateLimitConfig.objects.all()
            
            # Apply text search
            if query:
                queryset = self._apply_text_search(queryset, query, 'RateLimitConfig')
            
            # Apply filters
            if filters:
                queryset = self._apply_config_filters(queryset, filters)
            
            results = []
            for config in queryset:
                results.append({
                    'id': config.id,
                    'name': config.name,
                    'rate_limit_type': config.rate_limit_type,
                    'requests_per_unit': config.requests_per_unit,
                    'time_unit': config.time_unit,
                    'endpoint': config.endpoint,
                    'is_active': config.is_active,
                    'relevance': self._calculate_relevance(config, query)
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Config search failed: {str(e)}")
            return []
    
    def search_users(self, query: str, filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Search user rate limit profiles.
        
        Args:
            query: Search query
            filters: Additional filters
            
        Returns:
            Search results
        """
        try:
            queryset = UserRateLimitProfile.objects.select_related('user').all()
            
            # Apply text search
            if query:
                queryset = self._apply_text_search(queryset, query, 'UserRateLimitProfile')
            
            # Apply filters
            if filters:
                queryset = self._apply_user_filters(queryset, filters)
            
            results = []
            for profile in queryset:
                results.append({
                    'id': profile.id,
                    'user_id': profile.user.id,
                    'username': profile.user.username,
                    'email': profile.user.email,
                    'api_health_score': profile.api_health_score,
                    'suspicion_score': profile.suspicion_score,
                    'is_premium': profile.is_premium,
                    'total_requests': profile.total_requests,
                    'relevance': self._calculate_relevance(profile, query)
                })
            
            return results
            
        except Exception as e:
            logger.error(f"User search failed: {str(e)}")
            return []
    
    def search_abuse_reports(self, query: str, filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Search abuse reports.
        
        Args:
            query: Search query
            filters: Additional filters
            
        Returns:
            Search results
        """
        try:
            queryset = AbuseReport.objects.all()
            
            # Apply text search
            if query:
                queryset = self._apply_text_search(queryset, query, 'AbuseReport')
            
            # Apply filters
            if filters:
                queryset = self._apply_abuse_filters(queryset, filters)
            
            results = []
            for report in queryset:
                results.append({
                    'id': report.id,
                    'abuse_type': report.abuse_type,
                    'severity': report.severity,
                    'ip_address': report.ip_address,
                    'description': report.description,
                    'is_investigated': report.is_investigated,
                    'created_at': report.created_at.isoformat(),
                    'relevance': self._calculate_relevance(report, query)
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Abuse report search failed: {str(e)}")
            return []
    
    def search_ip_blocks(self, query: str, filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Search IP blocks.
        
        Args:
            query: Search query
            filters: Additional filters
            
        Returns:
            Search results
        """
        try:
            queryset = IPBlockList.objects.all()
            
            # Apply text search
            if query:
                queryset = self._apply_text_search(queryset, query, 'IPBlockList')
            
            # Apply filters
            if filters:
                queryset = self._apply_ip_block_filters(queryset, filters)
            
            results = []
            for block in queryset:
                results.append({
                    'id': block.id,
                    'ip_address': block.ip_address,
                    'block_type': block.block_type,
                    'block_reason': block.block_reason,
                    'is_active': block.is_active,
                    'permanent': block.permanent,
                    'created_at': block.created_at.isoformat(),
                    'relevance': self._calculate_relevance(block, query)
                })
            
            return results
            
        except Exception as e:
            logger.error(f"IP block search failed: {str(e)}")
            return []
    
    def _apply_text_search(self, queryset, query: str, model_name: str):
        """
        Apply text search to queryset.
        
        Args:
            queryset: Django queryset
            query: Search query
            model_name: Model name
            
        Returns:
            Filtered queryset
        """
        if not query or model_name not in self.search_fields:
            return queryset
        
        search_fields = self.search_fields[model_name]
        q_objects = Q()
        
        for field in search_fields:
            q_objects |= Q(**{f"{field}__icontains": query})
        
        return queryset.filter(q_objects)
    
    def _apply_log_filters(self, queryset, filters: Dict[str, Any]):
        """Apply filters to log queryset."""
        if 'status' in filters:
            queryset = queryset.filter(status=filters['status'])
        
        if 'user_id' in filters:
            queryset = queryset.filter(user_id=filters['user_id'])
        
        if 'ip_address' in filters:
            queryset = queryset.filter(ip_address=filters['ip_address'])
        
        if 'endpoint' in filters:
            queryset = queryset.filter(endpoint__icontains=filters['endpoint'])
        
        if 'date_from' in filters:
            queryset = queryset.filter(timestamp__gte=filters['date_from'])
        
        if 'date_to' in filters:
            queryset = queryset.filter(timestamp__lte=filters['date_to'])
        
        if 'suspicion_score_min' in filters:
            queryset = queryset.filter(suspicion_score__gte=filters['suspicion_score_min'])
        
        return queryset
    
    def _apply_config_filters(self, queryset, filters: Dict[str, Any]):
        """Apply filters to config queryset."""
        if 'rate_limit_type' in filters:
            queryset = queryset.filter(rate_limit_type=filters['rate_limit_type'])
        
        if 'is_active' in filters:
            queryset = queryset.filter(is_active=filters['is_active'])
        
        if 'endpoint' in filters:
            queryset = queryset.filter(endpoint__icontains=filters['endpoint'])
        
        return queryset
    
    def _apply_user_filters(self, queryset, filters: Dict[str, Any]):
        """Apply filters to user queryset."""
        if 'is_premium' in filters:
            queryset = queryset.filter(is_premium=filters['is_premium'])
        
        if 'api_health_score_min' in filters:
            queryset = queryset.filter(api_health_score__gte=filters['api_health_score_min'])
        
        if 'suspicion_score_min' in filters:
            queryset = queryset.filter(suspicion_score__gte=filters['suspicion_score_min'])
        
        return queryset
    
    def _apply_abuse_filters(self, queryset, filters: Dict[str, Any]):
        """Apply filters to abuse queryset."""
        if 'abuse_type' in filters:
            queryset = queryset.filter(abuse_type=filters['abuse_type'])
        
        if 'severity' in filters:
            queryset = queryset.filter(severity=filters['severity'])
        
        if 'is_investigated' in filters:
            queryset = queryset.filter(is_investigated=filters['is_investigated'])
        
        return queryset
    
    def _apply_ip_block_filters(self, queryset, filters: Dict[str, Any]):
        """Apply filters to IP block queryset."""
        if 'block_type' in filters:
            queryset = queryset.filter(block_type=filters['block_type'])
        
        if 'block_reason' in filters:
            queryset = queryset.filter(block_reason=filters['block_reason'])
        
        if 'is_active' in filters:
            queryset = queryset.filter(is_active=filters['is_active'])
        
        if 'permanent' in filters:
            queryset = queryset.filter(permanent=filters['permanent'])
        
        return queryset
    
    def _calculate_relevance(self, instance, query: str) -> float:
        """
        Calculate relevance score for search result.
        
        Args:
            instance: Model instance
            query: Search query
            
        Returns:
            Relevance score (0-1)
        """
        if not query:
            return 1.0
        
        relevance = 0.0
        query_lower = query.lower()
        
        # Check different fields based on model type
        if hasattr(instance, 'endpoint') and instance.endpoint:
            if query_lower in instance.endpoint.lower():
                relevance += 0.4
        
        if hasattr(instance, 'name') and instance.name:
            if query_lower in instance.name.lower():
                relevance += 0.3
        
        if hasattr(instance, 'ip_address') and instance.ip_address:
            if query_lower in instance.ip_address.lower():
                relevance += 0.2
        
        if hasattr(instance, 'description') and instance.description:
            if query_lower in instance.description.lower():
                relevance += 0.1
        
        return min(1.0, relevance)


class AdvancedSearchEngine(RateLimitSearchEngine):
    """
    Advanced search engine with more sophisticated features.
    """
    
    def __init__(self):
        super().__init__()
        self.search_weights = {
            'exact_match': 1.0,
            'starts_with': 0.8,
            'contains': 0.6,
            'fuzzy': 0.4
        }
    
    def fuzzy_search(self, query: str, model_name: str, threshold: float = 0.6) -> List[Dict[str, Any]]:
        """
        Perform fuzzy search.
        
        Args:
            query: Search query
            model_name: Model name
            threshold: Similarity threshold
            
        Returns:
            Search results
        """
        try:
            from difflib import SequenceMatcher
            
            results = []
            
            # Get all records
            if model_name == 'RateLimitLog':
                queryset = RateLimitLog.objects.all()
            elif model_name == 'RateLimitConfig':
                queryset = RateLimitConfig.objects.all()
            elif model_name == 'UserRateLimitProfile':
                queryset = UserRateLimitProfile.objects.select_related('user').all()
            else:
                return results
            
            for instance in queryset:
                similarity = self._calculate_fuzzy_similarity(instance, query)
                
                if similarity >= threshold:
                    results.append({
                        'instance': instance,
                        'similarity': similarity,
                        'relevance': similarity
                    })
            
            # Sort by similarity
            results.sort(key=lambda x: x['similarity'], reverse=True)
            
            return results
            
        except Exception as e:
            logger.error(f"Fuzzy search failed: {str(e)}")
            return []
    
    def _calculate_fuzzy_similarity(self, instance, query: str) -> float:
        """Calculate fuzzy similarity score."""
        similarity = 0.0
        query_lower = query.lower()
        
        # Check different fields
        fields_to_check = []
        
        if hasattr(instance, 'endpoint') and instance.endpoint:
            fields_to_check.append(instance.endpoint)
        
        if hasattr(instance, 'name') and instance.name:
            fields_to_check.append(instance.name)
        
        if hasattr(instance, 'ip_address') and instance.ip_address:
            fields_to_check.append(instance.ip_address)
        
        if hasattr(instance, 'description') and instance.description:
            fields_to_check.append(instance.description)
        
        if hasattr(instance, 'user') and instance.user:
            fields_to_check.append(instance.user.username)
            fields_to_check.append(instance.user.email)
        
        # Calculate maximum similarity across all fields
        for field_value in fields_to_check:
            if field_value:
                field_similarity = SequenceMatcher(None, query_lower, field_value.lower()).ratio()
                similarity = max(similarity, field_similarity)
        
        return similarity
    
    def search_with_aggregations(self, query: str, model_name: str) -> Dict[str, Any]:
        """
        Search with aggregation results.
        
        Args:
            query: Search query
            model_name: Model name
            
        Returns:
            Search results with aggregations
        """
        try:
            base_results = []
            
            if model_name == 'RateLimitLog':
                base_results = self.search_logs(query)
                aggregations = self._get_log_aggregations(query)
            elif model_name == 'RateLimitConfig':
                base_results = self.search_configs(query)
                aggregations = self._get_config_aggregations(query)
            elif model_name == 'UserRateLimitProfile':
                base_results = self.search_users(query)
                aggregations = self._get_user_aggregations(query)
            else:
                return {'success': False, 'error': 'Unknown model'}
            
            return {
                'success': True,
                'query': query,
                'results': base_results,
                'aggregations': aggregations
            }
            
        except Exception as e:
            logger.error(f"Search with aggregations failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _get_log_aggregations(self, query: str) -> Dict[str, Any]:
        """Get log aggregations for search results."""
        # This would implement aggregation logic
        return {
            'status_counts': {},
            'hourly_distribution': [],
            'top_endpoints': [],
            'top_ips': []
        }
    
    def _get_config_aggregations(self, query: str) -> Dict[str, Any]:
        """Get config aggregations for search results."""
        return {
            'type_counts': {},
            'time_unit_counts': {},
            'active_inactive_counts': {}
        }
    
    def _get_user_aggregations(self, query: str) -> Dict[str, Any]:
        """Get user aggregations for search results."""
        return {
            'premium_standard_counts': {},
            'health_score_distribution': [],
            'suspicion_score_distribution': []
        }


class SearchIndexManager:
    """
    Manager for search index operations.
    """
    
    def __init__(self):
        self.index_name = 'rate_limit_search'
    
    def build_index(self):
        """Build search index."""
        try:
            # This would integrate with Elasticsearch or similar
            logger.info("Building search index...")
            
            # Index different model types
            self._index_logs()
            self._index_configs()
            self._index_users()
            self._index_abuse_reports()
            self._index_ip_blocks()
            
            logger.info("Search index built successfully")
            
        except Exception as e:
            logger.error(f"Failed to build search index: {str(e)}")
    
    def _index_logs(self):
        """Index rate limit logs."""
        # Implementation would index logs in search engine
        pass
    
    def _index_configs(self):
        """Index rate limit configs."""
        # Implementation would index configs in search engine
        pass
    
    def _index_users(self):
        """Index user profiles."""
        # Implementation would index users in search engine
        pass
    
    def _index_abuse_reports(self):
        """Index abuse reports."""
        # Implementation would index abuse reports in search engine
        pass
    
    def _index_ip_blocks(self):
        """Index IP blocks."""
        # Implementation would index IP blocks in search engine
        pass
    
    def update_index(self, model_instance, operation: str = 'update'):
        """
        Update search index for a model instance.
        
        Args:
            model_instance: Model instance
            operation: Operation type (create, update, delete)
        """
        try:
            # This would update the search index
            logger.debug(f"Updating search index for {model_instance.__class__.__name__} {model_instance.id}: {operation}")
            
        except Exception as e:
            logger.error(f"Failed to update search index: {str(e)}")


# Global instances
search_engine = RateLimitSearchEngine()
advanced_search_engine = AdvancedSearchEngine()
index_manager = SearchIndexManager()


# Export search classes
__all__ = [
    'RateLimitSearchEngine',
    'AdvancedSearchEngine',
    'SearchIndexManager',
    'search_engine',
    'advanced_search_engine',
    'index_manager'
]
