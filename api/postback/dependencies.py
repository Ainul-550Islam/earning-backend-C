"""
dependencies.py – Dependency management and external service integrations.

Manages external dependencies, third-party service integrations,
and provides a unified interface for accessing external services used
by the postback module.
"""
import logging
from typing import Dict, List, Optional, Any, Union
from urllib.parse import urljoin, urlencode
import json
import requests
from datetime import datetime, timedelta

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django.contrib.auth import get_user_model

from .exceptions import PostbackException, NetworkInactiveException

logger = logging.getLogger(__name__)
User = get_user_model()


class ExternalServiceDependency:
    """Base class for external service dependencies."""
    
    def __init__(self, name: str, base_url: str, api_key: str = None, timeout: int = 30):
        self.name = name
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout
        self.session = requests.Session()
        
        # Set default headers
        self.session.headers.update({
            'User-Agent': f'PostbackModule/1.0',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        })
        
        if api_key:
            self.session.headers['Authorization'] = f'Bearer {api_key}'
    
    def _make_request(self, method: str, endpoint: str, data: Dict = None, params: Dict = None) -> Dict:
        """Make HTTP request to external service."""
        url = urljoin(self.base_url, endpoint)
        
        try:
            response = self.session.request(
                method=method.upper(),
                url=url,
                json=data,
                params=params,
                timeout=self.timeout
            )
            
            response.raise_for_status()
            
            try:
                return response.json()
            except ValueError:
                return {'status': 'success', 'data': response.text}
        
        except requests.exceptions.Timeout:
            logger.error(f"Timeout error for {self.name} service: {url}")
            raise PostbackException(f"Service {self.name} timeout")
        
        except requests.exceptions.ConnectionError:
            logger.error(f"Connection error for {self.name} service: {url}")
            raise PostbackException(f"Service {self.name} unavailable")
        
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error for {self.name} service: {e}")
            raise PostbackException(f"Service {self.name} HTTP error: {e.response.status_code}")
        
        except Exception as e:
            logger.error(f"Unexpected error for {self.name} service: {e}")
            raise PostbackException(f"Service {self.name} error: {str(e)}")
    
    def health_check(self) -> Dict:
        """Check if the external service is healthy."""
        try:
            response = self._make_request('GET', '/health')
            return {
                'service': self.name,
                'status': 'healthy',
                'response': response,
                'timestamp': timezone.now().isoformat()
            }
        except Exception as e:
            return {
                'service': self.name,
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }


class NotificationService(ExternalServiceDependency):
    """Service for sending notifications (email, SMS, push)."""
    
    def __init__(self):
        config = getattr(settings, 'POSTBACK_NOTIFICATION_SERVICE', {})
        super().__init__(
            name='notification',
            base_url=config.get('base_url', 'https://api.notification-service.com'),
            api_key=config.get('api_key'),
            timeout=config.get('timeout', 30)
        )
    
    def send_email(self, to: Union[str, List[str]], subject: str, body: str, **kwargs) -> Dict:
        """Send email notification."""
        data = {
            'type': 'email',
            'to': to if isinstance(to, list) else [to],
            'subject': subject,
            'body': body,
            **kwargs
        }
        
        return self._make_request('POST', '/send', data)
    
    def send_sms(self, to: Union[str, List[str]], message: str, **kwargs) -> Dict:
        """Send SMS notification."""
        data = {
            'type': 'sms',
            'to': to if isinstance(to, list) else [to],
            'message': message,
            **kwargs
        }
        
        return self._make_request('POST', '/send', data)
    
    def send_push(self, to: Union[str, List[str]], title: str, message: str, **kwargs) -> Dict:
        """Send push notification."""
        data = {
            'type': 'push',
            'to': to if isinstance(to, list) else [to],
            'title': title,
            'message': message,
            **kwargs
        }
        
        return self._make_request('POST', '/send', data)


class AnalyticsService(ExternalServiceDependency):
    """Service for external analytics tracking."""
    
    def __init__(self):
        config = getattr(settings, 'POSTBACK_ANALYTICS_SERVICE', {})
        super().__init__(
            name='analytics',
            base_url=config.get('base_url', 'https://api.analytics-service.com'),
            api_key=config.get('api_key'),
            timeout=config.get('timeout', 30)
        )
    
    def track_event(self, event_name: str, properties: Dict = None, user_id: str = None) -> Dict:
        """Track analytics event."""
        data = {
            'event': event_name,
            'properties': properties or {},
            'user_id': user_id,
            'timestamp': timezone.now().isoformat(),
            'source': 'postback_module'
        }
        
        return self._make_request('POST', '/events', data)
    
    def track_conversion(self, conversion_data: Dict) -> Dict:
        """Track conversion event."""
        data = {
            'event': 'conversion',
            'conversion_data': conversion_data,
            'timestamp': timezone.now().isoformat(),
            'source': 'postback_module'
        }
        
        return self._make_request('POST', '/conversions', data)
    
    def get_analytics(self, start_date: datetime, end_date: datetime, filters: Dict = None) -> Dict:
        """Get analytics data."""
        params = {
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'source': 'postback_module'
        }
        
        if filters:
            params.update(filters)
        
        return self._make_request('GET', '/analytics', params=params)


