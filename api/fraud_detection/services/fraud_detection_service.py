# =============================================================================
# fraud_detection/services/fraud_detection_service.py
#
# Core orchestration service.  ViewSets and APIViews call this; it delegates
# to individual detectors and the ML scorer, then persists the result.
# =============================================================================
from __future__ import annotations

import logging
from typing import Any

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone

from api.fraud_detection.constants import (
    CACHE_KEYS,
    CACHE_TTL,
    AUTO_BAN_THRESHOLD,
    AUTO_FLAG_THRESHOLD,
    RISK_THRESHOLDS,
    SCORING_WEIGHTS,
)

User = get_user_model()
logger = logging.getLogger('fraud_detection')


class FraudDetectionService:
    """
    Orchestrates the full fraud-detection pipeline:
      1. Load applicable detectors
      2. Run each detector in sequence
      3. Aggregate scores with SCORING_WEIGHTS
      4. Persist a FraudAttempt when score ≥ threshold
      5. Trigger auto-ban / auto-flag when score is critical
      6. Cache the result
    """

    DEFAULT_DETECTORS = [
        'VelocityEngine',
        'DeviceFingerprinter',
        'VPNProxyDetector',
        'GeoVelocityDetector',
        'BehavioralBiometricsAnalyzer',
        'PatternAnalyzer',
        'ClickFraudDetector',
    ]

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def run_check(
        self,
        context: dict[str, Any],
        detectors: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Run the fraud detection pipeline for *context*.

        Parameters
        ----------
        context : dict
            Must contain at least: user_id, ip_address, user_agent.
        detectors : list[str] | None
            Names of detector classes to run.  Defaults to DEFAULT_DETECTORS.

        Returns
        -------
        dict with keys:
            fraud_score, risk_level, risk_factors,
            detector_results, action_taken, cache_hit
        """
        # --- Cache check -------------------------------------------------
        cache_key = self._build_cache_key(context)
        cached    = cache.get(cache_key)
        if cached:
            cached['cache_hit'] = True
            return cached

        # --- Run detectors -----------------------------------------------
        detector_results: dict[str, dict] = {}
        for name in (detectors or self.DEFAULT_DETECTORS):
            try:
                detector = self._load_detector(name)
                if detector:
                    result = detector.analyze(context)
                    detector_results[name] = result
            except Exception as exc:
                logger.warning('Detector %s failed: %s', name, exc)
                detector_results[name] = {'score': 0, 'error': str(exc)}

        # --- Aggregate ---------------------------------------------------
        fraud_score = self._aggregate_score(detector_results)
        risk_level  = self._score_to_risk_level(fraud_score)
        risk_factors = self._extract_risk_factors(detector_results)

        # --- Actions -----------------------------------------------------
        action_taken = self._take_action(context, fraud_score)

        result = {
            'fraud_score':      fraud_score,
            'risk_level':       risk_level,
            'risk_factors':     risk_factors,
            'detector_results': detector_results,
            'action_taken':     action_taken,
            'cache_hit':        False,
            'timestamp':        timezone.now().isoformat(),
        }

        # --- Cache & return ----------------------------------------------
        cache.set(cache_key, result, CACHE_TTL['detection_result'])
        return result

    def recalculate_user_risk(self, user) -> int:
        """
        Synchronously recalculate and persist the overall risk score for *user*.
        Returns the new overall_risk_score.
        """
        from api.fraud_detection.models import FraudAttempt, UserRiskProfile

        qs = FraudAttempt.objects.filter(user=user)
        total    = qs.count()
        confirmed = qs.filter(status='confirmed').count()

        # Weighted formula
        base_score = 0
        if total:
            ratio      = confirmed / total
            base_score = int(ratio * 100)

        # Boost for recent attempts
        recent = qs.filter(created_at__gte=timezone.now() - timezone.timedelta(days=7)).count()
        boost  = min(recent * 5, 30)
        score  = min(base_score + boost, 100)

        profile, _ = UserRiskProfile.objects.get_or_create(user=user)
        profile.overall_risk_score     = score
        profile.total_fraud_attempts   = total
        profile.confirmed_fraud_attempts = confirmed
        profile.last_risk_assessment   = timezone.now()
        profile.save(update_fields=[
            'overall_risk_score', 'total_fraud_attempts',
            'confirmed_fraud_attempts', 'last_risk_assessment',
        ])

        # Update cache
        cache_key = CACHE_KEYS['user_risk_score'].format(user_id=user.pk)
        cache.set(cache_key, score, CACHE_TTL['user_risk_score'])

        return score

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _load_detector(name: str):
        """
        Dynamically import a detector by class name.
        Returns None (with a warning) if the class cannot be found.
        """
        module_path = f'api.fraud_detection.detectors.{name}'
        try:
            import importlib
            mod = importlib.import_module(module_path)
            cls = getattr(mod, name)
            return cls()
        except (ImportError, AttributeError) as exc:
            logger.debug('Could not load detector %s: %s', name, exc)
            return None

    @staticmethod
    def _aggregate_score(detector_results: dict) -> int:
        """
        Weighted average of per-detector scores, capped at 100.
        Unknown detectors are given equal weight 1.0.
        """
        total_weight = 0.0
        total_score  = 0.0

        for name, result in detector_results.items():
            if 'error' in result:
                continue
            score  = float(result.get('score', 0))
            weight = SCORING_WEIGHTS.get(name.lower(), 1.0)
            total_score  += score * weight
            total_weight += weight

        if total_weight == 0:
            return 0
        raw = total_score / total_weight
        return min(int(raw), 100)

    @staticmethod
    def _score_to_risk_level(score: int) -> str:
        for level, (lo, hi) in RISK_THRESHOLDS.items():
            if lo <= score <= hi:
                return level
        return 'low'

    @staticmethod
    def _extract_risk_factors(detector_results: dict) -> list[dict]:
        factors = []
        for name, result in detector_results.items():
            if 'error' in result or not result.get('score', 0):
                continue
            factors.append({
                'detector': name,
                'score':    result.get('score', 0),
                'details':  result.get('details', {}),
            })
        return sorted(factors, key=lambda f: f['score'], reverse=True)

    def _take_action(self, context: dict, fraud_score: int) -> str:
        """Persist attempt + auto-ban/flag as required. Returns action string."""
        user_id = context.get('user_id')
        if not user_id:
            return 'no_action'

        # Always persist high-risk signals
        if fraud_score >= AUTO_FLAG_THRESHOLD:
            self._persist_fraud_attempt(context, fraud_score)

        if fraud_score >= AUTO_BAN_THRESHOLD:
            self._auto_ban(user_id)
            return 'auto_banned'

        if fraud_score >= AUTO_FLAG_THRESHOLD:
            self._auto_flag(user_id, fraud_score)
            return 'auto_flagged'

        return 'no_action'

    @staticmethod
    def _persist_fraud_attempt(context: dict, fraud_score: int) -> None:
        try:
            from api.fraud_detection.models import FraudAttempt
            user = User.objects.get(pk=context['user_id'])
            FraudAttempt.objects.create(
                user           = user,
                attempt_type   = context.get('attempt_type', 'other'),
                fraud_score    = fraud_score,
                confidence_score = fraud_score,
                evidence_data  = context,
                detected_by    = 'system',
            )
        except Exception as exc:
            logger.error('Failed to persist FraudAttempt: %s', exc)

    @staticmethod
    def _auto_flag(user_id: int, score: int) -> None:
        try:
            from api.fraud_detection.models import UserRiskProfile
            profile, _ = UserRiskProfile.objects.get_or_create(user_id=user_id)
            if not profile.is_flagged:
                profile.is_flagged           = True
                profile.overall_risk_score   = max(profile.overall_risk_score, score)
                profile.save(update_fields=['is_flagged', 'overall_risk_score'])
        except Exception as exc:
            logger.error('_auto_flag failed for user %s: %s', user_id, exc)

    @staticmethod
    def _auto_ban(user_id: int) -> None:
        try:
            User.objects.filter(pk=user_id).update(is_active=False)
            from api.fraud_detection.models import UserRiskProfile
            profile, _ = UserRiskProfile.objects.get_or_create(user_id=user_id)
            profile.is_flagged       = True
            profile.is_restricted    = True
            profile.overall_risk_score = 100
            profile.restrictions     = {
                'auto_banned': True,
                'banned_at':   timezone.now().isoformat(),
                'reason':      'Auto-ban: fraud score ≥ 90',
            }
            profile.save(update_fields=['is_flagged', 'is_restricted', 'overall_risk_score', 'restrictions'])
        except Exception as exc:
            logger.error('_auto_ban failed for user %s: %s', user_id, exc)

    @staticmethod
    def _build_cache_key(context: dict) -> str:
        import hashlib
        parts = '|'.join(str(context.get(k, '')) for k in ('user_id', 'ip_address', 'endpoint'))
        short = hashlib.md5(parts.encode()).hexdigest()[:16]
        return CACHE_KEYS['detection_result'].format(cache_key=short)
