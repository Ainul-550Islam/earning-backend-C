# api/offer_inventory/security_fraud/session_validator.py
"""
Session Validator.
Validates request sessions for offer interactions.
Detects session hijacking, replayed sessions, and anomalies.
"""
import hashlib
import logging
import time
from django.core.cache import cache

logger = logging.getLogger(__name__)

SESSION_MAX_AGE = 3600   # 1 hour
SESSION_TTL     = 7200   # 2 hour cache TTL


class SessionValidator:
    """
    Lightweight session fingerprinting for offer clicks.
    Not a replacement for Django sessions — additional security layer.
    """

    @staticmethod
    def create_session_token(user_id, ip: str, user_agent: str) -> str:
        """Create a short-lived session token."""
        ts      = str(int(time.time()))
        payload = f'{user_id}:{ip}:{user_agent}:{ts}'
        token   = hashlib.sha256(payload.encode()).hexdigest()

        cache.set(f'sess:{token}', {
            'user_id'   : str(user_id),
            'ip'        : ip,
            'ua'        : user_agent[:200],
            'created_at': time.time(),
        }, SESSION_TTL)
        return token

    @staticmethod
    def validate(token: str, user_id, ip: str,
                 user_agent: str) -> dict:
        """
        Validate session token.
        Returns {'valid': bool, 'reason': str}
        """
        if not token:
            return {'valid': False, 'reason': 'no_token'}

        data = cache.get(f'sess:{token}')
        if not data:
            return {'valid': False, 'reason': 'token_expired_or_not_found'}

        # Age check
        age = time.time() - data.get('created_at', 0)
        if age > SESSION_MAX_AGE:
            cache.delete(f'sess:{token}')
            return {'valid': False, 'reason': 'session_expired'}

        # User mismatch
        if str(data.get('user_id')) != str(user_id):
            logger.warning(f'Session user mismatch: token_user={data.get("user_id")} req_user={user_id}')
            return {'valid': False, 'reason': 'user_mismatch'}

        # IP change (soft warning, not hard fail — mobile IPs can change)
        if data.get('ip') != ip:
            logger.info(f'Session IP change: {data.get("ip")} → {ip} | user={user_id}')

        return {'valid': True, 'reason': 'ok', 'age_seconds': int(age)}

    @staticmethod
    def invalidate(token: str):
        """Invalidate a session token."""
        cache.delete(f'sess:{token}')

    @staticmethod
    def detect_session_sharing(token: str, current_ip: str) -> bool:
        """
        Detect if session used from multiple IPs simultaneously.
        Multiple different IPs using the same token = hijacking.
        """
        ip_key = f'sess_ips:{token}'
        ips    = cache.get(ip_key, set())
        ips.add(current_ip)
        cache.set(ip_key, ips, SESSION_TTL)
        # More than 3 distinct IPs = suspicious
        if len(ips) > 3:
            logger.warning(f'Session {token[:8]}... used from {len(ips)} IPs: {ips}')
            return True
        return False
