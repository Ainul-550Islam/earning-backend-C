"""
Metrics Tasks

This module contains Celery tasks for metrics collection and analysis including
daily/weekly/monthly metrics collection, health score calculations, and data cleanup.
"""

from celery import shared_task
from django.utils import timezone
from django.db import transaction
from datetime import timedelta
import logging

from ..services import TenantMetricService
from ..models import Tenant, TenantMetric, TenantHealthScore

logger = logging.getLogger(__name__)


@shared_task(name='tenants.metrics.collect_daily_metrics')
def collect_daily_metrics(date=None):
    """
    Collect daily metrics for all active tenants.
    
    Args:
        date (datetime.date): Date to collect metrics for (default: today)
    """
    logger.info("Starting daily metrics collection")
    
    if date is None:
        date = timezone.now().date()
    
    results = TenantMetricService.collect_daily_metrics(date)
    
    logger.info(f"Daily metrics collection completed: {results}")
    return results


@shared_task(name='tenants.metrics.collect_weekly_metrics')
def collect_weekly_metrics():
    """
    Collect and aggregate weekly metrics for all tenants.
    
    This task runs weekly to aggregate daily metrics into
    weekly summaries and calculate trends.
    """
    logger.info("Starting weekly metrics collection")
    
    # Get the end of last week
    today = timezone.now().date()
    week_end = today - timedelta(days=today.weekday() + 1)
    week_start = week_end - timedelta(days=6)
    
    collected_count = 0
    failed_count = 0
    errors = []
    
    # Get all active tenants
    tenants = Tenant.objects.filter(is_deleted=False, status='active')
    
    for tenant in tenants:
        try:
            # Aggregate daily metrics for the week
            daily_metrics = TenantMetric.objects.filter(
                tenant=tenant,
                date__range=[week_start, week_end]
            )
            
            # Calculate weekly aggregates for each metric type
            metric_types = set(daily_metrics.values_list('metric_type', flat=True))
            
            for metric_type in metric_types:
                daily_values = daily_metrics.filter(metric_type=metric_type)
                
                if daily_values.exists():
                    # Calculate weekly aggregate
                    values = [float(m.value) for m in daily_values]
                    
                    # Create weekly metric record
                    weekly_metric = TenantMetric.objects.create(
                        tenant=tenant,
                        date=week_end,
                        metric_type=f'weekly_{metric_type}',
                        value=sum(values),  # Sum for weekly totals
                        unit=daily_values.first().unit,
                        metadata={
                            'period': 'weekly',
                            'period_start': week_start.isoformat(),
                            'period_end': week_end.isoformat(),
                            'daily_count': len(values),
                            'average': sum(values) / len(values),
                            'min': min(values),
                            'max': max(values),
                        }
                    )
                    
                    # Calculate change from previous week
                    previous_week_end = week_end - timedelta(days=7)
                    previous_week_metric = TenantMetric.objects.filter(
                        tenant=tenant,
                        metric_type=f'weekly_{metric_type}',
                        date=previous_week_end
                    ).first()
                    
                    if previous_week_metric:
                        weekly_metric.previous_value = previous_week_metric.value
                        weekly_metric.calculate_change_percentage()
                        weekly_metric.save()
            
            collected_count += 1
            logger.info(f"Collected weekly metrics for {tenant.name}")
            
        except Exception as e:
            failed_count += 1
            error_msg = f"Failed to collect weekly metrics for {tenant.name}: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
    
    result = {
        'period_start': week_start,
        'period_end': week_end,
        'collected_count': collected_count,
        'failed_count': failed_count,
        'errors': errors,
        'total_tenants': tenants.count(),
    }
    
    logger.info(f"Weekly metrics collection completed: {result}")
    return result


