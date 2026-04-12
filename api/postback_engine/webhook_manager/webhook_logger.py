"""
webhook_manager/webhook_logger.py
───────────────────────────────────
Logs all outbound webhook attempts for audit and debugging.
"""
from __future__ import annotations
import logging
from django.utils import timezone

logger = logging.getLogger("postback_engine.webhooks")


class WebhookLogger:

    def log_attempt(
        self,
        url: str,
        event: str,
        payload: dict,
        status_code: int = None,
        success: bool = False,
        error: str = "",
        attempt: int = 1,
    ) -> None:
        if success:
            logger.info(
                "WEBHOOK OK: event=%s url=%s attempt=%d status=%s",
                event, url[:80], attempt, status_code,
            )
        else:
            logger.warning(
                "WEBHOOK FAIL: event=%s url=%s attempt=%d status=%s error=%s",
                event, url[:80], attempt, status_code, error[:200],
            )

    def log_delivery_metrics(self, event: str, duration_ms: int, success: bool) -> None:
        logger.debug(
            "WEBHOOK METRICS: event=%s duration=%dms success=%s",
            event, duration_ms, success,
        )


webhook_logger = WebhookLogger()
