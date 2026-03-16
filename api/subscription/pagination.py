"""pagination.py – Custom pagination classes for subscription endpoints."""
from rest_framework.pagination import PageNumberPagination, CursorPagination
from rest_framework.response import Response

from .constants import PAYMENT_PAGE_SIZE, PLAN_PAGE_SIZE, SUBSCRIPTION_PAGE_SIZE


class SubscriptionPageNumberPagination(PageNumberPagination):
    page_size = SUBSCRIPTION_PAGE_SIZE
    page_size_query_param = "page_size"
    max_page_size = 100

    def get_paginated_response(self, data):
        return Response(
            {
                "count": self.page.paginator.count,
                "total_pages": self.page.paginator.num_pages,
                "current_page": self.page.number,
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
                "results": data,
            }
        )

    def get_paginated_response_schema(self, schema):
        return {
            "type": "object",
            "properties": {
                "count": {"type": "integer"},
                "total_pages": {"type": "integer"},
                "current_page": {"type": "integer"},
                "next": {"type": "string", "nullable": True},
                "previous": {"type": "string", "nullable": True},
                "results": schema,
            },
        }


class PlanPagination(SubscriptionPageNumberPagination):
    page_size = PLAN_PAGE_SIZE


class PaymentPagination(SubscriptionPageNumberPagination):
    page_size = PAYMENT_PAGE_SIZE


class SubscriptionCursorPagination(CursorPagination):
    """
    Cursor-based pagination for real-time feeds or very large datasets.
    Provides stable, tamper-proof pages useful for webhook logs.
    """
    page_size = SUBSCRIPTION_PAGE_SIZE
    ordering = "-created_at"
    cursor_query_param = "cursor"