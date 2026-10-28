"""
Resource classes for alerts app
"""
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django.db import transaction
from django.core.cache import cache
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)


class AlertResource:
    """Base resource for alert operations"""
    
    def __init__(self, request):
        self.request = request
        self.user = request.user
    
    def has_permission(self, permission: str) -> bool:
        """Check if user has specific permission"""
        return (
            self.user.is_authenticated and
            (self.user.is_staff or self.user.has_perm(f'alerts.{permission}'))
        )
    
    def validate_request_data(self, required_fields: List[str]) -> Dict[str, Any]:
        """Validate request data and return errors"""
        errors = {}
        data = self.request.data
        
        for field in required_fields:
            if field not in data or data[field] in [None, '']:
                errors[field] = f'{field} is required'
        
        return errors
    
    def success_response(self, data: Any = None, message: str = "Success") -> Response:
        """Create success response"""
        return Response({
            'success': True,
            'message': message,
            'data': data,
            'timestamp': timezone.now().isoformat()
        })
    
    def error_response(self, message: str, status_code: int = 400, details: Any = None) -> Response:
        """Create error response"""
        response_data = {
            'success': False,
            'message': message,
            'timestamp': timezone.now().isoformat()
        }
        
        if details:
            response_data['details'] = details
        
        return Response(response_data, status=status_code)


class AlertRuleResource(AlertResource):
    """Resource for alert rule operations"""
    
    def create_rule(self) -> Response:
        """Create a new alert rule"""
        if not self.has_permission('manage_alert_rules'):
            return self.error_response(
                "You don't have permission to manage alert rules",
                status_code=403
            )
        
        # Validate required fields
        required_fields = ['name', 'alert_type', 'severity', 'threshold_value', 'time_window_minutes']
        errors = self.validate_request_data(required_fields)
        
        if errors:
            return self.error_response(
                "Validation failed",
                details=errors
            )
        
        try:
            from .models import AlertRule
            from .validator import AlertValidator
            
            data = self.request.data
            
            # Validate data
            AlertValidator.validate_threshold_value(
                data['threshold_value'], 
                data['alert_type']
            )
            AlertValidator.validate_time_window(data['time_window_minutes'])
            AlertValidator.validate_severity(data['severity'])
            AlertValidator.validate_alert_type(data['alert_type'])
            
            # Create rule
            rule = AlertRule.objects.create(
                name=data['name'],
                alert_type=data['alert_type'],
                severity=data['severity'],
                description=data.get('description', ''),
                threshold_value=data['threshold_value'],
                time_window_minutes=data['time_window_minutes'],
                cooldown_minutes=data.get('cooldown_minutes', 30),
                is_active=data.get('is_active', True),
                created_by=self.user,
                email_recipients=data.get('email_recipients', ''),
                telegram_chat_id=data.get('telegram_chat_id', ''),
                sms_recipients=data.get('sms_recipients', ''),
                send_email=data.get('send_email', False),
                send_telegram=data.get('send_telegram', False),
                send_sms=data.get('send_sms', False)
            )
            
            return self.success_response(
                {'rule_id': rule.id},
                "Alert rule created successfully"
            )
        
        except Exception as e:
            logger.error(f"Error creating alert rule: {e}")
            return self.error_response(
                "Failed to create alert rule",
                status_code=500
            )
    
    def update_rule(self, rule_id: int) -> Response:
        """Update an existing alert rule"""
        if not self.has_permission('manage_alert_rules'):
            return self.error_response(
                "You don't have permission to manage alert rules",
                status_code=403
            )
        
        try:
            from .models import AlertRule
            rule = AlertRule.objects.get(id=rule_id)
            
            # Check ownership or admin
            if not self.user.is_staff and rule.created_by != self.user:
                return self.error_response(
                    "You can only update your own rules",
                    status_code=403
                )
            
            # Update fields
            data = self.request.data
            updatable_fields = [
                'name', 'description', 'threshold_value', 'time_window_minutes',
                'cooldown_minutes', 'is_active', 'email_recipients',
                'telegram_chat_id', 'sms_recipients', 'send_email',
                'send_telegram', 'send_sms'
            ]
            
            for field in updatable_fields:
                if field in data:
                    setattr(rule, field, data[field])
            
            rule.save()
            
            return self.success_response(
                {'rule_id': rule.id},
                "Alert rule updated successfully"
            )
        
        except AlertRule.DoesNotExist:
            return self.error_response(
                "Alert rule not found",
                status_code=404
            )
        except Exception as e:
            logger.error(f"Error updating alert rule: {e}")
            return self.error_response(
                "Failed to update alert rule",
                status_code=500
            )
    
    def delete_rule(self, rule_id: int) -> Response:
        """Delete an alert rule"""
        if not self.has_permission('manage_alert_rules'):
            return self.error_response(
                "You don't have permission to manage alert rules",
                status_code=403
            )
        
        try:
            from .models import AlertRule
            rule = AlertRule.objects.get(id=rule_id)
            
            # Check ownership or admin
            if not self.user.is_staff and rule.created_by != self.user:
                return self.error_response(
                    "You can only delete your own rules",
                    status_code=403
                )
            
            rule.delete()
            
            return self.success_response(
                message="Alert rule deleted successfully"
            )
        
        except AlertRule.DoesNotExist:
            return self.error_response(
                "Alert rule not found",
                status_code=404
            )
        except Exception as e:
            logger.error(f"Error deleting alert rule: {e}")
            return self.error_response(
                "Failed to delete alert rule",
                status_code=500
            )
    
    def test_rule(self, rule_id: int) -> Response:
        """Test an alert rule"""
        if not self.has_permission('manage_alert_rules'):
            return self.error_response(
                "You don't have permission to manage alert rules",
                status_code=403
            )
        
        try:
            from .models import AlertRule, AlertLog
            rule = AlertRule.objects.get(id=rule_id)
            
            # Create test alert
            test_alert = AlertLog.objects.create(
                rule=rule,
                trigger_value=rule.threshold_value * 1.5,
                threshold_value=rule.threshold_value,
                message=f"Test alert for rule: {rule.name}",
                details={
                    'test': True,
                    'triggered_by': self.user.username,
                    'timestamp': timezone.now().isoformat()
                }
            )
            
            return self.success_response(
                {
                    'alert_id': test_alert.id,
                    'rule_name': rule.name
                },
                "Test alert created successfully"
            )
        
        except AlertRule.DoesNotExist:
            return self.error_response(
                "Alert rule not found",
                status_code=404
            )
        except Exception as e:
            logger.error(f"Error testing alert rule: {e}")
            return self.error_response(
                "Failed to test alert rule",
                status_code=500
            )


