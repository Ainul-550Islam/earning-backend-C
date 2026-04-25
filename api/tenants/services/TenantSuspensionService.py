"""
Tenant Suspension Service

This service handles tenant suspension, unsuspension,
and related operations for managing tenant access.
"""

from datetime import timedelta
from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from ..models import Tenant
from ..models.security import TenantAPIKey, TenantAuditLog
from ..models.analytics import TenantNotification

User = get_user_model()


class TenantSuspensionService:
    """
    Service class for tenant suspension operations.
    
    This service handles tenant suspension, unsuspension,
    and related compliance operations.
    """
    
    SUSPENSION_REASONS = [
        ('payment_overdue', _('Payment Overdue')),
        ('policy_violation', _('Policy Violation')),
        ('abuse', _('Abuse')),
        ('security_breach', _('Security Breach')),
        ('compliance', _('Compliance Issue')),
        ('maintenance', _('Maintenance')),
        ('manual', _('Manual Suspension')),
        ('other', _('Other')),
    ]
    
    @staticmethod
    def suspend_tenant(tenant, reason, suspended_by=None, notify=True, auto_unsuspend_at=None):
        """
        Suspend a tenant with detailed logging and notifications.
        
        Args:
            tenant (Tenant): Tenant to suspend
            reason (str): Reason for suspension
            suspended_by (User): User suspending the tenant
            notify (bool): Whether to send notifications
            auto_unsuspend_at (datetime): When to automatically unsuspend
            
        Returns:
            dict: Suspension result
            
        Raises:
            ValidationError: If tenant cannot be suspended
        """
        with transaction.atomic():
            # Check if tenant is already suspended
            if tenant.is_suspended:
                raise ValidationError(_('Tenant is already suspended.'))
            
            # Log suspension
            if suspended_by:
                TenantAuditLog.log_security_event(
                    tenant=tenant,
                    description=f"Tenant suspended: {reason}",
                    severity='high',
                    actor=suspended_by,
                    ip_address=getattr(suspended_by, 'last_login_ip', None),
                    metadata={
                        'reason': reason,
                        'auto_unsuspend_at': auto_unsuspend_at.isoformat() if auto_unsuspend_at else None,
                    }
                )
            
            # Suspend tenant
            tenant.suspend(reason)
            
            # Suspend API keys
            TenantSuspensionService._suspend_api_keys(tenant)
            
            # Create suspension notification
            if notify:
                TenantSuspensionService._create_suspension_notification(tenant, reason)
            
            # Schedule auto-unsuspension if requested
            if auto_unsuspend_at:
                TenantSuspensionService._schedule_auto_unsuspend(tenant, auto_unsuspend_at)
            
            # Send notifications
            if notify:
                TenantSuspensionService._send_suspension_notifications(tenant, reason, suspended_by)
            
            return {
                'success': True,
                'message': f'Tenant {tenant.name} suspended successfully',
                'suspended_at': tenant.suspended_at,
                'auto_unsuspend_at': auto_unsuspend_at,
            }
    
    @staticmethod
    def _suspend_api_keys(tenant):
        """Suspend all API keys for the tenant."""
        api_keys = TenantAPIKey.objects.filter(
            tenant=tenant,
            status='active'
        )
        
        for api_key in api_keys:
            api_key.status = 'suspended'
            api_key.save(update_fields=['status'])
    
    @staticmethod
    def _create_suspension_notification(tenant, reason):
        """Create in-app suspension notification."""
        TenantNotification.objects.create(
            tenant=tenant,
            title=_('Account Suspended'),
            message=_(
                f'Your account has been suspended. Reason: {reason}. '
                f'Please contact support for assistance.'
            ),
            notification_type='security',
            priority='high',
            send_email=True,
            send_push=True,
            action_url='/support',
            action_text=_('Contact Support'),
        )
    
    @staticmethod
    def _schedule_auto_unsuspend(tenant, auto_unsuspend_at):
        """Schedule automatic unsuspension."""
        # This would integrate with your task scheduler (Celery, etc.)
        # For now, just store in metadata
        tenant.metadata['auto_unsuspend_at'] = auto_unsuspend_at.isoformat()
        tenant.save(update_fields=['metadata'])
    
    @staticmethod
    def _send_suspension_notifications(tenant, reason, suspended_by=None):
        """Send suspension notifications to relevant parties."""
        # Send to tenant owner
        TenantSuspensionService._send_suspension_email_to_owner(tenant, reason)
        
        # Send to admin team
        TenantSuspensionService._send_suspension_email_to_admins(tenant, reason, suspended_by)
        
        # Trigger webhooks
        TenantSuspensionService._trigger_suspension_webhooks(tenant, reason)
    
    @staticmethod
    def _send_suspension_email_to_owner(tenant, reason):
        """Send suspension email to tenant owner."""
        # This would integrate with your email service
        # Implementation depends on your email system
        pass
    
    @staticmethod
    def _send_suspension_email_to_admins(tenant, reason, suspended_by):
        """Send suspension email to admin team."""
        # This would integrate with your email service
        # Implementation depends on your email system
        pass
    
    @staticmethod
    def _trigger_suspension_webhooks(tenant, reason):
        """Trigger suspension webhooks."""
        from ..models.security import TenantWebhookConfig
        
        webhooks = TenantWebhookConfig.objects.filter(
            tenant=tenant,
            is_active=True
        )
        
        for webhook in webhooks:
            if webhook.can_send_event('tenant.suspended'):
                # This would trigger the webhook
                # Implementation depends on your webhook system
                pass
    
    @staticmethod
    def unsuspend_tenant(tenant, unsuspended_by=None, notify=True):
        """
        Unsuspend a tenant with detailed logging and notifications.
        
        Args:
            tenant (Tenant): Tenant to unsuspend
            unsuspended_by (User): User unsuspending the tenant
            notify (bool): Whether to send notifications
            
        Returns:
            dict: Unsuspension result
            
        Raises:
            ValidationError: If tenant is not suspended
        """
        with transaction.atomic():
            # Check if tenant is suspended
            if not tenant.is_suspended:
                raise ValidationError(_('Tenant is not currently suspended.'))
            
            # Log unsuspension
            if unsuspended_by:
                TenantAuditLog.log_security_event(
                    tenant=tenant,
                    description=f"Tenant unsuspended by {unsuspended_by.get_full_name() or unsuspended_by.email}",
                    severity='medium',
                    actor=unsuspended_by,
                    ip_address=getattr(unsuspended_by, 'last_login_ip', None),
                )
            
            # Unsuspend tenant
            tenant.unsuspend()
            
            # Reactivate API keys
            TenantSuspensionService._reactivate_api_keys(tenant)
            
            # Clear auto-unsuspend schedule
            if 'auto_unsuspend_at' in tenant.metadata:
                del tenant.metadata['auto_unsuspend_at']
                tenant.save(update_fields=['metadata'])
            
            # Create unsuspension notification
            if notify:
                TenantSuspensionService._create_unsuspension_notification(tenant)
            
            # Send notifications
            if notify:
                TenantSuspensionService._send_unsuspension_notifications(tenant, unsuspended_by)
            
            return {
                'success': True,
                'message': f'Tenant {tenant.name} unsuspended successfully',
                'unsuspended_at': timezone.now(),
            }
    
    @staticmethod
    def _reactivate_api_keys(tenant):
        """Reactivate suspended API keys for the tenant."""
        api_keys = TenantAPIKey.objects.filter(
            tenant=tenant,
            status='suspended'
        )
        
        for api_key in api_keys:
            api_key.status = 'active'
            api_key.save(update_fields=['status'])
    
    @staticmethod
    def _create_unsuspension_notification(tenant):
        """Create in-app unsuspension notification."""
        TenantNotification.objects.create(
            tenant=tenant,
            title=_('Account Reactivated'),
            message=_('Your account has been reactivated. You can now access all services.'),
            notification_type='system',
            priority='medium',
            send_email=True,
            send_push=True,
            action_url='/dashboard',
            action_text=_('Go to Dashboard'),
        )
    
    @staticmethod
    def _send_unsuspension_notifications(tenant, unsuspended_by=None):
        """Send unsuspension notifications to relevant parties."""
        # Send to tenant owner
        TenantSuspensionService._send_unsuspension_email_to_owner(tenant)
        
        # Send to admin team
        if unsuspended_by:
            TenantSuspensionService._send_unsuspension_email_to_admins(tenant, unsuspended_by)
        
        # Trigger webhooks
        TenantSuspensionService._trigger_unsuspension_webhooks(tenant)
    
    @staticmethod
    def _send_unsuspension_email_to_owner(tenant):
        """Send unsuspension email to tenant owner."""
        # This would integrate with your email service
        # Implementation depends on your email system
        pass
    
    @staticmethod
    def _send_unsuspension_email_to_admins(tenant, unsuspended_by):
        """Send unsuspension email to admin team."""
        # This would integrate with your email service
        # Implementation depends on your email system
        pass
    
    @staticmethod
    def _trigger_unsuspension_webhooks(tenant):
        """Trigger unsuspension webhooks."""
        from ..models.security import TenantWebhookConfig
        
        webhooks = TenantWebhookConfig.objects.filter(
            tenant=tenant,
            is_active=True
        )
        
        for webhook in webhooks:
            if webhook.can_send_event('tenant.unsuspended'):
                # This would trigger the webhook
                # Implementation depends on your webhook system
                pass
    
    @staticmethod
    def check_auto_unsuspend():
        """
        Check for tenants that should be automatically unsuspended.
        
        This method should be called periodically (e.g., via cron job)
        to handle automatic unsuspensions.
        
        Returns:
            list: List of unsuspending tenants
        """
        from django.db.models import Q
        
        # Find tenants with auto-unsuspend scheduled
        now = timezone.now()
        tenants_to_unsuspend = Tenant.objects.filter(
            Q(is_suspended=True) &
            Q(metadata__auto_unsuspend_at__isnull=False) &
            Q(metadata__auto_unsuspend_at__lte=now.isoformat())
        )
        
        unsuspending_tenants = []
        
        for tenant in tenants_to_unsuspend:
            try:
                result = TenantSuspensionService.unsuspend_tenant(
                    tenant,
                    unsuspended_by=None,  # System action
                    notify=True
                )
                unsuspending_tenants.append({
                    'tenant': tenant,
                    'result': result
                })
            except Exception as e:
                # Log error but continue with other tenants
                TenantAuditLog.log_security_event(
                    tenant=tenant,
                    description=f"Failed to auto-unsuspend tenant: {str(e)}",
                    severity='medium',
                )
        
        return unsuspending_tenants
    
    @staticmethod
    def get_suspended_tenants(filters=None):
        """
        Get list of suspended tenants with details.
        
        Args:
            filters (dict): Optional filters
            
        Returns:
            QuerySet: Filtered suspended tenants
        """
        queryset = Tenant.objects.filter(is_suspended=True, is_deleted=False)
        
        if filters:
            if 'reason' in filters:
                # Filter by suspension reason (stored in suspension_reason)
                queryset = queryset.filter(
                    suspension_reason__icontains=filters['reason']
                )
            
            if 'suspended_after' in filters:
                queryset = queryset.filter(
                    suspended_at__gte=filters['suspended_after']
                )
            
            if 'suspended_before' in filters:
                queryset = queryset.filter(
                    suspended_at__lte=filters['suspended_before']
                )
            
            if 'auto_unsuspend_pending' in filters:
                if filters['auto_unsuspend_pending']:
                    queryset = queryset.filter(
                        metadata__auto_unsuspend_at__isnull=False
                    )
                else:
                    queryset = queryset.filter(
                        metadata__auto_unsuspend_at__isnull=True
                    )
        
        return queryset.select_related('owner', 'plan').order_by('-suspended_at')
    
    @staticmethod
    def get_suspension_statistics():
        """
        Get suspension statistics and analytics.
        
        Returns:
            dict: Suspension statistics
        """
        from django.db.models import Count, Q
        from django.utils import timezone
        from datetime import timedelta
        
        now = timezone.now()
        last_30_days = now - timedelta(days=30)
        last_7_days = now - timedelta(days=7)
        
        stats = {
            'total_suspended': Tenant.objects.filter(is_suspended=True, is_deleted=False).count(),
            'suspended_last_7_days': Tenant.objects.filter(
                is_suspended=True,
                suspended_at__gte=last_7_days,
                is_deleted=False
            ).count(),
            'suspended_last_30_days': Tenant.objects.filter(
                is_suspended=True,
                suspended_at__gte=last_30_days,
                is_deleted=False
            ).count(),
            'auto_unsuspend_pending': Tenant.objects.filter(
                is_suspended=True,
                metadata__auto_unsuspend_at__isnull=False,
                is_deleted=False
            ).count(),
        }
        
        # Suspension reasons breakdown
        reasons = Tenant.objects.filter(
            is_suspended=True,
            is_deleted=False
        ).values('suspension_reason').annotate(count=Count('id'))
        
        stats['by_reason'] = {
            item['suspension_reason']: item['count']
            for item in reasons
        }
        
        # Plan breakdown
        plans = Tenant.objects.filter(
            is_suspended=True,
            is_deleted=False
        ).values('plan__name').annotate(count=Count('id'))
        
        stats['by_plan'] = {
            item['plan__name']: item['count']
            for item in plans
        }
        
        return stats
    
    @staticmethod
    def validate_suspension_data(data):
        """
        Validate suspension request data.
        
        Args:
            data (dict): Suspension data to validate
            
        Returns:
            tuple: (is_valid, errors)
        """
        errors = []
        
        # Validate reason
        if 'reason' not in data or not data['reason']:
            errors.append('Suspension reason is required.')
        
        # Validate auto-unsuspend time
        if 'auto_unsuspend_at' in data:
            auto_unsuspend_at = data['auto_unsuspend_at']
            if isinstance(auto_unsuspend_at, str):
                try:
                    from django.utils.dateparse import parse_datetime
                    auto_unsuspend_at = parse_datetime(auto_unsuspend_at)
                except:
                    errors.append('Invalid auto-unsuspend datetime format.')
            
            if auto_unsuspend_at and auto_unsuspend_at <= timezone.now():
                errors.append('Auto-unsuspend time must be in the future.')
        
        return len(errors) == 0, errors
    
    @staticmethod
    def can_suspend_tenant(tenant, user):
        """
        Check if a user can suspend a tenant.
        
        Args:
            tenant (Tenant): Tenant to check
            user (User): User attempting suspension
            
        Returns:
            tuple: (can_suspend, reason)
        """
        # Check if user is tenant owner
        if tenant.owner == user:
            return False, 'Cannot suspend your own tenant.'
        
        # Check if user is superadmin (implement based on your auth system)
        if not hasattr(user, 'is_superuser') or not user.is_superuser:
            return False, 'Insufficient permissions to suspend tenant.'
        
        # Check if tenant is already suspended
        if tenant.is_suspended:
            return False, 'Tenant is already suspended.'
        
        return True, None
    
    @staticmethod
    def get_suspension_history(tenant, limit=50):
        """
        Get suspension history for a tenant.
        
        Args:
            tenant (Tenant): Tenant to get history for
            limit (int): Maximum number of records
            
        Returns:
            QuerySet: Suspension audit logs
        """
        return TenantAuditLog.objects.filter(
            tenant=tenant,
            action='security_event'
        ).filter(
            description__icontains='suspended'
        ).order_by('-created_at')[:limit]
