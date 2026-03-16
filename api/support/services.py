# api/support/services.py
"""
Business logic for support. Move complex logic out of views.
"""
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class SupportService:
    """Service for ticket and support operations."""

    @staticmethod
    def get_ticket_stats() -> Dict[str, int]:
        """Return counts by ticket status."""
        try:
            from .models import SupportTicket
            from django.db.models import Count
            qs = SupportTicket.objects.values('status').annotate(count=Count('id'))
            return {row['status']: row['count'] for row in qs}
        except Exception:
            return {}
