"""
Integration Data Validator - Enhanced validation for integration system
Provides safe data validation with existing alerts architecture
"""
import logging
import re
import json
from typing import Dict, Any, List, Optional, Union, Callable
from datetime import datetime, timezone
from django.utils import timezone as django_tz
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator, EmailValidator

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
    PATTERNS,
    MAX_TITLE_LENGTH,
    MAX_MESSAGE_LENGTH,
    MAX_WEBHOOK_URL_LENGTH,
    MAX_EMAIL_LENGTH,
    MAX_PHONE_LENGTH
)

logger = logging.getLogger(__name__)


class IntegrationDataValidator:
    """
    Enhanced data validator for integration system
    Maintains existing validation logic and adds integration-specific validation
    """
    
    def __init__(self):
        self.validation_rules = {}
        self.custom_validators = {}
        self.validation_stats = {
            'total_validations': 0,
            'successful_validations': 0,
            'failed_validations': 0,
            'last_validation': None
        }
    
    def validate_integration_data(self, integration_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate integration data using existing validators and additional rules
        """
        try:
            self.validation_stats['total_validations'] += 1
            self.validation_stats['last_validation'] = django_tz.now().isoformat()
            
            errors = []
            warnings = []
            
            # Step 1: Use existing validators for common fields
            common_validation = self._validate_common_fields(data)
            errors.extend(common_validation['errors'])
            warnings.extend(common_validation['warnings'])
            
            # Step 2: Use integration-specific validation
            integration_validation = self._validate_integration_specific_data(integration_type, data)
            errors.extend(integration_validation['errors'])
            warnings.extend(integration_validation['warnings'])
            
            # Step 3: Apply custom validation rules
            if integration_type in self.validation_rules:
                custom_validation = self.validation_rules[integration_type](data)
                errors.extend(custom_validation['errors'])
                warnings.extend(custom_validation['warnings'])
            
            # Update stats
            if len(errors) == 0:
                self.validation_stats['successful_validations'] += 1
            else:
                self.validation_stats['failed_validations'] += 1
            
            return {
                'valid': len(errors) == 0,
                'errors': errors,
                'warnings': warnings,
                'integration_type': integration_type
            }
            
        except Exception as e:
            logger.error(f"Error validating integration data: {e}")
            self.validation_stats['failed_validations'] += 1
            return {
                'valid': False,
                'errors': ['Validation error'],
                'warnings': [],
                'integration_type': integration_type
            }
    
    def _validate_common_fields(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate common fields using existing validators
        """
        errors = []
        warnings = []
        
        try:
            # Validate title
            title = data.get('title', '')
            if not title:
                errors.append("Title is required")
            elif len(title) > MAX_TITLE_LENGTH:
                errors.append(f"Title too long: {len(title)} > {MAX_TITLE_LENGTH}")
            
            # Validate message
            message = data.get('message', '')
            if not message:
                warnings.append("Message is empty")
            elif len(message) > MAX_MESSAGE_LENGTH:
                errors.append(f"Message too long: {len(message)} > {MAX_MESSAGE_LENGTH}")
            
            # Validate severity
            severity = data.get('severity', '')
            if severity:
                valid_severities = ['low', 'medium', 'high', 'critical']
                if severity not in valid_severities:
                    errors.append(f"Invalid severity: {severity}. Must be one of: {', '.join(valid_severities)}")
            
            # Validate timestamp
            timestamp = data.get('timestamp')
            if timestamp:
                try:
                    # Try to parse timestamp
                    if isinstance(timestamp, str):
                        datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                except ValueError:
                    errors.append(f"Invalid timestamp format: {timestamp}")
            
            # Validate condition using existing validator
            if 'condition' in data:
                condition_validation = validate_alert_rule_condition(data['condition'])
                if not condition_validation['valid']:
                    errors.extend(condition_validation['errors'])
                warnings.extend(condition_validation['warnings'])
            
            # Validate threshold using existing validator
            if 'threshold' in data:
                threshold_type = data.get('threshold_type', 'numeric')
                threshold_validation = validate_threshold_value(data['threshold'], threshold_type)
                if not threshold_validation['valid']:
                    errors.extend(threshold_validation['errors'])
                warnings.extend(threshold_validation['warnings'])
            
            return {
                'valid': len(errors) == 0,
                'errors': errors,
                'warnings': warnings
            }
            
        except Exception as e:
            logger.error(f"Error in common field validation: {e}")
            return {
                'valid': False,
                'errors': ['Common validation error'],
                'warnings': []
            }
    
    def _validate_integration_specific_data(self, integration_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate integration-specific data
        """
        errors = []
        warnings = []
        
        try:
            if integration_type == 'webhook':
                webhook_validation = self._validate_webhook_data(data)
                errors.extend(webhook_validation['errors'])
                warnings.extend(webhook_validation['warnings'])
            
            elif integration_type == 'email':
                email_validation = self._validate_email_data(data)
                errors.extend(email_validation['errors'])
                warnings.extend(email_validation['warnings'])
            
            elif integration_type == 'sms':
                sms_validation = self._validate_sms_data(data)
                errors.extend(sms_validation['errors'])
                warnings.extend(sms_validation['warnings'])
            
            elif integration_type == 'slack':
                slack_validation = self._validate_slack_data(data)
                errors.extend(slack_validation['errors'])
                warnings.extend(slack_validation['warnings'])
            
            elif integration_type == 'teams':
                teams_validation = self._validate_teams_data(data)
                errors.extend(teams_validation['errors'])
                warnings.extend(teams_validation['warnings'])
            
            elif integration_type == 'prometheus':
                prometheus_validation = self._validate_prometheus_data(data)
                errors.extend(prometheus_validation['errors'])
                warnings.extend(prometheus_validation['warnings'])
            
            elif integration_type == 'grafana':
                grafana_validation = self._validate_grafana_data(data)
                errors.extend(grafana_validation['errors'])
                warnings.extend(grafana_validation['warnings'])
            
            else:
                warnings.append(f"Unknown integration type: {integration_type}")
            
            return {
                'valid': len(errors) == 0,
                'errors': errors,
                'warnings': warnings
            }
            
        except Exception as e:
            logger.error(f"Error in integration-specific validation: {e}")
            return {
                'valid': False,
                'errors': ['Integration validation error'],
                'warnings': []
            }
    
    def _validate_webhook_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate webhook-specific data using existing webhook validator
        """
        errors = []
        warnings = []
        
        try:
            # Validate webhook URL using existing validator
            webhook_url = data.get('webhook_url')
            if webhook_url:
                url_validation = validate_webhook_url(webhook_url)
                if not url_validation['valid']:
                    errors.extend(url_validation['errors'])
                warnings.extend(url_validation['warnings'])
            else:
                errors.append("Webhook URL is required for webhook integration")
            
            # Validate webhook configuration
            webhook_config = data.get('webhook_config', {})
            if webhook_config:
                config_validation = validate_channel_config(webhook_config, 'webhook')
                if not config_validation['valid']:
                    errors.extend(config_validation['errors'])
                warnings.extend(config_validation['warnings'])
            
            # Validate method
            method = webhook_config.get('method', 'POST')
            valid_methods = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']
            if method not in valid_methods:
                errors.append(f"Invalid webhook method: {method}. Must be one of: {', '.join(valid_methods)}")
            
            # Validate headers
            headers = webhook_config.get('headers', {})
            if headers and not isinstance(headers, dict):
                errors.append("Webhook headers must be a dictionary")
            
            return {
                'valid': len(errors) == 0,
                'errors': errors,
                'warnings': warnings
            }
            
        except Exception as e:
            logger.error(f"Error validating webhook data: {e}")
            return {
                'valid': False,
                'errors': ['Webhook validation error'],
                'warnings': []
            }
    
    def _validate_email_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate email-specific data
        """
        errors = []
        warnings = []
        
        try:
            # Validate email address
            to_email = data.get('to_email')
            if to_email:
                try:
                    EmailValidator()(to_email)
                except ValidationError:
                    errors.append(f"Invalid email address: {to_email}")
            else:
                errors.append("Email address is required for email integration")
            
            # Validate subject
            subject = data.get('subject', '')
            if not subject:
                warnings.append("Email subject is empty")
            
            # Validate email configuration
            email_config = data.get('email_config', {})
            if email_config:
                config_validation = validate_channel_config(email_config, 'email')
                if not config_validation['valid']:
                    errors.extend(config_validation['errors'])
                warnings.extend(config_validation['warnings'])
            
            # Validate SMTP port
            smtp_port = email_config.get('smtp_port')
            if smtp_port and (not isinstance(smtp_port, int) or smtp_port < 1 or smtp_port > 65535):
                errors.append(f"Invalid SMTP port: {smtp_port}. Must be between 1 and 65535")
            
            return {
                'valid': len(errors) == 0,
                'errors': errors,
                'warnings': warnings
            }
            
        except Exception as e:
            logger.error(f"Error validating email data: {e}")
            return {
                'valid': False,
                'errors': ['Email validation error'],
                'warnings': []
            }
    
    def _validate_sms_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate SMS-specific data
        """
        errors = []
        warnings = []
        
        try:
            # Validate phone number
            phone_number = data.get('phone_number')
            if phone_number:
                if not PATTERNS['phone'].match(phone_number):
                    errors.append(f"Invalid phone number: {phone_number}")
            else:
                errors.append("Phone number is required for SMS integration")
            
            # Validate message length for SMS
            message = data.get('message', '')
            if message and len(message) > 160:
                warnings.append(f"SMS message too long: {len(message)} > 160 characters")
            
            # Validate SMS configuration
            sms_config = data.get('sms_config', {})
            if sms_config:
                config_validation = validate_channel_config(sms_config, 'sms')
                if not config_validation['valid']:
                    errors.extend(config_validation['errors'])
                warnings.extend(config_validation['warnings'])
            
            return {
                'valid': len(errors) == 0,
                'errors': errors,
                'warnings': warnings
            }
            
        except Exception as e:
            logger.error(f"Error validating SMS data: {e}")
            return {
                'valid': False,
                'errors': ['SMS validation error'],
                'warnings': []
            }
    
    def _validate_slack_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate Slack-specific data
        """
        errors = []
        warnings = []
        
        try:
            # Validate webhook URL
            webhook_url = data.get('webhook_url')
            if webhook_url:
                if not webhook_url.startswith('https://hooks.slack.com'):
                    errors.append("Slack webhook URL must start with https://hooks.slack.com")
            else:
                errors.append("Webhook URL is required for Slack integration")
            
            # Validate channel
            channel = data.get('channel')
            if channel and not channel.startswith('#'):
                errors.append("Slack channel must start with #")
            
            # Validate username
            username = data.get('username')
            if username and len(username) > 80:
                errors.append("Slack username too long: max 80 characters")
            
            return {
                'valid': len(errors) == 0,
                'errors': errors,
                'warnings': warnings
            }
            
        except Exception as e:
            logger.error(f"Error validating Slack data: {e}")
            return {
                'valid': False,
                'errors': ['Slack validation error'],
                'warnings': []
            }
    
    def _validate_teams_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate Teams-specific data
        """
        errors = []
        warnings = []
        
        try:
            # Validate webhook URL
            webhook_url = data.get('webhook_url')
            if webhook_url:
                if not webhook_url.startswith('https://outlook.office.com'):
                    warnings.append("Teams webhook URL should start with https://outlook.office.com")
            else:
                errors.append("Webhook URL is required for Teams integration")
            
            # Validate theme color
            theme_color = data.get('theme_color')
            if theme_color and not re.match(r'^[0-9A-Fa-f]{6}$', theme_color):
                errors.append("Teams theme color must be a valid hex color (6 characters)")
            
            # Validate title length
            title = data.get('title', '')
            if title and len(title) > 150:
                errors.append("Teams title too long: max 150 characters")
            
            return {
                'valid': len(errors) == 0,
                'errors': errors,
                'warnings': warnings
            }
            
        except Exception as e:
            logger.error(f"Error validating Teams data: {e}")
            return {
                'valid': False,
                'errors': ['Teams validation error'],
                'warnings': []
            }
    
    def _validate_prometheus_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate Prometheus-specific data
        """
        errors = []
        warnings = []
        
        try:
            # Validate labels
            labels = data.get('labels', {})
            if labels and not isinstance(labels, dict):
                errors.append("Prometheus labels must be a dictionary")
            
            # Validate annotations
            annotations = data.get('annotations', {})
            if annotations and not isinstance(annotations, dict):
                errors.append("Prometheus annotations must be a dictionary")
            
            # Validate metric name
            metric_name = labels.get('metric_name') if labels else None
            if metric_name and not re.match(r'^[a-zA-Z_:][a-zA-Z0-9_:]*$', metric_name):
                errors.append(f"Invalid Prometheus metric name: {metric_name}")
            
            # Validate value
            value = data.get('value')
            if value and not isinstance(value, (int, float)):
                errors.append("Prometheus value must be numeric")
            
            return {
                'valid': len(errors) == 0,
                'errors': errors,
                'warnings': warnings
            }
            
        except Exception as e:
            logger.error(f"Error validating Prometheus data: {e}")
            return {
                'valid': False,
                'errors': ['Prometheus validation error'],
                'warnings': []
            }
    
    def _validate_grafana_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate Grafana-specific data
        """
        errors = []
        warnings = []
        
        try:
            # Validate dashboard ID
            dashboard_id = data.get('dashboardId')
            if dashboard_id and not isinstance(dashboard_id, int):
                errors.append("Grafana dashboard ID must be an integer")
            
            # Validate panel ID
            panel_id = data.get('panelId')
            if panel_id and not isinstance(panel_id, int):
                errors.append("Grafana panel ID must be an integer")
            
            # Validate eval matches
            eval_matches = data.get('evalMatches', [])
            if eval_matches and not isinstance(eval_matches, list):
                errors.append("Grafana eval matches must be a list")
            
            # Validate state
            state = data.get('state')
            if state and state not in ['ok', 'warning', 'critical', 'unknown', 'paused', 'no_data', 'alerting']:
                errors.append(f"Invalid Grafana state: {state}")
            
            return {
                'valid': len(errors) == 0,
                'errors': errors,
                'warnings': warnings
            }
            
        except Exception as e:
            logger.error(f"Error validating Grafana data: {e}")
            return {
                'valid': False,
                'errors': ['Grafana validation error'],
                'warnings': []
            }
    
    def register_validation_rule(self, integration_type: str, rule_func: Callable):
        """
        Register custom validation rule
        """
        self.validation_rules[integration_type] = rule_func
        logger.info(f"Registered validation rule for: {integration_type}")
    
    def register_custom_validator(self, name: str, validator_func: Callable):
        """
        Register custom validator
        """
        self.custom_validators[name] = validator_func
        logger.info(f"Registered custom validator: {name}")
    
    def get_validation_statistics(self) -> Dict[str, Any]:
        """
        Get validation statistics
        """
        try:
            total_validations = self.validation_stats['total_validations']
            successful_validations = self.validation_stats['successful_validations']
            
            success_rate = (successful_validations / max(total_validations, 1)) * 100
            
            return {
                'total_validations': total_validations,
                'successful_validations': successful_validations,
                'failed_validations': self.validation_stats['failed_validations'],
                'success_rate': success_rate,
                'registered_rules': list(self.validation_rules.keys()),
                'custom_validators': list(self.custom_validators.keys()),
                'last_validation': self.validation_stats['last_validation'],
                'timestamp': django_tz.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting validation statistics: {e}")
            return {
                'error': 'Operation failed',
                'timestamp': django_tz.now().isoformat()
            }


# Global validator instance
integration_data_validator = IntegrationDataValidator()


# Utility functions
def validate_integration_data(data_type: str = None, data: Dict[str, Any] = None,
                               integration_type: str = None) -> Dict[str, Any]:
    """
    Validate integration data.
    Accepts `data_type` (used by IntegrationValidationViewSet.validate) or
    `integration_type` (legacy alias) to name the integration/data kind.
    """
    kind = data_type or integration_type
    return integration_data_validator.validate_integration_data(kind, data or {})


def get_validation_statistics() -> Dict[str, Any]:
    """
    Get validation statistics
    """
    return integration_data_validator.get_validation_statistics()


# Custom validation rule examples
def strict_webhook_validator(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Strict webhook validation rule
    """
    errors = []
    warnings = []
    
    # Require HTTPS
    webhook_url = data.get('webhook_url', '')
    if webhook_url and not webhook_url.startswith('https://'):
        errors.append("HTTPS is required for webhook URLs")
    
    # Require secret for security
    secret = data.get('webhook_config', {}).get('secret')
    if not secret:
        errors.append("Webhook secret is required for security")
    
    return {
        'valid': len(errors) == 0,
        'errors': errors,
        'warnings': warnings
    }


# Register strict webhook validator
integration_data_validator.register_validation_rule('webhook_strict', strict_webhook_validator)
