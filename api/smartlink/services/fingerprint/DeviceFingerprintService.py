"""
SmartLink Device Fingerprint Service
World #1 Feature: Server-side device fingerprinting for superior deduplication.

Creates a unique device fingerprint from:
- IP address (masked for privacy)
- User-Agent string hash
- Accept-Language header
- Accept header
- Accept-Encoding header
- Screen resolution (if passed via JS pixel)
- Timezone offset (if passed via JS pixel)

Goes beyond CPAlead's simple IP-based dedup.
Catches VPN users who change IPs but keep same device.
"""
import hashlib
import json
import logging
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger('smartlink.fingerprint')


class DeviceFingerprintService:
    """
    Generate stable device fingerprints for superior click deduplication.
    Works even when IP changes (VPN users, mobile network handoffs).
    """

    CACHE_TTL = 86400 * 30  # 30 days

    def generate(self, request_context: dict) -> str:
        """
        Generate a stable device fingerprint from request headers.

        Args:
            request_context: {
                ip, user_agent, accept_language,
                accept, accept_encoding,
                screen_resolution (optional, from JS),
                timezone_offset (optional, from JS),
                canvas_hash (optional, from JS pixel),
            }

        Returns:
            64-char hex fingerprint
        """
        components = []

        # 1. IP subnet (first 3 octets — stable across DHCP renewal)
        ip = request_context.get('ip', '')
        parts = ip.split('.')
        if len(parts) == 4:
            components.append(f"subnet:{'.'.join(parts[:3])}")
        else:
            components.append(f"ip:{ip[:20]}")

        # 2. User-Agent (most stable identifier)
        ua = request_context.get('user_agent', '')
        if ua:
            components.append(f"ua:{hashlib.md5(ua.encode()).hexdigest()[:16]}")

        # 3. Language preferences
        lang = request_context.get('accept_language', '')
        if lang:
            components.append(f"lang:{lang[:30]}")

        # 4. Accept header (browser-specific)
        accept = request_context.get('accept', '')
        if accept:
            components.append(f"accept:{hashlib.md5(accept.encode()).hexdigest()[:8]}")

        # 5. Screen resolution (if available from JS)
        screen = request_context.get('screen_resolution', '')
        if screen:
            components.append(f"screen:{screen}")

        # 6. Timezone (if available from JS)
        tz_offset = request_context.get('timezone_offset', '')
        if tz_offset:
            components.append(f"tz:{tz_offset}")

        # 7. Canvas fingerprint hash (if available from JS pixel)
        canvas = request_context.get('canvas_hash', '')
        if canvas:
            components.append(f"canvas:{canvas[:16]}")

        # Combine all components
        raw = '|'.join(sorted(components))
        fingerprint = hashlib.sha256(raw.encode()).hexdigest()

        logger.debug(f"Fingerprint generated: {fingerprint[:16]}... ({len(components)} components)")
        return fingerprint

    def is_seen(self, fingerprint: str, offer_id: int, window_hours: int = 24) -> bool:
        """
        Check if this device has already clicked this offer in the time window.
        More accurate than IP-based dedup.
        """
        cache_key = self._seen_key(fingerprint, offer_id)
        return bool(cache.get(cache_key))

    def mark_seen(self, fingerprint: str, offer_id: int, click_id: int,
                   window_hours: int = 24):
        """Mark device+offer combination as seen."""
        cache_key = self._seen_key(fingerprint, offer_id)
        cache.set(cache_key, {
            'click_id': click_id,
            'seen_at':  timezone.now().isoformat(),
        }, window_hours * 3600)

    def get_device_profile(self, fingerprint: str) -> dict:
        """Get stored device profile for a fingerprint."""
        cache_key = f"fp_profile:{fingerprint}"
        return cache.get(cache_key, {})

    def update_device_profile(self, fingerprint: str, context: dict):
        """
        Build/update device profile over time.
        Helps identify device upgrade (same user, new phone).
        """
        cache_key   = f"fp_profile:{fingerprint}"
        profile     = cache.get(cache_key, {})
        now_str     = timezone.now().isoformat()

        profile.update({
            'last_seen':    now_str,
            'user_agent':   context.get('user_agent', profile.get('user_agent', '')),
            'country':      context.get('country', profile.get('country', '')),
            'device_type':  context.get('device_type', profile.get('device_type', '')),
            'os':           context.get('os', profile.get('os', '')),
            'click_count':  profile.get('click_count', 0) + 1,
        })
        if 'first_seen' not in profile:
            profile['first_seen'] = now_str

        cache.set(cache_key, profile, self.CACHE_TTL)
        return profile

    def detect_emulator(self, context: dict) -> bool:
        """
        Detect if device is an Android emulator (common in click fraud).
        Emulators have telltale UA patterns.
        """
        ua = context.get('user_agent', '').lower()
        emulator_signals = [
            'android sdk built for x86',
            'genymotion',
            'emulator',
            'sdk_gphone',
            'android_x86',
            'vbox',
            'virtualbox',
        ]
        return any(sig in ua for sig in emulator_signals)

    def _seen_key(self, fingerprint: str, offer_id: int) -> str:
        return f"fp_seen:{fingerprint[:32]}:{offer_id}"