class AlertLogResource(AlertResource):
    """Resource for alert log operations"""
    
    def resolve_alert(self, alert_id: int) -> Response:
        """Resolve an alert"""
        if not self.has_permission('resolve_alerts'):
            return self.error_response(
                "You don't have permission to resolve alerts",
                status_code=403
            )
        
        try:
            from .models import AlertLog
            alert = AlertLog.objects.get(id=alert_id)
            
            if alert.is_resolved:
                return self.error_response(
                    "Alert is already resolved",
                    status_code=400
                )
            
            # Resolve alert
            alert.is_resolved = True
            alert.resolved_at = timezone.now()
            alert.resolved_by = self.user
            alert.resolution_note = self.request.data.get('resolution_note', '')
            alert.save()
            
            return self.success_response(
                {
                    'alert_id': alert.id,
                    'resolved_at': alert.resolved_at.isoformat()
                },
                "Alert resolved successfully"
            )
        
        except AlertLog.DoesNotExist:
            return self.error_response(
                "Alert not found",
                status_code=404
            )
        except Exception as e:
            logger.error(f"Error resolving alert: {e}")
            return self.error_response(
                "Failed to resolve alert",
                status_code=500
            )
    
    def acknowledge_alert(self, alert_id: int) -> Response:
        """Acknowledge an alert"""
        if not self.has_permission('acknowledge_alerts'):
            return self.error_response(
                "You don't have permission to acknowledge alerts",
                status_code=403
            )
        
        try:
            from .models import AlertLog
            alert = AlertLog.objects.get(id=alert_id)
            
            if alert.acknowledged_at:
                return self.error_response(
                    "Alert is already acknowledged",
                    status_code=400
                )
            
            # Acknowledge alert
            alert.acknowledged_at = timezone.now()
            alert.acknowledged_by = self.user
            alert.save(update_fields=['acknowledged_at', 'acknowledged_by'])
            
            return self.success_response(
                {
                    'alert_id': alert.id,
                    'acknowledged_at': alert.acknowledged_at.isoformat()
                },
                "Alert acknowledged successfully"
            )
        
        except AlertLog.DoesNotExist:
            return self.error_response(
                "Alert not found",
                status_code=404
            )
        except Exception as e:
            logger.error(f"Error acknowledging alert: {e}")
            return self.error_response(
                "Failed to acknowledge alert",
                status_code=500
            )
    
    def escalate_alert(self, alert_id: int) -> Response:
        """Escalate an alert"""
        if not self.has_permission('escalate_alerts'):
            return self.error_response(
                "You don't have permission to escalate alerts",
                status_code=403
            )
        
        try:
            from .models import AlertLog
            alert = AlertLog.objects.get(id=alert_id)
            
            escalation_level = self.request.data.get('escalation_level', 1)
            
            # Escalate alert
            alert.escalation_level = escalation_level
            alert.escalated_at = timezone.now()
            alert.save(update_fields=['escalation_level', 'escalated_at'])
            
            return self.success_response(
                {
                    'alert_id': alert.id,
                    'escalation_level': escalation_level,
                    'escalated_at': alert.escalated_at.isoformat()
                },
                "Alert escalated successfully"
            )
        
        except AlertLog.DoesNotExist:
            return self.error_response(
                "Alert not found",
                status_code=404
            )
        except Exception as e:
            logger.error(f"Error escalating alert: {e}")
            return self.error_response(
                "Failed to escalate alert",
                status_code=500
            )


