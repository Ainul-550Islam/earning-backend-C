"""
Integration Circuit Breaker - Circuit breaker pattern for integration resilience
Provides safe circuit breaking with existing alerts architecture and SMS gateway integration
"""
import logging
import time
import threading
from enum import Enum
from typing import Dict, Any, List, Optional, Callable, Union
from datetime import datetime, timezone, timedelta
from django.utils import timezone as django_tz
from django.core.cache import cache
from django.conf import settings

# Absolute imports to prevent ModuleNotFoundError
from api.alerts.models import AlertLog, AlertRule, Notification
from api.alerts.validators import validate_alert_rule_condition, validate_threshold_value
from api.alerts.services.channels.WebhookAlertService import WebhookAlertService
from api.alerts.integration.integ_constants import (
    CIRCUIT_BREAKER_DEFAULTS,
    CACHE_KEYS,
    CACHE_TIMEOUTS
)

logger = logging.getLogger(__name__)


class CircuitBreakerState(Enum):
    """Circuit breaker states"""
    CLOSED = 'closed'
    OPEN = 'open'
    HALF_OPEN = 'half_open'


class CircuitBreaker:
    """
    Circuit breaker implementation for integration resilience
    Integrates with SMS gateway logic and existing alert validation
    """
    
    def __init__(self, name: str = None, failure_threshold: int = None, timeout: int = None,
                 expected_exception: type = Exception, recovery_timeout: int = None):
        self.name = name or f"circuit_breaker_{id(self)}"
        self.failure_threshold = failure_threshold or CIRCUIT_BREAKER_DEFAULTS['failure_threshold']
        # Accept both `timeout` (short public alias) and `recovery_timeout` (original name)
        self.recovery_timeout = (
            timeout if timeout is not None else
            recovery_timeout if recovery_timeout is not None else
            CIRCUIT_BREAKER_DEFAULTS['recovery_timeout']
        )
        self.expected_exception = expected_exception or CIRCUIT_BREAKER_DEFAULTS['expected_exception']
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitBreakerState.CLOSED
        self.lock = threading.RLock()
        
        # Statistics
        self.total_calls = 0
        self.successful_calls = 0
        self.failed_calls = 0
        self.circuit_opened_count = 0
        
        logger.info(f"Circuit breaker initialized: {self.name}")
    
    def __call__(self, func: Callable) -> Callable:
        """
        Decorator for circuit breaker protection
        """
        def wrapper(*args, **kwargs):
            return self.call(func, *args, **kwargs)
        return wrapper
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection
        """
        with self.lock:
            self.total_calls += 1
            
            if self.state == CircuitBreakerState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitBreakerState.HALF_OPEN
                    logger.info(f"Circuit breaker {self.name} transitioning to HALF_OPEN")
                else:
                    self.failed_calls += 1
                    raise CircuitBreakerOpenException(f"Circuit breaker {self.name} is OPEN")
            
            try:
                result = func(*args, **kwargs)
                self._on_success()
                return result
                
            except self.expected_exception:
                self._on_failure()
                raise
            except Exception:
                self._on_failure()
                raise
    
    def _should_attempt_reset(self) -> bool:
        """
        Check if circuit breaker should attempt reset
        """
        return (self.last_failure_time and 
                time.time() - self.last_failure_time >= self.recovery_timeout)
    
    def _on_success(self):
        """
        Handle successful call
        """
        self.failure_count = 0
        self.successful_calls += 1
        
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.state = CircuitBreakerState.CLOSED
            logger.info(f"Circuit breaker {self.name} transitioning to CLOSED")
    
    def _on_failure(self):
        """
        Handle failed call
        """
        self.failure_count += 1
        self.failed_calls += 1
        self.last_failure_time = time.time()
        
        if self.state == CircuitBreakerState.CLOSED:
            if self.failure_count >= self.failure_threshold:
                self.state = CircuitBreakerState.OPEN
                self.circuit_opened_count += 1
                logger.warning(f"Circuit breaker {self.name} transitioning to OPEN (failures: {self.failure_count})")
        
        elif self.state == CircuitBreakerState.HALF_OPEN:
            self.state = CircuitBreakerState.OPEN
            self.circuit_opened_count += 1
            logger.warning(f"Circuit breaker {self.name} transitioning back to OPEN")
    
    def reset(self):
        """
        Reset circuit breaker to closed state
        """
        with self.lock:
            self.failure_count = 0
            self.last_failure_time = None
            self.state = CircuitBreakerState.CLOSED
            logger.info(f"Circuit breaker {self.name} reset to CLOSED")
    
    def get_state(self) -> CircuitBreakerState:
        """
        Get current circuit breaker state
        """
        return self.state
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get circuit breaker statistics
        """
        with self.lock:
            success_rate = (self.successful_calls / max(self.total_calls, 1)) * 100
            failure_rate = (self.failed_calls / max(self.total_calls, 1)) * 100
            
            return {
                'name': self.name,
                'state': self.state.value,
                'failure_count': self.failure_count,
                'failure_threshold': self.failure_threshold,
                'recovery_timeout': self.recovery_timeout,
                'last_failure_time': self.last_failure_time,
                'total_calls': self.total_calls,
                'successful_calls': self.successful_calls,
                'failed_calls': self.failed_calls,
                'success_rate': success_rate,
                'failure_rate': failure_rate,
                'circuit_opened_count': self.circuit_opened_count
            }


