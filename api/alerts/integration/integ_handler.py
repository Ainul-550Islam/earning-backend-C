"""
Integration Handler for alerts app - Core connector for external system integrations
"""
import json
import logging
from api.alerts.sql_utils import safe_identifier
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Callable
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


class IntegrationHandler(ABC):
    """Abstract base class for integration handlers"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = self.__class__.__name__
        self.enabled = config.get('enabled', True)
        self.timeout = config.get('timeout', 30)
        self.retry_count = config.get('retry_count', 3)
        self.retry_delay = config.get('retry_delay', 60)
        
    @abstractmethod
    def connect(self) -> bool:
        """Establish connection to external system"""
        pass
    
    @abstractmethod
    def disconnect(self) -> bool:
        """Close connection to external system"""
        pass
    
    @abstractmethod
    def send_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Send data to external system"""
        pass
    
    @abstractmethod
    def receive_data(self) -> List[Dict[str, Any]]:
        """Receive data from external system"""
        pass
    
    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """Check health of integration"""
        pass
    
    def is_connected(self) -> bool:
        """Check if connection is active"""
        return getattr(self, '_connected', False)
    
    def get_config(self) -> Dict[str, Any]:
        """Get integration configuration"""
        return self.config.copy()
    
    def update_config(self, new_config: Dict[str, Any]) -> bool:
        """Update integration configuration"""
        try:
            self.config.update(new_config)
            self.enabled = self.config.get('enabled', True)
            self.timeout = self.config.get('timeout', 30)
            self.retry_count = self.config.get('retry_count', 3)
            self.retry_delay = self.config.get('retry_delay', 60)
            return True
        except Exception as e:
            logger.error(f"Error updating config for {self.name}: {e}")
            return False
    
    def log_activity(self, activity_type: str, details: Dict[str, Any] = None):
        """Log integration activity"""
        log_entry = {
            'integration': self.name,
            'activity_type': activity_type,
            'timestamp': timezone.now().isoformat(),
            'details': details or {}
        }
        
        logger.info(f"Integration Activity: {json.dumps(log_entry)}")
        
        # Store in cache for recent activity
        cache_key = f"integ_activity_{self.name}"
        recent_activities = cache.get(cache_key, [])
        recent_activities.append(log_entry)
        
        # Keep only last 100 activities
        if len(recent_activities) > 100:
            recent_activities = recent_activities[-100:]
        
        cache.set(cache_key, recent_activities, timeout=3600)
    
    def get_recent_activity(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent integration activity"""
        cache_key = f"integ_activity_{self.name}"
        activities = cache.get(cache_key, [])
        return activities[-limit:]


class AlertIntegrationHandler(IntegrationHandler):
    """Base handler for alert-specific integrations"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.alert_mappings = config.get('alert_mappings', {})
        self.severity_mappings = config.get('severity_mappings', {})
        self.field_mappings = config.get('field_mappings', {})
    
    def transform_alert(self, alert_data: Dict[str, Any]) -> Dict[str, Any]:
        """Transform alert data according to mappings"""
        transformed = {}
        
        # Apply field mappings
        for target_field, source_field in self.field_mappings.items():
            if source_field in alert_data:
                transformed[target_field] = alert_data[source_field]
        
        # Apply alert type mappings
        if 'alert_type' in alert_data:
            alert_type = alert_data['alert_type']
            if alert_type in self.alert_mappings:
                transformed['alert_type'] = self.alert_mappings[alert_type]
        
        # Apply severity mappings
        if 'severity' in alert_data:
            severity = alert_data['severity']
            if severity in self.severity_mappings:
                transformed['severity'] = self.severity_mappings[severity]
        
        return transformed
    
    def validate_alert(self, alert_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate alert data before sending"""
        required_fields = self.config.get('required_fields', [])
        errors = []
        
        for field in required_fields:
            if field not in alert_data:
                errors.append(f"Missing required field: {field}")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }


class WebhookIntegrationHandler(AlertIntegrationHandler):
    """Handler for webhook-based integrations"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.webhook_url = config.get('webhook_url')
        self.secret_key = config.get('secret_key')
        self.headers = config.get('headers', {})
        self.verify_ssl = config.get('verify_ssl', True)
        
    def connect(self) -> bool:
        """Test webhook connectivity"""
        try:
            import requests
            
            # Send test payload
            test_payload = {
                'type': 'connection_test',
                'timestamp': timezone.now().isoformat()
            }
            
            response = requests.post(
                self.webhook_url,
                json=test_payload,
                headers=self.headers,
                timeout=self.timeout,
                verify=self.verify_ssl
            )
            
            success = response.status_code == 200
            self._connected = success
            
            if success:
                self.log_activity('connection_established', {
                    'webhook_url': self.webhook_url,
                    'response_code': response.status_code
                })
            else:
                self.log_activity('connection_failed', {
                    'webhook_url': self.webhook_url,
                    'response_code': response.status_code,
                    'response_text': response.text
                })
            
            return success
            
        except Exception as e:
            logger.error(f"Webhook connection failed: {e}")
            self._connected = False
            return False
    
    def disconnect(self) -> bool:
        """Disconnect webhook (no-op for webhooks)"""
        self._connected = False
        self.log_activity('connection_closed')
        return True
    
    def send_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Send data via webhook"""
        if not self.is_connected():
            return {'success': False, 'error': 'Not connected'}
        
        try:
            import requests
            import hmac
            import hashlib
            
            # Transform alert data
            transformed_data = self.transform_alert(data)
            
            # Validate data
            validation = self.validate_alert(transformed_data)
            if not validation['valid']:
                return {
                    'success': False,
                    'error': 'Validation failed',
                    'errors': validation['errors']
                }
            
            # Add signature if secret key is configured
            if self.secret_key:
                payload_str = json.dumps(transformed_data, sort_keys=True)
                signature = hmac.new(
                    self.secret_key.encode(),
                    payload_str.encode(),
                    hashlib.sha256
                ).hexdigest()
                
                self.headers['X-Webhook-Signature'] = signature
            
            # Send webhook
            response = requests.post(
                self.webhook_url,
                json=transformed_data,
                headers=self.headers,
                timeout=self.timeout,
                verify=self.verify_ssl
            )
            
            success = response.status_code in [200, 201, 202]
            
            self.log_activity('data_sent', {
                'webhook_url': self.webhook_url,
                'response_code': response.status_code,
                'success': success,
                'data_size': len(json.dumps(transformed_data))
            })
            
            return {
                'success': success,
                'response_code': response.status_code,
                'response_text': response.text,
                'data_sent': transformed_data
            }
            
        except Exception as e:
            logger.error(f"Error sending webhook data: {e}")
            self.log_activity('send_failed', {'error': str(e)})
            return {
                'success': False,
                'error': 'Operation failed'
            }
    
    def receive_data(self) -> List[Dict[str, Any]]:
        """Webhook integrations typically don't receive data"""
        return []
    
    def health_check(self) -> Dict[str, Any]:
        """Check webhook health"""
        try:
            import requests
            
            # Send health check
            health_payload = {
                'type': 'health_check',
                'timestamp': timezone.now().isoformat()
            }
            
            response = requests.post(
                self.webhook_url,
                json=health_payload,
                headers=self.headers,
                timeout=self.timeout,
                verify=self.verify_ssl
            )
            
            return {
                'healthy': response.status_code == 200,
                'response_time': getattr(response, 'elapsed', None),
                'last_check': timezone.now().isoformat(),
                'webhook_url': self.webhook_url
            }
            
        except Exception:
            logger.exception("Unhandled error in health_check")
            return {
                'healthy': False,
                'error': 'Operation failed',
                'last_check': timezone.now().isoformat()
            }


class APIIntegrationHandler(AlertIntegrationHandler):
    """Handler for REST API integrations"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_base_url = config.get('api_base_url')
        self.api_key = config.get('api_key')
        self.api_version = config.get('api_version', 'v1')
        self.auth_type = config.get('auth_type', 'bearer')
        self.username = config.get('username')
        self.password = config.get('password')
        
    def connect(self) -> bool:
        """Test API connectivity"""
        try:
            import requests
            
            # Prepare authentication
            headers = self._get_auth_headers()
            
            # Test connection
            response = requests.get(
                f"{self.api_base_url}/health",
                headers=headers,
                timeout=self.timeout
            )
            
            success = response.status_code == 200
            self._connected = success
            
            if success:
                self.log_activity('connection_established', {
                    'api_base_url': self.api_base_url,
                    'response_code': response.status_code
                })
            else:
                self.log_activity('connection_failed', {
                    'api_base_url': self.api_base_url,
                    'response_code': response.status_code,
                    'response_text': response.text
                })
            
            return success
            
        except Exception as e:
            logger.error(f"API connection failed: {e}")
            self._connected = False
            return False
    
    def disconnect(self) -> bool:
        """Disconnect API (no-op for REST APIs)"""
        self._connected = False
        self.log_activity('connection_closed')
        return True
    
    def send_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Send data via API"""
        if not self.is_connected():
            return {'success': False, 'error': 'Not connected'}
        
        try:
            import requests
            
            # Transform alert data
            transformed_data = self.transform_alert(data)
            
            # Validate data
            validation = self.validate_alert(transformed_data)
            if not validation['valid']:
                return {
                    'success': False,
                    'error': 'Validation failed',
                    'errors': validation['errors']
                }
            
            # Prepare request
            headers = self._get_auth_headers()
            headers['Content-Type'] = 'application/json'
            
            # Send to API
            endpoint = self.config.get('alerts_endpoint', '/alerts')
            url = f"{self.api_base_url}/{self.api_version}{endpoint}"
            
            response = requests.post(
                url,
                json=transformed_data,
                headers=headers,
                timeout=self.timeout
            )
            
            success = response.status_code in [200, 201, 202]
            
            self.log_activity('data_sent', {
                'url': url,
                'response_code': response.status_code,
                'success': success,
                'data_size': len(json.dumps(transformed_data))
            })
            
            return {
                'success': success,
                'response_code': response.status_code,
                'response_text': response.text,
                'data_sent': transformed_data
            }
            
        except Exception as e:
            logger.error(f"Error sending API data: {e}")
            self.log_activity('send_failed', {'error': str(e)})
            return {
                'success': False,
                'error': 'Operation failed'
            }
    
    def receive_data(self) -> List[Dict[str, Any]]:
        """Receive data from API"""
        if not self.is_connected():
            return []
        
        try:
            import requests
            
            headers = self._get_auth_headers()
            endpoint = self.config.get('receive_endpoint', '/alerts')
            url = f"{self.api_base_url}/{self.api_version}{endpoint}"
            
            response = requests.get(
                url,
                headers=headers,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict) and 'results' in data:
                    return data['results']
            
            return []
            
        except Exception as e:
            logger.error(f"Error receiving API data: {e}")
            return []
    
    def health_check(self) -> Dict[str, Any]:
        """Check API health"""
        try:
            import requests
            
            headers = self._get_auth_headers()
            response = requests.get(
                f"{self.api_base_url}/health",
                headers=headers,
                timeout=self.timeout
            )
            
            return {
                'healthy': response.status_code == 200,
                'response_time': getattr(response, 'elapsed', None),
                'last_check': timezone.now().isoformat(),
                'api_base_url': self.api_base_url
            }
            
        except Exception:
            logger.exception("Unhandled error in health_check")
            return {
                'healthy': False,
                'error': 'Operation failed',
                'last_check': timezone.now().isoformat()
            }
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers"""
        headers = {}
        
        if self.auth_type == 'bearer':
            headers['Authorization'] = f"Bearer {self.api_key}"
        elif self.auth_type == 'api_key':
            headers['X-API-Key'] = self.api_key
        elif self.auth_type == 'basic':
            import base64
            credentials = f"{self.username}:{self.password}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()
            headers['Authorization'] = f"Basic {encoded_credentials}"
        
        return headers


class DatabaseIntegrationHandler(AlertIntegrationHandler):
    """Handler for database integrations"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.connection_string = config.get('connection_string')
        self.database_type = config.get('database_type', 'postgresql')
        self.table_name = config.get('table_name', 'alerts')
        
    def connect(self) -> bool:
        """Establish database connection"""
        try:
            if self.database_type == 'postgresql':
                import psycopg2
                self._connection = psycopg2.connect(self.connection_string)
            elif self.database_type == 'mysql':
                import mysql.connector
                self._connection = mysql.connector.connect(**self.connection_string)
            elif self.database_type == 'sqlite':
                import sqlite3
                self._connection = sqlite3.connect(self.connection_string)
            else:
                raise ValueError(f"Unsupported database type: {self.database_type}")
            
            self._connected = True
            self.log_activity('connection_established', {
                'database_type': self.database_type,
                'table_name': self.table_name
            })
            
            return True
            
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            self._connected = False
            return False
    
    def disconnect(self) -> bool:
        """Close database connection"""
        try:
            if hasattr(self, '_connection') and self._connection:
                self._connection.close()
                self._connected = False
                self.log_activity('connection_closed')
                return True
            return False
        except Exception as e:
            logger.error(f"Error closing database connection: {e}")
            return False
    
    def send_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Insert data into database"""
        if not self.is_connected():
            return {'success': False, 'error': 'Not connected'}
        
        try:
            # Transform alert data
            transformed_data = self.transform_alert(data)
            
            # Validate data
            validation = self.validate_alert(transformed_data)
            if not validation['valid']:
                return {
                    'success': False,
                    'error': 'Validation failed',
                    'errors': validation['errors']
                }
            
            # Insert into database
            cursor = self._connection.cursor()
            
            # Build INSERT query based on database type
            if self.database_type == 'postgresql':
                columns = ', '.join(safe_identifier(key, 'column name') for key in transformed_data.keys())
                placeholders = ', '.join(['%s'] * len(transformed_data))
                query = f"INSERT INTO {safe_identifier(self.table_name, 'table name')} ({columns}) VALUES ({placeholders})"  # nosec B608 - identifiers validated via sql_utils; values are bound parameters
                cursor.execute(query, list(transformed_data.values()))
            elif self.database_type == 'mysql':
                columns = ', '.join(safe_identifier(key, 'column name') for key in transformed_data.keys())
                placeholders = ', '.join(['%s'] * len(transformed_data))
                query = f"INSERT INTO {safe_identifier(self.table_name, 'table name')} ({columns}) VALUES ({placeholders})"  # nosec B608 - identifiers validated via sql_utils; values are bound parameters
                cursor.execute(query, list(transformed_data.values()))
            elif self.database_type == 'sqlite':
                columns = ', '.join(safe_identifier(key, 'column name') for key in transformed_data.keys())
                placeholders = ', '.join(['?'] * len(transformed_data))
                query = f"INSERT INTO {safe_identifier(self.table_name, 'table name')} ({columns}) VALUES ({placeholders})"  # nosec B608 - identifiers validated via sql_utils; values are bound parameters
                cursor.execute(query, list(transformed_data.values()))
            
            self._connection.commit()
            cursor.close()
            
            self.log_activity('data_sent', {
                'table_name': self.table_name,
                'records_inserted': 1,
                'data_size': len(json.dumps(transformed_data))
            })
            
            return {'success': True, 'records_inserted': 1}
            
        except Exception as e:
            logger.error(f"Error inserting database data: {e}")
            self.log_activity('send_failed', {'error': str(e)})
            return {
                'success': False,
                'error': 'Operation failed'
            }
    
    def receive_data(self) -> List[Dict[str, Any]]:
        """Query data from database"""
        if not self.is_connected():
            return []
        
        try:
            cursor = self._connection.cursor()
            
            # Build SELECT query
            query = f"SELECT * FROM {safe_identifier(self.table_name, 'table name')} ORDER BY created_at DESC LIMIT 100"  # nosec B608 - identifiers validated via sql_utils; values are bound parameters
            cursor.execute(query)
            
            # Get column names
            if self.database_type == 'postgresql':
                columns = [desc[0] for desc in cursor.description]
            elif self.database_type == 'mysql':
                columns = [desc[0] for desc in cursor.description]
            elif self.database_type == 'sqlite':
                columns = [desc[0] for desc in cursor.description]
            
            # Fetch and format results
            rows = cursor.fetchall()
            data = []
            for row in rows:
                data.append(dict(zip(columns, row)))
            
            cursor.close()
            
            return data
            
        except Exception as e:
            logger.error(f"Error querying database data: {e}")
            return []
    
    def health_check(self) -> Dict[str, Any]:
        """Check database health"""
        try:
            cursor = self._connection.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            
            return {
                'healthy': True,
                'last_check': timezone.now().isoformat(),
                'database_type': self.database_type,
                'table_name': self.table_name
            }
            
        except Exception:
            logger.exception("Unhandled error in health_check")
            return {
                'healthy': False,
                'error': 'Operation failed',
                'last_check': timezone.now().isoformat()
            }


# Integration handler factory
class IntegrationHandlerFactory:
    """Factory for creating integration handlers"""
    
    _handlers = {
        'webhook': WebhookIntegrationHandler,
        'api': APIIntegrationHandler,
        'database': DatabaseIntegrationHandler
    }
    
    @classmethod
    def create_handler(cls, handler_type: str, config: Dict[str, Any]) -> Optional[IntegrationHandler]:
        """Create integration handler by type"""
        handler_class = cls._handlers.get(handler_type)
        if not handler_class:
            logger.error(f"Unknown handler type: {handler_type}")
            return None
        
        try:
            return handler_class(config)
        except Exception as e:
            logger.error(f"Error creating handler {handler_type}: {e}")
            return None
    
    @classmethod
    def register_handler(cls, handler_type: str, handler_class: type):
        """Register a new handler type"""
        cls._handlers[handler_type] = handler_class
        logger.info(f"Registered integration handler: {handler_type}")
    
    @classmethod
    def get_available_handlers(cls) -> List[str]:
        """Get list of available handler types"""
        return list(cls._handlers.keys())


# ─────────────────────────────────────────────────────────────────
# Module-level singleton — used across bridge.py, event_bus.py,
# fallback_logic.py, health_check.py, data_bridge.py, etc.
# ─────────────────────────────────────────────────────────────────
class GenericAlertIntegrationHandler(AlertIntegrationHandler):
    """
    Concrete, generic implementation of AlertIntegrationHandler used as a
    shared singleton for cross-module alert-data processing.
    Provides connect/disconnect/send_data/receive_data/health_check stubs
    plus process_alert_data() used throughout the integration layer.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config or {'enabled': True})
        self._connected = False

    def connect(self) -> bool:
        self._connected = True
        return True

    def disconnect(self) -> bool:
        self._connected = False
        return True

    def send_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        self.log_activity('send_data', {'keys': list(data.keys())})
        return {'success': True, 'sent': data}

    def receive_data(self) -> List[Dict[str, Any]]:
        return []

    def health_check(self) -> Dict[str, Any]:
        return {'status': 'healthy', 'enabled': self.enabled, 'connected': self.is_connected()}

    def process_alert_data(self, alert_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate, transform, and return a processed copy of alert_data.
        Used by bridges, event bus, fallback logic, and health checks as
        the common alert-processing entry point.
        """
        try:
            validation = self.validate_alert(alert_data)
            transformed = self.transform_alert(alert_data) if self.field_mappings or self.alert_mappings or self.severity_mappings else dict(alert_data)
            result = dict(alert_data)
            result.update(transformed)
            return {
                'success': validation.get('valid', True),
                'data': result,
                'validation': validation,
            }
        except Exception as e:
            logger.error(f"GenericAlertIntegrationHandler.process_alert_data error: {e}")
            return {'success': False, 'error': 'Operation failed', 'data': alert_data}


# Shared singleton instance
integration_handler = GenericAlertIntegrationHandler()
