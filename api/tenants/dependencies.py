"""
Tenant Dependencies - External Service Integration

This module manages dependencies and integrations with external services
including payment processors, analytics, notifications, and third-party APIs.
"""

import logging
from typing import Dict, Any, Optional, List
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string
import stripe
import paypalrestsdk
from datetime import datetime
import requests
import json

logger = logging.getLogger(__name__)


class TenantDependencyManager:
    """
    Manages external service dependencies for tenant operations.
    
    Handles initialization, configuration, and interaction with
    external services like Stripe, PayPal, analytics, etc.
    """
    
    def __init__(self):
        self._initialized = False
        self._services = {}
        self._configs = {}
    
    def initialize(self):
        """Initialize all external service dependencies."""
        try:
            self._initialize_stripe()
            self._initialize_paypal()
            self._initialize_analytics()
            self._initialize_notifications()
            self._initialize_storage()
            self._initialize_email()
            self._initialized = True
            
            logger.info("Tenant dependencies initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize tenant dependencies: {e}")
            raise ImproperlyConfigured(f"Dependency initialization failed: {e}")
    
    def _initialize_stripe(self):
        """Initialize Stripe payment processing."""
        try:
            stripe_secret_key = getattr(settings, 'STRIPE_SECRET_KEY', None)
            if stripe_secret_key:
                stripe.api_key = stripe_secret_key
                self._services['stripe'] = stripe
                self._configs['stripe'] = {
                    'enabled': True,
                    'webhook_secret': getattr(settings, 'STRIPE_WEBHOOK_SECRET', ''),
                    'publishable_key': getattr(settings, 'STRIPE_PUBLISHABLE_KEY', ''),
                }
                logger.info("Stripe initialized successfully")
            else:
                self._services['stripe'] = None
                self._configs['stripe'] = {'enabled': False}
                logger.warning("Stripe not configured")
                
        except Exception as e:
            logger.error(f"Failed to initialize Stripe: {e}")
            self._services['stripe'] = None
            self._configs['stripe'] = {'enabled': False}
    
    def _initialize_paypal(self):
        """Initialize PayPal payment processing."""
        try:
            paypal_client_id = getattr(settings, 'PAYPAL_CLIENT_ID', None)
            paypal_client_secret = getattr(settings, 'PAYPAL_CLIENT_SECRET', None)
            
            if paypal_client_id and paypal_client_secret:
                paypalrestsdk.configure({
                    'mode': getattr(settings, 'PAYPAL_MODE', 'sandbox'),
                    'client_id': paypal_client_id,
                    'client_secret': paypal_client_secret,
                })
                
                self._services['paypal'] = paypalrestsdk
                self._configs['paypal'] = {
                    'enabled': True,
                    'mode': getattr(settings, 'PAYPAL_MODE', 'sandbox'),
                    'webhook_url': getattr(settings, 'PAYPAL_WEBHOOK_URL', ''),
                }
                logger.info("PayPal initialized successfully")
            else:
                self._services['paypal'] = None
                self._configs['paypal'] = {'enabled': False}
                logger.warning("PayPal not configured")
                
        except Exception as e:
            logger.error(f"Failed to initialize PayPal: {e}")
            self._services['paypal'] = None
            self._configs['paypal'] = {'enabled': False}
    
    def _initialize_analytics(self):
        """Initialize analytics services."""
        try:
            google_analytics_id = getattr(settings, 'GOOGLE_ANALYTICS_TRACKING_ID', None)
            
            self._services['analytics'] = {
                'google': {
                    'enabled': bool(google_analytics_id),
                    'tracking_id': google_analytics_id,
                }
            }
            
            self._configs['analytics'] = {
                'google': bool(google_analytics_id),
                'tracking_id': google_analytics_id,
            }
            
            logger.info("Analytics services initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize analytics: {e}")
            self._services['analytics'] = {}
            self._configs['analytics'] = {}
    
    def _initialize_notifications(self):
        """Initialize notification services."""
        try:
            firebase_server_key = getattr(settings, 'FIREBASE_SERVER_KEY', None)
            
            self._services['notifications'] = {
                'push': {
                    'enabled': bool(firebase_server_key),
                    'firebase_key': firebase_server_key,
                },
                'sms': {
                    'enabled': getattr(settings, 'SMS_ENABLED', False),
                    'provider': getattr(settings, 'SMS_PROVIDER', 'twilio'),
                },
                'email': {
                    'enabled': True,  # Email is always available
                    'backend': getattr(settings, 'EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend'),
                }
            }
            
            self._configs['notifications'] = self._services['notifications']
            
            logger.info("Notification services initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize notifications: {e}")
            self._services['notifications'] = {}
            self._configs['notifications'] = {}
    
    def _initialize_storage(self):
        """Initialize storage services."""
        try:
            storage_backend = getattr(settings, 'DEFAULT_FILE_STORAGE', None)
            
            self._services['storage'] = {
                'backend': storage_backend,
                'local': 'FileSystemStorage' in str(storage_backend),
                's3': 'S3Boto3Storage' in str(storage_backend),
                'gcs': 'GoogleCloudStorage' in str(storage_backend),
            }
            
            self._configs['storage'] = self._services['storage']
            
            logger.info("Storage services initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize storage: {e}")
            self._services['storage'] = {}
            self._configs['storage'] = {}
    
    def _initialize_email(self):
        """Initialize email services."""
        try:
            email_backend = getattr(settings, 'EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend')
            
            self._services['email'] = {
                'backend': email_backend,
                'host': getattr(settings, 'EMAIL_HOST', ''),
                'port': getattr(settings, 'EMAIL_PORT', 587),
                'use_tls': getattr(settings, 'EMAIL_USE_TLS', True),
                'use_ssl': getattr(settings, 'EMAIL_USE_SSL', False),
                'from_email': getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com'),
            }
            
            self._configs['email'] = self._services['email']
            
            logger.info("Email services initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize email: {e}")
            self._services['email'] = {}
            self._configs['email'] = {}
    
    def get_service(self, service_name: str):
        """Get a specific service instance."""
        if not self._initialized:
            self.initialize()
        
        return self._services.get(service_name)
    
    def get_config(self, service_name: str):
        """Get configuration for a specific service."""
        if not self._initialized:
            self.initialize()
        
        return self._configs.get(service_name, {})
    
    def is_service_enabled(self, service_name: str) -> bool:
        """Check if a service is enabled."""
        config = self.get_config(service_name)
        return config.get('enabled', False)
    
    def get_enabled_services(self) -> List[str]:
        """Get list of enabled services."""
        if not self._initialized:
            self.initialize()
        
        enabled_services = []
        for service_name, config in self._configs.items():
            if config.get('enabled', False):
                enabled_services.append(service_name)
        
        return enabled_services


