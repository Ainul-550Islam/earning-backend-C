"""
Notification Tasks

This module contains Celery tasks for notification operations including
onboarding reminders, trial expiry notifications, quota alerts, and email processing.
"""

from celery import shared_task
from django.utils import timezone
from django.db import transaction
from datetime import timedelta
import logging

from ..models import Tenant, TenantNotification
from ..services import OnboardingService

logger = logging.getLogger(__name__)


@shared_task(name='tenants.notifications.send_onboarding_reminders')
def send_onboarding_reminders():
    """
    Send onboarding reminders for inactive tenants.
    
    This task runs daily to check for tenants with incomplete
    onboarding and send appropriate reminders.
    """
    logger.info("Starting onboarding reminder sending")
    
    sent_count = 0
    failed_count = 0
    errors = []
    
    # Get tenants with incomplete onboarding
    from ..models.onboarding import TenantOnboarding
    
    inactive_onboardings = TenantOnboarding.objects.filter(
        status='in_progress'
    ).select_related('tenant')
    
    for onboarding in inactive_onboardings:
        try:
            # Check if reminder should be sent
            if onboarding.needs_attention:
                days_inactive = onboarding.days_since_start
                
                # Determine reminder type based on inactivity
                if days_inactive >= 14:
                    title = 'Complete Your Setup'
                    message = f'You started your setup {days_inactive} days ago. Complete the remaining steps to get the most out of your account.'
                    priority = 'high'
                elif days_inactive >= 7:
                    title = 'Continue Your Setup'
                    message = f'You have incomplete setup steps. Continue your onboarding to unlock all features.'
                    priority = 'medium'
                else:
                    title = 'Setup Progress'
                    message = f'You\'re {onboarding.completion_pct}% through setup. Complete the remaining steps when you have time.'
                    priority = 'low'
                
                # Send notification
                TenantNotification.objects.create(
                    tenant=onboarding.tenant,
                    title=title,
                    message=message,
                    notification_type='onboarding',
                    priority=priority,
                    send_email=True,
                    send_push=True,
                    action_url='/onboarding',
                    action_text='Continue Setup',
                    metadata={
                        'onboarding_id': str(onboarding.id),
                        'completion_pct': onboarding.completion_pct,
                        'days_inactive': days_inactive,
                    },
                )
                
                sent_count += 1
                logger.info(f"Sent onboarding reminder to {onboarding.tenant.name}")
                
                # Update last reminder sent
                onboarding.last_reminder_sent = timezone.now()
                onboarding.save(update_fields=['last_reminder_sent'])
            
        except Exception as e:
            failed_count += 1
            error_msg = f"Failed to send onboarding reminder to {onboarding.tenant.name}: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
    
    result = {
        'sent_count': sent_count,
        'failed_count': failed_count,
        'errors': errors,
        'total_inactive': inactive_onboardings.count(),
    }
    
    logger.info(f"Onboarding reminders completed: {result}")
    return result


@shared_task(name='tenants.notifications.send_trial_expiry_notifications')
def send_trial_expiry_notifications():
    """
    Send trial expiry notifications for tenants.
    
    This task runs daily to check for trials expiring soon
    and send appropriate notifications.
    """
    logger.info("Starting trial expiry notification sending")
    
    sent_count = 0
    failed_count = 0
    errors = []
    
    # Get tenants with active trials
    trial_tenants = Tenant.objects.filter(
        is_deleted=False,
        trial_ends_at__isnull=False,
        trial_ends_at__gt=timezone.now()
    )
    
    for tenant in trial_tenants:
        try:
            days_until_expiry = tenant.days_until_trial_expiry
            
            if days_until_expiry is not None:
                # Determine notification type based on days until expiry
                if days_until_expiry <= 1:
                    title = 'Trial Expires Tomorrow'
                    message = f'Your trial expires tomorrow! Upgrade now to continue using all features.'
                    priority = 'urgent'
                elif days_until_expiry <= 3:
                    title = 'Trial Expires Soon'
                    message = f'Your trial expires in {days_until_expiry} days. Choose a plan to continue.'
                    priority = 'high'
                elif days_until_expiry <= 7:
                    title = 'Trial Reminder'
                    message = f'Your trial expires in {days_until_expiry} days. Explore upgrade options.'
                    priority = 'medium'
                elif days_until_expiry == 14:
                    title = 'Halfway Through Trial'
                    message = 'You\'re halfway through your trial! Make the most of your remaining time.'
                    priority = 'low'
                else:
                    continue  # Skip if not within notification range
                
                # Send notification
                TenantNotification.objects.create(
                    tenant=tenant,
                    title=title,
                    message=message,
                    notification_type='trial',
                    priority=priority,
                    send_email=True,
                    send_push=True,
                    action_url='/billing/plans',
                    action_text='Upgrade Plan',
                    metadata={
                        'trial_ends_at': tenant.trial_ends_at.isoformat(),
                        'days_until_expiry': days_until_expiry,
                    },
                )
                
                sent_count += 1
                logger.info(f"Sent trial expiry notification to {tenant.name} (expires in {days_until_expiry} days)")
            
        except Exception as e:
            failed_count += 1
            error_msg = f"Failed to send trial notification to {tenant.name}: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
    
    result = {
        'sent_count': sent_count,
        'failed_count': failed_count,
        'errors': errors,
        'total_trial_tenants': trial_tenants.count(),
    }
    
    logger.info(f"Trial expiry notifications completed: {result}")
    return result


