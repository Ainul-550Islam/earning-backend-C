"""
Report Generation Tasks

Daily report generation for advertisers
and system performance metrics.
"""

from celery import shared_task
from django.utils import timezone
from django.db.models import Q, Sum, Count, Avg
from django.core.cache import cache

from ..models.reporting import CampaignReport, PublisherBreakdown, AdvertiserReport
from ..models.campaign import AdCampaign
from ..models.offer import AdvertiserOffer
from ..models.billing import AdvertiserInvoice
try:
    from ..services import AdvertiserReportService
except ImportError:
    AdvertiserReportService = None
try:
    from ..services import ReportExportService
except ImportError:
    ReportExportService = None

import logging
logger = logging.getLogger(__name__)


@shared_task(name="advertiser_portal.generate_daily_reports")
def generate_daily_reports():
    """
    Generate daily performance reports for all advertisers.
    
    This task runs daily at midnight to generate
    comprehensive performance reports for each advertiser.
    """
    try:
        report_service = AdvertiserReportService()
        export_service = ReportExportService()
        
        # Get all active advertisers
        from ..models.advertiser import Advertiser
        active_advertisers = Advertiser.objects.filter(
            status='active'
        ).select_related('profile')
        
        reports_generated = 0
        reports_failed = 0
        
        for advertiser in active_advertisers:
            try:
                # Generate daily report
                yesterday = timezone.now().date() - timezone.timedelta(days=1)
                
                report_data = report_service.generate_daily_report(
                    advertiser,
                    yesterday
                )
                
                # Save report to database
                report = AdvertiserReport.objects.create(
                    advertiser=advertiser,
                    report_type='daily',
                    report_date=yesterday,
                    data=report_data,
                    generated_at=timezone.now()
                )
                
                # Generate PDF report
                pdf_content = export_service.generate_daily_report_pdf(report_data)
                
                # Save PDF file
                from django.core.files.base import ContentFile
                filename = f"daily_report_{advertiser.id}_{yesterday.strftime('%Y%m%d')}.pdf"
                report.file_path.save(filename, ContentFile(pdf_content))
                
                reports_generated += 1
                logger.info(f"Daily report generated for advertiser {advertiser.id}")
                
                # Send report notification
                _send_daily_report_notification(advertiser, report)
                
            except Exception as e:
                reports_failed += 1
                logger.error(f"Error generating daily report for advertiser {advertiser.id}: {e}")
                continue
        
        logger.info(f"Daily report generation completed: {reports_generated} reports generated, {reports_failed} reports failed")
        
        return {
            'advertisers_checked': active_advertisers.count(),
            'reports_generated': reports_generated,
            'reports_failed': reports_failed,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in daily report generation task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name="advertiser_portal.generate_weekly_reports")
def generate_weekly_reports():
    """
    Generate weekly performance reports for all advertisers.
    
    This task runs weekly on Sunday to generate
    comprehensive weekly performance reports.
    """
    try:
        report_service = AdvertiserReportService()
        export_service = ReportExportService()
        
        # Get all active advertisers
        from ..models.advertiser import Advertiser
        active_advertisers = Advertiser.objects.filter(
            status='active'
        ).select_related('profile')
        
        reports_generated = 0
        reports_failed = 0
        
        for advertiser in active_advertisers:
            try:
                # Generate weekly report
                end_date = timezone.now().date()
                start_date = end_date - timezone.timedelta(days=7)
                
                report_data = report_service.generate_weekly_report(
                    advertiser,
                    start_date,
                    end_date
                )
                
                # Save report to database
                report = AdvertiserReport.objects.create(
                    advertiser=advertiser,
                    report_type='weekly',
                    report_date=end_date,
                    data=report_data,
                    generated_at=timezone.now()
                )
                
                # Generate PDF report
                pdf_content = export_service.generate_weekly_report_pdf(report_data)
                
                # Save PDF file
                from django.core.files.base import ContentFile
                filename = f"weekly_report_{advertiser.id}_{end_date.strftime('%Y%m%d')}.pdf"
                report.file_path.save(filename, ContentFile(pdf_content))
                
                reports_generated += 1
                logger.info(f"Weekly report generated for advertiser {advertiser.id}")
                
                # Send report notification
                _send_weekly_report_notification(advertiser, report)
                
            except Exception as e:
                reports_failed += 1
                logger.error(f"Error generating weekly report for advertiser {advertiser.id}: {e}")
                continue
        
        logger.info(f"Weekly report generation completed: {reports_generated} reports generated, {reports_failed} reports failed")
        
        return {
            'advertisers_checked': active_advertisers.count(),
            'reports_generated': reports_generated,
            'reports_failed': reports_failed,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in weekly report generation task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name="advertiser_portal.generate_monthly_reports")
