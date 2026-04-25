"""
Tenant Audit Service

This service handles audit logging, security monitoring,
and compliance tracking for tenant operations.
"""

from datetime import timedelta
from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from ..models import Tenant
from ..models.security import TenantAuditLog
from ..models.analytics import TenantNotification

User = get_user_model()


class TenantAuditService:
    """
    Service class for tenant audit operations.
    
    This service handles audit logging, security monitoring,
    and compliance tracking for tenant operations.
    """
    
    @staticmethod
    def log_action(tenant, action, actor=None, **kwargs):
        """
        Log an audit action for tenant.
        
        Args:
            tenant (Tenant): Tenant to log action for
            action (str): Action type
            actor (User): User performing the action
            **kwargs: Additional audit data
            
        Returns:
            TenantAuditLog: Created audit log entry
        """
        audit_data = {
            'tenant': tenant,
            'action': action,
            'actor': actor,
            'actor_type': 'user' if actor else 'system',
            'severity': kwargs.get('severity', 'medium'),
            'model_name': kwargs.get('model_name'),
            'object_id': kwargs.get('object_id'),
            'object_repr': kwargs.get('object_repr'),
            'old_value': kwargs.get('old_value', {}),
            'new_value': kwargs.get('new_value', {}),
            'changes': kwargs.get('changes', {}),
            'ip_address': kwargs.get('ip_address'),
            'user_agent': kwargs.get('user_agent'),
            'request_id': kwargs.get('request_id'),
            'description': kwargs.get('description'),
            'metadata': kwargs.get('metadata', {}),
        }
        
        return TenantAuditLog.objects.create(**audit_data)
    
    @staticmethod
    def log_security_event(tenant, description, severity='high', actor=None, **kwargs):
        """
        Log a security event for tenant.
        
        Args:
            tenant (Tenant): Tenant to log event for
            description (str): Event description
            severity (str): Event severity
            actor (User): User associated with event
            **kwargs: Additional event data
            
        Returns:
            TenantAuditLog: Created audit log entry
        """
        return TenantAuditService.log_action(
            tenant=tenant,
            action='security_event',
            actor=actor,
            severity=severity,
            description=description,
            metadata=kwargs.get('metadata', {}),
            **kwargs
        )
    
    @staticmethod
    def log_api_access(tenant, actor, endpoint, method='GET', **kwargs):
        """
        Log API access for tenant.
        
        Args:
            tenant (Tenant): Tenant
            actor (User): User making API call
            endpoint (str): API endpoint
            method (str): HTTP method
            **kwargs: Additional access data
            
        Returns:
            TenantAuditLog: Created audit log entry
        """
        return TenantAuditService.log_action(
            tenant=tenant,
            action='api_access',
            actor=actor,
            description=f"{method} {endpoint}",
            metadata={
                'endpoint': endpoint,
                'method': method,
                **kwargs.get('metadata', {})
            },
            **kwargs
        )
    
    @staticmethod
    def get_audit_logs(tenant, filters=None, limit=100):
        """
        Get audit logs for tenant with filtering.
        
        Args:
            tenant (Tenant): Tenant to get logs for
            filters (dict): Filter criteria
            limit (int): Maximum number of logs to return
            
        Returns:
            QuerySet: Filtered audit logs
        """
        queryset = TenantAuditLog.objects.filter(tenant=tenant)
        
        if filters:
            if 'action' in filters:
                queryset = queryset.filter(action=filters['action'])
            if 'severity' in filters:
                queryset = queryset.filter(severity=filters['severity'])
            if 'actor' in filters:
                queryset = queryset.filter(actor=filters['actor'])
            if 'model_name' in filters:
                queryset = queryset.filter(model_name=filters['model_name'])
            if 'date_from' in filters:
                queryset = queryset.filter(created_at__gte=filters['date_from'])
            if 'date_to' in filters:
                queryset = queryset.filter(created_at__lte=filters['date_to'])
        
        return queryset.select_related('actor').order_by('-created_at')[:limit]
    
    @staticmethod
    def get_security_events(tenant, days=30, severity=None):
        """
        Get security events for tenant.
        
        Args:
            tenant (Tenant): Tenant to get events for
            days (int): Number of days to look back
            severity (str): Filter by severity
            
        Returns:
            QuerySet: Security events
        """
        from django.utils import timezone
        
        start_date = timezone.now() - timedelta(days=days)
        queryset = TenantAuditLog.objects.filter(
            tenant=tenant,
            action='security_event',
            created_at__gte=start_date
        )
        
        if severity:
            queryset = queryset.filter(severity=severity)
        
        return queryset.order_by('-created_at')
    
    @staticmethod
    def get_user_activity(tenant, user, days=30):
        """
        Get activity logs for a specific user.
        
        Args:
            tenant (Tenant): Tenant
            user (User): User to get activity for
            days (int): Number of days to look back
            
        Returns:
            QuerySet: User activity logs
        """
        from django.utils import timezone
        
        start_date = timezone.now() - timedelta(days=days)
        
        return TenantAuditLog.objects.filter(
            tenant=tenant,
            actor=user,
            created_at__gte=start_date
        ).order_by('-created_at')
    
    @staticmethod
    def get_model_changes(tenant, model_name, object_id=None, days=30):
        """
        Get change logs for a specific model.
        
        Args:
            tenant (Tenant): Tenant
            model_name (str): Model name
            object_id (str): Specific object ID (optional)
            days (int): Number of days to look back
            
        Returns:
            QuerySet: Model change logs
        """
        from django.utils import timezone
        
        start_date = timezone.now() - timedelta(days=days)
        queryset = TenantAuditLog.objects.filter(
            tenant=tenant,
            model_name=model_name,
            created_at__gte=start_date
        )
        
        if object_id:
            queryset = queryset.filter(object_id=object_id)
        
        return queryset.order_by('-created_at')
    
    @staticmethod
    def get_compliance_report(tenant, days=90):
        """
        Generate compliance report for tenant.
        
        Args:
            tenant (Tenant): Tenant to generate report for
            days (int): Number of days to include in report
            
        Returns:
            dict: Compliance report data
        """
        from django.utils import timezone
        from django.db.models import Count, Q
        
        start_date = timezone.now() - timedelta(days=days)
        
        # Get all audit logs for period
        logs = TenantAuditLog.objects.filter(
            tenant=tenant,
            created_at__gte=start_date
        )
        
        # Generate statistics
        total_actions = logs.count()
        security_events = logs.filter(action='security_event').count()
        api_access = logs.filter(action='api_access').count()
        config_changes = logs.filter(action='config_change').count()
        
        # Breakdown by action type
        action_breakdown = logs.values('action').annotate(count=Count('id'))
        
        # Breakdown by severity
        severity_breakdown = logs.values('severity').annotate(count=Count('id'))
        
        # Breakdown by actor
        actor_breakdown = logs.values('actor__username').annotate(count=Count('id'))
        
        # Recent critical events
        critical_events = logs.filter(
            severity='critical'
        ).order_by('-created_at')[:10]
        
        # Failed login attempts
        failed_logins = logs.filter(
            action='security_event',
            description__icontains='login'
        ).count()
        
        report = {
            'period': {
                'start_date': start_date.date(),
                'end_date': timezone.now().date(),
                'days': days,
            },
            'summary': {
                'total_actions': total_actions,
                'security_events': security_events,
                'api_access': api_access,
                'config_changes': config_changes,
                'failed_logins': failed_logins,
                'actions_per_day': round(total_actions / days, 2),
            },
            'breakdowns': {
                'by_action': list(action_breakdown),
                'by_severity': list(severity_breakdown),
                'by_actor': list(actor_breakdown),
            },
            'critical_events': [
                {
                    'created_at': event.created_at,
                    'description': event.description,
                    'actor': event.actor_display,
                    'ip_address': event.ip_address,
                }
                for event in critical_events
            ],
            'compliance_score': TenantAuditService._calculate_compliance_score(logs),
        }
        
        return report
    
    @staticmethod
    def _calculate_compliance_score(logs):
        """Calculate compliance score based on audit logs."""
        if not logs.exists():
            return 100
        
        score = 100
        
        # Deduct points for security events
        security_events = logs.filter(action='security_event')
        critical_events = security_events.filter(severity='critical')
        high_events = security_events.filter(severity='high')
        
        score -= critical_events.count() * 10
        score -= high_events.count() * 5
        score -= (security_events.count() - critical_events.count() - high_events.count()) * 2
        
        # Deduct points for failed logins
        failed_logins = logs.filter(
            action='security_event',
            description__icontains='failed login'
        )
        score -= failed_logins.count() * 3
        
        return max(0, score)
    
    @staticmethod
    def detect_anomalies(tenant, hours=24):
        """
        Detect anomalies in tenant activity.
        
        Args:
            tenant (Tenant): Tenant to analyze
            hours (int): Number of hours to analyze
            
        Returns:
            list: List of detected anomalies
        """
        from django.utils import timezone
        from datetime import timedelta
        
        start_time = timezone.now() - timedelta(hours=hours)
        logs = TenantAuditLog.objects.filter(
            tenant=tenant,
            created_at__gte=start_time
        )
        
        anomalies = []
        
        # Check for unusual API access patterns
        api_logs = logs.filter(action='api_access')
        api_by_hour = {}
        for log in api_logs:
            hour = log.created_at.hour
            api_by_hour[hour] = api_by_hour.get(hour, 0) + 1
        
        if api_by_hour:
            avg_api_per_hour = sum(api_by_hour.values()) / len(api_by_hour)
            for hour, count in api_by_hour.items():
                if count > avg_api_per_hour * 3:  # 3x average
                    anomalies.append({
                        'type': 'high_api_usage',
                        'severity': 'medium',
                        'description': f'Unusually high API usage at hour {hour}: {count} calls',
                        'hour': hour,
                        'count': count,
                        'average': round(avg_api_per_hour, 2),
                    })
        
        # Check for multiple failed logins
        failed_logins = logs.filter(
            action='security_event',
            description__icontains='failed login'
        )
        
        failed_by_ip = {}
        for login in failed_logins:
            ip = login.ip_address
            if ip:
                failed_by_ip[ip] = failed_by_ip.get(ip, 0) + 1
        
        for ip, count in failed_by_ip.items():
            if count >= 5:  # 5 or more failed logins from same IP
                anomalies.append({
                    'type': 'multiple_failed_logins',
                    'severity': 'high',
                    'description': f'Multiple failed login attempts from IP {ip}: {count} attempts',
                    'ip_address': ip,
                    'count': count,
                })
        
        # Check for unusual config changes
        config_changes = logs.filter(action='config_change')
        if config_changes.count() > 50:  # More than 50 config changes in period
            anomalies.append({
                'type': 'excessive_config_changes',
                'severity': 'medium',
                'description': f'Excessive configuration changes: {config_changes.count()} changes',
                'count': config_changes.count(),
            })
        
        return anomalies
    
    @staticmethod
    def export_audit_logs(tenant, format='csv', days=30):
        """
        Export audit logs for tenant.
        
        Args:
            tenant (Tenant): Tenant to export logs for
            format (str): Export format (csv, json, xlsx)
            days (int): Number of days to export
            
        Returns:
            str/bytes: Exported data
        """
        from django.utils import timezone
        
        start_date = timezone.now() - timedelta(days=days)
        logs = TenantAuditLog.objects.filter(
            tenant=tenant,
            created_at__gte=start_date
        ).select_related('actor').order_by('-created_at')
        
        if format == 'json':
            import json
            data = []
            for log in logs:
                data.append({
                    'created_at': log.created_at.isoformat(),
                    'action': log.action,
                    'severity': log.severity,
                    'actor': log.actor_display,
                    'model_name': log.model_name,
                    'object_id': log.object_id,
                    'description': log.description,
                    'ip_address': log.ip_address,
                    'changes': log.get_changes_summary(),
                })
            return json.dumps(data, indent=2, default=str)
        
        elif format == 'csv':
            import csv
            import io
            
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write header
            writer.writerow([
                'Created At', 'Action', 'Severity', 'Actor', 'Model',
                'Object ID', 'Description', 'IP Address', 'Changes'
            ])
            
            # Write data
            for log in logs:
                writer.writerow([
                    log.created_at.isoformat(),
                    log.action,
                    log.severity,
                    log.actor_display,
                    log.model_name,
                    log.object_id,
                    log.description,
                    log.ip_address,
                    log.get_changes_summary(),
                ])
            
            return output.getvalue()
        
        elif format == 'xlsx':
            # This would require a library like openpyxl
            # For now, return CSV as fallback
            return TenantAuditService.export_audit_logs(tenant, 'csv', days)
        
        else:
            raise ValidationError(f'Unsupported export format: {format}')
    
    @staticmethod
    def cleanup_old_logs(days_to_keep=90):
        """
        Clean up old audit logs.
        
        Args:
            days_to_keep (int): Number of days to keep logs
            
        Returns:
            int: Number of logs deleted
        """
        from django.utils import timezone
        
        cutoff_date = timezone.now() - timedelta(days=days_to_keep)
        
        # Delete old logs
        deleted_count, _ = TenantAuditLog.objects.filter(
            created_at__lt=cutoff_date
        ).delete()
        
        return deleted_count
    
    @staticmethod
    def get_audit_summary(tenant=None, days=30):
        """
        Get audit summary for tenant or all tenants.
        
        Args:
            tenant (Tenant): Specific tenant (optional)
            days (int): Number of days to summarize
            
        Returns:
            dict: Audit summary
        """
        from django.utils import timezone
        from django.db.models import Count, Q
        
        start_date = timezone.now() - timedelta(days=days)
        
        queryset = TenantAuditLog.objects.filter(created_at__gte=start_date)
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        
        # Overall statistics
        total_logs = queryset.count()
        security_events = queryset.filter(action='security_event').count()
        api_access = queryset.filter(action='api_access').count()
        
        # Top actors
        top_actors = queryset.values('actor__username').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        # Top models
        top_models = queryset.values('model_name').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        # Recent critical events
        recent_critical = queryset.filter(
            severity='critical'
        ).order_by('-created_at')[:5]
        
        summary = {
            'period': {
                'start_date': start_date.date(),
                'end_date': timezone.now().date(),
                'days': days,
            },
            'statistics': {
                'total_logs': total_logs,
                'security_events': security_events,
                'api_access': api_access,
                'config_changes': queryset.filter(action='config_change').count(),
            },
            'top_actors': list(top_actors),
            'top_models': list(top_models),
            'recent_critical': [
                {
                    'created_at': event.created_at,
                    'description': event.description,
                    'actor': event.actor_display,
                    'tenant': event.tenant.name if tenant is None else None,
                }
                for event in recent_critical
            ],
        }
        
        return summary
