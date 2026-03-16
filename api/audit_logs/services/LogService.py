"""
Service for creating, managing, and querying audit logs
"""

import uuid
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from django.db import transaction, models
from django.db.models import Q, Count, Avg, Max, Min
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.conf import settings

from ..models import AuditLog, AuditLogAction, AuditLogLevel, AuditLogConfig
from ..serializers import AuditLogCreateSerializer
from core.utils import send_async_task

User = get_user_model()
logger = logging.getLogger(__name__)


class LogService:
    """Main service for audit log operations"""
    
    def __init__(self):
        self.batch_size = 100  # Batch size for bulk operations
        self.default_retention_days = 365
    
    def create_log(self, **kwargs) -> Optional[AuditLog]:
        """
        Create a new audit log entry synchronously
        
        Args:
            **kwargs: Log data including:
                - user: User object or ID
                - action: AuditLogAction value
                - level: AuditLogLevel value
                - message: Log message
                - old_data: Data before change (JSON)
                - new_data: Data after change (JSON)
                - metadata: Additional context (JSON)
                - user_ip: User IP address
                - user_agent: User agent string
                - resource_type: Type of resource being acted upon
                - resource_id: ID of resource
                - content_object: Generic foreign key object
                - correlation_id: Correlation ID for tracing
                - request_method: HTTP method
                - request_path: Request path
                - status_code: HTTP status code
                - response_time_ms: Response time in milliseconds
                - success: Boolean indicating success
        
        Returns:
            AuditLog instance or None if creation failed
        """
        try:
            # Prepare log data
            log_data = self._prepare_log_data(kwargs)
            
            # Validate using serializer
            serializer = AuditLogCreateSerializer(data=log_data)
            if not serializer.is_valid():
                logger.error(f"Invalid log data: {serializer.errors}")
                return None
            
            # Create log entry
            log_entry = AuditLog.objects.create(**serializer.validated_data)
            
            # Apply configuration rules
            self._apply_configuration_rules(log_entry)
            
            # Check for alert rules
            self._check_alert_rules(log_entry)
            
            # Cache recent logs
            self._cache_recent_log(log_entry)
            
            logger.debug(f"Created audit log: {log_entry.id} - {log_entry.action}")
            return log_entry
            
        except Exception as e:
            logger.error(f"Failed to create audit log: {e}", exc_info=True)
            # Create a minimal log for the failure
            self._log_creation_failure(e, kwargs)
            return None
    
    def create_log_async(self, **kwargs) -> str:
        """
        Create audit log asynchronously (for better performance)
        
        Returns:
            Task ID for tracking
        """
        try:
            # Prepare log data
            log_data = self._prepare_log_data(kwargs)
            
            # Generate task ID
            task_id = str(uuid.uuid4())
            log_data['task_id'] = task_id
            
            # Send to async task queue
            send_async_task(
                'api.audit_logs.tasks.create_audit_log_task',
                log_data=log_data
            )
            
            return task_id
            
        except Exception as e:
            logger.error(f"Failed to queue async audit log: {e}", exc_info=True)
            # Fall back to synchronous creation
            self.create_log(**kwargs)
            return str(uuid.uuid4())
    
    def create_bulk_logs(self, logs_data: List[Dict]) -> Tuple[int, List[AuditLog]]:
        """
        Create multiple audit logs in bulk
        
        Args:
            logs_data: List of log data dictionaries
        
        Returns:
            Tuple of (created_count, list_of_logs)
        """
        created_count = 0
        created_logs = []
        
        try:
            with transaction.atomic():
                for i in range(0, len(logs_data), self.batch_size):
                    batch = logs_data[i:i + self.batch_size]
                    log_instances = []
                    
                    for log_data in batch:
                        prepared_data = self._prepare_log_data(log_data)
                        serializer = AuditLogCreateSerializer(data=prepared_data)
                        
                        if serializer.is_valid():
                            log_instances.append(AuditLog(**serializer.validated_data))
                        else:
                            logger.warning(f"Invalid log data in bulk: {serializer.errors}")
                    
                    if log_instances:
                        created = AuditLog.objects.bulk_create(log_instances)
                        created_count += len(created)
                        created_logs.extend(created)
            
            logger.info(f"Created {created_count} audit logs in bulk")
            return created_count, created_logs
            
        except Exception as e:
            logger.error(f"Failed to create bulk audit logs: {e}", exc_info=True)
            return created_count, created_logs
    
    def get_log(self, log_id: str) -> Optional[AuditLog]:
        """Get audit log by ID"""
        try:
            return AuditLog.objects.get(id=log_id)
        except AuditLog.DoesNotExist:
            return None
    
    def get_logs_by_user(self, user_id: str, limit: int = 100, **filters) -> List[AuditLog]:
        """Get audit logs for a specific user"""
        queryset = AuditLog.objects.filter(
            models.Q(user_id=user_id) | models.Q(anonymous_id=user_id)
        )
        
        queryset = self._apply_filters(queryset, filters)
        return list(queryset.order_by('-timestamp')[:limit])
    
    def get_logs_by_action(self, action: str, **filters) -> List[AuditLog]:
        """Get audit logs for a specific action"""
        queryset = AuditLog.objects.filter(action=action)
        queryset = self._apply_filters(queryset, filters)
        return list(queryset.order_by('-timestamp'))
    
    def get_logs_by_resource(self, resource_type: str, resource_id: str, **filters) -> List[AuditLog]:
        """Get audit logs for a specific resource"""
        queryset = AuditLog.objects.filter(
            resource_type=resource_type,
            resource_id=resource_id
        )
        queryset = self._apply_filters(queryset, filters)
        return list(queryset.order_by('-timestamp'))
    
    def get_logs_by_correlation_id(self, correlation_id: str) -> List[AuditLog]:
        """Get all logs with a specific correlation ID"""
        return list(AuditLog.objects.filter(
            correlation_id=correlation_id
        ).order_by('timestamp'))
    
    def search_logs(self, search_query: str, **filters) -> List[AuditLog]:
        """
        Search audit logs by message, user info, etc.
        
        Args:
            search_query: Search string
            **filters: Additional filters
        
        Returns:
            List of matching audit logs
        """
        queryset = AuditLog.objects.filter(
            Q(message__icontains=search_query) |
            Q(user__email__icontains=search_query) |
            Q(user__username__icontains=search_query) |
            Q(user_ip__icontains=search_query) |
            Q(resource_id__icontains=search_query)
        )
        
        queryset = self._apply_filters(queryset, filters)
        return list(queryset.order_by('-timestamp')[:100])
    
    def get_statistics(self, start_date=None, end_date=None, group_by=None):
        """
        Get audit log statistics
        
        Args:
            start_date: Start date for filtering
            end_date: End date for filtering
            group_by: Field to group by ('action', 'level', 'user', 'hour', 'day')
        
        Returns:
            Dictionary of statistics
        """
        # Build base queryset
        queryset = AuditLog.objects.all()
        
        if start_date:
            queryset = queryset.filter(timestamp__gte=start_date)
        if end_date:
            queryset = queryset.filter(timestamp__lte=end_date)
        
        # Basic statistics
        stats = {
            'total': queryset.count(),
            'by_level': dict(queryset.values('level').annotate(count=Count('id')).values_list('level', 'count')),
            'by_action': dict(queryset.values('action').annotate(count=Count('id')).values_list('action', 'count')),
            'success_rate': queryset.filter(success=True).count() / max(queryset.count(), 1) * 100,
            'avg_response_time': queryset.exclude(response_time_ms__isnull=True)
                                  .aggregate(avg=Avg('response_time_ms'))['avg'] or 0,
        }
        
        # Group by time if requested
        if group_by in ['hour', 'day']:
            if group_by == 'hour':
                time_format = 'YYYY-MM-DD HH24:00'
            else:  # day
                time_format = 'YYYY-MM-DD'
            
            # Using Django's Trunc functions
            from django.db.models.functions import TruncHour, TruncDay
            trunc_func = TruncHour if group_by == 'hour' else TruncDay
            
            time_groups = queryset.annotate(
                time_group=trunc_func('timestamp')
            ).values('time_group').annotate(
                count=Count('id')
            ).order_by('time_group')
            
            stats['time_groups'] = list(time_groups)
        
        # Top users
        top_users = queryset.filter(user__isnull=False).values(
            'user__id', 'user__email', 'user__username'
        ).annotate(
            count=Count('id'),
            last_activity=Max('timestamp')
        ).order_by('-count')[:10]
        
        stats['top_users'] = list(top_users)
        
        # Error distribution
        error_logs = queryset.filter(level__in=['ERROR', 'CRITICAL'])
        stats['error_count'] = error_logs.count()
        stats['top_errors'] = list(
            error_logs.values('action', 'message')
            .annotate(count=Count('id'))
            .order_by('-count')[:10]
        )
        
        return stats
    
    def export_logs(self, queryset, format='json', fields=None):
        """
        Export logs in specified format
        
        Args:
            queryset: QuerySet of logs to export
            format: Export format ('json', 'csv', 'excel', 'pdf')
            fields: List of fields to include
        
        Returns:
            Export data in requested format
        """
        from .LogExporter import LogExporter
        exporter = LogExporter()
        return exporter.export(queryset, format, fields)
    
    def archive_old_logs(self, days_old=365, chunk_size=10000):
        """
        Archive logs older than specified days
        
        Args:
            days_old: Age in days to archive
            chunk_size: Number of logs to archive per chunk
        
        Returns:
            Tuple of (archived_count, archive_path)
        """
        from .LogExporter import LogExporter
        
        cutoff_date = timezone.now() - timedelta(days=days_old)
        logs_to_archive = AuditLog.objects.filter(
            timestamp__lt=cutoff_date,
            archived=False
        )
        
        total_logs = logs_to_archive.count()
        
        if total_logs == 0:
            return 0, None
        
        exporter = LogExporter()
        archive_path = exporter.create_archive(
            start_date=None,
            end_date=cutoff_date,
            compression='zip'
        )
        
        # Mark logs as archived
        logs_to_archive.update(archived=True)
        
        return total_logs, archive_path
    
    def cleanup_old_logs(self, days_old=730):
        """
        Permanently delete logs older than specified days
        
        Args:
            days_old: Age in days to delete
        
        Returns:
            Number of logs deleted
        """
        cutoff_date = timezone.now() - timedelta(days=days_old)
        
        # Get logs to delete
        logs_to_delete = AuditLog.objects.filter(
            timestamp__lt=cutoff_date
        )
        
        count = logs_to_delete.count()
        
        # Delete in chunks to avoid timeouts
        deleted = 0
        while True:
            chunk = logs_to_delete[:1000]
            if not chunk.exists():
                break
            
            chunk_ids = list(chunk.values_list('id', flat=True))
            
            # Delete related data if any
            AuditLog.objects.filter(id__in=chunk_ids).delete()
            
            deleted += len(chunk_ids)
            logger.info(f"Deleted {deleted}/{count} old logs")
        
        logger.info(f"Cleaned up {deleted} logs older than {days_old} days")
        return deleted
    
    def _prepare_log_data(self, data: Dict) -> Dict:
        """Prepare and validate log data"""
        prepared = data.copy()
        
        # Ensure required fields
        if 'timestamp' not in prepared:
            prepared['timestamp'] = timezone.now()
        
        if 'correlation_id' not in prepared:
            prepared['correlation_id'] = str(uuid.uuid4())
        
        # Handle user field (can be User instance or ID)
        if 'user' in prepared:
            user = prepared['user']
            if isinstance(user, User):
                prepared['user_id'] = user.id
                del prepared['user']
            elif isinstance(user, str):
                prepared['user_id'] = user
        
        # Handle content object
        if 'content_object' in prepared:
            obj = prepared.pop('content_object')
            if obj:
                prepared['content_type'] = ContentType.objects.get_for_model(obj)
                prepared['object_id'] = str(obj.pk)
        
        # Convert JSON fields to dict if they are strings
        json_fields = ['old_data', 'new_data', 'metadata', 'request_params', 
                      'request_headers', 'request_body', 'response_body']
        
        for field in json_fields:
            if field in prepared and isinstance(prepared[field], str):
                try:
                    prepared[field] = json.loads(prepared[field])
                except (json.JSONDecodeError, TypeError):
                    prepared[field] = {'raw': str(prepared[field])[:1000]}
        
        # Truncate long strings
        if 'message' in prepared and len(prepared['message']) > 2000:
            prepared['message'] = prepared['message'][:2000] + '...'
        
        if 'error_message' in prepared and prepared['error_message'] and len(prepared['error_message']) > 2000:
            prepared['error_message'] = prepared['error_message'][:2000] + '...'
        
        return prepared
    
    def _apply_filters(self, queryset, filters):
        """Apply filters to queryset"""
        if not filters:
            return queryset
        
        # Date filters
        if 'start_date' in filters:
            queryset = queryset.filter(timestamp__gte=filters['start_date'])
        if 'end_date' in filters:
            queryset = queryset.filter(timestamp__lte=filters['end_date'])
        
        # Level filter
        if 'level' in filters:
            if isinstance(filters['level'], list):
                queryset = queryset.filter(level__in=filters['level'])
            else:
                queryset = queryset.filter(level=filters['level'])
        
        # Action filter
        if 'action' in filters:
            if isinstance(filters['action'], list):
                queryset = queryset.filter(action__in=filters['action'])
            else:
                queryset = queryset.filter(action=filters['action'])
        
        # Success filter
        if 'success' in filters:
            queryset = queryset.filter(success=filters['success'])
        
        # User IP filter
        if 'user_ip' in filters:
            queryset = queryset.filter(user_ip=filters['user_ip'])
        
        return queryset
    
    def _apply_configuration_rules(self, log_entry: AuditLog):
        """Apply configuration rules to log entry"""
        try:
            config = AuditLogConfig.objects.filter(action=log_entry.action).first()
            if config:
                # Apply retention policy
                log_entry.retention_days = config.retention_days
                
                # Apply notification rules
                if config.notify_admins and log_entry.level in ['ERROR', 'CRITICAL', 'SECURITY']:
                    self._notify_admins(log_entry, config)
                
                if config.notify_users and log_entry.user:
                    self._notify_user(log_entry, config)
                
                log_entry.save(update_fields=['retention_days'])
                
        except Exception as e:
            logger.error(f"Failed to apply config rules: {e}")
    
    def _check_alert_rules(self, log_entry: AuditLog):
        """Check if log entry triggers any alert rules"""
        try:
            from ..models import AuditAlertRule
            
            active_rules = AuditAlertRule.objects.filter(
                enabled=True,
                severity__lte=log_entry.level  # Assuming severity levels are comparable
            )
            
            for rule in active_rules:
                if self._rule_matches(log_entry, rule.condition):
                    self._trigger_alert(rule, log_entry)
                    
        except Exception as e:
            logger.error(f"Failed to check alert rules: {e}")
    
    def _rule_matches(self, log_entry: AuditLog, condition: Dict) -> bool:
        """Check if log entry matches alert rule condition"""
        try:
            field = condition.get('field')
            operator = condition.get('operator')
            value = condition.get('value')
            
            if not field or not operator:
                return False
            
            # Get field value from log entry
            field_value = getattr(log_entry, field, None)
            
            # Apply operator
            if operator == 'equals':
                return field_value == value
            elif operator == 'not_equals':
                return field_value != value
            elif operator == 'contains':
                return value in str(field_value) if field_value else False
            elif operator == 'greater_than':
                return field_value > value
            elif operator == 'less_than':
                return field_value < value
            elif operator == 'in':
                return field_value in value
            elif operator == 'not_in':
                return field_value not in value
            else:
                return False
                
        except Exception:
            return False
    
    def _trigger_alert(self, rule, log_entry):
        """Trigger alert for matched rule"""
        try:
            # Update rule stats
            rule.trigger_count += 1
            rule.last_triggered = timezone.now()
            rule.save()
            
            # Execute action based on rule configuration
            action = rule.action
            action_config = rule.action_config
            
            if action == 'EMAIL':
                self._send_alert_email(rule, log_entry, action_config)
            elif action == 'WEBHOOK':
                self._call_webhook(rule, log_entry, action_config)
            elif action == 'CREATE_TICKET':
                self._create_support_ticket(rule, log_entry, action_config)
            
            # Log the alert trigger
            self.create_log(
                action='ALERT_TRIGGERED',
                level='WARNING',
                message=f"Alert '{rule.name}' triggered by log {log_entry.id}",
                resource_type='AuditAlertRule',
                resource_id=str(rule.id),
                metadata={
                    'log_id': str(log_entry.id),
                    'rule_id': str(rule.id),
                    'rule_name': rule.name,
                    'condition': rule.condition
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to trigger alert: {e}")
    
    def _send_alert_email(self, rule, log_entry, config):
        """Send alert email"""
        # Implementation depends on your email service
        pass
    
    def _call_webhook(self, rule, log_entry, config):
        """Call webhook with alert data"""
        # Implementation depends on your needs
        pass
    
    def _create_support_ticket(self, rule, log_entry, config):
        """Create support ticket for alert"""
        # Implementation depends on your ticketing system
        pass
    
    def _notify_admins(self, log_entry, config):
        """Notify administrators about important log entry"""
        # Implementation would send email/SMS/notification to admins
        pass
    
    def _notify_user(self, log_entry, config):
        """Notify user about their log entry"""
        # Implementation would send notification to user
        pass
    
    def _cache_recent_log(self, log_entry: AuditLog):
        """Cache recent log for quick access"""
        cache_key = f"audit_recent_{log_entry.user_id if log_entry.user else 'anonymous'}"
        recent_logs = cache.get(cache_key, [])
        
        # Keep only last 10 logs
        recent_logs.insert(0, {
            'id': str(log_entry.id),
            'action': log_entry.action,
            'message': log_entry.message,
            'timestamp': log_entry.timestamp.isoformat(),
            'level': log_entry.level
        })
        
        if len(recent_logs) > 10:
            recent_logs = recent_logs[:10]
        
        cache.set(cache_key, recent_logs, timeout=3600)  # 1 hour
    
    def _log_creation_failure(self, error, original_data):
        """Create a minimal log when log creation fails"""
        try:
            # Use Django's logging as fallback
            logger.critical(
                "Failed to create audit log",
                extra={
                    'error': str(error),
                    'original_data': original_data,
                    'timestamp': timezone.now().isoformat()
                }
            )
        except Exception:
            # Ultimate fallback - print to console
            print(f"CRITICAL: Failed to create audit log: {error}")
    
    def get_recent_activity(self, user_id=None, limit=20):
        """Get recent activity for dashboard"""
        cache_key = f"recent_activity_{user_id or 'all'}_{limit}"
        cached = cache.get(cache_key)
        
        if cached is not None:
            return cached
        
        queryset = AuditLog.objects.all().order_by('-timestamp')
        
        if user_id:
            queryset = queryset.filter(
                Q(user_id=user_id) | Q(anonymous_id=user_id)
            )
        
        recent = list(queryset[:limit])
        
        # Cache for 1 minute
        cache.set(cache_key, recent, timeout=60)
        
        return recent
    
    def get_user_activity_summary(self, user_id, days=30):
        """Get summary of user activity over time"""
        cache_key = f"user_activity_summary_{user_id}_{days}"
        cached = cache.get(cache_key)
        
        if cached is not None:
            return cached
        
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        queryset = AuditLog.objects.filter(
            Q(user_id=user_id) | Q(anonymous_id=user_id),
            timestamp__range=(start_date, end_date)
        )
        
        summary = {
            'total_actions': queryset.count(),
            'successful_actions': queryset.filter(success=True).count(),
            'failed_actions': queryset.filter(success=False).count(),
            'by_action': dict(queryset.values('action').annotate(count=Count('id')).values_list('action', 'count')),
            'by_level': dict(queryset.values('level').annotate(count=Count('id')).values_list('level', 'count')),
            'first_activity': queryset.earliest('timestamp').timestamp if queryset.exists() else None,
            'last_activity': queryset.latest('timestamp').timestamp if queryset.exists() else None,
            'avg_response_time': queryset.exclude(response_time_ms__isnull=True)
                                  .aggregate(avg=Avg('response_time_ms'))['avg'] or 0,
        }
        
        # Cache for 5 minutes
        cache.set(cache_key, summary, timeout=300)
        
        return summary


# Singleton instance
log_service = LogService()