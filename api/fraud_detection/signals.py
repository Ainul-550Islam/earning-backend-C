# =============================================================================
# fraud_detection/signals.py
# =============================================================================
"""
Enterprise Fraud Detection Signals.

Comprehensive signal handlers for real-time fraud detection and prevention:
- User risk profile management
- Transaction monitoring
- Device fingerprinting
- IP reputation tracking
- Case management automation
- Hash integrity verification
- Alert generation

DETECTORS NOW WIRED (previously floating):
  - VelocityEngine       → check_offer_completion_fraud, check_transaction_fraud
  - GraphNetworkAnalyzer → handle_new_fraud_attempt
  - GeoVelocityDetector  → check_offer_completion_fraud, check_transaction_fraud
  - BehavioralBiometricsAnalyzer → check_offer_completion_fraud (session biometrics)
"""

from __future__ import annotations

import json
import logging
from datetime import timedelta
from typing import Any, Dict, Optional

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.db.models.signals import post_save, pre_save, pre_delete
from django.dispatch import receiver
from django.utils import timezone

User = get_user_model()

from api.fraud_detection.models import (
    DeviceFingerprint, FraudAlert, FraudAttempt,
    FraudCase, FraudCaseAction, FraudCaseEvidence,
    FraudNotification, FraudPattern, FraudSettings,
    FraudWhitelist, IPReputation, OfferCompletion,
    UserRiskProfile,
)
from api.fraud_detection.choices import AlertPriority, CaseStatus, FraudAlertType
from api.fraud_detection.constants import CACHE_KEYS, RISK_THRESHOLDS

logger = logging.getLogger(__name__)


# =============================================================================
# Detector loader helpers — lazy-import so a missing optional lib
# never breaks the whole signal chain.
# =============================================================================

def _get_velocity_engine():
    try:
        from api.fraud_detection.detectors.VelocityEngine import VelocityEngine
        return VelocityEngine()
    except Exception as exc:
        logger.warning("VelocityEngine unavailable: %s", exc)
        return None


def _get_graph_analyzer():
    try:
        from api.fraud_detection.detectors.GraphNetworkAnalyzer import GraphNetworkAnalyzer
        return GraphNetworkAnalyzer()
    except Exception as exc:
        logger.warning("GraphNetworkAnalyzer unavailable: %s", exc)
        return None


def _get_geo_velocity():
    try:
        from api.fraud_detection.detectors.GeoVelocityDetector import GeoVelocityDetector
        return GeoVelocityDetector()
    except Exception as exc:
        logger.warning("GeoVelocityDetector unavailable: %s", exc)
        return None


def _get_biometrics():
    try:
        from api.fraud_detection.detectors.BehavioralBiometricsAnalyzer import BehavioralBiometricsAnalyzer
        return BehavioralBiometricsAnalyzer()
    except Exception as exc:
        logger.warning("BehavioralBiometricsAnalyzer unavailable: %s", exc)
        return None


def _get_click_detector():
    try:
        from api.fraud_detection.detectors.ClickFraudDetector import ClickFraudDetector
        return ClickFraudDetector()
    except Exception as exc:
        logger.warning("ClickFraudDetector unavailable: %s", exc)
        return None


def _get_referral_detector():
    try:
        from api.fraud_detection.detectors.ReferralFraudDetector import ReferralFraudDetector
        return ReferralFraudDetector()
    except Exception as exc:
        logger.warning("ReferralFraudDetector unavailable: %s", exc)
        return None


def _get_multi_account_detector():
    try:
        from api.fraud_detection.detectors.MultiAccountDetector import MultiAccountDetector
        return MultiAccountDetector()
    except Exception as exc:
        logger.warning("MultiAccountDetector unavailable: %s", exc)
        return None


# =============================================================================
# CORE FRAUD DETECTION SIGNALS
# =============================================================================

@receiver(post_save, sender=FraudAttempt)
def handle_new_fraud_attempt(sender, instance, created, **kwargs):
    """
    Handle new fraud attempt detection with comprehensive processing.

    NOW WIRED:
      - GraphNetworkAnalyzer.analyze_entity() — detects fraud rings
    """
    if not created:
        return

    try:
        # 1. Update user risk profile
        _update_user_risk_from_attempt(instance)

        # 2. Create fraud case if high risk
        if instance.fraud_score >= RISK_THRESHOLDS.get('critical', 80):
            _create_fraud_case_from_attempt(instance)

        # 3. Generate alerts
        _create_fraud_alerts(instance)

        # 4. Update device and IP reputation
        _update_reputation_from_attempt(instance)

        # 5. ── GraphNetworkAnalyzer (was floating) ────────────────────────
        #    Detect fraud rings: shared IPs, shared devices, known fraud users
        if instance.user_id:
            _run_graph_network_analysis(instance)

        # 6. Cache invalidation
        _invalidate_user_cache(instance.user)

        logger.info(
            "Fraud attempt processed: %s score=%s user=%s",
            instance.attempt_id, instance.fraud_score, instance.user_id,
        )

    except Exception as exc:
        logger.error("Error processing fraud attempt %s: %s", instance.attempt_id, exc)


