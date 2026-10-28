# api/cms/services_new/ContentCalendarService.py
"""Content Calendar / Scheduling Service — CMS owns this."""
import logging
from typing import Dict, List, Any
from django.utils import timezone
logger = logging.getLogger(__name__)


class ContentCalendarService:

    @staticmethod
    def schedule(content_type: str, content_id: int, title: str,
                 scheduled_at, created_by=None, note: str = '',
                 expires_at=None) -> Dict:
        from api.cms.models_new.site_config import ContentSchedule
        schedule = ContentSchedule.objects.create(
            title=title, content_type=content_type, content_id=content_id,
            status='scheduled', scheduled_at=scheduled_at,
            expires_at=expires_at, note=note, created_by=created_by,
        )
        return {
            'id': schedule.id, 'uuid': str(schedule.uuid),
            'title': schedule.title, 'status': schedule.status,
            'scheduled_at': schedule.scheduled_at.isoformat(),
        }

    @staticmethod
    def get_upcoming(days: int = 30, content_type: str = None) -> List[Dict]:
        from api.cms.models_new.site_config import ContentSchedule
        from datetime import timedelta
        cutoff = timezone.now() + timedelta(days=days)
        qs = ContentSchedule.objects.filter(
            status='scheduled', scheduled_at__lte=cutoff,
            scheduled_at__gte=timezone.now(),
        ).order_by('scheduled_at')
        if content_type:
            qs = qs.filter(content_type=content_type)
        return [{
            'id': s.id, 'title': s.title, 'content_type': s.content_type,
            'content_id': s.content_id, 'scheduled_at': s.scheduled_at.isoformat(),
            'expires_at': s.expires_at.isoformat() if s.expires_at else None,
            'note': s.note,
        } for s in qs]

    @staticmethod
    def get_calendar(year: int, month: int) -> Dict[str, List]:
        from api.cms.models_new.site_config import ContentSchedule
        import calendar as cal
        from datetime import date
        first_day = date(year, month, 1)
        last_day = date(year, month, cal.monthrange(year, month)[1])
        schedules = ContentSchedule.objects.filter(
            scheduled_at__date__gte=first_day,
            scheduled_at__date__lte=last_day,
        ).order_by('scheduled_at')
        calendar_data = {}
        for s in schedules:
            day_key = s.scheduled_at.strftime('%Y-%m-%d')
            if day_key not in calendar_data:
                calendar_data[day_key] = []
            calendar_data[day_key].append({
                'id': s.id, 'title': s.title,
                'content_type': s.content_type, 'status': s.status,
                'time': s.scheduled_at.strftime('%H:%M'),
            })
        return calendar_data

    @staticmethod
    def process_due_schedules() -> int:
        """Celery task: publish any scheduled content that is due."""
        from api.cms.models_new.site_config import ContentSchedule
        due = ContentSchedule.objects.filter(
            status='scheduled', scheduled_at__lte=timezone.now()
        )
        published_count = 0
        for schedule in due:
            try:
                ContentCalendarService._publish_scheduled(schedule)
                schedule.status = 'published'
                schedule.published_at = timezone.now()
                schedule.save(update_fields=['status', 'published_at'])
                published_count += 1
            except Exception as e:
                logger.error(f"Failed to publish schedule #{schedule.id}: {e}")
        logger.info(f"Content calendar: published {published_count} items")
        return published_count

    @staticmethod
    def _publish_scheduled(schedule):
        """Publish a single scheduled content item."""
        ct = schedule.content_type
        cid = schedule.content_id
        if not cid:
            return
        if ct == 'blog_post':
            from api.cms.models_new.blog import BlogPost
            BlogPost.objects.filter(pk=cid).update(status='published', published_at=timezone.now())
        elif ct == 'announcement':
            from api.cms.models_new.extras import Announcement
            Announcement.objects.filter(pk=cid).update(is_active=True)
        elif ct == 'popup':
            from api.cms.models_new.popup import Popup
            Popup.objects.filter(pk=cid).update(is_active=True)

    @staticmethod
    def cancel_schedule(schedule_id: int) -> bool:
        from api.cms.models_new.site_config import ContentSchedule
        try:
            ContentSchedule.objects.filter(id=schedule_id, status='scheduled').update(status='cancelled')
            return True
        except Exception:
            return False
