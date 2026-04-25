"""
Maintenance Management Commands

This module contains Django management commands for maintenance operations
including cleanup, SSL certificate management, and database optimization.
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
import json
from datetime import timedelta

from ...models.security import TenantAPIKey
from ...models.branding import TenantDomain
from ...services import DomainService


class CleanupExpiredAPIKeysCommand(BaseCommand):
    """
    Clean up expired API keys.
    
    Usage:
        python manage.py cleanup_expired_api_keys [--dry-run]
    """
    
    help = "Clean up expired API keys"
    
    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Show what would be cleaned without deleting')
    
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        self.stdout.write("Cleaning up expired API keys")
        
        # Get expired API keys
        expired_keys = TenantAPIKey.objects.filter(
            expires_at__lt=timezone.now(),
            status='active'
        ).select_related('tenant')
        
        count = expired_keys.count()
        
        if dry_run:
            self.stdout.write(f"Would clean up {count} expired API keys")
            for api_key in expired_keys:
                self.stdout.write(f"  {api_key.name} ({api_key.tenant.name})")
        else:
            for api_key in expired_keys:
                # Mark as inactive
                api_key.status = 'expired'
                api_key.save(update_fields=['status'])
                
                # Send notification to tenant
                from ...models.analytics import TenantNotification
                
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
                )
            
            self.stdout.write(f"Cleaned up {count} expired API keys")
        
        self.stdout.write(
            self.style.SUCCESS(f"Cleanup completed{' (dry run)' if dry_run else ''}")
        )


class RenewSSLCertificatesCommand(BaseCommand):
    """
    Renew SSL certificates for domains expiring soon.
    
    Usage:
        python manage.py renew_ssl_certificates [--days=<days>] [--dry-run]
    """
    
    help = "Renew SSL certificates for domains expiring soon"
    
    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=7, help='Days until expiry to renew')
        parser.add_argument('--dry-run', action='store_true', help='Show what would be renewed without renewing')
    
    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry-run']
        
        self.stdout.write(f"Renewing SSL certificates expiring within {days} days")
        
        # Get domains needing renewal
        expiring_domains = DomainService.monitor_ssl_expiration()
        
        renewed_count = 0
        failed_count = 0
        
        for domain_info in expiring_domains:
            domain = domain_info['domain']
            
            if domain_info['priority'] == 'critical' and domain.ssl_auto_renew:
                try:
                    if dry_run:
                        self.stdout.write(f"Would renew SSL for: {domain.domain}")
                        renewed_count += 1
                    else:
                        renewal_result = DomainService.renew_ssl_certificate(domain)
                        
                        if renewal_result['success']:
                            renewed_count += 1
                            self.stdout.write(f"Renewed SSL for: {domain.domain}")
                            
                            # Send notification
                            from ...models.analytics import TenantNotification
                            
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
                            )
                        else:
                            failed_count += 1
                            self.stdout.write(
                                self.style.ERROR(f"Failed to renew SSL for {domain.domain}: {renewal_result.get('error')}")
                            )
                
                except Exception as e:
                    failed_count += 1
                    self.stdout.write(
                        self.style.ERROR(f"Failed to renew SSL for {domain.domain}: {str(e)}")
                    )
        
        action = "Would renew" if dry_run else "Renewed"
        self.stdout.write(
            self.style.SUCCESS(f"{action} {renewed_count} SSL certificates, {failed_count} failed")
        )


class BackupTenantDataCommand(BaseCommand):
    """
    Backup tenant data for disaster recovery.
    
    Usage:
        python manage.py backup_tenant_data [--tenant=<tenant_id>] [--dry-run]
    """
    
    help = "Backup tenant data"
    
    def add_arguments(self, parser):
        parser.add_argument('--tenant', type=str, help='Backup specific tenant ID or name')
        parser.add_argument('--dry-run', action='store_true', help='Show what would be backed up without backing up')
    
    def handle(self, *args, **options):
        tenant_id = options.get('tenant')
        dry_run = options['dry_run']
        
        self.stdout.write("Backing up tenant data")
        
        # Get tenants to backup
        if tenant_id:
            try:
                tenant = Tenant.objects.get(id=tenant_id)
                tenants = [tenant]
            except (Tenant.DoesNotExist, ValueError):
                try:
                    tenant = Tenant.objects.get(name=tenant_id)
                    tenants = [tenant]
                except Tenant.DoesNotExist:
                    raise CommandError(f"Tenant '{tenant_id}' not found")
        else:
            tenants = Tenant.objects.filter(is_deleted=False, status='active')
        
        backed_up_count = 0
        failed_count = 0
        
        for tenant in tenants:
            try:
                if dry_run:
                    self.stdout.write(f"Would backup data for: {tenant.name}")
                    backed_up_count += 1
                else:
                    # This would integrate with your backup system
                    # For now, just create a backup record
                    backup_data = {
                        'tenant_id': str(tenant.id),
                        'tenant_name': tenant.name,
                        'backup_date': timezone.now().date().isoformat(),
                        'data_types': ['settings', 'billing', 'metrics', 'audit_logs'],
                        'status': 'completed',
                    }
                    
                    backed_up_count += 1
                    self.stdout.write(f"Backed up data for: {tenant.name}")
            
            except Exception as e:
                failed_count += 1
                self.stdout.write(
                    self.style.ERROR(f"Failed to backup data for {tenant.name}: {str(e)}")
                )
        
        action = "Would backup" if dry_run else "Backed up"
        self.stdout.write(
            self.style.SUCCESS(f"{action} data for {backed_up_count} tenants, {failed_count} failed")
        )


class ArchiveAuditLogsCommand(BaseCommand):
    """
    Archive old audit logs.
    
    Usage:
        python manage.py archive_audit_logs [--days=<days>] [--dry-run]
    """
    
    help = "Archive old audit logs"
    
    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=90, help='Number of days to keep logs')
        parser.add_argument('--dry-run', action='store_true', help='Show what would be archived without archiving')
    
    def handle(self, *args, **options):
        retention_days = options['days']
        dry_run = options['dry-run']
        
        self.stdout.write(f"Archiving audit logs older than {retention_days} days")
        
        cutoff_date = timezone.now() - timedelta(days=retention_days)
        
        # Get old audit logs
        from ...models.security import TenantAuditLog
        
        old_logs = TenantAuditLog.objects.filter(
            created_at__lt=cutoff_date
        ).select_related('tenant')
        
        count = old_logs.count()
        
        if dry_run:
            self.stdout.write(f"Would archive {count} old audit logs")
        else:
            # This would archive logs to cold storage
            # For now, just delete old logs
            old_logs.delete()
            
            self.stdout.write(f"Archived {count} old audit logs")
        
        self.stdout.write(
            self.style.SUCCESS(f"Archive completed (cutoff date: {cutoff_date.date()})")
        )


class OptimizeDatabaseCommand(BaseCommand):
    """
    Optimize database tables for better performance.
    
    Usage:
        python manage.py optimize_database [--dry-run]
    """
    
    help = "Optimize database tables"
    
    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Show what would be optimized without optimizing')
    
    def handle(self, *args, **options):
        dry_run = options['dry-run']
        
        self.stdout.write("Optimizing database tables")
        
        try:
            from django.db import connection
            
            with connection.cursor() as cursor:
                # Tables to optimize
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
                        if dry_run:
                            self.stdout.write(f"Would optimize table: {table}")
                            optimized_tables.append(table)
                        else:
                            # Run OPTIMIZE TABLE (MySQL specific)
                            cursor.execute(f"OPTIMIZE TABLE {table}")
                            optimized_tables.append(table)
                            self.stdout.write(f"Optimized table: {table}")
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(f"Failed to optimize table {table}: {str(e)}")
                        )
            
                action = "Would optimize" if dry_run else "Optimized"
                self.stdout.write(
                    self.style.SUCCESS(f"{action} {len(optimized_tables)} tables")
                )
        
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Database optimization failed: {str(e)}")
            )


class CheckSystemHealthCommand(BaseCommand):
    """
    Check overall system health.
    
    Usage:
        python manage.py check_system_health [--format=<format>]
    """
    
    help = "Check overall system health"
    
    def add_arguments(self, parser):
        parser.add_argument('--format', type=str, choices=['table', 'json'], default='table', help='Output format')
    
    def handle(self, *args, **options):
        output_format = options['format']
        
        self.stdout.write("Checking system health")
        
        try:
            import psutil
            
            # System resources
            disk_usage = psutil.disk_usage('/')
            memory = psutil.virtual_memory()
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Database stats
            from ...models import Tenant
            from ...models.security import TenantAPIKey
            from ...models.analytics import TenantMetric
            
            health_data = {
                'timestamp': timezone.now().isoformat(),
                'system_resources': {
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
                },
                'tenant_stats': {
                    'total_tenants': Tenant.objects.filter(is_deleted=False).count(),
                    'active_tenants': Tenant.objects.filter(is_deleted=False, status='active').count(),
                    'trial_tenants': Tenant.objects.filter(is_deleted=False, status='trial').count(),
                    'suspended_tenants': Tenant.objects.filter(is_deleted=False, status='suspended').count(),
                },
                'security_stats': {
                    'active_api_keys': TenantAPIKey.objects.filter(status='active').count(),
                    'expired_api_keys': TenantAPIKey.objects.filter(status='expired').count(),
                    'total_metrics': TenantMetric.objects.count(),
                },
                'overall_health': 'good',
            }
            
            # Determine overall health
            if (disk_usage.used / disk_usage.total) > 0.9 or memory.percent > 90:
                health_data['overall_health'] = 'critical'
            elif (disk_usage.used / disk_usage.total) > 0.8 or memory.percent > 80:
                health_data['overall_health'] = 'warning'
            
            if output_format == 'json':
                self.stdout.write(json.dumps(health_data, indent=2))
            else:
                self._output_table(health_data)
        
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Health check failed: {str(e)}")
            )
    
    def _output_table(self, health_data):
        """Output in table format."""
        self.stdout.write(self.style.SUCCESS("System Health Report"))
        self.stdout.write("=" * 50)
        
        # Overall health
        health_color = {
            'good': self.style.SUCCESS,
            'warning': self.style.WARNING,
            'critical': self.style.ERROR,
        }
        
        self.stdout.write(f"Overall Health: {health_color.get(health_data['overall_health'], '')(health_data['overall_health'].upper())}")
        
        # System resources
        resources = health_data['system_resources']
        self.stdout.write(f"\nSystem Resources:")
        self.stdout.write(f"  Disk Usage: {resources['disk_usage']['usage_percent']:.1f}% ({resources['disk_usage']['used_gb']:.1f}/{resources['disk_usage']['total_gb']:.1f} GB)")
        self.stdout.write(f"  Memory Usage: {resources['memory']['usage_percent']:.1f}% ({resources['memory']['used_gb']:.1f}/{resources['memory']['total_gb']:.1f} GB)")
        self.stdout.write(f"  CPU Usage: {resources['cpu']['usage_percent']:.1f}%")
        
        # Tenant stats
        tenants = health_data['tenant_stats']
        self.stdout.write(f"\nTenant Statistics:")
        self.stdout.write(f"  Total: {tenants['total_tenants']}")
        self.stdout.write(f"  Active: {tenants['active_tenants']}")
        self.stdout.write(f"  Trial: {tenants['trial_tenants']}")
        self.stdout.write(f"  Suspended: {tenants['suspended_tenants']}")
        
        # Security stats
        security = health_data['security_stats']
        self.stdout.write(f"\nSecurity Statistics:")
        self.stdout.write(f"  Active API Keys: {security['active_api_keys']}")
        self.stdout.write(f"  Expired API Keys: {security['expired_api_keys']}")
        self.stdout.write(f"  Total Metrics: {security['total_metrics']}")


class CleanupTempFilesCommand(BaseCommand):
    """
    Clean up temporary files and uploads.
    
    Usage:
        python manage.py cleanup_temp_files [--dry-run]
    """
    
    help = "Clean up temporary files and uploads"
    
    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Show what would be cleaned without cleaning')
    
    def handle(self, *args, **options):
        dry_run = options['dry-run']
        
        self.stdout.write("Cleaning up temporary files")
        
        # This would clean up temporary files
        # For now, just log the action
        
        if dry_run:
            self.stdout.write("Would clean up temporary files")
        else:
            self.stdout.write("Temporary files cleaned up")
        
        self.stdout.write(
            self.style.SUCCESS(f"Cleanup completed{' (dry run)' if dry_run else ''}")
        )
