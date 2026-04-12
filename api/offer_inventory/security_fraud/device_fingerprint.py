# api/offer_inventory/security_fraud/device_fingerprint.py
"""
Device Fingerprinting.
Generates and analyzes browser/device fingerprints
to detect multi-account fraud.
"""
import hashlib
import logging
from django.core.cache import cache

logger = logging.getLogger(__name__)


class DeviceFingerprintAnalyzer:
    """Generate, store, and analyze device fingerprints."""

    @staticmethod
    def generate(user_agent: str = '', screen_res: str = '',
                 timezone_str: str = '', language: str = '',
                 canvas_hash: str = '', webgl_hash: str = '',
                 fonts_hash: str = '') -> str:
        """Generate a device fingerprint from browser signals."""
        components = [
            user_agent, screen_res, timezone_str,
            language, canvas_hash, webgl_hash, fonts_hash,
        ]
        raw = '|'.join(str(c) for c in components)
        return hashlib.sha256(raw.encode()).hexdigest()

    @staticmethod
    def from_request(request) -> str:
        """
        Generate fingerprint from request headers.
        Uses available signals without JS (server-side only).
        """
        ua       = request.META.get('HTTP_USER_AGENT', '')
        language = request.META.get('HTTP_ACCEPT_LANGUAGE', '')
        encoding = request.META.get('HTTP_ACCEPT_ENCODING', '')
        accept   = request.META.get('HTTP_ACCEPT', '')

        raw = f'{ua}|{language}|{encoding}|{accept}'
        return hashlib.sha256(raw.encode()).hexdigest()

    @staticmethod
    def store(fingerprint: str, user, user_agent: str = '',
              screen_res: str = '', timezone_str: str = '',
              language: str = '') -> object:
        """Store fingerprint to DB and return record."""
        from api.offer_inventory.models import DeviceFingerprint
        obj, created = DeviceFingerprint.objects.get_or_create(
            fingerprint=fingerprint,
            user=user,
            defaults={
                'user_agent': user_agent[:500],
                'screen_res': screen_res[:20],
                'timezone'  : timezone_str[:60],
                'language'  : language[:10],
            }
        )
        if not created and not obj.is_flagged:
            # Check for multi-account
            _, linked = DeviceFingerprintAnalyzer.check_multi_account(
                fingerprint, user.id
            )
            if linked:
                DeviceFingerprint.objects.filter(fingerprint=fingerprint).update(is_flagged=True)

        return obj

    @staticmethod
    def check_multi_account(fingerprint: str, current_user_id,
                             threshold: int = 2) -> tuple:
        """
        Detect multiple accounts sharing same device.
        Returns (is_multi_account: bool, other_user_ids: list)
        """
        from api.offer_inventory.models import DeviceFingerprint

        other_users = list(
            DeviceFingerprint.objects.filter(fingerprint=fingerprint)
            .exclude(user_id=current_user_id)
            .values_list('user_id', flat=True)
            .distinct()
        )

        if len(other_users) >= threshold:
            logger.warning(
                f'Multi-account fingerprint detected: '
                f'fp={fingerprint[:16]}... | '
                f'users={other_users}'
            )
            return True, other_users

        return False, []

    @staticmethod
    def get_risk_score(fingerprint: str, user_id) -> float:
        """Risk score based on fingerprint sharing."""
        is_multi, others = DeviceFingerprintAnalyzer.check_multi_account(
            fingerprint, user_id
        )
        if not is_multi:
            return 0.0
        # More shared accounts = higher risk
        return min(100.0, 30.0 + len(others) * 20.0)
