"""
Monitoring Tasks

This module contains Celery tasks for monitoring operations including
SSL monitoring, disk usage checking, API usage monitoring, and health reporting.
"""

from celery import shared_task
from django.utils import timezone
from django.db import transaction
from datetime import timedelta
import logging
import os
import psutil

from ..models import Tenant
from ..services import DomainService

logger = logging.getLogger(__name__)


@shared_task(name='tenants.monitoring.monitor_ssl_expiry')
def monitor_ssl_expiry():
    """
    Monitor SSL certificate expiry for all tenant domains.
    
    This task runs daily to check SSL certificates and
    send alerts for certificates expiring soon.
    """
    logger.info("Starting SSL expiry monitoring")
    
    monitored_count = 0
    alerts_sent = 0
    errors = []
    
    # Get all active domains
    from ..models.branding import TenantDomain
    
    domains = TenantDomain.objects.filter(is_active=True).select_related('tenant')
    
    for domain in domains:
        try:
            # Get domain health information
            health = DomainService.get_domain_health(domain)
            
            monitored_count += 1
            
            # Check if SSL needs attention
            if health['score'] < 70:  # Low score indicates issues
                # Send alert to tenant
                from ..models.analytics import TenantNotification
                
                if health['checks'].get('ssl_certificate', {}).get('days_until_expiry', 999) <= 7:
                    title = 'SSL Certificate Expiring Soon'
                    message = f'SSL certificate for {domain.domain} expires in {health["checks"]["ssl_certificate"]["days_until_expiry"]} days.'
                    priority = 'high' if health["checks"]["ssl_certificate"]["days_until_expiry"] <= 3 else 'medium'
                else:
                    title = 'SSL Certificate Issue'
                    message = f'SSL certificate issue detected for {domain.domain}.'
                    priority = 'high'
                
                TenantNotification.objects.create(
                    tenant=domain.tenant,
                    title=title,
                    message=message,
                    notification_type='security',
                    priority=priority,
                    send_email=True,
                    send_push=True,
                    action_url='/branding/domains',
                    action_text='Manage Domains',
                    metadata={
                        'domain_id': str(domain.id),
                        'domain': domain.domain,
                        'health_score': health['score'],
                    },
                )
                
                alerts_sent += 1
                logger.warning(f"SSL alert sent for {domain.domain}: {title}")
            
        except Exception as e:
            error_msg = f"Failed to monitor SSL for {domain.domain}: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
    
    result = {
        'monitored_count': monitored_count,
        'alerts_sent': alerts_sent,
        'failed_count': len(errors),
        'errors': errors,
        'total_domains': domains.count(),
    }
    
    logger.info(f"SSL expiry monitoring completed: {result}")
    return result


@shared_task(name='tenants.monitoring.check_disk_usage')
def check_disk_usage():
    """
    Check disk usage across tenant storage and system resources.
    
    This task runs hourly to monitor disk usage and
    send alerts when thresholds are exceeded.
    """
    logger.info("Starting disk usage check")
    
    alerts_sent = 0
    errors = []
    
    try:
        # Get system disk usage
        disk_usage = psutil.disk_usage('/')
        total_gb = disk_usage.total / (1024**3)
        used_gb = disk_usage.used / (1024**3)
        free_gb = disk_usage.free / (1024**3)
        usage_percent = (used_gb / total_gb) * 100
        
        system_stats = {
            'total_gb': round(total_gb, 2),
            'used_gb': round(used_gb, 2),
            'free_gb': round(free_gb, 2),
            'usage_percent': round(usage_percent, 2),
        }
        
        # Check system disk usage threshold
        if usage_percent > 85:
            # Send system alert to administrators
            from ..models.analytics import TenantNotification
            
            # Find admin tenant or system user
            admin_tenant = Tenant.objects.filter(is_deleted=False).first()
            
            if admin_tenant:
                TenantNotification.objects.create(
                    tenant=admin_tenant,
                    title='System Disk Usage Alert',
                    message=f'System disk usage is {usage_percent:.1f}% ({used_gb:.1f}GB used of {total_gb:.1f}GB).',
                    notification_type='system',
                    priority='urgent',
                    send_email=True,
                    send_push=True,
                    metadata=system_stats,
                )
                
                alerts_sent += 1
                logger.error(f"System disk usage alert: {usage_percent:.1f}%")
        
        # Check tenant storage usage
        tenants = Tenant.objects.filter(is_deleted=False, status='active').select_related('plan')
        
        for tenant in tenants:
            try:
                # Get tenant storage usage
                from ..services import PlanUsageService
                usage = PlanUsageService.get_current_usage(tenant, 'monthly')
                
                if 'storage' in usage:
                    storage_used = usage['storage']['used']
                    storage_limit = usage['storage']['limit']
                    storage_percentage = usage['storage']['percentage']
                    
                    # Check if storage usage is high
                    if storage_percentage > 90:
                        from ..models.analytics import TenantNotification
                        
                        TenantNotification.objects.create(
                            tenant=tenant,
                            title='Storage Usage Alert',
                            message=f'Your storage usage is {storage_percentage:.1f}% ({storage_used:.1f}GB of {storage_limit:.1f}GB).',
                            notification_type='quota',
                            priority='high',
                            send_email=True,
                            send_push=True,
                            action_url='/billing/usage',
                            action_text='View Usage',
                            metadata={
                                'storage_used': storage_used,
                                'storage_limit': storage_limit,
                                'storage_percentage': storage_percentage,
                            },
                        )
                        
                        alerts_sent += 1
                        logger.warning(f"Storage alert sent to {tenant.name}: {storage_percentage:.1f}%")
                
            except Exception as e:
                error_msg = f"Failed to check storage for {tenant.name}: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)
        
        result = {
            'system_stats': system_stats,
            'alerts_sent': alerts_sent,
            'failed_count': len(errors),
            'errors': errors,
            'monitored_tenants': tenants.count(),
        }
        
        logger.info(f"Disk usage check completed: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Disk usage check failed: {str(e)}")
        return {'error': str(e)}


