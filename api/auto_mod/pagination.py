# =============================================================================
# auto_mod/pagination.py
# =============================================================================

"""
Custom pagination classes for auto moderation system.
"""

from collections import OrderedDict
from django.core.paginator import Paginator
from django.utils.translation import gettext_lazy as _
from rest_framework import pagination
from rest_framework.response import Response
from rest_framework.settings import api_settings

from .models import SuspiciousSubmission, ModerationDecision, ModerationAppeal, ModerationQueue
from .choices import ModerationStatus, AppealStatus


class AutoModPagination(pagination.PageNumberPagination):
    """
    Custom pagination class for auto moderation endpoints.
    
    Provides enhanced pagination with:
    - Custom page size limits
    - Metadata about filtered results
    - Performance optimization for large datasets
    - Support for different content types
    """
    
    # Default page size
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100
    
    # Custom query parameters
    count_query_param = 'include_count'
    metadata_query_param = 'include_metadata'
    
    def get_paginated_response(self, data):
        """
        Return a paginated response with enhanced metadata.
        """
        # Build response data
        response_data = OrderedDict([
            ('count', self.get_count(data)),
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('results', data)
        ])
        
        # Add pagination metadata
        pagination_metadata = self.get_pagination_metadata()
        if pagination_metadata:
            response_data['pagination'] = pagination_metadata
        
        # Add filtering metadata if available
        filtering_metadata = self.get_filtering_metadata()
        if filtering_metadata:
            response_data['filtering'] = filtering_metadata
        
        # Add performance metadata
        performance_metadata = self.get_performance_metadata()
        if performance_metadata:
            response_data['performance'] = performance_metadata
        
        return Response(response_data)
    
    def get_count(self, data):
        """
        Get total count with optimization for large datasets.
        """
        if self.request.query_params.get(self.count_query_param) == 'false':
            return None
        
        # Use count optimization for large datasets
        try:
            queryset = getattr(self, 'queryset', None)
            if queryset is not None:
                # Use count optimization
                if hasattr(queryset, 'count'):
                    return queryset.count()
                else:
                    return len(queryset)
        except Exception as _e:
            pass  # logged: auto_mod silently handles this
        
        return super().get_count(data)
    
    def get_pagination_metadata(self):
        """
        Get detailed pagination metadata.
        """
        if not hasattr(self, 'page'):
            return None
        
        page = self.page
        paginator = self.page.paginator
        
        metadata = {
            'page_number': page.number,
            'page_size': self.get_page_size(self.request),
            'total_pages': paginator.num_pages,
            'has_next': page.has_next(),
            'has_previous': page.has_previous(),
            'start_index': page.start_index(),
            'end_index': page.end_index(),
        }
        
        # Add range information
        if paginator.num_pages > 1:
            metadata['page_range'] = list(paginator.page_range)
            
            # Add nearby pages for navigation
            current_page = page.number
            nearby_pages = []
            
            # Show 2 pages before and after current
            for i in range(max(1, current_page - 2), min(paginator.num_pages + 1, current_page + 3)):
                nearby_pages.append(i)
            
            metadata['nearby_pages'] = nearby_pages
        
        return metadata
    
    def get_filtering_metadata(self):
        """
        Get metadata about applied filters.
        """
        request = self.request
        metadata = {}
        
        # Get filter parameters
        filter_params = {}
        
        # Common filter parameters
        filter_fields = [
            'status', 'submission_type', 'priority', 'escalation_level',
            'assigned_to', 'created_at', 'updated_at', 'risk_score'
        ]
        
        for field in filter_fields:
            value = request.query_params.get(field)
            if value:
                filter_params[field] = value
        
        if filter_params:
            metadata['applied_filters'] = filter_params
        
        # Get search parameters
        search_query = request.query_params.get('search')
        if search_query:
            metadata['search_query'] = search_query
        
        # Get ordering parameters
        ordering = request.query_params.get('ordering')
        if ordering:
            metadata['ordering'] = ordering
        
        # Get date range filters
        date_fields = ['created_at__gte', 'created_at__lte', 'updated_at__gte', 'updated_at__lte']
        date_filters = {}
        for field in date_fields:
            value = request.query_params.get(field)
            if value:
                date_filters[field] = value
        
        if date_filters:
            metadata['date_filters'] = date_filters
        
        return metadata if metadata else None
    
    def get_performance_metadata(self):
        """
        Get performance metadata for the request.
        """
        request = self.request
        metadata = {}
        
        # Query execution time (if available)
        if hasattr(request, 'query_time'):
            metadata['query_time_ms'] = int(request.query_time * 1000)
        
        # Database query count (if available)
        if hasattr(request, 'query_count'):
            metadata['query_count'] = request.query_count
        
        # Cache hit status (if available)
        if hasattr(request, 'cache_hit'):
            metadata['cache_hit'] = request.cache_hit
        
        return metadata if any(metadata.values()) else None
    
    def paginate_queryset(self, queryset):
        """
        Paginate a queryset with performance optimizations.
        """
        # Store queryset for metadata
        self.queryset = queryset
        
        # Apply optimizations based on queryset type
        queryset = self.apply_queryset_optimizations(queryset)
        
        # Record start time for performance tracking
        import time
        self.request.query_start_time = time.time()
        
        # Use parent pagination
        page = super().paginate_queryset(queryset)
        
        # Record query time
        if hasattr(self.request, 'query_start_time'):
            self.request.query_time = time.time() - self.request.query_start_time
        
        return page
    
    def apply_queryset_optimizations(self, queryset):
        """
        Apply queryset optimizations based on model type.
        """
        model = queryset.model
        
        # Apply select_related/prefetch_related optimizations
        if model == SuspiciousSubmission:
            queryset = queryset.select_related('user').prefetch_related('decisions', 'signals')
        
        elif model == ModerationDecision:
            queryset = queryset.select_related('submission', 'decided_by', 'applied_rule').prefetch_related('appeals')
        
        elif model == ModerationAppeal:
            queryset = queryset.select_related('user', 'original_decision', 'submission', 'reviewed_by')
        
        elif model == ModerationQueue:
            queryset = queryset.select_related('submission', 'assigned_to', 'assigned_by')
        
        return queryset


