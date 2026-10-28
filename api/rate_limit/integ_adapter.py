# api/rate_limit/integ_adapter.py
"""
Integration adapters for rate limit module.

Provides adapter pattern for external system integrations.
"""

import logging
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
import requests
import json

from api.rate_limit.integ_constants import IntegrationType, IntegrationStatus
from api.rate_limit.integ_exceptions import IntegrationError, IntegrationTimeoutError

logger = logging.getLogger(__name__)


class BaseIntegrationAdapter:
    """
    Base class for integration adapters.
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = self.__class__.__name__
        self.type = IntegrationType.CUSTOM
        self.status = IntegrationStatus.INACTIVE
        self.last_activity = None
        self.error_count = 0
        self.max_errors = 10
        self.timeout = 30  # seconds
    
    def test_connection(self) -> Dict[str, Any]:
        """
        Test connection to the integration.
        
        Returns:
            Connection test result
        """
        raise NotImplementedError("Subclasses must implement test_connection()")
    
    def execute(self, action: str, data: Dict[str, Any] = None, **kwargs) -> Dict[str, Any]:
        """
        Execute an integration action.
        
        Args:
            action: Action to execute
            data: Action data
            **kwargs: Additional parameters
            
        Returns:
            Execution result
        """
        raise NotImplementedError("Subclasses must implement execute()")
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check.
        
        Returns:
            Health check result
        """
        try:
            # Test connection
            connection_result = self.test_connection()
            
            if not connection_result.get('success', False):
                return {
                    'healthy': False,
                    'message': f"Connection test failed: {connection_result.get('error', 'Unknown error')}",
                    'details': connection_result
                }
            
            # Check error count
            if self.error_count >= self.max_errors:
                return {
                    'healthy': False,
                    'message': f"Too many errors: {self.error_count}/{self.max_errors}",
                    'details': {'error_count': self.error_count}
                }
            
            # Check last activity
            if self.last_activity:
                inactive_hours = (timezone.now() - self.last_activity).total_seconds() / 3600
                if inactive_hours > 24:
                    return {
                        'healthy': False,
                        'message': f"Inactive for {inactive_hours:.1f} hours",
                        'details': {'inactive_hours': inactive_hours}
                    }
            
            return {
                'healthy': True,
                'message': 'Integration is healthy',
                'details': {
                    'status': self.status,
                    'last_activity': self.last_activity.isoformat() if self.last_activity else None,
                    'error_count': self.error_count
                }
            }
            
        except Exception as e:
            return {
                'healthy': False,
                'message': f"Health check failed: {str(e)}",
                'details': {'error': str(e)}
            }
    
    def cleanup(self):
        """Clean up adapter resources."""
        pass
    
    def handle_rate_limit_exceeded(self, data: Dict[str, Any]):
        """
        Handle rate limit exceeded events.
        
        Args:
            data: Event data
        """
        pass
    
    def handle_abuse_detected(self, data: Dict[str, Any]):
        """
        Handle abuse detected events.
        
        Args:
            data: Event data
        """
        pass
    
    def handle_config_updated(self, data: Dict[str, Any]):
        """
        Handle configuration update events.
        
        Args:
            data: Event data
        """
        pass
    
    def handle_user_profile_updated(self, data: Dict[str, Any]):
        """
        Handle user profile update events.
        
        Args:
            data: Event data
        """
        pass


