"""
Telegram Alert Service — Enhanced Telegram bot with rich formatting, retry logic, and error handling
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

SEVERITY_EMOJI = {
    'low': '🟢',
    'medium': '🟡',
    'high': '🟠',
    'critical': '🔴',
}

SEVERITY_COLOR = {
    'low': '#36a64f',
    'medium': '#ffcc00',
    'high': '#ff6600',
    'critical': '#cc0000',
}


class TelegramAlertService:
    """Enhanced Telegram alert service with retry logic, rate limiting, and rich formatting"""

    def __init__(self):
        self.rate_limit_cache_key = "telegram_rate_limit"
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

    def _check_rate_limit(self, bot_token: str, chat_id: str) -> bool:
        """Check if we're rate limited for this bot/chat combination"""
        cache_key = f"{self.rate_limit_cache_key}_{hash(bot_token)}_{hash(chat_id)}"
        rate_limit_until = cache.get(cache_key)
        
        if rate_limit_until and time.time() < rate_limit_until:
            logger.warning(f"Telegram rate limited until {rate_limit_until}")
            return False
        
        return True

    def _handle_rate_limit(self, bot_token: str, chat_id: str, retry_after: int):
        """Handle rate limiting by setting cache"""
        cache_key = f"{self.rate_limit_cache_key}_{hash(bot_token)}_{hash(chat_id)}"
        cache.set(cache_key, time.time() + retry_after, timeout=retry_after + 10)

    def _validate_bot_token(self, bot_token: str) -> bool:
        """Validate Telegram bot token format"""
        if not bot_token:
            return False
        
        # Basic validation - Telegram tokens are typically 46 characters
        if len(bot_token) < 40 or len(bot_token) > 50:
            return False
        
        # Check if it contains only valid characters
        if not bot_token.replace('_', '').replace('-', '').isalnum():
            return False
        
        return True

    def _validate_chat_id(self, chat_id: str) -> bool:
        """Validate Telegram chat ID format"""
        if not chat_id:
            return False
        
        # Chat IDs can be numeric (for private chats) or @username (for public channels)
        try:
            int(chat_id)
            return True
        except ValueError:
            # Check if it's a valid username format
            if chat_id.startswith('@') and len(chat_id) > 1:
                return True
        
        return False

    def _build_text_message(self, notification, channel) -> str:
        """Build rich text message for Telegram"""
        config = channel.config
        alert_log = get_effective_alert_log(notification)
        
        severity = alert_log.rule.severity
        emoji = SEVERITY_EMOJI.get(severity, '⚠️')
        
        # Build message with Markdown formatting
        message_parts = [
            f"{emoji} *{alert_log.rule.name}*",
            f"🔸 *Severity:* `{severity.upper()}`",
            f"📝 *Message:* {notification.message}",
            f"📊 *Value:* `{alert_log.trigger_value}` | *Threshold:* `{alert_log.threshold_value}`",
            f"⏰ *Triggered:* {alert_log.triggered_at.strftime('%Y-%m-%d %H:%M:%S UTC')}"
        ]
        
        # Add optional fields
        if hasattr(alert_log, 'source') and alert_log.source:
            message_parts.append(f"📍 *Source:* {alert_log.source}")
        
        if hasattr(alert_log, 'tags') and alert_log.tags:
            tags_text = ", ".join([f"#{tag}" for tag in alert_log.tags[:5]])
            if len(alert_log.tags) > 5:
                tags_text += f" +{len(alert_log.tags) - 5} more"
            message_parts.append(f"🏷️ *Tags:* {tags_text}")
        
        # Add context if available
        if hasattr(alert_log, 'context') and alert_log.context:
            context_text = json.dumps(alert_log.context, indent=2)
            message_parts.append(f"🔍 *Context:* ```{context_text}````")
        
        return "\n".join(message_parts)

    def _build_html_message(self, notification, channel) -> str:
        """Build HTML message for Telegram"""
        config = channel.config
        alert_log = get_effective_alert_log(notification)
        
        severity = alert_log.rule.severity
        emoji = SEVERITY_EMOJI.get(severity, '⚠️')
        color = SEVERITY_COLOR.get(severity, '#888888')
        
        # Build HTML message
        message_parts = [
            f"{emoji} <b>{alert_log.rule.name}</b>",
            f"🔸 <b>Severity:</b> <code>{severity.upper()}</code>",
            f"📝 <b>Message:</b> {notification.message}",
            f"📊 <b>Value:</b> <code>{alert_log.trigger_value}</code> | <b>Threshold:</b> <code>{alert_log.threshold_value}</code>",
            f"⏰ <b>Triggered:</b> {alert_log.triggered_at.strftime('%Y-%m-%d %H:%M:%S UTC')}"
        ]
        
        # Add optional fields
        if hasattr(alert_log, 'source') and alert_log.source:
            message_parts.append(f"📍 <b>Source:</b> {alert_log.source}")
        
        if hasattr(alert_log, 'tags') and alert_log.tags:
            tags_text = ", ".join([f"#{tag}" for tag in alert_log.tags[:5]])
            if len(alert_log.tags) > 5:
                tags_text += f" +{len(alert_log.tags) - 5} more"
            message_parts.append(f"🏷️ <b>Tags:</b> {tags_text}")
        
        return "\n".join(message_parts)

    def _build_inline_keyboard(self, config: Dict[str, Any]) -> Optional[List[List[Dict[str, Any]]]]:
        """Build inline keyboard for message"""
        actions = config.get('actions', [])
        if not actions:
            return None
        
        keyboard = []
        for action in actions:
            keyboard.append([{
                'text': action.get('text', 'Action'),
                'url': action.get('url', '#')
            }])
        
        return keyboard

    def send(self, notification, channel, use_html: bool = False) -> bool:
        """
        Enhanced send method with retry logic and error handling
        
        Args:
            notification: Notification object
            channel: Channel object
            use_html: Whether to use HTML formatting (default: Markdown)
        
        Returns:
            bool: Success status
        """
        config = channel.config
        bot_token = config.get('bot_token')
        chat_id = notification.recipient

        if not bot_token:
            logger.error("Telegram bot_token not configured")
            return False

        if not self._validate_bot_token(bot_token):
            logger.error("Invalid Telegram bot_token format")
            return False

        if not self._validate_chat_id(chat_id):
            logger.error("Invalid Telegram chat_id format")
            return False

        # Check rate limiting
        if not self._check_rate_limit(bot_token, chat_id):
            return False

        # Choose message format
        if use_html or config.get('use_html', False):
            text = self._build_html_message(notification, channel)
            parse_mode = 'HTML'
        else:
            text = self._build_text_message(notification, channel)
            parse_mode = 'Markdown'

        # Build request payload
        payload = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': parse_mode,
            'disable_web_page_preview': config.get('disable_web_page_preview', False),
            'disable_notification': config.get('disable_notification', False)
        }

        # Add reply markup if configured
        inline_keyboard = self._build_inline_keyboard(config)
        if inline_keyboard:
            payload['reply_markup'] = {
                'inline_keyboard': inline_keyboard
            }

        try:
            # Send message with retry logic
            response = self.session.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json=payload,
                timeout=self.timeout
            )
            
            # Handle rate limiting
            if response.status_code == 429:
                retry_after = int(response.json().get('parameters', {}).get('retry_after', 60))
                self._handle_rate_limit(bot_token, chat_id, retry_after)
                logger.warning(f"Telegram rate limited, retry after {retry_after} seconds")
                return False
            
            # Handle other HTTP errors
            response.raise_for_status()
            
            # Check for Telegram-specific errors
            response_data = response.json()
            if not response_data.get('ok', True):
                error_code = response_data.get('error_code', 'unknown')
                error_description = response_data.get('description', 'Unknown Telegram error')
                logger.error(f"Telegram API error {error_code}: {error_description}")
                
                # Handle specific error codes
                if error_code == 401:
                    logger.error("Telegram bot token is invalid or revoked")
                elif error_code == 400:
                    logger.error("Bad request - check bot token, chat_id, or message format")
                elif error_code == 403:
                    logger.error("Bot was blocked by the user")
                
                return False
            
            channel.record_success()
            logger.info(f"Telegram message sent successfully to {chat_id}")
            return True

        except requests.exceptions.Timeout:
            logger.error("TelegramAlertService timeout error")
            channel.record_failure()
            return False
            
        except requests.exceptions.ConnectionError:
            logger.error("TelegramAlertService connection error")
            channel.record_failure()
            return False
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"TelegramAlertService HTTP error: {e}")
            channel.record_failure()
            return False
            
        except Exception as e:
            logger.error(f"TelegramAlertService unexpected error: {e}")
            channel.record_failure()
            return False

    def send_test_message(self, bot_token: str, chat_id: str) -> bool:
        """
        Send a test message to verify bot connectivity
        
        Args:
            bot_token: Telegram bot token
            chat_id: Telegram chat ID
        
        Returns:
            bool: Success status
        """
        if not bot_token or not chat_id:
            logger.error("Bot token and chat ID required for test message")
            return False

        if not self._validate_bot_token(bot_token):
            logger.error("Invalid Telegram bot token format")
            return False

        if not self._validate_chat_id(chat_id):
            logger.error("Invalid Telegram chat ID format")
            return False

        test_payload = {
            'chat_id': chat_id,
            'text': "🧪 *Test message from Alert System*\n\n✅ Telegram bot is working correctly!",
            'parse_mode': 'Markdown',
            'disable_web_page_preview': True
        }

        try:
            response = self.session.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json=test_payload,
                timeout=10
            )
            response.raise_for_status()
            
            response_data = response.json()
            if response_data.get('ok', True):
                logger.info("Telegram test message sent successfully")
                return True
            else:
                logger.error(f"Telegram test message failed: {response_data.get('description')}")
                return False
                
        except Exception as e:
            logger.error(f"Telegram test message error: {e}")
            return False

    def get_bot_info(self, bot_token: str) -> Optional[Dict[str, Any]]:
        """
        Get bot information from Telegram API
        
        Args:
            bot_token: Telegram bot token
        
        Returns:
            Dict with bot info or None if error
        """
        if not self._validate_bot_token(bot_token):
            return None

        try:
            response = self.session.get(
                f"https://api.telegram.org/bot{bot_token}/getMe",
                timeout=10
            )
            response.raise_for_status()
            
            response_data = response.json()
            if response_data.get('ok', True):
                bot_info = response_data.get('result', {})
                logger.info(f"Bot info retrieved: {bot_info.get('username')}")
                return bot_info
            else:
                logger.error(f"Failed to get bot info: {response_data.get('description')}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting bot info: {e}")
            return None

    def get_chat_info(self, bot_token: str, chat_id: str) -> Optional[Dict[str, Any]]:
        """
        Get chat information from Telegram API
        
        Args:
            bot_token: Telegram bot token
            chat_id: Telegram chat ID
        
        Returns:
            Dict with chat info or None if error
        """
        if not self._validate_bot_token(bot_token) or not self._validate_chat_id(chat_id):
            return None

        try:
            response = self.session.post(
                f"https://api.telegram.org/bot{bot_token}/getChat",
                json={'chat_id': chat_id},
                timeout=10
            )
            response.raise_for_status()
            
            response_data = response.json()
            if response_data.get('ok', True):
                chat_info = response_data.get('result', {})
                logger.info(f"Chat info retrieved: {chat_info.get('type', 'unknown')}")
                return chat_info
            else:
                logger.error(f"Failed to get chat info: {response_data.get('description')}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting chat info: {e}")
            return None

    def validate_configuration(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate Telegram configuration
        
        Args:
            config: Channel configuration
        
        Returns:
            Dict with validation results
        """
        errors = []
        warnings = []
        
        # Validate bot token
        bot_token = config.get('bot_token')
        if not bot_token:
            errors.append("Bot token is required")
        elif not self._validate_bot_token(bot_token):
            errors.append("Invalid bot token format")
        
        # Validate chat ID
        chat_id = config.get('chat_id')
        if not chat_id:
            errors.append("Chat ID is required")
        elif not self._validate_chat_id(chat_id):
            errors.append("Invalid chat ID format")
        
        # Check for optional settings
        if config.get('use_html') and config.get('parse_mode') == 'Markdown':
            warnings.append("HTML formatting conflicts with Markdown parse_mode")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }

    def close(self):
        """Close the HTTP session"""
        if self.session:
            self.session.close()
