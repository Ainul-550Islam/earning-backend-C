"""
pagination.py – Enhanced Custom pagination classes for postback module.

Provides optimized pagination for postback-related endpoints with
enhanced performance for high-volume data and flexible configuration.
Enhanced with integration system features for monitoring, caching, and analytics.
"""
import math
import time
from collections import OrderedDict
from typing import Dict, List, Optional, Any, Union

from django.core.paginator import Paginator as DjangoPaginator
from django.core.cache import cache
from django.utils.functional import cached_property
from django.conf import settings
from django.utils import timezone
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
# from rest_framework.utils import replace_html_param
try:
    from rest_framework.utils import replace_html_param
except ImportError:
    def replace_html_param(name, val): return val

from .constants import POSTBACK_CACHE_TIMEOUT
from .INTEGRATION_SYSTEM.MONITORING_LOGS.performance_monitor import record_performance_metric
from .INTEGRATION_SYSTEM.integ_audit_logs import log_integration_event
from .caching import get_cached, set_cached


class PostbackPagination(PageNumberPagination):
    """
    Enhanced custom pagination class optimized for postback endpoints.
    
    Features:
    - Configurable page sizes with defaults
    - Enhanced metadata for frontend consumption
    - Performance optimizations for large datasets
    - Cache-friendly pagination for frequently accessed data
    - Custom response structure for postback analytics
    - Integration system monitoring and logging
    - Advanced caching with multi-level support
    - Performance metrics and analytics
    """
    
    # Default configuration
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 1000
    
    # Custom query parameters
    include_metadata_param = 'include_metadata'
    cache_param = 'cache'
    analytics_param = 'analytics'
    
    # Cache configuration
    cache_enabled = True
    cache_timeout = POSTBACK_CACHE_TIMEOUT
    cache_key_prefix = 'postback_pagination'
    
    # Integration system features
    enable_monitoring = True
    enable_audit_logging = True
    enable_performance_tracking = True
    
    def __init__(self, *args, **kwargs):
        """Initialize pagination with custom configuration."""
        super().__init__(*args, **kwargs)
        self.include_metadata = self._get_include_metadata()
        self.use_cache = self._should_use_cache()
        self.include_analytics = self._get_include_analytics()
        self.start_time = time.time()
        self.query_time = 0
        self.cache_hit = False
    
    def paginate_queryset(self, queryset, view, request=None):
        """Override to add caching, monitoring, and performance optimizations."""
        query_start_time = time.time()
        
        # Log pagination start
        if self.enable_audit_logging:
            log_integration_event(
                event_type="pagination_started",
                user_id=getattr(request, 'user', None).id if request and hasattr(request, 'user') else None,
                details={
                    'queryset_model': queryset.model.__name__,
                    'queryset_count': queryset.count(),
                    'cache_enabled': self.use_cache,
                    'include_metadata': self.include_metadata,
                    'include_analytics': self.include_analytics,
                }
            )
        
        # Generate cache key if caching is enabled
        cache_key = None
        if self.use_cache:
            cache_key = self._generate_cache_key(queryset, request)
            
            # Try multi-level cache first
            cached_result = get_cached(cache_key)
            
            if cached_result is not None:
                # Return cached pagination result
                self._cached_result = cached_result
                self.cache_hit = True
                self.query_time = time.time() - query_start_time
                
                # Log cache hit
                if self.enable_audit_logging:
                    log_integration_event(
                        event_type="pagination_cache_hit",
                        details={
                            'cache_key': cache_key,
                            'query_time': self.query_time,
                            'items_count': len(cached_result['items']),
                        }
                    )
                
                return cached_result['items']
        
        # Apply pagination
        page_size = self.get_page_size(request)
        
        # Use Django's built-in paginator for efficiency
        paginator = DjangoPaginator(queryset, page_size)
        
        # Get page number
        page_number = self.get_page_number(request, paginator)
        
        # Get page
        page = paginator.page(page_number)
        
        # Convert to list for JSON serialization
        items = list(page.object_list)
        
        # Cache the result if enabled
        if self.use_cache and cache_key:
            cache_data = {
                'items': items,
                'paginator': paginator,
                'page': page,
                'cached_at': timezone.now().isoformat(),
                'query_time': time.time() - query_start_time,
            }
            set_cached(cache_key, cache_data, self.cache_timeout)
            self._cached_result = cache_data
        
        self.query_time = time.time() - query_start_time
        
        # Record performance metrics
        if self.enable_performance_tracking:
            record_performance_metric(
                "pagination_query",
                self.query_time,
                headers={
                    'queryset_model': queryset.model.__name__,
                    'items_count': len(items),
                    'cache_hit': self.cache_hit,
                    'page_size': page_size,
                    'page_number': page_number,
                }
            )
        
        return items
    
    def get_paginated_response(self, data):
        """Return paginated response with enhanced metadata and integration system features."""
        total_time = time.time() - self.start_time
        
        # Get pagination data
        if hasattr(self, '_cached_result'):
            paginator = self._cached_result['paginator']
            page = self._cached_result['page']
        else:
            paginator = self.paginator
            page = self.page
        
        # Build response data
        response_data = {
            'results': data,
            'pagination': self._get_pagination_metadata(paginator, page)
        }
        
        # Add additional metadata if requested
        if self.include_metadata:
            response_data['metadata'] = self._get_enhanced_metadata(paginator, page)
        
        # Add analytics data if requested
        if self.include_analytics:
            response_data['analytics'] = self._get_analytics_metadata(paginator, page)
        
        # Add performance metrics
        if self.enable_performance_tracking:
            response_data['performance'] = {
                'total_time': total_time,
                'query_time': self.query_time,
                'cache_hit': self.cache_hit,
                'items_per_second': len(data) / self.query_time if self.query_time > 0 else 0,
            }
        
        # Log pagination completion
        if self.enable_audit_logging:
            log_integration_event(
                event_type="pagination_completed",
                details={
                    'total_time': total_time,
                    'query_time': self.query_time,
                    'cache_hit': self.cache_hit,
                    'items_count': len(data),
                    'total_items': paginator.count,
                    'page_number': page.number,
                    'total_pages': paginator.num_pages,
                }
            )
        
        # Record final performance metrics
        if self.enable_performance_tracking:
            record_performance_metric(
                "pagination_response",
                total_time,
                headers={
                    'total_items': paginator.count,
                    'returned_items': len(data),
                    'cache_hit': self.cache_hit,
                    'include_metadata': self.include_metadata,
                    'include_analytics': self.include_analytics,
                }
            )
        
        return Response(response_data)
    
    def _get_pagination_metadata(self, paginator, page):
        """Get standard pagination metadata."""
        return {
            'count': paginator.count,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'page_number': page.number,
            'num_pages': paginator.num_pages,
            'per_page': paginator.per_page,
            'has_next': page.has_next(),
            'has_previous': page.has_previous(),
            'total_pages': paginator.num_pages,
            'current_page': page.number,
            'items_on_page': len(page.object_list),
            'start_index': page.start_index(),
            'end_index': page.end_index(),
        }
    
    def _get_enhanced_metadata(self, paginator, page):
        """Get enhanced metadata for analytics and performance."""
        metadata = {
            'page_info': {
                'is_first_page': page.number == 1,
                'is_last_page': page.number == paginator.num_pages,
                'page_range': list(paginator.page_range),
                'current_page_range': self._get_current_page_range(paginator, page),
            },
            'performance': {
                'items_per_page': paginator.per_page,
                'total_items': paginator.count,
                'estimated_total_pages': math.ceil(paginator.count / paginator.per_page),
                'cache_enabled': self.use_cache,
                'cache_key': self._generate_cache_key(None, None) if self.use_cache else None,
                'query_time': self.query_time,
                'cache_hit': self.cache_hit,
            }
        }
        
        # Add analytics metadata for postback-specific endpoints
        if hasattr(self, '_view') and hasattr(self._view, 'get_analytics_metadata'):
            try:
                analytics_metadata = self._view.get_analytics_metadata(paginator, page)
                metadata['analytics'] = analytics_metadata
            except Exception:
                pass  # Ignore analytics metadata errors
        
        return metadata
    
    def _get_analytics_metadata(self, paginator, page):
        """Get analytics metadata for pagination performance and usage."""
        analytics = {
            'pagination_efficiency': {
                'items_per_second': len(page.object_list) / self.query_time if self.query_time > 0 else 0,
                'cache_efficiency': self.cache_hit,
                'page_utilization': len(page.object_list) / paginator.per_page,
                'total_efficiency': paginator.count / (self.query_time + 0.001),  # Avoid division by zero
            },
            'usage_patterns': {
                'page_size_optimal': len(page.object_list) >= paginator.per_page * 0.8,
                'deep_pagination': page.number > paginator.num_pages * 0.5,
                'large_dataset': paginator.count > 10000,
                'high_frequency_access': self.cache_hit,
            },
            'recommendations': self._get_pagination_recommendations(paginator, page),
        }
        
        return analytics
    
    def _get_pagination_recommendations(self, paginator, page):
        """Get pagination performance recommendations."""
        recommendations = []
        
        # Page size recommendations
        if len(page.object_list) < paginator.per_page * 0.5:
            recommendations.append({
                'type': 'page_size',
                'message': 'Consider reducing page size for better performance',
                'suggested_page_size': max(10, paginator.per_page // 2)
            })
        
        # Cache recommendations
        if not self.cache_hit and paginator.count > 1000:
            recommendations.append({
                'type': 'caching',
                'message': 'Enable caching for better performance on large datasets',
                'suggested_action': 'Add cache=true parameter'
            })
        
        # Query optimization recommendations
        if self.query_time > 1.0:
            recommendations.append({
                'type': 'query_optimization',
                'message': 'Query time is high, consider optimizing the queryset',
                'suggested_action': 'Add select_related/prefetch_related or database indexes'
            })
        
        # Large dataset recommendations
        if paginator.count > 50000:
            recommendations.append({
                'type': 'large_dataset',
                'message': 'Large dataset detected, consider using cursor-based pagination',
                'suggested_action': 'Implement CursorPagination for better performance'
            })
        
        return recommendations
    
    def _get_current_page_range(self, paginator, page):
        """Get current page range for display."""
        current = page.number
        total = paginator.num_pages
        
        if total <= 7:
            return list(range(1, total + 1))
        
        if current <= 4:
            return list(range(1, 8))
        
        if current >= total - 3:
            return list(range(total - 6, total + 1))
        
        return list(range(current - 3, current + 4))
    
    def _generate_cache_key(self, queryset, request):
        """Generate cache key for pagination."""
        if not queryset or not request:
            return None
        
        # Build cache components
        components = [
            self.cache_key_prefix,
            str(queryset.model.__name__),
            str(queryset.count()),
            str(self.get_page_size(request)),
            str(self.get_page_number(request, DjangoPaginator(queryset, self.get_page_size(request)))),
        ]
        
        # Add query parameters for more specific caching
        if request:
            query_params = OrderedDict(sorted(request.query_params.items()))
            for key, value in query_params.items():
                if key not in ['page', 'page_size']:
                    components.append(f"{key}={value}")
        
        return ':'.join(components)
    
    def _get_include_metadata(self):
        """Get metadata inclusion flag from request."""
        if hasattr(self, 'request') and self.request:
            return self.request.query_params.get(self.include_metadata_param, 'false').lower() == 'true'
        return False
    
    def _get_include_analytics(self):
        """Get analytics inclusion flag from request."""
        if hasattr(self, 'request') and self.request:
            return self.request.query_params.get(self.analytics_param, 'false').lower() == 'true'
        return False
    
    def _should_use_cache(self):
        """Determine if caching should be used."""
        if not self.cache_enabled:
            return False
        
        if not settings.DEBUG:
            return True
        
        # Check cache parameter
        if hasattr(self, 'request') and self.request:
            cache_param = self.request.query_params.get(self.cache_param, 'true')
            return cache_param.lower() != 'false'
        
        return True
    
    def get_page_size(self, request):
        """Get page size with validation and defaults."""
        try:
            page_size = int(request.query_params.get(self.page_size_query_param, self.page_size))
            
            # Validate page size
            if page_size < 1:
                page_size = self.page_size
            elif page_size > self.max_page_size:
                page_size = self.max_page_size
            
            return page_size
        except (ValueError, TypeError):
            return self.page_size
    
    def get_next_link(self):
        """Get next link with proper URL construction."""
        if not self.page.has_next():
            return None
        
        url = self.request.build_absolute_uri()
        page_number = self.page.next_page_number()
        
        return replace_html_param(url, self.page_query_param, page_number)
    
    def get_previous_link(self):
        """Get previous link with proper URL construction."""
        if not self.page.has_previous():
            return None
        
        url = self.request.build_absolute_uri()
        page_number = self.page.previous_page_number()
        
        return replace_html_param(url, self.page_query_param, page_number)


class PostbackAnalyticsPagination(PostbackPagination):
    """
    Specialized pagination for postback analytics endpoints.
    
    Provides additional metadata and optimizations specifically for
    postback analytics and reporting endpoints.
    """
    
    # Analytics-specific defaults
    page_size = 25  # Smaller default for analytics data
    max_page_size = 500  # Lower max for performance
    
    def _get_enhanced_metadata(self, paginator, page):
        """Get analytics-specific enhanced metadata."""
        metadata = super()._get_enhanced_metadata(paginator, page)
        
        # Add analytics-specific metadata
        metadata['analytics'] = {
            'data_summary': self._get_data_summary(paginator, page),
            'performance_metrics': self._get_performance_metrics(paginator, page),
            'export_info': self._get_export_info(paginator, page),
        }
        
        return metadata
    
    def _get_data_summary(self, paginator, page):
        """Get data summary for analytics endpoints."""
        # This would be customized based on the specific analytics data
        summary = {
            'total_items': paginator.count,
            'items_in_page': len(page.object_list),
            'page_number': page.number,
            'total_pages': paginator.num_pages,
        }
        
        # Add field-specific summaries if available
        if hasattr(page.object_list, 'first'):
            first_item = page.object_list.first()
            if hasattr(first_item, 'get_summary_data'):
                try:
                    summary.update(first_item.get_summary_data())
                except Exception:
                    pass
        
        return summary
    
    def _get_performance_metrics(self, paginator, page):
        """Get performance metrics for the pagination."""
        return {
            'query_time': getattr(self, '_query_time', None),
            'cache_hit': getattr(self, '_cache_hit', False),
            'items_per_page': paginator.per_page,
            'estimated_total_items': paginator.count,
            'page_load_time': getattr(self, '_page_load_time', None),
        }
    
    def _get_export_info(self, paginator, page):
        """Get export information for analytics data."""
        return {
            'can_export': paginator.count <= 10000,  # Limit for export
            'export_formats': ['csv', 'excel', 'json'],
            'max_export_items': min(paginator.count, 10000),
            'current_page_export': len(page.object_list),
        }


class PostbackLogPagination(PostbackPagination):
    """
    Specialized pagination for postback log endpoints.
    
    Optimized for high-volume postback log data with
    additional filtering and sorting metadata.
    """
    
    # Log-specific defaults
    page_size = 100  # Larger default for logs
    max_page_size = 2000  # Higher max for logs
    
    def _get_enhanced_metadata(self, paginator, page):
        """Get log-specific enhanced metadata."""
        metadata = super()._get_enhanced_metadata(paginator, page)
        
        # Add log-specific metadata
        metadata['logs'] = {
            'time_range': self._get_time_range(page.object_list),
            'status_distribution': self._get_status_distribution(page.object_list),
            'network_distribution': self._get_network_distribution(page.object_list),
            'performance_summary': self._get_performance_summary(page.object_list),
        }
        
        return metadata
    
    def _get_time_range(self, items):
        """Get time range for log items."""
        if not items:
            return None
        
        try:
            from django.utils import timezone
            
            timestamps = [item.received_at for item in items if hasattr(item, 'received_at') and item.received_at]
            if timestamps:
                earliest = min(timestamps)
                latest = max(timestamps)
                return {
                    'earliest': earliest.isoformat(),
                    'latest': latest.isoformat(),
                    'duration_hours': (latest - earliest).total_seconds() / 3600
                }
        except Exception:
            pass
        
        return None
    
    def _get_status_distribution(self, items):
        """Get status distribution for log items."""
        from api.postback.choices import PostbackStatus
        
        distribution = {}
        for item in items:
            if hasattr(item, 'status'):
                status = item.get_status_display() if hasattr(item, 'get_status_display') else str(item.status)
                distribution[status] = distribution.get(status, 0) + 1
        
        return distribution
    
    def _get_network_distribution(self, items):
        """Get network distribution for log items."""
        distribution = {}
        for item in items:
            if hasattr(item, 'network') and item.network:
                network_name = item.network.name or item.network.network_key
                distribution[network_name] = distribution.get(network_name, 0) + 1
        
        return distribution
    
    def _get_performance_summary(self, items):
        """Get performance summary for log items."""
        processed_items = [item for item in items if hasattr(item, 'processed_at') and item.processed_at]
        
        if not processed_items:
            return None
        
        try:
            processing_times = []
            for item in processed_items:
                if hasattr(item, 'received_at') and item.received_at:
                    time_diff = (item.processed_at - item.received_at).total_seconds()
                    processing_times.append(time_diff)
            
            if processing_times:
                return {
                    'avg_processing_time': sum(processing_times) / len(processing_times),
                    'min_processing_time': min(processing_times),
                    'max_processing_time': max(processing_times),
                    'processed_count': len(processed_items),
                    'unprocessed_count': len(items) - len(processed_items)
                }
        except Exception:
            pass
        
        return None


class PostbackInsightPagination(PostbackAnalyticsPagination):
    """
    Specialized pagination for postback insight endpoints.
    
    Optimized for insight data with additional health metrics
    and trend information.
    """
    
    # Insight-specific defaults
    page_size = 31  # One month of daily insights
    max_page_size = 365  # One year of daily insights
    
    def _get_enhanced_metadata(self, paginator, page):
        """Get insight-specific enhanced metadata."""
        metadata = super()._get_enhanced_metadata(paginator, page)
        
        # Add insight-specific metadata
        metadata['insights'] = {
            'date_range': self._get_date_range(page.object_list),
            'health_summary': self._get_health_summary(page.object_list),
            'anomaly_summary': self._get_anomaly_summary(page.object_list),
            'trend_info': self._get_trend_info(page.object_list),
        }
        
        return metadata
    
    def _get_date_range(self, items):
        """Get date range for insight items."""
        if not items:
            return None
        
        try:
            dates = [item.date for item in items if hasattr(item, 'date')]
            if dates:
                return {
                    'earliest_date': min(dates).isoformat(),
                    'latest_date': max(dates).isoformat(),
                    'total_days': len(set(dates))
                }
        except Exception:
            pass
        
        return None
    
    def _get_health_summary(self, items):
        """Get health score summary for insight items."""
        health_scores = []
        for item in items:
            if hasattr(item, 'health_score'):
                health_scores.append(float(item.health_score))
        
        if not health_scores:
            return None
        
        return {
            'avg_health_score': sum(health_scores) / len(health_scores),
            'min_health_score': min(health_scores),
            'max_health_score': max(health_scores),
            'healthy_days': len([s for s in health_scores if s >= 80]),
            'critical_days': len([s for s in health_scores if s < 50]),
        }
    
    def _get_anomaly_summary(self, items):
        """Get anomaly summary for insight items."""
        anomaly_count = 0
        anomaly_types = {}
        
        for item in items:
            if hasattr(item, 'anomaly_detected') and item.anomaly_detected:
                anomaly_count += 1
                if hasattr(item, 'anomaly_details') and item.anomaly_details:
                    for anomaly_type in item.anomaly_details.keys():
                        anomaly_types[anomaly_type] = anomaly_types.get(anomaly_type, 0) + 1
        
        return {
            'total_anomalies': anomaly_count,
            'anomaly_types': anomaly_types,
            'anomaly_rate': (anomaly_count / len(items)) * 100 if items else 0,
        }
    
    def _get_trend_info(self, items):
        """Get trend information for insight items."""
        if len(items) < 2:
            return None
        
        try:
            # Sort by date
            sorted_items = sorted(items, key=lambda x: x.date if hasattr(x, 'date') else None)
            
            # Calculate trend for received count
            counts = [item.received_count for item in sorted_items if hasattr(item, 'received_count')]
            if len(counts) >= 2:
                first_half = counts[:len(counts)//2]
                second_half = counts[len(counts)//2:]
                
                first_avg = sum(first_half) / len(first_half)
                second_avg = sum(second_half) / len(second_half)
                
                trend = 'stable'
                if second_avg > first_avg * 1.1:
                    trend = 'increasing'
                elif second_avg < first_avg * 0.9:
                    trend = 'decreasing'
                
                return {
                    'volume_trend': trend,
                    'first_half_avg': first_avg,
                    'second_half_avg': second_avg,
                    'trend_percentage': ((second_avg - first_avg) / first_avg * 100) if first_avg > 0 else 0
                }
        except Exception:
            pass
        
        return None
