# =============================================================================
# auto_mod/search.py
# =============================================================================

"""
Search functionality for auto moderation system.
Provides search indexing, querying, and analytics capabilities.
"""
import time

import logging
import json
from typing import Any, Dict, List, Optional, Union, Tuple
from datetime import datetime, timedelta
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings
from django.db import models
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
from django.contrib.postgres.aggregates import StringAgg

logger = logging.getLogger(__name__)


class SearchIndex:
    """
    Base class for search indexing functionality.
    """
    
    def __init__(self, model_class, index_name: str = None):
        self.model_class = model_class
        self.index_name = index_name or f"{model_class.__name__.lower()}_search"
        self.search_fields = []
        self.filter_fields = []
        self.sort_fields = []
        self.boost_fields = {}
    
    def add_search_field(self, field_name: str, weight: float = 1.0) -> None:
        """Add a field to search index."""
        self.search_fields.append((field_name, weight))
    
    def add_filter_field(self, field_name: str, field_type: str = 'text') -> None:
        """Add a filter field."""
        self.filter_fields.append((field_name, field_type))
    
    def add_sort_field(self, field_name: str) -> None:
        """Add a sort field."""
        self.sort_fields.append(field_name)
    
    def add_boost_field(self, field_name: str, boost: float) -> None:
        """Add a boost field."""
        self.boost_fields[field_name] = boost
    
    def build_search_vector(self) -> SearchVector:
        """Build PostgreSQL search vector."""
        vectors = []
        
        for field_name, weight in self.search_fields:
            vectors.append(SearchVector(field_name, weight=weight))
        
        if vectors:
            return vectors[0] if len(vectors) == 1 else sum(vectors)
        
        return SearchVector('id')  # Fallback
    
    def index_document(self, instance) -> Dict[str, Any]:
        """Index a single document."""
        doc = {
            'id': str(instance.pk),
            'model': self.model_class.__name__,
            'indexed_at': timezone.now().isoformat(),
        }
        
        # Add search fields
        for field_name, weight in self.search_fields:
            value = getattr(instance, field_name, '')
            if value:
                doc[field_name] = str(value)
        
        # Add filter fields
        for field_name, field_type in self.filter_fields:
            value = getattr(instance, field_name, None)
            if value is not None:
                if field_type == 'date':
                    doc[field_name] = value.isoformat() if hasattr(value, 'isoformat') else str(value)
                elif field_type == 'number':
                    doc[field_name] = float(value)
                else:
                    doc[field_name] = str(value)
        
        # Add sort fields
        for field_name in self.sort_fields:
            value = getattr(instance, field_name, None)
            if value is not None:
                doc[field_name] = value
        
        return doc
    
    def build_search_query(self, query: str, filters: Dict = None, 
                          sort_by: str = None, boost: bool = True) -> Tuple[SearchQuery, Dict]:
        """Build search query with filters."""
        search_query = SearchQuery(query)
        
        # Apply boosts if enabled
        if boost and self.boost_fields:
            # This would be implemented with PostgreSQL search configuration
            pass
        
        return search_query, filters or {}


class ModerationSearchIndex(SearchIndex):
    """
    Search index for moderation data.
    """
    
    def __init__(self):
        from .models import (
            SuspiciousSubmission, ModerationDecision, 
            ModerationAppeal, TaskBot, ContentSignal
        )
        
        super().__init__(SuspiciousSubmission, 'moderation_search')
        
        # Search fields with weights
        self.add_search_field('text_content', weight=2.0)
        self.add_search_field('metadata', weight=1.5)
        self.add_search_field('submission_type', weight=1.0)
        self.add_search_field('flag_reason', weight=1.8)
        
        # Filter fields
        self.add_filter_field('status', 'text')
        self.add_filter_field('risk_level', 'text')
        self.add_filter_field('submission_type', 'text')
        self.add_filter_field('created_at', 'date')
        self.add_filter_field('ai_confidence', 'number')
        self.add_filter_field('risk_score', 'number')
        
        # Sort fields
        self.add_sort_field('created_at')
        self.add_sort_field('ai_confidence')
        self.add_sort_field('risk_score')
        
        # Boost fields
        self.add_boost_field('text_content', 2.0)
        self.add_boost_field('flag_reason', 1.5)