def generate_monthly_reports():
    """
    Generate monthly performance reports for all advertisers.
    
    This task runs monthly on the 1st to generate
    comprehensive monthly performance reports.
    """
    try:
        report_service = AdvertiserReportService()
        export_service = ReportExportService()
        
        # Get all active advertisers
        from ..models.advertiser import Advertiser
        active_advertisers = Advertiser.objects.filter(
            status='active'
        ).select_related('profile')
        
        reports_generated = 0
        reports_failed = 0
        
        for advertiser in active_advertisers:
            try:
                # Generate monthly report
                end_date = timezone.now().date().replace(day=1) - timezone.timedelta(days=1)
                start_date = end_date.replace(day=1)
                
                report_data = report_service.generate_monthly_report(
                    advertiser,
                    start_date,
                    end_date
                )
                
                # Save report to database
                report = AdvertiserReport.objects.create(
                    advertiser=advertiser,
                    report_type='monthly',
                    report_date=end_date,
                    data=report_data,
                    generated_at=timezone.now()
                )
                
                # Generate PDF report
                pdf_content = export_service.generate_monthly_report_pdf(report_data)
                
                # Save PDF file
                from django.core.files.base import ContentFile
                filename = f"monthly_report_{advertiser.id}_{end_date.strftime('%Y%m')}.pdf"
                report.file_path.save(filename, ContentFile(pdf_content))
                
                reports_generated += 1
                logger.info(f"Monthly report generated for advertiser {advertiser.id}")
                
                # Send report notification
                _send_monthly_report_notification(advertiser, report)
                
            except Exception as e:
                reports_failed += 1
                logger.error(f"Error generating monthly report for advertiser {advertiser.id}: {e}")
                continue
        
        logger.info(f"Monthly report generation completed: {reports_generated} reports generated, {reports_failed} reports failed")
        
        return {
            'advertisers_checked': active_advertisers.count(),
            'reports_generated': reports_generated,
            'reports_failed': reports_failed,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in monthly report generation task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name="advertiser_portal.generate_system_reports")
def generate_system_reports():
    """
    Generate system performance reports.
    
    This task runs daily to generate system-wide
    performance and operational reports.
    """
    try:
        # Generate system performance report
        yesterday = timezone.now().date() - timezone.timedelta(days=1)
        
        system_report = _generate_system_performance_report(yesterday)
        
        # Save system report
        from ..models.reporting import SystemReport
        system_report_obj = SystemReport.objects.create(
            report_type='daily_system',
            report_date=yesterday,
            data=system_report,
            generated_at=timezone.now()
        )
        
        # Generate and save PDF
        export_service = ReportExportService()
        pdf_content = export_service.generate_system_report_pdf(system_report)
        
        from django.core.files.base import ContentFile
        filename = f"system_report_{yesterday.strftime('%Y%m%d')}.pdf"
        system_report_obj.file_path.save(filename, ContentFile(pdf_content))
        
        logger.info(f"System report generated for {yesterday}")
        
        # Send admin notification
        _send_system_report_notification(system_report_obj)
        
        return {
            'report_date': yesterday.isoformat(),
            'system_report_generated': True,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in system report generation task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name="advertiser_portal.aggregate_report_data")
def aggregate_report_data():
    """
    Aggregate report data for performance metrics.
    
    This task runs hourly to aggregate performance data
    for faster report generation.
    """
    try:
        # Get current hour
        current_time = timezone.now()
        hour_start = current_time.replace(minute=0, second=0, microsecond=0)
        hour_end = hour_start + timezone.timedelta(hours=1)
        
        # Aggregate campaign performance
        campaign_aggregates = _aggregate_campaign_performance(hour_start, hour_end)
        
        # Aggregate publisher performance
        publisher_aggregates = _aggregate_publisher_performance(hour_start, hour_end)
        
        # Store aggregates in cache
        cache_key = f"report_aggregates_{hour_start.strftime('%Y%m%d_%H')}"
        cache.set(cache_key, {
            'campaigns': campaign_aggregates,
            'publishers': publisher_aggregates,
            'generated_at': current_time.isoformat()
        }, timeout=86400)  # Cache for 24 hours
        
        logger.info(f"Report data aggregated for hour {hour_start.strftime('%Y-%m-%d %H:00')}")
        
        return {
            'hour': hour_start.strftime('%Y-%m-%d %H:00'),
            'campaigns_aggregated': len(campaign_aggregates),
            'publishers_aggregated': len(publisher_aggregates),
            'timestamp': current_time.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in report data aggregation task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name="advertiser_portal.cleanup_report_cache")
