"""
Security Search Module
Advanced search functionality for security data
"""

import logging
import re
from typing import Dict, List, Any, Optional, Type, Union, Tuple
from datetime import datetime, timedelta
from django.db import models
from django.db.models import Q, Count, Avg, Max, Min, Sum
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.conf import settings

from .utils import SecurityUtils
from .helpers import DataSanitizer, TimeHelper

User = get_user_model()
logger = logging.getLogger('security.search')


class SearchQuery:
    """Search query builder and parser"""
    
    def __init__(self, query_string: str = '', filters: Dict[str, Any] = None):
        self.query_string = query_string.strip() if query_string else ''
        self.filters = filters or {}
        self.terms = self._parse_query()
        self.cache_key = f"search_query_{hash(query_string)}_{hash(str(filters))}"
    
    def _parse_query(self) -> List[Dict[str, Any]]:
        """Parse search query into terms"""
        if not self.query_string:
            return []
        
        terms = []
        
        # Parse quoted phrases
        quoted_pattern = r'"([^"]*)"'
        quoted_matches = re.findall(quoted_pattern, self.query_string)
        
        # Remove quoted phrases from query
        remaining_query = re.sub(quoted_pattern, '', self.query_string)
        
        # Add quoted terms
        for phrase in quoted_matches:
            terms.append({
                'type': 'phrase',
                'value': phrase,
                'operator': 'exact'
            })
        
        # Parse field-specific searches (field:value)
        field_pattern = r'(\w+):([^\s"]+)'
        field_matches = re.findall(field_pattern, remaining_query)
        
        # Remove field searches from remaining query
        remaining_query = re.sub(field_pattern, '', remaining_query)
        
        # Add field-specific terms
        for field, value in field_matches:
            terms.append({
                'type': 'field',
                'field': field,
                'value': value,
                'operator': 'icontains'
            })
        
        # Parse remaining words
        remaining_words = remaining_query.strip().split()
        for word in remaining_words:
            if word:
                terms.append({
                    'type': 'word',
                    'value': word,
                    'operator': 'icontains'
                })
        
        return terms
    
    def build_q_object(self, searchable_fields: List[str]) -> Q:
        """Build Django Q object from search terms"""
        if not self.terms:
            return Q()
        
        q_objects = []
        
        for term in self.terms:
            if term['type'] == 'phrase':
                # Search for exact phrase in any field
                phrase_q = Q()
                for field in searchable_fields:
                    phrase_q |= Q(**{f"{field}__iexact": term['value']})
                q_objects.append(phrase_q)
                
            elif term['type'] == 'field':
                # Field-specific search
                field = term['field']
                value = term['value']
                
                # Handle range searches
                if value.startswith('>') or value.startswith('<'):
                    operator = '__gt' if value.startswith('>') else '__lt'
                    num_value = value[1:]
                    try:
                        num_value = float(num_value)
                        q_objects.append(Q(**{f"{field}{operator}": num_value}))
                    except ValueError:
                        pass
                else:
                    q_objects.append(Q(**{f"{field}__{term['operator']}": value}))
                    
            elif term['type'] == 'word':
                # Search word in any field
                word_q = Q()
                for field in searchable_fields:
                    word_q |= Q(**{f"{field}__{term['operator']}": term['value']})
                q_objects.append(word_q)
        
        # Combine all Q objects with AND
        if q_objects:
            combined_q = q_objects[0]
            for q_obj in q_objects[1:]:
                combined_q &= q_obj
            return combined_q
        
        return Q()


