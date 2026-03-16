# api/audit_logs/services.py
"""
Business logic for audit logs.
"""
import logging
import json
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Q, Count

logger = logging.getLogger(__name__)


class AuditLogService:
    """Service for writing and querying audit logs."""

    @staticmethod
    def log_action(
        user_id: Optional[int],
        action: str,
        message: str = "",
        metadata: Optional[Dict] = None
    ) -> Optional[Any]:
        """Create an audit log entry."""
        try:
            from .models import AuditLog, AuditLogLevel, AuditLogAction
            valid_actions = [c[0] for c in AuditLogAction.choices]
            action_value = action if action in valid_actions else AuditLogAction.API_CALL
            return AuditLog.objects.create(
                user_id=user_id,
                action=action_value,
                message=message or action,
                level=AuditLogLevel.INFO,
                metadata=metadata or {},
            )
        except Exception as e:
            logger.debug("Audit log write failed: %s", e)
            return None


class LogService:
    """Extended log service with level support."""

    @staticmethod
    def info(user_id, action, message="", metadata=None):
        return LogService._write(user_id, action, message, 'INFO', metadata)

    @staticmethod
    def warning(user_id, action, message="", metadata=None):
        return LogService._write(user_id, action, message, 'WARNING', metadata)

    @staticmethod
    def error(user_id, action, message="", metadata=None):
        return LogService._write(user_id, action, message, 'ERROR', metadata)

    @staticmethod
    def critical(user_id, action, message="", metadata=None):
        return LogService._write(user_id, action, message, 'CRITICAL', metadata)

    @staticmethod
    def _write(user_id, action, message, level, metadata):
        try:
            from .models import AuditLog, AuditLogAction
            valid_actions = [c[0] for c in AuditLogAction.choices]
            action_value = action if action in valid_actions else AuditLogAction.API_CALL
            return AuditLog.objects.create(
                user_id=user_id,
                action=action_value,
                message=message or action,
                level=level,
                metadata=metadata or {},
            )
        except Exception as e:
            logger.debug("LogService write failed: %s", e)
            return None


class AuditQuery:
    """Query helpers for audit logs."""

    @staticmethod
    def get_user_logs(user_id: int, days: int = 30):
        """Get logs for a specific user."""
        try:
            from .models import AuditLog
            since = timezone.now() - timedelta(days=days)
            return AuditLog.objects.filter(
                user_id=user_id,
                created_at__gte=since
            ).order_by('-created_at')
        except Exception as e:
            logger.debug("AuditQuery.get_user_logs failed: %s", e)
            return []

    @staticmethod
    def get_action_logs(action: str, days: int = 7):
        """Get logs for a specific action."""
        try:
            from .models import AuditLog
            since = timezone.now() - timedelta(days=days)
            return AuditLog.objects.filter(
                action=action,
                created_at__gte=since
            ).order_by('-created_at')
        except Exception as e:
            logger.debug("AuditQuery.get_action_logs failed: %s", e)
            return []

    @staticmethod
    def get_error_logs(days: int = 1):
        """Get ERROR and CRITICAL logs."""
        try:
            from .models import AuditLog
            since = timezone.now() - timedelta(days=days)
            return AuditLog.objects.filter(
                level__in=['ERROR', 'CRITICAL'],
                created_at__gte=since
            ).order_by('-created_at')
        except Exception as e:
            logger.debug("AuditQuery.get_error_logs failed: %s", e)
            return []

    @staticmethod
    def get_stats(days: int = 30) -> Dict:
        """Get audit log statistics."""
        try:
            from .models import AuditLog
            since = timezone.now() - timedelta(days=days)
            qs = AuditLog.objects.filter(created_at__gte=since)
            return {
                'total': qs.count(),
                'by_level': dict(qs.values_list('level').annotate(c=Count('id')).values_list('level', 'c')),
                'by_action': dict(qs.values_list('action').annotate(c=Count('id')).values_list('action', 'c')),
            }
        except Exception as e:
            logger.debug("AuditQuery.get_stats failed: %s", e)
            return {}


class LogExporter:
    """Export audit logs to different formats."""

    @staticmethod
    def to_json(queryset) -> str:
        """Export logs as JSON string."""
        try:
            data = list(queryset.values(
                'id', 'user_id', 'action', 'level', 'message', 'metadata', 'created_at'
            ))
            # Convert datetime to string
            for item in data:
                if isinstance(item.get('created_at'), datetime):
                    item['created_at'] = item['created_at'].isoformat()
            return json.dumps(data, default=str, indent=2)
        except Exception as e:
            logger.debug("LogExporter.to_json failed: %s", e)
            return "[]"

    @staticmethod
    def to_csv(queryset) -> str:
        """Export logs as CSV string."""
        try:
            import csv
            import io
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(['ID', 'User ID', 'Action', 'Level', 'Message', 'Created At'])
            for log in queryset.values_list('id', 'user_id', 'action', 'level', 'message', 'created_at'):
                writer.writerow(log)
            return output.getvalue()
        except Exception as e:
            logger.debug("LogExporter.to_csv failed: %s", e)
            return ""

    @staticmethod
    def to_dict_list(queryset) -> List[Dict]:
        """Export logs as list of dicts."""
        try:
            return list(queryset.values(
                'id', 'user_id', 'action', 'level', 'message', 'metadata', 'created_at'
            ))
        except Exception as e:
            logger.debug("LogExporter.to_dict_list failed: %s", e)
            return []



# # api/audit_logs/services.py
# """
# Business logic for audit logs. Move complex logic out of views/middleware.
# """
# import logging
# from typing import Optional, Dict, Any

# logger = logging.getLogger(__name__)


# class AuditLogService:
#     """Service for writing and querying audit logs."""

#     @staticmethod
#     def log_action(user_id: Optional[int], action: str, message: str = "", metadata: Optional[Dict] = None) -> Optional[Any]:
#         """Create an audit log entry. action should be a valid AuditLogAction choice (e.g. API_CALL)."""
#         try:
#             from .models import AuditLog, AuditLogLevel, AuditLogAction
#             valid_actions = [c[0] for c in AuditLogAction.choices]
#             action_value = action if action in valid_actions else AuditLogAction.API_CALL
#             return AuditLog.objects.create(
#                 user_id=user_id,
#                 action=action_value,
#                 message=message or action,
#                 level=AuditLogLevel.INFO,
#                 metadata=metadata or {},
#             )
#         except Exception as e:
#             logger.debug("Audit log: %s", e)
#             return None
