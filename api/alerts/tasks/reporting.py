"""
Reporting Tasks
"""
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging

from ..models.reporting import AlertReport, MTTRMetric, MTTDMetric, SLABreach

logger = logging.getLogger(__name__)


@shared_task
def generate_daily_reports():
    """Generate daily alert reports"""
    try:
        from ..serializers.reporting import AlertReportCreateDailySerializer
        
        # Create daily report
        report_data = {
            'title': f'Daily Report - {timezone.now().date()}',
            'report_type': 'daily',
            'start_date': timezone.now().replace(hour=0, minute=0, second=0, microsecond=0),
            'end_date': timezone.now().replace(hour=23, minute=59, second=59, microsecond=999999),
            'included_metrics': ['basic_metrics', 'severity_breakdown', 'rule_performance'],
            'format_type': 'json',
            'auto_distribute': False
        }
        
        report = AlertReport.objects.create(**report_data)
        report.generate_report()
        
        logger.info(f"Generated daily report: {report.id}")
        return report.id
        
    except Exception as e:
        logger.error(f"Error in generate_daily_reports: {e}")
        return None


@shared_task
def generate_weekly_reports():
    """Generate weekly alert reports"""
    try:
        from datetime import date, timedelta
        
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        
        report_data = {
            'title': f'Weekly Report - {week_start} to {week_end}',
            'report_type': 'weekly',
            'start_date': timezone.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=today.weekday()),
            'end_date': timezone.now().replace(hour=23, minute=59, second=59, microsecond=999999) - timedelta(days=(today.weekday() - 6)),
            'included_metrics': ['basic_metrics', 'severity_breakdown', 'rule_performance', 'trend_analysis'],
            'format_type': 'json',
            'auto_distribute': False
        }
        
        report = AlertReport.objects.create(**report_data)
        report.generate_report()
        
        logger.info(f"Generated weekly report: {report.id}")
        return report.id
        
    except Exception as e:
        logger.error(f"Error in generate_weekly_reports: {e}")
        return None


@shared_task
def generate_monthly_reports():
    """Generate monthly alert reports"""
    try:
        from datetime import date, timedelta
        
        today = date.today()
        month_start = today.replace(day=1)
        
        report_data = {
            'title': f'Monthly Report - {month_start.strftime("%B %Y")}',
            'report_type': 'monthly',
            'start_date': timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0),
            'end_date': timezone.now().replace(day=1, hour=23, minute=59, second=59, microsecond=999999) + timedelta(days=32),
            'included_metrics': ['basic_metrics', 'severity_breakdown', 'rule_performance', 'mttr_analysis'],
            'format_type': 'json',
            'auto_distribute': False
        }
        
        report = AlertReport.objects.create(**report_data)
        report.generate_report()
        
        logger.info(f"Generated monthly report: {report.id}")
        return report.id
        
    except Exception as e:
        logger.error(f"Error in generate_monthly_reports: {e}")
        return None


@shared_task
def generate_sla_reports():
    """Generate SLA compliance reports"""
    try:
        days = 30
        
        report_data = {
            'title': f'SLA Report - Last {days} Days',
            'report_type': 'sla',
            'start_date': timezone.now() - timedelta(days=days),
            'end_date': timezone.now(),
            'included_metrics': ['sla_metrics', 'resolution_times', 'compliance_rates'],
            'format_type': 'json',
            'auto_distribute': False
        }
        
        report = AlertReport.objects.create(**report_data)
        report.generate_report()
        
        logger.info(f"Generated SLA report: {report.id}")
        return report.id
        
    except Exception as e:
        logger.error(f"Error in generate_sla_reports: {e}")
        return None


@shared_task
def calculate_mttr_metrics():
    """Calculate MTTR metrics for all configured metrics"""
    try:
        metrics = MTTRMetric.objects.all()
        
        calculated_count = 0
        for metric in metrics:
            metric.calculate_mttr()
            calculated_count += 1
        
        logger.info(f"Calculated MTTR for {calculated_count} metrics")
        return calculated_count
        
    except Exception as e:
        logger.error(f"Error in calculate_mttr_metrics: {e}")
        return 0


