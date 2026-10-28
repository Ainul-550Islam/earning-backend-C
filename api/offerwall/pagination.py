"""
api/offerwall/pagination.py

DRF Pagination classes for offerwall module.
Provides 3 pagination strategies:
  1. StandardPagination — 20 items/page (default for list views)
  2. LargePagination — 50 items/page (analytics, exports)
  3. SmallPagination — 10 items/page (mobile, lightweight)
"""

from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    """
    Standard pagination for offerwall list views.
    20 items per page, allows customization via ?page_size=N
    """
    page_size = 20
    page_size_query_param = 'page_size'
    page_size_query_description = 'Number of results to return per page'
    max_page_size = 100
    
    def get_paginated_response(self, data):
        from rest_framework.response import Response
        return Response({
            'count': self.page.paginator.count,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'total_pages': self.page.paginator.num_pages,
            'current_page': self.page.number,
            'page_size': self.get_page_size(self.request),
            'results': data
        })


class LargePagination(PageNumberPagination):
    """
    Large pagination for analytics, reports, and export views.
    50 items per page, allows up to 200 per page.
    """
    page_size = 50
    page_size_query_param = 'page_size'
    page_size_query_description = 'Number of results to return per page'
    max_page_size = 200
    
    def get_paginated_response(self, data):
        from rest_framework.response import Response
        return Response({
            'count': self.page.paginator.count,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'total_pages': self.page.paginator.num_pages,
            'current_page': self.page.number,
            'page_size': self.get_page_size(self.request),
            'results': data
        })


class SmallPagination(PageNumberPagination):
    """
    Small pagination for mobile clients or lightweight views.
    10 items per page, allows customization.
    Useful for low-bandwidth scenarios.
    """
    page_size = 10
    page_size_query_param = 'page_size'
    page_size_query_description = 'Number of results to return per page'
    max_page_size = 50
    
    def get_paginated_response(self, data):
        from rest_framework.response import Response
        return Response({
            'count': self.page.paginator.count,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'total_pages': self.page.paginator.num_pages,
            'current_page': self.page.number,
            'page_size': self.get_page_size(self.request),
            'results': data
        })
