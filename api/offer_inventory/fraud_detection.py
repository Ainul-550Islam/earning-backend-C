# api/offer_inventory/fraud_detection.py
"""
Fraud Detection Facade.
Central entry point for all fraud checks.
Aggregates signals from all security_fraud/ modules into a single score.

Usage:
    result = FraudDetectionEngine.evaluate(request, offer=offer, user=user)
    if result['blocked']:
        raise FraudDetectedException(result['reason'])
"""
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class FraudEvalResult:
    """Complete fraud evaluation result."""
    score          : float = 0.0          # 0–100 composite score
    blocked        : bool  = False        # Should request be blocked?
    reason         : str   = ''           # Block reason if blocked
    signals        : dict  = field(default_factory=dict)   # Per-signal scores
    risk_level     : str   = 'low'        # low | medium | high | critical
    action         : str   = 'allow'      # allow | flag | block | suspend

    def as_dict(self) -> dict:
        return {
            'score'     : self.score,
            'blocked'   : self.blocked,
            'reason'    : self.reason,
            'signals'   : self.signals,
            'risk_level': self.risk_level,
            'action'    : self.action,
        }


class FraudDetectionEngine:
    """
    Multi-signal fraud detection engine.
    Combines: bot detection, IP reputation, device fingerprint,
    duplicate check, velocity, VPN/proxy, user risk profile.
    """

    # Score thresholds
    BLOCK_THRESHOLD   = 85.0
    FLAG_THRESHOLD    = 50.0
    SUSPEND_THRESHOLD = 95.0

    # Signal weights (must sum to 1.0)
    WEIGHTS = {
        'ip_reputation'     : 0.25,
        'bot_detection'     : 0.25,
        'user_risk_profile' : 0.20,
        'velocity'          : 0.15,
        'device_fingerprint': 0.10,
        'vpn_proxy'         : 0.05,
    }

    @classmethod
    def evaluate(cls, request, user=None, offer=None,
                  extra_ip: str = '') -> FraudEvalResult:
        """
        Full fraud evaluation.
        Returns FraudEvalResult with score, action, and signal breakdown.
        """
        ip         = extra_ip or cls._get_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '') if request else ''
        user_id    = str(user.id) if user else None

        signals    = {}

        # 1. IP Reputation
        signals['ip_reputation'] = cls._score_ip(ip)

        # 2. Bot Detection
        signals['bot_detection'] = cls._score_bot(ip, user_agent, user_id)

        # 3. User Risk Profile
        signals['user_risk_profile'] = cls._score_user_risk(user_id)

        # 4. Velocity Check
        signals['velocity'] = cls._score_velocity(ip, user_id)

        # 5. Device Fingerprint
        signals['device_fingerprint'] = cls._score_fingerprint(request, user_id)

        # 6. VPN/Proxy
        signals['vpn_proxy'] = cls._score_vpn(ip)

        # Composite score (weighted average)
        composite = sum(
            signals[k] * cls.WEIGHTS[k]
            for k in signals
        )

        return cls._make_result(composite, signals, ip, user_id)

    @classmethod
    def evaluate_conversion(cls, conversion) -> FraudEvalResult:
        """Evaluate fraud risk for a conversion event."""
        signals = {}

        # Speed of conversion (click → conversion)
        if conversion.click and conversion.click.created_at:
            delta_secs = (conversion.created_at - conversion.click.created_at).total_seconds()
            if delta_secs < 10:
                signals['conversion_speed'] = 90.0
            elif delta_secs < 30:
                signals['conversion_speed'] = 50.0
            else:
                signals['conversion_speed'] = 0.0
        else:
            signals['conversion_speed'] = 0.0

        # IP reputation
        signals['ip_reputation'] = cls._score_ip(conversion.ip_address or '')

        # User risk
        signals['user_risk_profile'] = cls._score_user_risk(
            str(conversion.user_id) if conversion.user_id else None
        )

        composite = sum(signals.values()) / len(signals) if signals else 0.0
        return cls._make_result(composite, signals,
                                 conversion.ip_address or '', str(conversion.user_id or ''))

    # ── Signal scorers ─────────────────────────────────────────────

    @staticmethod
    def _score_ip(ip: str) -> float:
        """IP reputation score (0=clean, 100=blocked)."""
        if not ip:
            return 50.0
        from api.offer_inventory.security_fraud import IPBlacklistManager
        if IPBlacklistManager.is_blocked(ip):
            return 100.0
        # Check hosting/datacenter
        from api.offer_inventory.targeting import ISPTargetingEngine
        return ISPTargetingEngine.get_risk_score_from_isp(ip)

    @staticmethod
    def _score_bot(ip: str, user_agent: str, user_id: Optional[str]) -> float:
        """Bot probability score."""
        from api.offer_inventory.security_fraud import BotDetector
        return BotDetector.score(ip, user_agent, user_id)

    @staticmethod
    def _score_user_risk(user_id: Optional[str]) -> float:
        """User risk profile score."""
        if not user_id:
            return 0.0
        from api.offer_inventory.repository import FraudRepository
        profile = FraudRepository.get_user_risk_profile(user_id)
        return profile.risk_score if profile else 0.0

    @staticmethod
    def _score_velocity(ip: str, user_id: Optional[str]) -> float:
        """Click velocity score."""
        from api.offer_inventory.security_fraud import BotDetector
        score = 0.0
        if ip:
            count = BotDetector._check_click_velocity.__func__(ip) if hasattr(BotDetector._check_click_velocity, '__func__') else 0
            # Simplified velocity check via cache
            from django.core.cache import cache
            count = cache.get(f'click_vel:{ip}:1min', 0)
            if count >= 10:
                score = min(100.0, count * 5.0)
        return score

    @staticmethod
    def _score_fingerprint(request, user_id: Optional[str]) -> float:
        """Device fingerprint risk score."""
        if not request or not user_id:
            return 0.0
        try:
            from api.offer_inventory.security_fraud import DeviceFingerprintAnalyzer
            fingerprint = DeviceFingerprintAnalyzer.from_request(request)
            return DeviceFingerprintAnalyzer.get_risk_score(fingerprint, user_id)
        except Exception:
            return 0.0

    @staticmethod
    def _score_vpn(ip: str) -> float:
        """VPN/proxy detection score."""
        if not ip:
            return 0.0
        try:
            from api.offer_inventory.geo_targeting import GeoTargetingEngine
            is_risky, reason = GeoTargetingEngine.is_high_risk_location(ip)
            return 80.0 if is_risky else 0.0
        except Exception:
            return 0.0

    # ── Result builder ─────────────────────────────────────────────

    @classmethod
    def _make_result(cls, score: float, signals: dict,
                      ip: str, user_id: str) -> FraudEvalResult:
        score = min(100.0, max(0.0, score))

        # Determine action
        if score >= cls.SUSPEND_THRESHOLD:
            action = 'suspend'
            blocked = True
            reason  = f'critical_fraud_score:{score:.0f}'
        elif score >= cls.BLOCK_THRESHOLD:
            action = 'block'
            blocked = True
            reason  = f'high_fraud_score:{score:.0f}'
        elif score >= cls.FLAG_THRESHOLD:
            action = 'flag'
            blocked = False
            reason  = f'medium_fraud_score:{score:.0f}'
        else:
            action = 'allow'
            blocked = False
            reason  = ''

        # Risk level
        if score >= 85:    risk_level = 'critical'
        elif score >= 60:  risk_level = 'high'
        elif score >= 35:  risk_level = 'medium'
        else:              risk_level = 'low'

        result = FraudEvalResult(
            score     =round(score, 1),
            blocked   =blocked,
            reason    =reason,
            signals   =signals,
            risk_level=risk_level,
            action    =action,
        )

        # Log high-risk results
        if score >= cls.FLAG_THRESHOLD:
            logger.warning(
                f'Fraud signal: score={score:.1f} action={action} '
                f'ip={ip} user={user_id} signals={signals}'
            )

        return result

    @staticmethod
    def _get_ip(request) -> str:
        if not request:
            return ''
        xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
        return xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR', '')

    # ── Auto-action ───────────────────────────────────────────────

    @classmethod
    def apply_action(cls, result: FraudEvalResult, user=None, ip: str = ''):
        """Apply the recommended action from evaluation."""
        if result.action in ('block', 'suspend') and ip:
            from api.offer_inventory.security_fraud import IPBlacklistManager
            IPBlacklistManager.block(ip, reason=result.reason, hours=24)

        if result.action == 'suspend' and user:
            from api.offer_inventory.repository import FraudRepository
            FraudRepository.update_risk_score(user.id, score_delta=20, flag=True)

        if result.action == 'flag' and user:
            from api.offer_inventory.repository import FraudRepository
            FraudRepository.update_risk_score(user.id, score_delta=5, flag=True)
