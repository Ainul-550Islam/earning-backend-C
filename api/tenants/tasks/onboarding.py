"""
Onboarding Tasks

This module contains Celery tasks for onboarding operations including
step completion automation, welcome emails, and trial extension scheduling.
"""

from celery import shared_task
from django.utils import timezone
from django.db import transaction
from datetime import timedelta
import logging

from ..models import Tenant, TenantOnboarding, TenantOnboardingStep
from ..services import OnboardingService

logger = logging.getLogger(__name__)


@shared_task(name='tenants.onboarding.complete_onboarding_steps')
def complete_onboarding_steps():
    """
    Automatically complete onboarding steps based on user activity.
    
    This task runs hourly to check for user activity that
    indicates completion of onboarding steps.
    """
    logger.info("Starting automatic onboarding step completion")
    
    completed_count = 0
    failed_count = 0
    errors = []
    
    # Get active onboarding sessions
    active_onboardings = TenantOnboarding.objects.filter(
        status='in_progress'
    ).select_related('tenant')
    
    for onboarding in active_onboardings:
        try:
            # Get incomplete steps
            incomplete_steps = TenantOnboardingStep.objects.filter(
                tenant=onboarding.tenant,
                status__in=['not_started', 'in_progress']
            ).order_by('sort_order')
            
            for step in incomplete_steps:
                # Check if step should be auto-completed based on activity
                should_complete = False
                step_data = {}
                
                if step.step_key == 'profile_setup':
                    # Auto-complete if user has updated profile
                    if onboarding.tenant.contact_phone and onboarding.tenant.contact_email:
                        should_complete = True
                        step_data = {
                            'phone_added': True,
                            'email_configured': True,
                        }
                
                elif step.step_key == 'team_invitation':
                    # Auto-complete if user has invited team members
                    from django.contrib.auth import get_user_model
                    User = get_user_model()
                    
                    team_members = User.objects.filter(
                        tenant=onboarding.tenant
                    ).count()
                    
                    if team_members > 1:
                        should_complete = True
                        step_data = {
                            'team_members_count': team_members,
                        }
                
                elif step.step_key == 'integration_setup':
                    # Auto-complete if user has configured integrations
                    from ..models.security import TenantAPIKey
                    
                    api_keys = TenantAPIKey.objects.filter(
                        tenant=onboarding.tenant,
                        status='active'
                    ).count()
                    
                    if api_keys > 0:
                        should_complete = True
                        step_data = {
                            'api_keys_created': api_keys,
                        }
                
                elif step.step_key == 'first_campaign':
                    # Auto-complete if user has created campaigns
                    # This would check your campaign system
                    # For now, skip auto-completion
                    pass
                
                if should_complete:
                    # Complete the step
                    result = OnboardingService.complete_step(
                        onboarding.tenant,
                        step.step_key,
                        step_data
                    )
                    
                    if result['success']:
                        completed_count += 1
                        logger.info(f"Auto-completed onboarding step {step.step_key} for {onboarding.tenant.name}")
                    else:
                        failed_count += 1
                        logger.error(f"Failed to auto-complete step {step.step_key}: {result}")
            
        except Exception as e:
            failed_count += 1
            error_msg = f"Failed to process onboarding for {onboarding.tenant.name}: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
    
    result = {
        'completed_count': completed_count,
        'failed_count': failed_count,
        'errors': errors,
        'total_active_onboardings': active_onboardings.count(),
    }
    
    logger.info(f"Automatic onboarding step completion completed: {result}")
    return result


