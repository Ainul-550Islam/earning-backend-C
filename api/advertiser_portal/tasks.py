"""
Background Tasks for Advertiser Portal

This module contains background task definitions for async processing,
including campaign optimization, report generation, and data synchronization.
"""

import time
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, date, timedelta
from decimal import Decimal
from dataclasses import dataclass
from enum import Enum

from celery import Celery
from celery.exceptions import Retry
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from django.core.mail import send_mail
from django.contrib.auth import get_user_model

from .models import *
from .services import *
from .utils import *
from .exceptions import *
from .constants import *
from .enums import *

# Import all 14 Celery task modules from the tasks directory
from api.advertiser_portal.tasks.alert_tasks import *
from api.advertiser_portal.tasks.auto_refill_tasks import *
from api.advertiser_portal.tasks.budget_check_tasks import *
from api.advertiser_portal.tasks.campaign_optimizer_tasks import *
from api.advertiser_portal.tasks.campaign_schedule_tasks import *
from api.advertiser_portal.tasks.cleanup_tasks import *
from api.advertiser_portal.tasks.conversion_quality_tasks import *
from api.advertiser_portal.tasks.creative_expiry_tasks import *
from api.advertiser_portal.tasks.domain_verify_tasks import *
from api.advertiser_portal.tasks.fraud_config_tasks import *
from api.advertiser_portal.tasks.invoice_tasks import *
from api.advertiser_portal.tasks.offer_moderation_tasks import *
from api.advertiser_portal.tasks.report_generation_tasks import *
from api.advertiser_portal.tasks.spend_rollup_tasks import *


User = get_user_model()
logger = logging.getLogger(__name__)

# Celery app configuration
app = Celery('advertiser_portal')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()