class SecuritySearchEngine:
    """Advanced search engine for security data"""
    
    def __init__(self, model_class: Type[models.Model], cache_timeout: int = 300):
        self.model_class = model_class
        self.cache_timeout = cache_timeout
        self.searchable_fields = self._get_searchable_fields()
        self.filterable_fields = self._get_filterable_fields()
    
    def _get_searchable_fields(self) -> List[str]:
        """Get searchable fields for the model"""
        fields = []
        
        for field in self.model_class._meta.fields:
            if field.__class__.__name__ in ['CharField', 'TextField']:
                fields.append(field.name)
        
        return fields
    
    def _get_filterable_fields(self) -> Dict[str, Type]:
        """Get filterable fields and their types"""
        fields = {}
        
        for field in self.model_class._meta.fields:
            field_type = field.__class__.__name__
            if field_type in ['CharField', 'TextField', 'IntegerField', 'FloatField',
                            'DateTimeField', 'BooleanField', 'EmailField']:
                fields[field.name] = field_type
        
        return fields
    
    def search(self, query: SearchQuery, page: int = 1, page_size: int = 20,
              sort_by: str = None, sort_order: str = 'desc') -> Dict[str, Any]:
        """Perform search with pagination and sorting"""
        cache_key = f"search_{self.model_class.__name__}_{query.cache_key}_{page}_{page_size}_{sort_by}_{sort_order}"
        
        # Try to get from cache
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result
        
        # Build base queryset
        queryset = self.model_class.objects.all()
        
        # Apply search filters
        search_q = query.build_q_object(self.searchable_fields)
        if search_q:
            queryset = queryset.filter(search_q)
        
        # Apply additional filters
        queryset = self._apply_filters(queryset, query.filters)
        
        # Apply sorting
        queryset = self._apply_sorting(queryset, sort_by, sort_order)
        
        # Apply pagination
        total_count = queryset.count()
        offset = (page - 1) * page_size
        items = list(queryset[offset:offset + page_size])
        
        result = {
            'items': items,
            'total_count': total_count,
            'page': page,
            'page_size': page_size,
            'total_pages': (total_count + page_size - 1) // page_size,
            'has_next': offset + page_size < total_count,
            'has_previous': page > 1,
            'query': query.query_string,
            'filters': query.filters,
            'sort_by': sort_by,
            'sort_order': sort_order
        }
        
        # Cache result
        cache.set(cache_key, result, self.cache_timeout)
        
        return result
    
    def _apply_filters(self, queryset: models.QuerySet, filters: Dict[str, Any]) -> models.QuerySet:
        """Apply additional filters to queryset"""
        if not filters:
            return queryset
        
        for field, value in filters.items():
            if field not in self.filterable_fields:
                continue
            
            field_type = self.filterable_fields[field]
            
            if field_type in ['CharField', 'TextField', 'EmailField']:
                if isinstance(value, list):
                    queryset = queryset.filter(**{f"{field}__in": value})
                else:
                    queryset = queryset.filter(**{field: value})
                    
            elif field_type in ['IntegerField', 'FloatField']:
                if isinstance(value, dict):
                    # Range filter
                    if 'min' in value:
                        queryset = queryset.filter(**{f"{field}__gte": value['min']})
                    if 'max' in value:
                        queryset = queryset.filter(**{f"{field}__lte": value['max']})
                elif isinstance(value, list):
                    queryset = queryset.filter(**{f"{field}__in": value})
                else:
                    queryset = queryset.filter(**{field: value})
                    
            elif field_type == 'DateTimeField':
                if isinstance(value, dict):
                    # Date range filter
                    if 'start' in value:
                        queryset = queryset.filter(**{f"{field}__gte": value['start']})
                    if 'end' in value:
                        queryset = queryset.filter(**{f"{field}__lte": value['end']})
                else:
                    queryset = queryset.filter(**{field: value})
                    
            elif field_type == 'BooleanField':
                queryset = queryset.filter(**{field: bool(value)})
        
        return queryset
    
    def _apply_sorting(self, queryset: models.QuerySet, sort_by: str, sort_order: str) -> models.QuerySet:
        """Apply sorting to queryset"""
        if not sort_by or sort_by not in self.filterable_fields:
            # Default sorting
            if hasattr(self.model_class, 'created_at'):
                sort_field = 'created_at'
            else:
                sort_field = 'id'
        else:
            sort_field = sort_by
        
        order_prefix = '-' if sort_order == 'desc' else ''
        return queryset.order_by(f"{order_prefix}{sort_field}")
    
    def get_search_suggestions(self, partial_query: str, limit: int = 10) -> List[str]:
        """Get search suggestions based on partial query"""
        if not partial_query or len(partial_query) < 2:
            return []
        
        cache_key = f"suggestions_{self.model_class.__name__}_{hash(partial_query)}"
        cached_suggestions = cache.get(cache_key)
        
        if cached_suggestions:
            return cached_suggestions
        
        suggestions = []
        
        # Get suggestions from searchable fields
        for field in self.searchable_fields:
            try:
                # Use distinct values from the field
                values = self.model_class.objects.filter(
                    **{f"{field}__icontains": partial_query}
                ).values_list(field, flat=True).distinct()[:limit]
                
                for value in values:
                    if value and isinstance(value, str):
                        if partial_query.lower() in value.lower():
                            suggestions.append(value)
            except Exception:
                pass
        
        # Limit and deduplicate
        suggestions = list(set(suggestions))[:limit]
        
        # Cache suggestions
        cache.set(cache_key, suggestions, self.cache_timeout)
        
        return suggestions
    
    def get_faceted_search(self, query: SearchQuery, facet_fields: List[str] = None) -> Dict[str, Any]:
        """Get faceted search results"""
        if not facet_fields:
            facet_fields = ['status', 'severity', 'created_at']
        
        # Get base search results
        search_results = self.search(query, page=1, page_size=0)  # No pagination needed
        
        # Build base queryset
        queryset = self.model_class.objects.all()
        search_q = query.build_q_object(self.searchable_fields)
        if search_q:
            queryset = queryset.filter(search_q)
        
        # Apply filters
        queryset = self._apply_filters(queryset, query.filters)
        
        facets = {}
        
        for field in facet_fields:
            if field not in self.filterable_fields:
                continue
            
            field_type = self.filterable_fields[field]
            
            if field_type in ['CharField', 'TextField', 'EmailField', 'BooleanField']:
                # Count by field values
                facet_data = queryset.values(field).annotate(count=Count('id')).order_by('-count')
                facets[field] = list(facet_data)
                
            elif field_type == 'DateTimeField':
                # Date range facets
                date_ranges = {
                    'last_hour': timezone.now() - timedelta(hours=1),
                    'last_24h': timezone.now() - timedelta(hours=24),
                    'last_7d': timezone.now() - timedelta(days=7),
                    'last_30d': timezone.now() - timedelta(days=30),
                    'last_90d': timezone.now() - timedelta(days=90),
                }
                
                date_facets = {}
                for range_name, start_date in date_ranges.items():
                    count = queryset.filter(**{f"{field}__gte": start_date}).count()
                    date_facets[range_name] = count
                
                facets[field] = date_facets
        
        return {
            'facets': facets,
            'total_count': search_results['total_count']
        }