@shared_task(name='tenants.monitoring.monitor_api_usage')
def monitor_api_usage():
    """
    Monitor API usage patterns and detect anomalies.
    
    This task runs hourly to monitor API usage and
    detect unusual patterns or potential abuse.
    """
    logger.info("Starting API usage monitoring")
    
    anomalies_detected = 0
    errors = []
    
    try:
        # Get recent API usage from audit logs
        from ..models.security import TenantAuditLog
        from datetime import timedelta
        
        last_hour = timezone.now() - timedelta(hours=1)
        api_logs = TenantAuditLog.objects.filter(
            action='api_access',
            created_at__gte=last_hour
        ).select_related('tenant')
        
        # Group by tenant
        usage_by_tenant = {}
        for log in api_logs:
            tenant_id = log.tenant.id
            if tenant_id not in usage_by_tenant:
                usage_by_tenant[tenant_id] = {
                    'tenant': log.tenant,
                    'count': 0,
                    'unique_ips': set(),
                    'endpoints': set(),
                }
            
            usage_by_tenant[tenant_id]['count'] += 1
            if log.ip_address:
                usage_by_tenant[tenant_id]['unique_ips'].add(log.ip_address)
            
            # Extract endpoint from metadata
            if log.metadata and 'endpoint' in log.metadata:
                usage_by_tenant[tenant_id]['endpoints'].add(log.metadata['endpoint'])
        
        # Check for anomalies
        for tenant_id, data in usage_by_tenant.items():
            tenant = data['tenant']
            count = data['count']
            unique_ips = len(data['unique_ips'])
            endpoints = len(data['endpoints'])
            
            # Check for unusually high API usage
            plan_limit = tenant.plan.api_calls_per_day if tenant.plan else 1000
            hourly_average = plan_limit / 24  # Rough estimate
            
            if count > hourly_average * 3:  # 3x hourly average
                anomalies_detected += 1
                
                from ..models.analytics import TenantNotification
                
                TenantNotification.objects.create(
                    tenant=tenant,
                    title='Unusual API Usage Detected',
                    message=f'High API usage detected: {count} calls in the last hour (normal: ~{hourly_average:.0f}).',
                    notification_type='security',
                    priority='high',
                    send_email=True,
                    send_push=True,
                    action_url='/security/audit',
                    action_text='View Audit Log',
                    metadata={
                        'api_calls': count,
                        'hourly_average': hourly_average,
                        'unique_ips': unique_ips,
                    },
                )
                
                logger.warning(f"API usage anomaly detected for {tenant.name}: {count} calls")
            
            # Check for usage from many different IPs (potential abuse)
            if unique_ips > 50:
                anomalies_detected += 1
                
                from ..models.analytics import TenantNotification
                
                TenantNotification.objects.create(
                    tenant=tenant,
                    title='API Usage from Multiple IPs',
                    message=f'API usage detected from {unique_ips} different IP addresses in the last hour.',
                    notification_type='security',
                    priority='medium',
                    send_email=True,
                    send_push=False,
                    action_url='/security/audit',
                    action_text='View Audit Log',
                    metadata={
                        'unique_ips': unique_ips,
                        'api_calls': count,
                    },
                )
                
                logger.info(f"Multiple IP usage detected for {tenant.name}: {unique_ips} IPs")
        
        result = {
            'anomalies_detected': anomalies_detected,
            'failed_count': len(errors),
            'errors': errors,
            'total_api_logs': api_logs.count(),
            'monitored_tenants': len(usage_by_tenant),
        }
        
        logger.info(f"API usage monitoring completed: {result}")
        return result
        
    except Exception as e:
        logger.error(f"API usage monitoring failed: {str(e)}")
        return {'error': str(e)}