class TaskPriority(Enum):
    """Task priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4
    CRITICAL = 5


@dataclass
class TaskResult:
    """Task result data structure."""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time: Optional[float] = None


@app.task(bind=True, max_retries=3)
def process_campaign_optimization(self, campaign_id: str) -> Dict[str, Any]:
    """
    Optimize campaign performance based on historical data.
    
    Args:
        campaign_id: Campaign UUID
        
    Returns:
        Task result dictionary
    """
    start_time = time.time()
    
    try:
        # Get campaign
        campaign = Campaign.objects.get(id=campaign_id, is_deleted=False)
        
        # Get analytics service
        analytics_service = AnalyticsService()
        campaign_service = CampaignService()
        
        # Get performance data
        performance = analytics_service.get_campaign_performance(campaign_id)
        
        # Generate optimization recommendations
        recommendations = campaign_service.generate_optimization_recommendations(campaign, performance)
        
        # Apply optimizations if configured
        if campaign.auto_optimize:
            optimization_results = campaign_service.apply_optimizations(campaign, recommendations)
            
            result = TaskResult(
                success=True,
                message="Campaign optimization completed successfully",
                data={
                    'campaign_id': campaign_id,
                    'recommendations': recommendations,
                    'optimizations_applied': optimization_results,
                    'performance_before': performance
                },
                execution_time=time.time() - start_time
            )
        else:
            result = TaskResult(
                success=True,
                message="Campaign optimization recommendations generated",
                data={
                    'campaign_id': campaign_id,
                    'recommendations': recommendations,
                    'performance_before': performance
                },
                execution_time=time.time() - start_time
            )
        
        # Log optimization
        logger.info(f"Campaign optimization completed for {campaign_id}: {result.message}")
        
        return result.__dict__
        
    except Campaign.DoesNotExist:
        error_msg = f"Campaign {campaign_id} not found"
        logger.error(error_msg)
        return TaskResult(
            success=False,
            message=error_msg,
            execution_time=time.time() - start_time
        ).__dict__
        
    except Exception as e:
        logger.error(f"Campaign optimization failed for {campaign_id}: {str(e)}")
        
        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (2 ** self.request.retries))
        
        return TaskResult(
            success=False,
            message=f"Campaign optimization failed: {str(e)}",
            error=str(e),
            execution_time=time.time() - start_time
        ).__dict__


@app.task(bind=True, max_retries=3)
def generate_analytics_report(self, report_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate analytics report based on configuration.
    
    Args:
        report_config: Report configuration dictionary
        
    Returns:
        Task result dictionary
    """
    start_time = time.time()
    
    try:
        # Extract report parameters
        report_type = report_config.get('type', 'performance')
        start_date = report_config.get('start_date')
        end_date = report_config.get('end_date')
        advertiser_ids = report_config.get('advertiser_ids', [])
        campaign_ids = report_config.get('campaign_ids', [])
        metrics = report_config.get('metrics', ['impressions', 'clicks', 'conversions'])
        format_type = report_config.get('format', 'json')
        email_recipients = report_config.get('email_recipients', [])
        
        # Get analytics service
        analytics_service = AnalyticsService()
        
        # Generate report data
        report_data = analytics_service.generate_report(
            report_type=report_type,
            start_date=start_date,
            end_date=end_date,
            advertiser_ids=advertiser_ids,
            campaign_ids=campaign_ids,
            metrics=metrics
        )
        
        # Format report
        formatted_report = analytics_service.format_report(report_data, format_type)
        
        # Save report if configured
        report_file_path = None
        if report_config.get('save_to_file', False):
            report_file_path = analytics_service.save_report(formatted_report, report_type, format_type)
        
        # Send email if configured
        if email_recipients and report_config.get('send_email', False):
            analytics_service.email_report(
                report_data=formatted_report,
                recipients=email_recipients,
                report_type=report_type,
                format_type=format_type
            )
        
        result = TaskResult(
            success=True,
            message=f"Analytics report generated successfully: {report_type}",
            data={
                'report_type': report_type,
                'period': f"{start_date} to {end_date}",
                'file_path': report_file_path,
                'email_sent': len(email_recipients) > 0,
                'record_count': len(report_data.get('data', []))
            },
            execution_time=time.time() - start_time
        )
        
        logger.info(f"Analytics report generated: {result.message}")
        
        return result.__dict__
        
    except Exception as e:
        logger.error(f"Analytics report generation failed: {str(e)}")
        
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (2 ** self.request.retries))
        
        return TaskResult(
            success=False,
            message=f"Report generation failed: {str(e)}",
            error=str(e),
            execution_time=time.time() - start_time
        ).__dict__


