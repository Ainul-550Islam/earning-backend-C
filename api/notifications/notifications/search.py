# earning_backend/api/notifications/search.py
"""
Search — Full-text and filtered search for notifications.

Supports:
  - Basic DB LIKE search (always available)
  - Django ORM Q-filter search (default)
  - PostgreSQL full-text search (if pg is available)
  - Elasticsearch integration (optional, for large datasets)

Usage:
    from notifications.search import notification_search

    results = notification_search.search(
        user=request.user,
        query='withdrawal',
        filters={'channel': 'push', 'is_read': False},
        page=1,
        page_size=20,
    )
"""

import logging
from typing import Dict, List, Optional

from django.db.models import Q, Value, TextField
from django.utils import timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Search result container
# ---------------------------------------------------------------------------

class SearchResult:
    """Container for notification search results."""

    def __init__(self, queryset, total: int, page: int, page_size: int, query: str = ''):
        self.queryset = queryset
        self.total = total
        self.page = page
        self.page_size = page_size
        self.query = query

    @property
    def total_pages(self) -> int:
        if self.page_size <= 0:
            return 1
        import math
        return math.ceil(self.total / self.page_size)

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages

    @property
    def has_prev(self) -> bool:
        return self.page > 1

    def to_dict(self) -> Dict:
        return {
            'total': self.total,
            'page': self.page,
            'page_size': self.page_size,
            'total_pages': self.total_pages,
            'has_next': self.has_next,
            'has_prev': self.has_prev,
            'query': self.query,
        }


# ---------------------------------------------------------------------------
# Main search service
# ---------------------------------------------------------------------------