class FraudDetectionService(ExternalServiceDependency):
    """Service for fraud detection and risk assessment."""
    
    def __init__(self):
        config = getattr(settings, 'POSTBACK_FRAUD_SERVICE', {})
        super().__init__(
            name='fraud_detection',
            base_url=config.get('base_url', 'https://api.fraud-service.com'),
            api_key=config.get('api_key'),
            timeout=config.get('timeout', 30)
        )
    
    def assess_risk(self, user_data: Dict, transaction_data: Dict) -> Dict:
        """Assess risk for a transaction."""
        data = {
            'user_data': user_data,
            'transaction_data': transaction_data,
            'timestamp': timezone.now().isoformat(),
            'source': 'postback_module'
        }
        
        return self._make_request('POST', '/assess', data)
    
    def check_ip_reputation(self, ip_address: str) -> Dict:
        """Check IP address reputation."""
        data = {
            'ip_address': ip_address,
            'timestamp': timezone.now().isoformat()
        }
        
        return self._make_request('POST', '/ip-check', data)
    
    def report_fraud(self, fraud_data: Dict) -> Dict:
        """Report fraudulent activity."""
        data = {
            'fraud_data': fraud_data,
            'timestamp': timezone.now().isoformat(),
            'source': 'postback_module'
        }
        
        return self._make_request('POST', '/report', data)


class PaymentService(ExternalServiceDependency):
    """Service for payment processing and wallet operations."""
    
    def __init__(self):
        config = getattr(settings, 'POSTBACK_PAYMENT_SERVICE', {})
        super().__init__(
            name='payment',
            base_url=config.get('base_url', 'https://api.payment-service.com'),
            api_key=config.get('api_key'),
            timeout=config.get('timeout', 30)
        )
    
    def process_payout(self, user_id: str, amount: float, currency: str, metadata: Dict = None) -> Dict:
        """Process payout to user."""
        data = {
            'user_id': user_id,
            'amount': amount,
            'currency': currency,
            'metadata': metadata or {},
            'timestamp': timezone.now().isoformat(),
            'source': 'postback_module'
        }
        
        return self._make_request('POST', '/payouts', data)
    
    def get_balance(self, user_id: str) -> Dict:
        """Get user balance."""
        params = {
            'user_id': user_id,
            'source': 'postback_module'
        }
        
        return self._make_request('GET', '/balance', params=params)
    
    def create_wallet_transaction(self, user_id: str, amount: float, transaction_type: str, metadata: Dict = None) -> Dict:
        """Create wallet transaction."""
        data = {
            'user_id': user_id,
            'amount': amount,
            'type': transaction_type,
            'metadata': metadata or {},
            'timestamp': timezone.now().isoformat(),
            'source': 'postback_module'
        }
        
        return self._make_request('POST', '/transactions', data)


class WebhookService(ExternalServiceDependency):
    """Service for webhook delivery and management."""
    
    def __init__(self):
        config = getattr(settings, 'POSTBACK_WEBHOOK_SERVICE', {})
        super().__init__(
            name='webhook',
            base_url=config.get('base_url', 'https://api.webhook-service.com'),
            api_key=config.get('api_key'),
            timeout=config.get('timeout', 30)
        )
    
    def send_webhook(self, url: str, payload: Dict, headers: Dict = None, method: str = 'POST') -> Dict:
        """Send webhook to external URL."""
        data = {
            'url': url,
            'payload': payload,
            'headers': headers or {},
            'method': method.upper(),
            'timestamp': timezone.now().isoformat(),
            'source': 'postback_module'
        }
        
        return self._make_request('POST', '/send', data)
    
    def verify_webhook(self, webhook_data: Dict, signature: str, secret: str) -> Dict:
        """Verify webhook signature."""
        data = {
            'webhook_data': webhook_data,
            'signature': signature,
            'secret': secret,
            'timestamp': timezone.now().isoformat()
        }
        
        return self._make_request('POST', '/verify', data)
    
    def get_delivery_status(self, webhook_id: str) -> Dict:
        """Get webhook delivery status."""
        params = {
            'webhook_id': webhook_id,
            'source': 'postback_module'
        }
        
        return self._make_request('GET', '/status', params=params)


