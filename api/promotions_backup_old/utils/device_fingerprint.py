# api/promotions/utils/device_fingerprint.py
import hashlib, json, logging
from django.core.cache import cache
logger = logging.getLogger('utils.fingerprint')

class DeviceFingerprinter:
    """Browser/device fingerprint generate ও match করে।"""

    def generate(self, request_data: dict) -> str:
        """Stable device fingerprint generate করে।"""
        stable_keys = ['user_agent', 'screen_resolution', 'timezone', 'language', 'platform', 'canvas_hash', 'webgl_hash']
        payload = {k: request_data.get(k, '') for k in stable_keys}
        fp = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:32]
        return fp

    def is_same_device(self, fp1: str, fp2: str) -> bool:
        return fp1 == fp2

    def check_multi_account(self, fingerprint: str, user_id: int) -> dict:
        """Same device থেকে multiple accounts detect করে।"""
        fp_key   = f'fp:{fingerprint}'
        known    = cache.get(fp_key) or []
        if user_id not in known:
            known.append(user_id)
            cache.set(fp_key, known[-10:], timeout=86400*30)
        suspicious = len(known) > 1
        return {'accounts': known, 'suspicious': suspicious, 'count': len(known)}

    def track_device(self, fingerprint: str, user_id: int, ip: str) -> None:
        cache.set(f'fp:user:{user_id}', fingerprint, timeout=86400*30)
        fp_key = f'fp:{fingerprint}'
        known  = cache.get(fp_key) or []
        if user_id not in known:
            known.append(user_id)
            cache.set(fp_key, known[-10:], timeout=86400*30)
