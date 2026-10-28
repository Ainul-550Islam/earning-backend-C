"""
Webhook dispatcher for Telemetry Observability.

Sends HTTP POST payloads to configured external URLs when telemetry
events occur (primarily alert lifecycle events).

WIRING (apps.py ready()):
    from .events import event_bus, EventType
    from .webhooks import WebhookDispatcher

    dispatcher = WebhookDispatcher(urls=settings.TELEMETRY_WEBHOOK_URLS)
    event_bus.subscribe(EventType.ALERT_TRIGGERED,    dispatcher.on_alert_triggered)
    event_bus.subscribe(EventType.ALERT_ACKNOWLEDGED, dispatcher.on_alert_acknowledged)
    event_bus.subscribe(EventType.ALERT_RESOLVED,     dispatcher.on_alert_resolved)

Settings (settings.py):
    TELEMETRY_WEBHOOK_URLS = [
        'https://hooks.slack.com/services/...',
        'https://your-ops-tool.example.com/webhook',
    ]
    TELEMETRY_WEBHOOK_TIMEOUT = 5   # seconds
    TELEMETRY_WEBHOOK_SECRET  = ''  # HMAC-SHA256 signing secret (optional)
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from typing import Any, Dict, Iterable, List, Optional
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

from .events import Event, EventType

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Payload builders — one per event type (single responsibility)
# ---------------------------------------------------------------------------

def _build_alert_payload(event: Event) -> Dict[str, Any]:
    """Build a normalized webhook payload for alert events."""
    return {
        'event':    event.event_type.value,
        'data':     event.data,
        'metadata': event.metadata,
        'timestamp': event.timestamp.isoformat(),
        'source':   'telemetry_observability',
    }


def _build_health_payload(event: Event) -> Dict[str, Any]:
    return {
        'event':     event.event_type.value,
        'data':      event.data,
        'timestamp': event.timestamp.isoformat(),
        'source':    'telemetry_observability',
    }


# Map each EventType to the appropriate payload builder
_PAYLOAD_BUILDER = {
    EventType.ALERT_TRIGGERED:      _build_alert_payload,
    EventType.ALERT_ACKNOWLEDGED:   _build_alert_payload,
    EventType.ALERT_RESOLVED:       _build_alert_payload,
    EventType.HEALTH_STATUS_CHANGED: _build_health_payload,
}


# ---------------------------------------------------------------------------
# WebhookDispatcher
# ---------------------------------------------------------------------------

class WebhookDispatcher:
    """
    Delivers webhook payloads to a list of target URLs.

    Thread-safety: instances are stateless after __init__; safe for multi-thread use.
    """

    def __init__(
        self,
        urls: Optional[List[str]] = None,
        timeout: int = 5,
        secret: str = '',
        max_retries: int = 2,
    ):
        """
        Args:
            urls:        List of webhook endpoint URLs to deliver to.
            timeout:     HTTP request timeout in seconds.
            secret:      Optional HMAC-SHA256 signing secret.
                         If set, adds X-Telemetry-Signature header.
            max_retries: Number of retry attempts on failure.
        """
        self.urls        = list(urls or [])
        self.timeout     = timeout
        self.secret      = secret
        self.max_retries = max_retries

    # -- public event handlers (subscribe to EventBus) --

    def on_alert_triggered(self, event: Event) -> None:
        """Called by EventBus when EventType.ALERT_TRIGGERED fires."""
        self._dispatch(event)

    def on_alert_acknowledged(self, event: Event) -> None:
        """Called by EventBus when EventType.ALERT_ACKNOWLEDGED fires."""
        self._dispatch(event)

    def on_alert_resolved(self, event: Event) -> None:
        """Called by EventBus when EventType.ALERT_RESOLVED fires."""
        self._dispatch(event)

    def on_health_changed(self, event: Event) -> None:
        """Called by EventBus when EventType.HEALTH_STATUS_CHANGED fires."""
        self._dispatch(event)

    def add_url(self, url: str) -> None:
        """Register an additional webhook URL at runtime."""
        if url not in self.urls:
            self.urls.append(url)

    def remove_url(self, url: str) -> bool:
        """Deregister a webhook URL. Returns True if it was found."""
        if url in self.urls:
            self.urls.remove(url)
            return True
        return False

    # -- internal dispatch --

    def _dispatch(self, event: Event) -> None:
        """Build payload and POST to all registered URLs."""
        if not self.urls:
            return

        builder = _PAYLOAD_BUILDER.get(event.event_type)
        if builder is None:
            logger.debug('No webhook builder for %s — skipping', event.event_type.value)
            return

        payload      = builder(event)
        payload_json = json.dumps(payload).encode('utf-8')

        for url in self.urls:
            self._post_with_retry(url, payload_json)

    def _post_with_retry(self, url: str, payload_bytes: bytes) -> None:
        """POST payload to a single URL with retry on failure."""
        headers = {
            'Content-Type': 'application/json',
            'User-Agent':   'TelemetryObservability/1.0',
        }
        if self.secret:
            sig = hmac.new(
                self.secret.encode('utf-8'),
                payload_bytes,
                hashlib.sha256,
            ).hexdigest()
            headers['X-Telemetry-Signature'] = f'sha256={sig}'

        for attempt in range(self.max_retries + 1):
            try:
                req = Request(url, data=payload_bytes, headers=headers, method='POST')
                with urlopen(req, timeout=self.timeout) as resp:
                    logger.debug(
                        'Webhook delivered to %s (HTTP %s)', url, resp.status
                    )
                return  # success — stop retrying

            except (HTTPError, URLError, OSError) as exc:
                if attempt < self.max_retries:
                    wait = 2 ** attempt          # exponential back-off: 1s, 2s
                    logger.warning(
                        'Webhook to %s failed (attempt %d/%d): %s — retrying in %ds',
                        url, attempt + 1, self.max_retries + 1, exc, wait,
                    )
                    time.sleep(wait)
                else:
                    logger.error(
                        'Webhook to %s permanently failed after %d attempts: %s',
                        url, self.max_retries + 1, exc,
                    )
