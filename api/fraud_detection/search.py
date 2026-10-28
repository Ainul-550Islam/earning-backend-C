# =============================================================================
# fraud_detection/search.py
# =============================================================================
"""
Search Functionality for Fraud Detection System.

Provides comprehensive search capabilities for fraud detection data
with advanced filtering, indexing, and performance optimization.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union, Type, Tuple
from dataclasses import dataclass
from enum import Enum

from django.db import models
from django.db.models import Q, Count, Sum, Avg
from django.utils import timezone
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
from django.core.cache import cache
from rest_framework.request import Request

from api.fraud_detection.models import (
    FraudCase, FraudAlert, FraudRule, FraudRiskProfile,
    DeviceFingerprint, FraudSuspiciousIP
)
from api.fraud_detection.querysets import (
    FraudCaseQuerySet, FraudAlertQuerySet, FraudRuleQuerySet
)
from api.fraud_detection.exceptions import SearchError
from api.fraud_detection.helpers import (
    parse_datetime_string, get_time_range, sanitize_string
)


logger = logging.getLogger(__name__)


class SearchType(Enum):
    """Search types for different search operations."""
    FULL_TEXT = "full_text"
    FIELD = "field"
    RANGE = "range"
    BOOLEAN = "boolean"
    FUZZY = "fuzzy"
    WILDCARD = "wildcard"


class SearchOperator(Enum):
    """Search operators for combining conditions."""
    AND = "and"
    OR = "or"
    NOT = "not"


@dataclass
class SearchCriteria:
    """Search criteria definition."""
    field: str
    value: Any
    operator: SearchOperator = SearchOperator.AND
    search_type: SearchType = SearchType.FIELD
    case_sensitive: bool = False
    exact_match: bool = False
    
    def __post_init__(self):
        if isinstance(self.value, str) and not self.case_sensitive:
            self.value = self.value.lower()


@dataclass
class SearchOptions:
    """Search options and configuration."""
    page: int = 1
    page_size: int = 20
    sort_by: Optional[str] = None
    sort_order: str = "desc"
    include_metadata: bool = True
    cache_results: bool = True
    cache_timeout: int = 300
    highlight_results: bool = False


@dataclass
class SearchResult:
    """Search result with metadata."""
    items: List[Dict[str, Any]]
    total_count: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_previous: bool
    search_time: float
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class BaseSearchEngine:
    """Base search engine for fraud detection data."""
    
    def __init__(self):
        """Initialize search engine."""
        self.model_class = None
        self.searchable_fields = []
        self.default_sort_field = 'created_at'
        self.cache_prefix = 'fraud_search'
    
    def search(self, criteria: List[SearchCriteria], options: SearchOptions) -> SearchResult:
        """
        Perform search with given criteria and options.
        
        Args:
            criteria: List of search criteria
            options: Search options
            
        Returns:
            Search result
        """
        if not self.model_class:
            raise SearchError("Model class not set")
        
        start_time = timezone.now()
        
        try:
            # Check cache first
            if options.cache_results:
                cache_key = self._generate_cache_key(criteria, options)
                cached_result = cache.get(cache_key)
                if cached_result:
                    return cached_result
            
            # Build query
            queryset = self._build_search_query(criteria, options)
            
            # Apply sorting
            if options.sort_by:
                queryset = self._apply_sorting(queryset, options.sort_by, options.sort_order)
            
            # Count total results
            total_count = queryset.count()
            
            # Apply pagination
            offset = (options.page - 1) * options.page_size
            items = list(queryset[offset:offset + options.page_size])
            
            # Format results
            formatted_items = self._format_results(items, options)
            
            # Calculate pagination info
            total_pages = (total_count + options.page_size - 1) // options.page_size
            has_next = options.page < total_pages
            has_previous = options.page > 1
            
            search_time = (timezone.now() - start_time).total_seconds()
            
            # Create result
            result = SearchResult(
                items=formatted_items,
                total_count=total_count,
                page=options.page,
                page_size=options.page_size,
                total_pages=total_pages,
                has_next=has_next,
                has_previous=has_previous,
                search_time=search_time,
                metadata=self._get_search_metadata(criteria, options)
            )
            
            # Cache result
            if options.cache_results:
                cache.set(cache_key, result, options.cache_timeout)
            
            return result
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise SearchError(f"Search failed: {e}")
    
    def _build_search_query(self, criteria: List[SearchCriteria], options: SearchOptions) -> models.QuerySet:
        """Build search query from criteria."""
        queryset = self.model_class.objects.all()
        
        if not criteria:
            return queryset
        
        combined_query = Q()
        
        for criterion in criteria:
            query = self._build_criterion_query(criterion)
            
            if criterion.operator == SearchOperator.AND:
                combined_query &= query
            elif criterion.operator == SearchOperator.OR:
                combined_query |= query
            elif criterion.operator == SearchOperator.NOT:
                combined_query &= ~query
        
        return queryset.filter(combined_query)
    
    def _build_criterion_query(self, criterion: SearchCriteria) -> Q:
        """Build query for individual criterion."""
        field_name = criterion.field
        value = criterion.value
        
        if criterion.search_type == SearchType.FULL_TEXT:
            return self._build_full_text_query(field_name, value, criterion)
        elif criterion.search_type == SearchType.FIELD:
            return self._build_field_query(field_name, value, criterion)
        elif criterion.search_type == SearchType.RANGE:
            return self._build_range_query(field_name, value, criterion)
        elif criterion.search_type == SearchType.BOOLEAN:
            return self._build_boolean_query(field_name, value, criterion)
        elif criterion.search_type == SearchType.FUZZY:
            return self._build_fuzzy_query(field_name, value, criterion)
        elif criterion.search_type == SearchType.WILDCARD:
            return self._build_wildcard_query(field_name, value, criterion)
        else:
            raise SearchError(f"Unsupported search type: {criterion.search_type}")
    
    def _build_full_text_query(self, field: str, value: str, criterion: SearchCriteria) -> Q:
        """Build full-text search query."""
        if not hasattr(self.model_class, field):
            raise SearchError(f"Field {field} not found in model")
        
        vector = SearchVector(field)
        query = SearchQuery(value)
        rank = SearchRank(vector, query)
        
        return Q(**{f"{field}__search": query})
    
    def _build_field_query(self, field: str, value: Any, criterion: SearchCriteria) -> Q:
        """Build field search query."""
        if not hasattr(self.model_class, field):
            raise SearchError(f"Field {field} not found in model")
        
        if criterion.exact_match:
            return Q(**{field: value})
        else:
            if isinstance(value, str):
                if criterion.case_sensitive:
                    return Q(**{f"{field}__icontains": value})
                else:
                    return Q(**{f"{field}__icontains": value})
            else:
                return Q(**{field: value})
    
    def _build_range_query(self, field: str, value: Union[Dict, Tuple], criterion: SearchCriteria) -> Q:
        """Build range search query."""
        if not hasattr(self.model_class, field):
            raise SearchError(f"Field {field} not found in model")
        
        if isinstance(value, dict):
            min_val = value.get('min')
            max_val = value.get('max')
            
            query = Q()
            if min_val is not None:
                query &= Q(**{f"{field}__gte": min_val})
            if max_val is not None:
                query &= Q(**{f"{field}__lte": max_val})
            
            return query
        elif isinstance(value, (list, tuple)) and len(value) == 2:
            return Q(**{f"{field}__range": value})
        else:
            raise SearchError("Range query requires dict or tuple with min/max values")
    
    def _build_boolean_query(self, field: str, value: bool, criterion: SearchCriteria) -> Q:
        """Build boolean search query."""
        if not hasattr(self.model_class, field):
            raise SearchError(f"Field {field} not found in model")
        
        return Q(**{field: value})
    
    def _build_fuzzy_query(self, field: str, value: str, criterion: SearchCriteria) -> Q:
        """Build fuzzy search query."""
        if not hasattr(self.model_class, field):
            raise SearchError(f"Field {field} not found in model")
        
        # Simple fuzzy implementation using contains
        # In production, you might use more sophisticated fuzzy matching
        return Q(**{f"{field}__icontains": value})
    
    def _build_wildcard_query(self, field: str, value: str, criterion: SearchCriteria) -> Q:
        """Build wildcard search query."""
        if not hasattr(self.model_class, field):
            raise SearchError(f"Field {field} not found in model")
        
        # Convert SQL wildcards to Django lookups
        if '%' in value:
            django_value = value.replace('%', '')
            return Q(**{f"{field}__icontains": django_value})
        else:
            return Q(**{f"{field}__icontains": value})
    
    def _apply_sorting(self, queryset: models.QuerySet, sort_by: str, sort_order: str) -> models.QuerySet:
        """Apply sorting to queryset."""
        if sort_by not in self.searchable_fields:
            sort_by = self.default_sort_field
        
        order_prefix = '-' if sort_order == 'desc' else ''
        return queryset.order_by(f"{order_prefix}{sort_by}")
    
    def _format_results(self, items: List[Any], options: SearchOptions) -> List[Dict[str, Any]]:
        """Format search results."""
        formatted_items = []
        
        for item in items:
            item_data = {
                'id': item.pk,
                'type': self.model_class.__name__.lower()
            }
            
            # Add model fields
            for field in self.searchable_fields:
                if hasattr(item, field):
                    value = getattr(item, field)
                    
                    # Handle datetime fields
                    if isinstance(value, datetime):
                        value = value.isoformat()
                    # Handle decimal fields
                    elif isinstance(value, (int, float)) and field.endswith('_amount'):
                        value = float(value)
                    
                    item_data[field] = value
            
            # Add highlighting if requested
            if options.highlight_results:
                item_data['highlight'] = self._add_highlighting(item)
            
            formatted_items.append(item_data)
        
        return formatted_items
    
    def _add_highlighting(self, item: Any) -> Dict[str, str]:
        """Add search highlighting to item."""
        # Simple highlighting implementation
        return {}
    
    def _get_search_metadata(self, criteria: List[SearchCriteria], options: SearchOptions) -> Dict[str, Any]:
        """Get search metadata."""
        return {
            'criteria_count': len(criteria),
            'searchable_fields': self.searchable_fields,
            'model': self.model_class.__name__,
            'cache_enabled': options.cache_results,
            'cache_timeout': options.cache_timeout
        }
    
    def _generate_cache_key(self, criteria: List[SearchCriteria], options: SearchOptions) -> str:
        """Generate cache key for search."""
        import hashlib
        
        # Build cache key components
        components = [
            self.model_class.__name__,
            str(options.page),
            str(options.page_size),
            options.sort_by or '',
            options.sort_order
        ]
        
        # Add criteria
        for criterion in criteria:
            components.append(f"{criterion.field}:{criterion.value}:{criterion.search_type.value}")
        
        cache_string = '|'.join(components)
        return f"{self.cache_prefix}:{hashlib.md5(cache_string.encode()).hexdigest()}"


class FraudCaseSearchEngine(BaseSearchEngine):
    """Search engine for fraud cases."""
    
    def __init__(self):
        """Initialize fraud case search engine."""
        super().__init__()
        self.model_class = FraudCase
        self.searchable_fields = [
            'title', 'description', 'case_type', 'severity', 'status',
            'risk_score', 'user_id', 'detection_method', 'created_at',
            'updated_at', 'financial_impact', 'regulatory_impact'
        ]
        self.default_sort_field = 'created_at'
    
    def search_by_risk_level(self, risk_level: str, options: SearchOptions) -> SearchResult:
        """Search cases by risk level."""
        criteria = [
            SearchCriteria('risk_score', self._get_risk_score_range(risk_level), SearchType.RANGE)
        ]
        return self.search(criteria, options)
    
    def search_by_date_range(self, start_date: str, end_date: str, options: SearchOptions) -> SearchResult:
        """Search cases by date range."""
        start_dt = parse_datetime_string(start_date)
        end_dt = parse_datetime_string(end_date)
        
        if not start_dt or not end_dt:
            raise SearchError("Invalid date format")
        
        criteria = [
            SearchCriteria('created_at', (start_dt, end_dt), SearchType.RANGE)
        ]
        return self.search(criteria, options)
    
    def search_by_financial_impact(self, min_amount: float, max_amount: Optional[float], options: SearchOptions) -> SearchResult:
        """Search cases by financial impact range."""
        range_value = {'min': min_amount}
        if max_amount is not None:
            range_value['max'] = max_amount
        
        criteria = [
            SearchCriteria('financial_impact', range_value, SearchType.RANGE)
        ]
        return self.search(criteria, options)
    
    def search_regulatory_cases(self, options: SearchOptions) -> SearchResult:
        """Search cases with regulatory impact."""
        criteria = [
            SearchCriteria('regulatory_impact', True, SearchType.BOOLEAN)
        ]
        return self.search(criteria, options)
    
    def _get_risk_score_range(self, risk_level: str) -> Dict[str, int]:
        """Get risk score range for risk level."""
        risk_ranges = {
            'very_low': {'min': 0, 'max': 19},
            'low': {'min': 20, 'max': 39},
            'medium': {'min': 40, 'max': 59},
            'high': {'min': 60, 'max': 79},
            'very_high': {'min': 80, 'max': 89},
            'critical': {'min': 90, 'max': 100}
        }
        
        return risk_ranges.get(risk_level, {'min': 0, 'max': 100})


class FraudAlertSearchEngine(BaseSearchEngine):
    """Search engine for fraud alerts."""
    
    def __init__(self):
        """Initialize fraud alert search engine."""
        super().__init__()
        self.model_class = FraudAlert
        self.searchable_fields = [
            'title', 'description', 'alert_type', 'severity_score',
            'user_id', 'acknowledged', 'resolved', 'created_at',
            'acknowledged_at', 'resolved_at'
        ]
        self.default_sort_field = 'created_at'
    
    def search_by_severity_range(self, min_score: int, max_score: Optional[int], options: SearchOptions) -> SearchResult:
        """Search alerts by severity score range."""
        range_value = {'min': min_score}
        if max_score is not None:
            range_value['max'] = max_score
        
        criteria = [
            SearchCriteria('severity_score', range_value, SearchType.RANGE)
        ]
        return self.search(criteria, options)
    
    def search_unacknowledged(self, options: SearchOptions) -> SearchResult:
        """Search unacknowledged alerts."""
        criteria = [
            SearchCriteria('acknowledged', False, SearchType.BOOLEAN)
        ]
        return self.search(criteria, options)
    
    def search_by_alert_type(self, alert_type: str, options: SearchOptions) -> SearchResult:
        """Search alerts by type."""
        criteria = [
            SearchCriteria('alert_type', alert_type, SearchType.FIELD)
        ]
        return self.search(criteria, options)


class FraudRuleSearchEngine(BaseSearchEngine):
    """Search engine for fraud rules."""
    
    def __init__(self):
        """Initialize fraud rule search engine."""
        super().__init__()
        self.model_class = FraudRule
        self.searchable_fields = [
            'name', 'description', 'rule_type', 'enabled', 'priority',
            'risk_score_impact', 'confidence_score', 'created_at',
            'updated_at'
        ]
        self.default_sort_field = 'priority'
    
    def search_enabled_rules(self, options: SearchOptions) -> SearchResult:
        """Search enabled rules."""
        criteria = [
            SearchCriteria('enabled', True, SearchType.BOOLEAN)
        ]
        return self.search(criteria, options)
    
    def search_by_priority_range(self, min_priority: int, max_priority: Optional[int], options: SearchOptions) -> SearchResult:
        """Search rules by priority range."""
        range_value = {'min': min_priority}
        if max_priority is not None:
            range_value['max'] = max_priority
        
        criteria = [
            SearchCriteria('priority', range_value, SearchType.RANGE)
        ]
        return self.search(criteria, options)
    
    def search_by_rule_type(self, rule_type: str, options: SearchOptions) -> SearchResult:
        """Search rules by type."""
        criteria = [
            SearchCriteria('rule_type', rule_type, SearchType.FIELD)
        ]
        return self.search(criteria, options)


class AdvancedSearchEngine:
    """Advanced search engine with multi-model capabilities."""
    
    def __init__(self):
        """Initialize advanced search engine."""
        self.engines = {
            'cases': FraudCaseSearchEngine(),
            'alerts': FraudAlertSearchEngine(),
            'rules': FraudRuleSearchEngine()
        }
    
    def search_all(self, criteria: List[SearchCriteria], options: SearchOptions) -> Dict[str, SearchResult]:
        """
        Search across all models.
        
        Args:
            criteria: List of search criteria
            options: Search options
            
        Returns:
            Dictionary of model names to search results
        """
        results = {}
        
        for model_name, engine in self.engines.items():
            try:
                # Filter criteria for this model
                filtered_criteria = self._filter_criteria_for_model(criteria, model_name)
                
                if filtered_criteria:
                    results[model_name] = engine.search(filtered_criteria, options)
                else:
                    # No applicable criteria, return empty result
                    results[model_name] = SearchResult(
                        items=[],
                        total_count=0,
                        page=options.page,
                        page_size=options.page_size,
                        total_pages=0,
                        has_next=False,
                        has_previous=False,
                        search_time=0.0
                    )
                    
            except Exception as e:
                logger.error(f"Search failed for {model_name}: {e}")
                results[model_name] = SearchResult(
                    items=[],
                    total_count=0,
                    page=options.page,
                    page_size=options.page_size,
                    total_pages=0,
                    has_next=False,
                    has_previous=False,
                    search_time=0.0,
                    metadata={'error': str(e)}
                )
        
        return results
    
    def search_by_text(self, text: str, options: SearchOptions, models: Optional[List[str]] = None) -> Dict[str, SearchResult]:
        """
        Search by text across specified models.
        
        Args:
            text: Search text
            models: List of models to search (all if None)
            options: Search options
            
        Returns:
            Dictionary of model names to search results
        """
        if models is None:
            models = list(self.engines.keys())
        
        # Create text search criteria
        criteria = []
        
        for model in models:
            engine = self.engines.get(model)
            if engine:
                # Add text search criteria for common fields
                if model == 'cases':
                    criteria.extend([
                        SearchCriteria('title', text, SearchType.FULL_TEXT),
                        SearchCriteria('description', text, SearchType.FULL_TEXT)
                    ])
                elif model == 'alerts':
                    criteria.extend([
                        SearchCriteria('title', text, SearchType.FULL_TEXT),
                        SearchCriteria('description', text, SearchType.FULL_TEXT)
                    ])
                elif model == 'rules':
                    criteria.extend([
                        SearchCriteria('name', text, SearchType.FULL_TEXT),
                        SearchCriteria('description', text, SearchType.FULL_TEXT)
                    ])
        
        return self.search_all(criteria, options)
    
    def _filter_criteria_for_model(self, criteria: List[SearchCriteria], model_name: str) -> List[SearchCriteria]:
        """Filter criteria applicable to specific model."""
        engine = self.engines.get(model_name)
        if not engine:
            return []
        
        filtered_criteria = []
        
        for criterion in criteria:
            if criterion.field in engine.searchable_fields:
                filtered_criteria.append(criterion)
        
        return filtered_criteria


# Search utilities
def parse_search_query(query: str) -> List[SearchCriteria]:
    """
    Parse search query string into criteria.
    
    Args:
        query: Search query string
        
    Returns:
        List of search criteria
    """
    criteria = []
    
    if not query:
        return criteria
    
    # Simple query parsing - can be enhanced
    # Format: field:value OR field:"value with spaces"
    pattern = r'(\w+):(?:"([^"]+)"|([^\s]+))'
    matches = re.findall(pattern, query)
    
    for field, quoted_value, unquoted_value in matches:
        value = quoted_value if quoted_value else unquoted_value
        
        # Determine search type
        search_type = SearchType.FIELD
        if value.startswith('*') and value.endswith('*'):
            search_type = SearchType.WILDCARD
            value = value[1:-1]
        elif '%' in value:
            search_type = SearchType.WILDCARD
        
        criteria.append(SearchCriteria(
            field=field,
            value=value,
            search_type=search_type
        ))
    
    return criteria


def build_search_criteria_from_request(request: Request) -> List[SearchCriteria]:
    """
    Build search criteria from HTTP request.
    
    Args:
        request: HTTP request
        
    Returns:
        List of search criteria
    """
    criteria = []
    
    # Extract query parameters
    query = request.query_params.get('q', '')
    if query:
        criteria.extend(parse_search_query(query))
    
    # Extract specific filters
    filters = {
        'status': request.query_params.get('status'),
        'severity': request.query_params.get('severity'),
        'user_id': request.query_params.get('user_id'),
        'risk_score_min': request.query_params.get('risk_score_min'),
        'risk_score_max': request.query_params.get('risk_score_max'),
        'created_after': request.query_params.get('created_after'),
        'created_before': request.query_params.get('created_before'),
        'alert_type': request.query_params.get('alert_type'),
        'acknowledged': request.query_params.get('acknowledged'),
        'enabled': request.query_params.get('enabled')
    }
    
    # Build criteria from filters
    for field, value in filters.items():
        if value is not None:
            if field in ['acknowledged', 'enabled', 'regulatory_impact']:
                # Boolean fields
                bool_value = value.lower() in ['true', '1', 'yes']
                criteria.append(SearchCriteria(field, bool_value, SearchType.BOOLEAN))
            elif field in ['risk_score_min', 'risk_score_max']:
                # Range fields
                if field == 'risk_score_min':
                    existing = next((c for c in criteria if c.field == 'risk_score'), None)
                    if existing:
                        existing.value['min'] = int(value)
                    else:
                        criteria.append(SearchCriteria('risk_score', {'min': int(value)}, SearchType.RANGE))
                else:
                    existing = next((c for c in criteria if c.field == 'risk_score'), None)
                    if existing:
                        existing.value['max'] = int(value)
                    else:
                        criteria.append(SearchCriteria('risk_score', {'max': int(value)}, SearchType.RANGE))
            elif field in ['created_after', 'created_before']:
                # Date fields
                datetime_value = parse_datetime_string(value)
                if datetime_value:
                    if field == 'created_after':
                        existing = next((c for c in criteria if c.field == 'created_at'), None)
                        if existing:
                            if isinstance(existing.value, dict):
                                existing.value['min'] = datetime_value
                            else:
                                existing.value = {'min': datetime_value}
                        else:
                            criteria.append(SearchCriteria('created_at', {'min': datetime_value}, SearchType.RANGE))
                    else:
                        existing = next((c for c in criteria if c.field == 'created_at'), None)
                        if existing:
                            if isinstance(existing.value, dict):
                                existing.value['max'] = datetime_value
                            else:
                                existing.value = {'max': datetime_value}
                        else:
                            criteria.append(SearchCriteria('created_at', {'max': datetime_value}, SearchType.RANGE))
            else:
                # String fields
                criteria.append(SearchCriteria(field, value, SearchType.FIELD))
    
    return criteria


# Search manager
class SearchManager:
    """Manager for coordinating search operations."""
    
    def __init__(self):
        """Initialize search manager."""
        self.case_engine = FraudCaseSearchEngine()
        self.alert_engine = FraudAlertSearchEngine()
        self.rule_engine = FraudRuleSearchEngine()
        self.advanced_engine = AdvancedSearchEngine()
    
    def search_cases(self, criteria: List[SearchCriteria], options: SearchOptions) -> SearchResult:
        """Search fraud cases."""
        return self.case_engine.search(criteria, options)
    
    def search_alerts(self, criteria: List[SearchCriteria], options: SearchOptions) -> SearchResult:
        """Search fraud alerts."""
        return self.alert_engine.search(criteria, options)
    
    def search_rules(self, criteria: List[SearchCriteria], options: SearchOptions) -> SearchResult:
        """Search fraud rules."""
        return self.rule_engine.search(criteria, options)
    
    def search_all(self, criteria: List[SearchCriteria], options: SearchOptions) -> Dict[str, SearchResult]:
        """Search across all models."""
        return self.advanced_engine.search_all(criteria, options)
    
    def quick_search(self, text: str, model_type: str = 'all', options: Optional[SearchOptions] = None) -> Dict[str, SearchResult]:
        """Quick search by text."""
        if options is None:
            options = SearchOptions()
        
        if model_type == 'all':
            return self.advanced_engine.search_by_text(text, options=options)
        elif model_type == 'cases':
            return {'cases': self.case_engine.search([
                SearchCriteria('title', text, SearchType.FULL_TEXT),
                SearchCriteria('description', text, SearchType.FULL_TEXT)
            ], options)}
        elif model_type == 'alerts':
            return {'alerts': self.alert_engine.search([
                SearchCriteria('title', text, SearchType.FULL_TEXT),
                SearchCriteria('description', text, SearchType.FULL_TEXT)
            ], options)}
        elif model_type == 'rules':
            return {'rules': self.rule_engine.search([
                SearchCriteria('name', text, SearchType.FULL_TEXT),
                SearchCriteria('description', text, SearchType.FULL_TEXT)
            ], options)}
        else:
            raise SearchError(f"Unknown model type: {model_type}")


# Global search manager instance
search_manager = SearchManager()


# Export all search classes and utilities
__all__ = [
    # Enums and data classes
    'SearchType',
    'SearchOperator',
    'SearchCriteria',
    'SearchOptions',
    'SearchResult',
    
    # Base search engine
    'BaseSearchEngine',
    
    # Specific search engines
    'FraudCaseSearchEngine',
    'FraudAlertSearchEngine',
    'FraudRuleSearchEngine',
    'AdvancedSearchEngine',
    
    # Utilities
    'parse_search_query',
    'build_search_criteria_from_request',
    
    # Manager
    'SearchManager',
    'search_manager',
]
