"""
Integration Fallback Logic - Fallback mechanisms for integration failures
Provides safe fallback handling with existing alerts architecture
"""
import logging
from typing import Dict, Any, List, Optional, Callable, Union
from datetime import datetime, timezone, timedelta
from django.utils import timezone as django_tz
from django.core.cache import cache

# Absolute imports to prevent ModuleNotFoundError
from api.alerts.models import AlertLog, AlertRule, Notification
from api.alerts.validators import validate_alert_rule_condition, validate_threshold_value
from api.alerts.integration.integ_handler import integration_handler
from api.alerts.integration.integ_constants import (
    CACHE_KEYS,
    CACHE_TIMEOUTS,
    INTEGRATION_TYPES
)


def _alert_title(alert_log):
    """AlertLog has no `title` column (every fallback notification raised AttributeError);
    use the rule name, else the message."""
    title = getattr(alert_log, 'title', None)
    if title:
        return title
    name = getattr(getattr(alert_log, 'rule', None), 'name', None)
    if name:
        return name
    return (getattr(alert_log, 'message', '') or 'Alert')[:80]

logger = logging.getLogger(__name__)


class FallbackHandler:
    """
    Handles fallback logic for integration failures
    Maintains existing validation and security logic
    """
    
    def __init__(self):
        self.fallback_strategies = {}
        self.fallback_stats = {
            'total_fallbacks': 0,
            'successful_fallbacks': 0,
            'failed_fallbacks': 0,
            'fallbacks_by_type': {},
            'last_fallback': None
        }
        self._register_default_fallbacks()
    
    def _register_default_fallbacks(self):
        """
        Register default fallback strategies
        """
        self.fallback_strategies = {
            'webhook': self._webhook_fallback,
            'email': self._email_fallback,
            'sms': self._sms_fallback,
            'slack': self._slack_fallback,
            'teams': self._teams_fallback,
            'prometheus': self._prometheus_fallback,
            'grafana': self._grafana_fallback,
            'default': self._default_fallback
        }
    
    def handle_integration_failure(self, alert_id: int, error: str, 
                                 result: Optional[Dict[str, Any]] = None) -> bool:
        """
        Handle integration failure with fallback logic
        """
        try:
            self.fallback_stats['total_fallbacks'] += 1
            self.fallback_stats['last_fallback'] = django_tz.now().isoformat()
            
            # Get alert information
            alert_log = self._get_alert_log(alert_id)
            if not alert_log:
                logger.error(f"Alert log not found for ID: {alert_id}")
                return False
            
            # Determine integration type from result or alert
            integration_type = self._determine_integration_type(result, alert_log)
            
            # Get fallback strategy
            fallback_strategy = self.fallback_strategies.get(integration_type, 
                                                           self.fallback_strategies['default'])
            
            # Execute fallback
            fallback_result = fallback_strategy(alert_log, error, result)
            
            if fallback_result.get('success', False):
                self.fallback_stats['successful_fallbacks'] += 1
                
                # Update fallback type stats
                self.fallback_stats['fallbacks_by_type'][integration_type] = \
                    self.fallback_stats['fallbacks_by_type'].get(integration_type, 0) + 1
                
                logger.info(f"Fallback successful for alert {alert_id} using {integration_type} strategy")
                return True
            else:
                self.fallback_stats['failed_fallbacks'] += 1
                logger.error(f"Fallback failed for alert {alert_id}: {fallback_result.get('error')}")
                return False
                
        except Exception as e:
            logger.error(f"Error handling integration failure: {e}")
            self.fallback_stats['failed_fallbacks'] += 1
            return False
    
    def _get_alert_log(self, alert_id: int) -> Optional[AlertLog]:
        """
        Get alert log by ID
        """
        try:
            return AlertLog.objects.get(id=alert_id)
        except AlertLog.DoesNotExist:
            return None
        except Exception as e:
            logger.error(f"Error getting alert log: {e}")
            return None
    
    def _determine_integration_type(self, result: Optional[Dict[str, Any]], 
                                   alert_log: AlertLog) -> str:
        """
        Determine integration type from result or alert
        """
        try:
            # Try to get from result
            if result and 'channel' in result:
                return result['channel']
            
            # Try to get from alert metadata
            metadata = getattr(alert_log, 'metadata', {})
            if 'integration_type' in metadata:
                return metadata['integration_type']
            
            # Try to get from alert rule
            alert_rule = getattr(alert_log, 'alert_rule', None)
            if alert_rule:
                integration_config = getattr(alert_rule, 'integration_config', {})
                if 'type' in integration_config:
                    return integration_config['type']
            
            # Default to webhook
            return 'webhook'
            
        except Exception as e:
            logger.error(f"Error determining integration type: {e}")
            return 'default'
    
    def _webhook_fallback(self, alert_log: AlertLog, error: str, 
                         result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Fallback strategy for webhook failures
        """
        try:
            # Try alternative webhook if configured
            metadata = getattr(alert_log, 'metadata', {})
            alternative_webhooks = metadata.get('alternative_webhooks', [])
            
            if alternative_webhooks:
                for webhook_url in alternative_webhooks:
                    try:
                        fallback_result = integration_handler.process_alert_data({
                            'title': _alert_title(alert_log),
                            'severity': alert_log.severity,
                            'message': alert_log.message,
                            'channel': 'webhook',
                            'webhook_url': webhook_url,
                            'timestamp': alert_log.triggered_at.isoformat()
                        })
                        
                        if fallback_result.get('success', False):
                            return {
                                'success': True,
                                'message': f'Webhook fallback successful using alternative URL: {webhook_url}',
                                'fallback_type': 'alternative_webhook'
                            }
                    except Exception as e:
                        logger.warning(f"Alternative webhook failed: {e}")
                        continue
            
            # Fallback to email notification
            return self._fallback_to_email(alert_log, error, "webhook")
            
        except Exception as e:
            logger.error(f"Error in webhook fallback: {e}")
            return {
                'success': False,
                'error': 'Operation failed'
            }
    
    def _email_fallback(self, alert_log: AlertLog, error: str, 
                       result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Fallback strategy for email failures
        """
        try:
            # Try alternative email addresses
            metadata = getattr(alert_log, 'metadata', {})
            alternative_emails = metadata.get('alternative_emails', [])
            
            if alternative_emails:
                for email_address in alternative_emails:
                    try:
                        fallback_result = integration_handler.process_alert_data({
                            'title': _alert_title(alert_log),
                            'severity': alert_log.severity,
                            'message': alert_log.message,
                            'channel': 'email',
                            'to_email': email_address,
                            'subject': f"[ALERT] {_alert_title(alert_log)}",
                            'timestamp': alert_log.triggered_at.isoformat()
                        })
                        
                        if fallback_result.get('success', False):
                            return {
                                'success': True,
                                'message': f'Email fallback successful using alternative address: {email_address}',
                                'fallback_type': 'alternative_email'
                            }
                    except Exception as e:
                        logger.warning(f"Alternative email failed: {e}")
                        continue
            
            # Fallback to SMS notification
            return self._fallback_to_sms(alert_log, error, "email")
            
        except Exception as e:
            logger.error(f"Error in email fallback: {e}")
            return {
                'success': False,
                'error': 'Operation failed'
            }
    
    def _sms_fallback(self, alert_log: AlertLog, error: str, 
                     result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Fallback strategy for SMS failures
        """
        try:
            # Try alternative phone numbers
            metadata = getattr(alert_log, 'metadata', {})
            alternative_phones = metadata.get('alternative_phones', [])
            
            if alternative_phones:
                for phone_number in alternative_phones:
                    try:
                        fallback_result = integration_handler.process_alert_data({
                            'title': _alert_title(alert_log),
                            'severity': alert_log.severity,
                            'message': alert_log.message,
                            'channel': 'sms',
                            'phone_number': phone_number,
                            'timestamp': alert_log.triggered_at.isoformat()
                        })
                        
                        if fallback_result.get('success', False):
                            return {
                                'success': True,
                                'message': f'SMS fallback successful using alternative phone: {phone_number}',
                                'fallback_type': 'alternative_phone'
                            }
                    except Exception as e:
                        logger.warning(f"Alternative SMS failed: {e}")
                        continue
            
            # Fallback to email notification
            return self._fallback_to_email(alert_log, error, "sms")
            
        except Exception as e:
            logger.error(f"Error in SMS fallback: {e}")
            return {
                'success': False,
                'error': 'Operation failed'
            }
    
    def _slack_fallback(self, alert_log: AlertLog, error: str, 
                       result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Fallback strategy for Slack failures
        """
        try:
            # Try alternative Slack channels
            metadata = getattr(alert_log, 'metadata', {})
            alternative_channels = metadata.get('alternative_slack_channels', [])
            
            if alternative_channels:
                for channel in alternative_channels:
                    try:
                        fallback_result = integration_handler.process_alert_data({
                            'title': _alert_title(alert_log),
                            'severity': alert_log.severity,
                            'message': alert_log.message,
                            'channel': 'webhook',
                            'webhook_url': metadata.get('slack_webhook_url', ''),
                            'channel_name': channel,
                            'timestamp': alert_log.triggered_at.isoformat()
                        })
                        
                        if fallback_result.get('success', False):
                            return {
                                'success': True,
                                'message': f'Slack fallback successful using alternative channel: {channel}',
                                'fallback_type': 'alternative_slack_channel'
                            }
                    except Exception as e:
                        logger.warning(f"Alternative Slack channel failed: {e}")
                        continue
            
            # Fallback to email notification
            return self._fallback_to_email(alert_log, error, "slack")
            
        except Exception as e:
            logger.error(f"Error in Slack fallback: {e}")
            return {
                'success': False,
                'error': 'Operation failed'
            }
    
    def _teams_fallback(self, alert_log: AlertLog, error: str, 
                       result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Fallback strategy for Teams failures
        """
        try:
            # Try alternative Teams webhooks
            metadata = getattr(alert_log, 'metadata', {})
            alternative_webhooks = metadata.get('alternative_teams_webhooks', [])
            
            if alternative_webhooks:
                for webhook_url in alternative_webhooks:
                    try:
                        fallback_result = integration_handler.process_alert_data({
                            'title': _alert_title(alert_log),
                            'severity': alert_log.severity,
                            'message': alert_log.message,
                            'channel': 'webhook',
                            'webhook_url': webhook_url,
                            'timestamp': alert_log.triggered_at.isoformat()
                        })
                        
                        if fallback_result.get('success', False):
                            return {
                                'success': True,
                                'message': f'Teams fallback successful using alternative webhook',
                                'fallback_type': 'alternative_teams_webhook'
                            }
                    except Exception as e:
                        logger.warning(f"Alternative Teams webhook failed: {e}")
                        continue
            
            # Fallback to email notification
            return self._fallback_to_email(alert_log, error, "teams")
            
        except Exception as e:
            logger.error(f"Error in Teams fallback: {e}")
            return {
                'success': False,
                'error': 'Operation failed'
            }
    
    def _prometheus_fallback(self, alert_log: AlertLog, error: str, 
                           result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Fallback strategy for Prometheus failures
        """
        try:
            # Log Prometheus failure and create internal alert
            logger.warning(f"Prometheus integration failed for alert {alert_log.id}: {error}")
            
            # Create internal notification
            return self._create_internal_notification(alert_log, error, "prometheus")
            
        except Exception as e:
            logger.error(f"Error in Prometheus fallback: {e}")
            return {
                'success': False,
                'error': 'Operation failed'
            }
    
    def _grafana_fallback(self, alert_log: AlertLog, error: str, 
                         result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Fallback strategy for Grafana failures
        """
        try:
            # Log Grafana failure and create internal alert
            logger.warning(f"Grafana integration failed for alert {alert_log.id}: {error}")
            
            # Create internal notification
            return self._create_internal_notification(alert_log, error, "grafana")
            
        except Exception as e:
            logger.error(f"Error in Grafana fallback: {e}")
            return {
                'success': False,
                'error': 'Operation failed'
            }
    
    def _default_fallback(self, alert_log: AlertLog, error: str, 
                         result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Default fallback strategy
        """
        try:
            # Create internal notification
            return self._create_internal_notification(alert_log, error, "default")
            
        except Exception as e:
            logger.error(f"Error in default fallback: {e}")
            return {
                'success': False,
                'error': 'Operation failed'
            }
    
    def _fallback_to_email(self, alert_log: AlertLog, error: str, original_channel: str) -> Dict[str, Any]:
        """
        Fallback to email notification
        """
        try:
            # Get default email from settings
            from django.conf import settings
            default_email = getattr(settings, 'ALERTS_FALLBACK_EMAIL', 'alerts@example.com')
            
            fallback_result = integration_handler.process_alert_data({
                'title': _alert_title(alert_log),
                'severity': alert_log.severity,
                'message': f"Original {original_channel} notification failed: {error}\n\n{alert_log.message}",
                'channel': 'email',
                'to_email': default_email,
                'subject': f"[FALLBACK] {_alert_title(alert_log)}",
                'timestamp': alert_log.triggered_at.isoformat()
            })
            
            if fallback_result.get('success', False):
                return {
                    'success': True,
                    'message': f'Email fallback successful: {default_email}',
                    'fallback_type': 'email_fallback'
                }
            else:
                return {
                    'success': False,
                    'error': fallback_result.get('error', 'Email fallback failed')
                }
                
        except Exception as e:
            logger.error(f"Error in email fallback: {e}")
            return {
                'success': False,
                'error': 'Operation failed'
            }
    
    def _fallback_to_sms(self, alert_log: AlertLog, error: str, original_channel: str) -> Dict[str, Any]:
        """
        Fallback to SMS notification
        """
        try:
            # Get default phone from settings
            from django.conf import settings
            default_phone = getattr(settings, 'ALERTS_FALLBACK_PHONE', '+1234567890')
            
            # Truncate message for SMS
            message = f"[{alert_log.severity.upper()}] {_alert_title(alert_log)}: {alert_log.message}"
            if len(message) > 160:
                message = message[:157] + "..."
            
            fallback_result = integration_handler.process_alert_data({
                'title': _alert_title(alert_log),
                'severity': alert_log.severity,
                'message': message,
                'channel': 'sms',
                'phone_number': default_phone,
                'timestamp': alert_log.triggered_at.isoformat()
            })
            
            if fallback_result.get('success', False):
                return {
                    'success': True,
                    'message': f'SMS fallback successful: {default_phone}',
                    'fallback_type': 'sms_fallback'
                }
            else:
                return {
                    'success': False,
                    'error': fallback_result.get('error', 'SMS fallback failed')
                }
                
        except Exception as e:
            logger.error(f"Error in SMS fallback: {e}")
            return {
                'success': False,
                'error': 'Operation failed'
            }
    
    def _create_internal_notification(self, alert_log: AlertLog, error: str, 
                                    integration_type: str) -> Dict[str, Any]:
        """
        Create internal notification for integration failure
        """
        try:
            # Create notification record
            notification = Notification.objects.create(
                alert_log=alert_log,
                notification_type='internal',
                status='pending',
                message=f"Integration failure for {integration_type}: {error}",
                metadata={
                    'integration_type': integration_type,
                    'original_error': error,
                    'alert_id': alert_log.id,
                    'fallback_triggered': True
                }
            )
            
            # Log the failure
            logger.error(f"Integration failure logged: {notification.id}")
            
            return {
                'success': True,
                'message': f'Internal notification created: {notification.id}',
                'fallback_type': 'internal_notification',
                'notification_id': notification.id
            }
            
        except Exception as e:
            logger.error(f"Error creating internal notification: {e}")
            return {
                'success': False,
                'error': 'Operation failed'
            }
    
    def register_fallback_strategy(self, integration_type: str, strategy: Callable):
        """
        Register custom fallback strategy
        """
        self.fallback_strategies[integration_type] = strategy
        logger.info(f"Registered fallback strategy for: {integration_type}")
    
    def get_fallback_statistics(self) -> Dict[str, Any]:
        """
        Get fallback statistics
        """
        try:
            total_fallbacks = self.fallback_stats['total_fallbacks']
            successful_fallbacks = self.fallback_stats['successful_fallbacks']
            
            success_rate = (successful_fallbacks / max(total_fallbacks, 1)) * 100
            
            return {
                'total_fallbacks': total_fallbacks,
                'successful_fallbacks': successful_fallbacks,
                'failed_fallbacks': self.fallback_stats['failed_fallbacks'],
                'success_rate': success_rate,
                'fallbacks_by_type': self.fallback_stats['fallbacks_by_type'],
                'last_fallback': self.fallback_stats['last_fallback'],
                'registered_strategies': list(self.fallback_strategies.keys()),
                'timestamp': django_tz.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting fallback statistics: {e}")
            return {
                'error': 'Operation failed',
                'timestamp': django_tz.now().isoformat()
            }


# Global fallback handler instance
integration_fallback_handler = FallbackHandler()


# Utility functions
def handle_integration_fallback(alert_id: int, error: str, 
                              result: Optional[Dict[str, Any]] = None) -> bool:
    """
    Handle integration failure with fallback
    """
    return integration_fallback_handler.handle_integration_failure(alert_id, error, result)


def get_fallback_statistics() -> Dict[str, Any]:
    """
    Get fallback statistics
    """
    return integration_fallback_handler.get_fallback_statistics()


# Custom fallback strategy example
def custom_fallback_strategy(alert_log: AlertLog, error: str, 
                           result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Custom fallback strategy example
    """
    try:
        # Create custom fallback logic
        logger.info(f"Custom fallback for alert {alert_log.id}")
        
        # Try multiple fallback options
        fallback_options = [
            lambda: integration_fallback_handler._fallback_to_email(alert_log, error, "custom"),
            lambda: integration_fallback_handler._fallback_to_sms(alert_log, error, "custom"),
            lambda: integration_fallback_handler._create_internal_notification(alert_log, error, "custom")
        ]
        
        for option in fallback_options:
            try:
                result = option()
                if result.get('success', False):
                    return result
            except Exception as e:
                logger.warning(f"Fallback option failed: {e}")
                continue
        
        return {
            'success': False,
            'error': 'All fallback options failed'
        }
        
    except Exception as e:
        logger.error(f"Error in custom fallback strategy: {e}")
        return {
            'success': False,
            'error': 'Operation failed'
        }


# Register custom fallback strategy
integration_fallback_handler.register_fallback_strategy('custom', custom_fallback_strategy)