@shared_task(name='tenants.metrics.collect_monthly_metrics')
def collect_monthly_metrics():
    """
    Collect and aggregate monthly metrics for all tenants.
    
    This task runs monthly to aggregate daily metrics into
    monthly summaries and calculate long-term trends.
    """
    logger.info("Starting monthly metrics collection")
    
    # Get the end of last month
    today = timezone.now().date()
    month_end = today.replace(day=1) - timedelta(days=1)
    month_start = month_end.replace(day=1)
    
    collected_count = 0
    failed_count = 0
    errors = []
    
    # Get all active tenants
    tenants = Tenant.objects.filter(is_deleted=False, status='active')
    
    for tenant in tenants:
        try:
            # Aggregate daily metrics for the month
            daily_metrics = TenantMetric.objects.filter(
                tenant=tenant,
                date__range=[month_start, month_end]
            )
            
            # Calculate monthly aggregates for each metric type
            metric_types = set(daily_metrics.values_list('metric_type', flat=True))
            
            for metric_type in metric_types:
                daily_values = daily_metrics.filter(metric_type=metric_type)
                
                if daily_values.exists():
                    # Calculate monthly aggregate
                    values = [float(m.value) for m in daily_values]
                    
                    # Create monthly metric record
                    monthly_metric = TenantMetric.objects.create(
                        tenant=tenant,
                        date=month_end,
                        metric_type=f'monthly_{metric_type}',
                        value=sum(values),  # Sum for monthly totals
                        unit=daily_values.first().unit,
                        metadata={
                            'period': 'monthly',
                            'period_start': month_start.isoformat(),
                            'period_end': month_end.isoformat(),
                            'daily_count': len(values),
                            'average': sum(values) / len(values),
                            'min': min(values),
                            'max': max(values),
                        }
                    )
                    
                    # Calculate change from previous month
                    previous_month_end = month_end.replace(month=month_end.month-1 if month_end.month > 1 else 12)
                    previous_month_metric = TenantMetric.objects.filter(
                        tenant=tenant,
                        metric_type=f'monthly_{metric_type}',
                        date=previous_month_end
                    ).first()
                    
                    if previous_month_metric:
                        monthly_metric.previous_value = previous_month_metric.value
                        monthly_metric.calculate_change_percentage()
                        monthly_metric.save()
            
            collected_count += 1
            logger.info(f"Collected monthly metrics for {tenant.name}")
            
        except Exception as e:
            failed_count += 1
            error_msg = f"Failed to collect monthly metrics for {tenant.name}: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
    
    result = {
        'period_start': month_start,
        'period_end': month_end,
        'collected_count': collected_count,
        'failed_count': failed_count,
        'errors': errors,
        'total_tenants': tenants.count(),
    }
    
    logger.info(f"Monthly metrics collection completed: {result}")
    return result


@shared_task(name='tenants.metrics.calculate_health_scores')
def calculate_health_scores():
    """
    Calculate health scores for all active tenants.
    
    This task runs weekly to update tenant health scores
    based on recent activity and metrics.
    """
    logger.info("Starting health score calculation")
    
    calculated_count = 0
    failed_count = 0
    errors = []
    
    # Get all active tenants
    tenants = Tenant.objects.filter(is_deleted=False, status='active').select_related('plan')
    
    for tenant in tenants:
        try:
            # Get or create health score
            health_score, created = TenantHealthScore.objects.get_or_create(
                tenant=tenant,
                defaults={
                    'last_activity_at': tenant.last_activity_at or timezone.now(),
                }
            )
            
            # Calculate engagement score
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
                from ..models.plan import PlanUsage
                usage = PlanUsage.objects.filter(
                    tenant=tenant,
                    period='monthly'
                ).first()
                
                if usage:
                    # Calculate usage percentage
                    usage_pct = usage.api_calls_percentage if hasattr(usage, 'api_calls_percentage') else 50
                    usage_score = min(100, usage_pct * 2)  # Scale to 0-100
            except:
                pass
            
            # Calculate payment score
            payment_score = 100  # Default to good
            try:
                from ..models import TenantInvoice
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
            # This would be based on support ticket metrics
            
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
            
            # Calculate churn probability
            churn_probability = max(0, 100 - overall_score)
            
            # Update health score
            health_score.engagement_score = engagement_score
            health_score.usage_score = usage_score
            health_score.payment_score = payment_score
            health_score.support_score = support_score
            health_score.overall_score = overall_score
            health_score.health_grade = health_grade
            health_score.risk_level = risk_level
            health_score.churn_probability = churn_probability
            health_score.last_activity_at = tenant.last_activity_at or timezone.now()
            health_score.days_inactive = (timezone.now() - (tenant.last_activity_at or timezone.now())).days
            
            # Generate recommendations
            recommendations = []
            
            if engagement_score < 50:
                recommendations.append({
                    'type': 'engagement',
                    'message': 'Low user engagement detected. Consider sending re-engagement campaigns.',
                })
            
            if usage_score < 50:
                recommendations.append({
                    'type': 'usage',
                    'message': 'Low usage detected. Consider offering training or support.',
                })
            
            if payment_score < 50:
                recommendations.append({
                    'type': 'payment',
                    'message': 'Payment issues detected. Contact customer for resolution.',
                })
            
            health_score.recommendations = recommendations
            health_score.save()
            
            calculated_count += 1
            logger.info(f"Calculated health score for {tenant.name}: {health_grade}")
            
        except Exception as e:
            failed_count += 1
            error_msg = f"Failed to calculate health score for {tenant.name}: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
    
    result = {
        'calculated_count': calculated_count,
        'failed_count': failed_count,
        'errors': errors,
        'total_tenants': tenants.count(),
    }
    
    logger.info(f"Health score calculation completed: {result}")
    return result