class StorageService(ExternalServiceDependency):
    """Service for file storage and CDN operations."""
    
    def __init__(self):
        config = getattr(settings, 'POSTBACK_STORAGE_SERVICE', {})
        super().__init__(
            name='storage',
            base_url=config.get('base_url', 'https://api.storage-service.com'),
            api_key=config.get('api_key'),
            timeout=config.get('timeout', 30)
        )
    
    def upload_file(self, file_data: bytes, filename: str, content_type: str, metadata: Dict = None) -> Dict:
        """Upload file to storage service."""
        # For file uploads, we need to handle multipart data
        # This is a simplified version
        data = {
            'filename': filename,
            'content_type': content_type,
            'metadata': metadata or {},
            'timestamp': timezone.now().isoformat(),
            'source': 'postback_module'
        }
        
        return self._make_request('POST', '/upload', data)
    
    def get_file_url(self, file_id: str, expires_in: int = 3600) -> Dict:
        """Get temporary URL for file access."""
        params = {
            'file_id': file_id,
            'expires_in': expires_in,
            'source': 'postback_module'
        }
        
        return self._make_request('GET', '/url', params=params)
    
    def delete_file(self, file_id: str) -> Dict:
        """Delete file from storage."""
        data = {
            'file_id': file_id,
            'timestamp': timezone.now().isoformat(),
            'source': 'postback_module'
        }
        
        return self._make_request('DELETE', f'/files/{file_id}', data)


class DependencyManager:
    """Manager for all external service dependencies."""
    
    def __init__(self):
        self._services = {}
        self._initialize_services()
    
    def _initialize_services(self):
        """Initialize all external services."""
        try:
            # Initialize only enabled services
            if getattr(settings, 'POSTBACK_NOTIFICATIONS_ENABLED', False):
                self._services['notification'] = NotificationService()
            
            if getattr(settings, 'POSTBACK_ANALYTICS_ENABLED', False):
                self._services['analytics'] = AnalyticsService()
            
            if getattr(settings, 'POSTBACK_FRAUD_DETECTION_ENABLED', False):
                self._services['fraud_detection'] = FraudDetectionService()
            
            if getattr(settings, 'POSTBACK_PAYMENT_SERVICE_ENABLED', False):
                self._services['payment'] = PaymentService()
            
            if getattr(settings, 'POSTBACK_WEBHOOK_SERVICE_ENABLED', False):
                self._services['webhook'] = WebhookService()
            
            if getattr(settings, 'POSTBACK_STORAGE_SERVICE_ENABLED', False):
                self._services['storage'] = StorageService()
            
            logger.info(f"Initialized {len(self._services)} external services")
        
        except Exception as e:
            logger.error(f"Error initializing external services: {str(e)}")
    
    def get_service(self, service_name: str) -> Optional[ExternalServiceDependency]:
        """Get external service by name."""
        return self._services.get(service_name)
    
    def is_service_available(self, service_name: str) -> bool:
        """Check if external service is available."""
        service = self.get_service(service_name)
        if not service:
            return False
        
        try:
            health_check = service.health_check()
            return health_check['status'] == 'healthy'
        except Exception:
            return False
    
    def get_all_health_checks(self) -> Dict[str, Dict]:
        """Get health status for all services."""
        health_checks = {}
        
        for service_name, service in self._services.items():
            try:
                health_checks[service_name] = service.health_check()
            except Exception as e:
                health_checks[service_name] = {
                    'service': service_name,
                    'status': 'error',
                    'error': str(e),
                    'timestamp': timezone.now().isoformat()
                }
        
        return health_checks
    
    def send_notification(self, notification_type: str, **kwargs) -> Dict:
        """Send notification using notification service."""
        service = self.get_service('notification')
        if not service:
            raise PostbackException("Notification service not available")
        
        if notification_type == 'email':
            return service.send_email(**kwargs)
        elif notification_type == 'sms':
            return service.send_sms(**kwargs)
        elif notification_type == 'push':
            return service.send_push(**kwargs)
        else:
            raise PostbackException(f"Unknown notification type: {notification_type}")
    
    def track_analytics_event(self, event_name: str, **kwargs) -> Dict:
        """Track analytics event."""
        service = self.get_service('analytics')
        if not service:
            raise PostbackException("Analytics service not available")
        
        return service.track_event(event_name, **kwargs)
    
    def assess_fraud_risk(self, **kwargs) -> Dict:
        """Assess fraud risk."""
        service = self.get_service('fraud_detection')
        if not service:
            raise PostbackException("Fraud detection service not available")
        
        return service.assess_risk(**kwargs)
    
    def process_payment(self, **kwargs) -> Dict:
        """Process payment."""
        service = self.get_service('payment')
        if not service:
            raise PostbackException("Payment service not available")
        
        return service.process_payout(**kwargs)
    
    def send_webhook(self, **kwargs) -> Dict:
        """Send webhook."""
        service = self.get_service('webhook')
        if not service:
            raise PostbackException("Webhook service not available")
        
        return service.send_webhook(**kwargs)
    
    def upload_file(self, **kwargs) -> Dict:
        """Upload file to storage."""
        service = self.get_service('storage')
        if not service:
            raise PostbackException("Storage service not available")
        
        return service.upload_file(**kwargs)


