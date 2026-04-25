"""
Onboarding Service

This service handles tenant onboarding operations including
step tracking, progress monitoring, and user guidance.
"""

from datetime import timedelta
from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from ..models import Tenant
from ..models.onboarding import TenantOnboarding, TenantOnboardingStep, TenantTrialExtension
from ..models.security import TenantAuditLog

User = get_user_model()


class OnboardingService:
    """
    Service class for tenant onboarding operations.
    
    This service handles onboarding workflow management,
    step tracking, and trial extensions.
    """
    
    @staticmethod
    def start_onboarding(tenant, started_by=None):
        """
        Start onboarding process for tenant.
        
        Args:
            tenant (Tenant): Tenant to start onboarding for
            started_by (User): User starting onboarding
            
        Returns:
            TenantOnboarding: Started onboarding instance
        """
        with transaction.atomic():
            onboarding = tenant.onboarding
            onboarding.start_onboarding()
            
            # Mark first step as started
            try:
                first_step = TenantOnboardingStep.objects.get(
                    tenant=tenant,
                    sort_order=0
                )
                first_step.start_step()
            except TenantOnboardingStep.DoesNotExist:
                pass
            
            # Log start
            if started_by:
                TenantAuditLog.log_action(
                    tenant=tenant,
                    action='access',
                    actor=started_by,
                    model_name='TenantOnboarding',
                    object_id=str(onboarding.id),
                    object_repr=str(onboarding),
                    description=f"Onboarding started for {tenant.name}"
                )
            
            return onboarding
    
    @staticmethod
    def complete_step(tenant, step_key, step_data=None, completed_by=None):
        """
        Complete an onboarding step.
        
        Args:
            tenant (Tenant): Tenant
            step_key (str): Step key to complete
            step_data (dict): Step completion data
            completed_by (User): User completing the step
            
        Returns:
            dict: Completion result
        """
        with transaction.atomic():
            try:
                step = TenantOnboardingStep.objects.get(
                    tenant=tenant,
                    step_key=step_key
                )
            except TenantOnboardingStep.DoesNotExist:
                raise ValidationError(f"Onboarding step '{step_key}' not found.")
            
            # Validate step completion
            if not step.validate_completion():
                raise ValidationError("Step validation failed.")
            
            # Complete step
            step.complete_step(step_data)
            
            # Update onboarding progress
            onboarding = tenant.onboarding
            total_steps = TenantOnboardingStep.objects.filter(tenant=tenant).count()
            completed_steps = TenantOnboardingStep.objects.filter(
                tenant=tenant,
                is_done=True
            ).count()
            
            progress = int((completed_steps / total_steps) * 100)
            onboarding.update_progress(step_key, progress - onboarding.completion_pct)
            
            # Get next step
            next_step = TenantOnboardingStep.objects.filter(
                tenant=tenant,
                sort_order__gt=step.sort_order
            ).order_by('sort_order').first()
            
            if next_step:
                next_step.start_step()
                onboarding.current_step = next_step.step_key
                onboarding.save(update_fields=['current_step'])
            
            # Check if onboarding is complete
            if progress >= 100:
                onboarding.complete_onboarding()
            
            # Log completion
            if completed_by:
                TenantAuditLog.log_action(
                    tenant=tenant,
                    action='update',
                    actor=completed_by,
                    model_name='TenantOnboardingStep',
                    object_id=str(step.id),
                    object_repr=str(step),
                    description=f"Onboarding step '{step.label}' completed",
                    metadata={
                        'step_key': step_key,
                        'progress': progress,
                        'time_spent': step.time_spent_seconds,
                    }
                )
            
            return {
                'success': True,
                'message': f"Step '{step.label}' completed successfully",
                'step': {
                    'key': step.step_key,
                    'label': step.label,
                    'time_spent': step.time_spent_display,
                },
                'progress': progress,
                'next_step': {
                    'key': next_step.step_key,
                    'label': next_step.label,
                } if next_step else None,
                'is_complete': progress >= 100,
            }
    
    @staticmethod
    def skip_step(tenant, step_key, reason=None, skipped_by=None):
        """
        Skip an onboarding step.
        
        Args:
            tenant (Tenant): Tenant
            step_key (str): Step key to skip
            reason (str): Reason for skipping
            skipped_by (User): User skipping the step
            
        Returns:
            dict: Skip result
        """
        with transaction.atomic():
            try:
                step = TenantOnboardingStep.objects.get(
                    tenant=tenant,
                    step_key=step_key
                )
            except TenantOnboardingStep.DoesNotExist:
                raise ValidationError(f"Onboarding step '{step_key}' not found.")
            
            if not step.can_skip:
                raise ValidationError(f"Step '{step.label}' cannot be skipped.")
            
            # Skip step
            step.skip_step(reason)
            
            # Update onboarding
            onboarding = tenant.onboarding
            onboarding.skip_step(step_key)
            
            # Get next step
            next_step = TenantOnboardingStep.objects.filter(
                tenant=tenant,
                sort_order__gt=step.sort_order
            ).order_by('sort_order').first()
            
            if next_step:
                next_step.start_step()
                onboarding.current_step = next_step.step_key
                onboarding.save(update_fields=['current_step'])
            
            # Log skip
            if skipped_by:
                TenantAuditLog.log_action(
                    tenant=tenant,
                    action='update',
                    actor=skipped_by,
                    model_name='TenantOnboardingStep',
                    object_id=str(step.id),
                    object_repr=str(step),
                    description=f"Onboarding step '{step.label}' skipped",
                    metadata={
                        'step_key': step_key,
                        'reason': reason,
                    }
                )
            
            return {
                'success': True,
                'message': f"Step '{step.label}' skipped",
                'step': {
                    'key': step.step_key,
                    'label': step.label,
                },
                'next_step': {
                    'key': next_step.step_key,
                    'label': next_step.label,
                } if next_step else None,
            }
    
    @staticmethod
    def request_trial_extension(tenant, days, reason, requested_by=None):
        """
        Request trial extension for tenant.
        
        Args:
            tenant (Tenant): Tenant requesting extension
            days (int): Number of additional days requested
            reason (str): Reason for extension
            requested_by (User): User requesting extension
            
        Returns:
            TenantTrialExtension: Created trial extension request
        """
        with transaction.atomic():
            # Validate request
            if not tenant.trial_ends_at:
                raise ValidationError("Tenant does not have an active trial.")
            
            if tenant.is_trial_expired:
                raise ValidationError("Trial has already expired.")
            
            if days <= 0 or days > 90:
                raise ValidationError("Extension days must be between 1 and 90.")
            
            # Create trial extension request
            extension = TenantTrialExtension.objects.create(
                tenant=tenant,
                days_extended=days,
                reason=reason,
                reason_details=reason,
                original_trial_end=tenant.trial_ends_at,
            )
            
            # Log request
            if requested_by:
                TenantAuditLog.log_action(
                    tenant=tenant,
                    action='config_change',
                    actor=requested_by,
                    model_name='TenantTrialExtension',
                    object_id=str(extension.id),
                    object_repr=str(extension),
                    description=f"Trial extension requested: {days} days",
                    metadata={
                        'days': days,
                        'reason': reason,
                    }
                )
            
            # Send notification to admin
            OnboardingService._notify_trial_extension_request(extension)
            
            return extension
    
    @staticmethod
    def _notify_trial_extension_request(extension):
        """Notify admin about trial extension request."""
        from ..models.analytics import TenantNotification
        
        TenantNotification.objects.create(
            tenant=extension.tenant,
            title=_('Trial Extension Request'),
            message=_(
                f'Trial extension requested for {extension.days_extended} days. '
                f'Reason: {extension.reason}'
            ),
            notification_type='system',
            priority='medium',
            send_email=True,
            action_url='/admin/tenants/trial-extensions',
            action_text=_('Review Request'),
        )
    
    @staticmethod
    def approve_trial_extension(extension, approved_by, notes=None):
        """
        Approve trial extension request.
        
        Args:
            extension (TenantTrialExtension): Extension to approve
            approved_by (User): User approving extension
            notes (str): Approval notes
            
        Returns:
            dict: Approval result
        """
        with transaction.atomic():
            extension.approve(approved_by, notes)
            
            # Log approval
            TenantAuditLog.log_action(
                tenant=extension.tenant,
                action='config_change',
                actor=approved_by,
                model_name='TenantTrialExtension',
                object_id=str(extension.id),
                object_repr=str(extension),
                description=f"Trial extension approved: {extension.days_extended} days",
                metadata={
                    'days': extension.days_extended,
                    'new_trial_end': extension.new_trial_end.isoformat(),
                }
            )
            
            # Send notification to tenant
            OnboardingService._notify_trial_extension_approved(extension)
            
            return {
                'success': True,
                'message': f"Trial extension approved for {extension.days_extended} days",
                'new_trial_end': extension.new_trial_end,
            }
    
    @staticmethod
    def _notify_trial_extension_approved(extension):
        """Notify tenant about approved trial extension."""
        from ..models.analytics import TenantNotification
        
        TenantNotification.objects.create(
            tenant=extension.tenant,
            title=_('Trial Extended'),
            message=_(
                f'Your trial has been extended by {extension.days_extended} days. '
                f'New trial end date: {extension.new_trial_end.strftime("%B %d, %Y")}'
            ),
            notification_type='system',
            priority='medium',
            send_email=True,
            send_push=True,
            action_url='/dashboard',
            action_text=_('Continue Setup'),
        )
    
    @staticmethod
    def get_onboarding_progress(tenant):
        """
        Get comprehensive onboarding progress for tenant.
        
        Args:
            tenant (Tenant): Tenant to get progress for
            
        Returns:
            dict: Onboarding progress information
        """
        onboarding = tenant.onboarding
        steps = TenantOnboardingStep.objects.filter(tenant=tenant).order_by('sort_order')
        
        progress_data = {
            'tenant_id': str(tenant.id),
            'tenant_name': tenant.name,
            'onboarding': {
                'status': onboarding.status,
                'completion_pct': onboarding.completion_pct,
                'current_step': onboarding.current_step,
                'started_at': onboarding.started_at,
                'completed_at': onboarding.completed_at,
                'days_since_start': onboarding.days_since_start,
                'needs_attention': onboarding.needs_attention,
            },
            'steps': [],
            'summary': {
                'total_steps': steps.count(),
                'completed_steps': steps.filter(is_done=True).count(),
                'skipped_steps': steps.filter(status='skipped').count(),
                'in_progress_steps': steps.filter(status='in_progress').count(),
                'not_started_steps': steps.filter(status='not_started').count(),
            },
        }
        
        # Add step details
        for step in steps:
            step_data = {
                'key': step.step_key,
                'label': step.label,
                'description': step.description,
                'status': step.status,
                'is_done': step.is_done,
                'is_required': step.is_required,
                'can_skip': step.can_skip,
                'sort_order': step.sort_order,
                'time_spent': step.time_spent_display,
                'started_at': step.started_at,
                'done_at': step.done_at,
                'help_text': step.help_text,
                'video_url': step.video_url,
                'documentation_url': step.documentation_url,
            }
            progress_data['steps'].append(step_data)
        
        return progress_data
    
    @staticmethod
    def get_onboarding_recommendations(tenant):
        """
        Get personalized onboarding recommendations for tenant.
        
        Args:
            tenant (Tenant): Tenant to get recommendations for
            
        Returns:
            list: List of recommendations
        """
        onboarding = tenant.onboarding
        recommendations = []
        
        # Check for stuck onboarding
        if onboarding.needs_attention:
            recommendations.append({
                'type': 'attention',
                'priority': 'high',
                'title': 'Onboarding Needs Attention',
                'description': f"Your onboarding has been inactive for {onboarding.days_since_start} days.",
                'action': 'Continue Onboarding',
                'action_url': '/onboarding',
            })
        
        # Check for skipped required steps
        skipped_required = TenantOnboardingStep.objects.filter(
            tenant=tenant,
            is_required=True,
            status='skipped'
        )
        
        if skipped_required.exists():
            recommendations.append({
                'type': 'required_steps',
                'priority': 'medium',
                'title': 'Complete Required Steps',
                'description': f"You have {skipped_required.count()} required steps that were skipped.",
                'action': 'Complete Steps',
                'action_url': '/onboarding',
            })
        
        # Check trial expiry
        if tenant.trial_ends_at and tenant.days_until_trial_expiry <= 7:
            recommendations.append({
                'type': 'trial_expiry',
                'priority': 'high',
                'title': 'Trial Expiring Soon',
                'description': f"Your trial expires in {tenant.days_until_trial_expiry} days.",
                'action': 'Upgrade Plan',
                'action_url': '/billing/plans',
            })
        
        # Check for incomplete profile
        if not tenant.contact_phone:
            recommendations.append({
                'type': 'profile_completion',
                'priority': 'low',
                'title': 'Complete Your Profile',
                'description': 'Add your phone number to complete your profile.',
                'action': 'Update Profile',
                'action_url': '/settings/profile',
            })
        
        return recommendations
    
    @staticmethod
    def get_onboarding_analytics():
        """
        Get onboarding analytics for all tenants.
        
        Returns:
            dict: Onboarding analytics
        """
        from django.db.models import Count, Avg, Q
        from django.utils import timezone
        from datetime import timedelta
        
        # Get overall statistics
        total_onboardings = TenantOnboarding.objects.count()
        completed_onboardings = TenantOnboarding.objects.filter(status='completed').count()
        active_onboardings = TenantOnboarding.objects.filter(status='in_progress').count()
        
        # Average completion time
        completed = TenantOnboarding.objects.filter(
            status='completed',
            started_at__isnull=False,
            completed_at__isnull=False
        )
        
        avg_completion_days = 0
        if completed.exists():
            completion_times = [
                (comp.completed_at - comp.started_at).days
                for comp in completed
            ]
            avg_completion_days = sum(completion_times) / len(completion_times)
        
        # Step completion rates
        steps = TenantOnboardingStep.objects.all()
        step_stats = {}
        
        for step in steps:
            completed = steps.filter(step_key=step.step_key, is_done=True).count()
            total = steps.filter(step_key=step.step_key).count()
            step_stats[step.step_key] = {
                'label': step.label,
                'completed': completed,
                'total': total,
                'completion_rate': (completed / total * 100) if total > 0 else 0,
            }
        
        analytics = {
            'overview': {
                'total_onboardings': total_onboardings,
                'completed_onboardings': completed_onboardings,
                'active_onboardings': active_onboardings,
                'completion_rate': (completed_onboardings / total_onboardings * 100) if total_onboardings > 0 else 0,
                'avg_completion_days': round(avg_completion_days, 2),
            },
            'step_completion_rates': step_stats,
            'recent_activity': {
                'started_today': TenantOnboarding.objects.filter(
                    started_at__date=timezone.now().date()
                ).count(),
                'completed_today': TenantOnboarding.objects.filter(
                    completed_at__date=timezone.now().date()
                ).count(),
            },
        }
        
        return analytics