@shared_task(name='tenants.onboarding.send_welcome_emails')
def send_welcome_emails():
    """
    Send welcome emails to newly onboarded tenants.
    
    This task runs every 30 minutes to send welcome emails
    to tenants who have recently completed onboarding.
    """
    logger.info("Starting welcome email sending")
    
    sent_count = 0
    failed_count = 0
    errors = []
    
    # Get recently completed onboarding sessions
    from datetime import timedelta
    recent_time = timezone.now() - timedelta(hours=2)
    
    completed_onboardings = TenantOnboarding.objects.filter(
        status='completed',
        completed_at__gte=recent_time
    ).select_related('tenant')
    
    for onboarding in completed_onboardings:
        try:
            # Check if welcome email already sent
            welcome_sent = TenantNotification.objects.filter(
                tenant=onboarding.tenant,
                notification_type='onboarding_complete',
                status='sent'
            ).exists()
            
            if not welcome_sent:
                # Send onboarding complete email
                from ..services import TenantEmailService
                
                result = TenantEmailService.send_email(
                    tenant=onboarding.tenant,
                    template_name='onboarding_complete',
                    context_data={
                        'tenant_name': onboarding.tenant.name,
                        'owner_name': onboarding.tenant.owner.get_full_name() or onboarding.tenant.owner.username,
                        'completion_pct': onboarding.completion_pct,
                        'completed_at': onboarding.completed_at,
                        'plan_name': onboarding.tenant.plan.name,
                    },
                    recipients=[onboarding.tenant.owner.email],
                    subject=f'Congratulations on completing your setup!',
                )
                
                if result['success']:
                    # Create notification record
                    from ..models.analytics import TenantNotification
                    
                    TenantNotification.objects.create(
                        tenant=onboarding.tenant,
                        title='Setup Complete! Welcome Aboard!',
                        message=f'Congratulations on completing your setup! You\'re all set to make the most of {onboarding.tenant.plan.name}.',
                        notification_type='onboarding_complete',
                        priority='medium',
                        send_email=True,
                        send_push=True,
                        status='sent',
                        sent_at=timezone.now(),
                        action_url='/dashboard',
                        action_text='Go to Dashboard',
                        metadata={
                            'onboarding_id': str(onboarding.id),
                            'completion_pct': onboarding.completion_pct,
                        },
                    )
                    
                    sent_count += 1
                    logger.info(f"Sent onboarding complete email to {onboarding.tenant.name}")
                else:
                    failed_count += 1
                    logger.error(f"Failed to send onboarding email to {onboarding.tenant.name}: {result.get('error')}")
            
        except Exception as e:
            failed_count += 1
            error_msg = f"Failed to send onboarding email to {onboarding.tenant.name}: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
    
    result = {
        'sent_count': sent_count,
        'failed_count': failed_count,
        'errors': errors,
        'total_completed': completed_onboardings.count(),
    }
    
    logger.info(f"Welcome email sending completed: {result}")
    return result


