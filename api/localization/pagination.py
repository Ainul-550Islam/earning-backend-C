# pagination.py — Custom DRF pagination classes
from rest_framework.pagination import (
    PageNumberPagination, CursorPagination, LimitOffsetPagination
)
from rest_framework.response import Response
import logging

logger = logging.getLogger(__name__)


class LocalizationPagePagination(PageNumberPagination):
    """Standard page-based pagination for most endpoints"""
    page_size = 20
    page_size_query_param = 'per_page'
    max_page_size = 200
    page_query_param = 'page'

    def get_paginated_response(self, data):
        return Response({
            'success': True,
            'data': data,
            'pagination': {
                'total': self.page.paginator.count,
                'page': self.page.number,
                'pages': self.page.paginator.num_pages,
                'per_page': self.get_page_size(self.request),
                'has_next': self.page.has_next(),
                'has_prev': self.page.has_previous(),
                'next': self.get_next_link(),
                'prev': self.get_previous_link(),
            }
        })

    def get_paginated_response_schema(self, schema):
        return {
            'type': 'object',
            'required': ['success', 'data', 'pagination'],
            'properties': {
                'success': {'type': 'boolean'},
                'data': schema,
                'pagination': {
                    'type': 'object',
                    'properties': {
                        'total': {'type': 'integer'},
                        'page': {'type': 'integer'},
                        'pages': {'type': 'integer'},
                        'per_page': {'type': 'integer'},
                    }
                }
            }
        }


class TranslationCursorPagination(CursorPagination):
    """Cursor-based pagination for real-time translation feeds"""
    page_size = 50
    max_page_size = 500
    ordering = '-created_at'
    cursor_query_param = 'cursor'

    def get_paginated_response(self, data):
        return Response({
            'success': True,
            'data': data,
            'pagination': {
                'count': len(data),
                'next_cursor': self.get_next_link(),
                'prev_cursor': self.get_previous_link(),
            }
        })


class LargeResultPagination(PageNumberPagination):
    """For bulk exports — larger pages"""
    page_size = 200
    page_size_query_param = 'per_page'
    max_page_size = 1000


class LanguageListPagination(PageNumberPagination):
    """Languages list — default 100, they're usually all shown"""
    page_size = 100
    page_size_query_param = 'per_page'
    max_page_size = 300

    def get_paginated_response(self, data):
        return Response({
            'success': True,
            'data': data,
            'pagination': {
                'total': self.page.paginator.count,
                'page': self.page.number,
                'pages': self.page.paginator.num_pages,
                'per_page': self.get_page_size(self.request),
            }
        })


class CityPagination(PageNumberPagination):
    """Cities — smaller pages, many records"""
    page_size = 50
    page_size_query_param = 'per_page'
    max_page_size = 200

    def get_paginated_response(self, data):
        return Response({
            'success': True,
            'data': data,
            'pagination': {
                'total': self.page.paginator.count,
                'page': self.page.number,
                'pages': self.page.paginator.num_pages,
                'per_page': self.get_page_size(self.request),
            }
        })


class AnalyticsPagination(PageNumberPagination):
    """Analytics — smaller pages, ordered by date"""
    page_size = 30
    page_size_query_param = 'per_page'
    max_page_size = 100
    ordering = '-date'
