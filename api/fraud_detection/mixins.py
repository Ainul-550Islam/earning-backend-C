# =============================================================================
# fraud_detection/mixins.py
#
# ViewSet / View mixins for the Fraud Detection system.
# =============================================================================
from __future__ import annotations

import logging
from typing import Any

from django.core.cache import cache
from django.utils import timezone
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger('fraud_detection')


# ---------------------------------------------------------------------------
# FraudDetectionMixin
# ---------------------------------------------------------------------------

class FraudDetectionMixin:
    """
    Mixin for ViewSets that perform fraud detection checks.

    Provides:
      • get_fraud_context()  — builds a standardised context dict from the request
      • run_fraud_check()    — thin wrapper to call the detector pipeline
      • log_detection()      — structured logging helper
    """

    # Subclass can override to tune which detectors run
    fraud_detectors: list[str] = [
        'VelocityEngine',
        'DeviceFingerprinter',
        'VPNProxyDetector',
        'GeoVelocityDetector',
        'BehavioralBiometricsAnalyzer',
    ]

    def get_fraud_context(self) -> dict[str, Any]:
        """Build context dict from the current request."""
        request = getattr(self, 'request', None)
        if request is None:
            return {}

        return {
            'user_id':    request.user.pk if request.user.is_authenticated else None,
            'ip_address': self._get_client_ip(request),
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            'timestamp':  timezone.now().isoformat(),
            'endpoint':   request.path,
            'method':     request.method,
        }

    def run_fraud_check(self, context: dict | None = None) -> dict[str, Any]:
        """
        Execute the detector pipeline and return a risk summary.
        Falls back to a zero-score result on any error.
        """
        ctx = context or self.get_fraud_context()
        try:
            from api.fraud_detection.services.fraud_detection_service import (
                FraudDetectionService,
            )
            svc = FraudDetectionService()
            return svc.run_check(ctx, detectors=self.fraud_detectors)
        except Exception as exc:
            logger.warning('FraudDetectionMixin.run_fraud_check failed: %s', exc)
            return {
                'fraud_score': 0,
                'risk_level':  'low',
                'detectors':   {},
                'error':       str(exc),
            }

    def log_detection(self, result: dict, extra: dict | None = None) -> None:
        logger.info(
            'fraud_check score=%s risk=%s user=%s ip=%s',
            result.get('fraud_score'),
            result.get('risk_level'),
            self.get_fraud_context().get('user_id'),
            self.get_fraud_context().get('ip_address'),
            extra=extra or {},
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_client_ip(request) -> str:
        xff = request.META.get('HTTP_X_FORWARDED_FOR')
        if xff:
            return xff.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')


# ---------------------------------------------------------------------------
# UserRiskAssessmentMixin
# ---------------------------------------------------------------------------

class UserRiskAssessmentMixin:
    """
    Mixin for ViewSets that expose or update UserRiskProfile data.

    Provides:
      • get_or_create_risk_profile()  — fetch or create the profile for a user
      • recalculate_risk_score()      — trigger an async recalculation task
      • get_cached_risk_score()       — read from cache (or DB) without full recalc
    """

    RISK_CACHE_PREFIX = 'fraud:risk_score:'
    RISK_CACHE_TTL    = 60 * 15   # 15 minutes

    def get_or_create_risk_profile(self, user):
        """Return (profile, created) for *user*."""
        from api.fraud_detection.models import UserRiskProfile
        return UserRiskProfile.objects.get_or_create(user=user)

    def recalculate_risk_score(self, user, async_task: bool = True) -> None:
        """
        Trigger a risk score recalculation for *user*.

        With async_task=True the Celery task is dispatched; otherwise
        the calculation runs synchronously (useful in tests).
        """
        try:
            if async_task:
                from api.fraud_detection.tasks import calculate_user_risk_score
                calculate_user_risk_score.delay(user.pk)
            else:
                from api.fraud_detection.services.fraud_detection_service import (
                    FraudDetectionService,
                )
                FraudDetectionService().recalculate_user_risk(user)
        except Exception as exc:
            logger.warning(
                'UserRiskAssessmentMixin.recalculate_risk_score failed for user=%s: %s',
                user.pk, exc,
            )

    def get_cached_risk_score(self, user) -> int:
        """Return the cached risk score for *user* (0 if not found)."""
        key = f'{self.RISK_CACHE_PREFIX}{user.pk}'
        score = cache.get(key)
        if score is None:
            try:
                profile = user.risk_profile
                score = profile.overall_risk_score
                cache.set(key, score, self.RISK_CACHE_TTL)
            except Exception:
                score = 0
        return score

    def invalidate_risk_cache(self, user) -> None:
        key = f'{self.RISK_CACHE_PREFIX}{user.pk}'
        cache.delete(key)
