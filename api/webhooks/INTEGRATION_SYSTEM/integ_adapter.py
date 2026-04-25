"""Integration Adapter

This module provides adapter pattern implementation for integration system
with comprehensive data transformation and protocol adaptation.
"""

import logging
from typing import Dict, Any, Optional, List, Callable
from abc import ABC, abstractmethod
from django.utils import timezone
from django.conf import settings

from .integ_constants import IntegrationType, AdapterType
from .integ_exceptions import AdapterError, TransformationError
from .data_validator import DataValidator
from .performance_monitor import PerformanceMonitor

logger = logging.getLogger(__name__)


class BaseAdapter(ABC):
    """
    Abstract base class for integration adapters.
    Defines the interface that all adapters must implement.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the adapter."""
        self.config = config or {}
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.validator = DataValidator()
        self.monitor = PerformanceMonitor()
        
        # Load configuration
        self._load_configuration()
    
    def _load_configuration(self):
        """Load adapter configuration."""
        try:
            self.enabled = self.config.get('enabled', True)
            self.timeout = self.config.get('timeout', 30)
            self.retry_attempts = self.config.get('retry_attempts', 3)
            self.transformations = self.config.get('transformations', {})
            self.validations = self.config.get('validations', {})
            
        except Exception as e:
            self.logger.error(f"Error loading adapter configuration: {str(e)}")
            self.enabled = True
            self.timeout = 30
            self.retry_attempts = 3
            self.transformations = {}
            self.validations = {}
    
    @abstractmethod
    def adapt(self, data: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Adapt data according to adapter logic.
        
        Args:
            data: Data to adapt
            context: Additional context
            
        Returns:
            Adapted data
        """
        pass
    
    @abstractmethod
    def validate_input(self, data: Dict[str, Any]) -> bool:
        """
        Validate input data.
        
        Args:
            data: Data to validate
            
        Returns:
            True if valid
        """
        pass
    
    @abstractmethod
    def get_adapter_info(self) -> Dict[str, Any]:
        """
        Get adapter information.
        
        Returns:
            Adapter information
        """
        pass
    
    def transform_data(self, data: Dict[str, Any], transformation_name: str) -> Dict[str, Any]:
        """
        Apply data transformation.
        
        Args:
            data: Data to transform
            transformation_name: Name of transformation
            
        Returns:
            Transformed data
        """
        try:
            if transformation_name not in self.transformations:
                raise TransformationError(f"Transformation {transformation_name} not found")
            
            transformation_config = self.transformations[transformation_name]
            
            # Apply transformation based on type
            transformation_type = transformation_config.get('type')
            
            if transformation_type == 'field_mapping':
                return self._apply_field_mapping(data, transformation_config)
            elif transformation_type == 'value_conversion':
                return self._apply_value_conversion(data, transformation_config)
            elif transformation_type == 'data_filtering':
                return self._apply_data_filtering(data, transformation_config)
            elif transformation_type == 'custom_function':
                return self._apply_custom_function(data, transformation_config)
            else:
                raise TransformationError(f"Unknown transformation type: {transformation_type}")
                
        except Exception as e:
            self.logger.error(f"Error transforming data: {str(e)}")
            raise TransformationError(f"Data transformation failed: {str(e)}")
    
    def _apply_field_mapping(self, data: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        """Apply field mapping transformation."""
        try:
            mapping = config.get('mapping', {})
            transformed_data = {}
            
            for old_field, new_field in mapping.items():
                if old_field in data:
                    transformed_data[new_field] = data[old_field]
            
            # Include unmapped fields if specified
            if config.get('include_unmapped', False):
                for field, value in data.items():
                    if field not in mapping:
                        transformed_data[field] = value
            
            return transformed_data
            
        except Exception as e:
            self.logger.error(f"Error applying field mapping: {str(e)}")
            raise
    
    def _apply_value_conversion(self, data: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        """Apply value conversion transformation."""
        try:
            conversions = config.get('conversions', {})
            transformed_data = data.copy()
            
            for field, conversion_config in conversions.items():
                if field in transformed_data:
                    value = transformed_data[field]
                    conversion_type = conversion_config.get('type')
                    
                    if conversion_type == 'type_cast':
                        target_type = conversion_config.get('target_type')
                        if target_type == 'int':
                            transformed_data[field] = int(value)
                        elif target_type == 'float':
                            transformed_data[field] = float(value)
                        elif target_type == 'str':
                            transformed_data[field] = str(value)
                        elif target_type == 'bool':
                            transformed_data[field] = bool(value)
                    elif conversion_type == 'format':
                        format_string = conversion_config.get('format')
                        transformed_data[field] = format_string.format(value)
                    elif conversion_type == 'lookup':
                        lookup_table = conversion_config.get('lookup_table', {})
                        transformed_data[field] = lookup_table.get(value, value)
            
            return transformed_data
            
        except Exception as e:
            self.logger.error(f"Error applying value conversion: {str(e)}")
            raise
    
    def _apply_data_filtering(self, data: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        """Apply data filtering transformation."""
        try:
            include_fields = config.get('include_fields', [])
            exclude_fields = config.get('exclude_fields', [])
            
            filtered_data = {}
            
            if include_fields:
                for field in include_fields:
                    if field in data:
                        filtered_data[field] = data[field]
            else:
                filtered_data = data.copy()
            
            if exclude_fields:
                for field in exclude_fields:
                    filtered_data.pop(field, None)
            
            return filtered_data
            
        except Exception as e:
            self.logger.error(f"Error applying data filtering: {str(e)}")
            raise
    
    def _apply_custom_function(self, data: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        """Apply custom function transformation."""
        try:
            function_path = config.get('function')
            if not function_path:
                raise TransformationError("Custom function not specified")
            
            # Import and execute function
            module_path, function_name = function_path.rsplit('.', 1)
            module = __import__(module_path, fromlist=[function_name])
            custom_function = getattr(module, function_name)
            
            return custom_function(data, config)
            
        except Exception as e:
            self.logger.error(f"Error applying custom function: {str(e)}")
            raise
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check of adapter.
        
        Returns:
            Health check results
        """
        try:
            return {
                'status': 'healthy',
                'enabled': self.enabled,
                'timeout': self.timeout,
                'retry_attempts': self.retry_attempts,
                'transformations_count': len(self.transformations),
                'validations_count': len(self.validations),
                'checked_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error performing health check: {str(e)}")
            return {
                'status': 'unhealthy',
                'error': str(e),
                'checked_at': timezone.now().isoformat()
            }


class WebhookAdapter(BaseAdapter):
    """
    Adapter for webhook integration.
    Handles webhook-specific data transformation and validation.
    """
    
    def adapt(self, data: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Adapt webhook data.
        
        Args:
            data: Webhook data to adapt
            context: Additional context
            
        Returns:
            Adapted webhook data
        """
        try:
            with self.monitor.measure_adapter('webhook') as measurement:
                # Validate input
                if not self.validate_input(data):
                    raise AdapterError("Invalid webhook data")
                
                # Apply transformations
                transformed_data = data.copy()
                
                # Standard webhook transformations
                transformed_data = self._standardize_webhook_format(transformed_data)
                transformed_data = self._add_webhook_metadata(transformed_data, context)
                transformed_data = self._apply_webhook_validations(transformed_data)
                
                # Apply custom transformations
                if 'webhook' in self.transformations:
                    transformed_data = self.transform_data(transformed_data, 'webhook')
                
                return transformed_data
                
        except Exception as e:
            self.logger.error(f"Error adapting webhook data: {str(e)}")
            raise AdapterError(f"Webhook adaptation failed: {str(e)}")
    
    def validate_input(self, data: Dict[str, Any]) -> bool:
        """
        Validate webhook input data.
        
        Args:
            data: Data to validate
            
        Returns:
            True if valid
        """
        try:
            # Basic validation
            if not isinstance(data, dict):
                return False
            
            # Required fields for webhook
            required_fields = ['event_type', 'payload']
            for field in required_fields:
                if field not in data:
                    return False
            
            # Validate event type
            if not isinstance(data['event_type'], str):
                return False
            
            # Validate payload
            if not isinstance(data['payload'], dict):
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error validating webhook input: {str(e)}")
            return False
    
    def get_adapter_info(self) -> Dict[str, Any]:
        """
        Get webhook adapter information.
        
        Returns:
            Adapter information
        """
        return {
            'type': AdapterType.WEBHOOK,
            'name': 'WebhookAdapter',
            'description': 'Adapter for webhook integration',
            'version': '1.0.0',
            'supported_formats': ['json'],
            'required_fields': ['event_type', 'payload'],
            'optional_fields': ['timestamp', 'signature', 'headers'],
            'enabled': self.enabled,
            'config': self.config
        }
    
    def _standardize_webhook_format(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Standardize webhook format."""
        try:
            standardized = data.copy()
            
            # Ensure timestamp
            if 'timestamp' not in standardized:
                standardized['timestamp'] = timezone.now().isoformat()
            
            # Ensure event_type is lowercase
            if 'event_type' in standardized:
                standardized['event_type'] = standardized['event_type'].lower()
            
            # Standardize payload structure
            if 'payload' in standardized:
                payload = standardized['payload']
                if isinstance(payload, str):
                    import json
                    standardized['payload'] = json.loads(payload)
            
            return standardized
            
        except Exception as e:
            self.logger.error(f"Error standardizing webhook format: {str(e)}")
            raise
    
    def _add_webhook_metadata(self, data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Add webhook metadata."""
        try:
            data_with_metadata = data.copy()
            
            # Add adapter metadata
            data_with_metadata['adapter'] = {
                'type': 'webhook',
                'version': '1.0.0',
                'adapted_at': timezone.now().isoformat()
            }
            
            # Add context metadata
            if context:
                data_with_metadata['context'] = context
            
            return data_with_metadata
            
        except Exception as e:
            self.logger.error(f"Error adding webhook metadata: {str(e)}")
            raise
    
    def _apply_webhook_validations(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply webhook-specific validations."""
        try:
            validated_data = data.copy()
            
            # Validate event type format
            event_type = validated_data.get('event_type', '')
            if not event_type or '.' not in event_type:
                raise AdapterError(f"Invalid event type format: {event_type}")
            
            # Validate payload size
            payload = validated_data.get('payload', {})
            if isinstance(payload, dict):
                import json
                payload_size = len(json.dumps(payload))
                max_size = self.config.get('max_payload_size', 1024 * 1024)  # 1MB default
                
                if payload_size > max_size:
                    raise AdapterError(f"Payload too large: {payload_size} bytes")
            
            return validated_data
            
        except Exception as e:
            self.logger.error(f"Error applying webhook validations: {str(e)}")
            raise


class APIAdapter(BaseAdapter):
    """
    Adapter for API integration.
    Handles API-specific data transformation and validation.
    """
    
    def adapt(self, data: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Adapt API data.
        
        Args:
            data: API data to adapt
            context: Additional context
            
        Returns:
            Adapted API data
        """
        try:
            with self.monitor.measure_adapter('api') as measurement:
                # Validate input
                if not self.validate_input(data):
                    raise AdapterError("Invalid API data")
                
                # Apply transformations
                transformed_data = data.copy()
                
                # Standard API transformations
                transformed_data = self._standardize_api_format(transformed_data)
                transformed_data = self._add_api_metadata(transformed_data, context)
                transformed_data = self._apply_api_validations(transformed_data)
                
                # Apply custom transformations
                if 'api' in self.transformations:
                    transformed_data = self.transform_data(transformed_data, 'api')
                
                return transformed_data
                
        except Exception as e:
            self.logger.error(f"Error adapting API data: {str(e)}")
            raise AdapterError(f"API adaptation failed: {str(e)}")
    
    def validate_input(self, data: Dict[str, Any]) -> bool:
        """
        Validate API input data.
        
        Args:
            data: Data to validate
            
        Returns:
            True if valid
        """
        try:
            # Basic validation
            if not isinstance(data, dict):
                return False
            
            # Required fields for API
            required_fields = ['method', 'endpoint', 'data']
            for field in required_fields:
                if field not in data:
                    return False
            
            # Validate method
            valid_methods = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']
            if data['method'] not in valid_methods:
                return False
            
            # Validate endpoint
            if not isinstance(data['endpoint'], str):
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error validating API input: {str(e)}")
            return False
    
    def get_adapter_info(self) -> Dict[str, Any]:
        """
        Get API adapter information.
        
        Returns:
            Adapter information
        """
        return {
            'type': AdapterType.API,
            'name': 'APIAdapter',
            'description': 'Adapter for API integration',
            'version': '1.0.0',
            'supported_methods': ['GET', 'POST', 'PUT', 'DELETE', 'PATCH'],
            'required_fields': ['method', 'endpoint', 'data'],
            'optional_fields': ['headers', 'params', 'timeout'],
            'enabled': self.enabled,
            'config': self.config
        }
    
    def _standardize_api_format(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Standardize API format."""
        try:
            standardized = data.copy()
            
            # Ensure method is uppercase
            if 'method' in standardized:
                standardized['method'] = standardized['method'].upper()
            
            # Standardize endpoint
            if 'endpoint' in standardized:
                endpoint = standardized['endpoint']
                if not endpoint.startswith(('http://', 'https://')):
                    base_url = self.config.get('base_url', '')
                    standardized['endpoint'] = f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"
            
            # Ensure data is properly formatted
            if 'data' in standardized:
                if isinstance(standardized['data'], str):
                    import json
                    standardized['data'] = json.loads(standardized['data'])
            
            return standardized
            
        except Exception as e:
            self.logger.error(f"Error standardizing API format: {str(e)}")
            raise
    
    def _add_api_metadata(self, data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Add API metadata."""
        try:
            data_with_metadata = data.copy()
            
            # Add adapter metadata
            data_with_metadata['adapter'] = {
                'type': 'api',
                'version': '1.0.0',
                'adapted_at': timezone.now().isoformat()
            }
            
            # Add context metadata
            if context:
                data_with_metadata['context'] = context
            
            return data_with_metadata
            
        except Exception as e:
            self.logger.error(f"Error adding API metadata: {str(e)}")
            raise
    
    def _apply_api_validations(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply API-specific validations."""
        try:
            validated_data = data.copy()
            
            # Validate endpoint URL
            endpoint = validated_data.get('endpoint', '')
            if not endpoint or not endpoint.startswith(('http://', 'https://')):
                raise AdapterError(f"Invalid endpoint URL: {endpoint}")
            
            # Validate data size
            data_content = validated_data.get('data', {})
            if isinstance(data_content, dict):
                import json
                data_size = len(json.dumps(data_content))
                max_size = self.config.get('max_data_size', 1024 * 1024)  # 1MB default
                
                if data_size > max_size:
                    raise AdapterError(f"Data too large: {data_size} bytes")
            
            return validated_data
            
        except Exception as e:
            self.logger.error(f"Error applying API validations: {str(e)}")
            raise


class IntegrationAdapter:
    """
    Main integration adapter manager.
    Coordinates multiple adapters and provides unified interface.
    """
    
    def __init__(self):
        """Initialize the integration adapter manager."""
        self.logger = logger
        self.adapters = {}
        self.monitor = PerformanceMonitor()
        
        # Load configuration
        self._load_configuration()
        
        # Initialize adapters
        self._initialize_adapters()
    
    def _load_configuration(self):
        """Load adapter configuration from settings."""
        try:
            self.config = getattr(settings, 'WEBHOOK_ADAPTER_CONFIG', {})
            self.enabled_adapters = self.config.get('enabled_adapters', ['webhook', 'api'])
            
            self.logger.info("Adapter configuration loaded successfully")
        except Exception as e:
            self.logger.error(f"Error loading adapter configuration: {str(e)}")
            self.config = {}
            self.enabled_adapters = ['webhook', 'api']
    
    def _initialize_adapters(self):
        """Initialize enabled adapters."""
        try:
            # Initialize webhook adapter
            if 'webhook' in self.enabled_adapters:
                webhook_config = self.config.get('webhook', {})
                self.adapters['webhook'] = WebhookAdapter(webhook_config)
            
            # Initialize API adapter
            if 'api' in self.enabled_adapters:
                api_config = self.config.get('api', {})
                self.adapters['api'] = APIAdapter(api_config)
            
            self.logger.info(f"Initialized {len(self.adapters)} adapters")
            
        except Exception as e:
            self.logger.error(f"Error initializing adapters: {str(e)}")
    
    def adapt_data(self, adapter_type: str, data: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Adapt data using specified adapter.
        
        Args:
            adapter_type: Type of adapter to use
            data: Data to adapt
            context: Additional context
            
        Returns:
            Adapted data
        """
        try:
            if adapter_type not in self.adapters:
                raise AdapterError(f"Adapter {adapter_type} not found")
            
            adapter = self.adapters[adapter_type]
            return adapter.adapt(data, context)
            
        except Exception as e:
            self.logger.error(f"Error adapting data with {adapter_type}: {str(e)}")
            raise
    
    def get_adapter_status(self, adapter_type: str = None) -> Dict[str, Any]:
        """
        Get adapter status.
        
        Args:
            adapter_type: Optional specific adapter type
            
        Returns:
            Adapter status information
        """
        try:
            if adapter_type:
                if adapter_type in self.adapters:
                    return self.adapters[adapter_type].health_check()
                else:
                    return {'error': f'Adapter {adapter_type} not found'}
            else:
                return {
                    'total_adapters': len(self.adapters),
                    'enabled_adapters': self.enabled_adapters,
                    'adapters': {
                        name: adapter.health_check()
                        for name, adapter in self.adapters.items()
                    }
                }
                
        except Exception as e:
            self.logger.error(f"Error getting adapter status: {str(e)}")
            return {'error': str(e)}
    
    def register_adapter(self, adapter_type: str, adapter: BaseAdapter) -> bool:
        """
        Register a custom adapter.
        
        Args:
            adapter_type: Type of adapter
            adapter: Adapter instance
            
        Returns:
            True if registration successful
        """
        try:
            if not isinstance(adapter, BaseAdapter):
                raise AdapterError("Adapter must inherit from BaseAdapter")
            
            self.adapters[adapter_type] = adapter
            self.logger.info(f"Adapter {adapter_type} registered successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error registering adapter {adapter_type}: {str(e)}")
            return False
    
    def unregister_adapter(self, adapter_type: str) -> bool:
        """
        Unregister an adapter.
        
        Args:
            adapter_type: Type of adapter to unregister
            
        Returns:
            True if unregistration successful
        """
        try:
            if adapter_type in self.adapters:
                del self.adapters[adapter_type]
                self.logger.info(f"Adapter {adapter_type} unregistered successfully")
                return True
            else:
                self.logger.warning(f"Adapter {adapter_type} not found")
                return False
                
        except Exception as e:
            self.logger.error(f"Error unregistering adapter {adapter_type}: {str(e)}")
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check of adapter system.
        
        Returns:
            Health check results
        """
        try:
            health_status = {
                'overall': 'healthy',
                'components': {},
                'checks': []
            }
            
            # Check adapters
            for adapter_type, adapter in self.adapters.items():
                adapter_health = adapter.health_check()
                health_status['components'][adapter_type] = adapter_health
                
                if adapter_health['status'] != 'healthy':
                    health_status['overall'] = 'unhealthy'
            
            # Check configuration
            health_status['components']['configuration'] = {
                'status': 'healthy',
                'total_adapters': len(self.adapters),
                'enabled_adapters': len(self.enabled_adapters)
            }
            
            return health_status
            
        except Exception as e:
            self.logger.error(f"Error performing health check: {str(e)}")
            return {
                'overall': 'unhealthy',
                'error': str(e)
            }
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get adapter system status.
        
        Returns:
            System status
        """
        try:
            return {
                'adapter_manager': {
                    'status': 'running',
                    'total_adapters': len(self.adapters),
                    'enabled_adapters': self.enabled_adapters,
                    'uptime': self.monitor.get_uptime(),
                    'performance_metrics': self.monitor.get_system_metrics()
                },
                'adapters': {
                    name: adapter.get_adapter_info()
                    for name, adapter in self.adapters.items()
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error getting adapter status: {str(e)}")
            return {'error': str(e)}
