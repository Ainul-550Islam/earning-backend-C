# services/translation/WebhookService.py
"""Webhook triggers — notify external systems on translation events."""
import json
import hashlib
import hmac
import logging
import time
import urllib.request
from typing import Dict, List
from django.conf import settings
logger = logging.getLogger(__name__)


class WebhookService:
    """Send webhooks on translation events — Slack, GitHub, JIRA, custom."""

    def trigger(self, event_type: str, payload: Dict, webhook_urls: List[str] = None) -> Dict:
        """Webhook trigger করে।"""
        urls = webhook_urls or getattr(settings, "LOCALIZATION_WEBHOOKS", {}).get(event_type, [])
        if not urls:
            return {"sent": 0, "skipped": True}

        body = json.dumps({"event": event_type, "timestamp": time.time(), "data": payload}).encode()
        secret = getattr(settings, "LOCALIZATION_WEBHOOK_SECRET", "")
        signature = ""
        if secret:
            signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

        sent = failed = 0
        for url in urls:
            try:
                req = urllib.request.Request(
                    url, data=body, method="POST",
                    headers={
                        "Content-Type": "application/json",
                        "X-Localization-Event": event_type,
                        "X-Signature-SHA256": signature,
                    }
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    if resp.status < 400:
                        sent += 1
                    else:
                        failed += 1
            except Exception as e:
                logger.error(f"Webhook to {url} failed: {e}")
                failed += 1

        return {"sent": sent, "failed": failed, "event": event_type}

    def on_translation_approved(self, key: str, language: str, value: str):
        return self.trigger("translation.approved", {"key": key, "language": language, "value": value[:100]})

    def on_coverage_milestone(self, language: str, coverage_percent: float):
        return self.trigger("coverage.milestone", {"language": language, "coverage": coverage_percent})

    def on_missing_translation_spike(self, count: int, language: str):
        return self.trigger("missing.spike", {"count": count, "language": language})

    def on_pack_published(self, language: str, namespace: str, version: str):
        return self.trigger("pack.published", {"language": language, "namespace": namespace, "version": version})