@shared_task(name='tenants.monitoring.generate_system_health_report')
def generate_system_health_report():
    """
    Generate comprehensive system health report.
    
    This task runs daily to generate a detailed health
    report covering all aspects of the system.
    """
    logger.info("Starting system health report generation")
    
    try:
        from datetime import timedelta
        from django.db.models import Count, Avg, Sum
        
        report = {
            'timestamp': timezone.now().isoformat(),
            'period': '24 hours',
            'overall_health': 'good',
            'sections': {},
        }
        
        # System Resources
        try:
            disk_usage = psutil.disk_usage('/')
            memory = psutil.virtual_memory()
            cpu_percent = psutil.cpu_percent(interval=1)
            
            report['sections']['system_resources'] = {
                'disk_usage': {
                    'total_gb': round(disk_usage.total / (1024**3), 2),
                    'used_gb': round(disk_usage.used / (1024**3), 2),
                    'free_gb': round(disk_usage.free / (1024**3), 2),
                    'usage_percent': round((disk_usage.used / disk_usage.total) * 100, 2),
                },
                'memory': {
                    'total_gb': round(memory.total / (1024**3), 2),
                    'used_gb': round(memory.used / (1024**3), 2),
                    'available_gb': round(memory.available / (1024**3), 2),
                    'usage_percent': memory.percent,
                },
                'cpu': {
                    'usage_percent': cpu_percent,
                },
            }
            
            # Check if any resource is critical
            if (disk_usage.used / disk_usage.total) > 0.9 or memory.percent > 90:
                report['overall_health'] = 'critical'
            elif (disk_usage.used / disk_usage.total) > 0.8 or memory.percent > 80:
                report['overall_health'] = 'warning'
                
        except Exception as e:
            logger.error(f"Failed to get system resources: {str(e)}")
            report['sections']['system_resources'] = {'error': str(e)}
        
        # Tenant Statistics
        try:
            from ..models import Tenant
            
            tenant_stats = {
                'total': Tenant.objects.filter(is_deleted=False).count(),
                'active': Tenant.objects.filter(is_deleted=False, status='active').count(),
                'trial': Tenant.objects.filter(is_deleted=False, status='trial').count(),
                'suspended': Tenant.objects.filter(is_deleted=False, status='suspended').count(),
                'created_today': Tenant.objects.filter(
                    is_deleted=False,
                    created_at__date=timezone.now().date()
                ).count(),
            }
            
            report['sections']['tenant_statistics'] = tenant_stats
            
            # Check if many tenants are suspended
            if tenant_stats['suspended'] > tenant_stats['total'] * 0.1:
                if report['overall_health'] == 'good':
                    report['overall_health'] = 'warning'
                
        except Exception as e:
            logger.error(f"Failed to get tenant statistics: {str(e)}")
            report['sections']['tenant_statistics'] = {'error': str(e)}
        
        # API Activity
        try:
            from ..models.security import TenantAuditLog
            
            last_24h = timezone.now() - timedelta(hours=24)
            
            api_stats = {
                'total_requests': TenantAuditLog.objects.filter(
                    action='api_access',
                    created_at__gte=last_24h
                ).count(),
                'security_events': TenantAuditLog.objects.filter(
                    action='security_event',
                    created_at__gte=last_24h
                ).count(),
                'unique_tenants': TenantAuditLog.objects.filter(
                    created_at__gte=last_24h
                ).values('tenant').distinct().count(),
            }
            
            report['sections']['api_activity'] = api_stats
            
            # Check for high security events
            if api_stats['security_events'] > 100:
                if report['overall_health'] == 'good':
                    report['overall_health'] = 'warning'
            elif api_stats['security_events'] > 500:
                report['overall_health'] = 'critical'
                
        except Exception as e:
            logger.error(f"Failed to get API activity: {str(e)}")
            report['sections']['api_activity'] = {'error': str(e)}
        
        # Database Performance
        try:
            from django.db import connection
            
            with connection.cursor() as cursor:
                # Get table sizes (MySQL specific)
                cursor.execute("""
                    SELECT table_name, 
                           ROUND(((data_length + index_length) / 1024 / 1024), 2) AS size_mb
                    FROM information_schema.tables 
                    WHERE table_schema = DATABASE() 
                    ORDER BY size_mb DESC 
                    LIMIT 10
                """)
                
                table_sizes = cursor.fetchall()
                
                report['sections']['database_performance'] = {
                    'largest_tables': [
                        {'table': row[0], 'size_mb': row[1]}
                        for row in table_sizes
                    ],
                    'total_tables': len(table_sizes),
                }
                
        except Exception as e:
            logger.error(f"Failed to get database performance: {str(e)}")
            report['sections']['database_performance'] = {'error': str(e)}
        
        # SSL Certificates
        try:
            from ..models.branding import TenantDomain
            
            ssl_stats = {
                'total_domains': TenantDomain.objects.filter(is_active=True).count(),
                'valid_ssl': TenantDomain.objects.filter(
                    is_active=True,
                    ssl_status='verified'
                ).count(),
                'expiring_soon': TenantDomain.objects.filter(
                    is_active=True,
                    ssl_expires_at__lte=timezone.now() + timedelta(days=7)
                ).count(),
            }
            
            report['sections']['ssl_certificates'] = ssl_stats
            
            # Check if many SSL certificates are expiring
            if ssl_stats['expiring_soon'] > ssl_stats['total_domains'] * 0.1:
                if report['overall_health'] == 'good':
                    report['overall_health'] = 'warning'
                
        except Exception as e:
            logger.error(f"Failed to get SSL statistics: {str(e)}")
            report['sections']['ssl_certificates'] = {'error': str(e)}
        
        # Recommendations
        recommendations = []
        
        if report['overall_health'] in ['warning', 'critical']:
            recommendations.append('System health requires attention. Review detailed report.')
        
        if report['sections'].get('system_resources', {}).get('disk_usage', {}).get('usage_percent', 0) > 80:
            recommendations.append('Disk usage is high. Consider cleaning up old data or expanding storage.')
        
        if report['sections'].get('system_resources', {}).get('memory', {}).get('usage_percent', 0) > 80:
            recommendations.append('Memory usage is high. Monitor for potential memory leaks.')
        
        if report['sections'].get('api_activity', {}).get('security_events', 0) > 100:
            recommendations.append('High number of security events detected. Review security logs.')
        
        report['recommendations'] = recommendations
        
        logger.info(f"System health report generated: {report['overall_health']} health")
        return report
        
    except Exception as e:
        logger.error(f"System health report generation failed: {str(e)}")
        return {'error': str(e)}


