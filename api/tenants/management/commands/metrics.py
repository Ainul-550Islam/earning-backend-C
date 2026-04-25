"""
Metrics Management Commands

This module contains Django management commands for metrics operations
including collection, health score calculation, and cleanup.
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db.models import Count, Sum, Avg
import json
from datetime import timedelta

from ...models.analytics import TenantMetric, TenantHealthScore
from ...services import TenantMetricService


class CollectMetricsCommand(BaseCommand):
    """
    Collect metrics for all tenants.
    
    Usage:
        python manage.py collect_metrics [--date=<date>] [--type=<type>] [--tenant=<tenant_id>]
    """
    
    help = "Collect metrics for all tenants"
    
    def add_arguments(self, parser):
        parser.add_argument('--date', type=str, help='Date for metric collection (YYYY-MM-DD)')
        parser.add_argument('--type', type=str, choices=['daily', 'weekly', 'monthly'], default='daily', help='Metric collection type')
        parser.add_argument('--tenant', type=str, help='Collect metrics for specific tenant ID or name')
        parser.add_argument('--dry-run', action='store_true', help='Show what would be collected without creating')
    
    def handle(self, *args, **options):
        date = options.get('date')
        metric_type = options['type']
        tenant_id = options.get('tenant')
        dry_run = options['dry_run']
        
        if date:
            try:
                target_date = timezone.datetime.strptime(date, '%Y-%m-%d').date()
            except ValueError:
                raise CommandError("Invalid date format. Use YYYY-MM-DD")
        else:
            target_date = timezone.now().date()
        
        self.stdout.write(f"Collecting {metric_type} metrics for {target_date}")
        
        # Get tenants to process
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
        
        collected_count = 0
        failed_count = 0
        
        for tenant in tenants:
            try:
                if dry_run:
                    self.stdout.write(f"Would collect {metric_type} metrics for: {tenant.name}")
                    collected_count += 1
                else:
                    if metric_type == 'daily':
                        result = TenantMetricService.collect_daily_metrics(target_date)
                    elif metric_type == 'weekly':
                        result = TenantMetricService.collect_weekly_metrics()
                    elif metric_type == 'monthly':
                        result = TenantMetricService.collect_monthly_metrics()
                    
                    collected_count += 1
                    self.stdout.write(f"Collected {metric_type} metrics for: {tenant.name}")
            
            except Exception as e:
                failed_count += 1
                self.stdout.write(
                    self.style.ERROR(f"Failed to collect metrics for {tenant.name}: {str(e)}")
                )
        
        action = "Would collect" if dry_run else "Collected"
        self.stdout.write(
            self.style.SUCCESS(f"{action} {metric_type} metrics for {collected_count} tenants, {failed_count} failed")
        )


class CalculateHealthScoresCommand(BaseCommand):
    """
    Calculate health scores for all tenants.
    
    Usage:
        python manage.py calculate_health_scores [--tenant=<tenant_id>] [--dry-run]
    """
    
    help = "Calculate health scores for all tenants"
    
    def add_arguments(self, parser):
        parser.add_argument('--tenant', type=str, help='Calculate for specific tenant ID or name')
        parser.add_argument('--dry-run', action='store_true', help='Show what would be calculated without creating')
    
    def handle(self, *args, **options):
        tenant_id = options.get('tenant')
        dry_run = options['dry_run']
        
        self.stdout.write("Calculating health scores")
        
        # Get tenants to process
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
        
        calculated_count = 0
        failed_count = 0
        
        for tenant in tenants:
            try:
                if dry_run:
                    self.stdout.write(f"Would calculate health score for: {tenant.name}")
                    calculated_count += 1
                else:
                    # Get or create health score
                    health_score, created = TenantHealthScore.objects.get_or_create(
                        tenant=tenant,
                        defaults={
                            'last_activity_at': tenant.last_activity_at or timezone.now(),
                        }
                    )
                    
                    # Calculate scores
                    engagement_score = 0
                    if tenant.last_activity_at:
                        days_inactive = (timezone.now() - tenant.last_activity_at).days
                        if days_inactive == 0:
                            engagement_score = 100
                        elif days_inactive <= 7:
                            engagement_score = 80
                        elif days_inactive <= 30:
                            engagement_score = 60
                        elif days_inactive <= 90:
                            engagement_score = 40
                        else:
                            engagement_score = 20
                    
                    # Calculate usage score
                    usage_score = 50  # Base score
                    try:
                        from ...models.plan import PlanUsage
                        usage = PlanUsage.objects.filter(
                            tenant=tenant,
                            period='monthly'
                        ).first()
                        
                        if usage and hasattr(usage, 'api_calls_percentage'):
                            usage_score = min(100, usage.api_calls_percentage * 2)
                    except:
                        pass
                    
                    # Calculate payment score
                    payment_score = 100  # Default to good
                    try:
                        from ...models import TenantInvoice
                        overdue_invoices = TenantInvoice.objects.filter(
                            tenant=tenant,
                            status='overdue'
                        ).count()
                        
                        if overdue_invoices > 0:
                            payment_score = max(0, 100 - (overdue_invoices * 20))
                    except:
                        pass
                    
                    # Calculate support score
                    support_score = 80  # Default to good
                    
                    # Calculate overall score
                    overall_score = (engagement_score + usage_score + payment_score + support_score) / 4
                    
                    # Determine health grade
                    if overall_score >= 90:
                        health_grade = 'A'
                        risk_level = 'low'
                    elif overall_score >= 80:
                        health_grade = 'B'
                        risk_level = 'low'
                    elif overall_score >= 70:
                        health_grade = 'C'
                        risk_level = 'medium'
                    elif overall_score >= 60:
                        health_grade = 'D'
                        risk_level = 'high'
                    else:
                        health_grade = 'F'
                        risk_level = 'critical'
                    
                    # Update health score
                    health_score.engagement_score = engagement_score
                    health_score.usage_score = usage_score
                    health_score.payment_score = payment_score
                    health_score.support_score = support_score
                    health_score.overall_score = overall_score
                    health_score.health_grade = health_grade
                    health_score.risk_level = risk_level
                    health_score.churn_probability = max(0, 100 - overall_score)
                    health_score.last_activity_at = tenant.last_activity_at or timezone.now()
                    health_score.days_inactive = (timezone.now() - (tenant.last_activity_at or timezone.now())).days
                    health_score.save()
                    
                    calculated_count += 1
                    self.stdout.write(f"Calculated health score for: {tenant.name} ({health_grade})")
            
            except Exception as e:
                failed_count += 1
                self.stdout.write(
                    self.style.ERROR(f"Failed to calculate health score for {tenant.name}: {str(e)}")
                )
        
        action = "Would calculate" if dry_run else "Calculated"
        self.stdout.write(
            self.style.SUCCESS(f"{action} health scores for {calculated_count} tenants, {failed_count} failed")
        )


class CleanupOldMetricsCommand(BaseCommand):
    """
    Clean up old metrics data.
    
    Usage:
        python manage.py cleanup_old_metrics [--days=<days>] [--dry-run]
    """
    
    help = "Clean up old metrics data"
    
    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=365, help='Number of days to keep metrics')
        parser.add_argument('--dry-run', action='store_true', help='Show what would be deleted without deleting')
    
    def handle(self, *args, **options):
        days_to_keep = options['days']
        dry_run = options['dry-run']
        
        self.stdout.write(f"Cleaning up metrics older than {days_to_keep} days")
        
        cutoff_date = timezone.now() - timedelta(days=days_to_keep)
        
        # Get old metrics
        old_metrics = TenantMetric.objects.filter(
            created_at__lt=cutoff_date
        )
        
        count = old_metrics.count()
        
        if dry_run:
            self.stdout.write(f"Would delete {count} old metrics")
        else:
            old_metrics.delete()
            self.stdout.write(f"Deleted {count} old metrics")
        
        self.stdout.write(
            self.style.SUCCESS(f"Cleanup completed (cutoff date: {cutoff_date.date()})")
        )


class GenerateUsageReportCommand(BaseCommand):
    """
    Generate comprehensive usage report.
    
    Usage:
        python manage.py generate_usage_report [--period=<period>] [--format=<format>]
    """
    
    help = "Generate comprehensive usage report"
    
    def add_arguments(self, parser):
        parser.add_argument('--period', type=str, choices=['daily', 'weekly', 'monthly'], default='monthly', help='Report period')
        parser.add_argument('--format', type=str, choices=['table', 'json'], default='table', help='Output format')
        parser.add_argument('--days', type=int, default=30, help='Number of days for report')
    
    def handle(self, *args, **options):
        period = options['period']
        output_format = options['format']
        days = options['days']
        
        self.stdout.write(f"Generating {period} usage report for last {days} days")
        
        # Calculate date range
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        # Collect data
        summary = TenantMetricService.get_tenant_metrics_summary()
        
        # Get recent metrics
        recent_metrics = TenantMetric.objects.filter(
            date__range=[start_date, end_date]
        )
        
        # Additional analytics
        from ...models import Tenant
        from ...models.plan import PlanUsage
        
        report_data = {
            'period': period,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'days': days,
            'summary': summary,
            'top_performers': [],
            'most_active': [],
            'usage_stats': {},
            'metric_trends': {},
        }
        
        # Top performers by revenue
        top_revenue = Tenant.objects.filter(
            is_deleted=False,
            created_at__date__gte=start_date
        ).order_by('-billing__final_price')[:10]
        
        for tenant in top_revenue:
            report_data['top_performers'].append({
                'name': tenant.name,
                'revenue': float(tenant.billing.final_price),
                'plan': tenant.plan.name,
            })
        
        # Most active users
        most_active = Tenant.objects.filter(
            is_deleted=False,
            last_activity_at__date__gte=start_date
        ).order_by('-last_activity_at')[:10]
        
        for tenant in most_active:
            report_data['most_active'].append({
                'name': tenant.name,
                'last_activity': tenant.last_activity_at,
                'days_inactive': (timezone.now() - tenant.last_activity_at).days if tenant.last_activity_at else None,
            })
        
        # Usage statistics
        usage_stats = {
            'total_tenants': Tenant.objects.filter(is_deleted=False).count(),
            'active_tenants': Tenant.objects.filter(is_deleted=False, status='active').count(),
            'total_api_calls': 0,
            'total_storage': 0,
            'total_users': 0,
        }
        
        for usage in PlanUsage.objects.filter(period='monthly'):
            usage_stats['total_api_calls'] += usage.api_calls_used
            usage_stats['total_storage'] += usage.storage_used_gb
            usage_stats['total_users'] += usage.users_used
        
        report_data['usage_stats'] = usage_stats
        
        # Metric trends
        metric_types = recent_metrics.values_list('metric_type', flat=True).distinct()
        
        for metric_type in metric_types:
            type_metrics = recent_metrics.filter(metric_type=metric_type)
            values = [float(m.value) for m in type_metrics.order_by('date')]
            
            if len(values) >= 2:
                first_value = values[0]
                last_value = values[-1]
                change_pct = ((last_value - first_value) / first_value) * 100 if first_value != 0 else 0
                
                report_data['metric_trends'][metric_type] = {
                    'trend': 'up' if change_pct > 5 else 'down' if change_pct < -5 else 'stable',
                    'change_percentage': round(change_pct, 2),
                    'data_points': len(values),
                    'first_value': first_value,
                    'last_value': last_value,
                }
        
        if output_format == 'json':
            self.stdout.write(json.dumps(report_data, indent=2))
        else:
            self._output_table(report_data, start_date, end_date)
    
    def _output_table(self, data, start_date, end_date):
        """Output in table format."""
        self.stdout.write(self.style.SUCCESS(f"Usage Report: {start_date} to {end_date}"))
        self.stdout.write("=" * 60)
        
        # Summary
        self.stdout.write(f"Period: {data['period']} ({data['days']} days)")
        self.stdout.write(f"Total Tenants: {data['summary']['total_tenants']}")
        self.stdout.write(f"Active Tenants: {data['summary']['active_tenants']}")
        
        # Usage stats
        stats = data['usage_stats']
        self.stdout.write(f"\nUsage Statistics:")
        self.stdout.write(f"  Total API Calls: {stats['total_api_calls']:,}")
        self.stdout.write(f"  Total Storage: {stats['total_storage']:.1f} GB")
        self.stdout.write(f"  Total Users: {stats['total_users']:,}")
        
        # Top performers
        self.stdout.write(f"\nTop Performers:")
        for i, performer in enumerate(data['top_performers'], 1):
            self.stdout.write(f"  {i}. {performer['name']} - ${performer['revenue']:.2f} ({performer['plan']})")
        
        # Most active
        self.stdout.write(f"\nMost Active:")
        for i, active in enumerate(data['most_active'], 1):
            days_inactive = active['days_inactive']
            self.stdout.write(f"  {i}. {active['name']} - {days_inactive} days inactive")
        
        # Metric trends
        self.stdout.write(f"\nMetric Trends:")
        for metric_type, trend_data in data['metric_trends'].items():
            self.stdout.write(f"  {metric_type}: {trend_data['trend']} ({trend_data['change_percentage']:+.1f}%)")


class MetricSummaryCommand(BaseCommand):
    """
    Show summary of all metrics.
    
    Usage:
        python manage.py metric_summary [--type=<type>] [--format=<format>]
    """
    
    help = "Show summary of all metrics"
    
    def add_arguments(self, parser):
        parser.add_argument('--type', type=str, help='Filter by metric type')
        parser.add_argument('--format', type=str, choices=['table', 'json'], default='table', help='Output format')
    
    def handle(self, *args, **options):
        metric_type = options.get('type')
        output_format = options['format']
        
        self.stdout.write("Generating metrics summary")
        
        # Get metrics
        queryset = TenantMetric.objects.all()
        
        if metric_type:
            queryset = queryset.filter(metric_type=metric_type)
        
        # Aggregate data
        metrics_by_type = {}
        
        for metric in queryset:
            if metric.metric_type not in metrics_by_type:
                metrics_by_type[metric.metric_type] = {
                    'count': 0,
                    'total_value': 0,
                    'avg_value': 0,
                    'min_value': float('inf'),
                    'max_value': 0,
                    'unit': metric.unit,
                }
            
            data = metrics_by_type[metric.metric_type]
            data['count'] += 1
            data['total_value'] += float(metric.value)
            data['min_value'] = min(data['min_value'], float(metric.value))
            data['max_value'] = max(data['max_value'], float(metric.value))
        
        # Calculate averages
        for metric_type, data in metrics_by_type.items():
            data['avg_value'] = data['total_value'] / data['count']
        
        if output_format == 'json':
            self.stdout.write(json.dumps(metrics_by_type, indent=2))
        else:
            self._output_table(metrics_by_type)
    
    def _output_table(self, metrics_by_type):
        """Output in table format."""
        self.stdout.write(self.style.SUCCESS("Metrics Summary"))
        self.stdout.write("=" * 80)
        self.stdout.write(f"{'Type':<20} {'Count':<8} {'Avg':<12} {'Min':<12} {'Max':<12} {'Unit':<8}")
        self.stdout.write("=" * 80)
        
        for metric_type, data in sorted(metrics_by_type.items()):
            self.stdout.write(
                f"{metric_type:<20} "
                f"{data['count']:<8} "
                f"{data['avg_value']:<12.2f} "
                f"{data['min_value']:<12.2f} "
                f"{data['max_value']:<12.2f} "
                f"{data['unit']:<8}"
            )