class AdvancedSearchEngine(SecuritySearchEngine):
    """Advanced search engine with additional features"""
    
    def __init__(self, model_class: Type[models.Model], cache_timeout: int = 300):
        super().__init__(model_class, cache_timeout)
        self.indexed_fields = self._get_indexed_fields()
    
    def _get_indexed_fields(self) -> List[str]:
        """Get fields that should be indexed for search"""
        # This would typically be configured based on database indexes
        return self.searchable_fields
    
    def fuzzy_search(self, query: SearchQuery, fuzzy_threshold: float = 0.8) -> Dict[str, Any]:
        """Perform fuzzy search"""
        # This is a simplified implementation
        # In production, you might use Elasticsearch or another search engine
        
        # For now, fall back to regular search
        return self.search(query)
    
    def boolean_search(self, query_string: str) -> Dict[str, Any]:
        """Perform boolean search with AND, OR, NOT operators"""
        # Parse boolean query
        boolean_terms = self._parse_boolean_query(query_string)
        
        # Build complex Q object
        q_object = self._build_boolean_q_object(boolean_terms)
        
        # Apply to queryset
        queryset = self.model_class.objects.filter(q_object)
        
        return {
            'items': list(queryset),
            'total_count': queryset.count(),
            'query_type': 'boolean'
        }
    
    def _parse_boolean_query(self, query_string: str) -> List[Dict[str, Any]]:
        """Parse boolean search query"""
        terms = []
        
        # Simple boolean parsing (would be more sophisticated in production)
        # Split on AND, OR, NOT
        operators = ['AND', 'OR', 'NOT']
        
        # This is a very basic implementation
        # A full implementation would handle parentheses and precedence
        parts = re.split(r'\s+(AND|OR|NOT)\s+', query_string, flags=re.IGNORECASE)
        
        i = 0
        while i < len(parts):
            part = parts[i].strip()
            
            if part.upper() in operators:
                # Operator
                if i == 0:
                    # Can't start with operator, skip
                    i += 1
                    continue
                
                # Add operator to previous term
                if terms:
                    terms[-1]['operator'] = part.upper()
                i += 1
            else:
                # Term
                terms.append({
                    'value': part,
                    'operator': 'AND'  # Default operator
                })
                i += 1
        
        return terms
    
    def _build_boolean_q_object(self, boolean_terms: List[Dict[str, Any]]) -> Q:
        """Build Q object from boolean terms"""
        if not boolean_terms:
            return Q()
        
        q_objects = []
        
        for i, term in enumerate(boolean_terms):
            if term['operator'] == 'NOT':
                # NOT operator - invert the term
                term_q = self._build_term_q_object(term['value'])
                q_objects.append(~term_q)
            else:
                # AND or OR operator
                term_q = self._build_term_q_object(term['value'])
                
                if term['operator'] == 'OR':
                    # OR - add to list (will be combined later)
                    q_objects.append(term_q)
                else:
                    # AND - combine with previous if exists
                    if q_objects:
                        q_objects[-1] &= term_q
                    else:
                        q_objects.append(term_q)
        
        # Combine all OR conditions
        if len(q_objects) > 1:
            final_q = q_objects[0]
            for q_obj in q_objects[1:]:
                final_q |= q_obj
            return final_q
        elif q_objects:
            return q_objects[0]
        
        return Q()
    
    def _build_term_q_object(self, term: str) -> Q:
        """Build Q object for a single term"""
        term_q = Q()
        
        for field in self.searchable_fields:
            term_q |= Q(**{f"{field}__icontains": term})
        
        return term_q
    
    def proximity_search(self, terms: List[str], proximity: int = 10) -> Dict[str, Any]:
        """Perform proximity search (words within certain distance)"""
        # This is a simplified implementation
        # Real proximity search would require full-text search capabilities
        
        combined_query = ' '.join(terms)
        query = SearchQuery(combined_query)
        
        return self.search(query)
    
    def wildcard_search(self, pattern: str) -> Dict[str, Any]:
        """Perform wildcard search"""
        # Convert wildcard pattern to regex
        regex_pattern = pattern.replace('*', '.*').replace('?', '.')
        
        # Search using regex (if supported)
        try:
            q_objects = []
            for field in self.searchable_fields:
                q_objects.append(Q(**{f"{field}__regex": regex_pattern}))
            
            if q_objects:
                combined_q = q_objects[0]
                for q_obj in q_objects[1:]:
                    combined_q |= q_obj
                
                queryset = self.model_class.objects.filter(combined_q)
                
                return {
                    'items': list(queryset),
                    'total_count': queryset.count(),
                    'query_type': 'wildcard'
                }
        except Exception:
            pass
        
        # Fallback to regular search
        query = SearchQuery(pattern.replace('*', '').replace('?', ''))
        return self.search(query)