class StripeService:
    """Stripe payment processing service."""
    
    def __init__(self, stripe_client):
        self.stripe = stripe_client
    
    def create_customer(self, email: str, name: str = None) -> Dict[str, Any]:
        """Create a Stripe customer."""
        try:
            customer_data = {'email': email}
            if name:
                customer_data['name'] = name
            
            customer = self.stripe.Customer.create(**customer_data)
            
            return {
                'success': True,
                'customer_id': customer.id,
                'customer': customer,
            }
            
        except Exception as e:
            logger.error(f"Failed to create Stripe customer: {e}")
            return {
                'success': False,
                'error': str(e),
            }
    
    def create_subscription(self, customer_id: str, price_id: str) -> Dict[str, Any]:
        """Create a Stripe subscription."""
        try:
            subscription = self.stripe.Subscription.create(
                customer=customer_id,
                items=[{'price': price_id}],
                payment_behavior='create_if_missing',
            )
            
            return {
                'success': True,
                'subscription_id': subscription.id,
                'subscription': subscription,
            }
            
        except Exception as e:
            logger.error(f"Failed to create Stripe subscription: {e}")
            return {
                'success': False,
                'error': str(e),
            }
    
    def cancel_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """Cancel a Stripe subscription."""
        try:
            subscription = self.stripe.Subscription.delete(subscription_id)
            
            return {
                'success': True,
                'subscription': subscription,
            }
            
        except Exception as e:
            logger.error(f"Failed to cancel Stripe subscription: {e}")
            return {
                'success': False,
                'error': str(e),
            }
    
    def create_invoice(self, customer_id: str, amount: int, currency: str = 'usd') -> Dict[str, Any]:
        """Create a Stripe invoice."""
        try:
            invoice = self.stripe.Invoice.create(
                customer=customer_id,
                amount=amount,
                currency=currency,
            )
            
            return {
                'success': True,
                'invoice_id': invoice.id,
                'invoice': invoice,
            }
            
        except Exception as e:
            logger.error(f"Failed to create Stripe invoice: {e}")
            return {
                'success': False,
                'error': str(e),
            }
    
    def retrieve_webhook_event(self, payload: bytes, sig_header: str, webhook_secret: str) -> Dict[str, Any]:
        """Retrieve and verify Stripe webhook event."""
        try:
            event = self.stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
            
            return {
                'success': True,
                'event': event,
            }
            
        except Exception as e:
            logger.error(f"Failed to retrieve Stripe webhook event: {e}")
            return {
                'success': False,
                'error': str(e),
            }


