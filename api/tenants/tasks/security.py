"""
Security Tasks

This module contains Celery tasks for security-related operations including
API key management, security monitoring, and audit logging.
"""

from celery import shared_task
from django.utils import timezone
from django.conf import settings
import logging

from ..models.security import TenantAPIKey, TenantWebhookConfig, TenantIPWhitelist, TenantAuditLog
from ..models.core import Tenant
from ..services import TenantAuditService

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def rotate_api_keys(self, tenant_id=None, days_old=90):
    """
    Rotate API keys that are older than specified days.
    
    Args:
        tenant_id (str): Specific tenant ID (optional)
        days_old (int): Age threshold in days
    """
    try:
        cutoff_date = timezone.now() - timezone.timedelta(days=days_old)
        
        queryset = TenantAPIKey.objects.filter(
            created_at__lt=cutoff_date,
            is_active=True
        )
        
        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)
        
        rotated_keys = []
        
        for api_key in queryset:
            # Generate new key
            new_key = TenantAPIKeyService.generate_api_key()
            
            # Deactivate old key
            api_key.is_active = False
            api_key.deactivated_at = timezone.now()
            api_key.deactivated_reason = 'Automatic rotation'
            api_key.save()
            
            # Create new key
            new_api_key = TenantAPIKey.objects.create(
                tenant=api_key.tenant,
                name=api_key.name,
                key=new_key,
                permissions=api_key.permissions,
                rate_limit_per_minute=api_key.rate_limit_per_minute,
                rate_limit_per_hour=api_key.rate_limit_per_hour,
                rate_limit_per_day=api_key.rate_limit_per_day,
                allowed_ips=api_key.allowed_ips,
                metadata=api_key.metadata
            )
            
            rotated_keys.append({
                'old_key_id': api_key.id,
                'new_key_id': new_api_key.id,
                'tenant_id': api_key.tenant_id
            })
            
            # Create audit log
            TenantAuditService.create_audit_log(
                tenant=api_key.tenant,
                action='api_key_rotated',
                description=f'API key {api_key.name} automatically rotated',
                metadata={
                    'old_key_id': api_key.id,
                    'new_key_id': new_api_key.id,
                    'rotation_reason': 'automatic'
                }
            )
        
        logger.info(f"Rotated {len(rotated_keys)} API keys")
        
        return {
            'rotated_count': len(rotated_keys),
            'rotated_keys': rotated_keys
        }
        
    except Exception as exc:
        logger.error(f"Error rotating API keys: {str(exc)}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def check_security_events(self, tenant_id=None, hours=24):
    """
    Check for security events and generate alerts.
    
    Args:
        tenant_id (str): Specific tenant ID (optional)
        hours (int): Time window in hours
    """
    try:
        start_time = timezone.now() - timezone.timedelta(hours=hours)
        
        # Check for failed login attempts
        failed_logins = TenantAuditLog.objects.filter(
            action='login_failed',
            created_at__gte=start_time
        )
        
        if tenant_id:
            failed_logins = failed_logins.filter(tenant_id=tenant_id)
        
        # Group by tenant and IP
        security_alerts = {}
        
        for log in failed_logins:
            tenant_key = str(log.tenant_id)
            ip_address = log.metadata.get('ip_address', 'unknown')
            
            if tenant_key not in security_alerts:
                security_alerts[tenant_key] = {
                    'tenant_id': tenant_key,
                    'failed_attempts': 0,
                    'unique_ips': set(),
                    'suspicious_ips': {}
                }
            
            security_alerts[tenant_key]['failed_attempts'] += 1
            security_alerts[tenant_key]['unique_ips'].add(ip_address)
            
            # Track IPs with multiple failures
            if ip_address not in security_alerts[tenant_key]['suspicious_ips']:
                security_alerts[tenant_key]['suspicious_ips'][ip_address] = 0
            security_alerts[tenant_key]['suspicious_ips'][ip_address] += 1
        
        # Generate alerts for suspicious activity
        alerts_generated = []
        
        for tenant_key, alert_data in security_alerts.items():
            # Alert if more than 10 failed attempts
            if alert_data['failed_attempts'] > 10:
                alerts_generated.append({
                    'tenant_id': tenant_key,
                    'alert_type': 'high_failed_attempts',
                    'failed_attempts': alert_data['failed_attempts'],
                    'unique_ips': len(alert_data['unique_ips']),
                    'severity': 'high'
                })
                
                # Create audit log
                try:
                    tenant = Tenant.objects.get(id=tenant_key)
                    TenantAuditService.create_audit_log(
                        tenant=tenant,
                        action='security_alert',
                        description=f'High number of failed login attempts detected',
                        severity='high',
                        metadata={
                            'alert_type': 'high_failed_attempts',
                            'failed_attempts': alert_data['failed_attempts'],
                            'unique_ips': len(alert_data['unique_ips']),
                            'suspicious_ips': dict(alert_data['suspicious_ips'])
                        }
                    )
                except Tenant.DoesNotExist:
                    pass
            
            # Alert if same IP has multiple failures
            for ip, count in alert_data['suspicious_ips'].items():
                if count > 5:
                    alerts_generated.append({
                        'tenant_id': tenant_key,
                        'alert_type': 'suspicious_ip_activity',
                        'ip_address': ip,
                        'failed_attempts': count,
                        'severity': 'medium'
                    })
        
        logger.info(f"Generated {len(alerts_generated)} security alerts")
        
        return {
            'alerts_count': len(alerts_generated),
            'alerts': alerts_generated
        }
        
    except Exception as exc:
        logger.error(f"Error checking security events: {str(exc)}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def generate_security_report(self, tenant_id=None, days=7):
    """
    Generate security report for tenants.
    
    Args:
        tenant_id (str): Specific tenant ID (optional)
        days (int): Number of days to include in report
    """
    try:
        start_date = timezone.now() - timezone.timedelta(days=days)
        
        # Get security metrics
        queryset = TenantAuditLog.objects.filter(
            created_at__gte=start_date
        )
        
        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)
        
        # Aggregate security events
        security_report = {
            'period': {
                'start_date': start_date.date(),
                'end_date': timezone.now().date(),
                'days': days
            },
            'total_events': queryset.count(),
            'events_by_type': {},
            'events_by_severity': {},
            'events_by_tenant': {},
            'top_suspicious_ips': {},
            'api_key_activity': {},
            'recommendations': []
        }
        
        # Count by event type
        for action in ['login_success', 'login_failed', 'api_key_used', 'api_key_created', 'api_key_revoked']:
            count = queryset.filter(action=action).count()
            security_report['events_by_type'][action] = count
        
        # Count by severity
        for severity in ['low', 'medium', 'high', 'critical']:
            count = queryset.filter(severity=severity).count()
            security_report['events_by_severity'][severity] = count
        
        # Count by tenant
        tenant_events = queryset.values('tenant_id').annotate(
            count=models.Count('id')
        ).order_by('-count')[:10]
        
        for event in tenant_events:
            security_report['events_by_tenant'][str(event['tenant_id'])] = event['count']
        
        # Get suspicious IPs
        suspicious_ips = {}
        for log in queryset.filter(action='login_failed'):
            ip = log.metadata.get('ip_address')
            if ip:
                suspicious_ips[ip] = suspicious_ips.get(ip, 0) + 1
        
        # Sort and get top 10
        security_report['top_suspicious_ips'] = dict(
            sorted(suspicious_ips.items(), key=lambda x: x[1], reverse=True)[:10]
        )
        
        # API key activity
        api_key_events = queryset.filter(action='api_key_used')
        for log in api_key_events:
            key_id = log.metadata.get('api_key_id')
            if key_id:
                security_report['api_key_activity'][key_id] = security_report['api_key_activity'].get(key_id, 0) + 1
        
        # Generate recommendations
        if security_report['events_by_severity'].get('high', 0) > 0:
            security_report['recommendations'].append('Review high-severity security events')
        
        if security_report['events_by_type'].get('login_failed', 0) > security_report['events_by_type'].get('login_success', 0):
            security_report['recommendations'].append('Failed login attempts exceed successful logins')
        
        if len(security_report['top_suspicious_ips']) > 0:
            security_report['recommendations'].append('Consider IP whitelisting for suspicious activity')
        
        logger.info(f"Generated security report for {days} days")
        
        return security_report
        
    except Exception as exc:
        logger.error(f"Error generating security report: {str(exc)}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def audit_log_export(self, tenant_id=None, start_date=None, end_date=None, format='csv'):
    """
    Export audit logs for analysis.
    
    Args:
        tenant_id (str): Specific tenant ID (optional)
        start_date (str): Start date (YYYY-MM-DD format)
        end_date (str): End date (YYYY-MM-DD format)
        format (str): Export format ('csv' or 'json')
    """
    try:
        from datetime import datetime
        
        # Parse dates
        if start_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        else:
            start_date = timezone.now().date() - timezone.timedelta(days=30)
        
        if end_date:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        else:
            end_date = timezone.now().date()
        
        # Get audit logs
        queryset = TenantAuditLog.objects.filter(
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        )
        
        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)
        
        # Export based on format
        if format == 'csv':
            export_data = _export_audit_logs_to_csv(queryset)
        elif format == 'json':
            export_data = _export_audit_logs_to_json(queryset)
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        logger.info(f"Exported {queryset.count()} audit logs to {format}")
        
        return {
            'export_format': format,
            'record_count': queryset.count(),
            'date_range': {
                'start_date': start_date,
                'end_date': end_date
            },
            'data': export_data
        }
        
    except Exception as exc:
        logger.error(f"Error exporting audit logs: {str(exc)}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def security_scan(self, tenant_id=None, scan_type='full'):
    """
    Perform security scan on tenant configurations.
    
    Args:
        tenant_id (str): Specific tenant ID (optional)
        scan_type (str): Type of scan ('full', 'quick', 'api_keys', 'webhooks')
    """
    try:
        scan_results = {
            'scan_type': scan_type,
            'scanned_at': timezone.now(),
            'findings': [],
            'recommendations': [],
            'risk_score': 0
        }
        
        # Get tenants to scan
        if tenant_id:
            tenants = [Tenant.objects.get(id=tenant_id)]
        else:
            tenants = Tenant.objects.filter(is_active=True, is_deleted=False)
        
        total_risk_score = 0
        
        for tenant in tenants:
            tenant_findings = []
            
            # Scan API keys
            if scan_type in ['full', 'quick', 'api_keys']:
                api_key_findings = _scan_api_keys(tenant)
                tenant_findings.extend(api_key_findings)
            
            # Scan webhooks
            if scan_type in ['full', 'webhooks']:
                webhook_findings = _scan_webhooks(tenant)
                tenant_findings.extend(webhook_findings)
            
            # Scan IP whitelist
            if scan_type in ['full']:
                ip_findings = _scan_ip_whitelist(tenant)
                tenant_findings.extend(ip_findings)
            
            # Calculate tenant risk score
            tenant_risk_score = _calculate_tenant_risk_score(tenant_findings)
            total_risk_score += tenant_risk_score
            
            if tenant_findings:
                scan_results['findings'].append({
                    'tenant_id': tenant.id,
                    'tenant_name': tenant.name,
                    'risk_score': tenant_risk_score,
                    'findings': tenant_findings
                })
        
        # Calculate overall risk score
        if tenants:
            scan_results['risk_score'] = total_risk_score / len(tenants)
        
        # Generate recommendations
        scan_results['recommendations'] = _generate_security_recommendations(scan_results['findings'])
        
        logger.info(f"Security scan completed with risk score: {scan_results['risk_score']}")
        
        return scan_results
        
    except Exception as exc:
        logger.error(f"Error performing security scan: {str(exc)}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def cleanup_expired_api_keys(self, tenant_id=None):
    """
    Clean up expired API keys.
    
    Args:
        tenant_id (str): Specific tenant ID (optional)
    """
    try:
        queryset = TenantAPIKey.objects.filter(
            expires_at__lt=timezone.now(),
            is_active=True
        )
        
        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)
        
        expired_keys = []
        
        for api_key in queryset:
            api_key.is_active = False
            api_key.deactivated_at = timezone.now()
            api_key.deactivated_reason = 'Expired'
            api_key.save()
            
            expired_keys.append({
                'key_id': api_key.id,
                'key_name': api_key.name,
                'tenant_id': api_key.tenant_id,
                'expired_at': api_key.expires_at
            })
            
            # Create audit log
            TenantAuditService.create_audit_log(
                tenant=api_key.tenant,
                action='api_key_expired',
                description=f'API key {api_key.name} expired and deactivated',
                metadata={
                    'api_key_id': api_key.id,
                    'expired_at': api_key.expires_at.isoformat()
                }
            )
        
        logger.info(f"Cleaned up {len(expired_keys)} expired API keys")
        
        return {
            'cleaned_count': len(expired_keys),
            'expired_keys': expired_keys
        }
        
    except Exception as exc:
        logger.error(f"Error cleaning up expired API keys: {str(exc)}")
        raise self.retry(exc=exc, countdown=60)


# Helper functions
def _export_audit_logs_to_csv(queryset):
    """Export audit logs to CSV format."""
    import csv
    from io import StringIO
    
    output = StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        'id', 'tenant_id', 'action', 'description', 'severity',
        'user_id', 'ip_address', 'user_agent', 'created_at'
    ])
    
    # Write data
    for log in queryset:
        writer.writerow([
            log.id,
            log.tenant_id,
            log.action,
            log.description,
            log.severity,
            log.user_id,
            log.ip_address,
            log.user_agent,
            log.created_at.isoformat()
        ])
    
    return output.getvalue()