class SearchEngine:
    """
    Main search engine for moderation system.
    """
    
    def __init__(self):
        self.indices = {}
        self.query_cache = {}
        self.cache_timeout = 300  # 5 minutes
        self.max_results = 1000
        self.register_default_indices()
    
    def register_index(self, index: SearchIndex) -> None:
        """Register a search index."""
        self.indices[index.index_name] = index
        logger.info(f"SearchEngine: registered index {index.index_name}")
    
    def register_default_indices(self) -> None:
        """Register default search indices."""
        moderation_index = ModerationSearchIndex()
        self.register_index(moderation_index)
    
    def search(self, index_name: str, query: str, filters: Dict = None,
               sort_by: str = None, limit: int = 50, offset: int = 0,
               highlight: bool = False) -> Dict[str, Any]:
        """
        Perform search query.
        
        Args:
            index_name: Name of search index
            query: Search query string
            filters: Filter criteria
            sort_by: Sort field
            limit: Result limit
            offset: Result offset
            highlight: Whether to highlight matches
            
        Returns:
            Search results dictionary
        """
        # Check cache first
        cache_key = f"search:{index_name}:{hash(query)}:{hash(str(filters))}"
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result
        
        if index_name not in self.indices:
            logger.error(f"SearchEngine: index {index_name} not found")
            return {'results': [], 'total': 0, 'error': 'Index not found'}
        
        index = self.indices[index_name]
        
        try:
            # Build search query
            search_query, search_filters = index.build_search_query(
                query, filters, sort_by, boost=True
            )
            
            # Perform database search
            results = self._perform_database_search(
                index, search_query, search_filters, sort_by, limit, offset
            )
            
            # Add highlights if requested
            if highlight:
                results = self._add_highlights(results, query)
            
            # Cache results
            cache.set(cache_key, results, self.cache_timeout)
            
            return results
            
        except Exception as exc:
            logger.error(f"SearchEngine: search error: {exc}")
            return {'results': [], 'total': 0, 'error': str(exc)}
    
    def _perform_database_search(self, index: SearchIndex, search_query: SearchQuery,
                               filters: Dict, sort_by: str, limit: int, offset: int) -> Dict[str, Any]:
        """Perform actual database search."""
        queryset = index.model_class.objects.all()
        
        # Apply search
        search_vector = index.build_search_vector()
        queryset = queryset.annotate(
            rank=SearchRank(search_vector, search_query)
        ).filter(search_vector=search_query)
        
        # Apply filters
        if filters:
            queryset = self._apply_filters(queryset, filters)
        
        # Apply sorting
        if sort_by:
            queryset = queryset.order_by(f"-{sort_by}")
        else:
            queryset = queryset.order_by('-rank')
        
        # Get total count
        total = queryset.count()
        
        # Apply pagination
        queryset = queryset[offset:offset + limit]
        
        # Convert to results
        results = []
        for instance in queryset:
            doc = index.index_document(instance)
            if hasattr(instance, 'rank'):
                doc['search_rank'] = instance.rank
            results.append(doc)
        
        return {
            'results': results,
            'total': total,
            'limit': limit,
            'offset': offset
        }
    
    def _apply_filters(self, queryset, filters: Dict) -> models.QuerySet:
        """Apply filters to queryset."""
        filter_mapping = {
            'status': 'status',
            'risk_level': 'risk_level',
            'submission_type': 'submission_type',
            'created_at': 'created_at',
            'ai_confidence': 'ai_confidence',
            'risk_score': 'risk_score',
        }
        
        for field, value in filters.items():
            if field in filter_mapping and value is not None:
                if field == 'created_at':
                    if isinstance(value, dict):
                        start_date = value.get('gte')
                        end_date = value.get('lte')
                        if start_date:
                            queryset = queryset.filter(**{f"{filter_mapping[field]}__gte": start_date})
                        if end_date:
                            queryset = queryset.filter(**{f"{filter_mapping[field]}__lte": end_date})
                elif field in ['ai_confidence', 'risk_score']:
                    if isinstance(value, dict):
                        min_val = value.get('gte')
                        max_val = value.get('lte')
                        if min_val is not None:
                            queryset = queryset.filter(**{f"{filter_mapping[field]}__gte": min_val})
                        if max_val is not None:
                            queryset = queryset.filter(**{f"{filter_mapping[field]}__lte": max_val})
                    else:
                        queryset = queryset.filter(**{filter_mapping[field]: value})
                else:
                    queryset = queryset.filter(**{filter_mapping[field]: value})
        
        return queryset
    
    def _add_highlights(self, results: List[Dict], query: str) -> List[Dict]:
        """Add search highlights to results."""
        for result in results:
            highlights = {}
            
            # Highlight text content
            if 'text_content' in result:
                highlights['text_content'] = self._highlight_text(
                    result['text_content'], query
                )
            
            # Highlight metadata
            if 'metadata' in result and isinstance(result['metadata'], dict):
                metadata_text = str(result['metadata'])
                highlights['metadata'] = self._highlight_text(metadata_text, query)
            
            result['highlights'] = highlights
        
        return results
    
    def _highlight_text(self, text: str, query: str, max_length: int = 200) -> str:
        """Simple text highlighting."""
        if not text or not query:
            return text[:max_length]
        
        # Simple highlighting - in production, use proper search highlighting
        query_lower = query.lower()
        text_lower = text.lower()
        
        if query_lower in text_lower:
            start_pos = text_lower.find(query_lower)
            if start_pos != -1:
                # Get context around match
                context_start = max(0, start_pos - 50)
                context_end = min(len(text), start_pos + len(query) + 50)
                highlighted = text[context_start:context_end]
                return f"...{highlighted}..."
        
        return text[:max_length]
    
    def suggest(self, index_name: str, query: str, field: str = None,
                limit: int = 10) -> List[str]:
        """
        Get search suggestions.
        
        Args:
            index_name: Name of search index
            query: Query string
            field: Field to search in
            limit: Number of suggestions
            
        Returns:
            List of suggestions
        """
        if index_name not in self.indices:
            return []
        
        index = self.indices[index_name]
        
        # Simple suggestion implementation
        # In production, use proper autocomplete/suggestion engine
        try:
            queryset = index.model_class.objects.all()
            
            if field and hasattr(index.model_class, field):
                # Search in specific field
                queryset = queryset.filter(**{f"{field}__icontains": query})
            else:
                # Search in all text fields
                q_objects = models.Q()
                for field_name, _ in index.search_fields:
                    if hasattr(index.model_class, field_name):
                        q_objects |= models.Q(**{f"{field_name}__icontains": query})
                
                if q_objects:
                    queryset = queryset.filter(q_objects)
            
            # Get distinct values
            if field:
                values = queryset.values_list(field, flat=True).distinct()[:limit]
                return [str(v) for v in values if v]
            else:
                # Return first few objects as suggestions
                objects = queryset[:limit]
                suggestions = []
                for obj in objects:
                    doc = index.index_document(obj)
                    # Find best matching field
                    best_match = ""
                    for field_name, _ in index.search_fields:
                        if field_name in doc:
                            value = str(doc[field_name])
                            if query.lower() in value.lower():
                                best_match = value
                                break
                    if best_match:
                        suggestions.append(best_match)
                return suggestions[:limit]
        
        except Exception as exc:
            logger.error(f"SearchEngine: suggestion error: {exc}")
        
        return []
    
    def get_search_analytics(self, index_name: str, days: int = 30) -> Dict[str, Any]:
        """
        Get search analytics.
        
        Args:
            index_name: Name of search index
            days: Number of days to analyze
            
        Returns:
            Analytics dictionary
        """
        # This would integrate with search analytics
        # For now, return mock data
        return {
            'total_searches': 0,
            'unique_queries': 0,
            'average_results': 0.0,
            'no_result_queries': 0,
            'top_queries': [],
            'search_trends': []
        }
    
    def rebuild_index(self, index_name: str) -> bool:
        """
        Rebuild search index.
        
        Args:
            index_name: Name of index to rebuild
            
        Returns:
            True if successful, False otherwise
        """
        if index_name not in self.indices:
            logger.error(f"SearchEngine: index {index_name} not found")
            return False
        
        index = self.indices[index_name]
        
        try:
            # Clear cache
            self._clear_search_cache(index_name)
            
            # Re-index all documents
            count = 0
            for instance in index.model_class.objects.all():
                doc = index.index_document(instance)
                # This would be sent to search engine
                count += 1
            
            logger.info(f"SearchEngine: rebuilt index {index_name} with {count} documents")
            return True
            
        except Exception as exc:
            logger.error(f"SearchEngine: rebuild error: {exc}")
            return False
    
    def _clear_search_cache(self, index_name: str) -> None:
        """Clear search cache for index."""
        # This would clear search engine cache
        pass


