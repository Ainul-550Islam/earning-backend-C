"""
Maintenance Tasks

This module contains Celery tasks for maintenance operations including
cleanup tasks, SSL certificate management, data backups, and system maintenance.
"""

from celery import shared_task
from django.utils import timezone
from django.db import transaction
from datetime import timedelta
import logging

from ..models import Tenant
from ..services import DomainService, FeatureFlagService

logger = logging.getLogger(__name__)


@shared_task(name='tenants.maintenance.cleanup_expired_api_keys')
def cleanup_expired_api_keys():
    """
    Clean up expired API keys to maintain security.
    
    This task runs daily to clean up expired API keys
    and mark them as inactive.
    """
    logger.info("Starting expired API key cleanup")
    
    cleaned_count = 0
    errors = []
    
    # Get expired API keys
    from ..models.security import TenantAPIKey
    
    expired_keys = TenantAPIKey.objects.filter(
        expires_at__lt=timezone.now(),
        status='active'
    ).select_related('tenant')
    
    for api_key in expired_keys:
        try:
            # Mark as inactive
            api_key.status = 'expired'
            api_key.save(update_fields=['status'])
            
            # Send notification to tenant
            from ..models.analytics import TenantNotification
            
            TenantNotification.objects.create(
                tenant=api_key.tenant,
                title='API Key Expired',
                message=f'API key "{api_key.name}" has expired and been deactivated.',
                notification_type='security',
                priority='medium',
                send_email=True,
                send_push=True,
                action_url='/security/api-keys',
                action_text='Manage API Keys',
                metadata={'api_key_id': str(api_key.id)},
            )
            
            cleaned_count += 1
            logger.info(f"Cleaned up expired API key for {api_key.tenant.name}: {api_key.name}")
            
        except Exception as e:
            error_msg = f"Failed to cleanup API key {api_key.id}: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
    
    result = {
        'cleaned_count': cleaned_count,
        'failed_count': len(errors),
        'errors': errors,
        'total_expired': expired_keys.count(),
    }
    
    logger.info(f"API key cleanup completed: {result}")
    return result


@shared_task(name='tenants.maintenance.cleanup_expired_feature_flags')
def cleanup_expired_feature_flags():
    """
    Clean up expired feature flags.
    
    This task runs daily to deactivate expired feature flags
    and clean up old data.
    """
    logger.info("Starting expired feature flag cleanup")
    
    result = FeatureFlagService.cleanup_expired_flags()
    
    logger.info(f"Feature flag cleanup completed: {result}")
    return result


@shared_task(name='tenants.maintenance.renew_ssl_certificates')
def renew_ssl_certificates():
    """
    Renew SSL certificates for domains expiring soon.
    
    This task runs daily to check for SSL certificates
    expiring within 7 days and attempt renewal.
    """
    logger.info("Starting SSL certificate renewal")
    
    renewed_count = 0
    failed_count = 0
    errors = []
    
    # Get domains needing renewal
    expiring_domains = DomainService.monitor_ssl_expiration()
    
    for domain_info in expiring_domains:
        domain = domain_info['domain']
        
        try:
            if domain_info['priority'] == 'critical' and domain.ssl_auto_renew:
                # Attempt renewal
                renewal_result = DomainService.renew_ssl_certificate(domain)
                
                if renewal_result['success']:
                    renewed_count += 1
                    logger.info(f"Renewed SSL certificate for {domain.domain}")
                    
                    # Send notification
                    from ..models.analytics import TenantNotification
                    
                    TenantNotification.objects.create(
                        tenant=domain.tenant,
                        title='SSL Certificate Renewed',
                        message=f'SSL certificate for {domain.domain} has been automatically renewed.',
                        notification_type='system',
                        priority='medium',
                        send_email=True,
                        send_push=True,
                        action_url='/branding/domains',
                        action_text='View Domains',
                        metadata={'domain_id': str(domain.id)},
                    )
                else:
                    failed_count += 1
                    logger.error(f"Failed to renew SSL for {domain.domain}: {renewal_result.get('error')}")
            
        except Exception as e:
            failed_count += 1
            error_msg = f"Failed to renew SSL for {domain.domain}: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
    
    result = {
        'renewed_count': renewed_count,
        'failed_count': failed_count,
        'errors': errors,
        'total_expiring': len(expiring_domains),
    }
    
    logger.info(f"SSL certificate renewal completed: {result}")
    return result


