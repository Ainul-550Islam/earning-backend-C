"""
Analytics Management Commands

This module contains Django management commands for analytics operations
including report generation, data export, and import.
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db.models import Count, Sum, Avg
import json
from datetime import timedelta

from ...models.analytics import TenantMetric, TenantHealthScore, TenantNotification
from ...models import Tenant


class GenerateAnalyticsReportCommand(BaseCommand):
    """
    Generate comprehensive analytics report.
    
    Usage:
        python manage.py generate_analytics_report [--period=<period>] [--format=<format>]
    """
    
    help = "Generate comprehensive analytics report"
    
    def add_arguments(self, parser):
        parser.add_argument('--period', type=str, choices=['daily', 'weekly', 'monthly'], default='monthly', help='Report period')
        parser.add_argument('--format', type=str, choices=['table', 'json'], default='table', help='Output format')
        parser.add_argument('--days', type=int, default=30, help='Number of days for report')
    
    def handle(self, *args, **options):
        period = options['period']
        output_format = options['format']
        days = options['days']
        
        self.stdout.write(f"Generating {period} analytics report for last {days} days")
        
        # Calculate date range
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        # Collect comprehensive analytics data
        report_data = {
            'period': period,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'days': days,
            'tenant_metrics': {},
            'health_scores': {},
            'notifications': {},
            'usage_trends': {},
            'performance_metrics': {},
        }
        
        # Tenant metrics
        tenant_count = Tenant.objects.filter(is_deleted=False).count()
        active_tenants = Tenant.objects.filter(is_deleted=False, status='active').count()
        trial_tenants = Tenant.objects.filter(is_deleted=False, status='trial').count()
        suspended_tenants = Tenant.objects.filter(is_deleted=False, status='suspended').count()
        
        report_data['tenant_metrics'] = {
            'total_tenants': tenant_count,
            'active_tenants': active_tenants,
            'trial_tenants': trial_tenants,
            'suspended_tenants': suspended_tenants,
            'activation_rate': (active_tenants / tenant_count * 100) if tenant_count > 0 else 0,
        }
        
        # Health scores
        health_scores = TenantHealthScore.objects.all()
        grade_distribution = health_scores.values('health_grade').annotate(count=Count('id'))
        risk_distribution = health_scores.values('risk_level').annotate(count=Count('id'))
        
        report_data['health_scores'] = {
            'total_scores': health_scores.count(),
            'average_score': health_scores.aggregate(avg=Avg('overall_score'))['avg'] or 0,
            'grade_distribution': {g['health_grade']: g['count'] for g in grade_distribution},
            'risk_distribution': {r['risk_level']: r['count'] for r in risk_distribution},
            'high_risk_tenants': health_scores.filter(risk_level='high').count(),
            'critical_risk_tenants': health_scores.filter(risk_level='critical').count(),
        }
        
        # Notifications
        notifications = TenantNotification.objects.filter(
            created_at__range=[start_date, end_date]
        )
        notification_stats = notifications.values('notification_type').annotate(count=Count('id'))
        priority_stats = notifications.values('priority').annotate(count=Count('id'))
        
        report_data['notifications'] = {
            'total_notifications': notifications.count(),
            'by_type': {n['notification_type']: n['count'] for n in notification_stats},
            'by_priority': {p['priority']: p['count'] for p in priority_stats},
            'high_priority': notifications.filter(priority='high').count(),
            'urgent_notifications': notifications.filter(priority='urgent').count(),
        }
        
        # Usage trends
        recent_metrics = TenantMetric.objects.filter(
            date__range=[start_date, end_date]
        )
        metric_types = recent_metrics.values_list('metric_type', flat=True).distinct()
        
        for metric_type in metric_types:
            type_metrics = recent_metrics.filter(metric_type=metric_type)
            values = [float(m.value) for m in type_metrics.order_by('date')]
            
            if len(values) >= 2:
                first_value = values[0]
                last_value = values[-1]
                change_pct = ((last_value - first_value) / first_value) * 100 if first_value != 0 else 0
                
                report_data['usage_trends'][metric_type] = {
                    'trend': 'up' if change_pct > 5 else 'down' if change_pct < -5 else 'stable',
                    'change_percentage': round(change_pct, 2),
                    'data_points': len(values),
                    'first_value': first_value,
                    'last_value': last_value,
                }
        
        # Performance metrics
        from ...models.security import TenantAuditLog
        
        audit_logs = TenantAuditLog.objects.filter(
            created_at__range=[start_date, end_date]
        )
        
        report_data['performance_metrics'] = {
            'total_api_calls': audit_logs.filter(action='api_access').count(),
            'security_events': audit_logs.filter(action='security_event').count(),
            'config_changes': audit_logs.filter(action='config_change').count(),
            'billing_events': audit_logs.filter(action='billing_event').count(),
            'average_response_time': 0.5,  # Placeholder - would calculate from actual data
            'system_uptime': 99.9,  # Placeholder - would calculate from actual data
        }
        
        if output_format == 'json':
            self.stdout.write(json.dumps(report_data, indent=2))
        else:
            self._output_table(report_data, start_date, end_date)
    
    def _output_table(self, report_data, start_date, end_date):
        """Output in table format."""
        self.stdout.write(self.style.SUCCESS(f"Analytics Report: {start_date} to {end_date}"))
        self.stdout.write("=" * 60)
        
        # Tenant metrics
        tenant_metrics = report_data['tenant_metrics']
        self.stdout.write(f"Tenant Metrics:")
        self.stdout.write(f"  Total: {tenant_metrics['total_tenants']}")
        self.stdout.write(f"  Active: {tenant_metrics['active_tenants']}")
        self.stdout.write(f"  Trial: {tenant_metrics['trial_tenants']}")
        self.stdout.write(f"  Suspended: {tenant_metrics['suspended_tenants']}")
        self.stdout.write(f"  Activation Rate: {tenant_metrics['activation_rate']:.1f}%")
        
        # Health scores
        health_scores = report_data['health_scores']
        self.stdout.write(f"\nHealth Scores:")
        self.stdout.write(f"  Average Score: {health_scores['average_score']:.1f}")
        self.stdout.write(f"  High Risk: {health_scores['high_risk_tenants']}")
        self.stdout.write(f"  Critical Risk: {health_scores['critical_risk_tenants']}")
        
        # Notifications
        notifications = report_data['notifications']
        self.stdout.write(f"\nNotifications:")
        self.stdout.write(f"  Total: {notifications['total_notifications']}")
        self.stdout.write(f"  High Priority: {notifications['high_priority']}")
        self.stdout.write(f"  Urgent: {notifications['urgent_notifications']}")
        
        # Performance metrics
        performance = report_data['performance_metrics']
        self.stdout.write(f"\nPerformance Metrics:")
        self.stdout.write(f"  API Calls: {performance['total_api_calls']:,}")
        self.stdout.write(f"  Security Events: {performance['security_events']}")
        self.stdout.write(f"  Config Changes: {performance['config_changes']}")
        self.stdout.write(f"  Billing Events: {performance['billing_events']}")
        
        # Usage trends
        trends = report_data['usage_trends']
        if trends:
            self.stdout.write(f"\nUsage Trends:")
            for metric_type, trend_data in trends.items():
                self.stdout.write(f"  {metric_type}: {trend_data['trend']} ({trend_data['change_percentage']:+.1f}%)")


class ExportTenantDataCommand(BaseCommand):
    """
    Export all data for a specific tenant.
    
    Usage:
        python manage.py export_tenant_data <tenant_id_or_name> [--format=<format>] [--file=<file>]
    """
    
    help = "Export all data for a specific tenant"
    
    def add_arguments(self, parser):
        parser.add_argument('tenant', type=str, help='Tenant ID or name')
        parser.add_argument('--format', type=str, choices=['json', 'csv'], default='json', help='Export format')
        parser.add_argument('--file', type=str, help='Output filename (without extension)')
    
    def handle(self, *args, **options):
        tenant_id = options['tenant']
        export_format = options['format']
        filename = options.get('file', f'tenant_data_{tenant_id}')
        
        self.stdout.write(f"Exporting data for tenant: {tenant_id}")
        
        # Get tenant
        try:
            tenant = Tenant.objects.get(id=tenant_id)
        except (Tenant.DoesNotExist, ValueError):
            try:
                tenant = Tenant.objects.get(name=tenant_id)
            except Tenant.DoesNotExist:
                raise CommandError(f"Tenant '{tenant_id}' not found")
        
        # Collect all tenant data
        export_data = {
            'tenant_info': {
                'id': str(tenant.id),
                'name': tenant.name,
                'slug': tenant.slug,
                'status': tenant.status,
                'tier': tenant.tier,
                'created_at': tenant.created_at.isoformat(),
                'last_activity_at': tenant.last_activity_at.isoformat() if tenant.last_activity_at else None,
                'trial_ends_at': tenant.trial_ends_at.isoformat() if tenant.trial_ends_at else None,
            },
            'settings': {},
            'billing': {},
            'metrics': [],
            'notifications': [],
            'audit_logs': [],
            'api_keys': [],
        }
        
        # Settings
        try:
            settings = tenant.settings
            export_data['settings'] = {
                'enable_smartlink': settings.enable_smartlink,
                'enable_ai_engine': settings.enable_ai_engine,
                'max_users': settings.max_users,
                'api_calls_per_day': settings.api_calls_per_day,
                'storage_gb': settings.storage_gb,
            }
        except:
            pass
        
        # Billing
        try:
            billing = tenant.billing
            export_data['billing'] = {
                'billing_cycle': billing.billing_cycle,
                'payment_method': billing.payment_method,
                'final_price': float(billing.final_price),
                'next_billing_date': billing.next_billing_date.isoformat(),
            }
        except:
            pass
        
        # Metrics
        metrics = TenantMetric.objects.filter(tenant=tenant)
        for metric in metrics:
            export_data['metrics'].append({
                'metric_type': metric.metric_type,
                'value': metric.value,
                'unit': metric.unit,
                'date': metric.date.isoformat(),
                'created_at': metric.created_at.isoformat(),
            })
        
        # Notifications
        notifications = TenantNotification.objects.filter(tenant=tenant)
        for notification in notifications:
            export_data['notifications'].append({
                'title': notification.title,
                'message': notification.message,
                'notification_type': notification.notification_type,
                'priority': notification.priority,
                'status': notification.status,
                'created_at': notification.created_at.isoformat(),
            })
        
        # Audit logs
        from ...models.security import TenantAuditLog
        audit_logs = TenantAuditLog.objects.filter(tenant=tenant)
        for log in audit_logs:
            export_data['audit_logs'].append({
                'action': log.action,
                'severity': log.severity,
                'description': log.description,
                'created_at': log.created_at.isoformat(),
                'ip_address': log.ip_address,
            })
        
        # API keys
        from ...models.security import TenantAPIKey
        api_keys = TenantAPIKey.objects.filter(tenant=tenant)
        for api_key in api_keys:
            export_data['api_keys'].append({
                'name': api_key.name,
                'status': api_key.status,
                'scopes': api_key.scopes,
                'created_at': api_key.created_at.isoformat(),
                'last_used_at': api_key.last_used_at.isoformat() if api_key.last_used_at else None,
            })
        
        # Export data
        if export_format == 'json':
            content = json.dumps(export_data, indent=2)
            file_path = f"{filename}.json"
        else:  # CSV
            import csv
            import io
            
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write tenant info
            writer.writerow(['Tenant Information'])
            for key, value in export_data['tenant_info'].items():
                writer.writerow([key, value])
            
            writer.writerow([])
            writer.writerow(['Metrics'])
            writer.writerow(['Type', 'Value', 'Unit', 'Date'])
            for metric in export_data['metrics']:
                writer.writerow([metric['metric_type'], metric['value'], metric['unit'], metric['date']])
            
            content = output.getvalue()
            file_path = f"{filename}.csv"
        
        # Write to file
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            self.stdout.write(
                self.style.SUCCESS(f"Exported tenant data to {file_path}")
            )
        
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Failed to export tenant data: {str(e)}")
            )


class ImportTenantDataCommand(BaseCommand):
    """
    Import tenant data from file.
    
    Usage:
        python manage.py import_tenant_data <file_path> [--dry-run]
    """
    
    help = "Import tenant data from file"
    
    def add_arguments(self, parser):
        parser.add_argument('file_path', type=str, help='Path to import file')
        parser.add_argument('--dry-run', action='store_true', help='Show what would be imported without importing')
    
    def handle(self, *args, **options):
        file_path = options['file_path']
        dry_run = options['dry-run']
        
        self.stdout.write(f"Importing tenant data from: {file_path}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                if file_path.endswith('.json'):
                    import_data = json.load(f)
                else:
                    self.stdout.write(
                        self.style.ERROR("Only JSON files are supported for import")
                    )
                    return
            
            # Validate import data
            if 'tenant_info' not in import_data:
                self.stdout.write(
                    self.style.ERROR("Invalid import data format")
                )
                return
            
            tenant_info = import_data['tenant_info']
            
            if dry_run:
                self.stdout.write(f"Would import tenant: {tenant_info['name']}")
                self.stdout.write(f"  Metrics: {len(import_data.get('metrics', []))}")
                self.stdout.write(f"  Notifications: {len(import_data.get('notifications', []))}")
                self.stdout.write(f"  Audit Logs: {len(import_data.get('audit_logs', []))}")
                self.stdout.write(f"  API Keys: {len(import_data.get('api_keys', []))}")
            else:
                # Find or create tenant
                tenant, created = Tenant.objects.get_or_create(
                    name=tenant_info['name'],
                    defaults={
                        'slug': tenant_info.get('slug', tenant_info['name'].lower().replace(' ', '-')),
                        'status': tenant_info.get('status', 'active'),
                        'tier': tenant_info.get('tier', 'basic'),
                    }
                )
                
                if created:
                    self.stdout.write(f"Created tenant: {tenant.name}")
                else:
                    self.stdout.write(f"Found existing tenant: {tenant.name}")
                
                # Import metrics
                for metric_data in import_data.get('metrics', []):
                    TenantMetric.objects.create(
                        tenant=tenant,
                        metric_type=metric_data['metric_type'],
                        value=metric_data['value'],
                        unit=metric_data.get('unit', ''),
                        date=timezone.datetime.fromisoformat(metric_data['date']).date(),
                    )
                
                # Import notifications
                for notification_data in import_data.get('notifications', []):
                    TenantNotification.objects.create(
                        tenant=tenant,
                        title=notification_data['title'],
                        message=notification_data['message'],
                        notification_type=notification_data['notification_type'],
                        priority=notification_data.get('priority', 'medium'),
                        status=notification_data.get('status', 'pending'),
                    )
                
                self.stdout.write(
                    self.style.SUCCESS(f"Imported data for tenant: {tenant.name}")
                )
        
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Failed to import tenant data: {str(e)}")
            )


class DataIntegrityCheckCommand(BaseCommand):
    """
    Check data integrity across the tenant system.
    
    Usage:
        python manage.py data_integrity_check [--fix] [--format=<format>]
    """
    
    help = "Check data integrity across the tenant system"
    
    def add_arguments(self, parser):
        parser.add_argument('--fix', action='store_true', help='Fix integrity issues found')
        parser.add_argument('--format', type=str, choices=['table', 'json'], default='table', help='Output format')
    
    def handle(self, *args, **options):
        fix_issues = options['fix']
        output_format = options['format']
        
        self.stdout.write("Checking data integrity")
        
        integrity_results = {
            'timestamp': timezone.now().isoformat(),
            'checks': {
                'orphaned_records': {},
                'missing_relations': {},
                'data_consistency': {},
                'duplicate_records': {},
            },
            'issues_found': 0,
            'issues_fixed': 0,
        }
        
        # Check for orphaned metrics
        orphaned_metrics = TenantMetric.objects.filter(
            tenant__isnull=True
        ).count()
        
        integrity_results['checks']['orphaned_metrics'] = {
            'count': orphaned_metrics,
            'fixed': 0,
        }
        
        if orphaned_metrics > 0:
            integrity_results['issues_found'] += 1
            
            if fix_issues:
                deleted = TenantMetric.objects.filter(tenant__isnull=True).delete()[0]
                integrity_results['checks']['orphaned_metrics']['fixed'] = deleted
                integrity_results['issues_fixed'] += 1
        
        # Check for orphaned notifications
        orphaned_notifications = TenantNotification.objects.filter(
            tenant__isnull=True
        ).count()
        
        integrity_results['checks']['orphaned_notifications'] = {
            'count': orphaned_notifications,
            'fixed': 0,
        }
        
        if orphaned_notifications > 0:
            integrity_results['issues_found'] += 1
            
            if fix_issues:
                deleted = TenantNotification.objects.filter(tenant__isnull=True).delete()[0]
                integrity_results['checks']['orphaned_notifications']['fixed'] = deleted
                integrity_results['issues_fixed'] += 1
        
        # Check for duplicate tenant slugs
        from django.db.models import Count
        
        duplicate_slugs = Tenant.objects.values('slug').annotate(
            count=Count('id')
        ).filter(count__gt=1).count()
        
        integrity_results['checks']['duplicate_slugs'] = {
            'count': duplicate_slugs,
            'fixed': 0,
        }
        
        if duplicate_slugs > 0:
            integrity_results['issues_found'] += 1
            # Note: Fixing duplicate slugs requires manual intervention
        
        # Check for missing health scores
        tenants_without_health = Tenant.objects.filter(
            is_deleted=False
        ).exclude(
            healthscore__isnull=False
        ).count()
        
        integrity_results['checks']['missing_health_scores'] = {
            'count': tenants_without_health,
            'fixed': 0,
        }
        
        if tenants_without_health > 0:
            integrity_results['issues_found'] += 1
            
            if fix_issues:
                from ...models.analytics import TenantHealthScore
                
                created = 0
                for tenant in Tenant.objects.filter(is_deleted=False).filter(healthscore__isnull=True):
                    TenantHealthScore.objects.create(tenant=tenant)
                    created += 1
                
                integrity_results['checks']['missing_health_scores']['fixed'] = created
                integrity_results['issues_fixed'] += 1
        
        if output_format == 'json':
            self.stdout.write(json.dumps(integrity_results, indent=2))
        else:
            self._output_table(integrity_results)
    
    def _output_table(self, results):
        """Output in table format."""
        self.stdout.write(self.style.SUCCESS("Data Integrity Check"))
        self.stdout.write("=" * 50)
        
        self.stdout.write(f"Issues Found: {results['issues_found']}")
        self.stdout.write(f"Issues Fixed: {results['issues_fixed']}")
        
        checks = results['checks']
        self.stdout.write(f"\nCheck Results:")
        
        for check_name, check_data in checks.items():
            status = "OK" if check_data['count'] == 0 else "ISSUE"
            color = self.style.SUCCESS if check_data['count'] == 0 else self.style.WARNING
            
            self.stdout.write(f"  {color}{status)} {check_name}: {check_data['count']} found")
            if check_data['fixed'] > 0:
                self.stdout.write(f"    Fixed: {check_data['fixed']}")
        
        if results['issues_found'] > 0 and results['issues_fixed'] < results['issues_found']:
            self.stdout.write(f"\n{self.style.WARNING('Some issues remain. Run with --fix to resolve automatically.')}")
        elif results['issues_found'] > 0:
            self.stdout.write(f"\n{self.style.SUCCESS('All issues have been fixed!')}")
        else:
            self.stdout.write(f"\n{self.style.SUCCESS('No integrity issues found!')}")


class BackupAnalyticsCommand(BaseCommand):
    """
    Backup analytics data for archiving.
    
    Usage:
        python manage.py backup_analytics [--days=<days>] [--dry-run]
    """
    
    help = "Backup analytics data for archiving"
    
    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=365, help='Number of days to keep')
        parser.add_argument('--dry-run', action='store_true', help='Show what would be backed up without backing up')
    
    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry-run']
        
        self.stdout.write(f"Backing up analytics data older than {days} days")
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Get old metrics
        old_metrics = TenantMetric.objects.filter(
            created_at__lt=cutoff_date
        ).select_related('tenant')
        
        # Get old notifications
        old_notifications = TenantNotification.objects.filter(
            created_at__lt=cutoff_date
        ).select_related('tenant')
        
        backup_data = {
            'backup_date': timezone.now().isoformat(),
            'cutoff_date': cutoff_date.isoformat(),
            'metrics': [],
            'notifications': [],
        }
        
        # Collect metrics data
        for metric in old_metrics:
            backup_data['metrics'].append({
                'id': str(metric.id),
                'tenant_id': str(metric.tenant.id),
                'tenant_name': metric.tenant.name,
                'metric_type': metric.metric_type,
                'value': metric.value,
                'unit': metric.unit,
                'date': metric.date.isoformat(),
                'created_at': metric.created_at.isoformat(),
            })
        
        # Collect notifications data
        for notification in old_notifications:
            backup_data['notifications'].append({
                'id': str(notification.id),
                'tenant_id': str(notification.tenant.id),
                'tenant_name': notification.tenant.name,
                'title': notification.title,
                'message': notification.message,
                'notification_type': notification.notification_type,
                'priority': notification.priority,
                'status': notification.status,
                'created_at': notification.created_at.isoformat(),
            })
        
        if dry_run:
            self.stdout.write(f"Would backup {len(backup_data['metrics'])} metrics and {len(backup_data['notifications'])} notifications")
        else:
            # Write backup to file
            backup_filename = f"analytics_backup_{cutoff_date.date().isoformat()}.json"
            
            try:
                with open(backup_filename, 'w', encoding='utf-8') as f:
                    json.dump(backup_data, f, indent=2)
                
                # Delete old data
                old_metrics.delete()
                old_notifications.delete()
                
                self.stdout.write(
                    self.style.SUCCESS(f"Backed up data to {backup_filename}")
                )
                self.stdout.write(f"Deleted {len(backup_data['metrics'])} metrics and {len(backup_data['notifications'])} notifications")
            
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"Failed to backup analytics data: {str(e)}")
                )