def _export_audit_logs_to_json(queryset):
    """Export audit logs to JSON format."""
    import json
    
    logs_data = []
    
    for log in queryset:
        logs_data.append({
            'id': log.id,
            'tenant_id': log.tenant_id,
            'action': log.action,
            'description': log.description,
            'severity': log.severity,
            'user_id': log.user_id,
            'ip_address': log.ip_address,
            'user_agent': log.user_agent,
            'created_at': log.created_at.isoformat(),
            'metadata': log.metadata
        })
    
    return json.dumps(logs_data, indent=2)


def _scan_api_keys(tenant):
    """Scan API keys for security issues."""
    findings = []
    api_keys = TenantAPIKey.objects.filter(tenant=tenant, is_active=True)
    
    # Check for keys without expiration
    keys_without_expiration = api_keys.filter(expires_at__isnull=True)
    if keys_without_expiration.exists():
        findings.append({
            'type': 'api_key_no_expiration',
            'severity': 'medium',
            'description': f'{keys_without_expiration.count()} API keys without expiration date',
            'recommendation': 'Set expiration dates for all API keys'
        })
    
    # Check for keys with very permissive permissions
    keys_with_full_permissions = api_keys.filter(permissions__contains=['*'])
    if keys_with_full_permissions.exists():
        findings.append({
            'type': 'api_key_full_permissions',
            'severity': 'high',
            'description': f'{keys_with_full_permissions.count()} API keys with full permissions',
            'recommendation': 'Restrict API key permissions to minimum required'
        })
    
    # Check for old keys
    old_keys = api_keys.filter(created_at__lt=timezone.now() - timezone.timedelta(days=365))
    if old_keys.exists():
        findings.append({
            'type': 'api_key_old',
            'severity': 'low',
            'description': f'{old_keys.count()} API keys older than 1 year',
            'recommendation': 'Consider rotating old API keys'
        })
    
    return findings


