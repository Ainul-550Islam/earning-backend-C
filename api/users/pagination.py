"""
api/users/pagination.py
Custom pagination classes for user endpoints
"""
from rest_framework.pagination import PageNumberPagination, CursorPagination
from rest_framework.response import Response


class UserListPagination(PageNumberPagination):
    """Admin user list-এর জন্য"""
    page_size            = 25
    page_size_query_param= 'page_size'
    max_page_size        = 100
    page_query_param     = 'page'

    def get_paginated_response(self, data):
        return Response({
            'pagination': {
                'total':    self.page.paginator.count,
                'pages':    self.page.paginator.num_pages,
                'current':  self.page.number,
                'per_page': self.get_page_size(self.request),
                'next':     self.get_next_link(),
                'previous': self.get_previous_link(),
            },
            'results': data,
        })


class ActivityLogPagination(CursorPagination):
    """Activity log — cursor-based (real-time feed)"""
    page_size            = 20
    ordering             = '-created_at'
    cursor_query_param   = 'cursor'

    def get_paginated_response(self, data):
        return Response({
            'next':     self.get_next_link(),
            'previous': self.get_previous_link(),
            'results':  data,
        })


class LeaderboardPagination(PageNumberPagination):
    """Leaderboard — ছোট page"""
    page_size     = 50
    max_page_size = 100

    def get_paginated_response(self, data):
        return Response({
            'total':   self.page.paginator.count,
            'page':    self.page.number,
            'results': data,
        })


class SmallResultsPagination(PageNumberPagination):
    """Devices, sessions, API keys list-এর জন্য"""
    page_size     = 10
    max_page_size = 50

    def get_paginated_response(self, data):
        return Response({
            'count':   self.page.paginator.count,
            'next':    self.get_next_link(),
            'previous':self.get_previous_link(),
            'results': data,
        })