class PayPalService:
    """PayPal payment processing service."""
    
    def __init__(self, paypal_client):
        self.paypal = paypal_client
    
    def create_payment(self, amount: float, currency: str = 'USD', return_url: str = None, cancel_url: str = None) -> Dict[str, Any]:
        """Create a PayPal payment."""
        try:
            payment = self.paypal.Payment({
                'intent': 'sale',
                'payer': {'payment_method': 'paypal'},
                'transactions': [{
                    'amount': {
                        'total': str(amount),
                        'currency': currency,
                    },
                    'description': 'Tenant subscription payment',
                }],
                'redirect_urls': {
                    'return_url': return_url,
                    'cancel_url': cancel_url,
                } if return_url and cancel_url else None,
            })
            
            if payment.create():
                return {
                    'success': True,
                    'payment_id': payment.id,
                    'approval_url': payment.links[1].href,
                    'payment': payment,
                }
            else:
                return {
                    'success': False,
                    'error': payment.error,
                }
                
        except Exception as e:
            logger.error(f"Failed to create PayPal payment: {e}")
            return {
                'success': False,
                'error': str(e),
            }
    
    def execute_payment(self, payment_id: str, payer_id: str) -> Dict[str, Any]:
        """Execute a PayPal payment."""
        try:
            payment = self.paypal.Payment.find(payment_id)
            
            if payment.execute({'payer_id': payer_id}):
                return {
                    'success': True,
                    'payment': payment,
                }
            else:
                return {
                    'success': False,
                    'error': payment.error,
                }
                
        except Exception as e:
            logger.error(f"Failed to execute PayPal payment: {e}")
            return {
                'success': False,
                'error': str(e),
            }