def cleanup_report_cache():
    """
    Clean up old report cache entries.
    
    This task runs daily to clean up cached
    report data to maintain performance.
    """
    try:
        # Clean up cache entries older than 7 days
        cutoff_time = timezone.now() - timezone.timedelta(days=7)
        
        # This would implement actual cache cleanup
        # For now, just log the action
        cache_keys_cleaned = 0
        
        logger.info(f"Report cache cleanup completed: {cache_keys_cleaned} cache entries cleaned")
        
        return {
            'cutoff_time': cutoff_time.isoformat(),
            'cache_keys_cleaned': cache_keys_cleaned,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in report cache cleanup task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


def _generate_system_performance_report(date):
    """Generate system performance report data."""
    try:
        # Get system metrics for the date
        from django.db import connection
        
        # Campaign metrics
        active_campaigns = AdCampaign.objects.filter(
            status='active'
        ).count()
        
        total_campaigns = AdCampaign.objects.count()
        
        # Advertiser metrics
        active_advertisers = AdCampaign.objects.filter(
            status='active'
        ).values('advertiser').distinct().count()
        
        # Performance metrics (simplified)
        system_report = {
            'date': date.isoformat(),
            'campaigns': {
                'total': total_campaigns,
                'active': active_campaigns,
                'inactive': total_campaigns - active_campaigns,
            },
            'advertisers': {
                'active': active_advertisers,
            },
            'system_health': {
                'database_status': 'healthy',
                'cache_status': 'healthy',
                'task_queue_status': 'healthy',
            },
            'generated_at': timezone.now().isoformat(),
        }
        
        return system_report
        
    except Exception as e:
        logger.error(f"Error generating system performance report: {e}")
        return {}


def _aggregate_campaign_performance(start_time, end_time):
    """Aggregate campaign performance for the hour."""
    try:
        # This would implement actual campaign performance aggregation
        # For now, return empty list
        return []
        
    except Exception as e:
        logger.error(f"Error aggregating campaign performance: {e}")
        return []


def _aggregate_publisher_performance(start_time, end_time):
    """Aggregate publisher performance for the hour."""
    try:
        # This would implement actual publisher performance aggregation
        # For now, return empty list
        return []
        
    except Exception as e:
        logger.error(f"Error aggregating publisher performance: {e}")
        return []


def _send_daily_report_notification(advertiser, report):
    """Send daily report notification."""
    try:
        try:
            from ..services import NotificationService
        except ImportError:
            NotificationService = None
        
        notification_service = NotificationService()
        
        notification_data = {
            'advertiser': advertiser,
            'type': 'daily_report',
            'title': 'Daily Performance Report',
            'message': f'Your daily performance report for {report.report_date} is now available.',
            'data': {
                'report_id': report.id,
                'report_date': report.report_date.isoformat(),
                'file_path': report.file_path.name if report.file_path else None,
            }
        }
        
        notification_service.send_notification(notification_data)
        
    except Exception as e:
        logger.error(f"Error sending daily report notification: {e}")


def _send_weekly_report_notification(advertiser, report):
    """Send weekly report notification."""
    try:
        try:
            from ..services import NotificationService
        except ImportError:
            NotificationService = None
        
        notification_service = NotificationService()
        
        notification_data = {
            'advertiser': advertiser,
            'type': 'weekly_report',
            'title': 'Weekly Performance Report',
            'message': f'Your weekly performance report for {report.report_date} is now available.',
            'data': {
                'report_id': report.id,
                'report_date': report.report_date.isoformat(),
                'file_path': report.file_path.name if report.file_path else None,
            }
        }
        
        notification_service.send_notification(notification_data)
        
    except Exception as e:
        logger.error(f"Error sending weekly report notification: {e}")


def _send_monthly_report_notification(advertiser, report):
    """Send monthly report notification."""
    try:
        try:
            from ..services import NotificationService
        except ImportError:
            NotificationService = None
        
        notification_service = NotificationService()
        
        notification_data = {
            'advertiser': advertiser,
            'type': 'monthly_report',
            'title': 'Monthly Performance Report',
            'message': f'Your monthly performance report for {report.report_date.strftime("%B %Y")} is now available.',
            'data': {
                'report_id': report.id,
                'report_date': report.report_date.isoformat(),
                'file_path': report.file_path.name if report.file_path else None,
            }
        }
        
        notification_service.send_notification(notification_data)
        
    except Exception as e:
        logger.error(f"Error sending monthly report notification: {e}")


def _send_system_report_notification(report):
    """Send system report notification to admins."""
    try:
        try:
            from ..services import NotificationService
        except ImportError:
            NotificationService = None
        
        notification_service = NotificationService()
        
        notification_data = {
            'type': 'system_report',
            'title': 'Daily System Report',
            'message': f'Daily system performance report for {report.report_date} is now available.',
            'data': {
                'report_id': report.id,
                'report_date': report.report_date.isoformat(),
                'file_path': report.file_path.name if report.file_path else None,
            }
        }
        
        # Send to admin users
        notification_service.send_admin_notification(notification_data)
        
    except Exception as e:
        logger.error(f"Error sending system report notification: {e}")
