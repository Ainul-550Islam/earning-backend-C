# api/cms/viewsets/cms_viewset_base.py
"""
Professional DRF base classes: throttling, pagination, filtering, schema.
All CMS ViewSets inherit from these.
"""
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework.pagination import PageNumberPagination
from rest_framework import filters


# ── Throttling ───────────────────────────────────────────────────

class CMSAnonThrottle(AnonRateThrottle):
    """100 requests/hour for anonymous users."""
    rate = '100/hour'


class CMSUserThrottle(UserRateThrottle):
    """1000 requests/hour for authenticated users."""
    rate = '1000/hour'


class CMSPostbackThrottle(UserRateThrottle):
    """500 postbacks/day for CPAlead endpoints."""
    scope = 'cpalead_postback'
    rate = '500/day'


class CMSWriteThrottle(UserRateThrottle):
    """60 writes/minute for POST/PUT/DELETE."""
    scope = 'cms_write'
    rate = '60/minute'


# ── Pagination ───────────────────────────────────────────────────

class CMSPagePagination(PageNumberPagination):
    """
    Standard CMS pagination.
    Usage: GET /api/cms/blog/?page=2&page_size=20
    """
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100
    page_query_param = 'page'

    def get_paginated_response(self, data):
        from rest_framework.response import Response
        return Response({
            'count': self.page.paginator.count,
            'total_pages': self.page.paginator.num_pages,
            'current_page': self.page.number,
            'page_size': self.get_page_size(self.request),
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'results': data,
        })


class CMSSmallPagination(PageNumberPagination):
    """For small result sets: 10 per page."""
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 50


class CMSLargePagination(PageNumberPagination):
    """For larger result sets: 50 per page."""
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200


# ── Filter backends ──────────────────────────────────────────────

class CMSFilterBackend(filters.BaseFilterBackend):
    """
    CMS-specific filter: ?status=active&created_after=2024-01-01
    """
    def filter_queryset(self, request, queryset, view):
        params = request.query_params

        # Status filter
        if params.get('status') and hasattr(queryset.model, 'status'):
            queryset = queryset.filter(status=params['status'])

        # is_active filter
        if params.get('is_active') is not None:
            queryset = queryset.filter(is_active=params['is_active'].lower() == 'true')

        # Date range
        if params.get('created_after'):
            try:
                from django.utils.dateparse import parse_datetime, parse_date
                dt = parse_datetime(params['created_after']) or parse_date(params['created_after'])
                if dt:
                    queryset = queryset.filter(created_at__gte=dt)
            except Exception:
                pass

        if params.get('created_before'):
            try:
                from django.utils.dateparse import parse_datetime, parse_date
                dt = parse_datetime(params['created_before']) or parse_date(params['created_before'])
                if dt:
                    queryset = queryset.filter(created_at__lte=dt)
            except Exception:
                pass

        return queryset


# ── Base ViewSet mixin ───────────────────────────────────────────

class CMSViewSetMixin:
    """
    Mixin for all CMS ViewSets.
    Provides: throttling + pagination + filtering + error handling.
    """
    throttle_classes = [CMSAnonThrottle, CMSUserThrottle]
    pagination_class = CMSPagePagination
    filter_backends = [
        filters.SearchFilter,
        filters.OrderingFilter,
        CMSFilterBackend,
    ]

    def get_throttles(self):
        """Override per-action throttling."""
        if self.request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            return [CMSWriteThrottle()]
        return super().get_throttles()

    def handle_exception(self, exc):
        """Unified error response format."""
        import logging
        logger = logging.getLogger(__name__)
        from rest_framework import exceptions
        from rest_framework.response import Response
        from rest_framework import status

        if isinstance(exc, (exceptions.NotAuthenticated, exceptions.AuthenticationFailed)):
            return Response(
                {'error': 'authentication_required', 'message': str(exc)},
                status=status.HTTP_401_UNAUTHORIZED
            )
        if isinstance(exc, exceptions.PermissionDenied):
            return Response(
                {'error': 'permission_denied', 'message': str(exc)},
                status=status.HTTP_403_FORBIDDEN
            )
        if isinstance(exc, exceptions.NotFound):
            return Response(
                {'error': 'not_found', 'message': str(exc)},
                status=status.HTTP_404_NOT_FOUND
            )
        if isinstance(exc, exceptions.Throttled):
            return Response(
                {'error': 'rate_limited', 'retry_after': exc.wait},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )
        logger.error(f"[ViewSet] Unhandled exception: {exc}", exc_info=True)
        return super().handle_exception(exc)
