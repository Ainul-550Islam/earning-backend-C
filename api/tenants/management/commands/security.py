"""
Security Management Commands

This module contains Django management commands for security operations
including API key rotation, security event monitoring, and reporting.
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db.models import Count, Sum, Avg
import json
from datetime import timedelta

from ...models.security import TenantAPIKey, TenantAuditLog
from ...services import TenantAuditService


class RotateAPIKeysCommand(BaseCommand):
    """
    Rotate API keys for security.
    
    Usage:
        python manage.py rotate_api_keys [--tenant=<tenant_id>] [--dry-run]
    """
    
    help = "Rotate API keys for security"
    
    def add_arguments(self, parser):
        parser.add_argument('--tenant', type=str, help='Rotate keys for specific tenant ID or name')
        parser.add_argument('--days', type=int, default=90, help='Rotate keys older than N days')
        parser.add_argument('--dry-run', action='store_true', help='Show what would be rotated without rotating')
    
    def handle(self, *args, **options):
        tenant_id = options.get('tenant')
        days = options['days']
        dry_run = options['dry_run']
        
        self.stdout.write(f"Rotating API keys older than {days} days")
        
        # Get API keys to rotate
        cutoff_date = timezone.now() - timedelta(days=days)
        
        if tenant_id:
            try:
                tenant = Tenant.objects.get(id=tenant_id)
                api_keys = TenantAPIKey.objects.filter(
                    tenant=tenant,
                    created_at__lt=cutoff_date,
                    status='active'
                )
            except (Tenant.DoesNotExist, ValueError):
                try:
                    tenant = Tenant.objects.get(name=tenant_id)
                    api_keys = TenantAPIKey.objects.filter(
                        tenant=tenant,
                        created_at__lt=cutoff_date,
                        status='active'
                    )
                except Tenant.DoesNotExist:
                    raise CommandError(f"Tenant '{tenant_id}' not found")
        else:
            api_keys = TenantAPIKey.objects.filter(
                created_at__lt=cutoff_date,
                status='active'
            ).select_related('tenant')
        
        rotated_count = 0
        failed_count = 0
        
        for api_key in api_keys:
            try:
                if dry_run:
                    self.stdout.write(f"Would rotate key: {api_key.name} ({api_key.tenant.name})")
                    rotated_count += 1
                else:
                    # Generate new key
                    from ...models.security import TenantAPIKey
                    new_key = TenantAPIKey.generate_key()
                    api_key.set_key(new_key)
                    api_key.status = 'active'
                    api_key.save(update_fields=['key_hash', 'key_prefix', 'status'])
                    
                    # Send notification
                    from ...models.analytics import TenantNotification
                    
                    TenantNotification.objects.create(
                        tenant=api_key.tenant,
                        title='API Key Rotated',
                        message=f'API key "{api_key.name}" has been automatically rotated for security.',
                        notification_type='security',
                        priority='medium',
                        send_email=True,
                        send_push=True,
                        action_url='/security/api-keys',
                        action_text='Manage API Keys',
                    )
                    
                    rotated_count += 1
                    self.stdout.write(f"Rotated key: {api_key.name} ({api_key.tenant.name})")
            
            except Exception as e:
                failed_count += 1
                self.stdout.write(
                    self.style.ERROR(f"Failed to rotate key {api_key.name}: {str(e)}")
                )
        
        action = "Would rotate" if dry_run else "Rotated"
        self.stdout.write(
            self.style.SUCCESS(f"{action} {rotated_count} API keys, {failed_count} failed")
        )


class CheckSecurityEventsCommand(BaseCommand):
    """
    Check for security events and anomalies.
    
    Usage:
        python manage.py check_security_events [--hours=<hours>] [--format=<format>]
    """
    
    help = "Check for security events and anomalies"
    
    def add_arguments(self, parser):
        parser.add_argument('--hours', type=int, default=24, help='Hours to check back')
        parser.add_argument('--format', type=str, choices=['table', 'json'], default='table', help='Output format')
    
    def handle(self, *args, **options):
        hours = options['hours']
        output_format = options['format']
        
        self.stdout.write(f"Checking security events for last {hours} hours")
        
        # Get recent security events
        from datetime import timedelta
        
        last_hours = timezone.now() - timedelta(hours=hours)
        
        security_events = TenantAuditLog.objects.filter(
            action='security_event',
            created_at__gte=last_hours
        ).select_related('tenant')
        
        # Group by tenant
        events_by_tenant = {}
        for event in security_events:
            tenant_id = event.tenant.id
            if tenant_id not in events_by_tenant:
                events_by_tenant[tenant_id] = {
                    'tenant': event.tenant,
                    'events': []
                }
            events_by_tenant[tenant_id]['events'].append(event)
        
        # Detect anomalies
        anomalies = []
        for tenant_id, data in events_by_tenant.items():
            tenant = data['tenant']
            events = data['events']
            
            # Check for high frequency of events
            if len(events) > 10:
                anomalies.append({
                    'tenant': tenant,
                    'type': 'high_frequency',
                    'count': len(events),
                    'description': f"High frequency of security events: {len(events)} in {hours} hours"
                })
            
            # Check for critical events
            critical_events = [e for e in events if e.severity == 'critical']
            if critical_events:
                anomalies.append({
                    'tenant': tenant,
                    'type': 'critical_events',
                    'count': len(critical_events),
                    'description': f"Critical security events detected: {len(critical_events)}"
                })
        
        # Build report data
        report_data = {
            'period_hours': hours,
            'total_events': security_events.count(),
            'affected_tenants': len(events_by_tenant),
            'events_by_severity': {},
            'anomalies': anomalies,
        }
        
        # Count by severity
        severity_counts = security_events.values('severity').annotate(count=Count('id'))
        report_data['events_by_severity'] = {s['severity']: s['count'] for s in severity_counts}
        
        if output_format == 'json':
            self.stdout.write(json.dumps(report_data, indent=2))
        else:
            self._output_table(report_data)
    
    def _output_table(self, report_data):
        """Output in table format."""
        self.stdout.write(self.style.SUCCESS("Security Events Report"))
        self.stdout.write("=" * 50)
        
        # Summary
        self.stdout.write(f"Period: Last {report_data['period_hours']} hours")
        self.stdout.write(f"Total Events: {report_data['total_events']}")
        self.stdout.write(f"Affected Tenants: {report_data['affected_tenants']}")
        
        # By severity
        self.stdout.write(f"\nEvents by Severity:")
        for severity, count in report_data['events_by_severity'].items():
            self.stdout.write(f"  {severity}: {count}")
        
        # Anomalies
        if report_data['anomalies']:
            self.stdout.write(f"\nAnomalies Detected:")
            for anomaly in report_data['anomalies']:
                self.stdout.write(f"  {anomaly['tenant'].name}: {anomaly['description']}")
        else:
            self.stdout.write(f"\nNo anomalies detected")


class GenerateSecurityReportCommand(BaseCommand):
    """
    Generate comprehensive security report.
    
    Usage:
        python manage.py generate_security_report [--days=<days>] [--format=<format>]
    """
    
    help = "Generate comprehensive security report"
    
    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=30, help='Number of days for report')
        parser.add_argument('--format', type=str, choices=['table', 'json'], default='table', help='Output format')
    
    def handle(self, *args, **options):
        days = options['days']
        output_format = options['format']
        
        self.stdout.write(f"Generating security report for last {days} days")
        
        # Calculate date range
        from datetime import timedelta
        
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        # Collect security data
        report_data = {
            'period_days': days,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'api_keys': {},
            'audit_logs': {},
            'security_events': {},
            'recommendations': [],
        }
        
        # API key statistics
        api_keys = TenantAPIKey.objects.all()
        report_data['api_keys'] = {
            'total': api_keys.count(),
            'active': api_keys.filter(status='active').count(),
            'inactive': api_keys.filter(status='inactive').count(),
            'expired': api_keys.filter(status='expired').count(),
            'revoked': api_keys.filter(status='revoked').count(),
        }
        
        # Audit log statistics
        audit_logs = TenantAuditLog.objects.filter(
            created_at__range=[start_date, end_date]
        )
        report_data['audit_logs'] = {
            'total': audit_logs.count(),
            'by_action': {},
            'by_severity': {},
            'by_tenant': audit_logs.values('tenant').distinct().count(),
        }
        
        # Count by action
        action_counts = audit_logs.values('action').annotate(count=Count('id'))
        report_data['audit_logs']['by_action'] = {a['action']: a['count'] for a in action_counts}
        
        # Count by severity
        severity_counts = audit_logs.values('severity').annotate(count=Count('id'))
        report_data['audit_logs']['by_severity'] = {s['severity']: s['count'] for s in severity_counts}
        
        # Security events
        security_events = audit_logs.filter(action='security_event')
        report_data['security_events'] = {
            'total': security_events.count(),
            'critical': security_events.filter(severity='critical').count(),
            'high': security_events.filter(severity='high').count(),
            'medium': security_events.filter(severity='medium').count(),
            'low': security_events.filter(severity='low').count(),
        }
        
        # Generate recommendations
        recommendations = []
        
        # Check for expired API keys
        if report_data['api_keys']['expired'] > 0:
            recommendations.append({
                'type': 'security',
                'priority': 'high',
                'message': f"Found {report_data['api_keys']['expired']} expired API keys. Consider cleaning them up.",
            })
        
        # Check for critical security events
        if report_data['security_events']['critical'] > 0:
            recommendations.append({
                'type': 'security',
                'priority': 'critical',
                'message': f"Found {report_data['security_events']['critical']} critical security events. Immediate attention required.",
            })
        
        # Check for high volume of security events
        if report_data['security_events']['total'] > 100:
            recommendations.append({
                'type': 'security',
                'priority': 'medium',
                'message': f"High volume of security events ({report_data['security_events']['total']}). Review for potential issues.",
            })
        
        report_data['recommendations'] = recommendations
        
        if output_format == 'json':
            self.stdout.write(json.dumps(report_data, indent=2))
        else:
            self._output_table(report_data, start_date, end_date)
    
    def _output_table(self, report_data, start_date, end_date):
        """Output in table format."""
        self.stdout.write(self.style.SUCCESS(f"Security Report: {start_date.date()} to {end_date.date()}"))
        self.stdout.write("=" * 60)
        
        # API keys
        api_keys = report_data['api_keys']
        self.stdout.write(f"API Keys:")
        self.stdout.write(f"  Total: {api_keys['total']}")
        self.stdout.write(f"  Active: {api_keys['active']}")
        self.stdout.write(f"  Expired: {api_keys['expired']}")
        self.stdout.write(f"  Revoked: {api_keys['revoked']}")
        
        # Audit logs
        audit_logs = report_data['audit_logs']
        self.stdout.write(f"\nAudit Logs:")
        self.stdout.write(f"  Total: {audit_logs['total']}")
        self.stdout.write(f"  Unique Tenants: {audit_logs['by_tenant']}")
        
        # Security events
        security_events = report_data['security_events']
        self.stdout.write(f"\nSecurity Events:")
        self.stdout.write(f"  Total: {security_events['total']}")
        self.stdout.write(f"  Critical: {security_events['critical']}")
        self.stdout.write(f"  High: {security_events['high']}")
        self.stdout.write(f"  Medium: {security_events['medium']}")
        
        # Recommendations
        if report_data['recommendations']:
            self.stdout.write(f"\nRecommendations:")
            for rec in report_data['recommendations']:
                priority_icon = "!" if rec['priority'] == 'critical' else "*" if rec['priority'] == 'high' else "-"
                self.stdout.write(f"  {priority_icon} [{rec['priority'].upper()}] {rec['message']}")
        else:
            self.stdout.write(f"\nNo security recommendations at this time.")


class AuditLogExportCommand(BaseCommand):
    """
    Export audit logs for analysis.
    
    Usage:
        python manage.py audit_log_export [--days=<days>] [--format=<format>] [--file=<file>]
    """
    
    help = "Export audit logs for analysis"
    
    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=30, help='Number of days to export')
        parser.add_argument('--format', type=str, choices=['csv', 'json'], default='csv', help='Export format')
        parser.add_argument('--file', type=str, help='Output filename (without extension)')
    
    def handle(self, *args, **options):
        days = options['days']
        export_format = options['format']
        filename = options.get('file', f'audit_logs_{days}_days')
        
        self.stdout.write(f"Exporting audit logs for last {days} days")
        
        # Calculate date range
        from datetime import timedelta
        from django.http import HttpResponse
        
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        # Get audit logs
        audit_logs = TenantAuditLog.objects.filter(
            created_at__range=[start_date, end_date]
        ).select_related('tenant', 'actor')
        
        # Export data
        if export_format == 'csv':
            import csv
            import io
            
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write header
            writer.writerow([
                'Timestamp', 'Tenant', 'Action', 'Severity', 'Actor',
                'Description', 'IP Address', 'User Agent', 'Request ID'
            ])
            
            # Write data
            for log in audit_logs:
                writer.writerow([
                    log.created_at.isoformat(),
                    log.tenant.name if log.tenant else 'System',
                    log.action,
                    log.severity,
                    log.actor_display,
                    log.description,
                    log.ip_address or '',
                    log.user_agent or '',
                    log.request_id or '',
                ])
            
            content = output.getvalue()
            content_type = 'text/csv'
        else:  # JSON
            import json
            
            export_data = []
            for log in audit_logs:
                export_data.append({
                    'timestamp': log.created_at.isoformat(),
                    'tenant': log.tenant.name if log.tenant else 'System',
                    'action': log.action,
                    'severity': log.severity,
                    'actor': log.actor_display,
                    'description': log.description,
                    'ip_address': log.ip_address,
                    'user_agent': log.user_agent,
                    'request_id': log.request_id,
                    'metadata': log.metadata,
                })
            
            content = json.dumps(export_data, indent=2)
            content_type = 'application/json'
        
        # Write to file
        file_path = f"{filename}.{export_format}"
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            self.stdout.write(
                self.style.SUCCESS(f"Exported {audit_logs.count()} audit logs to {file_path}")
            )
        
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Failed to export audit logs: {str(e)}")
            )


class SecurityScanCommand(BaseCommand):
    """
    Perform security scan of the system.
    
    Usage:
        python manage.py security_scan [--format=<format>]
    """
    
    help = "Perform security scan of the system"
    
    def add_arguments(self, parser):
        parser.add_argument('--format', type=str, choices=['table', 'json'], default='table', help='Output format')
    
    def handle(self, *args, **options):
        output_format = options['format']
        
        self.stdout.write("Performing security scan")
        
        scan_results = {
            'timestamp': timezone.now().isoformat(),
            'scan_results': {
                'api_keys': {},
                'audit_logs': {},
                'tenant_security': {},
                'system_security': {},
            },
            'overall_score': 0,
            'issues': [],
            'recommendations': [],
        }
        
        # Scan API keys
        api_keys = TenantAPIKey.objects.all()
        expired_keys = api_keys.filter(status='expired').count()
        active_keys = api_keys.filter(status='active').count()
        
        scan_results['scan_results']['api_keys'] = {
            'total': api_keys.count(),
            'active': active_keys,
            'expired': expired_keys,
            'issues': expired_keys,
        }
        
        if expired_keys > 0:
            scan_results['issues'].append({
                'type': 'api_keys',
                'severity': 'medium',
                'description': f"Found {expired_keys} expired API keys",
            })
        
        # Scan audit logs for anomalies
        from datetime import timedelta
        
        recent_logs = TenantAuditLog.objects.filter(
            created_at__gte=timezone.now() - timedelta(hours=24)
        )
        
        security_events = recent_logs.filter(action='security_event')
        critical_events = security_events.filter(severity='critical').count()
        
        scan_results['scan_results']['audit_logs'] = {
            'total_recent': recent_logs.count(),
            'security_events': security_events.count(),
            'critical_events': critical_events,
            'issues': critical_events,
        }
        
        if critical_events > 0:
            scan_results['issues'].append({
                'type': 'audit_logs',
                'severity': 'critical',
                'description': f"Found {critical_events} critical security events in last 24 hours",
            })
        
        # Scan tenant security settings
        from ...models import Tenant
        
        tenants = Tenant.objects.filter(is_deleted=False)
        tenants_without_2fa = tenants.filter(settings__enable_two_factor_auth=False).count()
        
        scan_results['scan_results']['tenant_security'] = {
            'total_tenants': tenants.count(),
            'without_2fa': tenants_without_2fa,
            'issues': tenants_without_2fa,
        }
        
        if tenants_without_2fa > 0:
            scan_results['issues'].append({
                'type': 'tenant_security',
                'severity': 'medium',
                'description': f"{tenants_without_2fa} tenants without two-factor authentication",
            })
        
        # Calculate overall score
        total_issues = len(scan_results['issues'])
        critical_issues = len([i for i in scan_results['issues'] if i['severity'] == 'critical'])
        
        if critical_issues > 0:
            scan_results['overall_score'] = 20
        elif total_issues > 5:
            scan_results['overall_score'] = 50
        elif total_issues > 0:
            scan_results['overall_score'] = 80
        else:
            scan_results['overall_score'] = 95
        
        # Generate recommendations
        scan_results['recommendations'] = [
            {
                'type': 'api_keys',
                'priority': 'medium',
                'message': 'Regularly clean up expired API keys to maintain security',
            },
            {
                'type': 'audit_logs',
                'priority': 'high',
                'message': 'Monitor security events and respond quickly to critical events',
            },
            {
                'type': 'tenant_security',
                'priority': 'medium',
                'message': 'Encourage tenants to enable two-factor authentication',
            },
        ]
        
        if output_format == 'json':
            self.stdout.write(json.dumps(scan_results, indent=2))
        else:
            self._output_table(scan_results)
    
    def _output_table(self, scan_results):
        """Output in table format."""
        self.stdout.write(self.style.SUCCESS("Security Scan Results"))
        self.stdout.write("=" * 50)
        
        # Overall score
        score = scan_results['overall_score']
        score_color = self.style.SUCCESS if score >= 80 else self.style.WARNING if score >= 50 else self.style.ERROR
        self.stdout.write(f"Overall Security Score: {score_color(score)}{score}/100")
        
        # Issues
        issues = scan_results['issues']
        if issues:
            self.stdout.write(f"\nIssues Found ({len(issues)}):")
            for issue in issues:
                priority_icon = "!!" if issue['severity'] == 'critical' else "!" if issue['severity'] == 'high' else "*"
                self.stdout.write(f"  {priority_icon} [{issue['severity'].upper()}] {issue['description']}")
        else:
            self.stdout.write(f"\nNo security issues found!")
        
        # Scan results
        results = scan_results['scan_results']
        self.stdout.write(f"\nScan Details:")
        
        # API keys
        api_keys = results['api_keys']
        self.stdout.write(f"  API Keys: {api_keys['total']} total, {api_keys['active']} active, {api_keys['expired']} expired")
        
        # Audit logs
        audit_logs = results['audit_logs']
        self.stdout.write(f"  Audit Logs: {audit_logs['total_recent']} recent, {audit_logs['security_events']} security events, {audit_logs['critical_events']} critical")
        
        # Tenant security
        tenant_security = results['tenant_security']
        self.stdout.write(f"  Tenant Security: {tenant_security['total_tenants']} tenants, {tenant_security['without_2fa']} without 2FA")
        
        # Recommendations
        recommendations = scan_results['recommendations']
        self.stdout.write(f"\nRecommendations:")
        for rec in recommendations:
            self.stdout.write(f"  - {rec['message']}")
        
        if score < 80:
            self.stdout.write(f"\n{self.style.WARNING('Security score below 80. Consider addressing the issues above.')}")
        elif score < 50:
            self.stdout.write(f"\n{self.style.ERROR('Security score below 50. Immediate attention required.')}")