@shared_task
def calculate_mttd_metrics():
    """Calculate MTTD metrics for all configured metrics"""
    try:
        metrics = MTTDMetric.objects.all()
        
        calculated_count = 0
        for metric in metrics:
            metric.calculate_mttd()
            calculated_count += 1
        
        logger.info(f"Calculated MTTD for {calculated_count} metrics")
        return calculated_count
        
    except Exception as e:
        logger.error(f"Error in calculate_mttd_metrics: {e}")
        return 0


@shared_task
def check_sla_breaches():
    """Check for new SLA breaches"""
    try:
        from ..models.core import AlertLog
        
        # Get recently resolved alerts
        recent_resolved = AlertLog.objects.filter(
            is_resolved=True,
            resolved_at__gte=timezone.now() - timedelta(hours=1)
        ).select_related('rule')
        
        breach_count = 0
        for alert in recent_resolved:
            # Check if resolution time exceeds SLA
            if alert.resolved_at and alert.triggered_at:
                resolution_time = (alert.resolved_at - alert.triggered_at).total_seconds() / 60
                
                # Default SLA of 60 minutes for critical alerts, 120 for others
                sla_threshold = 60 if alert.rule.severity == 'critical' else 120
                
                if resolution_time > sla_threshold:
                    # Create SLA breach record
                    breach = SLABreach.objects.create(
                        name=f"SLA Breach - {alert.rule.name}",
                        sla_type='resolution_time',
                        severity=alert.rule.severity,
                        alert_log=alert,
                        threshold_minutes=sla_threshold,
                        breach_time=alert.resolved_at,
                        breach_duration_minutes=resolution_time - sla_threshold,
                        breach_percentage=(resolution_time / sla_threshold - 1) * 100
                    )
                    breach_count += 1
        
        logger.info(f"Detected {breach_count} new SLA breaches")
        return breach_count
        
    except Exception as e:
        logger.error(f"Error in check_sla_breaches: {e}")
        return 0


@shared_task
def generate_performance_reports():
    """Generate performance analysis reports"""
    try:
        days = 7
        
        report_data = {
            'title': f'Performance Report - Last {days} Days',
            'report_type': 'performance',
            'start_date': timezone.now() - timedelta(days=days),
            'end_date': timezone.now(),
            'included_metrics': ['performance_metrics', 'mttr_analysis', 'response_times'],
            'format_type': 'json',
            'auto_distribute': False
        }
        
        report = AlertReport.objects.create(**report_data)
        report.generate_report()
        
        logger.info(f"Generated performance report: {report.id}")
        return report.id
        
    except Exception as e:
        logger.error(f"Error in generate_performance_reports: {e}")
        return None


@shared_task
def generate_trend_analysis_reports():
    """Generate trend analysis reports"""
    try:
        days = 30
        
        report_data = {
            'title': f'Trend Analysis Report - Last {days} Days',
            'report_type': 'trend',
            'start_date': timezone.now() - timedelta(days=days),
            'end_date': timezone.now(),
            'included_metrics': ['trend_analysis', 'pattern_detection', 'forecasting'],
            'format_type': 'json',
            'auto_distribute': False
        }
        
        report = AlertReport.objects.create(**report_data)
        report.generate_report()
        
        logger.info(f"Generated trend analysis report: {report.id}")
        return report.id
        
    except Exception as e:
        logger.error(f"Error in generate_trend_analysis_reports: {e}")
        return None


@shared_task
def distribute_reports():
    """Distribute generated reports to recipients"""
    try:
        # Get completed reports that need distribution
        reports = AlertReport.objects.filter(
            status='completed',
            auto_distribute=True,
            generated_at__gte=timezone.now() - timedelta(hours=1)
        )
        
        distributed_count = 0
        for report in reports:
            # Simulate distribution
            # In real implementation, would send email, webhook, etc.
            distributed_count += 1
        
        logger.info(f"Distributed {distributed_count} reports")
        return distributed_count
        
    except Exception as e:
        logger.error(f"Error in distribute_reports: {e}")
        return 0


@shared_task
def cleanup_old_reports():
    """Clean up old generated reports"""
    try:
        days_to_keep = 90
        cutoff_date = timezone.now() - timedelta(days=days_to_keep)
        
        deleted_count = AlertReport.objects.filter(
            created_at__lt=cutoff_date
        ).delete()[0]
        
        logger.info(f"Cleaned up {deleted_count} old reports")
        return deleted_count
        
    except Exception as e:
        logger.error(f"Error in cleanup_old_reports: {e}")
        return 0


