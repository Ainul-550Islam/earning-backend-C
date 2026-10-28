"""
Backup Module Pagination
Custom pagination classes for backup views
"""

from rest_framework.pagination import PageNumberPagination, LimitOffsetPagination
from rest_framework.response import Response
from rest_framework.utils import json
from django.core.paginator import Paginator
from django.conf import settings


class BackupPagination(PageNumberPagination):
    """
    Custom pagination for backup views with enhanced features
    """
    
    # Default page size
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100
    
    # Custom query parameters
    count_query_param = 'count'
    include_metadata_param = 'include_metadata'
    
    def get_paginated_response_schema(self, schema):
        """
        Return the schema for the paginated response.
        """
        return {
            'type': 'object',
            'properties': {
                'count': {'type': 'integer', 'example': 150},
                'next': {'type': 'string', 'nullable': True},
                'previous': {'type': 'string', 'nullable': True},
                'results': {
                    'type': 'array',
                    'items': schema
                },
                'page_info': {
                    'type': 'object',
                    'properties': {
                        'current_page': {'type': 'integer'},
                        'total_pages': {'type': 'integer'},
                        'page_size': {'type': 'integer'},
                        'has_next': {'type': 'boolean'},
                        'has_previous': {'type': 'boolean'}
                    }
                },
                'metadata': {
                    'type': 'object',
                    'description': 'Additional metadata for the paginated results'
                }
            }
        }
    
    def get_paginated_response(self, data):
        """
        Override to add custom metadata and enhanced pagination info
        """
        # Get standard pagination data
        response_data = super().get_paginated_response(data)
        
        # Add enhanced page info
        response_data.data['page_info'] = {
            'current_page': self.page.number,
            'total_pages': self.page.paginator.num_pages,
            'page_size': self.get_page_size(self.request),
            'has_next': self.page.has_next(),
            'has_previous': self.page.has_previous(),
            'start_index': (self.page.number - 1) * self.get_page_size(self.request) + 1,
            'end_index': min(self.page.number * self.get_page_size(self.request), self.page.paginator.count)
        }
        
        # Add metadata if requested
        include_metadata = self.request.query_params.get(self.include_metadata_param, 'false').lower() == 'true'
        if include_metadata:
            response_data.data['metadata'] = self._get_metadata()
        
        return response_data
    
    def _get_metadata(self):
        """
        Get additional metadata for the paginated results
        """
        # This can be extended to include statistics, filters applied, etc.
        metadata = {
            'filters_applied': {},
            'statistics': {},
            'performance': {}
        }
        
        # Add filter information if available
        if hasattr(self.request, 'backup_filters'):
            metadata['filters_applied'] = self.request.backup_filters
        
        # Add statistics if available
        if hasattr(self.request, 'backup_stats'):
            metadata['statistics'] = self.request.backup_stats
        
        return metadata
    
    def get_page_size(self, request):
        """
        Get page size from request with validation
        """
        page_size = super().get_page_size(request)
        
        # Ensure page size is within bounds
        if page_size > self.max_page_size:
            page_size = self.max_page_size
        
        return page_size


class BackupLimitOffsetPagination(LimitOffsetPagination):
    """
    Limit/offset pagination for backup views with enhanced features
    """
    
    default_limit = 20
    limit_query_param = 'limit'
    offset_query_param = 'offset'
    max_limit = 100
    
    # Custom query parameters
    include_metadata_param = 'include_metadata'
    include_count_param = 'include_count'
    
    def get_paginated_response_schema(self, schema):
        """
        Return the schema for the paginated response.
        """
        return {
            'type': 'object',
            'properties': {
                'count': {'type': 'integer', 'example': 150},
                'next': {'type': 'string', 'nullable': True},
                'previous': {'type': 'string', 'nullable': True},
                'results': {
                    'type': 'array',
                    'items': schema
                },
                'pagination_info': {
                    'type': 'object',
                    'properties': {
                        'limit': {'type': 'integer'},
                        'offset': {'type': 'integer'},
                        'has_next': {'type': 'boolean'},
                        'has_previous': {'type': 'boolean'}
                    }
                },
                'metadata': {
                    'type': 'object',
                    'description': 'Additional metadata for the paginated results'
                }
            }
        }
    
    def get_paginated_response(self, data):
        """
        Override to add custom metadata and enhanced pagination info
        """
        response_data = Response(self.get_pagination_data(data))
        
        # Add pagination info
        response_data.data['pagination_info'] = {
            'limit': self.limit,
            'offset': self.offset,
            'has_next': self.get_next_link() is not None,
            'has_previous': self.get_previous_link() is not None
        }
        
        # Add metadata if requested
        include_metadata = self.request.query_params.get(self.include_metadata_param, 'false').lower() == 'true'
        if include_metadata:
            response_data.data['metadata'] = self._get_metadata()
        
        # Include count only if requested (for performance)
        include_count = self.request.query_params.get(self.include_count_param, 'true').lower() == 'true'
        if not include_count:
            response_data.data.pop('count', None)
        
        return response_data
    
    def _get_metadata(self):
        """
        Get additional metadata for the paginated results
        """
        metadata = {
            'filters_applied': {},
            'statistics': {},
            'performance': {}
        }
        
        # Add filter information if available
        if hasattr(self.request, 'backup_filters'):
            metadata['filters_applied'] = self.request.backup_filters
        
        # Add statistics if available
        if hasattr(self.request, 'backup_stats'):
            metadata['statistics'] = self.request.backup_stats
        
        return metadata