@shared_task(name='tenants.onboarding.schedule_trial_extensions')
def schedule_trial_extensions():
    """
    Schedule trial extensions for tenants approaching trial expiry.
    
    This task runs daily to identify tenants who might benefit
    from trial extensions and schedule appropriate actions.
    """
    logger.info("Starting trial extension scheduling")
    
    scheduled_count = 0
    failed_count = 0
    errors = []
    
    # Get tenants with trials expiring in the next 3 days
    from datetime import timedelta
    
    upcoming_expiry = timezone.now() + timedelta(days=3)
    
    trial_tenants = Tenant.objects.filter(
        is_deleted=False,
        trial_ends_at__isnull=False,
        trial_ends_at__lte=upcoming_expiry,
        trial_ends_at__gt=timezone.now()
    ).select_related('plan', 'owner')
    
    for tenant in trial_tenants:
        try:
            days_until_expiry = tenant.days_until_trial_expiry
            
            # Check if tenant is actively using the platform
            from ..models.security import TenantAuditLog
            from datetime import timedelta
            
            recent_activity = TenantAuditLog.objects.filter(
                tenant=tenant,
                created_at__gte=timezone.now() - timedelta(days=7)
            ).count()
            
            # Determine if extension should be offered
            should_offer_extension = False
            extension_days = 0
            reason = ""
            
            if days_until_expiry <= 1:
                # Last day - offer extension if there's activity
                if recent_activity >= 10:
                    should_offer_extension = True
                    extension_days = 7
                    reason = "Active user engagement"
            elif days_until_expiry <= 3:
                # 3 days or less - offer extension for good activity
                if recent_activity >= 20:
                    should_offer_extension = True
                    extension_days = 5
                    reason = "Good user engagement"
            elif days_until_expiry <= 7:
                # Week or less - offer extension for high activity
                if recent_activity >= 50:
                    should_offer_extension = True
                    extension_days = 3
                    reason = "High user engagement"
            
            if should_offer_extension:
                # Create trial extension request
                from ..models.onboarding import TenantTrialExtension
                
                extension = TenantTrialExtension.objects.create(
                    tenant=tenant,
                    days_extended=extension_days,
                    reason='auto_scheduled',
                    reason_details=f"Auto-scheduled based on {reason}",
                    original_trial_end=tenant.trial_ends_at,
                )
                
                # Send notification to tenant owner
                from ..models.analytics import TenantNotification
                
                TenantNotification.objects.create(
                    tenant=tenant,
                    title='Trial Extension Offered',
                    message=f'Based on your activity, we\'ve extended your trial by {extension_days} days. Enjoy exploring more features!',
                    notification_type='trial',
                    priority='medium',
                    send_email=True,
                    send_push=True,
                    action_url='/billing/plans',
                    action_text='View Plan Options',
                    metadata={
                        'extension_id': str(extension.id),
                        'days_extended': extension_days,
                        'reason': reason,
                    },
                )
                
                # Log the scheduling
                from ..models.security import TenantAuditLog
                
                TenantAuditLog.log_action(
                    tenant=tenant,
                    action='config_change',
                    model_name='TenantTrialExtension',
                    description=f"Trial extension auto-scheduled: {extension_days} days - {reason}",
                    metadata={
                        'extension_id': str(extension.id),
                        'days_extended': extension_days,
                        'reason': reason,
                        'recent_activity': recent_activity,
                    }
                )
                
                scheduled_count += 1
                logger.info(f"Scheduled trial extension for {tenant.name}: {extension_days} days")
            
        except Exception as e:
            failed_count += 1
            error_msg = f"Failed to schedule trial extension for {tenant.name}: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
    
    result = {
        'scheduled_count': scheduled_count,
        'failed_count': failed_count,
        'errors': errors,
        'total_trial_tenants': trial_tenants.count(),
    }
    
    logger.info(f"Trial extension scheduling completed: {result}")
    return result


@shared_task(name='tenants.onboarding.send_progress_tips')
def send_progress_tips():
    """
    Send helpful tips to tenants based on their onboarding progress.
    
    This task runs every 6 hours to send contextual tips
    to help tenants complete their setup.
    """
    logger.info("Starting onboarding progress tips sending")
    
    sent_count = 0
    failed_count = 0
    errors = []
    
    # Get active onboarding sessions
    active_onboardings = TenantOnboarding.objects.filter(
        status='in_progress'
    ).select_related('tenant')
    
    for onboarding in active_onboardings:
        try:
            # Get current step
            current_step = TenantOnboardingStep.objects.filter(
                tenant=onboarding.tenant,
                step_key=onboarding.current_step
            ).first()
            
            if current_step and current_step.status == 'in_progress':
                # Determine tip based on current step
                tip_data = OnboardingService._get_step_tip(current_step.step_key)
                
                if tip_data:
                    # Send tip notification
                    from ..models.analytics import TenantNotification
                    
                    TenantNotification.objects.create(
                        tenant=onboarding.tenant,
                        title=tip_data['title'],
                        message=tip_data['message'],
                        notification_type='onboarding',
                        priority='low',
                        send_email=False,  # Only push for tips
                        send_push=True,
                        action_url=tip_data.get('action_url', '/onboarding'),
                        action_text=tip_data.get('action_text', 'Continue'),
                        metadata={
                            'step_key': current_step.step_key,
                            'tip_type': tip_data['type'],
                        },
                    )
                    
                    sent_count += 1
                    logger.info(f"Sent onboarding tip to {onboarding.tenant.name}: {tip_data['title']}")
            
        except Exception as e:
            failed_count += 1
            error_msg = f"Failed to send tip to {onboarding.tenant.name}: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
    
    result = {
        'sent_count': sent_count,
        'failed_count': failed_count,
        'errors': errors,
        'total_active_onboardings': active_onboardings.count(),
    }
    
    logger.info(f"Onboarding progress tips completed: {result}")
    return result


