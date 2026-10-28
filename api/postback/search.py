"""
search.py – Search functionality for postback module.

Provides comprehensive search capabilities including:
- Full-text search
- Advanced filtering
- Search indexing
- Search analytics
"""
import json
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta

from django.db import models
from django.db.models import Q, Count, Avg, Sum
from django.utils import timezone
from django.core.cache import cache
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
from django.contrib.postgres.aggregates import StringAgg

from .models import PostbackLog, PostbackInsight, NetworkPostbackConfig
from .choices import PostbackStatus, RejectionReason

logger = logging.getLogger(__name__)


class SearchEngine:
    """
    Main search engine for postback module.
    
    Provides unified search interface across different
    models and data sources.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.indexers = {}
        self._setup_indexers()
    
    def _setup_indexers(self):
        """Setup search indexers."""
        self.indexers['postback_logs'] = PostbackLogIndexer()
        self.indexers['postback_insights'] = PostbackInsightIndexer()
        self.indexers['network_configs'] = NetworkConfigIndexer()
    
    def search(self, query: str, models: List[str] = None, filters: Dict[str, Any] = None, 
              sort_by: str = 'relevance', limit: int = 50) -> Dict[str, Any]:
        """
        Perform unified search across models.
        
        Args:
            query: Search query
            models: Models to search (None = all)
            filters: Additional filters
            sort_by: Sort method ('relevance', 'date', 'score')
            limit: Result limit per model
            
        Returns:
            Search results
        """
        if not query or len(query.strip()) < 2:
            return {'error': 'Query too short', 'results': {}}
        
        models = models or list(self.indexers.keys())
        filters = filters or {}
        results = {}
        
        for model_name in models:
            if model_name not in self.indexers:
                continue
            
            indexer = self.indexers[model_name]
            model_results = indexer.search(query, filters, sort_by, limit)
            
            if model_results['results']:
                results[model_name] = model_results
        
        return {
            'query': query,
            'total_results': sum(r['total_count'] for r in results.values()),
            'results': results,
            'search_time': timezone.now().isoformat(),
        }
    
    def get_search_suggestions(self, query: str, model: str = None, limit: int = 10) -> List[str]:
        """
        Get search suggestions.
        
        Args:
            query: Partial query
            model: Specific model to search
            limit: Number of suggestions
            
        Returns:
            List of suggestions
        """
        suggestions = []
        
        if model and model in self.indexers:
            indexer = self.indexers[model]
            suggestions = indexer.get_suggestions(query, limit)
        else:
            # Get suggestions from all indexers
            for indexer in self.indexers.values():
                model_suggestions = indexer.get_suggestions(query, limit // len(self.indexers))
                suggestions.extend(model_suggestions)
        
        # Remove duplicates and limit
        unique_suggestions = list(set(suggestions))[:limit]
        return unique_suggestions
    
    def get_search_analytics(self, query: str, days: int = 30) -> Dict[str, Any]:
        """
        Get search analytics for query.
        
        Args:
            query: Search query
            days: Number of days to analyze
            
        Returns:
            Search analytics
        """
        analytics = {
            'query': query,
            'search_count': 0,
            'result_count': 0,
            'popular_filters': {},
            'trending_queries': [],
        }
        
        # This would integrate with a search analytics system
        # For now, return basic analytics
        
        return analytics
    
    def reindex_all(self):
        """Reindex all searchable models."""
        for model_name, indexer in self.indexers.items():
            try:
                indexer.reindex()
                self.logger.info(f"Reindexed {model_name}")
            except Exception as e:
                self.logger.error(f"Error reindexing {model_name}: {str(e)}")


class BaseIndexer:
    """
    Base class for search indexers.
    
    Provides common indexing and search functionality.
    """
    
    def __init__(self, model_class: models.Model):
        self.model_class = model_class
        self.logger = logging.getLogger(self.__class__.__name__)
        self.search_fields = []
        self.filter_fields = []
        self.sort_fields = []
    
    def get_search_vector(self):
        """Get search vector for full-text search."""
        if not self.search_fields:
            return None
        
        vector_components = []
        for field in self.search_fields:
            vector_components.append(models.F(field))
        
        return SearchVector(*vector_components)
    
    def search(self, query: str, filters: Dict[str, Any] = None, 
              sort_by: str = 'relevance', limit: int = 50) -> Dict[str, Any]:
        """
        Perform search on model.
        
        Args:
            query: Search query
            filters: Additional filters
            sort_by: Sort method
            limit: Result limit
            
        Returns:
            Search results
        """
        queryset = self.model_class.objects.all()
        
        # Apply full-text search
        if query:
            search_vector = self.get_search_vector()
            if search_vector:
                search_query = SearchQuery(query)
                queryset = queryset.annotate(
                    rank=SearchRank(search_vector, search_query)
                ).filter(rank__gte=0.1)
        
        # Apply filters
        if filters:
            queryset = self._apply_filters(queryset, filters)
        
        # Apply sorting
        queryset = self._apply_sorting(queryset, sort_by)
        
        # Get total count
        total_count = queryset.count()
        
        # Limit results
        results = queryset[:limit]
        
        return {
            'total_count': total_count,
            'results': self._serialize_results(results),
            'query': query,
        }
    
    def _apply_filters(self, queryset, filters: Dict[str, Any]):
        """Apply filters to queryset."""
        for field, value in filters.items():
            if field in self.filter_fields and value is not None:
                if isinstance(value, list):
                    queryset = queryset.filter(**{f"{field}__in": value})
                elif isinstance(value, dict):
                    # Handle range filters
                    if 'min' in value:
                        queryset = queryset.filter(**{f"{field}__gte": value['min']})
                    if 'max' in value:
                        queryset = queryset.filter(**{f"{field}__lte": value['max']})
                else:
                    queryset = queryset.filter(**{field: value})
        
        return queryset
    
    def _apply_sorting(self, queryset, sort_by: str):
        """Apply sorting to queryset."""
        if sort_by == 'relevance' and hasattr(queryset, 'rank'):
            return queryset.order_by('-rank')
        elif sort_by == 'date':
            return queryset.order_by('-created_at')
        elif sort_by == 'score' and 'score' in self.sort_fields:
            return queryset.order_by('-score')
        else:
            return queryset.order_by('-created_at')
    
    def _serialize_results(self, results):
        """Serialize search results."""
        serialized = []
        
        for result in results:
            data = {
                'id': str(result.id),
                'type': self.model_class.__name__.lower(),
                'created_at': result.created_at.isoformat(),
            }
            
            # Add model-specific fields
            if hasattr(result, 'name'):
                data['name'] = result.name
            if hasattr(result, 'title'):
                data['title'] = result.title
            if hasattr(result, 'description'):
                data['description'] = result.description
            
            # Add search rank if available
            if hasattr(result, 'rank'):
                data['rank'] = result.rank
            
            serialized.append(data)
        
        return serialized
    
    def get_suggestions(self, query: str, limit: int = 10) -> List[str]:
        """
        Get search suggestions.
        
        Args:
            query: Partial query
            limit: Number of suggestions
            
        Returns:
            List of suggestions
        """
        # This would integrate with an autocomplete system
        # For now, return empty list
        return []
    
    def reindex(self):
        """Reindex model for search."""
        # This would trigger reindexing process
        pass


class PostbackLogIndexer(BaseIndexer):
    """Search indexer for PostbackLog model."""
    
    def __init__(self):
        super().__init__(PostbackLog)
        self.search_fields = ['lead_id', 'offer_id', 'source_ip', 'user_agent']
        self.filter_fields = ['status', 'network', 'resolved_user', 'rejection_reason']
        self.sort_fields = ['created_at', 'received_at', 'payout']
    
    def _apply_filters(self, queryset, filters: Dict[str, Any]):
        """Apply postback-specific filters."""
        queryset = super()._apply_filters(queryset, filters)
        
        # Date range filter
        if 'date_range' in filters:
            date_range = filters['date_range']
            start_date = date_range.get('start')
            end_date = date_range.get('end')
            
            if start_date:
                queryset = queryset.filter(received_at__gte=start_date)
            if end_date:
                queryset = queryset.filter(received_at__lte=end_date)
        
        # Payout range filter
        if 'payout_range' in filters:
            payout_range = filters['payout_range']
            min_payout = payout_range.get('min')
            max_payout = payout_range.get('max')
            
            if min_payout is not None:
                queryset = queryset.filter(payout__gte=min_payout)
            if max_payout is not None:
                queryset = queryset.filter(payout__lte=max_payout)
        
        # Text search in extracted fields
        if 'extracted_fields' in filters:
            text_query = filters['extracted_fields']
            if text_query:
                queryset = queryset.filter(extracted_fields__icontains=text_query)
        
        return queryset
    
    def _serialize_results(self, results):
        """Serialize postback search results."""
        serialized = []
        
        for result in results:
            data = {
                'id': str(result.id),
                'type': 'postback_log',
                'lead_id': result.lead_id,
                'offer_id': result.offer_id,
                'status': result.status,
                'network_key': result.network.network_key,
                'payout': float(result.payout) if result.payout else None,
                'received_at': result.received_at.isoformat(),
                'source_ip': result.source_ip,
                'rejection_reason': result.rejection_reason,
            }
            
            if hasattr(result, 'rank'):
                data['rank'] = result.rank
            
            serialized.append(data)
        
        return serialized
    
    def get_suggestions(self, query: str, limit: int = 10) -> List[str]:
        """Get postback search suggestions."""
        suggestions = []
        
        # Lead ID suggestions
        lead_suggestions = self.model_class.objects.filter(
            lead_id__icontains=query
        ).values_list('lead_id', flat=True).distinct()[:limit//2]
        suggestions.extend(lead_suggestions)
        
        # Offer ID suggestions
        offer_suggestions = self.model_class.objects.filter(
            offer_id__icontains=query
        ).values_list('offer_id', flat=True).distinct()[:limit//2]
        suggestions.extend(offer_suggestions)
        
        return list(set(suggestions))[:limit]


class PostbackInsightIndexer(BaseIndexer):
    """Search indexer for PostbackInsight model."""
    
    def __init__(self):
        super().__init__(PostbackInsight)
        self.search_fields = ['network__name', 'network__network_key']
        self.filter_fields = ['network', 'date', 'anomaly_detected']
        self.sort_fields = ['date', 'health_score', 'received_count']
    
    def _apply_filters(self, queryset, filters: Dict[str, Any]):
        """Apply insight-specific filters."""
        queryset = super()._apply_filters(queryset, filters)
        
        # Health score range filter
        if 'health_score_range' in filters:
            score_range = filters['health_score_range']
            min_score = score_range.get('min')
            max_score = score_range.get('max')
            
            if min_score is not None:
                queryset = queryset.filter(health_score__gte=min_score)
            if max_score is not None:
                queryset = queryset.filter(health_score__lte=max_score)
        
        # Count range filters
        if 'received_count_range' in filters:
            count_range = filters['received_count_range']
            min_count = count_range.get('min')
            max_count = count_range.get('max')
            
            if min_count is not None:
                queryset = queryset.filter(received_count__gte=min_count)
            if max_count is not None:
                queryset = queryset.filter(received_count__lte=max_count)
        
        return queryset
    
    def _serialize_results(self, results):
        """Serialize insight search results."""
        serialized = []
        
        for result in results:
            data = {
                'id': str(result.id),
                'type': 'postback_insight',
                'network_key': result.network.network_key,
                'network_name': result.network.name,
                'date': result.date.isoformat(),
                'health_score': float(result.health_score),
                'received_count': result.received_count,
                'rewarded_count': result.rewarded_count,
                'rejected_count': result.rejected_count,
                'total_payout': float(result.total_payout),
                'anomaly_detected': result.anomaly_detected,
            }
            
            if hasattr(result, 'rank'):
                data['rank'] = result.rank
            
            serialized.append(data)
        
        return serialized


class NetworkConfigIndexer(BaseIndexer):
    """Search indexer for NetworkPostbackConfig model."""
    
    def __init__(self):
        super().__init__(NetworkPostbackConfig)
        self.search_fields = ['network_key', 'name', 'description']
        self.filter_fields = ['is_active', 'signature_algorithm']
        self.sort_fields = ['created_at', 'name', 'network_key']
    
    def _serialize_results(self, results):
        """Serialize network config search results."""
        serialized = []
        
        for result in results:
            data = {
                'id': str(result.id),
                'type': 'network_config',
                'network_key': result.network_key,
                'name': result.name,
                'is_active': result.is_active,
                'signature_algorithm': result.signature_algorithm,
                'max_payout': float(result.max_payout) if result.max_payout else None,
                'default_reward_points': result.default_reward_points,
                'created_at': result.created_at.isoformat(),
            }
            
            if hasattr(result, 'rank'):
                data['rank'] = result.rank
            
            serialized.append(data)
        
        return serialized


class SearchAnalytics:
    """
    Analytics for search functionality.
    
    Provides insights into search patterns and
    performance metrics.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def get_search_statistics(self, days: int = 30) -> Dict[str, Any]:
        """
        Get search statistics.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Search statistics
        """
        # This would integrate with search analytics storage
        # For now, return placeholder data
        return {
            'total_searches': 0,
            'unique_queries': 0,
            'avg_results_per_search': 0,
            'most_searched_models': {},
            'popular_queries': [],
            'search_trends': [],
        }
    
    def get_query_performance(self, query: str) -> Dict[str, Any]:
        """
        Get performance metrics for specific query.
        
        Args:
            query: Search query
            
        Returns:
            Query performance metrics
        """
        return {
            'query': query,
            'avg_search_time': 0.0,
            'avg_result_count': 0,
            'success_rate': 0.0,
            'click_through_rate': 0.0,
        }
    
    def get_model_search_stats(self, model_name: str, days: int = 30) -> Dict[str, Any]:
        """
        Get search statistics for specific model.
        
        Args:
            model_name: Model name
            days: Number of days to analyze
            
        Returns:
            Model search statistics
        """
        return {
            'model': model_name,
            'total_searches': 0,
            'unique_queries': 0,
            'avg_result_count': 0,
            'popular_filters': {},
        }