@app.task(bind=True, max_retries=3)
def process_billing_cycle(self, billing_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process billing cycle for advertisers.
    
    Args:
        billing_config: Billing configuration
        
    Returns:
        Task result dictionary
    """
    start_time = time.time()
    
    try:
        # Extract billing parameters
        cycle_type = billing_config.get('cycle_type', 'monthly')
        end_date = billing_config.get('end_date', timezone.now().date())
        advertiser_ids = billing_config.get('advertiser_ids', [])
        auto_charge = billing_config.get('auto_charge', False)
        
        # Get billing service
        billing_service = BillingService()
        
        # Process billing for specified advertisers or all
        if advertiser_ids:
            advertisers = Advertiser.objects.filter(id__in=advertiser_ids, is_deleted=False)
        else:
            advertisers = Advertiser.objects.filter(is_deleted=False, is_verified=True)
        
        processed_invoices = []
        failed_invoices = []
        total_amount = Decimal('0')
        
        for advertiser in advertisers:
            try:
                # Generate invoice
                invoice = billing_service.generate_invoice(
                    advertiser=advertiser,
                    cycle_type=cycle_type,
                    end_date=end_date
                )
                
                processed_invoices.append({
                    'advertiser_id': str(advertiser.id),
                    'invoice_id': str(invoice.id),
                    'amount': float(invoice.total_amount)
                })
                
                total_amount += invoice.total_amount
                
                # Auto-charge if configured
                if auto_charge and advertiser.auto_charge_enabled:
                    payment_result = billing_service.process_auto_charge(
                        advertiser=advertiser,
                        invoice=invoice
                    )
                    
                    if payment_result['success']:
                        processed_invoices[-1]['payment_processed'] = True
                        processed_invoices[-1]['payment_id'] = payment_result['payment_id']
                    else:
                        processed_invoices[-1]['payment_failed'] = True
                        processed_invoices[-1]['payment_error'] = payment_result['error']
                
            except Exception as e:
                failed_invoices.append({
                    'advertiser_id': str(advertiser.id),
                    'error': str(e)
                })
                logger.error(f"Billing failed for advertiser {advertiser.id}: {str(e)}")
        
        result = TaskResult(
            success=len(failed_invoices) == 0,
            message=f"Billing cycle processed: {len(processed_invoices)} successful, {len(failed_invoices)} failed",
            data={
                'cycle_type': cycle_type,
                'end_date': str(end_date),
                'processed_invoices': processed_invoices,
                'failed_invoices': failed_invoices,
                'total_amount': float(total_amount)
            },
            execution_time=time.time() - start_time
        )
        
        logger.info(f"Billing cycle completed: {result.message}")
        
        return result.__dict__
        
    except Exception as e:
        logger.error(f"Billing cycle processing failed: {str(e)}")
        
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (2 ** self.request.retries))
        
        return TaskResult(
            success=False,
            message=f"Billing cycle failed: {str(e)}",
            error=str(e),
            execution_time=time.time() - start_time
        ).__dict__


@app.task(bind=True, max_retries=3)
def detect_fraud_activity(self, detection_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Detect and handle fraudulent activity.
    
    Args:
        detection_config: Fraud detection configuration
        
    Returns:
        Task result dictionary
    """
    start_time = time.time()
    
    try:
        # Extract detection parameters
        time_window = detection_config.get('time_window', 24)  # hours
        fraud_types = detection_config.get('fraud_types', ['click_fraud', 'impression_fraud'])
        auto_block = detection_config.get('auto_block', True)
        
        # Get fraud detection service
        fraud_service = FraudDetectionService()
        
        # Run fraud detection
        detection_results = fraud_service.detect_fraud(
            time_window_hours=time_window,
            fraud_types=fraud_types
        )
        
        # Process detected fraud
        blocked_activities = []
        flagged_activities = []
        
        for fraud_case in detection_results['detected_cases']:
            if fraud_case['risk_score'] >= 80 and auto_block:
                # Block high-risk activity
                block_result = fraud_service.block_activity(fraud_case)
                blocked_activities.append({
                    'case_id': fraud_case['id'],
                    'type': fraud_case['type'],
                    'blocked': block_result['success']
                })
            else:
                # Flag medium-risk activity
                flagged_activities.append({
                    'case_id': fraud_case['id'],
                    'type': fraud_case['type'],
                    'risk_score': fraud_case['risk_score']
                })
        
        # Send alerts for detected fraud
        if detection_results['detected_cases']:
            fraud_service.send_fraud_alerts(detection_results['detected_cases'])
        
        result = TaskResult(
            success=True,
            message=f"Fraud detection completed: {len(detection_results['detected_cases'])} cases detected",
            data={
                'time_window_hours': time_window,
                'total_cases': len(detection_results['detected_cases']),
                'blocked_activities': blocked_activities,
                'flagged_activities': flagged_activities,
                'detection_summary': detection_results.get('summary', {})
            },
            execution_time=time.time() - start_time
        )
        
        logger.info(f"Fraud detection completed: {result.message}")
        
        return result.__dict__
        
    except Exception as e:
        logger.error(f"Fraud detection failed: {str(e)}")
        
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (2 ** self.request.retries))
        
        return TaskResult(
            success=False,
            message=f"Fraud detection failed: {str(e)}",
            error=str(e),
            execution_time=time.time() - start_time
        ).__dict__