@shared_task(name='tenants.notifications.send_quota_exceeded_notifications')
def send_quota_exceeded_notifications():
    """
    Send notifications for quota exceeded warnings.
    
    This task runs daily to check for tenants approaching or
    exceeding their plan quotas and send alerts.
    """
    logger.info("Starting quota exceeded notification sending")
    
    sent_count = 0
    failed_count = 0
    errors = []
    
    # Get all active tenants
    tenants = Tenant.objects.filter(is_deleted=False, status='active').select_related('plan')
    
    for tenant in tenants:
        try:
            # Get current usage
            from ..services import PlanUsageService
            usage = PlanUsageService.get_current_usage(tenant, 'monthly')
            
            quota_violations = []
            
            # Check each metric for quota violations
            for metric, data in usage.items():
                if isinstance(data, dict) and data.get('percentage', 0) > 100:
                    quota_violations.append({
                        'metric': metric,
                        'used': data['used'],
                        'limit': data['limit'],
                        'percentage': data['percentage'],
                    })
            
            if quota_violations:
                # Send quota exceeded notification
                violations_text = ', '.join([f"{v['metric']} ({v['percentage']:.1f}%)" for v in quota_violations])
                
                TenantNotification.objects.create(
                    tenant=tenant,
                    title='Quota Limits Exceeded',
                    message=f'You have exceeded your quota limits: {violations_text}. Consider upgrading your plan.',
                    notification_type='quota',
                    priority='high',
                    send_email=True,
                    send_push=True,
                    action_url='/billing/plans',
                    action_text='Upgrade Plan',
                    metadata={
                        'quota_violations': quota_violations,
                        'usage_data': usage,
                    },
                )
                
                sent_count += 1
                logger.warning(f"Sent quota exceeded notification to {tenant.name}: {violations_text}")
            
            # Check for quota warnings (80%+)
            else:
                quota_warnings = []
                
                for metric, data in usage.items():
                    if isinstance(data, dict) and 80 <= data.get('percentage', 0) < 100:
                        quota_warnings.append({
                            'metric': metric,
                            'used': data['used'],
                            'limit': data['limit'],
                            'percentage': data['percentage'],
                        })
                
                if quota_warnings:
                    # Send quota warning notification
                    warnings_text = ', '.join([f"{w['metric']} ({w['percentage']:.1f}%)" for w in quota_warnings])
                    
                    TenantNotification.objects.create(
                        tenant=tenant,
                        title='Quota Limits Warning',
                        message=f'You are approaching your quota limits: {warnings_text}. Consider upgrading soon.',
                        notification_type='quota',
                        priority='medium',
                        send_email=False,  # Only push for warnings
                        send_push=True,
                        action_url='/billing/usage',
                        action_text='View Usage',
                        metadata={
                            'quota_warnings': quota_warnings,
                            'usage_data': usage,
                        },
                    )
                    
                    sent_count += 1
                    logger.info(f"Sent quota warning notification to {tenant.name}: {warnings_text}")
            
        except Exception as e:
            failed_count += 1
            error_msg = f"Failed to send quota notification to {tenant.name}: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
    
    result = {
        'sent_count': sent_count,
        'failed_count': failed_count,
        'errors': errors,
        'total_tenants': tenants.count(),
    }
    
    logger.info(f"Quota notifications completed: {result}")
    return result