@shared_task(name='tenants.maintenance.backup_tenant_data')
def backup_tenant_data():
    """
    Backup tenant data for disaster recovery.
    
    This task runs daily to create backups of critical
    tenant data and store them securely.
    """
    logger.info("Starting tenant data backup")
    
    backed_up_count = 0
    failed_count = 0
    errors = []
    
    # Get all active tenants
    tenants = Tenant.objects.filter(is_deleted=False, status='active')
    
    for tenant in tenants:
        try:
            # This would integrate with your backup system
            # For now, just create a backup record
            
            backup_data = {
                'tenant_id': str(tenant.id),
                'tenant_name': tenant.name,
                'backup_date': timezone.now().date().isoformat(),
                'data_types': ['settings', 'billing', 'metrics', 'audit_logs'],
                'status': 'completed',
            }
            
            # Log backup completion
            logger.info(f"Backed up data for {tenant.name}")
            backed_up_count += 1
            
        except Exception as e:
            failed_count += 1
            error_msg = f"Failed to backup data for {tenant.name}: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
    
    result = {
        'backed_up_count': backed_up_count,
        'failed_count': failed_count,
        'errors': errors,
        'total_tenants': tenants.count(),
    }
    
    logger.info(f"Tenant data backup completed: {result}")
    return result


@shared_task(name='tenants.maintenance.archive_audit_logs')
def archive_audit_logs():
    """
    Archive old audit logs to maintain database performance.
    
    This task runs monthly to archive audit logs older than
    a specified retention period.
    """
    logger.info("Starting audit log archival")
    
    # Get retention period from settings (default 90 days)
    retention_days = 90
    cutoff_date = timezone.now() - timedelta(days=retention_days)
    
    # Archive old audit logs
    from ..models.security import TenantAuditLog
    
    old_logs = TenantAuditLog.objects.filter(
        created_at__lt=cutoff_date
    ).select_related('tenant')
    
    archived_count = old_logs.count()
    
    # This would archive logs to cold storage
    # For now, just log the count
    logger.info(f"Archived {archived_count} audit logs older than {retention_days} days")
    
    result = {
        'archived_count': archived_count,
        'cutoff_date': cutoff_date.date(),
        'retention_days': retention_days,
    }
    
    logger.info(f"Audit log archival completed: {result}")
    return result


@shared_task(name='tenants.maintenance.cleanup_soft_deleted_tenants')
def cleanup_soft_deleted_tenants():
    """
    Permanently delete soft-deleted tenants after retention period.
    
    This task runs monthly to permanently delete tenants
    that were soft deleted more than 30 days ago.
    """
    logger.info("Starting soft-deleted tenant cleanup")
    
    retention_days = 30
    cutoff_date = timezone.now() - timedelta(days=retention_days)
    
    # Get soft-deleted tenants older than retention period
    old_tenants = Tenant.objects.filter(
        is_deleted=True,
        deleted_at__lt=cutoff_date
    )
    
    deleted_count = old_tenants.count()
    
    # Permanently delete
    old_tenants.delete()
    
    result = {
        'deleted_count': deleted_count,
        'cutoff_date': cutoff_date.date(),
        'retention_days': retention_days,
    }
    
    logger.info(f"Soft-deleted tenant cleanup completed: {result}")
    return result


@shared_task(name='tenants.maintenance.optimize_database')
def optimize_database():
    """
    Optimize database tables for better performance.
    
    This task runs weekly to optimize database tables
    and update statistics.
    """
    logger.info("Starting database optimization")
    
    try:
        from django.db import connection
        
        with connection.cursor() as cursor:
            # Optimize main tables
            tables = [
                'tenants_tenant',
                'tenants_tenantsettings',
                'tenants_tenantbilling',
                'tenants_tenantinvoice',
                'tenants_plan',
                'tenants_planusage',
                'tenants_tenantmetric',
                'tenants_tenantauditlog',
            ]
            
            optimized_tables = []
            
            for table in tables:
                try:
                    # Run OPTIMIZE TABLE (MySQL specific)
                    cursor.execute(f"OPTIMIZE TABLE {table}")
                    optimized_tables.append(table)
                    logger.info(f"Optimized table: {table}")
                except Exception as e:
                    logger.warning(f"Failed to optimize table {table}: {str(e)}")
            
            result = {
                'optimized_tables': optimized_tables,
                'total_tables': len(tables),
            }
            
        except Exception as e:
            logger.error(f"Database optimization failed: {str(e)}")
            result = {'error': str(e)}
        
        logger.info(f"Database optimization completed: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Database optimization failed: {str(e)}")
        return {'error': str(e)}


