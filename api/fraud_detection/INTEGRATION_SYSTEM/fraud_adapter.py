# =============================================================================
# fraud_detection/INTEGRATION_SYSTEM/fraud_adapter.py
# =============================================================================
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger('fraud_detection.adapter')


class FraudDetectionAdapter:
    """
    Bridge between external integrations (payment processors, identity providers,
    threat intelligence feeds) and the internal fraud detection pipeline.

    External systems call:
        adapter.check_user(user_id, context)
        adapter.report_fraud(event_type, data)
        adapter.get_risk_score(user_id)

    Internal views call:
        adapter.notify_external(event, payload)
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}

    # ── Inbound ─────────────────────────────────────────────────────────────

    def check_user(self, user_id: int, context: Dict[str, Any]) -> Dict[str, Any]:
        """Trigger a fraud check on behalf of an external caller."""
        try:
            from api.fraud_detection.services.fraud_detection_service import (
                FraudDetectionService,
            )
            ctx = {'user_id': user_id, **context}
            return FraudDetectionService().run_check(ctx)
        except Exception as exc:
            logger.error('FraudDetectionAdapter.check_user failed: %s', exc)
            return {'fraud_score': 0, 'risk_level': 'unknown', 'error': str(exc)}

    def report_fraud(self, event_type: str, data: Dict[str, Any]) -> bool:
        """Ingest a fraud report from an external system."""
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.event_bus import (
                get_event_bus, Event, EventType,
            )
            bus    = get_event_bus()
            ev_map = {
                'chargeback':    EventType.FRAUD_DETECTED,
                'account_takeover': EventType.FRAUD_DETECTED,
                'high_risk':     EventType.HIGH_RISK_SCORE,
            }
            ev_type = ev_map.get(event_type, EventType.FRAUD_DETECTED)
            bus.publish(Event(event_type=ev_type, payload=data, source='external'))
            return True
        except Exception as exc:
            logger.error('FraudDetectionAdapter.report_fraud failed: %s', exc)
            return False

    def get_risk_score(self, user_id: int) -> int:
        """Return the cached risk score for a user."""
        try:
            from django.core.cache import cache
            from api.fraud_detection.constants import CACHE_KEYS
            key   = CACHE_KEYS['user_risk_score'].format(user_id=user_id)
            score = cache.get(key)
            if score is not None:
                return int(score)
            from api.fraud_detection.models import UserRiskProfile
            profile = UserRiskProfile.objects.filter(user_id=user_id).first()
            return profile.overall_risk_score if profile else 0
        except Exception as exc:
            logger.error('FraudDetectionAdapter.get_risk_score failed: %s', exc)
            return 0

    # ── Outbound ─────────────────────────────────────────────────────────────

    def notify_external(self, event: str, payload: Dict[str, Any]) -> bool:
        """Send fraud event to external webhooks / integrations."""
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.message_queue import publish_message
            publish_message('external_notifications', {'event': event, 'payload': payload})
            return True
        except Exception as exc:
            logger.error('FraudDetectionAdapter.notify_external failed: %s', exc)
            return False