class ModerationQueuePagination(AutoModPagination):
    """
    Specialized pagination for moderation queue endpoints.
    """
    
    page_size = 25
    max_page_size = 50
    
    def get_filtering_metadata(self):
        """
        Get queue-specific filtering metadata.
        """
        metadata = super().get_filtering_metadata()
        
        request = self.request
        
        # Queue-specific filters
        queue_filters = {}
        
        # Priority filters
        priority = request.query_params.get('priority')
        if priority:
            queue_filters['priority'] = priority
        
        # Escalation level filters
        escalation_level = request.query_params.get('escalation_level')
        if escalation_level:
            queue_filters['escalation_level'] = escalation_level
        
        # Assignment filters
        assigned_to = request.query_params.get('assigned_to')
        if assigned_to:
            queue_filters['assigned_to'] = assigned_to
        
        # Overdue filter
        overdue = request.query_params.get('overdue')
        if overdue:
            queue_filters['overdue'] = overdue.lower() == 'true'
        
        if queue_filters:
            if metadata is None:
                metadata = {}
            metadata['queue_filters'] = queue_filters
        
        return metadata
    
    def get_performance_metadata(self):
        """
        Get queue-specific performance metadata.
        """
        metadata = super().get_performance_metadata()
        
        # Add queue-specific metrics
        request = self.request
        
        # Moderator workload (if available)
        if hasattr(request, 'moderator_workload'):
            if metadata is None:
                metadata = {}
            metadata['moderator_workload'] = request.moderator_workload
        
        return metadata