@app.task(bind=True, max_retries=3)
def synchronize_integrations(self, integration_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Synchronize data with third-party integrations.
    
    Args:
        integration_config: Integration configuration
        
    Returns:
        Task result dictionary
    """
    start_time = time.time()
    
    try:
        # Extract integration parameters
        integration_types = integration_config.get('types', ['google_ads', 'facebook_ads'])
        advertiser_ids = integration_config.get('advertiser_ids', [])
        sync_type = integration_config.get('sync_type', 'full')  # full, incremental
        
        # Get integration service
        integration_service = IntegrationService()
        
        sync_results = []
        
        for integration_type in integration_types:
            try:
                # Get advertisers for this integration
                advertisers = Advertiser.objects.filter(
                    is_deleted=False,
                    integrations__type=integration_type
                )
                
                if advertiser_ids:
                    advertisers = advertisers.filter(id__in=advertiser_ids)
                
                # Perform synchronization
                sync_result = integration_service.synchronize(
                    integration_type=integration_type,
                    advertisers=advertisers,
                    sync_type=sync_type
                )
                
                sync_results.append({
                    'integration_type': integration_type,
                    'success': sync_result['success'],
                    'synced_advertisers': len(sync_result.get('synced_advertisers', [])),
                    'errors': sync_result.get('errors', [])
                })
                
            except Exception as e:
                sync_results.append({
                    'integration_type': integration_type,
                    'success': False,
                    'error': str(e)
                })
                logger.error(f"Integration sync failed for {integration_type}: {str(e)}")
        
        successful_syncs = [r for r in sync_results if r['success']]
        failed_syncs = [r for r in sync_results if not r['success']]
        
        result = TaskResult(
            success=len(failed_syncs) == 0,
            message=f"Integration sync completed: {len(successful_syncs)} successful, {len(failed_syncs)} failed",
            data={
                'sync_type': sync_type,
                'integration_results': sync_results,
                'total_synced': sum(r.get('synced_advertisers', 0) for r in successful_syncs)
            },
            execution_time=time.time() - start_time
        )
        
        logger.info(f"Integration synchronization completed: {result.message}")
        
        return result.__dict__
        
    except Exception as e:
        logger.error(f"Integration synchronization failed: {str(e)}")
        
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (2 ** self.request.retries))
        
        return TaskResult(
            success=False,
            message=f"Integration sync failed: {str(e)}",
            error=str(e),
            execution_time=time.time() - start_time
        ).__dict__


@app.task(bind=True, max_retries=3)
def cleanup_old_data(self, cleanup_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Clean up old data and maintain database performance.
    
    Args:
        cleanup_config: Cleanup configuration
        
    Returns:
        Task result dictionary
    """
    start_time = time.time()
    
    try:
        # Extract cleanup parameters
        data_types = cleanup_config.get('data_types', ['logs', 'analytics', 'cache'])
        retention_days = cleanup_config.get('retention_days', 90)
        dry_run = cleanup_config.get('dry_run', False)
        
        cutoff_date = timezone.now() - timedelta(days=retention_days)
        
        cleanup_results = []
        
        # Clean up old logs
        if 'logs' in data_types:
            logs_deleted = 0
            if not dry_run:
                logs_deleted = AuditLog.objects.filter(
                    created_at__lt=cutoff_date
                ).delete()[0]
            
            cleanup_results.append({
                'data_type': 'logs',
                'records_deleted': logs_deleted,
                'cutoff_date': cutoff_date.isoformat()
            })
        
        # Clean up old analytics data
        if 'analytics' in data_types:
            analytics_deleted = 0
            if not dry_run:
                # This would depend on your analytics data structure
                # analytics_deleted = AnalyticsData.objects.filter(
                #     date__lt=cutoff_date.date()
                # ).delete()[0]
                analytics_deleted = 0  # Placeholder
            
            cleanup_results.append({
                'data_type': 'analytics',
                'records_deleted': analytics_deleted,
                'cutoff_date': cutoff_date.isoformat()
            })
        
        # Clean up old cache entries
        if 'cache' in data_types:
            cache_cleared = 0
            if not dry_run:
                # This would depend on your cache backend
                # cache_cleared = cache.clear_old_entries(cutoff_date)
                cache_cleared = 0  # Placeholder
            
            cleanup_results.append({
                'data_type': 'cache',
                'entries_cleared': cache_cleared,
                'cutoff_date': cutoff_date.isoformat()
            })
        
        total_deleted = sum(r.get('records_deleted', 0) for r in cleanup_results)
        
        result = TaskResult(
            success=True,
            message=f"Data cleanup completed: {total_deleted} records processed",
            data={
                'retention_days': retention_days,
                'dry_run': dry_run,
                'cutoff_date': cutoff_date.isoformat(),
                'cleanup_results': cleanup_results,
                'total_records_processed': total_deleted
            },
            execution_time=time.time() - start_time
        )
        
        logger.info(f"Data cleanup completed: {result.message}")
        
        return result.__dict__
        
    except Exception as e:
        logger.error(f"Data cleanup failed: {str(e)}")
        
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (2 ** self.request.retries))
        
        return TaskResult(
            success=False,
            message=f"Data cleanup failed: {str(e)}",
            error=str(e),
            execution_time=time.time() - start_time
        ).__dict__