@shared_task(name='tenants.monitoring.check_service_health')
def check_service_health():
    """
    Check health of external services and dependencies.
    
    This task runs every 30 minutes to check the health
    of external services like email providers, payment gateways, etc.
    """
    logger.info("Starting service health check")
    
    services_status = {}
    errors = []
    
    try:
        # Check email service health
        from ..models.branding import TenantEmail
        
        email_configs = TenantEmail.objects.filter(is_verified=True)
        
        email_health = {
            'total_configs': email_configs.count(),
            'healthy_configs': 0,
            'failed_configs': 0,
        }
        
        for email_config in email_configs:
            try:
                # Test email configuration
                from ..services import BrandingService
                result = BrandingService.test_email_connection(email_config)
                
                if result['success']:
                    email_health['healthy_configs'] += 1
                else:
                    email_health['failed_configs'] += 1
                    
            except Exception as e:
                email_health['failed_configs'] += 1
                errors.append(f"Email config test failed: {str(e)}")
        
        services_status['email'] = email_health
        
        # Check database connectivity
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                services_status['database'] = {'status': 'healthy'}
        except Exception as e:
            services_status['database'] = {'status': 'unhealthy', 'error': str(e)}
            errors.append(f"Database check failed: {str(e)}")
        
        # Check Redis connectivity (if used)
        try:
            # This would check Redis connectivity
            services_status['cache'] = {'status': 'healthy'}  # Placeholder
        except Exception as e:
            services_status['cache'] = {'status': 'unhealthy', 'error': str(e)}
            errors.append(f"Cache check failed: {str(e)}")
        
        result = {
            'timestamp': timezone.now().isoformat(),
            'services': services_status,
            'overall_health': 'healthy' if not errors else 'degraded',
            'errors': errors,
        }
        
        logger.info(f"Service health check completed: {result['overall_health']}")
        return result
        
    except Exception as e:
        logger.error(f"Service health check failed: {str(e)}")
        return {'error': str(e)}


@shared_task(name='tenants.monitoring.track_performance_metrics')
def track_performance_metrics():
    """
    Track system performance metrics.
    
    This task runs every 5 minutes to collect performance
    metrics for monitoring and alerting.
    """
    logger.info("Starting performance metrics tracking")
    
    try:
        metrics = {
            'timestamp': timezone.now().isoformat(),
            'cpu_percent': psutil.cpu_percent(interval=1),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_usage_percent': (psutil.disk_usage('/').used / psutil.disk_usage('/').total) * 100,
            'load_average': psutil.getloadavg()[0] if hasattr(psutil, 'getloadavg') else None,
        }
        
        # This would store metrics in a monitoring system
        # For now, just log the metrics
        logger.debug(f"Performance metrics: {metrics}")
        
        return metrics
        
    except Exception as e:
        logger.error(f"Performance metrics tracking failed: {str(e)}")
        return {'error': str(e)}
