"""
Base Signal Classes

This module contains base signal classes and utilities that other
tenant management signal handlers inherit from or use.
"""

from django.db.models.signals import pre_save, post_save, pre_delete, post_delete
from django.dispatch import Signal, receiver
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


# Custom signals for tenant management
tenant_created = Signal()
tenant_updated = Signal()
tenant_deleted = Signal()
tenant_suspended = Signal()
tenant_unsuspended = Signal()

plan_created = Signal()
plan_updated = Signal()
plan_deleted = Signal()

billing_created = Signal()
billing_updated = Signal()
invoice_created = Signal()
invoice_paid = Signal()

api_key_created = Signal()
api_key_used = Signal()
api_key_revoked = Signal()

webhook_triggered = Signal()
webhook_failed = Signal()

metric_recorded = Signal()
health_score_updated = Signal()
feature_flag_toggled = Signal()

notification_created = Signal()
notification_sent = Signal()

onboarding_started = Signal()
onboarding_completed = Signal()
onboarding_step_completed = Signal()

security_event_detected = Signal()
audit_log_created = Signal()

reseller_created = Signal()
commission_calculated = Signal()

branding_updated = Signal()
domain_verified = Signal()


class BaseSignalHandler:
    """
    Base class for signal handlers.
    
    Provides common functionality for signal handling including:
    - Error handling and logging
    - Signal validation
    - Common operations
    """
    
    @staticmethod
    def handle_signal_error(signal_name, sender, **kwargs):
        """
        Handle signal errors consistently.
        
        Args:
            signal_name (str): Name of the signal
            sender: Signal sender
            **kwargs: Signal kwargs
        """
        try:
            logger.error(f"Error handling {signal_name} signal from {sender}")
        except Exception as e:
            logger.error(f"Error in signal error handler: {str(e)}")
    
    @staticmethod
    def validate_signal_data(signal_name, data):
        """
        Validate signal data.
        
        Args:
            signal_name (str): Name of the signal
            data (dict): Signal data to validate
            
        Returns:
            bool: True if valid
        """
        try:
            # Basic validation - ensure data is a dict
            if not isinstance(data, dict):
                logger.error(f"Invalid signal data for {signal_name}: expected dict")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating signal data for {signal_name}: {str(e)}")
            return False
    
    @staticmethod
    def create_audit_log(instance, action, description, **kwargs):
        """
        Create audit log for signal events.
        
        Args:
            instance: Model instance
            action (str): Action performed
            description (str): Description of action
            **kwargs: Additional data
        """
        try:
            from ..models.security import TenantAuditLog
            from ..services import TenantAuditService
            
            # Get tenant from instance
            tenant = None
            if hasattr(instance, 'tenant'):
                tenant = instance.tenant
            elif hasattr(instance, '__class__'):
                if instance.__class__.__name__ == 'Tenant':
                    tenant = instance
            
            if tenant:
                TenantAuditService.create_audit_log(
                    tenant=tenant,
                    action=action,
                    description=description,
                    metadata=kwargs
                )
                
        except Exception as e:
            logger.error(f"Error creating audit log: {str(e)}")
    
    @staticmethod
    def create_notification(instance, title, message, **kwargs):
        """
        Create notification for signal events.
        
        Args:
            instance: Model instance
            title (str): Notification title
            message (str): Notification message
            **kwargs: Additional data
        """
        try:
            from ..models.analytics import TenantNotification
            
            # Get tenant from instance
            tenant = None
            if hasattr(instance, 'tenant'):
                tenant = instance.tenant
            elif hasattr(instance, '__class__'):
                if instance.__class__.__name__ == 'Tenant':
                    tenant = instance
            
            if tenant:
                TenantNotification.objects.create(
                    tenant=tenant,
                    title=title,
                    message=message,
                    notification_type=kwargs.get('type', 'system'),
                    priority=kwargs.get('priority', 'medium'),
                    metadata=kwargs.get('metadata', {})
                )
                
        except Exception as e:
            logger.error(f"Error creating notification: {str(e)}")
    
    @staticmethod
    def trigger_webhook(instance, event_type, data):
        """
        Trigger webhook for signal events.
        
        Args:
            instance: Model instance
            event_type (str): Type of event
            data (dict): Event data
        """
        try:
            from ..models.security import TenantWebhookConfig
            
            # Get tenant from instance
            tenant = None
            if hasattr(instance, 'tenant'):
                tenant = instance.tenant
            elif hasattr(instance, '__class__'):
                if instance.__class__.__name__ == 'Tenant':
                    tenant = instance
            
            if tenant:
                # Get active webhooks for this event type
                webhooks = TenantWebhookConfig.objects.filter(
                    tenant=tenant,
                    is_active=True,
                    event_types__contains=[event_type]
                )
                
                for webhook in webhooks:
                    # Trigger webhook asynchronously
                    from ..tasks import trigger_webhook_task
                    trigger_webhook_task.delay(
                        webhook_id=webhook.id,
                        event_type=event_type,
                        data=data
                    )
                    
        except Exception as e:
            logger.error(f"Error triggering webhook: {str(e)}")


