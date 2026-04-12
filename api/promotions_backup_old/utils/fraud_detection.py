# api/promotions/utils/fraud_detection.py
import logging
from django.core.cache import cache
logger = logging.getLogger('utils.fraud')

class FraudDetectionService:
    """Unified fraud detection — coordinates all fraud signals。"""

    def full_check(self, submission_id: int, user_id: int, ip: str, fingerprint: str = '') -> dict:
        signals = {}
        score   = 0.0

        # IP reputation
        from api.promotions.utils.ip_geolocation import IPGeolocation
        geo = IPGeolocation().lookup(ip)
        if geo.get('is_proxy'):
            signals['vpn_proxy'] = True; score += 0.3

        # Device fingerprint multi-account
        if fingerprint:
            from api.promotions.utils.device_fingerprint import DeviceFingerprinter
            fp_check = DeviceFingerprinter().check_multi_account(fingerprint, user_id)
            if fp_check['suspicious']:
                signals['multi_account'] = fp_check['count']; score += 0.25

        # User trust score
        trust = cache.get(f'gov:trust:{user_id}')
        if trust is not None and trust < 30:
            signals['low_trust'] = trust; score += 0.2

        # Submission velocity (too many in 1 hour)
        velocity_key = f'fraud:velocity:{user_id}'
        count = (cache.get(velocity_key) or 0) + 1
        cache.set(velocity_key, count, timeout=3600)
        if count > 20:
            signals['high_velocity'] = count; score += 0.25

        risk = 'critical' if score >= 0.7 else ('high' if score >= 0.4 else ('medium' if score >= 0.2 else 'low'))
        return {'fraud_score': round(min(1.0, score), 3), 'risk_level': risk, 'signals': signals,
                'action': 'ban' if score >= 0.8 else ('reject' if score >= 0.5 else 'allow')}