@shared_task
def schedule_recurring_reports():
    """Schedule next run for recurring reports"""
    try:
        # Get recurring reports that need scheduling
        reports = AlertReport.objects.filter(
            is_recurring=True,
            next_run__lte=timezone.now()
        )
        
        scheduled_count = 0
        for report in reports:
            report.schedule_next_run()
            scheduled_count += 1
        
        logger.info(f"Scheduled {scheduled_count} recurring reports")
        return scheduled_count
        
    except Exception as e:
        logger.error(f"Error in schedule_recurring_reports: {e}")
        return 0


@shared_task
def update_reporting_metrics():
    """Update reporting metrics and statistics"""
    try:
        # Update MTTR/MTTD metrics
        mttr_count = calculate_mttr_metrics()
        mttd_count = calculate_mttd_metrics()
        
        # Check for SLA breaches
        breach_count = check_sla_breaches()
        
        logger.info(f"Updated reporting metrics: MTTR({mttr_count}), MTTD({mttd_count}), SLA breaches({breach_count})")
        return {
            'mttr_updated': mttr_count,
            'mttd_updated': mttd_count,
            'sla_breaches': breach_count
        }
        
    except Exception as e:
        logger.error(f"Error in update_reporting_metrics: {e}")
        return {'mttr_updated': 0, 'mttd_updated': 0, 'sla_breaches': 0}


@shared_task
def generate_custom_report(report_id):
    """Generate a specific custom report"""
    try:
        report = AlertReport.objects.get(id=report_id)
        report.generate_report()
        
        logger.info(f"Generated custom report: {report_id}")
        return report.id
        
    except Exception as e:
        logger.error(f"Error in generate_custom_report: {e}")
        return None


@shared_task
def export_report(report_id, format_type=None):
    """Export a report in specified format"""
    try:
        report = AlertReport.objects.get(id=report_id)
        
        if format_type:
            report.format_type = format_type
            report.save(update_fields=['format_type'])
        
        export_data = report.export_to_file()
        
        logger.info(f"Exported report {report_id} in {format_type or report.format_type} format")
        return export_data
        
    except Exception as e:
        logger.error(f"Error in export_report: {e}")
        return None


@shared_task
def create_scheduled_report(report_config):
    """Create and schedule a report based on configuration"""
    try:
        # Create report from configuration
        report = AlertReport.objects.create(**report_config)
        
        # Generate the report
        report.generate_report()
        
        # Schedule next run if recurring
        if report.is_recurring:
            report.schedule_next_run()
        
        logger.info(f"Created scheduled report: {report.id}")
        return report.id
        
    except Exception as e:
        logger.error(f"Error in create_scheduled_report: {e}")
        return None


@shared_task
def analyze_report_usage():
    """Analyze report usage and generate insights"""
    try:
        # Analyze recent report usage
        cutoff_date = timezone.now() - timedelta(days=30)
        
        reports = AlertReport.objects.filter(created_at__gte=cutoff_date)
        
        usage_stats = {
            'total_reports': reports.count(),
            'by_type': {},
            'by_status': {},
            'most_popular_types': [],
            'average_generation_time': 0
        }
        
        # By type
        type_stats = reports.values('report_type').annotate(count=models.Count('id'))
        usage_stats['by_type'] = {stat['report_type']: stat['count'] for stat in type_stats}
        
        # By status
        status_stats = reports.values('status').annotate(count=models.Count('id'))
        usage_stats['by_status'] = {stat['status']: stat['count'] for stat in status_stats}
        
        # Most popular types
        popular_types = type_stats.order_by('-count')[:5]
        usage_stats['most_popular_types'] = [
            {'type': stat['report_type'], 'count': stat['count']} for stat in popular_types
        ]
        
        # Average generation time
        completed_reports = reports.filter(status='completed', generation_duration_ms__isnull=False)
        if completed_reports.exists():
            avg_time = completed_reports.aggregate(
                avg_time=models.Avg('generation_duration_ms')
            )['avg_time'] or 0
            usage_stats['average_generation_time'] = avg_time
        
        logger.info(f"Analyzed report usage: {usage_stats}")
        return usage_stats
        
    except Exception as e:
        logger.error(f"Error in analyze_report_usage: {e}")
        return None