class TenantSignalHandler(BaseSignalHandler):
    """
    Signal handler for tenant-related events.
    """
    
    @staticmethod
    @receiver(tenant_created)
    def handle_tenant_created(sender, **kwargs):
        """Handle tenant created signal."""
        try:
            tenant = kwargs.get('tenant')
            user = kwargs.get('user')
            
            if not tenant:
                logger.error("Tenant created signal missing tenant instance")
                return
            
            # Create audit log
            TenantSignalHandler.create_audit_log(
                tenant=tenant,
                action='tenant_created',
                description=f'Tenant {tenant.name} created',
                user=user,
                metadata={
                    'tenant_id': tenant.id,
                    'tenant_slug': tenant.slug,
                    'plan': tenant.plan.name if tenant.plan else None
                }
            )
            
            # Create welcome notification
            TenantSignalHandler.create_notification(
                tenant=tenant,
                title='Welcome to Your New Tenant',
                message=f'Your tenant {tenant.name} has been successfully created.',
                type='onboarding',
                metadata={'event': 'tenant_created'}
            )
            
            # Trigger webhook
            TenantSignalHandler.trigger_webhook(
                tenant,
                'tenant.created',
                {
                    'tenant_id': tenant.id,
                    'tenant_name': tenant.name,
                    'tenant_slug': tenant.slug,
                    'created_at': tenant.created_at.isoformat()
                }
            )
            
            logger.info(f"Handled tenant created signal for {tenant.name}")
            
        except Exception as e:
            TenantSignalHandler.handle_signal_error('tenant_created', sender, **kwargs)
    
    @staticmethod
    @receiver(tenant_updated)
    def handle_tenant_updated(sender, **kwargs):
        """Handle tenant updated signal."""
        try:
            tenant = kwargs.get('tenant')
            user = kwargs.get('user')
            changes = kwargs.get('changes', {})
            
            if not tenant:
                logger.error("Tenant updated signal missing tenant instance")
                return
            
            # Create audit log
            TenantSignalHandler.create_audit_log(
                tenant=tenant,
                action='tenant_updated',
                description=f'Tenant {tenant.name} updated',
                user=user,
                metadata={
                    'tenant_id': tenant.id,
                    'changes': changes
                }
            )
            
            # Trigger webhook
            TenantSignalHandler.trigger_webhook(
                tenant,
                'tenant.updated',
                {
                    'tenant_id': tenant.id,
                    'tenant_name': tenant.name,
                    'changes': changes,
                    'updated_at': tenant.updated_at.isoformat()
                }
            )
            
            logger.info(f"Handled tenant updated signal for {tenant.name}")
            
        except Exception as e:
            TenantSignalHandler.handle_signal_error('tenant_updated', sender, **kwargs)
    
    @staticmethod
    @receiver(tenant_deleted)
    def handle_tenant_deleted(sender, **kwargs):
        """Handle tenant deleted signal."""
        try:
            tenant = kwargs.get('tenant')
            user = kwargs.get('user')
            
            if not tenant:
                logger.error("Tenant deleted signal missing tenant instance")
                return
            
            # Create audit log
            TenantSignalHandler.create_audit_log(
                tenant=tenant,
                action='tenant_deleted',
                description=f'Tenant {tenant.name} deleted',
                user=user,
                metadata={
                    'tenant_id': tenant.id,
                    'tenant_name': tenant.name
                }
            )
            
            # Trigger webhook
            TenantSignalHandler.trigger_webhook(
                tenant,
                'tenant.deleted',
                {
                    'tenant_id': tenant.id,
                    'tenant_name': tenant.name,
                    'deleted_at': timezone.now().isoformat()
                }
            )
            
            logger.info(f"Handled tenant deleted signal for {tenant.name}")
            
        except Exception as e:
            TenantSignalHandler.handle_signal_error('tenant_deleted', sender, **kwargs)
    
    @staticmethod
    @receiver(tenant_suspended)
    def handle_tenant_suspended(sender, **kwargs):
        """Handle tenant suspended signal."""
        try:
            tenant = kwargs.get('tenant')
            user = kwargs.get('user')
            reason = kwargs.get('reason', '')
            
            if not tenant:
                logger.error("Tenant suspended signal missing tenant instance")
                return
            
            # Create audit log
            TenantSignalHandler.create_audit_log(
                tenant=tenant,
                action='tenant_suspended',
                description=f'Tenant {tenant.name} suspended: {reason}',
                user=user,
                metadata={
                    'tenant_id': tenant.id,
                    'reason': reason
                }
            )
            
            # Create notification
            TenantSignalHandler.create_notification(
                tenant=tenant,
                title='Tenant Suspended',
                message=f'Your tenant {tenant.name} has been suspended. Reason: {reason}',
                type='security',
                priority='high',
                metadata={'event': 'tenant_suspended'}
            )
            
            # Trigger webhook
            TenantSignalHandler.trigger_webhook(
                tenant,
                'tenant.suspended',
                {
                    'tenant_id': tenant.id,
                    'tenant_name': tenant.name,
                    'reason': reason,
                    'suspended_at': timezone.now().isoformat()
                }
            )
            
            logger.info(f"Handled tenant suspended signal for {tenant.name}")
            
        except Exception as e:
            TenantSignalHandler.handle_signal_error('tenant_suspended', sender, **kwargs)
    
    @staticmethod
    @receiver(tenant_unsuspended)
    def handle_tenant_unsuspended(sender, **kwargs):
        """Handle tenant unsuspended signal."""
        try:
            tenant = kwargs.get('tenant')
            user = kwargs.get('user')
            
            if not tenant:
                logger.error("Tenant unsuspended signal missing tenant instance")
                return
            
            # Create audit log
            TenantSignalHandler.create_audit_log(
                tenant=tenant,
                action='tenant_unsuspended',
                description=f'Tenant {tenant.name} unsuspended',
                user=user,
                metadata={
                    'tenant_id': tenant.id
                }
            )
            
            # Create notification
            TenantSignalHandler.create_notification(
                tenant=tenant,
                title='Tenant Unsuspended',
                message=f'Your tenant {tenant.name} has been unsuspended and is now active.',
                type='security',
                priority='medium',
                metadata={'event': 'tenant_unsuspended'}
            )
            
            # Trigger webhook
            TenantSignalHandler.trigger_webhook(
                tenant,
                'tenant.unsuspended',
                {
                    'tenant_id': tenant.id,
                    'tenant_name': tenant.name,
                    'unsuspended_at': timezone.now().isoformat()
                }
            )
            
            logger.info(f"Handled tenant unsuspended signal for {tenant.name}")
            
        except Exception as e:
            TenantSignalHandler.handle_signal_error('tenant_unsuspended', sender, **kwargs)


