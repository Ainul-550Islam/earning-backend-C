# api/payment_gateways/fraud/DeviceFingerprint.py
# Device fingerprinting for fraud detection

import hashlib
import json
from django.core.cache import cache
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class DeviceFingerprint:
    """
    Device fingerprinting to detect:
        - Same device used by multiple accounts
        - Known fraud devices
        - Device switching behavior
    """

    CACHE_TTL = 86400 * 30  # 30 days

    def check(self, user, fingerprint_data: dict) -> dict:
        """
        Check device fingerprint against known fraud patterns.

        Args:
            fingerprint_data: {
                'user_agent': str,
                'ip': str,
                'screen_resolution': str (optional),
                'timezone': str (optional),
                'language': str (optional),
                'platform': str (optional),
            }
        """
        fp_hash = self._generate_hash(fingerprint_data)
        risk_score = 0
        reasons    = []

        # Check if device is linked to other users
        other_users = self._check_device_users(fp_hash, user.id)
        if other_users > 0:
            risk_score += min(30, other_users * 10)
            reasons.append(f'Device linked to {other_users} other account(s)')

        # Check if device is flagged
        if self._is_device_flagged(fp_hash):
            risk_score += 40
            reasons.append('Device is flagged for previous fraud')

        # Check IP + device mismatch
        ip_devices = self._count_devices_for_ip(fingerprint_data.get('ip', ''))
        if ip_devices > 5:
            risk_score += 15
            reasons.append(f'{ip_devices} different devices from same IP')

        # Store device association
        self._store_device(fp_hash, user.id, fingerprint_data)

        return {
            'fingerprint_hash': fp_hash,
            'risk_score':       min(50, risk_score),
            'reasons':          reasons,
            'other_users':      other_users,
        }

    def _generate_hash(self, data: dict) -> str:
        """Generate stable hash from device data."""
        canonical = json.dumps({
            'ua':  data.get('user_agent', ''),
            'tz':  data.get('timezone', ''),
            'lang': data.get('language', ''),
            'platform': data.get('platform', ''),
        }, sort_keys=True)
        return hashlib.sha256(canonical.encode()).hexdigest()[:32]

    def _check_device_users(self, fp_hash: str, current_user_id: int) -> int:
        """Count how many different users have used this device."""
        key   = f'fp_users:{fp_hash}'
        users = cache.get(key, set())
        if isinstance(users, list):
            users = set(users)
        return len(users - {current_user_id})

    def _is_device_flagged(self, fp_hash: str) -> bool:
        """Check if device is in fraud blocklist."""
        return bool(cache.get(f'fp_flagged:{fp_hash}'))

    def _count_devices_for_ip(self, ip: str) -> int:
        """Count unique devices from an IP."""
        key     = f'ip_devices:{ip}'
        devices = cache.get(key, set())
        return len(devices)

    def _store_device(self, fp_hash: str, user_id: int, data: dict):
        """Store device-user association in cache."""
        # Store user association
        user_key  = f'fp_users:{fp_hash}'
        users     = cache.get(user_key, set())
        if isinstance(users, list):
            users = set(users)
        users.add(user_id)
        cache.set(user_key, users, self.CACHE_TTL)

        # Store IP-device association
        ip = data.get('ip', '')
        if ip:
            ip_key  = f'ip_devices:{ip}'
            devices = cache.get(ip_key, set())
            if isinstance(devices, list):
                devices = set(devices)
            devices.add(fp_hash)
            cache.set(ip_key, devices, self.CACHE_TTL)

    def flag_device(self, fp_hash: str, reason: str = ''):
        """Mark a device as fraudulent."""
        cache.set(f'fp_flagged:{fp_hash}', {'reason': reason, 'flagged_at': str(timezone.now())}, self.CACHE_TTL)
        logger.warning(f'Device flagged: {fp_hash} — {reason}')

    def unflag_device(self, fp_hash: str):
        """Remove device from fraud list."""
        cache.delete(f'fp_flagged:{fp_hash}')