class SearchIndexManager:
    """Manager for search indexes and optimization"""
    
    def __init__(self):
        self.indexes = {}
        self.cache_timeout = 3600  # 1 hour
    
    def create_index(self, model_class: Type[models.Model], fields: List[str]) -> bool:
        """Create search index for model"""
        try:
            index_name = f"{model_class.__name__}_search_index"
            
            # In a real implementation, this would create actual search indexes
            # For now, we just store the configuration
            self.indexes[index_name] = {
                'model': model_class,
                'fields': fields,
                'created_at': timezone.now()
            }
            
            logger.info(f"Created search index: {index_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create search index: {e}")
            return False
    
    def rebuild_index(self, model_class: Type[models.Model]) -> bool:
        """Rebuild search index for model"""
        try:
            index_name = f"{model_class.__name__}_search_index"
            
            if index_name in self.indexes:
                # In a real implementation, this would rebuild the index
                logger.info(f"Rebuilt search index: {index_name}")
                return True
            else:
                logger.warning(f"Index not found: {index_name}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to rebuild search index: {e}")
            return False
    
    def get_index_stats(self) -> Dict[str, Any]:
        """Get search index statistics"""
        stats = {
            'total_indexes': len(self.indexes),
            'indexes': {}
        }
        
        for name, index_info in self.indexes.items():
            model_class = index_info['model']
            
            try:
                stats['indexes'][name] = {
                    'model': model_class.__name__,
                    'fields': index_info['fields'],
                    'record_count': model_class.objects.count(),
                    'created_at': index_info['created_at'].isoformat()
                }
            except Exception:
                stats['indexes'][name] = {
                    'model': model_class.__name__,
                    'fields': index_info['fields'],
                    'record_count': 0,
                    'error': 'Failed to get count'
                }
        
        return stats