@shared_task(name='tenants.notifications.send_security_alerts')
def send_security_alerts():
    """
    Send security alerts for suspicious activities.
    
    This task runs hourly to check for security events
    and send alerts to administrators.
    """
    logger.info("Starting security alert sending")
    
    sent_count = 0
    failed_count = 0
    errors = []
    
    # Get recent security events
    from ..models.security import TenantAuditLog
    from datetime import timedelta
    
    recent_events = TenantAuditLog.objects.filter(
        action='security_event',
        created_at__gte=timezone.now() - timedelta(hours=1)
    ).select_related('tenant')
    
    # Group events by tenant
    events_by_tenant = {}
    for event in recent_events:
        tenant_id = event.tenant.id
        if tenant_id not in events_by_tenant:
            events_by_tenant[tenant_id] = {'tenant': event.tenant, 'events': []}
        events_by_tenant[tenant_id]['events'].append(event)
    
    for tenant_id, data in events_by_tenant.items():
        tenant = data['tenant']
        events = data['events']
        
        try:
            # Categorize events by severity
            critical_events = [e for e in events if e.severity == 'critical']
            high_events = [e for e in events if e.severity == 'high']
            
            if critical_events:
                # Send critical security alert
                event_descriptions = [e.description for e in critical_events[:3]]  # Limit to 3
                
                TenantNotification.objects.create(
                    tenant=tenant,
                    title='Critical Security Alert',
                    message=f'Critical security events detected: {"; ".join(event_descriptions)}',
                    notification_type='security',
                    priority='urgent',
                    send_email=True,
                    send_push=True,
                    action_url='/security/audit',
                    action_text='View Security Log',
                    metadata={
                        'event_count': len(critical_events),
                        'event_ids': [str(e.id) for e in critical_events],
                    },
                )
                
                sent_count += 1
                logger.error(f"Sent critical security alert to {tenant.name}: {len(critical_events)} events")
            
            elif high_events:
                # Send high priority security alert
                event_descriptions = [e.description for e in high_events[:3]]  # Limit to 3
                
                TenantNotification.objects.create(
                    tenant=tenant,
                    title='Security Alert',
                    message=f'Security events detected: {"; ".join(event_descriptions)}',
                    notification_type='security',
                    priority='high',
                    send_email=True,
                    send_push=False,  # Only email for high priority
                    action_url='/security/audit',
                    action_text='View Security Log',
                    metadata={
                        'event_count': len(high_events),
                        'event_ids': [str(e.id) for e in high_events],
                    },
                )
                
                sent_count += 1
                logger.warning(f"Sent security alert to {tenant.name}: {len(high_events)} events")
            
        except Exception as e:
            failed_count += 1
            error_msg = f"Failed to send security alert to {tenant.name}: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
    
    result = {
        'sent_count': sent_count,
        'failed_count': failed_count,
        'errors': errors,
        'total_events': recent_events.count(),
        'affected_tenants': len(events_by_tenant),
    }
    
    logger.info(f"Security alerts completed: {result}")
    return result


@shared_task(name='tenants.notifications.process_email_queue')
def process_email_queue():
    """
    Process email queue for sending notifications.
    
    This task runs every 5 minutes to process pending
    email notifications and handle delivery.
    """
    logger.info("Starting email queue processing")
    
    processed_count = 0
    failed_count = 0
    errors = []
    
    # Get pending email notifications
    pending_notifications = TenantNotification.objects.filter(
        send_email=True,
        status='pending'
    ).select_related('tenant')
    
    for notification in pending_notifications:
        try:
            # Get tenant email configuration
            from ..models.branding import TenantEmail
            email_config = notification.tenant.email_config
            
            if not email_config or not email_config.is_verified:
                # Mark as failed if no email config
                notification.status = 'failed'
                notification.save(update_fields=['status'])
                failed_count += 1
                continue
            
            # Send email using tenant's email service
            from ..services import TenantEmailService
            
            result = TenantEmailService.send_email(
                tenant=notification.tenant,
                template_name='notification',
                context_data={
                    'title': notification.title,
                    'message': notification.message,
                    'action_url': notification.action_url,
                    'action_text': notification.action_text,
                },
                recipients=[notification.tenant.owner.email],
                subject=notification.title,
            )
            
            if result['success']:
                notification.status = 'sent'
                notification.sent_at = timezone.now()
                processed_count += 1
                logger.info(f"Sent email notification to {notification.tenant.name}")
            else:
                notification.status = 'failed'
                failed_count += 1
                logger.error(f"Failed to send email to {notification.tenant.name}: {result.get('error')}")
            
            notification.save(update_fields=['status', 'sent_at'])
            
        except Exception as e:
            failed_count += 1
            error_msg = f"Failed to process email notification {notification.id}: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
            
            # Mark as failed
            notification.status = 'failed'
            notification.save(update_fields=['status'])
    
    result = {
        'processed_count': processed_count,
        'failed_count': failed_count,
        'errors': errors,
        'total_pending': pending_notifications.count(),
    }
    
    logger.info(f"Email queue processing completed: {result}")
    return result


