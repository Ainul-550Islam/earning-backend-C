# api/offer_inventory/reporting_audit/audit_logs.py
"""
Audit Log Service — Comprehensive immutable audit trail.
Tracks all admin actions, model changes, and security events.
"""
import csv
import logging
from datetime import timedelta
from django.utils import timezone
from django.http import HttpResponse

logger = logging.getLogger(__name__)


class AuditLogService:
    """Full audit log lifecycle — write, query, export."""

    @staticmethod
    def log_action(user, action: str, model_name: str = '',
                    object_id: str = '', changes: dict = None,
                    ip: str = '', ua: str = '') -> object:
        """Write an audit log entry."""
        from api.offer_inventory.models import AuditLog
        return AuditLog.objects.create(
            user      =user,
            action    =action,
            model_name=model_name,
            object_id =str(object_id),
            changes   =changes or {},
            ip_address=ip,
            user_agent=ua[:500],
        )

    @staticmethod
    def get_user_audit_trail(user, days: int = 30, limit: int = 100) -> list:
        """Paginated audit history for a user."""
        from api.offer_inventory.models import AuditLog
        since = timezone.now() - timedelta(days=days)
        return list(
            AuditLog.objects.filter(user=user, created_at__gte=since)
            .order_by('-created_at')
            .values('action', 'model_name', 'object_id', 'ip_address', 'created_at')
            [:limit]
        )

    @staticmethod
    def get_model_audit_trail(model_name: str, object_id: str) -> list:
        """All changes to a specific model instance."""
        from api.offer_inventory.models import AuditLog
        return list(
            AuditLog.objects.filter(model_name=model_name, object_id=str(object_id))
            .order_by('-created_at')
            .values('user__username', 'action', 'changes', 'ip_address', 'created_at')
            [:50]
        )

    @staticmethod
    def get_recent_admin_actions(hours: int = 24, limit: int = 100) -> list:
        """Recent admin actions for security review."""
        from api.offer_inventory.models import AuditLog
        since = timezone.now() - timedelta(hours=hours)
        return list(
            AuditLog.objects.filter(
                created_at__gte=since,
                action__in=['DELETE', 'POST', 'PATCH', 'PUT']
            )
            .select_related('user')
            .order_by('-created_at')
            .values('user__username', 'action', 'model_name', 'object_id',
                    'ip_address', 'created_at')
            [:limit]
        )

    @staticmethod
    def export_audit_csv(days: int = 30) -> HttpResponse:
        """Export audit logs as CSV."""
        from api.offer_inventory.models import AuditLog
        since    = timezone.now() - timedelta(days=days)
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="audit_log.csv"'
        response.write('\ufeff')
        writer = csv.writer(response)
        writer.writerow(['Date', 'User', 'Action', 'Model', 'Object ID', 'IP'])
        for log in AuditLog.objects.filter(
            created_at__gte=since
        ).select_related('user').order_by('-created_at')[:10000]:
            writer.writerow([
                log.created_at.strftime('%Y-%m-%d %H:%M'),
                log.user.username if log.user else '',
                log.action, log.model_name, log.object_id, log.ip_address,
            ])
        return response

    @staticmethod
    def count_by_action(days: int = 7) -> dict:
        """Count audit events by action type."""
        from api.offer_inventory.models import AuditLog
        from django.db.models import Count
        since = timezone.now() - timedelta(days=days)
        return dict(
            AuditLog.objects.filter(created_at__gte=since)
            .values_list('action')
            .annotate(count=Count('id'))
        )