class BackupCursorPagination:
    """
    Cursor-based pagination for large datasets with better performance
    """
    
    page_size = 20
    cursor_query_param = 'cursor'
    ordering = '-created_at'  # Default ordering
    
    def paginate_queryset(self, queryset, request, view=None):
        """
        Paginate queryset using cursor-based pagination
        """
        # Get cursor from request
        cursor = request.query_params.get(self.cursor_query_param)
        
        if cursor:
            # Decode cursor (base64 encoded timestamp)
            import base64
            import json
            try:
                cursor_data = json.loads(base64.b64decode(cursor).decode())
                timestamp = cursor_data.get('timestamp')
                if timestamp:
                    # Convert to datetime
                    from datetime import datetime
                    from django.utils import timezone
                    cursor_time = datetime.fromisoformat(timestamp)
                    if timezone.is_naive(cursor_time):
                        cursor_time = timezone.make_aware(cursor_time)
                    queryset = queryset.filter(created_at__lt=cursor_time)
            except (ValueError, json.JSONDecodeError):
                pass  # Invalid cursor, return unfiltered queryset
        
        # Order and limit
        queryset = queryset.order_by(self.ordering)[:self.page_size + 1]  # +1 to check if there's next
        
        return queryset
    
    def get_paginated_response(self, data, request):
        """
        Get paginated response with cursor information
        """
        has_next = len(data) > self.page_size
        if has_next:
            data = data[:self.page_size]
        
        # Create next cursor if there are more items
        next_cursor = None
        if has_next and data:
            # Use the last item's timestamp for next cursor
            last_item = data[-1]
            if hasattr(last_item, 'created_at'):
                import base64
                import json
                cursor_data = {
                    'timestamp': last_item.created_at.isoformat()
                }
                next_cursor = base64.b64encode(
                    json.dumps(cursor_data).encode()
                ).decode()
        
        return Response({
            'results': data,
            'next_cursor': next_cursor,
            'has_next': has_next,
            'page_size': self.page_size
        })


class BackupSearchPagination(BackupPagination):
    """
    Specialized pagination for search results with relevance scoring
    """
    
    def paginate_queryset(self, queryset, request, view=None):
        """
        Paginate search results with relevance preservation
        """
        # Check if this is a search request
        search_query = request.query_params.get('search')
        if search_query:
            # For search results, we might want to sort by relevance
            # This would require a search engine like Elasticsearch
            pass
        
        return super().paginate_queryset(queryset, request, view)
    
    def get_paginated_response(self, data):
        """
        Enhanced response for search results
        """
        response = super().get_paginated_response(data)
        
        # Add search-specific metadata
        if hasattr(self.request, 'search_query'):
            response.data['search_info'] = {
                'query': self.request.search_query,
                'total_results': self.page.paginator.count,
                'search_time': getattr(self.request, 'search_time', 0)
            }
        
        return response