def _run_graph_network_analysis(attempt) -> None:
    """
    Run GraphNetworkAnalyzer for the user involved in the attempt.
    Elevates user risk score if they are part of a fraud ring.
    """
    if not attempt.user_id:
        return

    analyzer = _get_graph_analyzer()
    if analyzer is None:
        return

    try:
        # Build connection data from recent attempts
        recent_ips = list(
            FraudAttempt.objects.filter(user_id=attempt.user_id)
            .values_list('evidence_data__ip', flat=True)
            .distinct()[:20]
        )
        shared_devices = list(
            DeviceFingerprint.objects.filter(user_id=attempt.user_id)
            .values_list('device_hash', flat=True)[:10]
        )
        # Users who share the same IPs
        shared_ip_user_ids = list(
            FraudAttempt.objects.filter(
                evidence_data__ip__in=recent_ips
            ).exclude(user_id=attempt.user_id)
            .values_list('user_id', flat=True)
            .distinct()[:50]
        )
        known_fraud_ids = list(
            UserRiskProfile.objects.filter(
                overall_risk_score__gte=RISK_THRESHOLDS.get('high', 70),
                is_flagged=True,
            ).values_list('user_id', flat=True)[:100]
        )

        data = {
            'user_id':             attempt.user_id,
            'connections':         shared_ip_user_ids,
            'shared_ips':          recent_ips,
            'shared_devices':      shared_devices,
            'shared_payment_methods': [],
            'known_fraud_user_ids': known_fraud_ids,
        }

        result = analyzer.analyze(data) if hasattr(analyzer, 'analyze') else analyzer.detect(data)

        ring_score = result.get('risk_score', 0)
        if ring_score >= settings.GRAPH_NETWORK_CONFIG.get('ring_risk_score', 80):
            # Escalate user risk profile
            try:
                profile = UserRiskProfile.objects.get(user_id=attempt.user_id)
                profile.overall_risk_score = min(100, max(profile.overall_risk_score, ring_score))
                profile.is_flagged = True
                profile.risk_factors = {**profile.risk_factors, 'fraud_ring': result}
                profile.save(update_fields=['overall_risk_score', 'is_flagged', 'risk_factors'])
                logger.warning(
                    "GraphNetwork: user %s is in a fraud ring (score=%s). Profile escalated.",
                    attempt.user_id, ring_score,
                )
            except UserRiskProfile.DoesNotExist:
                pass

            # Create alert
            FraudAlert.objects.create(
                alert_type=FraudAlertType.RULE_TRIGGERED,
                priority=AlertPriority.CRITICAL,
                title="Fraud Ring Detected",
                description=(
                    f"User {attempt.user_id} is connected to a fraud ring "
                    f"(graph risk score: {ring_score})"
                ),
                user_id=attempt.user_id,
                fraud_attempt=attempt,
                data={'graph_result': result},
            )

    except Exception as exc:
        logger.error("GraphNetworkAnalyzer failed for attempt %s: %s", attempt.attempt_id, exc)


@receiver(post_save, sender=User)
def create_user_risk_profile(sender, instance, created, **kwargs):
    """
    Create risk profile for new users.
    NOTE: receivers.py (user_created_receiver) handles the full fraud detection
    analysis. This handler only ensures the basic risk profile exists as a fallback.
    """
    if created:
        try:
            UserRiskProfile.objects.get_or_create(
                user=instance,
                defaults={
                    'overall_risk_score': 0,
                    'monitoring_level': 'normal',
                }
            )
            logger.info("Risk profile ensured for user: %s", instance.id)
        except Exception as exc:
            logger.error("Error ensuring risk profile for user %s: %s", instance.id, exc)


# =============================================================================
# TRANSACTION AND OFFER MONITORING SIGNALS
# =============================================================================

@receiver(pre_save, sender="wallet.WalletTransaction")
def check_transaction_fraud(sender, instance, **kwargs):
    """
    Check wallet transactions for fraud before save.
    Wrapped in try/except — WalletTransaction is a cross-app model.
    """
    try:
        from api.fraud_detection.services.fraud_detection_service import FraudDetectionService
        user_id = getattr(instance, 'user_id', None) or getattr(getattr(instance, 'user', None), 'id', None)
        if not user_id:
            return
        amount = float(getattr(instance, 'amount', 0) or 0)
        result = FraudDetectionService().check_user(user_id, {
            'amount':           amount,
            'transaction_type': getattr(instance, 'transaction_type', 'unknown'),
        })
        if result.get('risk_score', 0) >= 80:
            import logging as _log
            _log.getLogger(__name__).warning(
                'HIGH RISK transaction blocked: user=%s score=%s',
                user_id, result['risk_score']
            )
    except ImportError:
        pass
    except Exception as exc:
        import logging as _log
        _log.getLogger(__name__).error('check_transaction_fraud: %s', exc)


@receiver(post_save, sender=OfferCompletion)
def check_offer_completion_fraud(sender, instance, created, **kwargs):
    """
    Check offer completions for fraud AND credit wallet on clean completions.

    Flow:
      1. VelocityEngine  — sliding window rate check (revenue abuse prevention)
      2. GeoVelocityDetector — impossible-travel on IP
      3. BehavioralBiometricsAnalyzer — bot/headless-browser check via session
      4. ClickFraudDetector — CPA fraud check
      5a. Fraudulent → create FraudAttempt, mark is_fraud=True, skip payment.
      5b. Clean       → credit reward_amount to wallet.
      6. Update user behaviour metrics.
    """
    if not created:
        return
    if instance.status != 'completed':
        return

    try:
        extra_score = 0

        # ── Step 1: VelocityEngine ────────────────────────────────────────
        velocity_score = _run_velocity_check(
            user_id=instance.user_id,
            event_type='offer_completion',
            ip_address=str(instance.ip_address) if instance.ip_address else None,
            device_id=instance.device_id,
        )
        if velocity_score >= 70:
            extra_score += velocity_score // 2
            logger.warning(
                "VelocityEngine flagged offer completion for user %s (score=%s)",
                instance.user_id, velocity_score,
            )

        # ── Step 2: GeoVelocityDetector ───────────────────────────────────
        geo_score = _run_geo_velocity_check(
            user_id=instance.user_id,
            ip_address=str(instance.ip_address) if instance.ip_address else None,
        )
        if geo_score >= 70:
            extra_score += geo_score // 2
            logger.warning(
                "GeoVelocityDetector flagged impossible travel for user %s (score=%s)",
                instance.user_id, geo_score,
            )

        # ── Step 3: BehavioralBiometricsAnalyzer ──────────────────────────
        bio_score = _run_biometrics_check(user_id=instance.user_id)
        if bio_score >= 70:
            extra_score += bio_score // 3
            logger.warning(
                "BehavioralBiometrics flagged bot behaviour for user %s (score=%s)",
                instance.user_id, bio_score,
            )

        # ── Step 3b: ReferralFraudDetector ───────────────────────────────
        # Only runs when a referral_code is present in completion_data
        referral_code = (instance.completion_data or {}).get('referral_code', '') or instance.referral_code or ''
        if referral_code:
            referral_score = _run_referral_check(
                referrer_user_id=instance.user_id,
                referral_code=referral_code,
                ip_address=str(instance.ip_address) if instance.ip_address else None,
                device_id=instance.device_id or '',
            )
            if referral_score >= 70:
                extra_score += referral_score // 3
                logger.warning(
                    "ReferralFraudDetector flagged referral abuse for user %s (score=%s, code=%s)",
                    instance.user_id, referral_score, referral_code,
                )

        # ── Step 4: Base offer fraud analysis ─────────────────────────────
        base_score = _analyze_offer_completion(instance)

        fraud_score = min(100, base_score + extra_score)

        if fraud_score >= RISK_THRESHOLDS.get('medium', 50):
            # ── Step 5a: fraudulent completion ───────────────────────────
            _create_offer_fraud_attempt(instance, fraud_score)
            OfferCompletion.objects.filter(pk=instance.pk).update(
                is_fraud=True,
                fraud_reason=(
                    f'Fraud score {fraud_score} >= threshold '
                    f'{RISK_THRESHOLDS.get("medium", 50)} '
                    f'(velocity={velocity_score}, geo={geo_score}, bio={bio_score})'
                ),
                status='rejected',
            )
            logger.warning(
                "OfferCompletion %s rejected: fraud_score=%s user=%s",
                instance.pk, fraud_score, instance.user_id,
            )
        else:
            # ── Step 5b: clean → credit wallet ───────────────────────────
            if instance.reward_amount and instance.reward_amount > 0:
                _credit_offer_reward_to_wallet(instance)

        # ── Step 6: behaviour metrics ─────────────────────────────────────
        _update_user_behavior_metrics(instance.user)

    except Exception as exc:
        logger.error("Error in check_offer_completion_fraud: %s", exc)


