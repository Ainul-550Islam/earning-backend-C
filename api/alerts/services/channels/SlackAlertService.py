"""
Slack Alert Service — Enhanced Slack webhook with rich blocks, retry logic, and error handling
"""
import logging
from ._shared import get_effective_alert_log
import requests
import json
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from django.core.cache import cache
from django.conf import settings
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

SEVERITY_COLOR = {
    'low': '#36a64f',
    'medium': '#ffcc00',
    'high': '#ff6600',
    'critical': '#cc0000',
}

SEVERITY_EMOJI = {
    'low': '🟢',
    'medium': '🟡',
    'high': '🟠',
    'critical': '🔴',
}


class SlackAlertService:
    """Enhanced Slack alert service with retry logic, rate limiting, and rich formatting"""

    def __init__(self):
        self.rate_limit_cache_key = "slack_rate_limit"
        self.max_retries = 3
        self.timeout = 30
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        """Create HTTP session with retry strategy"""
        session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["POST"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session

    def _check_rate_limit(self, webhook_url: str) -> bool:
        """Check if we're rate limited for this webhook"""
        cache_key = f"{self.rate_limit_cache_key}_{hash(webhook_url)}"
        rate_limit_until = cache.get(cache_key)
        
        if rate_limit_until and time.time() < rate_limit_until:
            logger.warning(f"Slack rate limited until {rate_limit_until}")
            return False
        
        return True

    def _handle_rate_limit(self, webhook_url: str, retry_after: int):
        """Handle rate limiting by setting cache"""
        cache_key = f"{self.rate_limit_cache_key}_{hash(webhook_url)}"
        cache.set(cache_key, time.time() + retry_after, timeout=retry_after + 10)

    def _build_basic_payload(self, notification, channel) -> Dict[str, Any]:
        """Build basic Slack payload"""
        config = channel.config
        alert_log = get_effective_alert_log(notification)
        
        severity = alert_log.rule.severity
        color = SEVERITY_COLOR.get(severity, '#888888')
        emoji = SEVERITY_EMOJI.get(severity, '⚠️')
        
        # Build attachment
        attachment = {
            "color": color,
            "title": f"{emoji} {alert_log.rule.name}",
            "text": notification.message,
            "fields": [
                {
                    "title": "Severity",
                    "value": severity.upper(),
                    "short": True
                },
                {
                    "title": "Value",
                    "value": str(alert_log.trigger_value),
                    "short": True
                },
                {
                    "title": "Threshold",
                    "value": str(alert_log.threshold_value),
                    "short": True
                },
                {
                    "title": "Triggered At",
                    "value": alert_log.triggered_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
                    "short": True
                }
            ],
            "footer": "Alert System",
            "ts": int(alert_log.triggered_at.timestamp())
        }
        
        # Add optional fields
        if hasattr(alert_log, 'source') and alert_log.source:
            attachment["fields"].append({
                "title": "Source",
                "value": alert_log.source,
                "short": True
            })
        
        if hasattr(alert_log, 'tags') and alert_log.tags:
            tags_text = ", ".join(alert_log.tags[:3])  # Limit to 3 tags
            if len(alert_log.tags) > 3:
                tags_text += f" +{len(alert_log.tags) - 3} more"
            
            attachment["fields"].append({
                "title": "Tags",
                "value": tags_text,
                "short": True
            })
        
        return {
            "attachments": [attachment],
            "username": config.get('username', 'Alert System'),
            "icon_emoji": config.get('icon_emoji', ':warning:'),
            "channel": config.get('channel', None)  # Override channel if specified
        }

    def _build_rich_payload(self, notification, channel) -> Dict[str, Any]:
        """Build rich Slack payload with blocks"""
        config = channel.config
        alert_log = get_effective_alert_log(notification)
        
        severity = alert_log.rule.severity
        color = SEVERITY_COLOR.get(severity, '#888888')
        emoji = SEVERITY_EMOJI.get(severity, '⚠️')
        
        # Build blocks
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{emoji} {alert_log.rule.name}"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Severity:* {severity.upper()}\n*Message:* {notification.message}"
                }
            },
            {
                "type": "divider"
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Value:* `{alert_log.trigger_value}`"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Threshold:* `{alert_log.threshold_value}`"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Triggered:* {alert_log.triggered_at.strftime('%Y-%m-%d %H:%M:%S UTC')}"
                    }
                ]
            }
        ]
        
        # Add context section if available
        if hasattr(alert_log, 'context') and alert_log.context:
            blocks.append({
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Context:* {json.dumps(alert_log.context, indent=2)}"
                    }
                ]
            })
        
        # Add actions if configured
        actions = config.get('actions', [])
        if actions:
            action_blocks = []
            for action in actions:
                action_blocks.append({
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": action.get('text', 'Action')
                    },
                    "url": action.get('url', '#')
                })
            
            blocks.append({
                "type": "actions",
                "elements": action_blocks
            })
        
        return {
            "blocks": blocks,
            "username": config.get('username', 'Alert System'),
            "icon_emoji": config.get('icon_emoji', ':warning:'),
            "channel": config.get('channel', None)
        }

    def send(self, notification, channel, use_blocks: bool = False) -> bool:
        """
        Enhanced send method with retry logic and error handling
        
        Args:
            notification: Notification object
            channel: Channel object
            use_blocks: Whether to use block format (richer) or attachment format
        
        Returns:
            bool: Success status
        """
        config = channel.config
        webhook_url = config.get('webhook_url')
        
        if not webhook_url:
            logger.error("Slack webhook_url not configured")
            return False

        # Check rate limiting
        if not self._check_rate_limit(webhook_url):
            return False

        # Choose payload format
        if use_blocks or config.get('use_blocks', False):
            payload = self._build_rich_payload(notification, channel)
        else:
            payload = self._build_basic_payload(notification, channel)

        # Add custom headers if configured
        headers = {
            'Content-Type': 'application/json'
        }
        
        custom_headers = config.get('headers', {})
        headers.update(custom_headers)

        try:
            # Send message with retry logic
            response = self.session.post(
                webhook_url,
                json=payload,
                headers=headers,
                timeout=self.timeout
            )
            
            # Handle rate limiting
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 60))
                self._handle_rate_limit(webhook_url, retry_after)
                logger.warning(f"Slack rate limited, retry after {retry_after} seconds")
                return False
            
            # Handle other HTTP errors
            response.raise_for_status()
            
            # Check for Slack-specific errors
            response_data = response.json()
            if not response_data.get('ok', True):
                error_msg = response_data.get('error', 'Unknown Slack error')
                logger.error(f"Slack API error: {error_msg}")
                return False
            
            channel.record_success()
            logger.info(f"Slack message sent successfully to webhook")
            return True

        except requests.exceptions.Timeout:
            logger.error("SlackAlertService timeout error")
            channel.record_failure()
            return False
            
        except requests.exceptions.ConnectionError:
            logger.error("SlackAlertService connection error")
            channel.record_failure()
            return False
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"SlackAlertService HTTP error: {e}")
            channel.record_failure()
            return False
            
        except Exception as e:
            logger.error(f"SlackAlertService unexpected error: {e}")
            channel.record_failure()
            return False

    def send_test_message(self, webhook_url: str, channel: str = None) -> bool:
        """
        Send a test message to verify webhook connectivity
        
        Args:
            webhook_url: Slack webhook URL
            channel: Optional channel override
        
        Returns:
            bool: Success status
        """
        if not webhook_url:
            logger.error("Webhook URL required for test message")
            return False

        test_payload = {
            "text": "🧪 Test message from Alert System",
            "attachments": [{
                "color": "#36a64f",
                "title": "Test Alert",
                "text": "This is a test message to verify Slack webhook connectivity.",
                "fields": [
                    {"title": "Status", "value": "✅ Connected", "short": True},
                    {"title": "Time", "value": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"), "short": True}
                ],
                "footer": "Alert System Test",
                "ts": int(datetime.now(timezone.utc).timestamp())
            }],
            "username": "Alert System Test",
            "icon_emoji": ":robot_face:"
        }
        
        if channel:
            test_payload["channel"] = channel

        try:
            response = self.session.post(
                webhook_url,
                json=test_payload,
                timeout=10
            )
            response.raise_for_status()
            
            response_data = response.json()
            if response_data.get('ok', True):
                logger.info("Slack test message sent successfully")
                return True
            else:
                logger.error(f"Slack test message failed: {response_data.get('error')}")
                return False
                
        except Exception as e:
            logger.error(f"Slack test message error: {e}")
            return False

    def validate_webhook_url(self, webhook_url: str) -> bool:
        """
        Validate Slack webhook URL format
        
        Args:
            webhook_url: Webhook URL to validate
        
        Returns:
            bool: Validity status
        """
        if not webhook_url:
            return False
        
        # Basic URL validation
        if not webhook_url.startswith('https://hooks.slack.com/'):
            return False
        
        # Additional validation could be added here
        return True

    def get_webhook_info(self, webhook_url: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a webhook (limited by Slack API)
        
        Args:
            webhook_url: Webhook URL
        
        Returns:
            Dict with webhook info or None if error
        """
        # Note: Slack doesn't provide a direct way to get webhook info
        # This is a placeholder for future implementation
        return {
            "url": webhook_url,
            "validated": self.validate_webhook_url(webhook_url),
            "status": "active" if self.validate_webhook_url(webhook_url) else "invalid"
        }

    def close(self):
        """Close the HTTP session"""
        if self.session:
            self.session.close()
