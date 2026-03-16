from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from .constants import CODE_PAGE_SIZE, INVENTORY_PAGE_SIZE, ITEM_PAGE_SIZE


class StandardPagination(PageNumberPagination):
    page_size = ITEM_PAGE_SIZE
    page_size_query_param = "page_size"
    max_page_size = 200

    def get_paginated_response(self, data):
        return Response({
            "count": self.page.paginator.count,
            "total_pages": self.page.paginator.num_pages,
            "current_page": self.page.number,
            "next": self.get_next_link(),
            "previous": self.get_previous_link(),
            "results": data,
        })


class InventoryPagination(StandardPagination):
    page_size = INVENTORY_PAGE_SIZE


class CodePagination(StandardPagination):
    page_size = CODE_PAGE_SIZE