def _scan_webhooks(tenant):
    """Scan webhook configurations for security issues."""
    findings = []
    webhooks = TenantWebhookConfig.objects.filter(tenant=tenant, is_active=True)
    
    # Check for webhooks without SSL
    webhooks_without_ssl = webhooks.filter(url__startswith='http://')
    if webhooks_without_ssl.exists():
        findings.append({
            'type': 'webhook_no_ssl',
            'severity': 'high',
            'description': f'{webhooks_without_ssl.count()} webhooks using HTTP instead of HTTPS',
            'recommendation': 'Use HTTPS for all webhook URLs'
        })
    
    # Check for webhooks without secret
    webhooks_without_secret = webhooks.filter(secret__isnull=True) | webhooks.filter(secret='')
    if webhooks_without_secret.exists():
        findings.append({
            'type': 'webhook_no_secret',
            'severity': 'medium',
            'description': f'{webhooks_without_secret.count()} webhooks without secret key',
            'recommendation': 'Add secret keys for webhook security'
        })
    
    return findings


def _scan_ip_whitelist(tenant):
    """Scan IP whitelist for security issues."""
    findings = []
    ip_whitelist = TenantIPWhitelist.objects.filter(tenant=tenant, is_active=True)
    
    # Check for very broad IP ranges
    broad_ranges = ip_whitelist.filter(
        ip_address__in=['0.0.0.0/0', '0.0.0.0', '127.0.0.1']
    )
    if broad_ranges.exists():
        findings.append({
            'type': 'ip_whitelist_broad_range',
            'severity': 'high',
            'description': f'{broad_ranges.count()} broad IP ranges in whitelist',
            'recommendation': 'Use specific IP ranges instead of broad ranges'
        })
    
    return findings