# Global search index manager
search_index_manager = SearchIndexManager()


class SearchAnalytics:
    """Analytics for search operations"""
    
    def __init__(self):
        self.cache_timeout = 300  # 5 minutes
    
    def log_search(self, user: User, query: str, results_count: int, 
                   search_time: float, model_name: str):
        """Log search operation for analytics"""
        try:
            from .models import SecurityLog
            
            SecurityLog.objects.create(
                user=user,
                security_type='search_operation',
                severity='info',
                description=f'Search performed on {model_name}',
                metadata={
                    'query': query,
                    'results_count': results_count,
                    'search_time_ms': search_time * 1000,
                    'model': model_name
                }
            )
        except Exception as e:
            logger.error(f"Failed to log search analytics: {e}")
    
    def get_popular_searches(self, model_name: str = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Get popular search queries"""
        try:
            from .models import SecurityLog
            
            queryset = SecurityLog.objects.filter(security_type='search_operation')
            
            if model_name:
                queryset = queryset.filter(metadata__model=model_name)
            
            # Group by query and count
            popular_searches = (
                queryset.values('metadata__query')
                .annotate(count=Count('id'), avg_results=Avg('metadata__results_count'))
                .order_by('-count')[:limit]
            )
            
            return list(popular_searches)
            
        except Exception as e:
            logger.error(f"Failed to get popular searches: {e}")
            return []
    
    def get_search_stats(self, model_name: str = None, days: int = 7) -> Dict[str, Any]:
        """Get search statistics"""
        try:
            from .models import SecurityLog
            
            start_date = timezone.now() - timedelta(days=days)
            
            queryset = SecurityLog.objects.filter(
                security_type='search_operation',
                created_at__gte=start_date
            )
            
            if model_name:
                queryset = queryset.filter(metadata__model=model_name)
            
            total_searches = queryset.count()
            unique_queries = queryset.values('metadata__query').distinct().count()
            avg_results = queryset.aggregate(avg=Avg('metadata__results_count'))['avg'] or 0
            avg_search_time = queryset.aggregate(avg=Avg('metadata__search_time_ms'))['avg'] or 0
            
            # Daily breakdown
            daily_stats = (
                queryset.extra(select={'day': 'date(created_at)'})
                .values('day')
                .annotate(count=Count('id'))
                .order_by('day')
            )
            
            return {
                'total_searches': total_searches,
                'unique_queries': unique_queries,
                'avg_results': avg_results,
                'avg_search_time_ms': avg_search_time,
                'daily_breakdown': list(daily_stats),
                'period_days': days
            }
            
        except Exception as e:
            logger.error(f"Failed to get search stats: {e}")
            return {}


# Global search analytics
search_analytics = SearchAnalytics()


# Export classes and utilities
__all__ = [
    'SearchQuery',
    'SecuritySearchEngine',
    'AdvancedSearchEngine',
    'SearchIndexManager',
    'search_index_manager',
    'SearchAnalytics',
    'search_analytics'
]