class NotificationResource(AlertResource):
    """Resource for notification operations"""
    
    def retry_notification(self, notification_id: int) -> Response:
        """Retry a failed notification"""
        if not self.has_permission('manage_notifications'):
            return self.error_response(
                "You don't have permission to manage notifications",
                status_code=403
            )
        
        try:
            from .models import Notification
            notification = Notification.objects.get(id=notification_id)
            
            if notification.status != 'failed':
                return self.error_response(
                    "Only failed notifications can be retried",
                    status_code=400
                )
            
            # Reset to pending for retry
            notification.status = 'pending'
            notification.retry_count += 1
            notification.last_retry_at = timezone.now()
            notification.save(update_fields=['status', 'retry_count', 'last_retry_at'])
            
            return self.success_response(
                {
                    'notification_id': notification.id,
                    'retry_count': notification.retry_count
                },
                "Notification queued for retry"
            )
        
        except Notification.DoesNotExist:
            return self.error_response(
                "Notification not found",
                status_code=404
            )
        except Exception as e:
            logger.error(f"Error retrying notification: {e}")
            return self.error_response(
                "Failed to retry notification",
                status_code=500
            )
    
    def get_notification_status(self, notification_id: int) -> Response:
        """Get notification delivery status"""
        if not self.has_permission('view_notifications'):
            return self.error_response(
                "You don't have permission to view notifications",
                status_code=403
            )
        
        try:
            from .models import Notification
            notification = Notification.objects.get(id=notification_id)
            
            status_data = {
                'id': notification.id,
                'type': notification.notification_type,
                'recipient': notification.recipient,
                'status': notification.status,
                'created_at': notification.created_at.isoformat(),
                'sent_at': notification.sent_at.isoformat() if notification.sent_at else None,
                'delivered_at': notification.delivered_at.isoformat() if notification.delivered_at else None,
                'read_at': notification.read_at.isoformat() if notification.read_at else None,
                'retry_count': notification.retry_count,
                'last_retry_at': notification.last_retry_at.isoformat() if notification.last_retry_at else None,
                'error_message': notification.error_message,
                'response_time_ms': notification.response_time_ms
            }
            
            return self.success_response(status_data)
        
        except Notification.DoesNotExist:
            return self.error_response(
                "Notification not found",
                status_code=404
            )
        except Exception as e:
            logger.error(f"Error getting notification status: {e}")
            return self.error_response(
                "Failed to get notification status",
                status_code=500
            )


class SystemResource(AlertResource):
    """Resource for system operations"""
    
    def get_system_health(self) -> Response:
        """Get system health status"""
        if not self.has_permission('view_system_health'):
            return self.error_response(
                "You don't have permission to view system health",
                status_code=403
            )
        
        try:
            from .models import SystemHealthCheck, SystemMetrics
            
            # Get health checks
            health_checks = SystemHealthCheck.objects.filter(
                is_active=True
            ).order_by('-checked_at')[:20]
            
            # Calculate overall health
            if health_checks.exists():
                healthy_count = health_checks.filter(status='healthy').count()
                total_count = health_checks.count()
                health_percentage = (healthy_count / total_count) * 100
            else:
                health_percentage = 0
            
            # Get latest metrics
            latest_metrics = SystemMetrics.objects.order_by('-timestamp').first()
            
            metrics_data = {}
            if latest_metrics:
                metrics_data = {
                    'timestamp': latest_metrics.timestamp.isoformat(),
                    'cpu_usage_percent': latest_metrics.cpu_usage_percent,
                    'memory_usage_percent': latest_metrics.memory_usage_percent,
                    'disk_usage_percent': latest_metrics.disk_usage_percent,
                    'total_users': latest_metrics.total_users,
                    'active_users_1h': latest_metrics.active_users_1h
                }
            
            health_data = {
                'overall_health': {
                    'percentage': round(health_percentage, 1),
                    'status': 'healthy' if health_percentage >= 80 else 'degraded' if health_percentage >= 60 else 'unhealthy',
                    'checks_count': health_checks.count(),
                    'healthy_checks': healthy_count if health_checks.exists() else 0
                },
                'health_checks': [
                    {
                        'check_name': check.check_name,
                        'check_type': check.check_type,
                        'status': check.status,
                        'status_message': check.status_message,
                        'response_time_ms': check.response_time_ms,
                        'checked_at': check.checked_at.isoformat()
                    }
                    for check in health_checks
                ],
                'system_metrics': metrics_data
            }
            
            return self.success_response(health_data)
        
        except Exception as e:
            logger.error(f"Error getting system health: {e}")
            return self.error_response(
                "Failed to get system health",
                status_code=500
            )
    
    def trigger_health_check(self, check_name: str = None) -> Response:
        """Trigger system health check"""
        if not self.has_permission('manage_system_health'):
            return self.error_response(
                "You don't have permission to manage system health",
                status_code=403
            )
        
        try:
            from .tasks import run_system_health_checks
            
            # Trigger async health check
            if check_name:
                run_system_health_checks.delay(check_names=[check_name])
            else:
                run_system_health_checks.delay()
            
            return self.success_response(
                message="System health checks triggered"
            )
        
        except Exception as e:
            logger.error(f"Error triggering health check: {e}")
            return self.error_response(
                "Failed to trigger health check",
                status_code=500
            )


