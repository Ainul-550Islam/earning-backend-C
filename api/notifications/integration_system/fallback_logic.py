# integration_system/fallback_logic.py
"""Fallback Logic — Graceful degradation when primary services fail."""
import logging, time
from typing import Any, Callable, Dict, List, Optional
from .integ_exceptions import FallbackFailed
logger = logging.getLogger(__name__)

class FallbackChain:
    """Execute a chain of fallbacks: try primary, then each fallback in order."""
    def __init__(self, name: str = ""):
        self.name = name
        self._handlers: List[Callable] = []
        self._on_fallback: Optional[Callable] = None
        self._on_all_failed: Optional[Callable] = None

    def primary(self, fn: Callable):
        self._handlers.insert(0, fn)
        return self

    def fallback(self, fn: Callable):
        self._handlers.append(fn)
        return self

    def on_fallback(self, fn: Callable):
        self._on_fallback = fn
        return self

    def on_all_failed(self, fn: Callable):
        self._on_all_failed = fn
        return self

    def execute(self, *args, **kwargs) -> Any:
        last_error = None
        for i, handler in enumerate(self._handlers):
            try:
                result = handler(*args, **kwargs)
                if i > 0 and self._on_fallback:
                    self._on_fallback(handler_name=handler.__name__, level=i)
                return result
            except Exception as exc:
                last_error = exc
                logger.warning(f"FallbackChain[{self.name}]: handler {handler.__name__} failed: {exc}")
                if i < len(self._handlers) - 1:
                    time.sleep(0.5)
        if self._on_all_failed:
            return self._on_all_failed(error=last_error)
        raise FallbackFailed(self.name)


class FallbackService:
    """Pre-built fallback strategies for common integration operations."""

    def notify_fallback(self, user_id: int, title: str, message: str) -> Dict:
        """Try push → email → in_app for notification delivery."""
        from .integ_handler import handler
        channels = ["push", "email", "in_app"]
        for channel in channels:
            try:
                result = handler.notify_user(user_id, "announcement", title, message, channel=channel)
                if result.get("success"):
                    logger.info(f"FallbackService.notify: succeeded via {channel}")
                    return result
            except Exception as exc:
                logger.warning(f"FallbackService.notify: {channel} failed: {exc}")
        return {"success": False, "error": "All notification channels failed"}

    def sms_fallback(self, phone: str, message: str) -> Dict:
        """Try ShohoSMS (BD) → Twilio for SMS."""
        chain = FallbackChain("sms")
        def shoho():
            from api.notifications.services.providers.ShohoSMSProvider import shoho_sms_provider
            if not shoho_sms_provider.is_available():
                raise Exception("ShohoSMS not available")
            return shoho_sms_provider.send_sms(phone, message)
        def twilio():
            from api.notifications.services.providers.TwilioProvider import twilio_provider
            if not twilio_provider.is_available():
                raise Exception("Twilio not available")
            return twilio_provider.send_sms(phone, message)
        chain.primary(shoho).fallback(twilio)
        try:
            return chain.execute()
        except FallbackFailed:
            return {"success": False, "error": "All SMS providers failed"}

    def cache_fallback(self, key: str, fetch_fn: Callable, ttl: int = 300) -> Any:
        """Try cache → DB fetch for read operations."""
        from django.core.cache import cache
        cached = cache.get(key)
        if cached is not None:
            return cached
        result = fetch_fn()
        cache.set(key, result, ttl)
        return result


fallback_service = FallbackService()