class SearchQueryBuilder:
    """
    Builder for complex search queries.
    """
    
    def __init__(self):
        self.query_parts = []
        self.filters = {}
        self.sort_fields = []
        self.boost_fields = {}
        self.facets = []
    
    def add_text_query(self, text: str, field: str = None, boost: float = 1.0) -> 'SearchQueryBuilder':
        """Add text query part."""
        if field:
            self.query_parts.append(f"{field}:{text}^{boost}")
        else:
            self.query_parts.append(f"{text}^{boost}")
        return self
    
    def add_phrase_query(self, phrase: str, field: str = None, boost: float = 1.0) -> 'SearchQueryBuilder':
        """Add phrase query part."""
        if field:
            self.query_parts.append(f"{field}:\"{phrase}\"^{boost}")
        else:
            self.query_parts.append(f"\"{phrase}\"^{boost}")
        return self
    
    def add_wildcard_query(self, pattern: str, field: str = None) -> 'SearchQueryBuilder':
        """Add wildcard query part."""
        if field:
            self.query_parts.append(f"{field}:{pattern}")
        else:
            self.query_parts.append(pattern)
        return self
    
    def add_filter(self, field: str, value: Any, operator: str = 'eq') -> 'SearchQueryBuilder':
        """Add filter condition."""
        filter_key = f"{field}__{operator}" if operator != 'eq' else field
        self.filters[filter_key] = value
        return self
    
    def add_range_filter(self, field: str, min_val: Any = None, max_val: Any = None) -> 'SearchQueryBuilder':
        """Add range filter."""
        if min_val is not None:
            self.filters[f"{field}__gte"] = min_val
        if max_val is not None:
            self.filters[f"{field}__lte"] = max_val
        return self
    
    def add_sort(self, field: str, order: str = 'desc') -> 'SearchQueryBuilder':
        """Add sort field."""
        prefix = '-' if order == 'desc' else ''
        self.sort_fields.append(f"{prefix}{field}")
        return self
    
    def add_facet(self, field: str, size: int = 10) -> 'SearchQueryBuilder':
        """Add facet field."""
        self.facets.append({'field': field, 'size': size})
        return self
    
    def build(self) -> Dict[str, Any]:
        """Build final query dictionary."""
        query = ' '.join(self.query_parts) if self.query_parts else '*'
        
        return {
            'query': query,
            'filters': self.filters,
            'sort': self.sort_fields,
            'facets': self.facets,
            'boost_fields': self.boost_fields
        }