class WebhookAdapter(BaseIntegrationAdapter):
    """
    Adapter for webhook integrations.
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.type = IntegrationType.WEBHOOK
        self.webhook_url = config.get('webhook_url')
        self.secret_key = config.get('secret_key')
        self.headers = config.get('headers', {})
        self.timeout = config.get('timeout', 30)
    
    def test_connection(self) -> Dict[str, Any]:
        """Test webhook connection."""
        try:
            # Send test webhook
            test_data = {
                'event': 'test',
                'timestamp': timezone.now().isoformat(),
                'source': 'rate_limit_module'
            }
            
            response = self._send_webhook('test', test_data)
            
            return {
                'success': True,
                'status_code': response.status_code,
                'response_time': response.elapsed.total_seconds()
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def execute(self, action: str, data: Dict[str, Any] = None, **kwargs) -> Dict[str, Any]:
        """Execute webhook action."""
        try:
            webhook_data = {
                'action': action,
                'data': data or {},
                'timestamp': timezone.now().isoformat(),
                **kwargs
            }
            
            response = self._send_webhook(action, webhook_data)
            
            # Update activity
            self.last_activity = timezone.now()
            
            return {
                'success': True,
                'status_code': response.status_code,
                'response_data': response.text,
                'response_time': response.elapsed.total_seconds()
            }
            
        except Exception as e:
            self.error_count += 1
            logger.error(f"Webhook execution failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _send_webhook(self, action: str, data: Dict[str, Any]) -> requests.Response:
        """Send webhook request."""
        if not self.webhook_url:
            raise IntegrationError("Webhook URL not configured")
        
        # Prepare headers
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'RateLimit-Integration/1.0'
        }
        headers.update(self.headers)
        
        # Add signature if secret key is provided
        if self.secret_key:
            import hmac
            import hashlib
            
            payload = json.dumps(data, sort_keys=True).encode()
            signature = hmac.new(
                self.secret_key.encode(),
                payload,
                hashlib.sha256
            ).hexdigest()
            
            headers['X-RateLimit-Signature'] = signature
        
        # Send request
        response = requests.post(
            self.webhook_url,
            json=data,
            headers=headers,
            timeout=self.timeout
        )
        
        response.raise_for_status()
        return response
    
    def handle_rate_limit_exceeded(self, data: Dict[str, Any]):
        """Handle rate limit exceeded events."""
        self.execute('rate_limit_exceeded', data)
    
    def handle_abuse_detected(self, data: Dict[str, Any]):
        """Handle abuse detected events."""
        self.execute('abuse_detected', data)
    
    def handle_config_updated(self, data: Dict[str, Any]):
        """Handle configuration update events."""
        self.execute('config_updated', data)
    
    def handle_user_profile_updated(self, data: Dict[str, Any]):
        """Handle user profile update events."""
        self.execute('user_profile_updated', data)


class APIAdapter(BaseIntegrationAdapter):
    """
    Adapter for REST API integrations.
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.type = IntegrationType.API
        self.base_url = config.get('base_url')
        self.api_key = config.get('api_key')
        self.auth_type = config.get('auth_type', 'api_key')
        self.headers = config.get('headers', {})
        self.timeout = config.get('timeout', 30)
    
    def test_connection(self) -> Dict[str, Any]:
        """Test API connection."""
        try:
            # Send test request to health endpoint
            response = self._send_request('GET', '/health')
            
            return {
                'success': True,
                'status_code': response.status_code,
                'response_time': response.elapsed.total_seconds()
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def execute(self, action: str, data: Dict[str, Any] = None, **kwargs) -> Dict[str, Any]:
        """Execute API action."""
        try:
            # Map actions to endpoints
            endpoint_map = {
                'rate_limit_exceeded': '/rate-limit/events',
                'abuse_detected': '/abuse/events',
                'config_updated': '/config/events',
                'user_profile_updated': '/user/events'
            }
            
            endpoint = endpoint_map.get(action, '/events')
            
            # Prepare request data
            request_data = {
                'event': action,
                'data': data or {},
                'timestamp': timezone.now().isoformat(),
                **kwargs
            }
            
            response = self._send_request('POST', endpoint, request_data)
            
            # Update activity
            self.last_activity = timezone.now()
            
            return {
                'success': True,
                'status_code': response.status_code,
                'response_data': response.json() if response.content else {},
                'response_time': response.elapsed.total_seconds()
            }
            
        except Exception as e:
            self.error_count += 1
            logger.error(f"API execution failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _send_request(self, method: str, endpoint: str, data: Dict[str, Any] = None) -> requests.Response:
        """Send API request."""
        if not self.base_url:
            raise IntegrationError("Base URL not configured")
        
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        
        # Prepare headers
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'RateLimit-Integration/1.0'
        }
        headers.update(self.headers)
        
        # Add authentication
        if self.auth_type == 'api_key' and self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'
        elif self.auth_type == 'header' and self.api_key:
            headers['X-API-Key'] = self.api_key
        
        # Send request
        if method.upper() == 'GET':
            response = requests.get(url, headers=headers, timeout=self.timeout)
        elif method.upper() == 'POST':
            response = requests.post(url, json=data, headers=headers, timeout=self.timeout)
        elif method.upper() == 'PUT':
            response = requests.put(url, json=data, headers=headers, timeout=self.timeout)
        elif method.upper() == 'DELETE':
            response = requests.delete(url, headers=headers, timeout=self.timeout)
        else:
            raise IntegrationError(f"Unsupported HTTP method: {method}")
        
        response.raise_for_status()
        return response
    
    def handle_rate_limit_exceeded(self, data: Dict[str, Any]):
        """Handle rate limit exceeded events."""
        self.execute('rate_limit_exceeded', data)
    
    def handle_abuse_detected(self, data: Dict[str, Any]):
        """Handle abuse detected events."""
        self.execute('abuse_detected', data)
    
    def handle_config_updated(self, data: Dict[str, Any]):
        """Handle configuration update events."""
        self.execute('config_updated', data)
    
    def handle_user_profile_updated(self, data: Dict[str, Any]):
        """Handle user profile update events."""
        self.execute('user_profile_updated', data)


class DatabaseAdapter(BaseIntegrationAdapter):
    """
    Adapter for database integrations.
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.type = IntegrationType.DATABASE
        self.database_url = config.get('database_url')
        self.table_name = config.get('table_name', 'integration_events')
    
    def test_connection(self) -> Dict[str, Any]:
        """Test database connection."""
        try:
            # Simple connection test
            # In a real implementation, you'd use the appropriate database driver
            return {
                'success': True,
                'message': 'Database connection successful'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def execute(self, action: str, data: Dict[str, Any] = None, **kwargs) -> Dict[str, Any]:
        """Execute database action."""
        try:
            # Store event in database
            record = {
                'action': action,
                'data': data or {},
                'timestamp': timezone.now().isoformat(),
                **kwargs
            }
            
            # In a real implementation, you'd use the appropriate database driver
            # For now, we'll just log the action
            logger.info(f"Database integration: {action} - {record}")
            
            # Update activity
            self.last_activity = timezone.now()
            
            return {
                'success': True,
                'record_id': 'mock_id',  # In real implementation, return actual ID
                'timestamp': record['timestamp']
            }
            
        except Exception as e:
            self.error_count += 1
            logger.error(f"Database execution failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def handle_rate_limit_exceeded(self, data: Dict[str, Any]):
        """Handle rate limit exceeded events."""
        self.execute('rate_limit_exceeded', data)
    
    def handle_abuse_detected(self, data: Dict[str, Any]):
        """Handle abuse detected events."""
        self.execute('abuse_detected', data)
    
    def handle_config_updated(self, data: Dict[str, Any]):
        """Handle configuration update events."""
        self.execute('config_updated', data)
    
    def handle_user_profile_updated(self, data: Dict[str, Any]):
        """Handle user profile update events."""
        self.execute('user_profile_updated', data)


class MessageQueueAdapter(BaseIntegrationAdapter):
    """
    Adapter for message queue integrations.
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.type = IntegrationType.MESSAGE_QUEUE
        self.queue_name = config.get('queue_name', 'rate_limit_events')
        self.connection_url = config.get('connection_url')
        self.exchange = config.get('exchange', 'rate_limit')
    
    def test_connection(self) -> Dict[str, Any]:
        """Test message queue connection."""
        try:
            # In a real implementation, you'd connect to the message queue
            return {
                'success': True,
                'message': 'Message queue connection successful'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def execute(self, action: str, data: Dict[str, Any] = None, **kwargs) -> Dict[str, Any]:
        """Execute message queue action."""
        try:
            # Prepare message
            message = {
                'action': action,
                'data': data or {},
                'timestamp': timezone.now().isoformat(),
                **kwargs
            }
            
            # In a real implementation, you'd publish to the message queue
            # For now, we'll just log the message
            logger.info(f"Message queue integration: {action} - {message}")
            
            # Update activity
            self.last_activity = timezone.now()
            
            return {
                'success': True,
                'message_id': 'mock_id',  # In real implementation, return actual ID
                'timestamp': message['timestamp']
            }
            
        except Exception as e:
            self.error_count += 1
            logger.error(f"Message queue execution failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def handle_rate_limit_exceeded(self, data: Dict[str, Any]):
        """Handle rate limit exceeded events."""
        self.execute('rate_limit_exceeded', data)
    
    def handle_abuse_detected(self, data: Dict[str, Any]):
        """Handle abuse detected events."""
        self.execute('abuse_detected', data)
    
    def handle_config_updated(self, data: Dict[str, Any]):
        """Handle configuration update events."""
        self.execute('config_updated', data)
    
    def handle_user_profile_updated(self, data: Dict[str, Any]):
        """Handle user profile update events."""
        self.execute('user_profile_updated', data)


class EmailAdapter(BaseIntegrationAdapter):
    """
    Adapter for email integrations.
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.type = IntegrationType.EMAIL
        self.smtp_host = config.get('smtp_host')
        self.smtp_port = config.get('smtp_port', 587)
        self.smtp_username = config.get('smtp_username')
        self.smtp_password = config.get('smtp_password')
        self.from_email = config.get('from_email')
        self.to_emails = config.get('to_emails', [])
    
    def test_connection(self) -> Dict[str, Any]:
        """Test email connection."""
        try:
            # In a real implementation, you'd test SMTP connection
            return {
                'success': True,
                'message': 'Email connection successful'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def execute(self, action: str, data: Dict[str, Any] = None, **kwargs) -> Dict[str, Any]:
        """Execute email action."""
        try:
            # Prepare email content
            subject = f"Rate Limit Event: {action}"
            
            email_body = f"""
            Rate Limit Event Notification
            
            Event: {action}
            Timestamp: {timezone.now().isoformat()}
            Data: {json.dumps(data or {}, indent=2)}
            """
            
            # In a real implementation, you'd send the email
            # For now, we'll just log the email
            logger.info(f"Email integration: {subject} - {email_body}")
            
            # Update activity
            self.last_activity = timezone.now()
            
            return {
                'success': True,
                'subject': subject,
                'recipients': self.to_emails,
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            self.error_count += 1
            logger.error(f"Email execution failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def handle_rate_limit_exceeded(self, data: Dict[str, Any]):
        """Handle rate limit exceeded events."""
        self.execute('rate_limit_exceeded', data)
    
    def handle_abuse_detected(self, data: Dict[str, Any]):
        """Handle abuse detected events."""
        self.execute('abuse_detected', data)
    
    def handle_config_updated(self, data: Dict[str, Any]):
        """Handle configuration update events."""
        self.execute('config_updated', data)
    
    def handle_user_profile_updated(self, data: Dict[str, Any]):
        """Handle user profile update events."""
        self.execute('user_profile_updated', data)


class SlackAdapter(BaseIntegrationAdapter):
    """
    Adapter for Slack integrations.
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.type = IntegrationType.SLACK
        self.webhook_url = config.get('webhook_url')
        self.channel = config.get('channel', '#general')
        self.username = config.get('username', 'RateLimitBot')
    
    def test_connection(self) -> Dict[str, Any]:
        """Test Slack connection."""
        try:
            # Send test message
            test_message = {
                'text': 'Rate Limit Integration Test',
                'channel': self.channel,
                'username': self.username
            }
            
            response = self._send_slack_message(test_message)
            
            return {
                'success': True,
                'status_code': response.status_code,
                'response_time': response.elapsed.total_seconds()
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def execute(self, action: str, data: Dict[str, Any] = None, **kwargs) -> Dict[str, Any]:
        """Execute Slack action."""
        try:
            # Prepare Slack message
            message = {
                'text': f'Rate Limit Event: {action}',
                'channel': self.channel,
                'username': self.username,
                'attachments': [
                    {
                        'color': 'warning' if action == 'abuse_detected' else 'good',
                        'fields': [
                            {
                                'title': 'Event',
                                'value': action,
                                'short': True
                            },
                            {
                                'title': 'Timestamp',
                                'value': timezone.now().isoformat(),
                                'short': True
                            }
                        ],
                        'text': json.dumps(data or {}, indent=2)
                    }
                ]
            }
            
            response = self._send_slack_message(message)
            
            # Update activity
            self.last_activity = timezone.now()
            
            return {
                'success': True,
                'status_code': response.status_code,
                'response_time': response.elapsed.total_seconds()
            }
            
        except Exception as e:
            self.error_count += 1
            logger.error(f"Slack execution failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _send_slack_message(self, message: Dict[str, Any]) -> requests.Response:
        """Send Slack message."""
        if not self.webhook_url:
            raise IntegrationError("Slack webhook URL not configured")
        
        response = requests.post(
            self.webhook_url,
            json=message,
            timeout=self.timeout
        )
        
        response.raise_for_status()
        return response
    
    def handle_rate_limit_exceeded(self, data: Dict[str, Any]):
        """Handle rate limit exceeded events."""
        self.execute('rate_limit_exceeded', data)
    
    def handle_abuse_detected(self, data: Dict[str, Any]):
        """Handle abuse detected events."""
        self.execute('abuse_detected', data)
    
    def handle_config_updated(self, data: Dict[str, Any]):
        """Handle configuration update events."""
        self.execute('config_updated', data)
    
    def handle_user_profile_updated(self, data: Dict[str, Any]):
        """Handle user profile update events."""
        self.execute('user_profile_updated', data)


# Adapter factory
class AdapterFactory:
    """
    Factory for creating integration adapters.
    """
    
    _adapters = {
        'webhook': WebhookAdapter,
        'api': APIAdapter,
        'database': DatabaseAdapter,
        'message_queue': MessageQueueAdapter,
        'email': EmailAdapter,
        'slack': SlackAdapter
    }
    
    @classmethod
    def create_adapter(cls, adapter_type: str, config: Dict[str, Any]) -> BaseIntegrationAdapter:
        """
        Create an adapter instance.
        
        Args:
            adapter_type: Type of adapter
            config: Adapter configuration
            
        Returns:
            Adapter instance
        """
        adapter_class = cls._adapters.get(adapter_type.lower())
        
        if not adapter_class:
            raise IntegrationError(f"Unknown adapter type: {adapter_type}")
        
        return adapter_class(config)
    
    @classmethod
    def register_adapter(cls, adapter_type: str, adapter_class: type):
        """
        Register a custom adapter.
        
        Args:
            adapter_type: Type identifier
            adapter_class: Adapter class
        """
        cls._adapters[adapter_type.lower()] = adapter_class
    
    @classmethod
    def get_available_adapters(cls) -> List[str]:
        """
        Get list of available adapter types.
        
        Returns:
            List of adapter types
        """
        return list(cls._adapters.keys())


# Export classes and functions
__all__ = [
    'BaseIntegrationAdapter',
    'WebhookAdapter',
    'APIAdapter',
    'DatabaseAdapter',
    'MessageQueueAdapter',
    'EmailAdapter',
    'SlackAdapter',
    'AdapterFactory'
]