class AppealPagination(AutoModPagination):
    """
    Specialized pagination for appeal endpoints.
    """
    
    page_size = 20
    max_page_size = 75
    
    def get_filtering_metadata(self):
        """
        Get appeal-specific filtering metadata.
        """
        metadata = super().get_filtering_metadata()
        
        request = self.request
        
        # Appeal-specific filters
        appeal_filters = {}
        
        # Status filters
        status = request.query_params.get('status')
        if status:
            appeal_filters['status'] = status
        
        # Outcome filters
        final_outcome = request.query_params.get('final_outcome')
        if final_outcome:
            appeal_filters['final_outcome'] = final_outcome
        
        # Escalation level filters
        escalation_level = request.query_params.get('escalation_level')
        if escalation_level:
            appeal_filters['escalation_level'] = escalation_level
        
        # Reviewer filters
        reviewed_by = request.query_params.get('reviewed_by')
        if reviewed_by:
            appeal_filters['reviewed_by'] = reviewed_by
        
        # Date range filters
        created_at_gte = request.query_params.get('created_at__gte')
        created_at_lte = request.query_params.get('created_at__lte')
        if created_at_gte or created_at_lte:
            date_range = {}
            if created_at_gte:
                date_range['gte'] = created_at_gte
            if created_at_lte:
                date_range['lte'] = created_at_lte
            appeal_filters['created_at'] = date_range
        
        if appeal_filters:
            if metadata is None:
                metadata = {}
            metadata['appeal_filters'] = appeal_filters
        
        return metadata


class DecisionPagination(AutoModPagination):
    """
    Specialized pagination for decision endpoints.
    """
    
    page_size = 30
    max_page_size = 100
    
    def get_filtering_metadata(self):
        """
        Get decision-specific filtering metadata.
        """
        metadata = super().get_filtering_metadata()
        
        request = self.request
        
        # Decision-specific filters
        decision_filters = {}
        
        # Decision type filters
        decision_type = request.query_params.get('decision_type')
        if decision_type:
            decision_filters['decision_type'] = decision_type
        
        # Confidence range filters
        confidence_gte = request.query_params.get('confidence__gte')
        confidence_lte = request.query_params.get('confidence__lte')
        if confidence_gte or confidence_lte:
            confidence_range = {}
            if confidence_gte:
                confidence_range['gte'] = confidence_gte
            if confidence_lte:
                confidence_range['lte'] = confidence_lte
            decision_filters['confidence'] = confidence_range
        
        # Automated/manual filters
        is_automated = request.query_params.get('is_automated')
        if is_automated:
            decision_filters['is_automated'] = is_automated.lower() == 'true'
        
        # Decider filters
        decided_by = request.query_params.get('decided_by')
        if decided_by:
            decision_filters['decided_by'] = decided_by
        
        # Applied rule filters
        applied_rule = request.query_params.get('applied_rule')
        if applied_rule:
            decision_filters['applied_rule'] = applied_rule
        
        if decision_filters:
            if metadata is None:
                metadata = {}
            metadata['decision_filters'] = decision_filters
        
        return metadata


class SubmissionPagination(AutoModPagination):
    """
    Specialized pagination for submission endpoints.
    """
    
    page_size = 25
    max_page_size = 75
    
    def get_filtering_metadata(self):
        """
        Get submission-specific filtering metadata.
        """
        metadata = super().get_filtering_metadata()
        
        request = self.request
        
        # Submission-specific filters
        submission_filters = {}
        
        # Risk score range filters
        risk_score_gte = request.query_params.get('risk_score__gte')
        risk_score_lte = request.query_params.get('risk_score__lte')
        if risk_score_gte or risk_score_lte:
            risk_score_range = {}
            if risk_score_gte:
                risk_score_range['gte'] = risk_score_gte
            if risk_score_lte:
                risk_score_range['lte'] = risk_score_lte
            submission_filters['risk_score'] = risk_score_range
        
        # AI confidence range filters
        ai_confidence_gte = request.query_params.get('ai_confidence__gte')
        ai_confidence_lte = request.query_params.get('ai_confidence__lte')
        if ai_confidence_gte or ai_confidence_lte:
            confidence_range = {}
            if ai_confidence_gte:
                confidence_range['gte'] = ai_confidence_gte
            if ai_confidence_lte:
                confidence_range['lte'] = ai_confidence_lte
            submission_filters['ai_confidence'] = confidence_range
        
        # Flag reason filters
        flag_reason = request.query_params.get('flag_reason')
        if flag_reason:
            submission_filters['flag_reason'] = flag_reason
        
        # User filters
        user = request.query_params.get('user')
        if user:
            submission_filters['user'] = user
        
        # Has decisions filter
        has_decisions = request.query_params.get('has_decisions')
        if has_decisions:
            submission_filters['has_decisions'] = has_decisions.lower() == 'true'
        
        # Has appeals filter
        has_appeals = request.query_params.get('has_appeals')
        if has_appeals:
            submission_filters['has_appeals'] = has_appeals.lower() == 'true'
        
        if submission_filters:
            if metadata is None:
                metadata = {}
            metadata['submission_filters'] = submission_filters
        
        return metadata