class SearchAnalytics:
    """
    Analytics for search functionality.
    """
    
    def __init__(self):
        self.search_logs = []
        self.query_stats = {}
        self.performance_metrics = {}
    
    def log_search(self, query: str, index_name: str, results_count: int,
                   search_time: float, user_id: str = None) -> None:
        """Log a search query."""
        log_entry = {
            'query': query,
            'index_name': index_name,
            'results_count': results_count,
            'search_time': search_time,
            'user_id': user_id,
            'timestamp': timezone.now().isoformat()
        }
        
        self.search_logs.append(log_entry)
        
        # Update query stats
        if query not in self.query_stats:
            self.query_stats[query] = {
                'count': 0,
                'total_results': 0,
                'total_time': 0.0,
                'no_results_count': 0
            }
        
        stats = self.query_stats[query]
        stats['count'] += 1
        stats['total_results'] += results_count
        stats['total_time'] += search_time
        if results_count == 0:
            stats['no_results_count'] += 1
    
    def get_popular_queries(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get most popular search queries."""
        sorted_queries = sorted(
            self.query_stats.items(),
            key=lambda x: x[1]['count'],
            reverse=True
        )
        
        popular = []
        for query, stats in sorted_queries[:limit]:
            avg_results = stats['total_results'] / stats['count']
            avg_time = stats['total_time'] / stats['count']
            
            popular.append({
                'query': query,
                'count': stats['count'],
                'avg_results': avg_results,
                'avg_time': avg_time,
                'no_results_rate': stats['no_results_count'] / stats['count']
            })
        
        return popular
    
    def get_zero_result_queries(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get queries with zero results."""
        zero_result_queries = [
            (query, stats) for query, stats in self.query_stats.items()
            if stats['no_results_count'] > 0
        ]
        
        sorted_queries = sorted(
            zero_result_queries,
            key=lambda x: x[1]['no_results_count'],
            reverse=True
        )
        
        zero_results = []
        for query, stats in sorted_queries[:limit]:
            zero_results.append({
                'query': query,
                'no_results_count': stats['no_results_count'],
                'total_count': stats['count'],
                'no_results_rate': stats['no_results_count'] / stats['count']
            })
        
        return zero_results
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get search performance metrics."""
        if not self.search_logs:
            return {}
        
        total_searches = len(self.search_logs)
        total_time = sum(log['search_time'] for log in self.search_logs)
        avg_time = total_time / total_searches
        
        # Calculate percentiles
        times = [log['search_time'] for log in self.search_logs]
        times.sort()
        
        p50 = times[len(times) // 2] if times else 0
        p95 = times[int(len(times) * 0.95)] if times else 0
        p99 = times[int(len(times) * 0.99)] if times else 0
        
        return {
            'total_searches': total_searches,
            'avg_time': avg_time,
            'p50_time': p50,
            'p95_time': p95,
            'p99_time': p99,
            'slow_queries': len([t for t in times if t > 1.0])  # Queries over 1 second
        }


# Global instances
search_engine = SearchEngine()
search_analytics = SearchAnalytics()


# Search utilities
def search_submissions(query: str, filters: Dict = None, **kwargs) -> Dict[str, Any]:
    """Search suspicious submissions."""
    return search_engine.search('moderation_search', query, filters, **kwargs)


def search_decisions(query: str, filters: Dict = None, **kwargs) -> Dict[str, Any]:
    """Search moderation decisions."""
    return search_engine.search('moderation_search', query, filters, **kwargs)


def search_appeals(query: str, filters: Dict = None, **kwargs) -> Dict[str, Any]:
    """Search moderation appeals."""
    return search_engine.search('moderation_search', query, filters, **kwargs)


def get_search_suggestions(query: str, limit: int = 10) -> List[str]:
    """Get search suggestions."""
    return search_engine.suggest('moderation_search', query, limit=limit)


def build_search_query() -> SearchQueryBuilder:
    """Create a new search query builder."""
    return SearchQueryBuilder()


# Search middleware and decorators
def log_search_performance(func):
    """Decorator to log search performance."""
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        search_time = time.time() - start_time
        
        # Log to analytics
        if isinstance(result, dict) and 'results' in result:
            search_analytics.log_search(
                query=kwargs.get('query', ''),
                index_name=kwargs.get('index_name', 'unknown'),
                results_count=len(result.get('results', [])),
                search_time=search_time
            )
        
        return result
    
    return wrapper


# Auto-indexing utilities
def auto_index_submissions():
    """Auto-index all submissions."""
    return search_engine.rebuild_index('moderation_search')


# Search configuration
def configure_search(settings: Dict[str, Any]) -> None:
    """Configure search engine settings."""
    if 'max_results' in settings:
        search_engine.max_results = settings['max_results']
    
    if 'cache_timeout' in settings:
        search_engine.cache_timeout = settings['cache_timeout']
    
    logger.info("SearchEngine: configuration updated")
