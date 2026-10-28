"""
api/support/cpa/announcement_system.py
FILE 4 — Network Announcement System

Admin network-wide announcements দিতে পারবে।
Support portal, widget, email-এ দেখাবে।
"""
import logging
from django.utils import timezone
logger = logging.getLogger(__name__)

class AnnouncementSystem:
    def get_active(self, tier: str = None) -> list:
        try:
            from api.support.cpa.models import NetworkAnnouncement
            now = timezone.now()
            qs  = NetworkAnnouncement.objects.filter(
                is_active=True,
                show_in_portal=True,
            ).filter(
                models.Q(starts_at__isnull=True) | models.Q(starts_at__lte=now)
            ).filter(
                models.Q(ends_at__isnull=True) | models.Q(ends_at__gte=now)
            ).order_by('-created_at')[:5]

            return [{
                'id':      a.id,
                'title':   a.title,
                'content': a.content,
                'type':    a.type,
                'color':   {'info':'#0ea5e9','warning':'#ca8a04','maintenance':'#dc2626','update':'#16a34a'}.get(a.type,'#6366f1'),
            } for a in qs]
        except Exception:
            return []

    def create(self, title: str, content: str, ann_type: str, created_by, **kwargs) -> object:
        from api.support.cpa.models import NetworkAnnouncement
        return NetworkAnnouncement.objects.create(
            title=title, content=content, type=ann_type, created_by=created_by,
            is_active=True, **kwargs,
        )

from django.db import models
announcement_system = AnnouncementSystem()