class ExportResource(AlertResource):
    """Resource for data export operations"""
    
    def export_alerts(self) -> Response:
        """Export alert data"""
        if not self.has_permission('export_data'):
            return self.error_response(
                "You don't have permission to export data",
                status_code=403
            )
        
        try:
            from .models import AlertLog
            from django.http import HttpResponse
            import csv
            from io import StringIO
            
            # Get alerts with filters
            queryset = AlertLog.objects.select_related('rule').order_by('-triggered_at')
            
            # Apply filters
            start_date = self.request.query_params.get('start_date')
            end_date = self.request.query_params.get('end_date')
            if start_date:
                queryset = queryset.filter(triggered_at__gte=start_date)
            if end_date:
                queryset = queryset.filter(triggered_at__lte=end_date)
            
            # Generate CSV
            output = StringIO()
            writer = csv.writer(output)
            
            # Headers
            writer.writerow([
                'ID', 'Rule Name', 'Severity', 'Message',
                'Triggered At', 'Resolved At', 'Status'
            ])
            
            # Data
            for alert in queryset:
                writer.writerow([
                    alert.id,
                    alert.rule.name,
                    alert.rule.severity,
                    alert.message,
                    alert.triggered_at,
                    alert.resolved_at,
                    'Resolved' if alert.is_resolved else 'Unresolved'
                ])
            
            # Create response
            response = HttpResponse(
                output.getvalue(),
                content_type='text/csv'
            )
            response['Content-Disposition'] = 'attachment; filename="alerts_export.csv"'
            
            return response
        
        except Exception as e:
            logger.error(f"Error exporting alerts: {e}")
            return self.error_response(
                "Failed to export alerts",
                status_code=500
            )


# Resource factory
class ResourceFactory:
    """Factory for creating resource instances"""
    
    @staticmethod
    def create_resource(resource_type: str, request) -> AlertResource:
        """Create resource instance by type"""
        resource_classes = {
            'alert_rule': AlertRuleResource,
            'alert_log': AlertLogResource,
            'notification': NotificationResource,
            'system': SystemResource,
            'export': ExportResource
        }
        
        resource_class = resource_classes.get(resource_type)
        if not resource_class:
            raise ValueError(f"Unknown resource type: {resource_type}")
        
        return resource_class(request)
    
    @staticmethod
    def get_available_resources() -> List[str]:
        """Get list of available resource types"""
        return [
            'alert_rule', 'alert_log', 'notification',
            'system', 'export'
        ]


# Utility functions
def create_resource_response(
    success: bool,
    message: str,
    data: Any = None,
    status_code: int = 200,
    errors: Dict[str, Any] = None
) -> Response:
    """Create standardized resource response"""
    response_data = {
        'success': success,
        'message': message,
        'timestamp': timezone.now().isoformat()
    }
    
    if data is not None:
        response_data['data'] = data
    
    if errors:
        response_data['errors'] = errors
    
    return Response(response_data, status=status_code)


def validate_resource_request(request, required_permissions: List[str]) -> Dict[str, Any]:
    """Validate resource request and permissions"""
    errors = {}
    
    # Check authentication
    if not request.user.is_authenticated:
        errors['authentication'] = 'Authentication required'
        return {'valid': False, 'errors': errors}
    
    # Check permissions
    for permission in required_permissions:
        if not request.user.has_perm(f'alerts.{permission}') and not request.user.is_staff:
            errors['permissions'] = f'Permission alerts.{permission} required'
    
    # Validate request data
    if not request.data:
        errors['data'] = 'Request data is required'
    
    return {
        'valid': len(errors) == 0,
        'errors': errors
    }