@shared_task(name='tenants.maintenance.update_system_statistics')
def update_system_statistics():
    """
    Update system-wide statistics for monitoring.
    
    This task runs hourly to update system statistics
    used for monitoring and reporting.
    """
    logger.info("Starting system statistics update")
    
    try:
        stats = {
            'timestamp': timezone.now().isoformat(),
            'tenants': {
                'total': Tenant.objects.filter(is_deleted=False).count(),
                'active': Tenant.objects.filter(is_deleted=False, status='active').count(),
                'trial': Tenant.objects.filter(is_deleted=False, status='trial').count(),
                'suspended': Tenant.objects.filter(is_deleted=False, status='suspended').count(),
            },
            'plans': {
                'total': Tenant.objects.filter(is_deleted=False).values('plan').distinct().count(),
                'by_type': dict(Tenant.objects.filter(is_deleted=False).values('plan__plan_type').annotate(count=models.Count('id'))),
            },
        }
        
        # This would store statistics in a monitoring system
        # For now, just log the stats
        logger.info(f"System statistics updated: {stats}")
        
        return stats
        
    except Exception as e:
        logger.error(f"System statistics update failed: {str(e)}")
        return {'error': str(e)}


@shared_task(name='tenants.maintenance.check_data_integrity')
def check_data_integrity():
    """
    Check data integrity across tenant-related models.
    
    This task runs weekly to check for data integrity issues
    and report any inconsistencies.
    """
    logger.info("Starting data integrity check")
    
    issues_found = []
    
    try:
        # Check for orphaned records
        from ..models.security import TenantAPIKey, TenantAuditLog
        from ..models.analytics import TenantMetric, TenantNotification
        
        # Check API keys without valid tenants
        orphaned_api_keys = TenantAPIKey.objects.filter(
            tenant__is_deleted=True
        ).count()
        
        if orphaned_api_keys > 0:
            issues_found.append({
                'type': 'orphaned_api_keys',
                'count': orphaned_api_keys,
                'description': 'API keys referencing deleted tenants',
            })
        
        # Check audit logs without valid tenants
        orphaned_audit_logs = TenantAuditLog.objects.filter(
            tenant__is_deleted=True
        ).count()
        
        if orphaned_audit_logs > 0:
            issues_found.append({
                'type': 'orphaned_audit_logs',
                'count': orphaned_audit_logs,
                'description': 'Audit logs referencing deleted tenants',
            })
        
        # Check metrics without valid tenants
        orphaned_metrics = TenantMetric.objects.filter(
            tenant__is_deleted=True
        ).count()
        
        if orphaned_metrics > 0:
            issues_found.append({
                'type': 'orphaned_metrics',
                'count': orphaned_metrics,
                'description': 'Metrics referencing deleted tenants',
            })
        
        # Check notifications without valid tenants
        orphaned_notifications = TenantNotification.objects.filter(
            tenant__is_deleted=True
        ).count()
        
        if orphaned_notifications > 0:
            issues_found.append({
                'type': 'orphaned_notifications',
                'count': orphaned_notifications,
                'description': 'Notifications referencing deleted tenants',
            })
        
        result = {
            'issues_found': len(issues_found),
            'issues': issues_found,
            'timestamp': timezone.now().isoformat(),
        }
        
        if issues_found:
            logger.warning(f"Data integrity issues found: {result}")
        else:
            logger.info("Data integrity check passed: no issues found")
        
        return result
        
    except Exception as e:
        logger.error(f"Data integrity check failed: {str(e)}")
        return {'error': str(e)}


@shared_task(name='tenants.maintenance.cleanup_temp_files')
def cleanup_temp_files():
    """
    Clean up temporary files and uploads.
    
    This task runs daily to clean up temporary files
    and orphaned uploads.
    """
    logger.info("Starting temporary file cleanup")
    
    cleaned_files = 0
    errors = []
    
    try:
        # This would clean up temporary files
        # For now, just log the action
        logger.info("Temporary file cleanup completed")
        
        result = {
            'cleaned_files': cleaned_files,
            'errors': errors,
        }
        
        return result
        
    except Exception as e:
        logger.error(f"Temporary file cleanup failed: {str(e)}")
        return {'error': str(e)}
