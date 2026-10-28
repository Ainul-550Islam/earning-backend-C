# api/admin_panel/services/AdminActivityService.py
"""Service for logging and querying AdminActivity."""
import logging
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


class AdminActivityService:

    @staticmethod
    def log(actor, action: str, model_name: str = '', object_id: str = '',
            object_repr: str = '', changes: dict = None, ip: str = '',
            user_agent: str = '', path: str = '', method: str = '',
            response_code: int = None, status: str = 'success', extra: dict = None):
        """Create an AdminActivity log entry."""
        try:
            from ..models.activity import AdminActivity
            return AdminActivity.log(
                actor=actor, action=action, model_name=model_name,
                object_id=object_id, object_repr=object_repr,
                changes=changes or {}, ip=ip, user_agent=user_agent,
                path=path, method=method, response_code=response_code,
                status=status, extra=extra or {},
            )
        except Exception as e:
            logger.error(f"AdminActivityService.log error: {e}")
            return None

    @staticmethod
    def get_recent(days: int = 7, actor=None, action: str = None, limit: int = 100):
        """Query recent admin activities."""
        from ..models.activity import AdminActivity
        cutoff = timezone.now() - timedelta(days=days)
        qs = AdminActivity.objects.filter(created_at__gte=cutoff).select_related('actor')
        if actor:
            qs = qs.filter(actor=actor)
        if action:
            qs = qs.filter(action=action)
        return qs.order_by('-created_at')[:limit]

    @staticmethod
    def get_summary(days: int = 7) -> dict:
        """Get activity summary stats."""
        from ..models.activity import AdminActivity
        from django.db.models import Count
        cutoff = timezone.now() - timedelta(days=days)
        qs = AdminActivity.objects.filter(created_at__gte=cutoff)
        return {
            'total': qs.count(),
            'by_action': list(qs.values('action').annotate(count=Count('id')).order_by('-count')[:10]),
            'by_status': list(qs.values('status').annotate(count=Count('id'))),
            'by_actor': list(qs.values('actor__username').annotate(count=Count('id')).order_by('-count')[:10]),
        }

    @staticmethod
    def export_csv(queryset, output_path: str) -> int:
        """Export activity queryset to CSV. Returns row count."""
        import csv
        count = 0
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['id', 'actor', 'action', 'model', 'object_id', 'status', 'ip', 'created_at'])
            for activity in queryset.iterator():
                writer.writerow([
                    activity.pk,
                    activity.actor.username if activity.actor else '',
                    activity.action, activity.model_name, activity.object_id,
                    activity.status, activity.ip,
                    activity.created_at.isoformat(),
                ])
                count += 1
        return count