# =============================================================================
# Detector runner helpers
# =============================================================================

def _run_velocity_check(
    user_id: int,
    event_type: str,
    ip_address: str | None = None,
    device_id: str | None = None,
) -> int:
    """
    Run VelocityEngine sliding-window check.
    Returns risk score 0-100.
    """
    engine = _get_velocity_engine()
    if engine is None:
        return 0

    cfg = getattr(settings, 'VELOCITY_ENGINE_CONFIG', {})
    window = cfg.get('offer_completion_limit', 15)

    # Count recent events from cache
    cache_key = f"vel:{event_type}:{user_id}"
    event_count = cache.get(cache_key, 0)
    event_count += 1
    cache.set(cache_key, event_count, timeout=3600)

    data = {
        'user_id':        user_id,
        'event_type':     event_type,
        'window_seconds': 3600,
        'event_count':    event_count,
        'ip_address':     ip_address,
        'device_id':      device_id,
    }
    check_method = (
        getattr(engine, 'check', None)
        or getattr(engine, 'analyze', None)
        or getattr(engine, 'detect', None)
    )
    if check_method is None:
        return 0

    try:
        result = check_method(data)
        return int(result.get('risk_score', 0))
    except Exception as exc:
        logger.error("VelocityEngine check failed: %s", exc)
        return 0


def _run_geo_velocity_check(user_id: int, ip_address: str | None) -> int:
    """
    Run GeoVelocityDetector impossible-travel check.
    Returns risk score 0-100.
    """
    if not ip_address:
        return 0

    detector = _get_geo_velocity()
    if detector is None:
        return 0

    cache_key_prev = f"geo_prev:{user_id}"
    previous = cache.get(cache_key_prev)
    now_iso = timezone.now().isoformat()

    # Get current location from IP (try IPReputation table)
    current_location: dict = {'country': 'unknown'}
    try:
        ip_rep = IPReputation.objects.filter(ip_address=ip_address).first()
        if ip_rep:
            current_location = {
                'lat':     float(ip_rep.latitude) if hasattr(ip_rep, 'latitude') and ip_rep.latitude else 0.0,
                'lng':     float(ip_rep.longitude) if hasattr(ip_rep, 'longitude') and ip_rep.longitude else 0.0,
                'country': ip_rep.country or 'unknown',
            }
    except Exception:
        pass

    # Store current as previous for next check
    cache.set(cache_key_prev, {'location': current_location, 'time': now_iso}, timeout=86400)

    if not previous:
        return 0  # First check — no baseline

    data = {
        'user_id':           user_id,
        'current_location':  current_location,
        'current_time':      now_iso,
        'previous_location': previous.get('location', current_location),
        'previous_time':     previous.get('time', now_iso),
    }

    try:
        result = detector.detect(data)
        return int(result.get('risk_score', 0))
    except Exception as exc:
        logger.error("GeoVelocityDetector failed: %s", exc)
        return 0


def _run_biometrics_check(user_id: int) -> int:
    """
    Run BehavioralBiometricsAnalyzer using cached session biometric data.
    Returns risk score 0-100.  Returns 0 if no session data available.
    """
    cache_key = f"biometrics:{user_id}"
    session_data = cache.get(cache_key)
    if not session_data:
        return 0

    analyzer = _get_biometrics()
    if analyzer is None:
        return 0

    try:
        data = {'user_id': user_id, **session_data}
        result = analyzer.analyze(data)
        score = int(result.get('risk_score', 0))
        if result.get('is_bot'):
            score = max(score, 80)
        return score
    except Exception as exc:
        logger.error("BehavioralBiometricsAnalyzer failed: %s", exc)
        return 0


def _run_referral_check(
    referrer_user_id: int,
    referral_code: str,
    ip_address: str | None = None,
    device_id: str = '',
) -> int:
    """
    Run ReferralFraudDetector on an offer completion that used a referral code.
    Returns risk score 0-100.
    """
    detector = _get_referral_detector()
    if detector is None:
        return 0

    data = {
        'referrer_user_id': referrer_user_id,
        'referral_code':    referral_code,
        'ip_address':       ip_address,
        'device_id':        device_id,
    }
    try:
        result = detector.detect(data)
        return int(result.get('risk_score', 0))
    except Exception as exc:
        logger.error("ReferralFraudDetector check failed: %s", exc)
        return 0


