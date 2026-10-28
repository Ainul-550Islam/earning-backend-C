"""
Integration Transformer - Transforms data between systems
Provides safe data transformation with existing alerts architecture
"""
import logging
import json
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timezone
from django.utils import timezone as django_tz
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
from api.alerts.integration.integ_constants import (
    SEVERITY_MAPPING,
    AlertSeverity,
    INTEGRATION_TYPES
)

logger = logging.getLogger(__name__)


class IntegrationTransformer:
    """
    Transforms data between external systems and alerts architecture
    Maintains existing validation and security logic
    """
    
    def __init__(self):
        self.transformers = {}
        self._register_default_transformers()
    
    def _register_default_transformers(self):
        """Register default transformers for common systems"""
        self.transformers = {
            'prometheus': PrometheusTransformer(),
            'grafana': GrafanaTransformer(),
            'slack': SlackTransformer(),
            'teams': TeamsTransformer(),
            'email': EmailTransformer(),
            'sms': SMSTransformer(),
            'webhook': WebhookTransformer(),
            'custom': CustomTransformer()
        }
    
    def transform_to_alerts(self, source_system: str, external_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform external data to alerts system format
        Validates data using existing validators
        """
        try:
            transformer = self.transformers.get(source_system)
            if not transformer:
                return {
                    'success': False,
                    'error': f'No transformer found for system: {source_system}'
                }
            
            # Transform data
            transformed_data = transformer.transform_to_alerts(external_data)
            
            # Validate transformed data
            validation_result = self._validate_transformed_data(transformed_data)
            if not validation_result['valid']:
                return {
                    'success': False,
                    'error': 'Transformed data validation failed',
                    'validation_errors': validation_result['errors']
                }
            
            return {
                'success': True,
                'data': transformed_data
            }
            
        except Exception as e:
            logger.error(f"Error transforming data from {source_system}: {e}")
            return {
                'success': False,
                'error': 'Operation failed'
            }
    
    def transform_from_alerts(self, target_system: str, alerts_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform alerts data to external system format
        """
        try:
            transformer = self.transformers.get(target_system)
            if not transformer:
                return {
                    'success': False,
                    'error': f'No transformer found for system: {target_system}'
                }
            
            # Transform data
            transformed_data = transformer.transform_from_alerts(alerts_data)
            
            return {
                'success': True,
                'data': transformed_data
            }
            
        except Exception as e:
            logger.error(f"Error transforming data to {target_system}: {e}")
            return {
                'success': False,
                'error': 'Operation failed'
            }
    
    def _validate_transformed_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate transformed data using existing validators
        """
        try:
            errors = []
            
            # Validate condition if present
            if 'condition' in data:
                condition_validation = validate_alert_rule_condition(data['condition'])
                if not condition_validation['valid']:
                    errors.extend(condition_validation['errors'])
            
            # Validate threshold if present
            if 'threshold' in data:
                threshold_validation = validate_threshold_value(data['threshold'])
                if not threshold_validation['valid']:
                    errors.extend(threshold_validation['errors'])
            
            # Validate webhook configuration if present
            if 'webhook_url' in data:
                webhook_validation = validate_webhook_url(data['webhook_url'])
                if not webhook_validation['valid']:
                    errors.extend(webhook_validation['errors'])
            
            return {
                'valid': len(errors) == 0,
                'errors': errors
            }
            
        except Exception as e:
            logger.error(f"Error validating transformed data: {e}")
            return {
                'valid': False,
                'errors': ['Validation error']
            }
    
    def register_transformer(self, name: str, transformer_class):
        """
        Register custom transformer
        """
        self.transformers[name] = transformer_class()
        logger.info(f"Registered transformer: {name}")
    
    def get_available_transformers(self) -> List[str]:
        """
        Get list of available transformers
        """
        return list(self.transformers.keys())


class BaseTransformer:
    """
    Base transformer class for data transformation
    """
    
    def transform_to_alerts(self, external_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform external data to alerts system format
        Must be implemented by subclasses
        """
        raise NotImplementedError
    
    def transform_from_alerts(self, alerts_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform alerts data to external system format
        Must be implemented by subclasses
        """
        raise NotImplementedError
    
    def _extract_common_fields(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract common fields from data
        """
        return {
            'title': data.get('title', data.get('name', data.get('alert', 'Unknown Alert'))),
            'severity': self._normalize_severity(data.get('severity', data.get('level', 'medium'))),
            'message': data.get('message', data.get('description', '')),
            'timestamp': data.get('timestamp', django_tz.now().isoformat()),
            'source': data.get('source', 'external')
        }
    
    def _normalize_severity(self, severity: str) -> str:
        """
        Normalize severity to alerts system format
        """
        severity_mapping = {
            'critical': 'critical',
            'high': 'high',
            'warning': 'medium',
            'info': 'low',
            'low': 'low',
            'error': 'high',
            'warn': 'medium',
            'notice': 'low'
        }
        
        return severity_mapping.get(severity.lower(), 'medium')


class PrometheusTransformer(BaseTransformer):
    """
    Transformer for Prometheus alerts
    """
    
    def transform_to_alerts(self, external_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform Prometheus alert data to alerts format
        """
        try:
            common_fields = self._extract_common_fields(external_data)
            
            # Prometheus-specific fields
            labels = external_data.get('labels', {})
            annotations = external_data.get('annotations', {})
            
            alerts_data = {
                **common_fields,
                'condition': {
                    'field': labels.get('metric_name', 'value'),
                    'operator': 'greater_than',
                    'value': external_data.get('value', 0)
                },
                'threshold': external_data.get('threshold', 0),
                'threshold_type': 'numeric',
                'channel': 'webhook',
                'webhook_url': external_data.get('webhook_url'),
                'metadata': {
                    'prometheus_labels': labels,
                    'prometheus_annotations': annotations,
                    'starts_at': external_data.get('startsAt'),
                    'generator_url': external_data.get('generatorURL')
                }
            }
            
            return alerts_data
            
        except Exception as e:
            logger.error(f"Error transforming Prometheus alert: {e}")
            raise
    
    def transform_from_alerts(self, alerts_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform alerts data to Prometheus format
        """
        try:
            metadata = alerts_data.get('metadata', {})
            prometheus_labels = metadata.get('prometheus_labels', {})
            
            prometheus_data = {
                'labels': prometheus_labels,
                'annotations': metadata.get('prometheus_annotations', {}),
                'startsAt': metadata.get('starts_at'),
                'generatorURL': metadata.get('generator_url'),
                'status': 'firing'
            }
            
            return prometheus_data
            
        except Exception as e:
            logger.error(f"Error transforming alerts to Prometheus: {e}")
            raise


class GrafanaTransformer(BaseTransformer):
    """
    Transformer for Grafana alerts
    """
    
    def transform_to_alerts(self, external_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform Grafana alert data to alerts format
        """
        try:
            common_fields = self._extract_common_fields(external_data)
            
            # Grafana-specific fields
            dashboard_id = external_data.get('dashboardId')
            panel_id = external_data.get('panelId')
            eval_matches = external_data.get('evalMatches', [])
            
            alerts_data = {
                **common_fields,
                'condition': {
                    'field': 'metric_value',
                    'operator': 'greater_than',
                    'value': external_data.get('threshold', 0)
                },
                'threshold': external_data.get('threshold', 0),
                'threshold_type': 'numeric',
                'channel': 'webhook',
                'webhook_url': external_data.get('webhook_url'),
                'metadata': {
                    'dashboard_id': dashboard_id,
                    'panel_id': panel_id,
                    'eval_matches': eval_matches,
                    'state': external_data.get('state'),
                    'image_url': external_data.get('imageUrl')
                }
            }
            
            return alerts_data
            
        except Exception as e:
            logger.error(f"Error transforming Grafana alert: {e}")
            raise
    
    def transform_from_alerts(self, alerts_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform alerts data to Grafana format
        """
        try:
            metadata = alerts_data.get('metadata', {})
            
            grafana_data = {
                'dashboardId': metadata.get('dashboard_id'),
                'panelId': metadata.get('panel_id'),
                'evalMatches': metadata.get('eval_matches', []),
                'state': metadata.get('state', 'alerting'),
                'imageUrl': metadata.get('image_url')
            }
            
            return grafana_data
            
        except Exception as e:
            logger.error(f"Error transforming alerts to Grafana: {e}")
            raise


class SlackTransformer(BaseTransformer):
    """
    Transformer for Slack integration
    """
    
    def transform_to_alerts(self, external_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform Slack alert data to alerts format
        """
        try:
            common_fields = self._extract_common_fields(external_data)
            
            alerts_data = {
                **common_fields,
                'channel': 'webhook',
                'webhook_url': external_data.get('webhook_url'),
                'webhook_config': {
                    'method': 'POST',
                    'headers': {
                        'Content-Type': 'application/json'
                    },
                    'channel': external_data.get('channel', '#alerts'),
                    'username': external_data.get('username', 'Alerts Bot')
                },
                'metadata': {
                    'slack_channel': external_data.get('channel'),
                    'slack_username': external_data.get('username'),
                    'slack_icon': external_data.get('icon_emoji')
                }
            }
            
            return alerts_data
            
        except Exception as e:
            logger.error(f"Error transforming Slack alert: {e}")
            raise
    
    def transform_from_alerts(self, alerts_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform alerts data to Slack format
        """
        try:
            metadata = alerts_data.get('metadata', {})
            
            slack_data = {
                'text': alerts_data.get('title', ''),
                'attachments': [
                    {
                        'color': self._get_slack_color(alerts_data.get('severity', 'medium')),
                        'fields': [
                            {
                                'title': 'Message',
                                'value': alerts_data.get('message', ''),
                                'short': False
                            },
                            {
                                'title': 'Severity',
                                'value': alerts_data.get('severity', 'medium'),
                                'short': True
                            },
                            {
                                'title': 'Timestamp',
                                'value': alerts_data.get('timestamp', ''),
                                'short': True
                            }
                        ]
                    }
                ],
                'channel': metadata.get('slack_channel', '#alerts'),
                'username': metadata.get('slack_username', 'Alerts Bot'),
                'icon_emoji': metadata.get('slack_icon', ':warning:')
            }
            
            return slack_data
            
        except Exception as e:
            logger.error(f"Error transforming alerts to Slack: {e}")
            raise
    
    def _get_slack_color(self, severity: str) -> str:
        """
        Get Slack color for severity
        """
        color_mapping = {
            'critical': 'danger',
            'high': 'warning',
            'medium': 'warning',
            'low': 'good'
        }
        
        return color_mapping.get(severity, 'warning')


class TeamsTransformer(BaseTransformer):
    """
    Transformer for Microsoft Teams integration
    """
    
    def transform_to_alerts(self, external_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform Teams alert data to alerts format
        """
        try:
            common_fields = self._extract_common_fields(external_data)
            
            alerts_data = {
                **common_fields,
                'channel': 'webhook',
                'webhook_url': external_data.get('webhook_url'),
                'webhook_config': {
                    'method': 'POST',
                    'headers': {
                        'Content-Type': 'application/json'
                    }
                },
                'metadata': {
                    'teams_title': external_data.get('title'),
                    'teams_summary': external_data.get('summary'),
                    'teams_theme_color': external_data.get('themeColor', 'FF0000')
                }
            }
            
            return alerts_data
            
        except Exception as e:
            logger.error(f"Error transforming Teams alert: {e}")
            raise
    
    def transform_from_alerts(self, alerts_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform alerts data to Teams format
        """
        try:
            metadata = alerts_data.get('metadata', {})
            
            teams_data = {
                '@type': 'MessageCard',
                '@context': 'http://schema.org/extensions',
                'themeColor': metadata.get('teams_theme_color', 'FF0000'),
                'summary': metadata.get('teams_summary', alerts_data.get('title', '')),
                'sections': [
                    {
                        'activityTitle': alerts_data.get('title', ''),
                        'activitySubtitle': alerts_data.get('severity', 'medium'),
                        'text': alerts_data.get('message', ''),
                        'facts': [
                            {
                                'name': 'Timestamp',
                                'value': alerts_data.get('timestamp', '')
                            }
                        ]
                    }
                ]
            }
            
            return teams_data
            
        except Exception as e:
            logger.error(f"Error transforming alerts to Teams: {e}")
            raise


class EmailTransformer(BaseTransformer):
    """
    Transformer for email integration
    """
    
    def transform_to_alerts(self, external_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform email alert data to alerts format
        """
        try:
            common_fields = self._extract_common_fields(external_data)
            
            alerts_data = {
                **common_fields,
                'channel': 'email',
                'to_email': external_data.get('to_email', external_data.get('email')),
                'subject': external_data.get('subject', common_fields['title']),
                'message': external_data.get('message', common_fields['message']),
                'email_config': {
                    'smtp_host': external_data.get('smtp_host'),
                    'smtp_port': external_data.get('smtp_port', 587),
                    'smtp_username': external_data.get('smtp_username'),
                    'smtp_password': external_data.get('smtp_password'),
                    'from_email': external_data.get('from_email', 'alerts@system.com')
                }
            }
            
            return alerts_data
            
        except Exception as e:
            logger.error(f"Error transforming email alert: {e}")
            raise
    
    def transform_from_alerts(self, alerts_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform alerts data to email format
        """
        try:
            email_data = {
                'to': alerts_data.get('to_email', ''),
                'subject': alerts_data.get('subject', alerts_data.get('title', '')),
                'body': alerts_data.get('message', ''),
                'html': self._generate_html_body(alerts_data)
            }
            
            return email_data
            
        except Exception as e:
            logger.error(f"Error transforming alerts to email: {e}")
            raise
    
    def _generate_html_body(self, alerts_data: Dict[str, Any]) -> str:
        """
        Generate HTML body for email
        """
        return f"""
        <html>
        <body>
            <h2>{alerts_data.get('title', 'Alert')}</h2>
            <p><strong>Severity:</strong> {alerts_data.get('severity', 'medium')}</p>
            <p><strong>Message:</strong> {alerts_data.get('message', '')}</p>
            <p><strong>Timestamp:</strong> {alerts_data.get('timestamp', '')}</p>
        </body>
        </html>
        """


class SMSTransformer(BaseTransformer):
    """
    Transformer for SMS integration
    """
    
    def transform_to_alerts(self, external_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform SMS alert data to alerts format
        """
        try:
            common_fields = self._extract_common_fields(external_data)
            
            alerts_data = {
                **common_fields,
                'channel': 'sms',
                'phone_number': external_data.get('phone_number', external_data.get('to')),
                'message': external_data.get('message', common_fields['message']),
                'sms_config': {
                    'api_key': external_data.get('api_key'),
                    'api_url': external_data.get('api_url'),
                    'from_number': external_data.get('from_number')
                }
            }
            
            return alerts_data
            
        except Exception as e:
            logger.error(f"Error transforming SMS alert: {e}")
            raise
    
    def transform_from_alerts(self, alerts_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform alerts data to SMS format
        """
        try:
            sms_data = {
                'to': alerts_data.get('phone_number', ''),
                'body': self._generate_sms_body(alerts_data)
            }
            
            return sms_data
            
        except Exception as e:
            logger.error(f"Error transforming alerts to SMS: {e}")
            raise
    
    def _generate_sms_body(self, alerts_data: Dict[str, Any]) -> str:
        """
        Generate SMS body
        """
        title = alerts_data.get('title', 'Alert')
        severity = alerts_data.get('severity', 'medium')
        message = alerts_data.get('message', '')
        
        # Limit to 160 characters
        sms_body = f"[{severity.upper()}] {title}: {message}"
        
        if len(sms_body) > 160:
            sms_body = sms_body[:157] + "..."
        
        return sms_body


class WebhookTransformer(BaseTransformer):
    """
    Transformer for generic webhooks
    """
    
    def transform_to_alerts(self, external_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform webhook alert data to alerts format
        """
        try:
            common_fields = self._extract_common_fields(external_data)
            
            alerts_data = {
                **common_fields,
                'channel': 'webhook',
                'webhook_url': external_data.get('webhook_url'),
                'webhook_config': {
                    'method': external_data.get('method', 'POST'),
                    'headers': external_data.get('headers', {}),
                    'secret': external_data.get('secret'),
                    'bearer_token': external_data.get('bearer_token')
                },
                'metadata': {
                    'webhook_method': external_data.get('method'),
                    'webhook_headers': external_data.get('headers')
                }
            }
            
            return alerts_data
            
        except Exception as e:
            logger.error(f"Error transforming webhook alert: {e}")
            raise
    
    def transform_from_alerts(self, alerts_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform alerts data to webhook format
        """
        try:
            webhook_data = {
                'alert': {
                    'title': alerts_data.get('title', ''),
                    'severity': alerts_data.get('severity', 'medium'),
                    'message': alerts_data.get('message', ''),
                    'timestamp': alerts_data.get('timestamp', ''),
                    'source': alerts_data.get('source', 'alerts')
                },
                'metadata': alerts_data.get('metadata', {})
            }
            
            return webhook_data
            
        except Exception as e:
            logger.error(f"Error transforming alerts to webhook: {e}")
            raise


class CustomTransformer(BaseTransformer):
    """
    Transformer for custom systems
    """
    
    def transform_to_alerts(self, external_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform custom alert data to alerts format
        """
        try:
            common_fields = self._extract_common_fields(external_data)
            
            # Custom system-specific transformation
            custom_config = external_data.get('custom_config', {})
            
            alerts_data = {
                **common_fields,
                'channel': external_data.get('channel', 'webhook'),
                'condition': external_data.get('condition', {}),
                'threshold': external_data.get('threshold'),
                'threshold_type': external_data.get('threshold_type', 'numeric'),
                'custom_config': custom_config
            }
            
            # Add channel-specific configuration
            if alerts_data['channel'] == 'webhook':
                alerts_data['webhook_url'] = external_data.get('webhook_url')
                alerts_data['webhook_config'] = custom_config
            elif alerts_data['channel'] == 'email':
                alerts_data['email_config'] = custom_config
            elif alerts_data['channel'] == 'sms':
                alerts_data['sms_config'] = custom_config
            
            return alerts_data
            
        except Exception as e:
            logger.error(f"Error transforming custom alert: {e}")
            raise
    
    def transform_from_alerts(self, alerts_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform alerts data to custom format
        """
        try:
            custom_data = {
                'alert': alerts_data,
                'custom_fields': alerts_data.get('custom_config', {}),
                'transformed_at': django_tz.now().isoformat()
            }
            
            return custom_data
            
        except Exception as e:
            logger.error(f"Error transforming alerts to custom: {e}")
            raise


# Global transformer instance
integration_transformer = IntegrationTransformer()


# Utility functions
def transform_external_to_alerts(source_format: str = None, data: Dict[str, Any] = None,
                                  source_system: str = None) -> Dict[str, Any]:
    """
    Transform external data to alerts format.
    Accepts `source_format` (used by TransformerViewSet.transform_to_alerts)
    or `source_system` (legacy alias) to name the source integration.
    """
    system = source_format or source_system
    return integration_transformer.transform_to_alerts(system, data or {})


def transform_alerts_to_external(target_system: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transform alerts data to external format
    """
    return integration_transformer.transform_from_alerts(target_system, data)


def get_transformer_info() -> Dict[str, Any]:
    """
    Get information about available transformers
    """
    return {
        'available_transformers': integration_transformer.get_available_transformers(),
        'transformer_count': len(integration_transformer.transformers),
        'timestamp': django_tz.now().isoformat()
    }