# Global dependency manager instance
dependency_manager = DependencyManager()


# Convenience functions
def send_notification(notification_type: str, **kwargs) -> Dict:
    """Send notification using dependency manager."""
    return dependency_manager.send_notification(notification_type, **kwargs)


def track_analytics_event(event_name: str, **kwargs) -> Dict:
    """Track analytics event using dependency manager."""
    return dependency_manager.track_analytics_event(event_name, **kwargs)


def assess_fraud_risk(**kwargs) -> Dict:
    """Assess fraud risk using dependency manager."""
    return dependency_manager.assess_fraud_risk(**kwargs)


def process_payment(**kwargs) -> Dict:
    """Process payment using dependency manager."""
    return dependency_manager.process_payment(**kwargs)


def send_webhook(**kwargs) -> Dict:
    """Send webhook using dependency manager."""
    return dependency_manager.send_webhook(**kwargs)


def upload_file(**kwargs) -> Dict:
    """Upload file using dependency manager."""
    return dependency_manager.upload_file(**kwargs)


def get_service_health() -> Dict[str, Dict]:
    """Get health status of all external services."""
    return dependency_manager.get_all_health_checks()


# Cache external service responses
def cached_service_call(service_name: str, method_name: str, cache_key: str, cache_timeout: int = 300, **kwargs):
    """Cache external service calls."""
    cache_key_full = f"postback_service:{service_name}:{method_name}:{cache_key}"
    
    # Try to get from cache
    cached_result = cache.get(cache_key_full)
    if cached_result is not None:
        return cached_result
    
    # Call service
    service = dependency_manager.get_service(service_name)
    if not service:
        raise PostbackException(f"Service {service_name} not available")
    
    method = getattr(service, method_name, None)
    if not method:
        raise PostbackException(f"Method {method_name} not found on service {service_name}")
    
    result = method(**kwargs)
    
    # Cache result
    cache.set(cache_key_full, result, cache_timeout)
    
    return result


# Service dependency validation
def validate_dependencies() -> Dict:
    """Validate all external service dependencies."""
    validation_results = {
        'valid': True,
        'services': {},
        'errors': []
    }
    
    health_checks = get_service_health()
    
    for service_name, health_check in health_checks.items():
        if health_check['status'] == 'healthy':
            validation_results['services'][service_name] = {
                'status': 'valid',
                'message': 'Service is healthy'
            }
        else:
            validation_results['valid'] = False
            validation_results['services'][service_name] = {
                'status': 'invalid',
                'message': health_check.get('error', 'Service unhealthy')
            }
            validation_results['errors'].append(
                f"Service {service_name}: {health_check.get('error', 'Service unhealthy')}"
            )
    
    return validation_results


# Configuration helpers
def get_service_config(service_name: str) -> Dict:
    """Get configuration for a specific service."""
    config_key = f'POSTBACK_{service_name.upper()}_SERVICE'
    return getattr(settings, config_key, {})


def is_service_enabled(service_name: str) -> bool:
    """Check if a service is enabled."""
    enabled_key = f'POSTBACK_{service_name.upper()}_ENABLED'
    return getattr(settings, enabled_key, False)


# Service metrics and monitoring
def collect_service_metrics() -> Dict:
    """Collect metrics for all external services."""
    metrics = {
        'total_services': len(dependency_manager._services),
        'healthy_services': 0,
        'unhealthy_services': 0,
        'service_details': {}
    }
    
    health_checks = get_service_health()
    
    for service_name, health_check in health_checks.items():
        if health_check['status'] == 'healthy':
            metrics['healthy_services'] += 1
        else:
            metrics['unhealthy_services'] += 1
        
        metrics['service_details'][service_name] = {
            'status': health_check['status'],
            'last_check': health_check['timestamp']
        }
    
    return metrics