class BillingSignalHandler(BaseSignalHandler):
    """
    Signal handler for billing-related events.
    """
    
    @staticmethod
    @receiver(invoice_created)
    def handle_invoice_created(sender, **kwargs):
        """Handle invoice created signal."""
        try:
            invoice = kwargs.get('invoice')
            
            if not invoice:
                logger.error("Invoice created signal missing invoice instance")
                return
            
            # Create audit log
            TenantSignalHandler.create_audit_log(
                invoice=invoice,
                action='invoice_created',
                description=f'Invoice {invoice.invoice_number} created',
                metadata={
                    'invoice_id': invoice.id,
                    'invoice_number': invoice.invoice_number,
                    'amount': float(invoice.total_amount),
                    'due_date': invoice.due_date.isoformat()
                }
            )
            
            # Create notification
            TenantSignalHandler.create_notification(
                invoice=invoice,
                title='New Invoice Available',
                message=f'Invoice {invoice.invoice_number} for {invoice.total_amount} is now available.',
                type='billing',
                metadata={'event': 'invoice_created'}
            )
            
            # Trigger webhook
            TenantSignalHandler.trigger_webhook(
                invoice,
                'invoice.created',
                {
                    'invoice_id': invoice.id,
                    'invoice_number': invoice.invoice_number,
                    'amount': float(invoice.total_amount),
                    'due_date': invoice.due_date.isoformat()
                }
            )
            
            logger.info(f"Handled invoice created signal for {invoice.invoice_number}")
            
        except Exception as e:
            BillingSignalHandler.handle_signal_error('invoice_created', sender, **kwargs)
    
    @staticmethod
    @receiver(invoice_paid)
    def handle_invoice_paid(sender, **kwargs):
        """Handle invoice paid signal."""
        try:
            invoice = kwargs.get('invoice')
            payment_amount = kwargs.get('payment_amount')
            
            if not invoice:
                logger.error("Invoice paid signal missing invoice instance")
                return
            
            # Create audit log
            TenantSignalHandler.create_audit_log(
                invoice=invoice,
                action='invoice_paid',
                description=f'Invoice {invoice.invoice_number} paid',
                metadata={
                    'invoice_id': invoice.id,
                    'invoice_number': invoice.invoice_number,
                    'payment_amount': float(payment_amount),
                    'paid_date': timezone.now().isoformat()
                }
            )
            
            # Create notification
            TenantSignalHandler.create_notification(
                invoice=invoice,
                title='Payment Received',
                message=f'Payment of {payment_amount} received for invoice {invoice.invoice_number}.',
                type='billing',
                metadata={'event': 'invoice_paid'}
            )
            
            # Trigger webhook
            TenantSignalHandler.trigger_webhook(
                invoice,
                'invoice.paid',
                {
                    'invoice_id': invoice.id,
                    'invoice_number': invoice.invoice_number,
                    'payment_amount': float(payment_amount),
                    'paid_date': timezone.now().isoformat()
                }
            )
            
            logger.info(f"Handled invoice paid signal for {invoice.invoice_number}")
            
        except Exception as e:
            BillingSignalHandler.handle_signal_error('invoice_paid', sender, **kwargs)


