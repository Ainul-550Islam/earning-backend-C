# Reconstructed from services/FIX_ALL_PART1_Services1-4.py (was never split into
# individual files, leaving alerts.services unimportable — see audit).
# Fixed on extraction: AlertNotification -> Notification (real model name),
# api.alerts.utils.* -> real existing module paths.

import logging
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


class ConfigurationService:
    """
    Consolidates configuration and validation logic.
    Eliminates duplicates from: validators.py + integration/
    """

    @staticmethod
    def validate_integration_config(config_dict):
        """
        Validate integration configuration.
        
        Previously duplicated in:
        - alerts/validators.py
        - alerts/integration/integ_constants.py
        
        Args:
            config_dict: Configuration dictionary
            
        Returns:
            bool: True if valid
            
        Raises:
            ValidationError: If invalid
        """
        logger.info("Validating integration config")
        
        required_fields = ['provider', 'api_key', 'api_url']
        
        for field in required_fields:
            if field not in config_dict or not config_dict[field]:
                raise ValidationError(f"Missing required field: {field}")
        
        # Validate API URL format
        if not ConfigurationService._is_valid_url(config_dict['api_url']):
            raise ValidationError("Invalid API URL format")
        
        # Validate API key format (provider-specific)
        if not ConfigurationService._is_valid_api_key(
            config_dict['api_key'],
            config_dict['provider']
        ):
            raise ValidationError(f"Invalid API key format for {config_dict['provider']}")
        
        logger.info("Integration config validation passed")
        return True

    @staticmethod
    def validate_webhook_url(url):
        """
        Validate webhook URL.
        
        Previously duplicated in:
        - alerts/validators.py
        - alerts/webhooks.py
        
        Args:
            url: Webhook URL
            
        Returns:
            bool: True if valid
            
        Raises:
            ValidationError: If invalid
        """
        logger.info(f"Validating webhook URL: {url}")
        
        if not ConfigurationService._is_valid_url(url):
            raise ValidationError("Invalid webhook URL format")
        
        # Verify URL is HTTPS for security
        if not url.startswith('https://'):
            raise ValidationError("Webhook URLs must use HTTPS")
        
        # Verify URL is reachable
        if not ConfigurationService._is_url_reachable(url):
            raise ValidationError("Webhook URL is not reachable")
        
        logger.info("Webhook URL validation passed")
        return True

    @staticmethod
    def _is_valid_url(url):
        """Check if URL format is valid"""
        from urllib.parse import urlparse
        
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except:
            return False

    @staticmethod
    def _is_valid_api_key(api_key, provider):
        """Check if API key format is valid for provider"""
        providers = {
            'slack': lambda k: len(k) > 20 and k.startswith('xoxb'),
            'pagerduty': lambda k: len(k) > 20,
            'opsgenie': lambda k: len(k) > 20,
            'discord': lambda k: len(k) > 20,
        }
        
        if provider in providers:
            return providers[provider](api_key)
        
        # Default: at least 20 chars
        return len(api_key) > 20

    @staticmethod
    def _is_url_reachable(url):
        """Check if URL is reachable"""
        import requests
        
        try:
            response = requests.head(url, timeout=5)
            return response.status_code < 500
        except:
            return False

    @staticmethod
    def validate_alert_rule(rule_data):
        """Validate alert rule data"""
        if 'name' not in rule_data or not rule_data['name']:
            raise ValidationError("Rule name is required")
        
        if 'condition' not in rule_data:
            raise ValidationError("Rule condition is required")
        
        if 'threshold' in rule_data and rule_data['threshold'] <= 0:
            raise ValidationError("Threshold must be positive")
        
        return True

    @staticmethod
    def validate_notification_config(config):
        """Validate notification configuration"""
        if 'method' not in config:
            raise ValidationError("Notification method is required")
        
        valid_methods = ['email', 'slack', 'pagerduty', 'webhook', 'sms']
        if config['method'] not in valid_methods:
            raise ValidationError(f"Invalid notification method: {config['method']}")
        
        return True


__all__ = ['ConfigurationService']