class AnalyticsService:
    """Analytics tracking service."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.google_enabled = config.get('google', {}).get('enabled', False)
        self.tracking_id = config.get('google', {}).get('tracking_id')
    
    def track_event(self, tenant_id: str, event_name: str, event_data: Dict[str, Any] = None) -> bool:
        """Track an analytics event."""
        try:
            if self.google_enabled and self.tracking_id:
                # Google Analytics tracking would go here
                # This is a placeholder implementation
                logger.info(f"Tracking event {event_name} for tenant {tenant_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to track analytics event: {e}")
            return False
    
    def track_page_view(self, tenant_id: str, page_path: str, user_agent: str = None) -> bool:
        """Track a page view."""
        try:
            if self.google_enabled and self.tracking_id:
                # Google Analytics page view tracking would go here
                logger.info(f"Tracking page view {page_path} for tenant {tenant_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to track page view: {e}")
            return False


class NotificationService:
    """Notification service for multiple channels."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.push_enabled = config.get('push', {}).get('enabled', False)
        self.sms_enabled = config.get('sms', {}).get('enabled', False)
        self.email_enabled = config.get('email', {}).get('enabled', True)
    
    def send_push_notification(self, tokens: List[str], title: str, body: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Send push notification."""
        try:
            if not self.push_enabled:
                return {'success': False, 'error': 'Push notifications not enabled'}
            
            # Firebase push notification implementation would go here
            logger.info(f"Sending push notification to {len(tokens)} devices")
            
            return {
                'success': True,
                'sent_count': len(tokens),
            }
            
        except Exception as e:
            logger.error(f"Failed to send push notification: {e}")
            return {
                'success': False,
                'error': str(e),
            }
    
    def send_sms(self, phone_number: str, message: str) -> Dict[str, Any]:
        """Send SMS message."""
        try:
            if not self.sms_enabled:
                return {'success': False, 'error': 'SMS not enabled'}
            
            # SMS implementation would go here (Twilio, etc.)
            logger.info(f"Sending SMS to {phone_number}")
            
            return {
                'success': True,
            }
            
        except Exception as e:
            logger.error(f"Failed to send SMS: {e}")
            return {
                'success': False,
                'error': str(e),
            }
    
    def send_email(self, to_email: str, subject: str, message: str, html_message: str = None) -> Dict[str, Any]:
        """Send email message."""
        try:
            from django.core.mail import send_mail
            
            if not self.email_enabled:
                return {'success': False, 'error': 'Email not enabled'}
            
            send_mail(
                subject=subject,
                message=message,
                from_email=self.config.get('email', {}).get('from_email'),
                recipient_list=[to_email],
                html_message=html_message,
                fail_silently=False,
            )
            
            logger.info(f"Email sent to {to_email}")
            
            return {
                'success': True,
            }
            
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return {
                'success': False,
                'error': str(e),
            }


class StorageService:
    """Storage service for file management."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.backend = config.get('backend')
        self.is_s3 = config.get('s3', False)
        self.is_gcs = config.get('gcs', False)
        self.is_local = config.get('local', True)
    
    def upload_file(self, file_obj, file_path: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Upload file to storage."""
        try:
            from django.core.files.storage import default_storage
            
            # Save file
            saved_path = default_storage.save(file_path, file_obj)
            
            # Get file URL
            file_url = default_storage.url(saved_path)
            
            logger.info(f"File uploaded to {saved_path}")
            
            return {
                'success': True,
                'file_path': saved_path,
                'file_url': file_url,
            }
            
        except Exception as e:
            logger.error(f"Failed to upload file: {e}")
            return {
                'success': False,
                'error': str(e),
            }
    
    def delete_file(self, file_path: str) -> Dict[str, Any]:
        """Delete file from storage."""
        try:
            from django.core.files.storage import default_storage
            
            if default_storage.exists(file_path):
                default_storage.delete(file_path)
                logger.info(f"File deleted: {file_path}")
                
                return {
                    'success': True,
                }
            else:
                return {
                    'success': False,
                    'error': 'File not found',
                }
                
        except Exception as e:
            logger.error(f"Failed to delete file: {e}")
            return {
                'success': False,
                'error': str(e),
            }
    
    def get_file_url(self, file_path: str) -> str:
        """Get file URL."""
        try:
            from django.core.files.storage import default_storage
            return default_storage.url(file_path)
        except Exception as e:
            logger.error(f"Failed to get file URL: {e}")
            return ''


# Global dependency manager instance
dependency_manager = TenantDependencyManager()

# Service factory functions
def get_stripe_service() -> Optional[StripeService]:
    """Get Stripe service instance."""
    stripe_client = dependency_manager.get_service('stripe')
    if stripe_client:
        return StripeService(stripe_client)
    return None

def get_paypal_service() -> Optional[PayPalService]:
    """Get PayPal service instance."""
    paypal_client = dependency_manager.get_service('paypal')
    if paypal_client:
        return PayPalService(paypal_client)
    return None

def get_analytics_service() -> AnalyticsService:
    """Get analytics service instance."""
    config = dependency_manager.get_config('analytics')
    return AnalyticsService(config)

def get_notification_service() -> NotificationService:
    """Get notification service instance."""
    config = dependency_manager.get_config('notifications')
    return NotificationService(config)

def get_storage_service() -> StorageService:
    """Get storage service instance."""
    config = dependency_manager.get_config('storage')
    return StorageService(config)

# Utility functions
def check_dependencies() -> Dict[str, bool]:
    """Check status of all dependencies."""
    return {
        'stripe': dependency_manager.is_service_enabled('stripe'),
        'paypal': dependency_manager.is_service_enabled('paypal'),
        'analytics': dependency_manager.is_service_enabled('analytics'),
        'notifications': dependency_manager.is_service_enabled('notifications'),
        'storage': dependency_manager.is_service_enabled('storage'),
        'email': dependency_manager.is_service_enabled('email'),
    }

def get_dependency_info() -> Dict[str, Any]:
    """Get detailed information about dependencies."""
    return {
        'enabled_services': dependency_manager.get_enabled_services(),
        'service_configs': dependency_manager._configs,
        'service_status': check_dependencies(),
    }