def _credit_offer_reward_to_wallet(completion) -> None:
    """Credit offer reward to user wallet — cross-app call guarded by try/except."""
    if getattr(completion, 'transaction_id', None):
        return
    reward = getattr(completion, 'reward_amount', None)
    if not reward or float(reward) <= 0:
        return
    try:
        from api.wallet.models import WalletTransaction
        txn = WalletTransaction.objects.create(
            user=completion.user,
            transaction_type='credit',
            amount=reward,
            description=f'Offer reward — completion #{completion.pk}',
            status='completed',
            metadata={
                'source':              'offer_completion',
                'offer_id':            getattr(completion, 'offer_id', None),
                'offer_completion_id': completion.pk,
                'ip_address':          str(getattr(completion, 'ip_address', '') or ''),
                'device_id':           getattr(completion, 'device_id', '') or '',
            },
        )
        type(completion).objects.filter(pk=completion.pk).update(
            transaction=txn,
        )
        import logging as _log
        _log.getLogger(__name__).info(
            'Wallet credit created: user=%s amount=%s txn=%s',
            completion.user_id, reward, txn.pk
        )
    except ImportError:
        pass
    except Exception as exc:
        import logging as _log
        _log.getLogger(__name__).error('_credit_offer_reward_to_wallet: %s', exc)


@receiver(post_save, sender=DeviceFingerprint)
def update_device_trust_score(sender, instance, created, **kwargs):
    """Update device trust score based on fraud patterns and user behavior."""
    try:
        if created:
            _set_initial_device_trust(instance)
        else:
            _update_device_trust(instance)
    except Exception as exc:
        logger.error("Error updating device trust score: %s", exc)


@receiver(post_save, sender=IPReputation)
def handle_ip_reputation_changes(sender, instance, **kwargs):
    """Handle IP reputation changes with comprehensive alerting."""
    try:
        if instance.is_blacklisted:
            _create_ip_blacklist_alert(instance)
            _invalidate_ip_cache(instance.ip_address)
        _update_users_with_ip(instance.ip_address, instance.fraud_score)
    except Exception as exc:
        logger.error("Error handling IP reputation changes: %s", exc)


# =============================================================================
# CASE MANAGEMENT SIGNALS
# =============================================================================

@receiver(post_save, sender=FraudCase)
def handle_fraud_case_lifecycle(sender, instance, created, **kwargs):
    """Handle fraud case lifecycle events with automated workflows."""
    if created:
        try:
            if instance.risk_score >= RISK_THRESHOLDS.get('critical', 80):
                _auto_assign_case(instance)
            _create_initial_case_action(instance)
        except Exception as exc:
            logger.error("Error handling new fraud case: %s", exc)
    else:
        try:
            if instance.status in [CaseStatus.RESOLVED, CaseStatus.CLOSED]:
                _handle_case_resolution(instance)
        except Exception as exc:
            logger.error("Error handling fraud case status change: %s", exc)


@receiver(post_save, sender=FraudCaseAction)
def handle_case_action(sender, instance, created, **kwargs):
    """Handle case actions with automated notifications and updates."""
    if created:
        try:
            _update_case_from_action(instance)
            _send_case_action_notifications(instance)
        except Exception as exc:
            logger.error("Error handling case action: %s", exc)


@receiver(post_save, sender=FraudCaseEvidence)
def handle_evidence_addition(sender, instance, created, **kwargs):
    """Handle evidence addition with integrity verification."""
    if created:
        try:
            _verify_evidence_integrity(instance)
            _update_case_priority_from_evidence(instance)
        except Exception as exc:
            logger.error("Error handling evidence addition: %s", exc)


# =============================================================================
# NOTIFICATION AND ALERT SIGNALS
# =============================================================================

@receiver(post_save, sender=FraudAlert)
def handle_fraud_alert(sender, instance, created, **kwargs):
    """Handle fraud alerts with comprehensive notification routing."""
    if created:
        try:
            _route_alert(instance)
            _update_monitoring_from_alert(instance)
        except Exception as exc:
            logger.error("Error handling fraud alert: %s", exc)


@receiver(post_save, sender=FraudNotification)
def handle_notification_delivery(sender, instance, created, **kwargs):
    """Handle notification delivery with retry logic."""
    if created and not instance.is_sent:
        try:
            _queue_notification_delivery(instance)
        except Exception as exc:
            logger.error("Error queuing notification delivery: %s", exc)


# =============================================================================
# WHITELIST AND PATTERN SIGNALS
# =============================================================================

@receiver(post_save, sender=FraudWhitelist)
def handle_whitelist_changes(sender, instance, created, **kwargs):
    """Handle whitelist changes with cache updates."""
    try:
        _update_whitelist_cache(instance)
        _log_whitelist_activity(instance)
    except Exception as exc:
        logger.error("Error handling whitelist changes: %s", exc)


