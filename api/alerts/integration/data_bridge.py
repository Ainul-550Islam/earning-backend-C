"""
Integration Data Bridge - Bridges data between systems with validation
Provides safe data bridging with existing alerts architecture
"""
import logging
import json
import re
from typing import Dict, Any, List, Optional, Union, Callable
from datetime import datetime, timezone
from django.utils import timezone as django_tz
from django.db import transaction
from django.core.cache import cache
from django.core.exceptions import ValidationError

# Absolute imports to prevent ModuleNotFoundError
from api.alerts.models import AlertLog, AlertRule, Notification
from api.alerts.validators import (
    validate_alert_rule_condition, 
    validate_threshold_value, 
    validate_channel_config,
    validate_cron_expression,
    validate_webhook_url
)
from api.alerts.integration.integ_handler import integration_handler
from api.alerts.integration.integ_adapter import integration_adapter
from api.alerts.integration.integ_constants import (
    CACHE_KEYS,
    CACHE_TIMEOUTS,
    MAX_BATCH_SIZE
)

logger = logging.getLogger(__name__)


class IntegrationDataBridge:
    """
    Bridges data between external systems and alerts architecture
    Maintains existing validation and security logic
    """
    
    def __init__(self):
        self.data_transformers = {}
        self.validation_rules = {}
        self.bridge_stats = {
            'total_bridged': 0,
            'successful_bridged': 0,
            'failed_bridged': 0,
            'last_bridged': None
        }
    
    def bridge_data(self, source_system: str, target_system: str, 
                   data: Union[Dict[str, Any], List[Dict[str, Any]]], 
                   config: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Bridge data between systems
        Validates data using existing validators
        """
        try:
            # Handle batch data
            if isinstance(data, list):
                return self._bridge_batch_data(source_system, target_system, data, config)
            else:
                return self._bridge_single_data(source_system, target_system, data, config)
                
        except Exception as e:
            logger.error(f"Error bridging data from {source_system} to {target_system}: {e}")
            self.bridge_stats['failed_bridged'] += 1
            return {
                'success': False,
                'error': 'Operation failed'
            }
    
    def _bridge_single_data(self, source_system: str, target_system: str, 
                           data: Dict[str, Any], config: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Bridge single data item
        """
        try:
            # Update stats
            self.bridge_stats['total_bridged'] += 1
            self.bridge_stats['last_bridged'] = django_tz.now().isoformat()
            
            # Step 1: Validate source data
            validation_result = self._validate_source_data(source_system, data)
            if not validation_result['valid']:
                return {
                    'success': False,
                    'error': 'Source data validation failed',
                    'validation_errors': validation_result['errors']
                }
            
            # Step 2: Transform data using adapter
            adapted_data = integration_adapter.adapt_external_alert(source_system, data)
            if not adapted_data.get('success', False):
                return adapted_data
            
            # Step 3: Apply additional transformations
            transformed_data = self._apply_transformations(source_system, target_system, adapted_data['data'])
            
            # Step 4: Validate transformed data
            target_validation = self._validate_target_data(target_system, transformed_data)
            if not target_validation['valid']:
                return {
                    'success': False,
                    'error': 'Target data validation failed',
                    'validation_errors': target_validation['errors']
                }
            
            # Step 5: Process through integration handler
            result = integration_handler.process_alert_data(transformed_data)
            
            if result.get('success', False):
                self.bridge_stats['successful_bridged'] += 1
            else:
                self.bridge_stats['failed_bridged'] += 1
            
            return result
            
        except Exception as e:
            logger.error(f"Error bridging single data: {e}")
            self.bridge_stats['failed_bridged'] += 1
            return {
                'success': False,
                'error': 'Operation failed'
            }
    
    def _bridge_batch_data(self, source_system: str, target_system: str, 
                          data_list: List[Dict[str, Any]], config: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Bridge batch data
        """
        try:
            if len(data_list) > MAX_BATCH_SIZE:
                return {
                    'success': False,
                    'error': f'Batch size too large: {len(data_list)} > {MAX_BATCH_SIZE}'
                }
            
            results = []
            successful_count = 0
            failed_count = 0
            
            for data in data_list:
                result = self._bridge_single_data(source_system, target_system, data, config)
                results.append(result)
                
                if result.get('success', False):
                    successful_count += 1
                else:
                    failed_count += 1
            
            return {
                'success': True,
                'batch_results': {
                    'total_items': len(data_list),
                    'successful_items': successful_count,
                    'failed_items': failed_count,
                    'success_rate': (successful_count / len(data_list)) * 100,
                    'results': results
                }
            }
            
        except Exception as e:
            logger.error(f"Error bridging batch data: {e}")
            return {
                'success': False,
                'error': 'Operation failed'
            }
    
    def _validate_source_data(self, source_system: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate source data using existing validators
        """
        try:
            errors = []
            
            # Validate alert-related fields
            if 'condition' in data:
                condition_validation = validate_alert_rule_condition(data['condition'])
                if not condition_validation['valid']:
                    errors.extend(condition_validation['errors'])
            
            if 'threshold' in data:
                threshold_validation = validate_threshold_value(data['threshold'])
                if not threshold_validation['valid']:
                    errors.extend(threshold_validation['errors'])
            
            # System-specific validation
            system_errors = self._validate_system_specific_data(source_system, data)
            errors.extend(system_errors)
            
            return {
                'valid': len(errors) == 0,
                'errors': errors
            }
            
        except Exception as e:
            logger.error(f"Error validating source data: {e}")
            return {
                'valid': False,
                'errors': ['Validation error']
            }
    
    def _validate_target_data(self, target_system: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate target data using existing validators
        """
        try:
            errors = []
            
            # Validate webhook configuration if present
            if 'webhook_url' in data:
                webhook_validation = validate_webhook_url(data['webhook_url'])
                if not webhook_validation['valid']:
                    errors.extend(webhook_validation['errors'])
            
            # Validate channel configuration if present
            if 'channel_config' in data and 'channel_type' in data:
                config_validation = validate_channel_config(data['channel_config'], data['channel_type'])
                if not config_validation['valid']:
                    errors.extend(config_validation['errors'])
            
            return {
                'valid': len(errors) == 0,
                'errors': errors
            }
            
        except Exception as e:
            logger.error(f"Error validating target data: {e}")
            return {
                'valid': False,
                'errors': ['Validation error']
            }
    
    def _validate_system_specific_data(self, system: str, data: Dict[str, Any]) -> List[str]:
        """
        Validate system-specific data
        """
        errors = []
        
        try:
            if system == 'prometheus':
                # Prometheus-specific validation
                if 'labels' in data and not isinstance(data['labels'], dict):
                    errors.append("Prometheus labels must be a dictionary")
                
                if 'annotations' in data and not isinstance(data['annotations'], dict):
                    errors.append("Prometheus annotations must be a dictionary")
            
            elif system == 'grafana':
                # Grafana-specific validation
                if 'dashboardId' in data and not isinstance(data['dashboardId'], int):
                    errors.append("Grafana dashboard ID must be an integer")
                
                if 'panelId' in data and not isinstance(data['panelId'], int):
                    errors.append("Grafana panel ID must be an integer")
            
            elif system == 'slack':
                # Slack-specific validation
                if 'channel' in data and not data['channel'].startswith('#'):
                    errors.append("Slack channel must start with #")
            
            elif system == 'teams':
                # Teams-specific validation
                if 'themeColor' in data and not re.match(r'^[0-9A-Fa-f]{6}$', data['themeColor']):
                    errors.append("Teams theme color must be a valid hex color")
            
        except Exception as e:
            logger.error(f"Error in system-specific validation: {e}")
            errors.append(f"System validation error: {str(e)}")
        
        return errors
    
    def _apply_transformations(self, source_system: str, target_system: str, 
                             data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply data transformations
        """
        try:
            transformed_data = data.copy()
            
            # Apply source-specific transformations
            if source_system == 'prometheus':
                transformed_data = self._transform_prometheus_data(transformed_data)
            elif source_system == 'grafana':
                transformed_data = self._transform_grafana_data(transformed_data)
            elif source_system == 'slack':
                transformed_data = self._transform_slack_data(transformed_data)
            elif source_system == 'teams':
                transformed_data = self._transform_teams_data(transformed_data)
            
            # Apply target-specific transformations
            if target_system == 'webhook':
                transformed_data = self._transform_for_webhook(transformed_data)
            elif target_system == 'email':
                transformed_data = self._transform_for_email(transformed_data)
            elif target_system == 'sms':
                transformed_data = self._transform_for_sms(transformed_data)
            
            return transformed_data
            
        except Exception as e:
            logger.error(f"Error applying transformations: {e}")
            return data
    
    def _transform_prometheus_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform Prometheus-specific data
        """
        try:
            # Extract Prometheus labels and annotations
            labels = data.get('labels', {})
            annotations = data.get('annotations', {})
            
            # Add Prometheus metadata
            data['metadata'] = data.get('metadata', {})
            data['metadata']['prometheus_labels'] = labels
            data['metadata']['prometheus_annotations'] = annotations
            
            # Extract metric name from labels
            if 'metric_name' in labels:
                data['metric_name'] = labels['metric_name']
            
            return data
            
        except Exception as e:
            logger.error(f"Error transforming Prometheus data: {e}")
            return data
    
    def _transform_grafana_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform Grafana-specific data
        """
        try:
            # Extract Grafana-specific fields
            dashboard_id = data.get('dashboardId')
            panel_id = data.get('panelId')
            eval_matches = data.get('evalMatches', [])
            
            # Add Grafana metadata
            data['metadata'] = data.get('metadata', {})
            data['metadata']['dashboard_id'] = dashboard_id
            data['metadata']['panel_id'] = panel_id
            data['metadata']['eval_matches'] = eval_matches
            
            return data
            
        except Exception as e:
            logger.error(f"Error transforming Grafana data: {e}")
            return data
    
    def _transform_slack_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform Slack-specific data
        """
        try:
            # Extract Slack-specific fields
            channel = data.get('channel', '#alerts')
            username = data.get('username', 'Alerts Bot')
            
            # Add Slack metadata
            data['metadata'] = data.get('metadata', {})
            data['metadata']['slack_channel'] = channel
            data['metadata']['slack_username'] = username
            
            return data
            
        except Exception as e:
            logger.error(f"Error transforming Slack data: {e}")
            return data
    
    def _transform_teams_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform Teams-specific data
        """
        try:
            # Extract Teams-specific fields
            theme_color = data.get('themeColor', 'FF0000')
            summary = data.get('summary', data.get('title', ''))
            
            # Add Teams metadata
            data['metadata'] = data.get('metadata', {})
            data['metadata']['teams_theme_color'] = theme_color
            data['metadata']['teams_summary'] = summary
            
            return data
            
        except Exception as e:
            logger.error(f"Error transforming Teams data: {e}")
            return data
    
    def _transform_for_webhook(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform data for webhook target
        """
        try:
            # Ensure webhook-specific fields
            if 'webhook_url' not in data:
                data['channel'] = 'webhook'
            
            # Add webhook configuration
            if 'webhook_config' not in data:
                data['webhook_config'] = {
                    'method': 'POST',
                    'headers': {'Content-Type': 'application/json'}
                }
            
            return data
            
        except Exception as e:
            logger.error(f"Error transforming for webhook: {e}")
            return data
    
    def _transform_for_email(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform data for email target
        """
        try:
            # Ensure email-specific fields
            data['channel'] = 'email'
            
            # Add email configuration
            if 'email_config' not in data:
                data['email_config'] = {
                    'smtp_port': 587,
                    'use_tls': True
                }
            
            return data
            
        except Exception as e:
            logger.error(f"Error transforming for email: {e}")
            return data
    
    def _transform_for_sms(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform data for SMS target
        """
        try:
            # Ensure SMS-specific fields
            data['channel'] = 'sms'
            
            # Add SMS configuration
            if 'sms_config' not in data:
                data['sms_config'] = {
                    'timeout': 30,
                    'max_length': 160
                }
            
            return data
            
        except Exception as e:
            logger.error(f"Error transforming for SMS: {e}")
            return data
    
    def register_transformer(self, source_system: str, target_system: str, 
                           transformer: Callable[[Dict[str, Any]], Dict[str, Any]]):
        """
        Register custom transformer
        """
        key = f"{source_system}_to_{target_system}"
        self.data_transformers[key] = transformer
        logger.info(f"Registered transformer: {key}")
    
    def register_validation_rule(self, system: str, rule: Callable[[Dict[str, Any]], List[str]]):
        """
        Register validation rule
        """
        self.validation_rules[system] = rule
        logger.info(f"Registered validation rule for: {system}")
    
    def get_bridge_statistics(self) -> Dict[str, Any]:
        """
        Get bridge statistics
        """
        try:
            total_bridged = self.bridge_stats['total_bridged']
            successful_bridged = self.bridge_stats['successful_bridged']
            
            success_rate = (successful_bridged / max(total_bridged, 1)) * 100
            
            return {
                'total_bridged': total_bridged,
                'successful_bridged': successful_bridged,
                'failed_bridged': self.bridge_stats['failed_bridged'],
                'success_rate': success_rate,
                'last_bridged': self.bridge_stats['last_bridged'],
                'registered_transformers': len(self.data_transformers),
                'registered_validation_rules': len(self.validation_rules),
                'timestamp': django_tz.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting bridge statistics: {e}")
            return {
                'error': 'Operation failed',
                'timestamp': django_tz.now().isoformat()
            }
    
    def reset_statistics(self):
        """
        Reset bridge statistics
        """
        self.bridge_stats = {
            'total_bridged': 0,
            'successful_bridged': 0,
            'failed_bridged': 0,
            'last_bridged': None
        }
        
        logger.info("Bridge statistics reset")


# Global data bridge instance
integration_data_bridge = IntegrationDataBridge()


# Utility functions
def bridge_integration_data(source_system: str, target_system: str, 
                          data: Union[Dict[str, Any], List[Dict[str, Any]]], 
                          config: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Bridge data between systems
    """
    return integration_data_bridge.bridge_data(source_system, target_system, data, config)


def get_bridge_statistics() -> Dict[str, Any]:
    """
    Get bridge statistics
    """
    return integration_data_bridge.get_bridge_statistics()


# Custom transformer example
def custom_prometheus_to_email_transformer(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Custom transformer for Prometheus to email
    """
    try:
        # Transform Prometheus data for email
        email_data = {
            'title': f"Prometheus Alert: {data.get('title', 'Unknown')}",
            'message': data.get('message', ''),
            'severity': data.get('severity', 'medium'),
            'channel': 'email',
            'to_email': 'alerts@example.com',
            'subject': f"Prometheus Alert: {data.get('title', 'Unknown')}",
            'email_config': {
                'smtp_host': 'smtp.example.com',
                'smtp_port': 587,
                'use_tls': True
            }
        }
        
        return email_data
        
    except Exception as e:
        logger.error(f"Error in custom transformer: {e}")
        return data


# Register custom transformer
integration_data_bridge.register_transformer('prometheus', 'email', custom_prometheus_to_email_transformer)
