"""Webhooks Integration

This module provides webhooks integration for integration system
with comprehensive webhook processing and management.
"""

import logging
from typing import Dict, Any, Optional, List, Callable
from django.utils import timezone
from django.conf import settings
from django.core.exceptions import ValidationError

from ..models import WebhookEndpoint, WebhookSubscription, WebhookDeliveryLog
from ..constants import DeliveryStatus
from .integ_constants import IntegrationType, HealthStatus
from .integ_exceptions import IntegrationError
from .performance_monitor import PerformanceMonitor
from .data_validator import DataValidator
from .fallback_logic import FallbackLogic

logger = logging.getLogger(__name__)


class WebhooksIntegration:
    """
    Webhooks integration for integration system.
    Provides comprehensive webhook processing and management.
    """
    
    def __init__(self):
        """Initialize the webhooks integration."""
        self.logger = logger
        self.monitor = PerformanceMonitor()
        self.validator = DataValidator()
        self.fallback = FallbackLogic()
        
        # Load configuration
        self._load_configuration()
        
        # Initialize integration
        self._initialize_integration()
    
    def _load_configuration(self):
        """Load webhooks integration configuration."""
        try:
            self.config = getattr(settings, 'WEBHOOKS_INTEGRATION_CONFIG', {})
            self.enabled = self.config.get('enabled', True)
            self.timeout = self.config.get('timeout', 30)
            self.max_retries = self.config.get('max_retries', 3)
            self.enable_validation = self.config.get('enable_validation', True)
            self.enable_fallback = self.config.get('enable_fallback', True)
            
            self.logger.info("Webhooks integration configuration loaded successfully")
        except Exception as e:
            self.logger.error(f"Error loading webhooks integration configuration: {str(e)}")
            self.config = {}
            self.enabled = True
            self.timeout = 30
            self.max_retries = 3
            self.enable_validation = True
            self.enable_fallback = True
    
    def _initialize_integration(self):
        """Initialize the webhooks integration."""
        try:
            # Initialize webhook processors
            self._initialize_processors()
            
            # Initialize webhook handlers
            self._initialize_handlers()
            
            self.logger.info("Webhooks integration initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Error initializing webhooks integration: {str(e)}")
    
    def _initialize_processors(self):
        """Initialize webhook processors."""
        try:
            self.processors = {}
            
            # Load processor configurations
            processor_configs = self.config.get('processors', {})
            
            for processor_name, processor_config in processor_configs.items():
                if processor_config.get('enabled', True):
                    self.processors[processor_name] = self._create_processor(processor_config)
            
        except Exception as e:
            self.logger.error(f"Error initializing processors: {str(e)}")
    
    def _initialize_handlers(self):
        """Initialize webhook handlers."""
        try:
            self.handlers = {}
            
            # Load handler configurations
            handler_configs = self.config.get('handlers', {})
            
            for handler_name, handler_config in handler_configs.items():
                if handler_config.get('enabled', True):
                    self.handlers[handler_name] = self._create_handler(handler_config)
            
        except Exception as e:
            self.logger.error(f"Error initializing handlers: {str(e)}")
    
    def _create_processor(self, config: Dict[str, Any]):
        """Create a webhook processor."""
        try:
            processor_type = config.get('type')
            
            if processor_type == 'validator':
                return WebhookValidatorProcessor(config)
            elif processor_type == 'transformer':
                return WebhookTransformerProcessor(config)
            elif processor_type == 'router':
                return WebhookRouterProcessor(config)
            else:
                raise IntegrationError(f"Unknown processor type: {processor_type}")
                
        except Exception as e:
            self.logger.error(f"Error creating processor: {str(e)}")
            raise
    
    def _create_handler(self, config: Dict[str, Any]):
        """Create a webhook handler."""
        try:
            handler_type = config.get('type')
            
            if handler_type == 'delivery':
                return WebhookDeliveryHandler(config)
            elif handler_type == 'retry':
                return WebhookRetryHandler(config)
            elif handler_type == 'batch':
                return WebhookBatchHandler(config)
            else:
                raise IntegrationError(f"Unknown handler type: {handler_type}")
                
        except Exception as e:
            self.logger.error(f"Error creating handler: {str(e)}")
            raise
    
    def process_webhook(self, endpoint_id: str, event_type: str, payload: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Process a webhook request.
        
        Args:
            endpoint_id: Webhook endpoint ID
            event_type: Event type
            payload: Webhook payload
            context: Additional context
            
        Returns:
            Processing result
        """
        try:
            with self.monitor.measure_integration('webhook') as measurement:
                # Validate input
                if not self.enabled:
                    raise IntegrationError("Webhooks integration is disabled")
                
                # Get endpoint
                endpoint = self._get_endpoint(endpoint_id)
                if not endpoint:
                    raise IntegrationError(f"Webhook endpoint not found: {endpoint_id}")
                
                # Validate endpoint
                if not self._validate_endpoint(endpoint):
                    raise IntegrationError(f"Webhook endpoint validation failed: {endpoint_id}")
                
                # Apply processors
                processed_data = self._apply_processors(event_type, payload, context)
                
                # Get subscriptions
                subscriptions = self._get_subscriptions(endpoint, event_type)
                
                # Process webhook
                result = self._process_webhook_delivery(endpoint, subscriptions, processed_data, context)
                
                return {
                    'success': result['success'],
                    'endpoint_id': endpoint_id,
                    'event_type': event_type,
                    'processed_at': timezone.now().isoformat(),
                    'performance': measurement.get_metrics(),
                    **result
                }
                
        except Exception as e:
            self.logger.error(f"Error processing webhook: {str(e)}")
            
            # Apply fallback logic
            if self.enable_fallback:
                fallback_result = self.fallback.handle_webhook_error(e, endpoint_id, event_type, payload, context)
                return {
                    'success': False,
                    'error': str(e),
                    'fallback_result': fallback_result,
                    'processed_at': timezone.now().isoformat()
                }
            
            return {
                'success': False,
                'error': str(e),
                'processed_at': timezone.now().isoformat()
            }
    
    def _get_endpoint(self, endpoint_id: str) -> Optional[WebhookEndpoint]:
        """Get webhook endpoint by ID."""
        try:
            return WebhookEndpoint.objects.get(id=endpoint_id)
        except WebhookEndpoint.DoesNotExist:
            return None
        except Exception as e:
            self.logger.error(f"Error getting endpoint {endpoint_id}: {str(e)}")
            return None
    
    def _validate_endpoint(self, endpoint: WebhookEndpoint) -> bool:
        """Validate webhook endpoint."""
        try:
            # Check if endpoint is active
            if not endpoint.is_active():
                return False
            
            # Validate URL
            if not endpoint.url:
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error validating endpoint: {str(e)}")
            return False
    
    def _apply_processors(self, event_type: str, payload: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Apply webhook processors."""
        try:
            processed_data = payload.copy()
            
            for processor_name, processor in self.processors.items():
                try:
                    processed_data = processor.process(event_type, processed_data, context)
                except Exception as e:
                    self.logger.error(f"Error in processor {processor_name}: {str(e)}")
                    continue
            
            return processed_data
            
        except Exception as e:
            self.logger.error(f"Error applying processors: {str(e)}")
            return payload
    
    def _get_subscriptions(self, endpoint: WebhookEndpoint, event_type: str) -> List[WebhookSubscription]:
        """Get subscriptions for endpoint and event type."""
        try:
            return WebhookSubscription.objects.filter(
                endpoint=endpoint,
                event_type=event_type,
                is_active=True
            )
        except Exception as e:
            self.logger.error(f"Error getting subscriptions: {str(e)}")
            return []
    
    def _process_webhook_delivery(self, endpoint: WebhookEndpoint, subscriptions: List[WebhookSubscription], data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Process webhook delivery."""
        try:
            results = []
            
            for subscription in subscriptions:
                try:
                    # Apply subscription filters
                    if not self._matches_subscription_filters(subscription, data):
                        continue
                    
                    # Process delivery
                    delivery_result = self._process_single_delivery(endpoint, subscription, data, context)
                    results.append(delivery_result)
                    
                except Exception as e:
                    self.logger.error(f"Error processing subscription {subscription.id}: {str(e)}")
                    results.append({
                        'subscription_id': str(subscription.id),
                        'success': False,
                        'error': str(e)
                    })
            
            # Compile final result
            success_count = sum(1 for r in results if r.get('success', False))
            
            return {
                'success': success_count > 0,
                'total_subscriptions': len(subscriptions),
                'successful_deliveries': success_count,
                'failed_deliveries': len(subscriptions) - success_count,
                'results': results
            }
            
        except Exception as e:
            self.logger.error(f"Error processing webhook delivery: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'total_subscriptions': 0,
                'successful_deliveries': 0,
                'failed_deliveries': 0,
                'results': []
            }
    
    def _matches_subscription_filters(self, subscription: WebhookSubscription, data: Dict[str, Any]) -> bool:
        """Check if data matches subscription filters."""
        try:
            if not subscription.filter_config:
                return True
            
            # Apply filter logic
            from ..services.filtering import FilterService
            filter_service = FilterService()
            
            return filter_service.evaluate_filter_config(subscription.filter_config, data)
            
        except Exception as e:
            self.logger.error(f"Error checking subscription filters: {str(e)}")
            return True  # Default to allowing
    
    def _process_single_delivery(self, endpoint: WebhookEndpoint, subscription: WebhookSubscription, data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Process single webhook delivery."""
        try:
            # Create delivery log
            delivery_log = WebhookDeliveryLog.objects.create(
                endpoint=endpoint,
                event_type=data.get('event_type', 'unknown'),
                payload=data,
                status=DeliveryStatus.PENDING,
                attempt_number=1,
                max_attempts=endpoint.max_retries or self.max_retries,
                dispatched_at=timezone.now()
            )
            
            # Apply handlers
            result = self._apply_handlers(endpoint, subscription, delivery_log, context)
            
            return {
                'subscription_id': str(subscription.id),
                'delivery_log_id': str(delivery_log.id),
                'success': result['success'],
                'result': result
            }
            
        except Exception as e:
            self.logger.error(f"Error processing single delivery: {str(e)}")
            return {
                'subscription_id': str(subscription.id),
                'success': False,
                'error': str(e)
            }
    
    def _apply_handlers(self, endpoint: WebhookEndpoint, subscription: WebhookSubscription, delivery_log: WebhookDeliveryLog, context: Dict[str, Any]) -> Dict[str, Any]:
        """Apply webhook handlers."""
        try:
            for handler_name, handler in self.handlers.items():
                try:
                    result = handler.handle(endpoint, subscription, delivery_log, context)
                    if result.get('success', False):
                        return result
                except Exception as e:
                    self.logger.error(f"Error in handler {handler_name}: {str(e)}")
                    continue
            
            # Default handler
            return self._default_handler(endpoint, subscription, delivery_log, context)
            
        except Exception as e:
            self.logger.error(f"Error applying handlers: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _default_handler(self, endpoint: WebhookEndpoint, subscription: WebhookSubscription, delivery_log: WebhookDeliveryLog, context: Dict[str, Any]) -> Dict[str, Any]:
        """Default webhook handler."""
        try:
            from ..services.core.DispatchService
            dispatch_service = DispatchService()
            
            success = dispatch_service.emit(
                endpoint=endpoint,
                event_type=delivery_log.event_type,
                payload=delivery_log.payload,
                async_emit=False
            )
            
            if success:
                delivery_log.status = DeliveryStatus.SUCCESS
                delivery_log.completed_at = timezone.now()
            else:
                delivery_log.status = DeliveryStatus.FAILED
                delivery_log.error_message = "Default handler failed"
                delivery_log.completed_at = timezone.now()
            
            delivery_log.save()
            
            return {
                'success': success,
                'handler': 'default'
            }
            
        except Exception as e:
            self.logger.error(f"Error in default handler: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'handler': 'default'
            }
    
    def get_webhook_status(self, endpoint_id: str = None) -> Dict[str, Any]:
        """
        Get webhook status.
        
        Args:
            endpoint_id: Optional endpoint ID
            
        Returns:
            Webhook status information
        """
        try:
            if endpoint_id:
                endpoint = self._get_endpoint(endpoint_id)
                if not endpoint:
                    return {'error': f'Endpoint not found: {endpoint_id}'}
                
                return {
                    'endpoint_id': endpoint_id,
                    'status': endpoint.status,
                    'url': endpoint.url,
                    'subscriptions_count': endpoint.get_subscription_count(),
                    'last_triggered_at': endpoint.last_triggered_at,
                    'created_at': endpoint.created_at,
                    'updated_at': endpoint.updated_at
                }
            else:
                # Get all endpoints status
                endpoints = WebhookEndpoint.objects.all()
                
                status_summary = {
                    'total_endpoints': endpoints.count(),
                    'active_endpoints': endpoints.filter(status='active').count(),
                    'paused_endpoints': endpoints.filter(status='paused').count(),
                    'suspended_endpoints': endpoints.filter(status='suspended').count(),
                    'endpoints': []
                }
                
                for endpoint in endpoints:
                    status_summary['endpoints'].append({
                        'id': str(endpoint.id),
                        'label': endpoint.label,
                        'status': endpoint.status,
                        'subscriptions_count': endpoint.get_subscription_count(),
                        'last_triggered_at': endpoint.last_triggered_at.isoformat() if endpoint.last_triggered_at else None
                    })
                
                return status_summary
                
        except Exception as e:
            self.logger.error(f"Error getting webhook status: {str(e)}")
            return {'error': str(e)}
    
    def get_integration_status(self) -> Dict[str, Any]:
        """
        Get integration status.
        
        Returns:
            Integration status
        """
        try:
            return {
                'webhooks_integration': {
                    'status': 'running' if self.enabled else 'disabled',
                    'processors_count': len(self.processors),
                    'handlers_count': len(self.handlers),
                    'timeout': self.timeout,
                    'max_retries': self.max_retries,
                    'enable_validation': self.enable_validation,
                    'enable_fallback': self.enable_fallback,
                    'uptime': self.monitor.get_uptime(),
                    'performance_metrics': self.monitor.get_system_metrics()
                },
                'processors': {
                    name: processor.get_status()
                    for name, processor in self.processors.items()
                },
                'handlers': {
                    name: handler.get_status()
                    for name, handler in self.handlers.items()
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error getting integration status: {str(e)}")
            return {'error': str(e)}
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check of webhooks integration.
        
        Returns:
            Health check results
        """
        try:
            health_status = {
                'overall': HealthStatus.HEALTHY,
                'components': {},
                'checks': []
            }
            
            # Check configuration
            health_status['components']['configuration'] = {
                'status': HealthStatus.HEALTHY,
                'enabled': self.enabled,
                'processors_count': len(self.processors),
                'handlers_count': len(self.handlers)
            }
            
            # Check database connection
            try:
                endpoint_count = WebhookEndpoint.objects.count()
                health_status['components']['database'] = {
                    'status': HealthStatus.HEALTHY,
                    'endpoint_count': endpoint_count
                }
            except Exception as e:
                health_status['components']['database'] = {
                    'status': HealthStatus.UNHEALTHY,
                    'error': str(e)
                }
                health_status['overall'] = HealthStatus.UNHEALTHY
            
            # Check processors
            for name, processor in self.processors.items():
                processor_health = processor.health_check()
                if processor_health['status'] != HealthStatus.HEALTHY:
                    health_status['overall'] = HealthStatus.UNHEALTHY
            
            # Check handlers
            for name, handler in self.handlers.items():
                handler_health = handler.health_check()
                if handler_health['status'] != HealthStatus.HEALTHY:
                    health_status['overall'] = HealthStatus.UNHEALTHY
            
            return health_status
            
        except Exception as e:
            self.logger.error(f"Error performing health check: {str(e)}")
            return {
                'overall': HealthStatus.UNHEALTHY,
                'error': str(e)
            }
    
    def reload_configuration(self) -> bool:
        """
        Reload webhooks integration configuration.
        
        Returns:
            True if reload successful
        """
        try:
            self._load_configuration()
            self._initialize_integration()
            
            self.logger.info("Webhooks integration configuration reloaded successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error reloading configuration: {str(e)}")
            return False


class WebhookValidatorProcessor:
    """Webhook validator processor."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the validator processor."""
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def process(self, event_type: str, data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Process webhook validation."""
        try:
            # Apply validation rules
            validation_rules = self.config.get('validation_rules', {})
            
            for rule_name, rule_config in validation_rules.items():
                if not self._apply_validation_rule(rule_name, rule_config, event_type, data):
                    raise IntegrationError(f"Validation failed: {rule_name}")
            
            return data
            
        except Exception as e:
            self.logger.error(f"Error in webhook validator processor: {str(e)}")
            raise
    
    def _apply_validation_rule(self, rule_name: str, rule_config: Dict[str, Any], event_type: str, data: Dict[str, Any]) -> bool:
        """Apply a validation rule."""
        try:
            rule_type = rule_config.get('type')
            
            if rule_type == 'required_fields':
                required_fields = rule_config.get('fields', [])
                return all(field in data for field in required_fields)
            elif rule_type == 'field_types':
                field_types = rule_config.get('fields', {})
                return all(isinstance(data.get(field), field_types[field]) for field in field_types)
            elif rule_type == 'custom':
                # Custom validation logic
                return True
            else:
                return True
                
        except Exception as e:
            self.logger.error(f"Error applying validation rule {rule_name}: {str(e)}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get processor status."""
        return {
            'processor': 'WebhookValidatorProcessor',
            'status': 'healthy',
            'validation_rules_count': len(self.config.get('validation_rules', {}))
        }
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check."""
        return self.get_status()


class WebhookTransformerProcessor:
    """Webhook transformer processor."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the transformer processor."""
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def process(self, event_type: str, data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Process webhook transformation."""
        try:
            # Apply transformation rules
            transformation_rules = self.config.get('transformation_rules', {})
            
            for rule_name, rule_config in transformation_rules.items():
                data = self._apply_transformation_rule(rule_name, rule_config, event_type, data, context)
            
            return data
            
        except Exception as e:
            self.logger.error(f"Error in webhook transformer processor: {str(e)}")
            raise
    
    def _apply_transformation_rule(self, rule_name: str, rule_config: Dict[str, Any], event_type: str, data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Apply a transformation rule."""
        try:
            rule_type = rule_config.get('type')
            
            if rule_type == 'field_mapping':
                mapping = rule_config.get('mapping', {})
                return self._apply_field_mapping(data, mapping)
            elif rule_type == 'value_conversion':
                conversions = rule_config.get('conversions', {})
                return self._apply_value_conversion(data, conversions)
            elif rule_type == 'custom':
                # Custom transformation logic
                return data
            else:
                return data
                
        except Exception as e:
            self.logger.error(f"Error applying transformation rule {rule_name}: {str(e)}")
            return data
    
    def _apply_field_mapping(self, data: Dict[str, Any], mapping: Dict[str, str]) -> Dict[str, Any]:
        """Apply field mapping transformation."""
        try:
            transformed_data = {}
            
            for old_field, new_field in mapping.items():
                if old_field in data:
                    transformed_data[new_field] = data[old_field]
            
            # Include unmapped fields
            for field, value in data.items():
                if field not in mapping:
                    transformed_data[field] = value
            
            return transformed_data
            
        except Exception as e:
            self.logger.error(f"Error applying field mapping: {str(e)}")
            return data
    
    def _apply_value_conversion(self, data: Dict[str, Any], conversions: Dict[str, Any]) -> Dict[str, Any]:
        """Apply value conversion transformation."""
        try:
            transformed_data = data.copy()
            
            for field, conversion_config in conversions.items():
                if field in transformed_data:
                    value = transformed_data[field]
                    conversion_type = conversion_config.get('type')
                    
                    if conversion_type == 'string':
                        transformed_data[field] = str(value)
                    elif conversion_type == 'integer':
                        transformed_data[field] = int(value)
                    elif conversion_type == 'float':
                        transformed_data[field] = float(value)
                    elif conversion_type == 'boolean':
                        transformed_data[field] = bool(value)
            
            return transformed_data
            
        except Exception as e:
            self.logger.error(f"Error applying value conversion: {str(e)}")
            return data
    
    def get_status(self) -> Dict[str, Any]:
        """Get processor status."""
        return {
            'processor': 'WebhookTransformerProcessor',
            'status': 'healthy',
            'transformation_rules_count': len(self.config.get('transformation_rules', {}))
        }
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check."""
        return self.get_status()


class WebhookRouterProcessor:
    """Webhook router processor."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the router processor."""
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def process(self, event_type: str, data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Process webhook routing."""
        try:
            # Apply routing rules
            routing_rules = self.config.get('routing_rules', {})
            
            for rule_name, rule_config in routing_rules.items():
                if self._matches_routing_rule(rule_name, rule_config, event_type, data):
                    return self._apply_routing_rule(rule_name, rule_config, event_type, data, context)
            
            return data
            
        except Exception as e:
            self.logger.error(f"Error in webhook router processor: {str(e)}")
            raise
    
    def _matches_routing_rule(self, rule_name: str, rule_config: Dict[str, Any], event_type: str, data: Dict[str, Any]) -> bool:
        """Check if data matches routing rule."""
        try:
            conditions = rule_config.get('conditions', [])
            
            for condition in conditions:
                if not self._evaluate_condition(condition, event_type, data):
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error evaluating routing rule {rule_name}: {str(e)}")
            return False
    
    def _evaluate_condition(self, condition: Dict[str, Any], event_type: str, data: Dict[str, Any]) -> bool:
        """Evaluate a routing condition."""
        try:
            field = condition.get('field')
            operator = condition.get('operator')
            value = condition.get('value')
            
            if field not in data:
                return False
            
            actual_value = data[field]
            
            if operator == 'equals':
                return actual_value == value
            elif operator == 'contains':
                return value in str(actual_value)
            elif operator == 'greater_than':
                return actual_value > value
            elif operator == 'less_than':
                return actual_value < value
            else:
                return True
                
        except Exception as e:
            self.logger.error(f"Error evaluating condition: {str(e)}")
            return False
    
    def _apply_routing_rule(self, rule_name: str, rule_config: Dict[str, Any], event_type: str, data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Apply routing rule."""
        try:
            actions = rule_config.get('actions', [])
            
            for action in actions:
                data = self._apply_action(action, event_type, data, context)
            
            return data
            
        except Exception as e:
            self.logger.error(f"Error applying routing rule {rule_name}: {str(e)}")
            return data
    
    def _apply_action(self, action: Dict[str, Any], event_type: str, data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Apply routing action."""
        try:
            action_type = action.get('type')
            
            if action_type == 'add_field':
                field = action.get('field')
                value = action.get('value')
                data[field] = value
            elif action_type == 'remove_field':
                field = action.get('field')
                data.pop(field, None)
            elif action_type == 'modify_field':
                field = action.get('field')
                modifier = action.get('modifier')
                if field in data:
                    if modifier == 'uppercase':
                        data[field] = str(data[field]).upper()
                    elif modifier == 'lowercase':
                        data[field] = str(data[field]).lower()
            
            return data
            
        except Exception as e:
            self.logger.error(f"Error applying action: {str(e)}")
            return data
    
    def get_status(self) -> Dict[str, Any]:
        """Get processor status."""
        return {
            'processor': 'WebhookRouterProcessor',
            'status': 'healthy',
            'routing_rules_count': len(self.config.get('routing_rules', {}))
        }
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check."""
        return self.get_status()


class WebhookDeliveryHandler:
    """Webhook delivery handler."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the delivery handler."""
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def handle(self, endpoint: WebhookEndpoint, subscription: WebhookSubscription, delivery_log: WebhookDeliveryLog, context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle webhook delivery."""
        try:
            # Implement delivery logic
            from ..services.core.DispatchService
            dispatch_service = DispatchService()
            
            success = dispatch_service.emit(
                endpoint=endpoint,
                event_type=delivery_log.event_type,
                payload=delivery_log.payload,
                async_emit=False
            )
            
            if success:
                delivery_log.status = DeliveryStatus.SUCCESS
                delivery_log.completed_at = timezone.now()
            else:
                delivery_log.status = DeliveryStatus.FAILED
                delivery_log.error_message = "Delivery handler failed"
                delivery_log.completed_at = timezone.now()
            
            delivery_log.save()
            
            return {
                'success': success,
                'handler': 'delivery',
                'delivery_log_id': str(delivery_log.id)
            }
            
        except Exception as e:
            self.logger.error(f"Error in webhook delivery handler: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'handler': 'delivery'
            }
    
    def get_status(self) -> Dict[str, Any]:
        """Get handler status."""
        return {
            'handler': 'WebhookDeliveryHandler',
            'status': 'healthy'
        }
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check."""
        return self.get_status()


class WebhookRetryHandler:
    """Webhook retry handler."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the retry handler."""
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def handle(self, endpoint: WebhookEndpoint, subscription: WebhookSubscription, delivery_log: WebhookDeliveryLog, context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle webhook retry."""
        try:
            # Check if retry is possible
            if not delivery_log.can_retry():
                return {
                    'success': False,
                    'error': 'Retry not possible',
                    'handler': 'retry'
                }
            
            # Schedule retry
            if delivery_log.schedule_retry():
                return {
                    'success': True,
                    'handler': 'retry',
                    'next_retry_at': delivery_log.next_retry_at.isoformat()
                }
            else:
                return {
                    'success': False,
                    'error': 'Retry scheduling failed',
                    'handler': 'retry'
                }
            
        except Exception as e:
            self.logger.error(f"Error in webhook retry handler: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'handler': 'retry'
            }
    
    def get_status(self) -> Dict[str, Any]:
        """Get handler status."""
        return {
            'handler': 'WebhookRetryHandler',
            'status': 'healthy'
        }
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check."""
        return self.get_status()


class WebhookBatchHandler:
    """Webhook batch handler."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the batch handler."""
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def handle(self, endpoint: WebhookEndpoint, subscription: WebhookSubscription, delivery_log: WebhookDeliveryLog, context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle webhook batch processing."""
        try:
            # Implement batch processing logic
            from ..services.batch.BatchDispatchService
            batch_service = BatchDispatchService()
            
            # Create batch
            batch = batch_service.create_batch(
                endpoint=endpoint,
                event_type=delivery_log.event_type,
                events=[delivery_log.payload]
            )
            
            # Process batch
            result = batch_service.process_batch(batch)
            
            return {
                'success': result.get('success', False),
                'handler': 'batch',
                'batch_id': batch.batch_id,
                'result': result
            }
            
        except Exception as e:
            self.logger.error(f"Error in webhook batch handler: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'handler': 'batch'
            }
    
    def get_status(self) -> Dict[str, Any]:
        """Get handler status."""
        return {
            'handler': 'WebhookBatchHandler',
            'status': 'healthy'
        }
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check."""
        return self.get_status()
