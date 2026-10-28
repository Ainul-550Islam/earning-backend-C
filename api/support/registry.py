# api/support/registry.py
"""
Support system plugin registry.
Central registration point for notification backends, AI backends,
channel integrations, and custom hooks.
Full code — no summarizing.
"""
import logging
from typing import Any, Callable, Dict, List, Optional, Type

logger = logging.getLogger(__name__)


class SupportPluginRegistry:
    """
    Singleton registry for all support system plugins.
    
    Register backends:
        registry.register_notification_backend('telegram', TelegramBackend())
        registry.register_ai_backend('claude', ClaudeBackend())
    
    Fetch:
        backend = registry.get_notification_backend('telegram')
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._notification_backends: Dict[str, Any] = {}
        self._ai_backends:           Dict[str, Any] = {}
        self._channel_handlers:      Dict[str, Any] = {}  # email, telegram, etc.
        self._pre_hooks:             Dict[str, List[Callable]] = {}
        self._post_hooks:            Dict[str, List[Callable]] = {}
        self._custom_validators:     Dict[str, Callable] = {}
        self._initialized = True

    # ── Notification Backends ─────────────────────────────────
    def register_notification_backend(self, name: str, backend: Any) -> None:
        """Register a notification backend (email, sms, push, telegram, whatsapp)."""
        self._notification_backends[name] = backend
        logger.debug(f'Notification backend registered: {name}')

    def get_notification_backend(self, name: str) -> Optional[Any]:
        return self._notification_backends.get(name)

    def get_all_notification_backends(self) -> Dict[str, Any]:
        return dict(self._notification_backends)

    # ── AI Backends ───────────────────────────────────────────
    def register_ai_backend(self, name: str, backend: Any) -> None:
        """Register an AI backend for auto-responses."""
        self._ai_backends[name] = backend
        logger.debug(f'AI backend registered: {name}')

    def get_primary_ai_backend(self) -> Optional[Any]:
        """Get the primary AI backend (first registered)."""
        if self._ai_backends:
            return next(iter(self._ai_backends.values()))
        return None

    def get_ai_backend(self, name: str) -> Optional[Any]:
        return self._ai_backends.get(name)

    # ── Channel Handlers ──────────────────────────────────────
    def register_channel_handler(self, channel: str, handler: Any) -> None:
        """Register incoming channel handler (email→ticket, telegram→ticket)."""
        self._channel_handlers[channel] = handler
        logger.debug(f'Channel handler registered: {channel}')

    def get_channel_handler(self, channel: str) -> Optional[Any]:
        return self._channel_handlers.get(channel)

    def get_active_channels(self) -> List[str]:
        return list(self._channel_handlers.keys())

    # ── Hooks ─────────────────────────────────────────────────
    def register_pre_hook(self, event: str, hook: Callable) -> None:
        """Register a pre-event hook (runs before ticket created, dispute submitted, etc.)."""
        if event not in self._pre_hooks:
            self._pre_hooks[event] = []
        self._pre_hooks[event].append(hook)

    def register_post_hook(self, event: str, hook: Callable) -> None:
        """Register a post-event hook (runs after action completes)."""
        if event not in self._post_hooks:
            self._post_hooks[event] = []
        self._post_hooks[event].append(hook)

    def run_pre_hooks(self, event: str, **kwargs) -> bool:
        """Run all pre-hooks for an event. Returns False if any hook blocks the action."""
        for hook in self._pre_hooks.get(event, []):
            try:
                result = hook(**kwargs)
                if result is False:  # Hook explicitly blocked the action
                    return False
            except Exception as e:
                logger.error(f'Pre-hook error [{event}]: {e}')
        return True

    def run_post_hooks(self, event: str, **kwargs) -> None:
        """Run all post-hooks for an event."""
        for hook in self._post_hooks.get(event, []):
            try:
                hook(**kwargs)
            except Exception as e:
                logger.error(f'Post-hook error [{event}]: {e}')

    # ── Custom Validators ─────────────────────────────────────
    def register_validator(self, name: str, validator: Callable) -> None:
        """Register a custom validator function."""
        self._custom_validators[name] = validator

    def get_validator(self, name: str) -> Optional[Callable]:
        return self._custom_validators.get(name)

    # ── Summary ───────────────────────────────────────────────
    def get_summary(self) -> dict:
        return {
            'notification_backends': list(self._notification_backends.keys()),
            'ai_backends':           list(self._ai_backends.keys()),
            'channel_handlers':      list(self._channel_handlers.keys()),
            'pre_hook_events':       list(self._pre_hooks.keys()),
            'post_hook_events':      list(self._post_hooks.keys()),
            'custom_validators':     list(self._custom_validators.keys()),
        }

    def reset(self):
        """Reset registry — for testing only."""
        self._notification_backends.clear()
        self._ai_backends.clear()
        self._channel_handlers.clear()
        self._pre_hooks.clear()
        self._post_hooks.clear()
        self._custom_validators.clear()


# ── Singleton ─────────────────────────────────────────────────
support_registry = SupportPluginRegistry()


def setup_default_registry():
    """Setup default registry with all built-in backends."""
    # Notification backends
    try:
        from api.support.plugins import NotificationsAppBackend, EmailNotificationBackend
        support_registry.register_notification_backend('app',   NotificationsAppBackend())
        support_registry.register_notification_backend('email', EmailNotificationBackend())
    except Exception as e:
        logger.debug(f'Default notification backends: {e}')

    # AI backends
    try:
        from api.support.plugins import AnthropicBackend
        support_registry.register_ai_backend('claude', AnthropicBackend())
    except Exception as e:
        logger.debug(f'Default AI backends: {e}')

    # Channel handlers
    try:
        from api.support.integrations.email_to_ticket import EmailToTicketHandler
        support_registry.register_channel_handler('email', EmailToTicketHandler())
    except Exception as e:
        logger.debug(f'Email channel handler: {e}')

    try:
        from api.support.integrations.telegram_bot import TelegramBotHandler
        support_registry.register_channel_handler('telegram', TelegramBotHandler())
    except Exception as e:
        logger.debug(f'Telegram channel handler: {e}')