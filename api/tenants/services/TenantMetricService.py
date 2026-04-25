"""
Tenant Metric Service

This service handles tenant metrics collection, analysis,
and reporting for business intelligence.
"""

from datetime import timedelta, date
from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.db.models import Sum, Avg, Count

from ..models import Tenant
from ..models.analytics import TenantMetric, TenantHealthScore
from ..models.plan import PlanUsage

User = get_user_model()


class TenantMetricService:
    """
    Service class for tenant metrics operations.
    
    This service handles metrics collection, analysis,
    and reporting for business intelligence.
    """
    
    METRIC_DEFINITIONS = {
        'mau': {
            'name': 'Monthly Active Users',
            'unit': 'users',
            'aggregation': 'sum',
            'calculation': 'count_unique_users',
        },
        'dau': {
            'name': 'Daily Active Users',
            'unit': 'users',
            'aggregation': 'sum',
            'calculation': 'count_unique_users',
        },
        'revenue': {
            'name': 'Revenue',
            'unit': 'USD',
            'aggregation': 'sum',
            'calculation': 'sum_invoice_amounts',
        },
        'api_calls': {
            'name': 'API Calls',
            'unit': 'calls',
            'aggregation': 'sum',
            'calculation': 'count_api_requests',
        },
        'storage_used': {
            'name': 'Storage Used',
            'unit': 'GB',
            'aggregation': 'sum',
            'calculation': 'sum_storage_usage',
        },
        'bandwidth_used': {
            'name': 'Bandwidth Used',
            'unit': 'GB',
            'aggregation': 'sum',
            'calculation': 'sum_bandwidth_usage',
        },
        'tickets_open': {
            'name': 'Tickets Open',
            'unit': 'tickets',
            'aggregation': 'sum',
            'calculation': 'count_support_tickets',
        },
        'campaigns_active': {
            'name': 'Active Campaigns',
            'unit': 'campaigns',
            'aggregation': 'sum',
            'calculation': 'count_active_campaigns',
        },
        'publishers_active': {
            'name': 'Active Publishers',
            'unit': 'publishers',
            'aggregation': 'sum',
            'calculation': 'count_active_publishers',
        },
        'conversion_rate': {
            'name': 'Conversion Rate',
            'unit': '%',
            'aggregation': 'avg',
            'calculation': 'calculate_conversion_rate',
        },
    }
    
    @staticmethod
    def record_metric(tenant, metric_type, value, date=None, metadata=None):
        """
        Record a metric for tenant.
        
        Args:
            tenant (Tenant): Tenant to record metric for
            metric_type (str): Type of metric
            value (float): Metric value
            date (date): Date for the metric
            metadata (dict): Additional metadata
            
        Returns:
            TenantMetric: Created metric record
        """
        if date is None:
            date = timezone.now().date()
        
        # Validate metric type
        if metric_type not in TenantMetricService.METRIC_DEFINITIONS:
            raise ValidationError(f'Invalid metric type: {metric_type}')
        
        # Get previous value for comparison
        try:
            previous_metric = TenantMetric.objects.get(
                tenant=tenant,
                metric_type=metric_type,
                date=date - timedelta(days=1)
            )
            previous_value = previous_metric.value
        except TenantMetric.DoesNotExist:
            previous_value = None
        
        # Create metric record
        metric = TenantMetric.objects.create(
            tenant=tenant,
            date=date,
            metric_type=metric_type,
            value=value,
            unit=TenantMetricService.METRIC_DEFINITIONS[metric_type]['unit'],
            metadata=metadata or {},
            previous_value=previous_value,
        )
        
        # Calculate change percentage
        metric.calculate_change_percentage()
        metric.save()
        
        return metric
    
    @staticmethod
    def calculate_mau(tenant, date=None):
        """
        Calculate Monthly Active Users for tenant.
        
        Args:
            tenant (Tenant): Tenant to calculate MAU for
            date (date): Date to calculate for
            
        Returns:
            int: MAU count
        """
        if date is None:
            date = timezone.now().date()
        
        # Get start and end of month
        month_start = date.replace(day=1)
        if date.month == 12:
            month_end = date.replace(year=date.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            month_end = date.replace(month=date.month + 1, day=1) - timedelta(days=1)
        
        # Count unique users who were active in the month
        # This would query your user activity logs
        # For now, return a placeholder
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # Count users who logged in during the month
        # This is a simplified calculation
        active_users = User.objects.filter(
            last_login__date__range=[month_start, month_end],
            # Add tenant filtering based on your user-tenant relationship
        ).count()
        
        return active_users
    
    @staticmethod
    def calculate_dau(tenant, date=None):
        """
        Calculate Daily Active Users for tenant.
        
        Args:
            tenant (Tenant): Tenant to calculate DAU for
            date (date): Date to calculate for
            
        Returns:
            int: DAU count
        """
        if date is None:
            date = timezone.now().date()
        
        # Count unique users who were active on the specific date
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # Count users who logged in on the specific date
        # This is a simplified calculation
        active_users = User.objects.filter(
            last_login__date=date,
            # Add tenant filtering based on your user-tenant relationship
        ).count()
        
        return active_users
    
    @staticmethod
    def calculate_revenue(tenant, date=None):
        """
        Calculate revenue for tenant.
        
        Args:
            tenant (Tenant): Tenant to calculate revenue for
            date (date): Date to calculate for
            
        Returns:
            float: Revenue amount
        """
        if date is None:
            date = timezone.now().date()
        
        # Sum paid invoices for the date
        from ..models import TenantInvoice
        
        revenue = TenantInvoice.objects.filter(
            tenant=tenant,
            status='paid',
            paid_date=date
        ).aggregate(total=Sum('total_amount'))['total'] or 0
        
        return float(revenue)
    
    @staticmethod
    def collect_daily_metrics(date=None):
        """
        Collect daily metrics for all tenants.
        
        Args:
            date (date): Date to collect metrics for
            
        Returns:
            dict: Collection results
        """
        if date is None:
            date = timezone.now().date()
        
        results = {
            'date': date,
            'tenants_processed': 0,
            'metrics_collected': 0,
            'errors': [],
        }
        
        # Process all active tenants
        for tenant in Tenant.objects.filter(is_deleted=False, status='active'):
            try:
                # Collect each metric type
                for metric_type in TenantMetricService.METRIC_DEFINITIONS:
                    value = TenantMetricService._calculate_metric_value(tenant, metric_type, date)
                    if value is not None:
                        TenantMetricService.record_metric(tenant, metric_type, value, date)
                        results['metrics_collected'] += 1
                
                results['tenants_processed'] += 1
                
            except Exception as e:
                results['errors'].append({
                    'tenant': tenant.name,
                    'error': str(e),
                })
        
        return results
    
    @staticmethod
    def _calculate_metric_value(tenant, metric_type, date):
        """Calculate metric value using appropriate method."""
        calculation_method = TenantMetricService.METRIC_DEFINITIONS[metric_type]['calculation']
        
        if calculation_method == 'count_unique_users':
            if metric_type == 'mau':
                return TenantMetricService.calculate_mau(tenant, date)
            else:
                return TenantMetricService.calculate_dau(tenant, date)
        
        elif calculation_method == 'sum_invoice_amounts':
            return TenantMetricService.calculate_revenue(tenant, date)
        
        elif calculation_method == 'count_api_requests':
            # This would query your API access logs
            return 0  # Placeholder
        
        elif calculation_method == 'sum_storage_usage':
            # Get storage usage from plan usage
            try:
                usage = PlanUsage.objects.get(
                    tenant=tenant,
                    period='daily',
                    period_start=date
                )
                return float(usage.storage_used_gb)
            except PlanUsage.DoesNotExist:
                return 0
        
        elif calculation_method == 'sum_bandwidth_usage':
            # This would query your bandwidth usage logs
            return 0  # Placeholder
        
        elif calculation_method == 'count_support_tickets':
            # This would query your support ticket system
            return 0  # Placeholder
        
        elif calculation_method == 'count_active_campaigns':
            # This would query your campaign system
            return 0  # Placeholder
        
        elif calculation_method == 'count_active_publishers':
            # This would query your publisher system
            return 0  # Placeholder
        
        elif calculation_method == 'calculate_conversion_rate':
            # This would calculate conversion rate
            return 0  # Placeholder
        
        return None
    
    @staticmethod
    def get_metrics(tenant, metric_types=None, days=30):
        """
        Get metrics for tenant.
        
        Args:
            tenant (Tenant): Tenant to get metrics for
            metric_types (list): List of metric types to get
            days (int): Number of days to retrieve
            
        Returns:
            dict: Metrics data
        """
        if metric_types is None:
            metric_types = list(TenantMetricService.METRIC_DEFINITIONS.keys())
        
        from django.utils import timezone
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        metrics_data = {
            'tenant_id': str(tenant.id),
            'tenant_name': tenant.name,
            'period': {
                'start_date': start_date,
                'end_date': end_date,
                'days': days,
            },
            'metrics': {},
        }
        
        for metric_type in metric_types:
            if metric_type not in TenantMetricService.METRIC_DEFINITIONS:
                continue
            
            metrics = TenantMetric.objects.filter(
                tenant=tenant,
                metric_type=metric_type,
                date__range=[start_date, end_date]
            ).order_by('date')
            
            metric_def = TenantMetricService.METRIC_DEFINITIONS[metric_type]
            
            metrics_data['metrics'][metric_type] = {
                'name': metric_def['name'],
                'unit': metric_def['unit'],
                'data': [
                    {
                        'date': metric.date,
                        'value': float(metric.value),
                        'change_percentage': metric.change_percentage,
                        'change_display': metric.change_display,
                    }
                    for metric in metrics
                ],
                'summary': TenantMetricService._calculate_metric_summary(metrics),
            }
        
        return metrics_data
    
    @staticmethod
    def _calculate_metric_summary(metrics):
        """Calculate summary statistics for metrics."""
        if not metrics.exists():
            return {
                'total': 0,
                'average': 0,
                'min': 0,
                'max': 0,
                'latest': 0,
                'trend': 'stable',
            }
        
        values = [float(m.value) for m in metrics]
        
        # Calculate trend (simple comparison of first and last values)
        if len(values) >= 2:
            first_value = values[0]
            last_value = values[-1]
            if last_value > first_value:
                trend = 'up'
            elif last_value < first_value:
                trend = 'down'
            else:
                trend = 'stable'
        else:
            trend = 'stable'
        
        return {
            'total': sum(values),
            'average': sum(values) / len(values),
            'min': min(values),
            'max': max(values),
            'latest': values[-1],
            'trend': trend,
        }
    
    @staticmethod
    def get_dashboard_metrics(tenant):
        """
        Get dashboard metrics for tenant.
        
        Args:
            tenant (Tenant): Tenant to get metrics for
            
        Returns:
            dict: Dashboard metrics data
        """
        # Get recent metrics for key dashboard indicators
        key_metrics = ['mau', 'dau', 'revenue', 'api_calls']
        metrics_data = TenantMetricService.get_metrics(tenant, key_metrics, days=30)
        
        dashboard_data = {
            'tenant': {
                'id': str(tenant.id),
                'name': tenant.name,
                'plan': tenant.plan.name,
                'status': tenant.status,
            },
            'metrics': {},
            'health_score': None,
        }
        
        # Add metrics with latest values
        for metric_type, data in metrics_data['metrics'].items():
            if data['data']:
                latest = data['data'][-1]
                dashboard_data['metrics'][metric_type] = {
                    'name': data['name'],
                    'unit': data['unit'],
                    'current': latest['value'],
                    'change': latest['change_percentage'],
                    'trend': data['summary']['trend'],
                }
        
        # Get health score
        try:
            health_score = tenant.health_score
            dashboard_data['health_score'] = {
                'overall_score': float(health_score.overall_score),
                'health_grade': health_score.health_grade,
                'risk_level': health_score.risk_level,
                'churn_probability': float(health_score.churn_probability),
                'last_activity': health_score.last_activity_at,
            }
        except:
            pass
        
        return dashboard_data
    
    @staticmethod
    def get_analytics_report(tenant, period='monthly', periods=12):
        """
        Generate analytics report for tenant.
        
        Args:
            tenant (Tenant): Tenant to generate report for
            period (str): Report period (daily, weekly, monthly, yearly)
            periods (int): Number of periods to include
            
        Returns:
            dict: Analytics report
        """
        # Map period to days
        period_days = {
            'daily': 1,
            'weekly': 7,
            'monthly': 30,
            'yearly': 365,
        }
        
        days = period_days.get(period, 30) * periods
        
        # Get metrics data
        metrics_data = TenantMetricService.get_metrics(
            tenant, 
            days=days
        )
        
        report = {
            'tenant': {
                'id': str(tenant.id),
                'name': tenant.name,
                'plan': tenant.plan.name,
            },
            'period': {
                'type': period,
                'periods': periods,
                'days': days,
            },
            'metrics': metrics_data['metrics'],
            'insights': TenantMetricService._generate_insights(metrics_data),
        }
        
        return report
    
    @staticmethod
    def _generate_insights(metrics_data):
        """Generate insights from metrics data."""
        insights = []
        
        # Analyze revenue trends
        if 'revenue' in metrics_data['metrics']:
            revenue_data = metrics_data['metrics']['revenue']
            if revenue_data['summary']['trend'] == 'up':
                insights.append({
                    'type': 'positive',
                    'title': 'Revenue Growing',
                    'description': f"Revenue is trending up by {revenue_data['summary']['latest']:.2f} {revenue_data['unit']}",
                    'metric': 'revenue',
                })
            elif revenue_data['summary']['trend'] == 'down':
                insights.append({
                    'type': 'negative',
                    'title': 'Revenue Declining',
                    'description': f"Revenue is trending down to {revenue_data['summary']['latest']:.2f} {revenue_data['unit']}",
                    'metric': 'revenue',
                })
        
        # Analyze user engagement
        if 'mau' in metrics_data['metrics'] and 'dau' in metrics_data['metrics']:
            mau_data = metrics_data['metrics']['mau']
            dau_data = metrics_data['metrics']['dau']
            
            if mau_data['data'] and dau_data['data']:
                latest_mau = mau_data['data'][-1]['value']
                latest_dau = dau_data['data'][-1]['value']
                
                if latest_mau > 0:
                    engagement_rate = (latest_dau / latest_mau) * 100
                    
                    if engagement_rate > 20:
                        insights.append({
                            'type': 'positive',
                            'title': 'High User Engagement',
                            'description': f"DAU/MAU ratio is {engagement_rate:.1f}%",
                            'metric': 'engagement',
                        })
                    elif engagement_rate < 5:
                        insights.append({
                            'type': 'negative',
                            'title': 'Low User Engagement',
                            'description': f"DAU/MAU ratio is only {engagement_rate:.1f}%",
                            'metric': 'engagement',
                        })
        
        return insights
    
    @staticmethod
    def export_metrics(tenant, format='csv', days=30):
        """
        Export metrics data for tenant.
        
        Args:
            tenant (Tenant): Tenant to export metrics for
            format (str): Export format (csv, json, xlsx)
            days (int): Number of days to export
            
        Returns:
            str/bytes: Exported data
        """
        metrics_data = TenantMetricService.get_metrics(tenant, days=days)
        
        if format == 'json':
            import json
            return json.dumps(metrics_data, indent=2, default=str)
        
        elif format == 'csv':
            import csv
            import io
            
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write header
            writer.writerow([
                'Date', 'Metric Type', 'Metric Name', 'Value', 'Unit', 
                'Previous Value', 'Change Percentage'
            ])
            
            # Write data
            for metric_type, data in metrics_data['metrics'].items():
                for metric_point in data['data']:
                    writer.writerow([
                        metric_point['date'],
                        metric_type,
                        data['name'],
                        metric_point['value'],
                        data['unit'],
                        metrics_data['metrics'][metric_type]['data'][0]['value'] if data['data'] else 0,
                        metric_point['change_percentage'],
                    ])
            
            return output.getvalue()
        
        elif format == 'xlsx':
            # This would require a library like openpyxl
            # For now, return CSV as fallback
            return TenantMetricService.export_metrics(tenant, 'csv', days)
        
        else:
            raise ValidationError(f'Unsupported export format: {format}')
    
    @staticmethod
    def get_tenant_metrics_summary():
        """
        Get metrics summary for all tenants.
        
        Returns:
            dict: Summary statistics
        """
        from django.utils import timezone
        from django.db.models import Sum, Avg, Count
        
        # Get metrics for the last 30 days
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=30)
        
        summary = {
            'period': {
                'start_date': start_date,
                'end_date': end_date,
                'days': 30,
            },
            'total_tenants': Tenant.objects.filter(is_deleted=False).count(),
            'active_tenants': Tenant.objects.filter(is_deleted=False, status='active').count(),
            'metrics': {},
        }
        
        # Calculate summary for each metric type
        for metric_type, definition in TenantMetricService.METRIC_DEFINITIONS.items():
            metrics = TenantMetric.objects.filter(
                date__range=[start_date, end_date],
                metric_type=metric_type
            )
            
            if metrics.exists():
                values = [float(m.value) for m in metrics]
                summary['metrics'][metric_type] = {
                    'name': definition['name'],
                    'unit': definition['unit'],
                    'total': sum(values),
                    'average': sum(values) / len(values),
                    'min': min(values),
                    'max': max(values),
                    'tenants_with_data': metrics.values('tenant').distinct().count(),
                }
        
        return summary
