"""
Analytics Tasks

This module contains Celery tasks for analytics operations including
metrics collection, health scoring, and reporting.
"""

from celery import shared_task
from django.utils import timezone
from django.db.models import Avg, Sum, Count, Max, Min
import logging

from ..models.analytics import TenantMetric, TenantHealthScore, TenantFeatureFlag, TenantNotification
from ..models.core import Tenant
from ..services import TenantMetricService, TenantHealthScoreService

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def generate_analytics_report(self, tenant_id=None, report_type='comprehensive', days=30):
    """
    Generate analytics report for tenants.
    
    Args:
        tenant_id (str): Specific tenant ID (optional)
        report_type (str): Type of report ('comprehensive', 'usage', 'health', 'financial')
        days (int): Number of days to include
    """
    try:
        start_date = timezone.now() - timezone.timedelta(days=days)
        
        # Get tenants to analyze
        if tenant_id:
            tenants = [Tenant.objects.get(id=tenant_id)]
        else:
            tenants = Tenant.objects.filter(is_active=True, is_deleted=False)
        
        report = {
            'report_type': report_type,
            'period': {
                'start_date': start_date.date(),
                'end_date': timezone.now().date(),
                'days': days
            },
            'generated_at': timezone.now(),
            'tenant_reports': []
        }
        
        for tenant in tenants:
            tenant_report = {
                'tenant_id': tenant.id,
                'tenant_name': tenant.name,
                'tenant_slug': tenant.slug,
                'plan': tenant.plan.name if tenant.plan else None
            }
            
            if report_type in ['comprehensive', 'usage']:
                tenant_report['usage'] = _generate_usage_report(tenant, start_date)
            
            if report_type in ['comprehensive', 'health']:
                tenant_report['health'] = _generate_health_report(tenant, start_date)
            
            if report_type in ['comprehensive', 'financial']:
                tenant_report['financial'] = _generate_financial_report(tenant, start_date)
            
            report['tenant_reports'].append(tenant_report)
        
        # Generate summary
        report['summary'] = _generate_report_summary(report['tenant_reports'])
        
        logger.info(f"Generated {report_type} report for {len(tenants)} tenants")
        
        return report
        
    except Exception as exc:
        logger.error(f"Error generating analytics report: {str(exc)}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def export_tenant_data(self, tenant_id, data_types=['all'], format='json'):
    """
    Export tenant data for analysis or backup.
    
    Args:
        tenant_id (str): Tenant ID to export
        data_types (list): Types of data to export
        format (str): Export format ('json', 'csv')
    """
    try:
        tenant = Tenant.objects.get(id=tenant_id)
        
        export_data = {
            'tenant_info': {
                'id': tenant.id,
                'name': tenant.name,
                'slug': tenant.slug,
                'created_at': tenant.created_at.isoformat(),
                'status': tenant.status,
                'tier': tenant.tier
            },
            'exported_at': timezone.now().isoformat(),
            'data_types': data_types,
            'format': format
        }
        
        # Export different data types
        if 'all' in data_types or 'metrics' in data_types:
            export_data['metrics'] = _export_tenant_metrics(tenant)
        
        if 'all' in data_types or 'health_scores' in data_types:
            export_data['health_scores'] = _export_tenant_health_scores(tenant)
        
        if 'all' in data_types or 'feature_flags' in data_types:
            export_data['feature_flags'] = _export_tenant_feature_flags(tenant)
        
        if 'all' in data_types or 'notifications' in data_types:
            export_data['notifications'] = _export_tenant_notifications(tenant)
        
        if 'all' in data_types or 'billing' in data_types:
            export_data['billing'] = _export_tenant_billing(tenant)
        
        if 'all' in data_types or 'settings' in data_types:
            export_data['settings'] = _export_tenant_settings(tenant)
        
        logger.info(f"Exported data for tenant {tenant_id} in {format} format")
        
        return export_data
        
    except Exception as exc:
        logger.error(f"Error exporting tenant data: {str(exc)}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def import_tenant_data(self, tenant_id, import_data, overwrite=False):
    """
    Import tenant data from export.
    
    Args:
        tenant_id (str): Tenant ID to import to
        import_data (dict): Data to import
        overwrite (bool): Whether to overwrite existing data
    """
    try:
        tenant = Tenant.objects.get(id=tenant_id)
        
        import_results = {
            'tenant_id': tenant_id,
            'imported_at': timezone.now(),
            'data_types_imported': [],
            'import_counts': {},
            'errors': []
        }
        
        # Import different data types
        if 'metrics' in import_data:
            result = _import_tenant_metrics(tenant, import_data['metrics'], overwrite)
            import_results['data_types_imported'].append('metrics')
            import_results['import_counts']['metrics'] = result['count']
            if result.get('errors'):
                import_results['errors'].extend(result['errors'])
        
        if 'feature_flags' in import_data:
            result = _import_tenant_feature_flags(tenant, import_data['feature_flags'], overwrite)
            import_results['data_types_imported'].append('feature_flags')
            import_results['import_counts']['feature_flags'] = result['count']
            if result.get('errors'):
                import_results['errors'].extend(result['errors'])
        
        if 'notifications' in import_data:
            result = _import_tenant_notifications(tenant, import_data['notifications'], overwrite)
            import_results['data_types_imported'].append('notifications')
            import_results['import_counts']['notifications'] = result['count']
            if result.get('errors'):
                import_results['errors'].extend(result['errors'])
        
        logger.info(f"Imported data for tenant {tenant_id}")
        
        return import_results
        
    except Exception as exc:
        logger.error(f"Error importing tenant data: {str(exc)}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def data_integrity_check(self, tenant_id=None):
    """
    Perform data integrity checks on tenant data.
    
    Args:
        tenant_id (str): Specific tenant ID (optional)
    """
    try:
        # Get tenants to check
        if tenant_id:
            tenants = [Tenant.objects.get(id=tenant_id)]
        else:
            tenants = Tenant.objects.filter(is_active=True, is_deleted=False)
        
        integrity_results = {
            'checked_at': timezone.now(),
            'tenant_results': [],
            'summary': {
                'total_tenants': len(tenants),
                'issues_found': 0,
                'critical_issues': 0
            }
        }
        
        for tenant in tenants:
            tenant_result = {
                'tenant_id': tenant.id,
                'tenant_name': tenant.name,
                'checks': {},
                'issues': [],
                'critical_issues': []
            }
            
            # Check metrics integrity
            metrics_issues = _check_metrics_integrity(tenant)
            tenant_result['checks']['metrics'] = metrics_issues
            tenant_result['issues'].extend(metrics_issues.get('issues', []))
            tenant_result['critical_issues'].extend(metrics_issues.get('critical_issues', []))
            
            # Check health scores integrity
            health_issues = _check_health_scores_integrity(tenant)
            tenant_result['checks']['health_scores'] = health_issues
            tenant_result['issues'].extend(health_issues.get('issues', []))
            tenant_result['critical_issues'].extend(health_issues.get('critical_issues', []))
            
            # Check feature flags integrity
            flag_issues = _check_feature_flags_integrity(tenant)
            tenant_result['checks']['feature_flags'] = flag_issues
            tenant_result['issues'].extend(flag_issues.get('issues', []))
            tenant_result['critical_issues'].extend(flag_issues.get('critical_issues', []))
            
            # Check billing integrity
            billing_issues = _check_billing_integrity(tenant)
            tenant_result['checks']['billing'] = billing_issues
            tenant_result['issues'].extend(billing_issues.get('issues', []))
            tenant_result['critical_issues'].extend(billing_issues.get('critical_issues', []))
            
            integrity_results['tenant_results'].append(tenant_result)
            integrity_results['summary']['issues_found'] += len(tenant_result['issues'])
            integrity_results['summary']['critical_issues'] += len(tenant_result['critical_issues'])
        
        logger.info(f"Data integrity check completed for {len(tenants)} tenants")
        
        return integrity_results
        
    except Exception as exc:
        logger.error(f"Error performing data integrity check: {str(exc)}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def backup_analytics(self, tenant_id=None, days=90):
    """
    Backup analytics data for long-term storage.
    
    Args:
        tenant_id (str): Specific tenant ID (optional)
        days (int): Number of days of data to backup
    """
    try:
        cutoff_date = timezone.now() - timezone.timedelta(days=days)
        
        # Get data to backup
        metrics_queryset = TenantMetric.objects.filter(date__lt=cutoff_date)
        health_scores_queryset = TenantHealthScore.objects.filter(calculated_at__lt=cutoff_date)
        notifications_queryset = TenantNotification.objects.filter(created_at__lt=cutoff_date)
        
        if tenant_id:
            metrics_queryset = metrics_queryset.filter(tenant_id=tenant_id)
            health_scores_queryset = health_scores_queryset.filter(tenant_id=tenant_id)
            notifications_queryset = notifications_queryset.filter(tenant_id=tenant_id)
        
        backup_results = {
            'backup_date': timezone.now(),
            'cutoff_date': cutoff_date,
            'backup_counts': {},
            'backup_files': []
        }
        
        # Backup metrics
        if metrics_queryset.exists():
            metrics_backup = _backup_metrics_data(metrics_queryset)
            backup_results['backup_counts']['metrics'] = metrics_queryset.count()
            backup_results['backup_files'].append(metrics_backup)
        
        # Backup health scores
        if health_scores_queryset.exists():
            health_backup = _backup_health_scores_data(health_scores_queryset)
            backup_results['backup_counts']['health_scores'] = health_scores_queryset.count()
            backup_results['backup_files'].append(health_backup)
        
        # Backup notifications
        if notifications_queryset.exists():
            notifications_backup = _backup_notifications_data(notifications_queryset)
            backup_results['backup_counts']['notifications'] = notifications_queryset.count()
            backup_results['backup_files'].append(notifications_backup)
        
        # Optionally delete old data after backup
        if getattr(settings, 'ANALYTICS_DELETE_AFTER_BACKUP', False):
            metrics_queryset.delete()
            health_scores_queryset.delete()
            notifications_queryset.delete()
            backup_results['data_deleted'] = True
        
        logger.info(f"Analytics backup completed for data older than {days} days")
        
        return backup_results
        
    except Exception as exc:
        logger.error(f"Error backing up analytics data: {str(exc)}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def calculate_trends(self, tenant_id=None, days=30):
    """
    Calculate trends for tenant metrics and health scores.
    
    Args:
        tenant_id (str): Specific tenant ID (optional)
        days (int): Number of days to analyze
    """
    try:
        start_date = timezone.now() - timezone.timedelta(days=days)
        
        # Get tenants to analyze
        if tenant_id:
            tenants = [Tenant.objects.get(id=tenant_id)]
        else:
            tenants = Tenant.objects.filter(is_active=True, is_deleted=False)
        
        trends_results = {
            'calculated_at': timezone.now(),
            'period': {
                'start_date': start_date.date(),
                'end_date': timezone.now().date(),
                'days': days
            },
            'tenant_trends': []
        }
        
        for tenant in tenants:
            tenant_trends = {
                'tenant_id': tenant.id,
                'tenant_name': tenant.name,
                'metric_trends': {},
                'health_trends': {}
            }
            
            # Calculate metric trends
            metric_types = ['api_calls', 'active_users', 'storage_usage', 'bandwidth_usage']
            for metric_type in metric_types:
                trend = _calculate_metric_trend(tenant, metric_type, start_date)
                tenant_trends['metric_trends'][metric_type] = trend
            
            # Calculate health score trends
            health_trend = _calculate_health_trend(tenant, start_date)
            tenant_trends['health_trends'] = health_trend
            
            trends_results['tenant_trends'].append(tenant_trends)
        
        logger.info(f"Calculated trends for {len(tenants)} tenants over {days} days")
        
        return trends_results
        
    except Exception as exc:
        logger.error(f"Error calculating trends: {str(exc)}")
        raise self.retry(exc=exc, countdown=60)


# Helper functions
def _generate_usage_report(tenant, start_date):
    """Generate usage report for tenant."""
    metrics = TenantMetric.objects.filter(
        tenant=tenant,
        date__gte=start_date.date()
    )
    
    usage_report = {
        'total_metrics': metrics.count(),
        'metrics_by_type': {},
        'daily_averages': {},
        'peak_usage': {}
    }
    
    # Group by metric type
    for metric_type in ['api_calls', 'active_users', 'storage_usage', 'bandwidth_usage']:
        type_metrics = metrics.filter(metric_type=metric_type)
        usage_report['metrics_by_type'][metric_type] = {
            'count': type_metrics.count(),
            'total': type_metrics.aggregate(total=Sum('value'))['total'] or 0,
            'average': type_metrics.aggregate(avg=Avg('value'))['avg'] or 0,
            'max': type_metrics.aggregate(max=Max('value'))['max'] or 0,
            'min': type_metrics.aggregate(min=Min('value'))['min'] or 0
        }
    
    return usage_report


def _generate_health_report(tenant, start_date):
    """Generate health report for tenant."""
    health_scores = TenantHealthScore.objects.filter(
        tenant=tenant,
        calculated_at__gte=start_date
    )
    
    health_report = {
        'total_scores': health_scores.count(),
        'average_score': health_scores.aggregate(avg=Avg('overall_score'))['avg'] or 0,
        'latest_score': None,
        'score_trend': 'stable',
        'risk_distribution': {}
    }
    
    # Get latest score
    latest_score = health_scores.order_by('-calculated_at').first()
    if latest_score:
        health_report['latest_score'] = {
            'score': latest_score.overall_score,
            'grade': latest_score.health_grade,
            'risk_level': latest_score.risk_level,
            'calculated_at': latest_score.calculated_at.isoformat()
        }
    
    # Risk distribution
    for risk_level in ['low', 'medium', 'high', 'critical']:
        count = health_scores.filter(risk_level=risk_level).count()
        health_report['risk_distribution'][risk_level] = count
    
    return health_report


def _generate_financial_report(tenant, start_date):
    """Generate financial report for tenant."""
    from ..models.core import TenantInvoice
    
    invoices = TenantInvoice.objects.filter(
        tenant=tenant,
        issue_date__gte=start_date.date()
    )
    
    financial_report = {
        'total_invoices': invoices.count(),
        'total_revenue': invoices.aggregate(total=Sum('total_amount'))['total'] or 0,
        'paid_invoices': invoices.filter(status='paid').count(),
        'pending_invoices': invoices.filter(status='pending').count(),
        'overdue_invoices': invoices.filter(status='overdue').count(),
        'average_invoice_amount': invoices.aggregate(avg=Avg('total_amount'))['avg'] or 0
    }
    
    return financial_report


def _generate_report_summary(tenant_reports):
    """Generate summary of all tenant reports."""
    summary = {
        'total_tenants': len(tenant_reports),
        'average_metrics': {},
        'health_summary': {},
        'financial_summary': {}
    }
    
    if not tenant_reports:
        return summary
    
    # Calculate averages
    total_usage = 0
    total_health = 0
    total_revenue = 0
    
    for report in tenant_reports:
        if 'usage' in report:
            total_usage += report['usage'].get('total_metrics', 0)
        
        if 'health' in report:
            total_health += report['health'].get('average_score', 0)
        
        if 'financial' in report:
            total_revenue += report['financial'].get('total_revenue', 0)
    
    summary['average_metrics'] = {
        'average_usage_per_tenant': total_usage / len(tenant_reports)
    }
    
    summary['health_summary'] = {
        'average_health_score': total_health / len(tenant_reports)
    }
    
    summary['financial_summary'] = {
        'average_revenue_per_tenant': total_revenue / len(tenant_reports)
    }
    
    return summary


def _export_tenant_metrics(tenant):
    """Export tenant metrics."""
    metrics = TenantMetric.objects.filter(tenant=tenant)
    return [
        {
            'date': metric.date.isoformat(),
            'metric_type': metric.metric_type,
            'value': metric.value,
            'metadata': metric.metadata
        }
        for metric in metrics
    ]


def _export_tenant_health_scores(tenant):
    """Export tenant health scores."""
    health_scores = TenantHealthScore.objects.filter(tenant=tenant)
    return [
        {
            'period': health_score.period,
            'overall_score': health_score.overall_score,
            'health_grade': health_score.health_grade,
            'risk_level': health_score.risk_level,
            'component_scores': health_score.component_scores,
            'calculated_at': health_score.calculated_at.isoformat()
        }
        for health_score in health_scores
    ]


def _export_tenant_feature_flags(tenant):
    """Export tenant feature flags."""
    feature_flags = TenantFeatureFlag.objects.filter(tenant=tenant)
    return [
        {
            'flag_key': flag.flag_key,
            'name': flag.name,
            'description': flag.description,
            'is_enabled': flag.is_enabled,
            'rollout_pct': flag.rollout_pct,
            'starts_at': flag.starts_at.isoformat() if flag.starts_at else None,
            'expires_at': flag.expires_at.isoformat() if flag.expires_at else None
        }
        for flag in feature_flags
    ]


def _export_tenant_notifications(tenant):
    """Export tenant notifications."""
    notifications = TenantNotification.objects.filter(tenant=tenant)
    return [
        {
            'title': notification.title,
            'message': notification.message,
            'notification_type': notification.notification_type,
            'priority': notification.priority,
            'status': notification.status,
            'created_at': notification.created_at.isoformat(),
            'read_at': notification.read_at.isoformat() if notification.read_at else None
        }
        for notification in notifications
    ]


def _export_tenant_billing(tenant):
    """Export tenant billing information."""
    from ..models.core import TenantBilling, TenantInvoice
    
    billing = TenantBilling.objects.filter(tenant=tenant).first()
    invoices = TenantInvoice.objects.filter(tenant=tenant)
    
    billing_data = {}
    
    if billing:
        billing_data['billing'] = {
            'status': billing.status,
            'billing_cycle': billing.billing_cycle,
            'payment_method': billing.payment_method,
            'base_price': float(billing.base_price),
            'final_price': float(billing.final_price),
            'currency': billing.currency
        }
    
    billing_data['invoices'] = [
        {
            'invoice_number': invoice.invoice_number,
            'status': invoice.status,
            'total_amount': float(invoice.total_amount),
            'issue_date': invoice.issue_date.isoformat(),
            'due_date': invoice.due_date.isoformat()
        }
        for invoice in invoices
    ]
    
    return billing_data


def _export_tenant_settings(tenant):
    """Export tenant settings."""
    from ..models.core import TenantSettings
    
    settings = TenantSettings.objects.filter(tenant=tenant).first()
    
    if settings:
        return {
            'enable_smartlink': settings.enable_smartlink,
            'enable_analytics': settings.enable_analytics,
            'enable_api_access': settings.enable_api_access,
            'default_language': settings.default_language,
            'default_currency': settings.default_currency,
            'default_timezone': settings.default_timezone,
            'theme': settings.theme,
            'custom_settings': settings.custom_settings
        }
    
    return {}


def _import_tenant_metrics(tenant, metrics_data, overwrite):
    """Import tenant metrics."""
    from ..models.analytics import TenantMetric
    
    imported_count = 0
    errors = []
    
    for metric_data in metrics_data:
        try:
            if overwrite:
                TenantMetric.objects.update_or_create(
                    tenant=tenant,
                    date=timezone.datetime.fromisoformat(metric_data['date']).date(),
                    metric_type=metric_data['metric_type'],
                    defaults={
                        'value': metric_data['value'],
                        'metadata': metric_data.get('metadata', {})
                    }
                )
            else:
                TenantMetric.objects.get_or_create(
                    tenant=tenant,
                    date=timezone.datetime.fromisoformat(metric_data['date']).date(),
                    metric_type=metric_data['metric_type'],
                    defaults={
                        'value': metric_data['value'],
                        'metadata': metric_data.get('metadata', {})
                    }
                )
            imported_count += 1
        except Exception as e:
            errors.append(f"Error importing metric: {str(e)}")
    
    return {'count': imported_count, 'errors': errors}


def _import_tenant_feature_flags(tenant, flags_data, overwrite):
    """Import tenant feature flags."""
    from ..models.analytics import TenantFeatureFlag
    
    imported_count = 0
    errors = []
    
    for flag_data in flags_data:
        try:
            if overwrite:
                TenantFeatureFlag.objects.update_or_create(
                    tenant=tenant,
                    flag_key=flag_data['flag_key'],
                    defaults={
                        'name': flag_data['name'],
                        'description': flag_data.get('description', ''),
                        'is_enabled': flag_data['is_enabled'],
                        'rollout_pct': flag_data.get('rollout_pct', 100),
                        'starts_at': timezone.datetime.fromisoformat(flag_data['starts_at']) if flag_data.get('starts_at') else None,
                        'expires_at': timezone.datetime.fromisoformat(flag_data['expires_at']) if flag_data.get('expires_at') else None
                    }
                )
            else:
                TenantFeatureFlag.objects.get_or_create(
                    tenant=tenant,
                    flag_key=flag_data['flag_key'],
                    defaults={
                        'name': flag_data['name'],
                        'description': flag_data.get('description', ''),
                        'is_enabled': flag_data['is_enabled'],
                        'rollout_pct': flag_data.get('rollout_pct', 100),
                        'starts_at': timezone.datetime.fromisoformat(flag_data['starts_at']) if flag_data.get('starts_at') else None,
                        'expires_at': timezone.datetime.fromisoformat(flag_data['expires_at']) if flag_data.get('expires_at') else None
                    }
                )
            imported_count += 1
        except Exception as e:
            errors.append(f"Error importing feature flag: {str(e)}")
    
    return {'count': imported_count, 'errors': errors}


def _import_tenant_notifications(tenant, notifications_data, overwrite):
    """Import tenant notifications."""
    from ..models.analytics import TenantNotification
    
    imported_count = 0
    errors = []
    
    for notification_data in notifications_data:
        try:
            # Don't import existing notifications unless overwriting
            if not overwrite:
                continue
            
            TenantNotification.objects.update_or_create(
                tenant=tenant,
                title=notification_data['title'],
                message=notification_data['message'],
                defaults={
                    'notification_type': notification_data.get('notification_type', 'system'),
                    'priority': notification_data.get('priority', 'medium'),
                    'status': notification_data.get('status', 'sent'),
                    'created_at': timezone.datetime.fromisoformat(notification_data['created_at'])
                }
            )
            imported_count += 1
        except Exception as e:
            errors.append(f"Error importing notification: {str(e)}")
    
    return {'count': imported_count, 'errors': errors}


def _check_metrics_integrity(tenant):
    """Check metrics data integrity."""
    issues = []
    critical_issues = []
    
    # Check for duplicate metrics
    duplicates = TenantMetric.objects.filter(tenant=tenant).values(
        'date', 'metric_type'
    ).annotate(count=Count('id')).filter(count__gt=1)
    
    if duplicates.exists():
        issues.append(f"Found {duplicates.count()} duplicate metric records")
    
    # Check for negative values where not expected
    negative_metrics = TenantMetric.objects.filter(
        tenant=tenant,
        value__lt=0,
        metric_type__in=['api_calls', 'active_users', 'storage_usage', 'bandwidth_usage']
    )
    
    if negative_metrics.exists():
        critical_issues.append(f"Found {negative_metrics.count()} metrics with negative values")
    
    return {'issues': issues, 'critical_issues': critical_issues}


def _check_health_scores_integrity(tenant):
    """Check health scores data integrity."""
    issues = []
    critical_issues = []
    
    # Check for scores outside valid range
    invalid_scores = TenantHealthScore.objects.filter(
        tenant=tenant,
        overall_score__lt=0
    ) | TenantHealthScore.objects.filter(
        tenant=tenant,
        overall_score__gt=100
    )
    
    if invalid_scores.exists():
        critical_issues.append(f"Found {invalid_scores.count()} health scores outside 0-100 range")
    
    return {'issues': issues, 'critical_issues': critical_issues}


def _check_feature_flags_integrity(tenant):
    """Check feature flags data integrity."""
    issues = []
    critical_issues = []
    
    # Check for rollout percentages outside valid range
    invalid_rollout = TenantFeatureFlag.objects.filter(
        tenant=tenant,
        rollout_pct__lt=0
    ) | TenantFeatureFlag.objects.filter(
        tenant=tenant,
        rollout_pct__gt=100
    )
    
    if invalid_rollout.exists():
        issues.append(f"Found {invalid_rollout.count()} feature flags with invalid rollout percentages")
    
    return {'issues': issues, 'critical_issues': critical_issues}


def _check_billing_integrity(tenant):
    """Check billing data integrity."""
    from ..models.core import TenantBilling, TenantInvoice
    
    issues = []
    critical_issues = []
    
    # Check for negative amounts
    negative_invoices = TenantInvoice.objects.filter(
        tenant=tenant,
        total_amount__lt=0
    )
    
    if negative_invoices.exists():
        critical_issues.append(f"Found {negative_invoices.count()} invoices with negative amounts")
    
    return {'issues': issues, 'critical_issues': critical_issues}


def _backup_metrics_data(queryset):
    """Backup metrics data to file."""
    import json
    from django.core.files.base import ContentFile
    import uuid
    
    backup_data = []
    for metric in queryset:
        backup_data.append({
            'tenant_id': metric.tenant_id,
            'date': metric.date.isoformat(),
            'metric_type': metric.metric_type,
            'value': metric.value,
            'metadata': metric.metadata,
            'created_at': metric.created_at.isoformat()
        })
    
    filename = f"metrics_backup_{uuid.uuid4()}.json"
    content = ContentFile(json.dumps(backup_data, indent=2), name=filename)
    
    return {'filename': filename, 'record_count': len(backup_data)}


def _backup_health_scores_data(queryset):
    """Backup health scores data to file."""
    import json
    from django.core.files.base import ContentFile
    import uuid
    
    backup_data = []
    for health_score in queryset:
        backup_data.append({
            'tenant_id': health_score.tenant_id,
            'period': health_score.period,
            'overall_score': health_score.overall_score,
            'health_grade': health_score.health_grade,
            'risk_level': health_score.risk_level,
            'component_scores': health_score.component_scores,
            'calculated_at': health_score.calculated_at.isoformat()
        })
    
    filename = f"health_scores_backup_{uuid.uuid4()}.json"
    content = ContentFile(json.dumps(backup_data, indent=2), name=filename)
    
    return {'filename': filename, 'record_count': len(backup_data)}


def _backup_notifications_data(queryset):
    """Backup notifications data to file."""
    import json
    from django.core.files.base import ContentFile
    import uuid
    
    backup_data = []
    for notification in queryset:
        backup_data.append({
            'tenant_id': notification.tenant_id,
            'title': notification.title,
            'message': notification.message,
            'notification_type': notification.notification_type,
            'priority': notification.priority,
            'status': notification.status,
            'created_at': notification.created_at.isoformat()
        })
    
    filename = f"notifications_backup_{uuid.uuid4()}.json"
    content = ContentFile(json.dumps(backup_data, indent=2), name=filename)
    
    return {'filename': filename, 'record_count': len(backup_data)}


def _calculate_metric_trend(tenant, metric_type, start_date):
    """Calculate trend for a specific metric."""
    metrics = TenantMetric.objects.filter(
        tenant=tenant,
        metric_type=metric_type,
        date__gte=start_date.date()
    ).order_by('date')
    
    if metrics.count() < 2:
        return {'trend': 'insufficient_data'}
    
    first_value = metrics.first().value
    last_value = metrics.last().value
    
    change = last_value - first_value
    change_percentage = (change / first_value * 100) if first_value != 0 else 0
    
    if change_percentage > 10:
        trend = 'increasing'
    elif change_percentage < -10:
        trend = 'decreasing'
    else:
        trend = 'stable'
    
    return {
        'trend': trend,
        'change': change,
        'change_percentage': change_percentage,
        'first_value': first_value,
        'last_value': last_value,
        'data_points': metrics.count()
    }


def _calculate_health_trend(tenant, start_date):
    """Calculate health score trend."""
    health_scores = TenantHealthScore.objects.filter(
        tenant=tenant,
        calculated_at__gte=start_date
    ).order_by('calculated_at')
    
    if health_scores.count() < 2:
        return {'trend': 'insufficient_data'}
    
    first_score = health_scores.first().overall_score
    last_score = health_scores.last().overall_score
    
    change = last_score - first_score
    
    if change > 5:
        trend = 'improving'
    elif change < -5:
        trend = 'declining'
    else:
        trend = 'stable'
    
    return {
        'trend': trend,
        'change': change,
        'first_score': first_score,
        'last_score': last_score,
        'data_points': health_scores.count()
    }