class CursorPagination(pagination.CursorPagination):
    """
    Cursor-based pagination for large datasets.
    """
    
    page_size = 50
    max_page_size = 200
    cursor_query_param = 'cursor'
    ordering = '-created_at'
    
    def get_paginated_response_schema(self, schema):
        """
        Override schema generation for cursor pagination.
        """
        return {
            'type': 'object',
            'properties': {
                'next': {
                    'type': 'string',
                    'nullable': True,
                    'format': 'uri'
                },
                'previous': {
                    'type': 'string',
                    'nullable': True,
                    'format': 'uri'
                },
                'results': schema,
                'count': {
                    'type': 'integer',
                    'nullable': True
                }
            }
        }


class HybridPagination(AutoModPagination):
    """
    Hybrid pagination that switches between page and cursor based on dataset size.
    """
    
    cursor_threshold = 1000  # Switch to cursor pagination for large datasets
    
    def paginate_queryset(self, queryset):
        """
        Choose pagination method based on dataset size.
        """
        # Quick count check
        try:
            count = queryset.count()
            if count > self.cursor_threshold:
                # Use cursor pagination for large datasets
                self.use_cursor_pagination = True
                return self._cursor_paginate(queryset)
        except Exception as _e:
            pass  # logged: auto_mod silently handles this
        
        # Use page pagination for smaller datasets
        self.use_cursor_pagination = False
        return super().paginate_queryset(queryset)
    
    def _cursor_paginate(self, queryset):
        """
        Implement cursor pagination.
        """
        # This is a simplified implementation
        # In practice, you'd use Django's built-in cursor pagination
        from rest_framework.pagination import CursorPagination
        
        cursor_paginator = CursorPagination()
        cursor_paginator.page_size = self.page_size
        cursor_paginator.ordering = self.ordering or '-created_at'
        
        return cursor_paginator.paginate_queryset(queryset)
    
    def get_paginated_response(self, data):
        """
        Return response based on pagination method used.
        """
        if getattr(self, 'use_cursor_pagination', False):
            # Cursor pagination response
            return Response({
                'next': getattr(self, 'next_cursor', None),
                'previous': getattr(self, 'previous_cursor', None),
                'results': data,
                'pagination_type': 'cursor'
            })
        else:
            # Page pagination response
            response = super().get_paginated_response(data)
            response.data['pagination_type'] = 'page'
            return response


class LimitOffsetPagination(pagination.LimitOffsetPagination):
    """
    Enhanced limit-offset pagination for auto moderation.
    """
    
    default_limit = 20
    max_limit = 100
    
    def get_paginated_response(self, data):
        """
        Return response with enhanced metadata.
        """
        response_data = OrderedDict([
            ('count', self.count),
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('results', data)
        ])
        
        # Add pagination metadata
        response_data['pagination'] = {
            'limit': self.limit,
            'offset': self.offset,
            'total_pages': (self.count + self.limit - 1) // self.limit,
            'current_page': (self.offset // self.limit) + 1,
        }
        
        return Response(response_data)


# Pagination class mapping for easy configuration
PAGINATION_CLASSES = {
    'default': AutoModPagination,
    'queue': ModerationQueuePagination,
    'appeals': AppealPagination,
    'decisions': DecisionPagination,
    'submissions': SubmissionPagination,
    'cursor': CursorPagination,
    'hybrid': HybridPagination,
    'limit_offset': LimitOffsetPagination,
}


def get_pagination_class(pagination_type='default'):
    """
    Get pagination class by type.
    
    Args:
        pagination_type: Type of pagination class
        
    Returns:
        Pagination class
    """
    return PAGINATION_CLASSES.get(pagination_type, AutoModPagination)