class SearchCache:
    """
    Cache management for search results.
    
    Provides intelligent caching for search queries
    and results.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.default_timeout = 300  # 5 minutes
    
    def get_cache_key(self, query: str, model: str, filters: Dict[str, Any] = None) -> str:
        """
        Generate cache key for search.
        
        Args:
            query: Search query
            model: Model name
            filters: Search filters
            
        Returns:
            Cache key
        """
        import hashlib
        
        key_parts = ['search', model, query.lower()]
        
        if filters:
            # Sort filters for consistent key
            sorted_filters = sorted(filters.items())
            filter_str = json.dumps(sorted_filters, sort_keys=True)
            key_parts.append(hashlib.md5(filter_str.encode()).hexdigest())
        
        return ':'.join(key_parts)
    
    def get_cached_results(self, query: str, model: str, filters: Dict[str, Any] = None):
        """
        Get cached search results.
        
        Args:
            query: Search query
            model: Model name
            filters: Search filters
            
        Returns:
            Cached results or None
        """
        cache_key = self.get_cache_key(query, model, filters)
        return cache.get(cache_key)
    
    def cache_results(self, query: str, model: str, results: Dict[str, Any], 
                     filters: Dict[str, Any] = None, timeout: int = None):
        """
        Cache search results.
        
        Args:
            query: Search query
            model: Model name
            results: Search results
            filters: Search filters
            timeout: Cache timeout
        """
        cache_key = self.get_cache_key(query, model, filters)
        timeout = timeout or self.default_timeout
        cache.set(cache_key, results, timeout)
    
    def invalidate_cache(self, model: str = None):
        """
        Invalidate search cache.
        
        Args:
            model: Specific model to invalidate (None = all)
        """
        if model:
            # Invalidate cache for specific model
            pattern = f"search:{model}:*"
        else:
            # Invalidate all search cache
            pattern = "search:*"
        
        # This would require cache implementation that supports pattern deletion
        # For now, we'll use a simple approach
        pass


# Global search engine instance
search_engine = SearchEngine()
search_analytics = SearchAnalytics()
search_cache = SearchCache()


# Convenience functions
def search_postbacks(query: str, filters: Dict[str, Any] = None, limit: int = 50) -> Dict[str, Any]:
    """Search postback logs."""
    return search_engine.search(query, ['postback_logs'], filters, limit=limit)


def search_insights(query: str, filters: Dict[str, Any] = None, limit: int = 50) -> Dict[str, Any]:
    """Search postback insights."""
    return search_engine.search(query, ['postback_insights'], filters, limit=limit)


def search_networks(query: str, filters: Dict[str, Any] = None, limit: int = 50) -> Dict[str, Any]:
    """Search network configurations."""
    return search_engine.search(query, ['network_configs'], filters, limit=limit)


def unified_search(query: str, models: List[str] = None, filters: Dict[str, Any] = None, 
                  limit: int = 50) -> Dict[str, Any]:
    """Perform unified search across models."""
    return search_engine.search(query, models, filters, limit=limit)


def get_search_suggestions(query: str, model: str = None, limit: int = 10) -> List[str]:
    """Get search suggestions."""
    return search_engine.get_search_suggestions(query, model, limit)


# Search decorators
def cache_search_results(timeout: int = 300):
    """
    Decorator for caching search results.
    
    Args:
        timeout: Cache timeout
        
    Returns:
        Decorator function
    """
    def decorator(func):
        def wrapper(query: str, filters: Dict[str, Any] = None, **kwargs):
            # Try to get from cache
            model_name = kwargs.get('model_name', 'unknown')
            cached_results = search_cache.get_cached_results(query, model_name, filters)
            
            if cached_results:
                return cached_results
            
            # Execute search
            results = func(query, filters, **kwargs)
            
            # Cache results
            search_cache.cache_results(query, model_name, results, filters, timeout)
            
            return results
        
        return wrapper
    return decorator


# Search utilities
def build_search_query(text: str, exact_match: bool = False) -> Q:
    """
    Build Django Q object for search query.
    
    Args:
        text: Search text
        exact_match: Whether to use exact match
        
    Returns:
        Q object
    """
    if exact_match:
        return Q(**{'text__exact': text})
    else:
        return Q(**{'text__icontains': text})


def parse_search_filters(filter_string: str) -> Dict[str, Any]:
    """
    Parse filter string into dictionary.
    
    Args:
        filter_string: Filter string (e.g., "status:rewarded,date:2023-01-01")
        
    Returns:
        Parsed filters dictionary
    """
    filters = {}
    
    if not filter_string:
        return filters
    
    try:
        pairs = filter_string.split(',')
        for pair in pairs:
            if ':' in pair:
                key, value = pair.split(':', 1)
                filters[key.strip()] = value.strip()
    except Exception as e:
        logger.error(f"Error parsing filter string '{filter_string}': {str(e)}")
    
    return filters


def format_search_results(results: Dict[str, Any], include_highlights: bool = False) -> Dict[str, Any]:
    """
    Format search results for API response.
    
    Args:
        results: Raw search results
        include_highlights: Whether to include search highlights
        
    Returns:
        Formatted search results
    """
    formatted = {
        'query': results.get('query'),
        'total_results': results.get('total_results', 0),
        'results': {},
        'search_time': results.get('search_time'),
    }
    
    for model_name, model_results in results.get('results', {}).items():
        formatted_results = []
        
        for result in model_results.get('results', []):
            formatted_result = result.copy()
            
            if include_highlights:
                # Add search highlights (placeholder implementation)
                formatted_result['highlights'] = []
            
            formatted_results.append(formatted_result)
        
        formatted['results'][model_name] = {
            'total_count': model_results.get('total_count', 0),
            'results': formatted_results,
        }
    
    return formatted


# Search indexing
def reindex_search():
    """Reindex all search models."""
    search_engine.reindex_all()


def reindex_model(model_name: str):
    """Reindex specific model."""
    if model_name in search_engine.indexers:
        search_engine.indexers[model_name].reindex()
    else:
        raise ValueError(f"Unknown model: {model_name}")


# Search health check
def check_search_health() -> Dict[str, Any]:
    """Check search system health."""
    health_status = {
        'overall': 'healthy',
        'indexers': {},
        'cache_status': 'unknown',
        'issues': [],
    }
    
    # Check indexers
    for model_name, indexer in search_engine.indexers.items():
        try:
            # Test search
            test_results = indexer.search("test", limit=1)
            health_status['indexers'][model_name] = {
                'status': 'healthy',
                'test_search': 'passed',
            }
        except Exception as e:
            health_status['indexers'][model_name] = {
                'status': 'error',
                'error': str(e),
            }
            health_status['issues'].append(f"Indexer {model_name}: {str(e)}")
    
    # Check cache
    try:
        cache.set('health_check', 'ok', timeout=10)
        cache_value = cache.get('health_check')
        if cache_value == 'ok':
            health_status['cache_status'] = 'healthy'
        else:
            health_status['cache_status'] = 'error'
            health_status['issues'].append('Cache not working properly')
    except Exception as e:
        health_status['cache_status'] = 'error'
        health_status['issues'].append(f"Cache error: {str(e)}")
    
    if health_status['issues']:
        health_status['overall'] = 'unhealthy'
    
    return health_status