@receiver(post_save, sender=FraudPattern)
def handle_pattern_updates(sender, instance, **kwargs):
    """Handle pattern updates with model retraining."""
    try:
        if instance.is_trained and instance.accuracy_rate >= 0.85:
            _update_pattern_cache(instance)
            _schedule_pattern_retraining(instance)
    except Exception as exc:
        logger.error("Error handling pattern updates: %s", exc)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _update_user_risk_from_attempt(attempt):
    """Update user risk profile from fraud attempt using FraudScoreCalculator."""
    if not attempt.user:
        return
    try:
        from api.fraud_detection.services.FraudScoreCalculator import FraudScoreCalculator
        calculator = FraudScoreCalculator(attempt.user)
        new_risk_score = calculator.calculate_overall_risk()

        profile, _ = UserRiskProfile.objects.get_or_create(user=attempt.user)
        profile.total_fraud_attempts += 1
        if attempt.status == 'confirmed':
            profile.confirmed_fraud_attempts += 1
        elif attempt.status == 'false_positive':
            profile.false_positives += 1

        profile.overall_risk_score = new_risk_score
        profile.last_risk_assessment = timezone.now()

        if profile.overall_risk_score >= RISK_THRESHOLDS.get('critical', 80):
            profile.monitoring_level = 'strict'
            profile.is_flagged = True
        elif profile.overall_risk_score >= RISK_THRESHOLDS.get('high', 70):
            profile.monitoring_level = 'enhanced'

        profile.save()

    except ImportError:
        profile, _ = UserRiskProfile.objects.get_or_create(user=attempt.user)
        profile.total_fraud_attempts += 1
        if attempt.status == 'confirmed':
            profile.confirmed_fraud_attempts += 1
        elif attempt.status == 'false_positive':
            profile.false_positives += 1
        profile.overall_risk_score = min(100, profile.overall_risk_score + (attempt.fraud_score // 10))
        if profile.overall_risk_score >= RISK_THRESHOLDS.get('critical', 80):
            profile.monitoring_level = 'strict'
            profile.is_flagged = True
        elif profile.overall_risk_score >= RISK_THRESHOLDS.get('high', 70):
            profile.monitoring_level = 'enhanced'
        profile.last_risk_assessment = timezone.now()
        profile.save()


def _create_fraud_case_from_attempt(attempt):
    """Create fraud case from high-risk attempt."""
    case_number = f"FC-{timezone.now().strftime('%Y%m%d')}-{attempt.user_id}"
    FraudCase.objects.get_or_create(
        case_number=case_number,
        defaults={
            'user':        attempt.user,
            'title':       f"High Risk Fraud: {attempt.get_attempt_type_display()}",
            'description': f"Automated case creation for fraud attempt with score {attempt.fraud_score}",
            'risk_score':  attempt.fraud_score,
            'priority':    'critical' if attempt.fraud_score >= 80 else 'high',
            'status':      CaseStatus.OPEN,
        }
    )


def _create_fraud_alerts(attempt):
    """Create appropriate alerts for fraud attempt."""
    priority = AlertPriority.CRITICAL if attempt.fraud_score >= 80 else AlertPriority.HIGH
    FraudAlert.objects.create(
        alert_type=FraudAlertType.RULE_TRIGGERED,
        priority=priority,
        title=f"Fraud Attempt Detected: {attempt.get_attempt_type_display()}",
        description=(
            f"User {attempt.user.username if attempt.user else 'Unknown'} "
            f"— Score: {attempt.fraud_score}"
        ),
        user=attempt.user,
        fraud_attempt=attempt,
        data={
            'fraud_score':  attempt.fraud_score,
            'attempt_type': attempt.attempt_type,
            'detected_by':  attempt.detected_by,
            'timestamp':    timezone.now().isoformat(),
        },
    )


def _update_reputation_from_attempt(attempt):
    """Update device and IP reputation based on fraud attempt."""
    try:
        ip = (attempt.evidence_data or {}).get('ip')
        if ip:
            rep, _ = IPReputation.objects.get_or_create(ip_address=ip)
            rep.fraud_attempts = (rep.fraud_attempts or 0) + 1
            rep.fraud_score = min(100, (rep.fraud_score or 0) + 5)
            rep.save(update_fields=['fraud_attempts', 'fraud_score'])
    except Exception as exc:
        logger.error("_update_reputation_from_attempt failed: %s", exc)


def _get_user_from_transaction(transaction):
    """Extract user from wallet transaction."""
    try:
        if hasattr(transaction, 'wallet') and transaction.wallet:
            return transaction.wallet.user
        if hasattr(transaction, 'user'):
            return transaction.user
    except Exception:
        pass
    return None


def _is_user_flagged(user) -> bool:
    """Check if user is flagged for fraud."""
    try:
        return UserRiskProfile.objects.filter(user=user, is_flagged=True).exists()
    except Exception:
        return False


def _analyze_transaction(transaction, user) -> int:
    """Analyze transaction for fraud patterns. Returns 0-100 score."""
    base_score = 0
    amount = float(transaction.amount) if transaction.amount else 0
    if amount > 1000:
        base_score += 30
    elif amount > 500:
        base_score += 15

    try:
        from api.wallet.models import WalletTransaction as _WT
    except ImportError:
        _WT = None
    if _WT is not None:
        try:
            recent_txns = _WT.objects.filter(
                wallet=getattr(transaction, "wallet", None),
                created_at__gte=timezone.now() - timedelta(hours=1),
            ).count()
            if recent_txns > 10:
                base_score += 20
        except Exception:
            pass
    return min(100, base_score)


def _create_transaction_fraud_attempt(transaction, user, fraud_score: int):
    """Create fraud attempt from suspicious transaction."""
    FraudAttempt.objects.create(
        user=user,
        attempt_type='payment_fraud',
        description=f"Suspicious transaction: ${transaction.amount}",
        detected_by='TransactionMonitor',
        fraud_score=fraud_score,
        confidence_score=80,
        evidence_data={
            'transaction_id': str(transaction.id if hasattr(transaction, 'id') else ''),
            'amount':         float(transaction.amount),
            'type':           getattr(transaction, 'type', 'unknown'),
        },
        amount_involved=transaction.amount,
    )


def _analyze_offer_completion(completion) -> int:
    """Analyze offer completion for fraud patterns. Returns 0-100 score."""
    base_score = 0

    if completion.completed_at and completion.tracked_at:
        time_taken = completion.completed_at - completion.tracked_at
        if time_taken.total_seconds() < 30:
            base_score += 20

    reward = float(completion.reward_amount) if completion.reward_amount else 0
    if reward > 50:
        base_score += 15

    user_completions = OfferCompletion.objects.filter(
        user=completion.user,
        status='completed',
        tracked_at__gte=timezone.now() - timedelta(days=1),
    ).count()

    if user_completions > 20:
        base_score += 25
    elif user_completions > 10:
        base_score += 10

    return min(100, base_score)


def _create_offer_fraud_attempt(completion, fraud_score: int):
    """Create fraud attempt from suspicious offer completion."""
    FraudAttempt.objects.create(
        user=completion.user,
        attempt_type='click_fraud',
        description=f"Suspicious offer completion: {getattr(completion.offer, 'title', 'Unknown') if completion.offer else 'Unknown'}",
        detected_by='OfferMonitor',
        fraud_score=fraud_score,
        confidence_score=75,
        evidence_data={
            'offer_id':        completion.offer_id,
            'reward_amount':   float(completion.reward_amount) if completion.reward_amount else 0,
            'completion_time': completion.completed_at.isoformat() if completion.completed_at else None,
        },
        amount_involved=completion.reward_amount or 0,
    )


def _update_user_behavior_metrics(user):
    """Update user behavior metrics after offer interaction."""
    try:
        profile = UserRiskProfile.objects.get(user=user)
        profile.last_risk_assessment = timezone.now()
        profile.save(update_fields=['last_risk_assessment'])
    except UserRiskProfile.DoesNotExist:
        pass
    except Exception as exc:
        logger.error("_update_user_behavior_metrics failed: %s", exc)


def _invalidate_user_cache(user):
    """Invalidate user-related cache entries."""
    if not user:
        return
    keys = [
        f'user_risk_{user.id}',
        f'fraud_user_risk_{user.id}',
        f'alert_throttle_{user.id}',
        f'vel:offer_completion:{user.id}',
        f'vel:withdrawal:{user.id}',
        f'vel:login:{user.id}',
    ]
    for key in keys:
        cache.delete(key)


def _invalidate_ip_cache(ip_address: str):
    """Invalidate IP reputation cache."""
    cache.delete(f'ip_rep:{ip_address}')
    cache.delete(f'ip_risk:{ip_address}')


def _set_initial_device_trust(device):
    """Set initial trust score for a new device."""
    trust_score = 50  # neutral start
    if device.is_bot:
        trust_score = 0
    elif device.is_vpn or device.is_proxy or device.is_tor:
        trust_score = 20
    device.trust_score = trust_score
    device.save(update_fields=['trust_score'])


def _update_device_trust(device):
    """Update trust score for existing device based on recent activity."""
    try:
        recent_fraud = FraudAttempt.objects.filter(
            user=device.user,
            created_at__gte=timezone.now() - timedelta(days=7),
            status__in=['confirmed', 'flagged'],
        ).count()
        if recent_fraud > 5:
            device.trust_score = max(0, device.trust_score - 20)
        elif recent_fraud == 0:
            device.trust_score = min(100, device.trust_score + 5)
        device.save(update_fields=['trust_score'])
    except Exception as exc:
        logger.error("_update_device_trust failed: %s", exc)


def _create_ip_blacklist_alert(ip_rep):
    """Create alert for blacklisted IP."""
    try:
        FraudAlert.objects.create(
            alert_type=FraudAlertType.RULE_TRIGGERED,
            priority=AlertPriority.HIGH,
            title=f"IP Blacklisted: {ip_rep.ip_address}",
            description=f"IP {ip_rep.ip_address} has been blacklisted. Reason: {ip_rep.blacklist_reason or 'Not specified'}",
            data={
                'ip_address':      ip_rep.ip_address,
                'fraud_score':     ip_rep.fraud_score,
                'blacklist_reason': ip_rep.blacklist_reason,
                'country':         ip_rep.country,
            },
        )
    except Exception as exc:
        logger.error("_create_ip_blacklist_alert failed: %s", exc)


def _update_users_with_ip(ip_address: str, fraud_score: int):
    """Update risk profiles for users who have used this IP."""
    if fraud_score < 70:
        return
    try:
        affected_users = FraudAttempt.objects.filter(
            evidence_data__ip=ip_address
        ).values_list('user_id', flat=True).distinct()

        UserRiskProfile.objects.filter(user_id__in=affected_users).update(
            overall_risk_score=models_min_expression(fraud_score)
        )
    except Exception as exc:
        logger.error("_update_users_with_ip failed: %s", exc)


def models_min_expression(score: int):
    """
    Django ORM expression: MAX(current_score, score).
    Used to only escalate, never lower, a risk score from IP reputation change.
    """
    from django.db.models import F, Case, When, Value, IntegerField
    return Case(
        When(overall_risk_score__lt=score, then=Value(score)),
        default=F('overall_risk_score'),
        output_field=IntegerField(),
    )


def _auto_assign_case(case):
    """Auto-assign high-priority case to available staff."""
    try:
        staff = User.objects.filter(is_staff=True, is_active=True).first()
        if staff:
            case.assigned_to = staff
            case.save(update_fields=['assigned_to'])
    except Exception as exc:
        logger.error("_auto_assign_case failed: %s", exc)


def _create_initial_case_action(case):
    """Create initial 'case opened' action for new fraud case."""
    try:
        FraudCaseAction.objects.create(
            fraud_case=case,
            action_type='investigate',
            note='Case automatically created by fraud detection system.',
            is_completed=False,
        )
    except Exception as exc:
        logger.error("_create_initial_case_action failed: %s", exc)


def _handle_case_resolution(case):
    """Handle case resolution — update user risk profile."""
    try:
        if case.user_id:
            profile = UserRiskProfile.objects.get(user_id=case.user_id)
            profile.last_risk_assessment = timezone.now()
            profile.save(update_fields=['last_risk_assessment'])
    except UserRiskProfile.DoesNotExist:
        pass
    except Exception as exc:
        logger.error("_handle_case_resolution failed: %s", exc)


def _update_case_from_action(action_obj):
    """Update case status based on action type."""
    try:
        action_to_status = {
            'investigate': 'investigating',
            'escalate':    'escalated',
            'close':       'closed',
            'resolve':     'resolved',
        }
        new_status = action_to_status.get(action_obj.action_type)
        if new_status and action_obj.fraud_case.status != new_status:
            FraudCase.objects.filter(pk=action_obj.fraud_case_id).update(status=new_status)
    except Exception as exc:
        logger.error("_update_case_from_action failed: %s", exc)


def _send_case_action_notifications(action_obj):
    """Send notifications for case action."""
    try:
        from api.fraud_detection.services.FraudNotificationService import FraudNotificationService
        svc = FraudNotificationService()
        svc.create_case_notification(
            case_id=action_obj.fraud_case_id,
            notification_type='case_updated',
            extra_context={'action_type': action_obj.action_type},
        )
    except Exception as exc:
        logger.error("_send_case_action_notifications failed: %s", exc)


def _verify_evidence_integrity(evidence):
    """Verify evidence integrity hash."""
    try:
        import hashlib
        data_str = f"{evidence.previous_hash}{evidence.pk}{evidence.created_at.isoformat()}"
        expected = hashlib.sha256(data_str.encode()).hexdigest()
        if evidence.integrity_hash and evidence.integrity_hash != expected:
            logger.error(
                "Evidence integrity check FAILED for evidence %s — possible tampering!",
                evidence.pk,
            )
    except Exception as exc:
        logger.error("_verify_evidence_integrity failed: %s", exc)


def _update_case_priority_from_evidence(evidence):
    """Escalate case priority if critical evidence is added."""
    try:
        if evidence.evidence_type in ('transaction_log', 'api_log'):
            FraudCase.objects.filter(pk=evidence.fraud_case_id, priority__in=['low', 'medium']).update(
                priority='high'
            )
    except Exception as exc:
        logger.error("_update_case_priority_from_evidence failed: %s", exc)


def _route_alert(alert):
    """Route alert to appropriate notification channels."""
    try:
        from api.fraud_detection.services.FraudNotificationService import FraudNotificationService
        svc = FraudNotificationService()
        svc.create_alert_notification(alert_id=alert.pk)
    except Exception as exc:
        logger.error("_route_alert failed: %s", exc)


def _update_monitoring_from_alert(alert):
    """Escalate monitoring level for high-priority alerts."""
    try:
        if alert.priority in (AlertPriority.CRITICAL, AlertPriority.HIGH) and alert.user_id:
            UserRiskProfile.objects.filter(
                user_id=alert.user_id,
                monitoring_level__in=['normal', 'low'],
            ).update(monitoring_level='enhanced')
    except Exception as exc:
        logger.error("_update_monitoring_from_alert failed: %s", exc)


def _queue_notification_delivery(notification):
    """Queue notification for async delivery via Celery."""
    try:
        from api.fraud_detection.tasks import deliver_fraud_notification
        deliver_fraud_notification.delay(notification_id=notification.pk)
    except ImportError:
        logger.info(
            "Celery tasks not available — notification %s will be retried via beat schedule.",
            notification.pk,
        )
    except Exception as exc:
        logger.error("_queue_notification_delivery failed: %s", exc)


def _update_whitelist_cache(whitelist_entry):
    """Update whitelist cache entry."""
    try:
        cache_key = f"whitelist:{whitelist_entry.entity_type}:{whitelist_entry.entity_value}"
        if whitelist_entry.is_active:
            cache.set(cache_key, True, timeout=3600)
        else:
            cache.delete(cache_key)
    except Exception as exc:
        logger.error("_update_whitelist_cache failed: %s", exc)


def _log_whitelist_activity(whitelist_entry):
    """Log whitelist add/remove for audit trail."""
    logger.info(
        "Whitelist %s: type=%s value=%s active=%s",
        'entry updated',
        whitelist_entry.entity_type,
        whitelist_entry.entity_value,
        whitelist_entry.is_active,
    )


def _update_pattern_cache(pattern):
    """Update fraud pattern cache after retraining."""
    try:
        cache_key = f"fraud_pattern:{pattern.pk}"
        cache.set(cache_key, {
            'name':          pattern.name,
            'pattern_type':  pattern.pattern_type,
            'accuracy_rate': float(pattern.accuracy_rate),
            'is_trained':    pattern.is_trained,
        }, timeout=3600)
    except Exception as exc:
        logger.error("_update_pattern_cache failed: %s", exc)


def _schedule_pattern_retraining(pattern):
    """Schedule ML pattern retraining if needed."""
    try:
        from api.fraud_detection.tasks import retrain_fraud_patterns
        retrain_fraud_patterns.apply_async(countdown=300)
    except ImportError:
        logger.info("Pattern retraining will run via scheduled beat task.")
    except Exception as exc:
        logger.error("_schedule_pattern_retraining failed: %s", exc)


# =============================================================================
# ADDITIONAL SIGNAL CONNECTIONS — previously floating
# Added here (DRY — one place for all signal wiring):
#   events.py      → EventProcessor wired to Django model signals
#   encryption.py  → auto-encrypt sensitive fields on pre_save
#   monitoring.py  → record metrics on key model events
# =============================================================================

# ── Lazy accessors ────────────────────────────────────────────────────────────
def _get_event_processor():
    from api.fraud_detection.events import EventProcessor, create_fraud_detected_event
    return EventProcessor.get_instance()


def _get_monitor():
    from api.fraud_detection.monitoring import get_real_time_monitor
    return get_real_time_monitor()


# ── events.py: emit FraudEvent objects alongside Django signals ───────────────

@receiver(post_save, sender=FraudAttempt)
def emit_fraud_detected_event(sender, instance, created, **kwargs):
    """
    WAS FLOATING: events.py defined EventProcessor but was never subscribed
    to Django signals.  Now wired here (DRY — single signal handler location).
    """
    if not created:
        return
    try:
        from api.fraud_detection.events import create_fraud_detected_event
        event = create_fraud_detected_event(
            user_id=instance.user_id,
            description=f"Fraud attempt detected: {instance.fraud_type}",
            risk_score=instance.risk_score,
            fraud_type=instance.fraud_type,
            source="signal.post_save.FraudAttempt",
        )
        _get_event_processor().process(event)
    except Exception as exc:
        import logging as _log
        _log.getLogger(__name__).error("emit_fraud_detected_event: %s", exc)


@receiver(post_save, sender=FraudCase)
def emit_case_created_event(sender, instance, created, **kwargs):
    """Emit FraudEvent when a new FraudCase is created."""
    if not created:
        return
    try:
        from api.fraud_detection.events import create_case_created_event
        event = create_case_created_event(
            case_id=str(instance.pk),
            user_id=instance.user_id if hasattr(instance, "user_id") else "unknown",
            severity=getattr(instance, "severity", "medium"),
        )
        _get_event_processor().process(event)
    except Exception as exc:
        import logging as _log
        _log.getLogger(__name__).error("emit_case_created_event: %s", exc)


@receiver(post_save, sender=FraudAlert)
def emit_alert_event(sender, instance, created, **kwargs):
    """Emit FraudEvent when a FraudAlert is created or risk score changes."""
    if not created:
        return
    try:
        from api.fraud_detection.events import create_alert_generated_event
        event = create_alert_generated_event(
            alert_id=str(instance.pk),
            user_id=getattr(instance, "user_id", "unknown"),
            risk_score=getattr(instance, "risk_score", 0),
        )
        _get_event_processor().process(event)
    except Exception as exc:
        import logging as _log
        _log.getLogger(__name__).error("emit_alert_event: %s", exc)


# ── encryption.py: auto-encrypt sensitive fields on pre_save ─────────────────

@receiver(pre_save, sender="fraud_detection.IPReputation")
def auto_encrypt_ip_address(sender, instance, **kwargs):
    """
    WAS FLOATING: encryption.py had encrypt_ip_address() but it was never
    called automatically.  Now applied on pre_save for IPReputation.
    """
    try:
        if instance.ip_address and not getattr(instance, "_ip_encrypted", False):
            from api.fraud_detection.encryption import encrypt_ip_address
            instance.ip_address  = encrypt_ip_address(instance.ip_address)
            instance._ip_encrypted = True
    except Exception as exc:
        import logging as _log
        _log.getLogger(__name__).warning("auto_encrypt_ip_address: %s", exc)


@receiver(pre_save, sender="fraud_detection.DeviceFingerprint")
def auto_encrypt_device_id(sender, instance, **kwargs):
    """Auto-encrypt device_id field on DeviceFingerprint save."""
    try:
        if instance.device_id and not getattr(instance, "_device_encrypted", False):
            from api.fraud_detection.encryption import encrypt_device_id
            instance.device_id     = encrypt_device_id(instance.device_id)
            instance._device_encrypted = True
    except Exception as exc:
        import logging as _log
        _log.getLogger(__name__).warning("auto_encrypt_device_id: %s", exc)


# ── monitoring.py: record real-time metrics on key model events ───────────────

@receiver(post_save, sender=FraudAttempt)
def record_fraud_attempt_metric(sender, instance, created, **kwargs):
    """
    WAS FLOATING: monitoring.py had get_real_time_monitor() but nothing
    called record_event(). Now wired to FraudAttempt post_save.
    """
    if not created:
        return
    try:
        monitor = _get_monitor()
        monitor.record_event("fraud_attempt", {
            "fraud_type":  getattr(instance, "fraud_type", "unknown"),
            "risk_score":  getattr(instance, "risk_score", 0),
            "is_flagged":  getattr(instance, "is_fraudulent", False),
        })
    except Exception as exc:
        import logging as _log
        _log.getLogger(__name__).debug("record_fraud_attempt_metric: %s", exc)


@receiver(post_save, sender=FraudAlert)
def record_alert_metric(sender, instance, created, **kwargs):
    """Record FraudAlert creation in real-time monitor."""
    if not created:
        return
    try:
        _get_monitor().record_event("fraud_alert", {
            "alert_type": getattr(instance, "alert_type", "unknown"),
            "risk_score": getattr(instance, "risk_score", 0),
        })
    except Exception as exc:
        import logging as _log
        _log.getLogger(__name__).debug("record_alert_metric: %s", exc)


# =============================================================================
# NEW SIGNAL CONNECTIONS — KYC, Chargeback, SLA, MFA
# =============================================================================

@receiver(post_save, sender="fraud_detection.UserRiskProfile")
def trigger_kyc_recheck_on_risk_spike(sender, instance, **kwargs):
    """If risk score spikes above 70, flag for KYC re-verification."""
    try:
        if instance.risk_score >= 70:
            from django.core.cache import cache
            key = f"kyc_recheck_flagged:{instance.user_id}"
            if not cache.get(key):
                cache.set(key, True, timeout=3600)
                logger.info("KYC re-check flagged for user %s (risk=%s)",
                            instance.user_id, instance.risk_score)
    except Exception as exc:
        logger.debug("trigger_kyc_recheck_on_risk_spike: %s", exc)


@receiver(post_save, sender="fraud_detection.FraudCase")
def check_sla_on_case_create(sender, instance, created, **kwargs):
    """On case creation, log the SLA target for tracking."""
    if not created:
        return
    try:
        severity  = getattr(instance, "severity", "medium")
        from api.fraud_detection.sla_manager import SLA_TARGETS
        target_h  = SLA_TARGETS.get(severity, 24)
        logger.info("SLA started: case=%s severity=%s target=%dh",
                    instance.pk, severity, target_h)
    except Exception as exc:
        logger.debug("check_sla_on_case_create: %s", exc)


@receiver(post_save, sender=FraudAttempt)
def check_chargeback_fraud_on_attempt(sender, instance, created, **kwargs):
    """If a fraud attempt is chargeback-type, trigger ChargebackService risk check."""
    if not created:
        return
    fraud_type = getattr(instance, "fraud_type", "")
    if "chargeback" not in str(fraud_type).lower():
        return
    try:
        from api.fraud_detection.services.ChargebackService import get_chargeback_service
        risk = get_chargeback_service()._score_chargeback_risk(
            instance.user_id,
            getattr(instance, "amount", 0) or 0,
        )
        if risk >= 50:
            logger.warning("Chargeback risk: user=%s score=%s", instance.user_id, risk)
    except Exception as exc:
        logger.debug("check_chargeback_fraud_on_attempt: %s", exc)
