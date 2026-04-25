# api/payment_gateways/fraud/FraudDetector.py
# UPDATED: Full ML + Device Fingerprint + Behavioral Analytics

from decimal import Decimal
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class FraudDetector:
    """
    Production-grade fraud detection engine.
    Runs 6 parallel checks and combines scores.

    Score 0-30:  Low    → allow
    Score 31-60: Medium → flag for review
    Score 61-80: High   → require verification
    Score 81+:   Critical → block

    New checks vs original:
        + ML risk scorer (statistical anomaly)
        + Device fingerprinting
        + Behavioral analytics
    """

    RISK_THRESHOLDS = {'low': 30, 'medium': 60, 'high': 80, 'critical': 100}

    def __init__(self):
        from .VelocityChecker    import VelocityChecker
        from .IPBlocklist         import IPBlocklist
        from .AnomalyDetector     import AnomalyDetector
        from .RiskRules           import RiskRules
        from .MLRiskScorer        import MLRiskScorer
        from .DeviceFingerprint   import DeviceFingerprint
        from .BehavioralAnalytics import BehavioralAnalytics

        self.velocity   = VelocityChecker()
        self.ip_check   = IPBlocklist()
        self.anomaly    = AnomalyDetector()
        self.rules      = RiskRules()
        self.ml         = MLRiskScorer()
        self.device     = DeviceFingerprint()
        self.behavioral = BehavioralAnalytics()

    def check(self, user, amount: Decimal, gateway: str,
              ip_address: str = None, metadata: dict = None,
              fingerprint: dict = None) -> dict:
        """
        Run all fraud checks.

        Args:
            user:         Django user object
            amount:       Transaction amount
            gateway:      Gateway name (bkash, stripe, etc.)
            ip_address:   Client IP
            metadata:     Extra context (session_key, user_agent, etc.)
            fingerprint:  Device fingerprint data dict

        Returns:
            {
                'risk_score': int (0-100),
                'risk_level': str,
                'action':     str (allow|flag|verify|block),
                'reasons':    [str],
                'checks':     {name: result},
            }
        """
        metadata    = metadata or {}
        reasons     = []
        checks      = {}
        total_score = 0

        # ── 1. IP Blocklist ──────────────────────────────────────────────────
        if ip_address:
            ip_result = self.ip_check.check(ip_address)
            checks['ip_blocklist'] = ip_result
            if ip_result.get('blocked'):
                total_score += 50
                reasons.append(f'IP {ip_address} is blocklisted')

        # ── 2. Velocity check ────────────────────────────────────────────────
        vel = self.velocity.check(user, amount, gateway)
        checks['velocity'] = vel
        total_score += vel['risk_score']
        reasons.extend(vel.get('reasons', []))

        # ── 3. Anomaly detection ─────────────────────────────────────────────
        anom = self.anomaly.check(user, amount, gateway, metadata)
        checks['anomaly'] = anom
        total_score += anom['risk_score']
        reasons.extend(anom.get('reasons', []))

        # ── 4. Rule engine ───────────────────────────────────────────────────
        rule = self.rules.evaluate(user, amount, gateway, ip_address, metadata)
        checks['rules'] = rule
        total_score += rule['risk_score']
        reasons.extend(rule.get('reasons', []))

        # ── 5. ML risk score (NEW) ───────────────────────────────────────────
        ml_result = self.ml.score(user, amount, gateway, ip_address, metadata)
        checks['ml_scorer'] = ml_result
        total_score += ml_result['risk_score']
        reasons.extend(ml_result.get('reasons', []))

        # ── 6. Device fingerprint (NEW) ──────────────────────────────────────
        if fingerprint:
            fp_data = {**fingerprint, 'ip': ip_address or ''}
            fp_result = self.device.check(user, fp_data)
            checks['device_fingerprint'] = fp_result
            total_score += fp_result['risk_score']
            reasons.extend(fp_result.get('reasons', []))

        # ── 7. Behavioral analytics (NEW) ────────────────────────────────────
        beh = self.behavioral.analyze(user, amount, gateway, metadata)
        checks['behavioral'] = beh
        total_score += beh['risk_score']
        reasons.extend(beh.get('reasons', []))

        # ── Final score ──────────────────────────────────────────────────────
        risk_score = min(100, max(0, total_score))
        risk_level = self._get_risk_level(risk_score)
        action     = self._get_action(risk_level)

        result = {
            'risk_score': risk_score,
            'risk_level': risk_level,
            'action':     action,
            'reasons':    list(set(reasons)),  # deduplicate
            'checks':     checks,
        }

        # Save alert for medium+ risks
        self._save_alert(user, amount, gateway, ip_address, result)

        logger.info(
            f'FraudDetector [{gateway}] user={user.id} amount={amount} '
            f'score={risk_score} level={risk_level} action={action}'
        )
        return result

    def _get_risk_level(self, score: int) -> str:
        if score <= self.RISK_THRESHOLDS['low']:     return 'low'
        if score <= self.RISK_THRESHOLDS['medium']:  return 'medium'
        if score <= self.RISK_THRESHOLDS['high']:    return 'high'
        return 'critical'

    def _get_action(self, risk_level: str) -> str:
        return {'low':'allow','medium':'flag','high':'verify','critical':'block'}[risk_level]

    def _save_alert(self, user, amount, gateway, ip_address, result):
        if result['risk_level'] in ('medium', 'high', 'critical'):
            try:
                from .models import FraudAlert
                FraudAlert.objects.create(
                    user       = user,
                    gateway    = gateway,
                    amount     = amount,
                    ip_address = ip_address,
                    risk_score = result['risk_score'],
                    risk_level = result['risk_level'],
                    action     = result['action'],
                    reasons    = result['reasons'],
                    metadata   = result['checks'],
                )
            except Exception as e:
                logger.warning(f'FraudDetector: could not save alert: {e}')