@shared_task(name='tenants.metrics.cleanup_old_metrics')
def cleanup_old_metrics(days_to_keep=365):
    """
    Clean up old metrics data to maintain database performance.
    
    Args:
        days_to_keep (int): Number of days to keep metrics data
    """
    logger.info(f"Starting cleanup of metrics older than {days_to_keep} days")
    
    cutoff_date = timezone.now() - timedelta(days=days_to_keep)
    
    # Archive old metrics
    old_metrics = TenantMetric.objects.filter(
        created_at__lt=cutoff_date
    )
    
    archived_count = old_metrics.count()
    
    # This would archive metrics to cold storage
    # For now, just delete old metrics
    old_metrics.delete()
    
    result = {
        'archived_count': archived_count,
        'cutoff_date': cutoff_date.date(),
    }
    
    logger.info(f"Metrics cleanup completed: {result}")
    return result


@shared_task(name='tenants.metrics.generate_usage_analytics')
def generate_usage_analytics():
    """
    Generate comprehensive usage analytics reports.
    
    This task runs monthly to generate detailed usage analytics
    for business intelligence purposes.
    """
    logger.info("Starting usage analytics generation")
    
    try:
        # Get usage summary for all tenants
        summary = TenantMetricService.get_tenant_metrics_summary()
        
        # Generate additional analytics
        from datetime import timedelta
        last_30_days = timezone.now() - timedelta(days=30)
        
        # Top performers
        top_revenue = Tenant.objects.filter(
            is_deleted=False,
            created_at__gte=last_30_days
        ).order_by('-billing__final_price')[:10]
        
        # Most active users
        most_active = Tenant.objects.filter(
            is_deleted=False,
            last_activity_at__gte=last_30_days
        ).order_by('-last_activity_at')[:10]
        
        analytics = {
            'summary': summary,
            'top_performers': [
                {
                    'name': tenant.name,
                    'revenue': float(tenant.billing.final_price),
                    'plan': tenant.plan.name,
                }
                for tenant in top_revenue
            ],
            'most_active': [
                {
                    'name': tenant.name,
                    'last_activity': tenant.last_activity_at,
                    'days_inactive': (timezone.now() - tenant.last_activity_at).days if tenant.last_activity_at else None,
                }
                for tenant in most_active
            ],
            'generated_at': timezone.now().isoformat(),
        }
        
        logger.info(f"Usage analytics generated: {len(analytics)} sections")
        return analytics
        
    except Exception as e:
        logger.error(f"Failed to generate usage analytics: {str(e)}")
        return {'error': str(e)}


@shared_task(name='tenants.metrics.track_api_usage')
def track_api_usage():
    """
    Track API usage for all tenants from access logs.
    
    This task runs hourly to process API access logs and
    update usage metrics.
    """
    logger.info("Starting API usage tracking")
    
    # This would process API access logs and update metrics
    # For now, just log that the task ran
    result = {
        'processed_logs': 0,
        'updated_metrics': 0,
        'timestamp': timezone.now().isoformat(),
    }
    
    logger.info(f"API usage tracking completed: {result}")
    return result


@shared_task(name='tenants.metrics.calculate_trends')
def calculate_trends():
    """
    Calculate trends and patterns in tenant metrics.
    
    This task runs weekly to identify trends and patterns
    in tenant behavior and system performance.
    """
    logger.info("Starting trend calculation")
    
    try:
        # Get recent metrics data
        from datetime import timedelta
        last_90_days = timezone.now() - timedelta(days=90)
        
        recent_metrics = TenantMetric.objects.filter(
            created_at__gte=last_90_days
        )
        
        # Calculate trends for each metric type
        trends = {}
        metric_types = recent_metrics.values_list('metric_type', flat=True).distinct()
        
        for metric_type in metric_types:
            type_metrics = recent_metrics.filter(metric_type=metric_type)
            
            # Calculate trend
            values = [float(m.value) for m in type_metrics.order_by('created_at')]
            
            if len(values) >= 2:
                # Simple linear trend calculation
                first_value = values[0]
                last_value = values[-1]
                change_pct = ((last_value - first_value) / first_value) * 100 if first_value != 0 else 0
                
                trends[metric_type] = {
                    'trend': 'up' if change_pct > 5 else 'down' if change_pct < -5 else 'stable',
                    'change_percentage': round(change_pct, 2),
                    'data_points': len(values),
                    'first_value': first_value,
                    'last_value': last_value,
                }
        
        logger.info(f"Trend calculation completed: {len(trends)} metrics analyzed")
        return trends
        
    except Exception as e:
        logger.error(f"Failed to calculate trends: {str(e)}")
        return {'error': str(e)}