@shared_task(name='tenants.notifications.send_welcome_emails')
def send_welcome_emails():
    """
    Send welcome emails to newly created tenants.
    
    This task runs every 30 minutes to send welcome emails
    to tenants that haven't received them yet.
    """
    logger.info("Starting welcome email sending")
    
    sent_count = 0
    failed_count = 0
    errors = []
    
    # Get tenants created in the last 24 hours without welcome emails
    from datetime import timedelta
    recent_tenants = Tenant.objects.filter(
        is_deleted=False,
        created_at__gte=timezone.now() - timedelta(hours=24)
    ).select_related('owner', 'plan')
    
    for tenant in recent_tenants:
        try:
            # Check if welcome email already sent
            welcome_sent = TenantNotification.objects.filter(
                tenant=tenant,
                notification_type='welcome',
                status='sent'
            ).exists()
            
            if not welcome_sent:
                # Send welcome email
                from ..services import TenantEmailService
                
                result = TenantEmailService.send_email(
                    tenant=tenant,
                    template_name='welcome',
                    context_data={
                        'tenant_name': tenant.name,
                        'owner_name': tenant.owner.get_full_name() or tenant.owner.username,
                        'plan_name': tenant.plan.name,
                        'trial_ends_at': tenant.trial_ends_at,
                    },
                    recipients=[tenant.owner.email],
                    subject=f'Welcome to {tenant.plan.name}!',
                )
                
                if result['success']:
                    # Create notification record
                    TenantNotification.objects.create(
                        tenant=tenant,
                        title='Welcome!',
                        message=f'Welcome to {tenant.plan.name}! We\'re excited to have you on board.',
                        notification_type='welcome',
                        priority='medium',
                        send_email=True,
                        send_push=True,
                        status='sent',
                        sent_at=timezone.now(),
                        action_url='/dashboard',
                        action_text='Get Started',
                    )
                    
                    sent_count += 1
                    logger.info(f"Sent welcome email to {tenant.name}")
                else:
                    failed_count += 1
                    logger.error(f"Failed to send welcome email to {tenant.name}: {result.get('error')}")
            
        except Exception as e:
            failed_count += 1
            error_msg = f"Failed to send welcome email to {tenant.name}: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
    
    result = {
        'sent_count': sent_count,
        'failed_count': failed_count,
        'errors': errors,
        'total_recent_tenants': recent_tenants.count(),
    }
    
    logger.info(f"Welcome email sending completed: {result}")
    return result


@shared_task(name='tenants.notifications.cleanup_old_notifications')
def cleanup_old_notifications(days_to_keep=90):
    """
    Clean up old notifications to maintain database performance.
    
    Args:
        days_to_keep (int): Number of days to keep notifications
    """
    logger.info(f"Starting cleanup of notifications older than {days_to_keep} days")
    
    cutoff_date = timezone.now() - timedelta(days=days_to_keep)
    
    # Archive old notifications
    old_notifications = TenantNotification.objects.filter(
        created_at__lt=cutoff_date
    )
    
    archived_count = old_notifications.count()
    
    # This would archive notifications to cold storage
    # For now, just delete old notifications
    old_notifications.delete()
    
    result = {
        'archived_count': archived_count,
        'cutoff_date': cutoff_date.date(),
    }
    
    logger.info(f"Notification cleanup completed: {result}")
    return result
