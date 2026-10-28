"""
Backup Module Search
Full-text and faceted search capabilities for backup records.
"""

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass, field

from django.db.models import Q, QuerySet

logger = logging.getLogger(__name__)


@dataclass
class SearchFilter:
    """Represents a single search filter"""
    field: str
    value: Any
    operator: str = "exact"   # exact | contains | gte | lte | in | isnull


@dataclass
class SearchQuery:
    """Structured search query for backups"""
    text: Optional[str] = None
    filters: List[SearchFilter] = field(default_factory=list)
    ordering: List[str] = field(default_factory=lambda: ["-created_at"])
    page: int = 1
    page_size: int = 20

    def add_filter(self, field: str, value: Any, operator: str = "exact") -> "SearchQuery":
        self.filters.append(SearchFilter(field=field, value=value, operator=operator))
        return self


@dataclass
class SearchResult:
    """Paginated search result"""
    items: List[Any]
    total_count: int
    page: int
    page_size: int
    query: SearchQuery

    @property
    def total_pages(self) -> int:
        if self.page_size == 0:
            return 0
        import math
        return math.ceil(self.total_count / self.page_size)

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages

    @property
    def has_previous(self) -> bool:
        return self.page > 1


class BackupSearchEngine:
    """
    Search engine for backup records.
    Supports text search across name/notes and structured filters.
    """

    TEXT_SEARCH_FIELDS = ["name__icontains", "notes__icontains", "tags__icontains"]

    FILTER_OPERATORS = {
        "exact": lambda field, val: Q(**{field: val}),
        "contains": lambda field, val: Q(**{f"{field}__icontains": val}),
        "gte": lambda field, val: Q(**{f"{field}__gte": val}),
        "lte": lambda field, val: Q(**{f"{field}__lte": val}),
        "in": lambda field, val: Q(**{f"{field}__in": val}),
        "isnull": lambda field, val: Q(**{f"{field}__isnull": val}),
    }

    def __init__(self, base_queryset: Optional[QuerySet] = None):
        self.base_queryset = base_queryset

    def _get_base_qs(self) -> QuerySet:
        if self.base_queryset is not None:
            return self.base_queryset
        from api.backup.models import Backup
        return Backup.objects.all()

    def search(self, query: SearchQuery) -> SearchResult:
        qs = self._get_base_qs()

        # Text search
        if query.text and query.text.strip():
            text_q = Q()
            for field_lookup in self.TEXT_SEARCH_FIELDS:
                text_q |= Q(**{field_lookup: query.text.strip()})
            qs = qs.filter(text_q)

        # Structured filters
        for f in query.filters:
            operator_fn = self.FILTER_OPERATORS.get(f.operator)
            if operator_fn:
                qs = qs.filter(operator_fn(f.field, f.value))
            else:
                logger.warning("Unknown search operator: %s", f.operator)

        # Ordering
        if query.ordering:
            qs = qs.order_by(*query.ordering)

        total_count = qs.count()
        offset = (query.page - 1) * query.page_size
        items = list(qs[offset: offset + query.page_size])

        return SearchResult(
            items=items,
            total_count=total_count,
            page=query.page,
            page_size=query.page_size,
            query=query,
        )

    def search_by_text(self, text: str, page: int = 1, page_size: int = 20) -> SearchResult:
        return self.search(SearchQuery(text=text, page=page, page_size=page_size))

    def search_by_date_range(self, start: datetime, end: datetime) -> SearchResult:
        q = SearchQuery()
        q.add_filter("created_at", start, "gte")
        q.add_filter("created_at", end, "lte")
        return self.search(q)

    def search_by_status(self, status: str) -> SearchResult:
        q = SearchQuery()
        q.add_filter("status", status)
        return self.search(q)