class NotificationSearchService:
    """
    Full-featured notification search service.

    Provides:
    - Full-text search on title + message
    - Filter by channel, priority, type, read status, date
    - Sort by relevance, date, priority
    - Pagination
    - Saved search support
    """

    SORTABLE_FIELDS = {
        'created_at': '-created_at',
        '-created_at': '-created_at',
        'priority': '-priority_score',
        'title': 'title',
        'is_read': 'is_read',
        'relevance': '-created_at',  # Default relevance = recency
    }

    def search(
        self,
        user=None,
        query: str = '',
        filters: Optional[Dict] = None,
        sort: str = '-created_at',
        page: int = 1,
        page_size: int = 20,
        include_deleted: bool = False,
        admin_mode: bool = False,
    ) -> SearchResult:
        """
        Search notifications with full filtering and pagination.

        Args:
            user:           Filter to this user (None = all users, admin only).
            query:          Full-text search query string.
            filters:        Dict of field filters (channel, priority, is_read, etc.)
            sort:           Sort field. Prefix '-' for descending.
            page:           Page number (1-indexed).
            page_size:      Results per page.
            include_deleted: Include soft-deleted notifications.
            admin_mode:     If True, bypass user filter (admin use only).

        Returns:
            SearchResult with queryset and pagination metadata.
        """
        from notifications.models import Notification

        qs = Notification.objects.all()

        # Scope to user
        if user and not admin_mode:
            qs = qs.filter(user=user)

        # Exclude deleted
        if not include_deleted:
            qs = qs.filter(is_deleted=False)

        # Full-text query
        if query and query.strip():
            qs = self._apply_query(qs, query.strip())

        # Apply filters
        if filters:
            qs = self._apply_filters(qs, filters)

        # Sort
        qs = self._apply_sort(qs, sort)

        # Count before pagination (for total)
        total = qs.count()

        # Paginate
        offset = (page - 1) * page_size
        qs = qs[offset:offset + page_size]

        return SearchResult(
            queryset=qs,
            total=total,
            page=page,
            page_size=page_size,
            query=query,
        )

    def search_templates(
        self,
        query: str = '',
        filters: Optional[Dict] = None,
        page: int = 1,
        page_size: int = 20,
        active_only: bool = True,
    ) -> SearchResult:
        """Search NotificationTemplates."""
        from notifications.models import NotificationTemplate

        qs = NotificationTemplate.objects.all()
        if active_only:
            qs = qs.filter(is_active=True)

        if query:
            qs = qs.filter(
                Q(name__icontains=query) |
                Q(title_en__icontains=query) |
                Q(message_en__icontains=query) |
                Q(description__icontains=query)
            )

        if filters:
            if filters.get('channel'):
                qs = qs.filter(channel=filters['channel'])
            if filters.get('template_type'):
                qs = qs.filter(template_type=filters['template_type'])
            if filters.get('category'):
                qs = qs.filter(category=filters['category'])

        total = qs.count()
        offset = (page - 1) * page_size
        qs = qs.order_by('-usage_count', 'name')[offset:offset + page_size]

        return SearchResult(qs, total, page, page_size, query)

    def search_logs(
        self,
        notification_id: int = None,
        user_id: int = None,
        log_level: str = '',
        log_type: str = '',
        date_from=None,
        date_to=None,
        page: int = 1,
        page_size: int = 50,
    ) -> SearchResult:
        """Search NotificationLogs."""
        from notifications.models import NotificationLog

        qs = NotificationLog.objects.all()

        if notification_id:
            qs = qs.filter(notification_id=notification_id)
        if user_id:
            qs = qs.filter(notification__user_id=user_id)
        if log_level:
            qs = qs.filter(log_level=log_level)
        if log_type:
            qs = qs.filter(log_type=log_type)
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)

        qs = qs.select_related('notification').order_by('-created_at')
        total = qs.count()
        offset = (page - 1) * page_size
        return SearchResult(qs[offset:offset + page_size], total, page, page_size)

    def search_campaigns(
        self,
        query: str = '',
        status: str = '',
        page: int = 1,
        page_size: int = 20,
    ) -> SearchResult:
        """Search NotificationCampaigns."""
        from notifications.models import NotificationCampaign

        qs = NotificationCampaign.objects.all()
        if query:
            qs = qs.filter(Q(name__icontains=query) | Q(description__icontains=query))
        if status:
            qs = qs.filter(status=status)

        qs = qs.order_by('-created_at')
        total = qs.count()
        offset = (page - 1) * page_size
        return SearchResult(qs[offset:offset + page_size], total, page, page_size, query)

    def get_suggestions(self, user, query: str, limit: int = 5) -> List[Dict]:
        """
        Return auto-complete suggestions for a search query.
        Returns list of {'title': ..., 'id': ..., 'type': ...}
        """
        if not query or len(query) < 2:
            return []

        from notifications.models import Notification
        results = (
            Notification.objects
            .filter(user=user, is_deleted=False, title__icontains=query)
            .values('pk', 'title', 'notification_type')
            .order_by('-created_at')[:limit]
        )
        return [{'id': r['pk'], 'title': r['title'], 'type': r['notification_type']}
                for r in results]

    def get_recent_searches(self, user, limit: int = 5) -> List[str]:
        """Return user's recent search queries from cache."""
        from django.core.cache import cache
        key = f'notif:recent_searches:{user.pk}'
        return cache.get(key, [])[:limit]

    def save_search_query(self, user, query: str):
        """Save a search query to the user's recent searches."""
        from django.core.cache import cache
        key = f'notif:recent_searches:{user.pk}'
        recent = cache.get(key, [])
        if query and query not in recent:
            recent.insert(0, query)
            cache.set(key, recent[:10], 86400)  # Keep last 10 queries for 24h

    def clear_recent_searches(self, user):
        """Clear user's recent search history."""
        from django.core.cache import cache
        cache.delete(f'notif:recent_searches:{user.pk}')

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _apply_query(self, qs, query: str):
        """Apply full-text search to queryset."""
        # Try PostgreSQL full-text search
        try:
            from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
            vector = SearchVector('title', weight='A') + SearchVector('message', weight='B')
            search_query = SearchQuery(query)
            qs = qs.annotate(rank=SearchRank(vector, search_query)).filter(rank__gte=0.1).order_by('-rank')
            return qs
        except Exception:
            pass

        # Fallback: LIKE search
        return qs.filter(Q(title__icontains=query) | Q(message__icontains=query))

    def _apply_filters(self, qs, filters: Dict):
        """Apply filter dict to queryset."""
        if filters.get('channel'):
            qs = qs.filter(channel=filters['channel'])

        if filters.get('priority'):
            qs = qs.filter(priority=filters['priority'])

        if filters.get('notification_type'):
            qs = qs.filter(notification_type=filters['notification_type'])

        if 'is_read' in filters and filters['is_read'] is not None:
            qs = qs.filter(is_read=filters['is_read'])

        if 'is_pinned' in filters and filters['is_pinned'] is not None:
            qs = qs.filter(is_pinned=filters['is_pinned'])

        if 'is_archived' in filters and filters['is_archived'] is not None:
            qs = qs.filter(is_archived=filters['is_archived'])

        if filters.get('date_from'):
            qs = qs.filter(created_at__date__gte=filters['date_from'])

        if filters.get('date_to'):
            qs = qs.filter(created_at__date__lte=filters['date_to'])

        if filters.get('campaign_id'):
            qs = qs.filter(campaign_id=filters['campaign_id'])

        if filters.get('group_id'):
            qs = qs.filter(group_id=filters['group_id'])

        if filters.get('status'):
            qs = qs.filter(status=filters['status'])

        return qs

    def _apply_sort(self, qs, sort: str):
        """Apply sort field to queryset."""
        field = self.SORTABLE_FIELDS.get(sort, '-created_at')
        try:
            return qs.order_by(field)
        except Exception:
            return qs.order_by('-created_at')


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
notification_search = NotificationSearchService()