class SecuritySignalHandler(BaseSignalHandler):
    """
    Signal handler for security-related events.
    """
    
    @staticmethod
    @receiver(api_key_created)
    def handle_api_key_created(sender, **kwargs):
        """Handle API key created signal."""
        try:
            api_key = kwargs.get('api_key')
            user = kwargs.get('user')
            
            if not api_key:
                logger.error("API key created signal missing api_key instance")
                return
            
            # Create audit log
            TenantSignalHandler.create_audit_log(
                api_key=api_key,
                action='api_key_created',
                description=f'API key {api_key.name} created',
                user=user,
                metadata={
                    'api_key_id': api_key.id,
                    'api_key_name': api_key.name,
                    'permissions': api_key.permissions
                }
            )
            
            # Create notification
            TenantSignalHandler.create_notification(
                api_key=api_key,
                title='New API Key Created',
                message=f'API key {api_key.name} has been created.',
                type='security',
                metadata={'event': 'api_key_created'}
            )
            
            # Trigger webhook
            TenantSignalHandler.trigger_webhook(
                api_key,
                'api_key.created',
                {
                    'api_key_id': api_key.id,
                    'api_key_name': api_key.name,
                    'permissions': api_key.permissions,
                    'created_at': api_key.created_at.isoformat()
                }
            )
            
            logger.info(f"Handled API key created signal for {api_key.name}")
            
        except Exception as e:
            SecuritySignalHandler.handle_signal_error('api_key_created', sender, **kwargs)
    
    @staticmethod
    @receiver(api_key_used)
    def handle_api_key_used(sender, **kwargs):
        """Handle API key used signal."""
        try:
            api_key = kwargs.get('api_key')
            request_data = kwargs.get('request_data', {})
            
            if not api_key:
                logger.error("API key used signal missing api_key instance")
                return
            
            # Create audit log
            TenantSignalHandler.create_audit_log(
                api_key=api_key,
                action='api_key_used',
                description=f'API key {api_key.name} used',
                metadata={
                    'api_key_id': api_key.id,
                    'api_key_name': api_key.name,
                    'endpoint': request_data.get('endpoint', ''),
                    'ip_address': request_data.get('ip_address', ''),
                    'user_agent': request_data.get('user_agent', '')
                }
            )
            
            # Trigger webhook
            TenantSignalHandler.trigger_webhook(
                api_key,
                'api_key.used',
                {
                    'api_key_id': api_key.id,
                    'api_key_name': api_key.name,
                    'endpoint': request_data.get('endpoint', ''),
                    'ip_address': request_data.get('ip_address', ''),
                    'used_at': timezone.now().isoformat()
                }
            )
            
            logger.info(f"Handled API key used signal for {api_key.name}")
            
        except Exception as e:
            SecuritySignalHandler.handle_signal_error('api_key_used', sender, **kwargs)
    
    @staticmethod
    @receiver(api_key_revoked)
    def handle_api_key_revoked(sender, **kwargs):
        """Handle API key revoked signal."""
        try:
            api_key = kwargs.get('api_key')
            user = kwargs.get('user')
            reason = kwargs.get('reason', '')
            
            if not api_key:
                logger.error("API key revoked signal missing api_key instance")
                return
            
            # Create audit log
            TenantSignalHandler.create_audit_log(
                api_key=api_key,
                action='api_key_revoked',
                description=f'API key {api_key.name} revoked: {reason}',
                user=user,
                metadata={
                    'api_key_id': api_key.id,
                    'api_key_name': api_key.name,
                    'reason': reason
                }
            )
            
            # Create notification
            TenantSignalHandler.create_notification(
                api_key=api_key,
                title='API Key Revoked',
                message=f'API key {api_key.name} has been revoked. Reason: {reason}',
                type='security',
                priority='high',
                metadata={'event': 'api_key_revoked'}
            )
            
            # Trigger webhook
            TenantSignalHandler.trigger_webhook(
                api_key,
                'api_key.revoked',
                {
                    'api_key_id': api_key.id,
                    'api_key_name': api_key.name,
                    'reason': reason,
                    'revoked_at': timezone.now().isoformat()
                }
            )
            
            logger.info(f"Handled API key revoked signal for {api_key.name}")
            
        except Exception as e:
            SecuritySignalHandler.handle_signal_error('api_key_revoked', sender, **kwargs)
    
    @staticmethod
    @receiver(security_event_detected)
    def handle_security_event_detected(sender, **kwargs):
        """Handle security event detected signal."""
        try:
            event_type = kwargs.get('event_type')
            tenant = kwargs.get('tenant')
            event_data = kwargs.get('event_data', {})
            
            if not event_type or not tenant:
                logger.error("Security event detected signal missing required data")
                return
            
            # Create audit log
            TenantSignalHandler.create_audit_log(
                tenant=tenant,
                action='security_event',
                description=f'Security event detected: {event_type}',
                severity='high',
                metadata={
                    'event_type': event_type,
                    'event_data': event_data
                }
            )
            
            # Create notification
            TenantSignalHandler.create_notification(
                tenant=tenant,
                title='Security Event Detected',
                message=f'Security event detected: {event_type}',
                type='security',
                priority='high',
                metadata={'event': 'security_event_detected'}
            )
            
            # Trigger webhook
            TenantSignalHandler.trigger_webhook(
                tenant,
                'security.event',
                {
                    'event_type': event_type,
                    'tenant_id': tenant.id,
                    'event_data': event_data,
                    'detected_at': timezone.now().isoformat()
                }
            )
            
            logger.info(f"Handled security event detected signal for {event_type}")
            
        except Exception as e:
            SecuritySignalHandler.handle_signal_error('security_event_detected', sender, **kwargs)


# Register signal handlers
def register_signal_handlers():
    """Register all signal handlers."""
    try:
        # Import all signal handler modules to register them
        from . import core
        from . import plan
        from . import billing
        from . import security
        from . import analytics
        from . import onboarding
        from . import branding
        from . import reseller
        
        logger.info("All signal handlers registered successfully")
        
    except Exception as e:
        logger.error(f"Error registering signal handlers: {str(e)}")


# Auto-register signal handlers when module is imported
register_signal_handlers()