def _calculate_tenant_risk_score(findings):
    """Calculate risk score based on findings."""
    risk_score = 0
    
    for finding in findings:
        severity = finding.get('severity', 'low')
        if severity == 'critical':
            risk_score += 10
        elif severity == 'high':
            risk_score += 5
        elif severity == 'medium':
            risk_score += 2
        elif severity == 'low':
            risk_score += 1
    
    return risk_score


def _generate_security_recommendations(findings):
    """Generate security recommendations based on findings."""
    recommendations = []
    
    # Count finding types
    finding_types = {}
    for tenant_finding in findings:
        for finding in tenant_finding['findings']:
            finding_type = finding['type']
            finding_types[finding_type] = finding_types.get(finding_type, 0) + 1
    
    # Generate recommendations based on common findings
    if finding_types.get('api_key_no_expiration', 0) > 0:
        recommendations.append({
            'priority': 'high',
            'category': 'api_keys',
            'recommendation': 'Set expiration dates for all API keys to improve security'
        })
    
    if finding_types.get('webhook_no_ssl', 0) > 0:
        recommendations.append({
            'priority': 'high',
            'category': 'webhooks',
            'recommendation': 'Migrate all webhook URLs to HTTPS'
        })
    
    if finding_types.get('api_key_full_permissions', 0) > 0:
        recommendations.append({
            'priority': 'medium',
            'category': 'api_keys',
            'recommendation': 'Review and restrict API key permissions'
        })
    
    return recommendations
