# api/support/plugins.py
import logging
from abc import ABC, abstractmethod
from typing import Optional

logger = logging.getLogger(__name__)


class NotificationBackend(ABC):
    @abstractmethod
    def send(self, user, title: str, body: str, **kwargs) -> bool:
        pass


class AIBackend(ABC):
    @abstractmethod
    def respond(self, text: str, context: dict = None) -> Optional[str]:
        pass


class AnthropicBackend(AIBackend):
    def respond(self, text: str, context: dict = None) -> Optional[str]:
        from api.support.openai import get_ai_response
        return get_ai_response(text, context=context)


class EmailNotificationBackend(NotificationBackend):
    def send(self, user, title: str, body: str, **kwargs) -> bool:
        try:
            from django.core.mail import send_mail
            from django.conf import settings
            if user.email:
                send_mail(title, body, getattr(settings, 'DEFAULT_FROM_EMAIL', 'support@site.com'),
                          [user.email], fail_silently=True)
                return True
        except Exception:
            pass
        return False


class NotificationsAppBackend(NotificationBackend):
    def send(self, user, title: str, body: str, **kwargs) -> bool:
        from api.support.integrations.integ_adapter import notifications_adapter
        return notifications_adapter.send(user, title, body, **kwargs)


class PluginRegistry:
    def __init__(self):
        self._ai_backend = AnthropicBackend()
        self._notif_backend = NotificationsAppBackend()

    def set_ai_backend(self, backend: AIBackend) -> None:
        self._ai_backend = backend

    def set_notification_backend(self, backend: NotificationBackend) -> None:
        self._notif_backend = backend

    def get_ai_response(self, text: str, context: dict = None) -> Optional[str]:
        return self._ai_backend.respond(text, context)

    def send_notification(self, user, title: str, body: str, **kwargs) -> bool:
        return self._notif_backend.send(user, title, body, **kwargs)


plugin_registry = PluginRegistry()