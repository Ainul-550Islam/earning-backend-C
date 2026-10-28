"""
api/gamification/integrations/analytics_adapter.py

Gamification ↔ Analytics adapter।

সব gamification event → api.analytics-এ track করে।
No wire-up needed — adapter.track_event() থেকে automatically call হয়।
"""
from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Standard event name prefix
PREFIX = "gamification"


class AnalyticsGamificationAdapter:
    """Gamification events → api.analytics।"""

    def track(
        self,
        event_name: str,
        user: Optional[Any] = None,
        properties: Optional[dict] = None,
    ) -> None:
        """
        Event api.analytics-এ পাঠাও।

        Tries (in order):
        1. api.analytics.services.AnalyticsService
        2. api.analytics.tasks (async Celery)
        3. Structured log (fallback)

        Args:
            event_name:  e.g. "wallet_credited", "achievement_awarded"
            user:        Django User instance (optional)
            properties:  dict of event properties
        """
        full_event = f"{PREFIX}.{event_name}" if not event_name.startswith(PREFIX) else event_name
        user_id    = str(getattr(user, "pk", "anonymous")) if user else "anonymous"
        props      = {
            "user_id": user_id,
            **(properties or {}),
        }

        # Try synchronous service
        if self._track_via_service(full_event, props):
            return

        # Try async Celery task
        if self._track_via_task(full_event, user_id, props):
            return

        # Structured log fallback — always succeeds
        logger.info(
            "[AnalyticsAdapter] event=%s user=%s props=%r",
            full_event, user_id, props
        )

    # ── Private ────────────────────────────────────────────────────────────────

    def _track_via_service(self, event: str, props: dict) -> bool:
        try:
            from api.analytics.services import AnalyticsService
            AnalyticsService().track(event, props)
            return True
        except ImportError:
            return False
        except Exception as exc:
            logger.debug("[AnalyticsAdapter] service track failed: %s", exc)
            return False

    def _track_via_task(self, event: str, user_id: str, props: dict) -> bool:
        try:
            from api.analytics.tasks import track_event_task
            track_event_task.delay(event_name=event, user_id=user_id, properties=props)
            return True
        except ImportError:
            return False
        except Exception as exc:
            logger.debug("[AnalyticsAdapter] task track failed: %s", exc)
            return False