@app.task(bind=True, max_retries=3)
def send_budget_alerts(self, alert_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Send budget alerts to advertisers.
    
    Args:
        alert_config: Alert configuration
        
    Returns:
        Task result dictionary
    """
    start_time = time.time()
    
    try:
        # Extract alert parameters
        alert_types = alert_config.get('types', ['low_budget', 'exhausted'])
        threshold_percent = alert_config.get('threshold_percent', 80)
        advertiser_ids = alert_config.get('advertiser_ids', [])
        
        # Get campaigns that need alerts
        campaigns = Campaign.objects.filter(
            is_deleted=False,
            status=StatusEnum.ACTIVE.value
        )
        
        if advertiser_ids:
            campaigns = campaigns.filter(advertiser_id__in=advertiser_ids)
        
        alerts_sent = []
        
        for campaign in campaigns:
            budget_utilization = campaign.budget_utilization
            
            # Check for low budget alert
            if 'low_budget' in alert_types and budget_utilization >= threshold_percent:
                alert_data = {
                    'campaign_id': str(campaign.id),
                    'campaign_name': campaign.name,
                    'advertiser_id': str(campaign.advertiser.id),
                    'advertiser_name': campaign.advertiser.company_name,
                    'alert_type': 'low_budget',
                    'budget_utilization': budget_utilization,
                    'remaining_budget': float(campaign.remaining_budget)
                }
                
                # Send alert
                email_sent = _send_budget_alert_email(alert_data)
                alert_data['email_sent'] = email_sent
                alerts_sent.append(alert_data)
            
            # Check for exhausted budget alert
            elif 'exhausted' in alert_types and budget_utilization >= 100:
                alert_data = {
                    'campaign_id': str(campaign.id),
                    'campaign_name': campaign.name,
                    'advertiser_id': str(campaign.advertiser.id),
                    'advertiser_name': campaign.advertiser.company_name,
                    'alert_type': 'budget_exhausted',
                    'budget_utilization': budget_utilization,
                    'overspend': float(max(0, campaign.current_spend - campaign.total_budget))
                }
                
                # Send alert
                email_sent = _send_budget_alert_email(alert_data)
                alert_data['email_sent'] = email_sent
                alerts_sent.append(alert_data)
        
        result = TaskResult(
            success=True,
            message=f"Budget alerts sent: {len(alerts_sent)} alerts processed",
            data={
                'alert_types': alert_types,
                'threshold_percent': threshold_percent,
                'alerts_sent': alerts_sent
            },
            execution_time=time.time() - start_time
        )
        
        logger.info(f"Budget alerts completed: {result.message}")
        
        return result.__dict__
        
    except Exception as e:
        logger.error(f"Budget alerts failed: {str(e)}")
        
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (2 ** self.request.retries))
        
        return TaskResult(
            success=False,
            message=f"Budget alerts failed: {str(e)}",
            error=str(e),
            execution_time=time.time() - start_time
        ).__dict__


def _send_budget_alert_email(alert_data: Dict[str, Any]) -> bool:
    """Send budget alert email to advertiser."""
    try:
        subject = f"Budget Alert: {alert_data['campaign_name']}"
        
        if alert_data['alert_type'] == 'low_budget':
            message = f"""
            Dear {alert_data['advertiser_name']},
            
            Your campaign "{alert_data['campaign_name']}" has used {alert_data['budget_utilization']:.1f}% of its budget.
            
            Remaining budget: ${alert_data['remaining_budget']:.2f}
            
            Please consider adding more funds to avoid campaign interruption.
            """
        else:  # budget_exhausted
            message = f"""
            Dear {alert_data['advertiser_name']},
            
            Your campaign "{alert_data['campaign_name']}" has exhausted its budget.
            
            {"Overspend: $" + str(alert_data['overspend']) + ". " if alert_data['overspend'] > 0 else ""}
            
            The campaign has been paused. Please add funds to resume advertising.
            """
        
        # Get advertiser email
        advertiser = Advertiser.objects.get(id=alert_data['advertiser_id'])
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[advertiser.contact_email],
            fail_silently=False
        )
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to send budget alert email: {str(e)}")
        return False


# Periodic tasks
@app.task
def daily_maintenance():
    """Run daily maintenance tasks."""
    logger.info("Starting daily maintenance tasks")
    
    # Process campaign optimizations
    active_campaigns = Campaign.objects.filter(
        status=StatusEnum.ACTIVE.value,
        is_deleted=False,
        auto_optimize=True
    )
    
    for campaign in active_campaigns:
        process_campaign_optimization.delay(str(campaign.id))
    
    # Detect fraud activity
    detect_fraud_activity.delay({
        'time_window': 24,
        'auto_block': True
    })
    
    # Send budget alerts
    send_budget_alerts.delay({
        'types': ['low_budget', 'exhausted'],
        'threshold_percent': 80
    })
    
    logger.info("Daily maintenance tasks completed")


@app.task
def weekly_maintenance():
    """Run weekly maintenance tasks."""
    logger.info("Starting weekly maintenance tasks")
    
    # Generate weekly reports
    generate_analytics_report.delay({
        'type': 'weekly_performance',
        'start_date': (timezone.now() - timedelta(days=7)).date(),
        'end_date': timezone.now().date(),
        'format': 'pdf',
        'send_email': True,
        'save_to_file': True
    })
    
    # Synchronize integrations
    synchronize_integrations.delay({
        'types': ['google_ads', 'facebook_ads'],
        'sync_type': 'incremental'
    })
    
    logger.info("Weekly maintenance tasks completed")


@app.task
def monthly_maintenance():
    """Run monthly maintenance tasks."""
    logger.info("Starting monthly maintenance tasks")
    
    # Process billing cycle
    process_billing_cycle.delay({
        'cycle_type': 'monthly',
        'auto_charge': True
    })
    
    # Clean up old data
    cleanup_old_data.delay({
        'data_types': ['logs', 'analytics'],
        'retention_days': 90,
        'dry_run': False
    })
    
    # Generate monthly reports
    generate_analytics_report.delay({
        'type': 'monthly_performance',
        'start_date': (timezone.now() - timedelta(days=30)).date(),
        'end_date': timezone.now().date(),
        'format': 'excel',
        'send_email': True,
        'save_to_file': True
    })
    
    logger.info("Monthly maintenance tasks completed")


# Schedule periodic tasks
from celery.schedules import crontab

app.conf.beat_schedule = {
    'daily-maintenance': {
        'task': 'api.advertiser_portal.tasks.daily_maintenance',
        'schedule': crontab(hour=2, minute=0),  # 2:00 AM daily
    },
    'weekly-maintenance': {
        'task': 'api.advertiser_portal.tasks.weekly_maintenance',
        'schedule': crontab(hour=3, minute=0, day_of_week=1),  # 3:00 AM every Monday
    },
    'monthly-maintenance': {
        'task': 'api.advertiser_portal.tasks.monthly_maintenance',
        'schedule': crontab(hour=4, minute=0, day_of_month=1),  # 4:00 AM on 1st of each month
    },
}