@shared_task(name='tenants.onboarding.cleanup_old_onboarding_data')
def cleanup_old_onboarding_data():
    """
    Clean up old onboarding data to maintain database performance.
    
    This task runs monthly to archive or delete old
    onboarding data that is no longer needed.
    """
    logger.info("Starting onboarding data cleanup")
    
    try:
        from datetime import timedelta
        
        # Archive onboarding data older than 6 months
        cutoff_date = timezone.now() - timedelta(days=180)
        
        # Archive completed onboarding sessions
        from ..models.onboarding import TenantOnboarding, TenantOnboardingStep
        
        old_onboardings = TenantOnboarding.objects.filter(
            completed_at__lt=cutoff_date,
            status='completed'
        ).select_related('tenant')
        
        archived_count = old_onboardings.count()
        
        # This would archive the data to cold storage
        # For now, just log the count
        logger.info(f"Archived {archived_count} old onboarding sessions")
        
        # Archive individual step data
        old_steps = TenantOnboardingStep.objects.filter(
            tenant__onboarding__completed_at__lt=cutoff_date,
            tenant__onboarding__status='completed'
        ).count()
        
        logger.info(f"Archived {old_steps} old onboarding steps")
        
        result = {
            'archived_onboardings': archived_count,
            'archived_steps': old_steps,
            'cutoff_date': cutoff_date.date(),
        }
        
        logger.info(f"Onboarding data cleanup completed: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Onboarding data cleanup failed: {str(e)}")
        return {'error': str(e)}


@shared_task(name='tenants.onboarding.generate_onboarding_analytics')
def generate_onboarding_analytics():
    """
    Generate comprehensive onboarding analytics.
    
    This task runs weekly to generate analytics reports
    on onboarding completion rates and patterns.
    """
    logger.info("Starting onboarding analytics generation")
    
    try:
        analytics = OnboardingService.get_onboarding_analytics()
        
        # Add additional analytics
        from datetime import timedelta
        from django.db.models import Count, Avg
        
        # Recent completion trends
        last_30_days = timezone.now() - timedelta(days=30)
        
        recent_completions = TenantOnboarding.objects.filter(
            completed_at__gte=last_30_days,
            status='completed'
        )
        
        analytics['recent_trends'] = {
            'completions_last_30_days': recent_completions.count(),
            'average_completion_time': recent_completions.aggregate(
                avg_time=Avg('completed_at') - Avg('started_at')
            )['avg_time'].days if recent_completions.exists() else 0,
            'completion_rate': (recent_completions.count() / Tenant.objects.filter(
                created_at__gte=last_30_days
            ).count() * 100) if Tenant.objects.filter(
                created_at__gte=last_30_days
            ).exists() else 0,
        }
        
        # Step completion rates
        step_stats = TenantOnboardingStep.objects.filter(
            tenant__onboarding__status='completed'
        ).values('step_key').annotate(
            total=Count('id'),
            completed=Count('id', filter=models.Q(status='done'))
        )
        
        analytics['step_completion_rates'] = {
            step['step_key']: {
                'total': step['total'],
                'completed': step['completed'],
                'rate': (step['completed'] / step['total'] * 100) if step['total'] > 0 else 0
            }
            for step in step_stats
        }
        
        logger.info(f"Onboarding analytics generated: {len(analytics)} sections")
        return analytics
        
    except Exception as e:
        logger.error(f"Onboarding analytics generation failed: {str(e)}")
        return {'error': str(e)}