class CircuitBreakerOpenException(Exception):
    """
    Exception raised when circuit breaker is open
    """
    pass


class SMSGatewayCircuitBreaker(CircuitBreaker):
    """
    Specialized circuit breaker for SMS gateway integration
    Integrates with existing SMS gateway logic and validation
    """
    
    def __init__(self, sms_gateway_url: str = None, api_key: str = None, **kwargs):
        super().__init__(name="sms_gateway_circuit_breaker", **kwargs)
        self.sms_gateway_url = sms_gateway_url or getattr(settings, 'SMS_GATEWAY_URL', '')
        self.api_key = api_key or getattr(settings, 'SMS_API_KEY', '')
        self.last_sms_success = None
        self.last_sms_failure = None
    
    def send_sms_with_circuit_breaker(self, phone_number: str, message: str, 
                                    config: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Send SMS with circuit breaker protection
        Validates SMS configuration using existing validators
        """
        try:
            # Validate SMS configuration
            if config:
                from api.alerts.validators import validate_channel_config
                validation_result = validate_channel_config(config, 'sms')
                if not validation_result['valid']:
                    return {
                        'success': False,
                        'error': 'Invalid SMS configuration',
                        'validation_errors': validation_result['errors']
                    }
            
            # Use circuit breaker for SMS sending
            return self.call(self._send_sms_internal, phone_number, message, config)
            
        except CircuitBreakerOpenException as e:
            logger.error(f"SMS circuit breaker is open: {e}")
            return {
                'success': False,
                'error': 'SMS service temporarily unavailable (circuit breaker open)',
                'retry_after': self.recovery_timeout
            }
        except Exception as e:
            logger.error(f"Error sending SMS with circuit breaker: {e}")
            return {
                'success': False,
                'error': 'Operation failed'
            }
    
    def _send_sms_internal(self, phone_number: str, message: str, 
                          config: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Internal SMS sending logic
        Integrates with existing SMS gateway
        """
        try:
            # Validate phone number
            if not self._validate_phone_number(phone_number):
                raise ValueError(f"Invalid phone number: {phone_number}")
            
            # Validate message
            if not message or len(message.strip()) == 0:
                raise ValueError("Message cannot be empty")
            
            # Prepare SMS request
            sms_data = {
                'to': phone_number,
                'message': message,
                'api_key': self.api_key or config.get('api_key'),
                'from': config.get('from_number', 'Alerts')
            }
            
            # Send SMS through gateway
            result = self._call_sms_gateway(sms_data)
            
            # Update success timestamp
            self.last_sms_success = django_tz.now().isoformat()
            
            logger.info(f"SMS sent successfully to {phone_number}")
            return {
                'success': True,
                'message_id': result.get('message_id'),
                'status': result.get('status', 'sent'),
                'timestamp': self.last_sms_success
            }
            
        except Exception as e:
            self.last_sms_failure = django_tz.now().isoformat()
            logger.error(f"SMS sending failed: {e}")
            raise
    
    def _validate_phone_number(self, phone_number: str) -> bool:
        """
        Validate phone number format
        """
        import re
        # Basic phone number validation
        phone_pattern = re.compile(r'^\+?[1-9]\d{1,14}$')
        return bool(phone_pattern.match(phone_number.replace('-', '').replace(' ', '')))
    
    def _call_sms_gateway(self, sms_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call SMS gateway API
        Integrates with existing SMS gateway logic
        """
        try:
            import requests
            
            # Use configured gateway URL or fallback
            gateway_url = self.sms_gateway_url or sms_data.get('gateway_url', '')
            if not gateway_url:
                raise ValueError("SMS gateway URL not configured")
            
            # Make API request
            response = requests.post(
                gateway_url,
                json=sms_data,
                timeout=30,
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {sms_data.get("api_key", "")}'
                }
            )
            
            response.raise_for_status()
            
            result = response.json()
            
            # Check for API errors
            if result.get('status') == 'error':
                raise ValueError(f"SMS gateway error: {result.get('message', 'Unknown error')}")
            
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(f"SMS gateway request failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Error calling SMS gateway: {e}")
            raise
    
    def get_sms_stats(self) -> Dict[str, Any]:
        """
        Get SMS-specific statistics
        """
        base_stats = self.get_stats()
        
        sms_stats = {
            'last_sms_success': self.last_sms_success,
            'last_sms_failure': self.last_sms_failure,
            'sms_gateway_url': self.sms_gateway_url,
            'api_configured': bool(self.api_key)
        }
        
        return {**base_stats, **sms_stats}


class WebhookCircuitBreaker(CircuitBreaker):
    """
    Specialized circuit breaker for webhook integration
    Integrates with existing WebhookAlertService
    """
    
    def __init__(self, **kwargs):
        super().__init__(name="webhook_circuit_breaker", **kwargs)
        self.webhook_service = WebhookAlertService()
    
    def send_webhook_with_circuit_breaker(self, url: str, data: Dict[str, Any], 
                                        config: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Send webhook with circuit breaker protection
        Validates webhook configuration using existing validators
        """
        try:
            # Validate webhook URL
            from api.alerts.validators import validate_webhook_url
            url_validation = validate_webhook_url(url)
            if not url_validation['valid']:
                return {
                    'success': False,
                    'error': 'Invalid webhook URL',
                    'validation_errors': url_validation['errors']
                }
            
            # Use circuit breaker for webhook sending
            return self.call(self._send_webhook_internal, url, data, config)
            
        except CircuitBreakerOpenException as e:
            logger.error(f"Webhook circuit breaker is open: {e}")
            return {
                'success': False,
                'error': 'Webhook service temporarily unavailable (circuit breaker open)',
                'retry_after': self.recovery_timeout
            }
        except Exception as e:
            logger.error(f"Error sending webhook with circuit breaker: {e}")
            return {
                'success': False,
                'error': 'Operation failed'
            }
    
    def _send_webhook_internal(self, url: str, data: Dict[str, Any], 
                              config: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Internal webhook sending logic
        Uses existing WebhookAlertService
        """
        try:
            # Use existing webhook service
            result = self.webhook_service.send_webhook(url, data, config or {})
            
            logger.info(f"Webhook sent successfully to {url}")
            return {
                'success': True,
                'status_code': result.get('status_code', 200),
                'response': result.get('response', ''),
                'timestamp': django_tz.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Webhook sending failed: {e}")
            raise


class CircuitBreakerManager:
    """
    Manages multiple circuit breakers
    """
    
    def __init__(self):
        self.circuit_breakers = {}
        self._initialize_default_breakers()
    
    def _initialize_default_breakers(self):
        """
        Initialize default circuit breakers
        """
        self.circuit_breakers = {
            'sms': SMSGatewayCircuitBreaker(),
            'webhook': WebhookCircuitBreaker(),
            'email': CircuitBreaker(name="email_circuit_breaker"),
            'default': CircuitBreaker(name="default_circuit_breaker")
        }
    
    def get_circuit_breaker(self, name: str) -> Optional[CircuitBreaker]:
        """
        Get circuit breaker by name
        """
        return self.circuit_breakers.get(name)
    
    def register_circuit_breaker(self, name: str, circuit_breaker: CircuitBreaker):
        """
        Register new circuit breaker
        """
        self.circuit_breakers[name] = circuit_breaker
        logger.info(f"Registered circuit breaker: {name}")

    def get_or_create(self, name: str, **kwargs) -> CircuitBreaker:
        """
        Get the circuit breaker registered under `name`, creating and
        registering a new one if it doesn't exist yet. Extra keyword
        args (failure_threshold, recovery_timeout, expected_exception)
        seed the breaker's config only when a new one is created.
        """
        existing = self.get_circuit_breaker(name)
        if existing is not None:
            return existing
        breaker = CircuitBreaker(name=name, **kwargs)
        self.register_circuit_breaker(name, breaker)
        return breaker
    
    def get_all_stats(self) -> Dict[str, Any]:
        """
        Get statistics for all circuit breakers
        """
        stats = {}
        for name, breaker in self.circuit_breakers.items():
            stats[name] = breaker.get_stats()
        
        return {
            'circuit_breakers': stats,
            'total_breakers': len(self.circuit_breakers),
            'timestamp': django_tz.now().isoformat()
        }
    
    def reset_all_breakers(self):
        """
        Reset all circuit breakers
        """
        for name, breaker in self.circuit_breakers.items():
            breaker.reset()
        
        logger.info("All circuit breakers reset")
    
    def get_breakers_by_state(self, state: CircuitBreakerState) -> List[str]:
        """
        Get circuit breakers by state
        """
        return [
            name for name, breaker in self.circuit_breakers.items()
            if breaker.get_state() == state
        ]


# Global circuit breaker manager
circuit_breaker_manager = CircuitBreakerManager()


# Decorator for circuit breaker protection
def circuit_breaker_protected(breaker_name: str = 'default'):
    """
    Decorator for circuit breaker protection
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            breaker = circuit_breaker_manager.get_circuit_breaker(breaker_name)
            if breaker:
                return breaker.call(func, *args, **kwargs)
            else:
                return func(*args, **kwargs)
        return wrapper
    return decorator


# Utility functions
def send_sms_with_protection(phone_number: str, message: str, 
                           config: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Send SMS with circuit breaker protection
    """
    sms_breaker = circuit_breaker_manager.get_circuit_breaker('sms')
    if sms_breaker and isinstance(sms_breaker, SMSGatewayCircuitBreaker):
        return sms_breaker.send_sms_with_circuit_breaker(phone_number, message, config)
    else:
        raise ValueError("SMS circuit breaker not available")


def send_webhook_with_protection(url: str, data: Dict[str, Any], 
                                config: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Send webhook with circuit breaker protection
    """
    webhook_breaker = circuit_breaker_manager.get_circuit_breaker('webhook')
    if webhook_breaker and isinstance(webhook_breaker, WebhookCircuitBreaker):
        return webhook_breaker.send_webhook_with_circuit_breaker(url, data, config)
    else:
        raise ValueError("Webhook circuit breaker not available")


def get_circuit_breaker_statistics() -> Dict[str, Any]:
    """
    Get circuit breaker statistics
    """
    return circuit_breaker_manager.get_all_stats()


def reset_circuit_breaker(breaker_name: str) -> bool:
    """
    Reset specific circuit breaker
    """
    breaker = circuit_breaker_manager.get_circuit_breaker(breaker_name)
    if breaker:
        breaker.reset()
        return True
    return False


def get_open_circuit_breakers() -> List[str]:
    """
    Get list of open circuit breakers
    """
    return circuit_breaker_manager.get_breakers_by_state(CircuitBreakerState.OPEN)