class BackupExportPagination:
    """
    Pagination for export operations with streaming support
    """
    
    def __init__(self, export_format='csv', batch_size=1000):
        self.export_format = export_format
        self.batch_size = batch_size
        self.current_offset = 0
        self.total_count = 0
    
    def paginate_export(self, queryset, view=None):
        """
        Paginate queryset for export operations
        """
        self.total_count = queryset.count()
        
        while self.current_offset < self.total_count:
            # Get batch
            batch = queryset[self.current_offset:self.current_offset + self.batch_size]
            
            yield {
                'data': batch,
                'offset': self.current_offset,
                'batch_number': (self.current_offset // self.batch_size) + 1,
                'total_batches': (self.total_count + self.batch_size - 1) // self.batch_size,
                'has_more': self.current_offset + self.batch_size < self.total_count
            }
            
            self.current_offset += self.batch_size
    
    def get_export_metadata(self):
        """
        Get metadata for the export operation
        """
        return {
            'total_records': self.total_count,
            'batch_size': self.batch_size,
            'total_batches': (self.total_count + self.batch_size - 1) // self.batch_size,
            'export_format': self.export_format,
            'completed': self.current_offset >= self.total_count
        }


# Utility functions for pagination
def get_pagination_class(pagination_type='page'):
    """
    Get pagination class based on type
    
    Args:
        pagination_type (str): Type of pagination ('page', 'offset', 'cursor', 'search')
        
    Returns:
        Class: Pagination class
    """
    pagination_classes = {
        'page': BackupPagination,
        'offset': BackupLimitOffsetPagination,
        'cursor': BackupCursorPagination,
        'search': BackupSearchPagination
    }
    
    return pagination_classes.get(pagination_type, BackupPagination)


def validate_pagination_params(request, max_page_size=100):
    """
    Validate and normalize pagination parameters
    
    Args:
        request: HTTP request object
        max_page_size (int): Maximum allowed page size
        
    Returns:
        dict: Validated pagination parameters
    """
    params = {}
    
    # Page number pagination
    if 'page' in request.query_params:
        try:
            page = int(request.query_params['page'])
            if page < 1:
                page = 1
            params['page'] = page
        except ValueError:
            params['page'] = 1
    else:
        params['page'] = 1
    
    # Page size
    if 'page_size' in request.query_params:
        try:
            page_size = int(request.query_params['page_size'])
            if page_size < 1:
                page_size = 20
            elif page_size > max_page_size:
                page_size = max_page_size
            params['page_size'] = page_size
        except ValueError:
            params['page_size'] = 20
    else:
        params['page_size'] = 20
    
    # Limit/offset pagination
    if 'limit' in request.query_params:
        try:
            limit = int(request.query_params['limit'])
            if limit < 1:
                limit = 20
            elif limit > max_page_size:
                limit = max_page_size
            params['limit'] = limit
        except ValueError:
            params['limit'] = 20
    else:
        params['limit'] = 20
    
    if 'offset' in request.query_params:
        try:
            offset = int(request.query_params['offset'])
            if offset < 0:
                offset = 0
            params['offset'] = offset
        except ValueError:
            params['offset'] = 0
    else:
        params['offset'] = 0
    
    return params


class BackupTimelinePagination(PageNumberPagination):
    """
    Specialized pagination for timeline-based backup views
    """
    
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200
    
    def get_paginated_response_schema(self, schema):
        """
        Return the schema for the timeline paginated response.
        """
        return {
            'type': 'object',
            'properties': {
                'count': {'type': 'integer', 'example': 150},
                'next': {'type': 'string', 'nullable': True},
                'previous': {'type': 'string', 'nullable': True},
                'results': {
                    'type': 'array',
                    'items': schema
                },
                'timeline_info': {
                    'type': 'object',
                    'properties': {
                        'current_page': {'type': 'integer'},
                        'total_pages': {'type': 'integer'},
                        'page_size': {'type': 'integer'},
                        'has_next': {'type': 'boolean'},
                        'has_previous': {'type': 'boolean'},
                        'date_range': {
                            'type': 'object',
                            'properties': {
                                'start_date': {'type': 'string', 'format': 'date'},
                                'end_date': {'type': 'string', 'format': 'date'}
                            }
                        }
                    }
                },
                'statistics': {
                    'type': 'object',
                    'description': 'Timeline-specific statistics'
                }
            }
        }
    
    def get_paginated_response(self, data):
        """
        Override to add timeline-specific metadata
        """
        response_data = super().get_paginated_response(data)
        
        # Add timeline info
        response_data.data['timeline_info'] = {
            'current_page': self.page.number,
            'total_pages': self.page.paginator.num_pages,
            'page_size': self.get_page_size(self.request),
            'has_next': self.page.has_next(),
            'has_previous': self.page.has_previous()
        }
        
        # Add date range if available
        if hasattr(self.request, 'timeline_start_date') and hasattr(self.request, 'timeline_end_date'):
            response_data.data['timeline_info']['date_range'] = {
                'start_date': self.request.timeline_start_date,
                'end_date': self.request.timeline_end_date
            }
        
        # Add timeline statistics
        response_data.data['statistics'] = self._get_timeline_statistics()
        
        return response_data
    
    def _get_timeline_statistics(self):
        """
        Get timeline-specific statistics
        """
        stats = {
            'total_items': self.page.paginator.count,
            'items_per_page': self.get_page_size(self.request),
            'current_range_start': (self.page.number - 1) * self.get_page_size(self.request) + 1,
            'current_range_end': min(self.page.number * self.get_page_size(self.request), self.page.paginator.count)
        }
        
        # Add timeline-specific stats if available
        if hasattr(self.request, 'timeline_stats'):
            stats.update(self.request.timeline_stats)
        
        return stats


class BackupLogPagination(PageNumberPagination):
    """
    Specialized pagination for backup logs with enhanced filtering
    """
    
    page_size = 100
    page_size_query_param = 'page_size'
    max_page_size = 500
    
    def get_paginated_response_schema(self, schema):
        """
        Return the schema for the log paginated response.
        """
        return {
            'type': 'object',
            'properties': {
                'count': {'type': 'integer', 'example': 1500},
                'next': {'type': 'string', 'nullable': True},
                'previous': {'type': 'string', 'nullable': True},
                'results': {
                    'type': 'array',
                    'items': schema
                },
                'log_info': {
                    'type': 'object',
                    'properties': {
                        'current_page': {'type': 'integer'},
                        'total_pages': {'type': 'integer'},
                        'page_size': {'type': 'integer'},
                        'has_next': {'type': 'boolean'},
                        'has_previous': {'type': 'boolean'},
                        'log_levels': {
                            'type': 'object',
                            'description': 'Distribution of log levels in current page'
                        },
                        'time_range': {
                            'type': 'object',
                            'properties': {
                                'earliest_log': {'type': 'string', 'format': 'date-time'},
                                'latest_log': {'type': 'string', 'format': 'date-time'}
                            }
                        }
                    }
                },
                'filters_applied': {
                    'type': 'object',
                    'description': 'Filters applied to the log query'
                }
            }
        }
    
    def get_paginated_response(self, data):
        """
        Override to add log-specific metadata
        """
        response_data = super().get_paginated_response(data)
        
        # Add log info
        response_data.data['log_info'] = {
            'current_page': self.page.number,
            'total_pages': self.page.paginator.num_pages,
            'page_size': self.get_page_size(self.request),
            'has_next': self.page.has_next(),
            'has_previous': self.page.has_previous(),
            'log_levels': self._get_log_level_distribution(),
            'time_range': self._get_time_range()
        }
        
        # Add filters applied
        if hasattr(self.request, 'log_filters'):
            response_data.data['filters_applied'] = self.request.log_filters
        
        return response_data
    
    def _get_log_level_distribution(self):
        """
        Get distribution of log levels in current page
        """
        log_levels = {}
        
        if hasattr(self.page, 'object_list'):
            for item in self.page.object_list:
                if hasattr(item, 'level'):
                    level = item.level
                    log_levels[level] = log_levels.get(level, 0) + 1
        
        return log_levels
    
    def _get_time_range(self):
        """
        Get time range of logs in current page
        """
        time_range = {}
        
        if hasattr(self.page, 'object_list') and self.page.object_list:
            timestamps = []
            for item in self.page.object_list:
                if hasattr(item, 'timestamp'):
                    timestamps.append(item.timestamp)
            
            if timestamps:
                time_range = {
                    'earliest_log': min(timestamps).isoformat(),
                    'latest_log': max(timestamps).isoformat()
                }
        
        return time_range


class BackupAnalyticsPagination(LimitOffsetPagination):
    """
    Specialized pagination for analytics and reporting data
    """
    
    default_limit = 50
    limit_query_param = 'limit'
    offset_query_param = 'offset'
    max_limit = 1000
    
    def get_paginated_response_schema(self, schema):
        """
        Return the schema for the analytics paginated response.
        """
        return {
            'type': 'object',
            'properties': {
                'count': {'type': 'integer', 'example': 500},
                'next': {'type': 'string', 'nullable': True},
                'previous': {'type': 'string', 'nullable': True},
                'results': {
                    'type': 'array',
                    'items': schema
                },
                'analytics_info': {
                    'type': 'object',
                    'properties': {
                        'limit': {'type': 'integer'},
                        'offset': {'type': 'integer'},
                        'has_next': {'type': 'boolean'},
                        'has_previous': {'type': 'boolean'},
                        'aggregation_type': {'type': 'string'},
                        'date_range': {
                            'type': 'object',
                            'properties': {
                                'start': {'type': 'string', 'format': 'date'},
                                'end': {'type': 'string', 'format': 'date'}
                            }
                        }
                    }
                },
                'summary': {
                    'type': 'object',
                    'description': 'Summary statistics for the analytics data'
                }
            }
        }
    
    def get_paginated_response(self, data):
        """
        Override to add analytics-specific metadata
        """
        response_data = Response(self.get_pagination_data(data))
        
        # Add analytics info
        response_data.data['analytics_info'] = {
            'limit': self.limit,
            'offset': self.offset,
            'has_next': self.get_next_link() is not None,
            'has_previous': self.get_previous_link() is not None,
            'aggregation_type': getattr(self.request, 'aggregation_type', 'daily'),
            'date_range': getattr(self.request, 'analytics_date_range', {})
        }
        
        # Add summary statistics
        response_data.data['summary'] = self._get_analytics_summary()
        
        return response_data
    
    def _get_analytics_summary(self):
        """
        Get summary statistics for analytics data
        """
        summary = {
            'total_records': self.count,
            'current_batch_size': len(self.data),
            'batch_start': self.offset + 1,
            'batch_end': self.offset + len(self.data)
        }
        
        # Add analytics-specific summary if available
        if hasattr(self.request, 'analytics_summary'):
            summary.update(self.request.analytics_summary)
        
        return summary


class BackupInfiniteScrollPagination:
    """
    Pagination optimized for infinite scroll interfaces
    """
    
    def __init__(self, page_size=20):
        self.page_size = page_size
        self.last_id = None
        self.has_more = True
    
    def paginate_queryset(self, queryset, request, view=None):
        """
        Paginate queryset for infinite scroll
        """
        # Get the last ID from request for pagination
        last_id = request.query_params.get('last_id')
        
        if last_id:
            try:
                self.last_id = int(last_id)
                # Filter to get items after the last ID
                queryset = queryset.filter(id__gt=self.last_id)
            except ValueError:
                pass  # Invalid ID, start from beginning
        
        # Limit to page size + 1 to check if there are more items
        queryset = queryset.order_by('id')[:self.page_size + 1]
        
        # Check if there are more items
        items = list(queryset)
        self.has_more = len(items) > self.page_size
        
        if self.has_more:
            items = items[:self.page_size]
        
        return items
    
    def get_paginated_response(self, data, request):
        """
        Get response for infinite scroll
        """
        # Get the last ID for next page
        next_last_id = None
        if data and self.has_more:
            next_last_id = str(data[-1].id)
        
        return Response({
            'results': data,
            'has_more': self.has_more,
            'next_last_id': next_last_id,
            'page_size': self.page_size
        })


class BackupCalendarPagination:
    """
    Pagination for calendar-based backup views
    """
    
    def __init__(self, date_field='created_at'):
        self.date_field = date_field
        self.current_date = None
        self.direction = 'future'  # or 'past'
    
    def paginate_queryset(self, queryset, request, view=None):
        """
        Paginate queryset by date ranges
        """
        # Get date parameters
        date_param = request.query_params.get('date')
        direction = request.query_params.get('direction', 'future')
        
        if date_param:
            try:
                from datetime import datetime
                from django.utils import timezone
                
                self.current_date = datetime.fromisoformat(date_param)
                if timezone.is_naive(self.current_date):
                    self.current_date = timezone.make_aware(self.current_date)
                
                self.direction = direction
                
                # Filter based on direction
                if direction == 'future':
                    queryset = queryset.filter(**{f'{self.date_field}__gte': self.current_date})
                else:
                    queryset = queryset.filter(**{f'{self.date_field}__lte': self.current_date})
                    
            except ValueError:
                pass  # Invalid date, return unfiltered queryset
        
        # Order and limit
        order_by = f'-{self.date_field}' if direction == 'past' else self.date_field
        queryset = queryset.order_by(order_by)[:50]  # Limit to 50 items per calendar view
        
        return queryset
    
    def get_paginated_response(self, data, request):
        """
        Get response for calendar pagination
        """
        # Calculate next and previous dates
        next_date = None
        prev_date = None
        
        if data and self.current_date:
            # Simple date calculation (can be enhanced based on requirements)
            from datetime import timedelta
            
            if self.direction == 'future':
                next_date = (self.current_date + timedelta(days=1)).isoformat()
                prev_date = (self.current_date - timedelta(days=1)).isoformat()
            else:
                next_date = (self.current_date - timedelta(days=1)).isoformat()
                prev_date = (self.current_date + timedelta(days=1)).isoformat()
        
        return Response({
            'results': data,
            'current_date': self.current_date.isoformat() if self.current_date else None,
            'direction': self.direction,
            'next_date': next_date,
            'prev_date': prev_date,
            'count': len(data)
        })


# Enhanced utility functions
def get_backup_pagination_config(view_type='list', user_role=None):
    """
    Get pagination configuration based on view type and user role
    
    Args:
        view_type (str): Type of view ('list', 'timeline', 'logs', 'analytics', 'calendar')
        user_role (str): User role for permission-based pagination
        
    Returns:
        dict: Pagination configuration
    """
    base_config = {
        'page_size': 20,
        'max_page_size': 100,
        'page_size_query_param': 'page_size'
    }
    
    # Adjust based on view type
    if view_type == 'timeline':
        base_config.update({
            'page_size': 50,
            'max_page_size': 200
        })
    elif view_type == 'logs':
        base_config.update({
            'page_size': 100,
            'max_page_size': 500
        })
    elif view_type == 'analytics':
        base_config.update({
            'page_size': 50,
            'max_page_size': 1000
        })
    elif view_type == 'calendar':
        base_config.update({
            'page_size': 30,  # Approximately one month
            'max_page_size': 365  # One year
        })
    
    # Adjust based on user role
    if user_role == 'admin':
        base_config['max_page_size'] = min(base_config['max_page_size'] * 2, 1000)
    elif user_role == 'viewer':
        base_config['max_page_size'] = min(base_config['max_page_size'], 50)
    
    return base_config


def create_pagination_class(config=None, **kwargs):
    """
    Create a custom pagination class with given configuration
    
    Args:
        config (dict): Pagination configuration
        **kwargs: Additional class attributes
        
    Returns:
        class: Custom pagination class
    """
    if config is None:
        config = {}
    
    class CustomBackupPagination(BackupPagination):
        pass
    
    # Set configuration
    for key, value in config.items():
        setattr(CustomBackupPagination, key, value)
    
    # Set additional attributes
    for key, value in kwargs.items():
        setattr(CustomBackupPagination, key, value)
    
    return CustomBackupPagination


def optimize_pagination_for_queryset(queryset, request, default_page_size=20):
    """
    Optimize pagination parameters based on queryset characteristics
    
    Args:
        queryset: Django queryset
        request: HTTP request
        default_page_size (int): Default page size
        
    Returns:
        dict: Optimized pagination parameters
    """
    # Estimate total count (this might be expensive for large querysets)
    try:
        total_count = queryset.count()
    except:
        total_count = 0
    
    # Adjust page size based on total count
    if total_count < 50:
        page_size = min(total_count, 20)
    elif total_count < 200:
        page_size = 25
    elif total_count < 1000:
        page_size = 30
    else:
        page_size = default_page_size
    
    # Respect user preference if available and reasonable
    user_page_size = request.query_params.get('page_size')
    if user_page_size:
        try:
            user_page_size = int(user_page_size)
            if 1 <= user_page_size <= 100:
                page_size = user_page_size
        except ValueError:
            pass
    
    return {
        'page_size': page_size,
        'total_count': total_count,
        'estimated_pages': (total_count + page_size - 1) // page_size if total_count > 0 else 0
    }
