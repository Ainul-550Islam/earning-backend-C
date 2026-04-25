# api/payment_gateways/tracking/FingerprintEngine.py
# Browser fingerprinting for anti-fraud and duplicate click detection

import hashlib
import json
import logging
from django.core.cache import cache

logger = logging.getLogger(__name__)


class FingerprintEngine:
    """
    Browser fingerprinting engine for click fraud detection.

    Collects:
        - User-Agent string
        - Accept-Language header
        - Accept-Encoding header
        - IP address
        - Screen resolution (from JS, optional)
        - Timezone (from JS, optional)
        - Canvas fingerprint hash (from JS, optional)

    Used to:
        1. Detect duplicate clicks from same browser
        2. Identify click fraud (one person, many IPs via VPN)
        3. Link clicks to conversions even if cookie is deleted
        4. Detect bot traffic patterns

    Privacy note: We hash all data — no PII stored in fingerprint.
    """

    CACHE_TTL       = 86400 * 30  # 30 days
    DUPLICATE_WINDOW= 3600        # 1 hour window for duplicate detection

    def generate_fingerprint(self, request, extra_data: dict = None) -> str:
        """
        Generate a browser fingerprint hash from HTTP request.

        Args:
            request:    Django HttpRequest
            extra_data: Optional JS-collected data (screen_res, timezone, etc.)

        Returns:
            str: 32-character hex fingerprint hash
        """
        components = {
            'ua':      request.META.get('HTTP_USER_AGENT', ''),
            'lang':    request.META.get('HTTP_ACCEPT_LANGUAGE', ''),
            'enc':     request.META.get('HTTP_ACCEPT_ENCODING', ''),
            'accept':  request.META.get('HTTP_ACCEPT', ''),
        }

        if extra_data:
            components.update({
                'screen': extra_data.get('screen_resolution', ''),
                'tz':     extra_data.get('timezone', ''),
                'canvas': extra_data.get('canvas_hash', ''),
                'fonts':  extra_data.get('fonts_hash', ''),
            })

        # Create stable, sorted JSON for consistent hashing
        canonical = json.dumps(components, sort_keys=True)
        fp_hash   = hashlib.sha256(canonical.encode()).hexdigest()[:32]

        return fp_hash

    def is_duplicate_click(self, fingerprint: str, offer_id: int,
                             publisher_id: int, window_seconds: int = None) -> bool:
        """
        Check if this browser already clicked this offer within the time window.

        Returns True if duplicate (should block), False if fresh click.
        """
        window    = window_seconds or self.DUPLICATE_WINDOW
        cache_key = f'fp_click:{fingerprint}:{offer_id}:{publisher_id}'
        return bool(cache.get(cache_key))

    def record_click(self, fingerprint: str, offer_id: int,
                      publisher_id: int, click_id: str,
                      window_seconds: int = None):
        """Record a click fingerprint to detect future duplicates."""
        window    = window_seconds or self.DUPLICATE_WINDOW
        cache_key = f'fp_click:{fingerprint}:{offer_id}:{publisher_id}'
        cache.set(cache_key, click_id, window)

        # Also track all click_ids for this fingerprint (for linking)
        fp_key  = f'fp_clicks:{fingerprint}'
        clicks  = cache.get(fp_key, [])
        if isinstance(clicks, str):
            clicks = [clicks]
        clicks.append(click_id)
        cache.set(fp_key, clicks[-100:], self.CACHE_TTL)  # Keep last 100

        logger.debug(f'Click fingerprinted: {fingerprint[:8]}... offer={offer_id}')

    def get_fingerprint_risk(self, fingerprint: str, ip: str) -> dict:
        """
        Assess risk level based on fingerprint history.

        Returns:
            dict: {risk_score: int, reasons: list, is_fraud: bool}
        """
        risk_score = 0
        reasons    = []

        # Check: many different offers clicked (normal publisher behavior)
        fp_key = f'fp_clicks:{fingerprint}'
        clicks = cache.get(fp_key, [])
        if len(clicks) > 50:
            risk_score += 15
            reasons.append(f'High click volume: {len(clicks)} clicks from this browser')

        # Check: fingerprint linked to known bad IPs
        if cache.get(f'fp_fraud:{fingerprint}'):
            risk_score += 50
            reasons.append('Fingerprint flagged for previous fraud')

        # Check: too many different IPs for same fingerprint (VPN rotation)
        ip_key  = f'fp_ips:{fingerprint}'
        ips     = cache.get(ip_key, set())
        if isinstance(ips, list):
            ips = set(ips)
        ips.add(ip)
        cache.set(ip_key, ips, self.CACHE_TTL)
        if len(ips) > 10:
            risk_score += 25
            reasons.append(f'Browser seen from {len(ips)} different IPs (possible VPN rotation)')

        return {
            'risk_score': min(100, risk_score),
            'reasons':    reasons,
            'is_fraud':   risk_score >= 50,
            'click_count':len(clicks),
            'ip_count':   len(ips),
        }

    def flag_fingerprint(self, fingerprint: str, reason: str = ''):
        """Flag a fingerprint as fraudulent."""
        cache.set(
            f'fp_fraud:{fingerprint}',
            {'reason': reason, 'flagged': True},
            self.CACHE_TTL
        )
        logger.warning(f'Fingerprint flagged as fraud: {fingerprint[:8]}... reason={reason}')

    def unflag_fingerprint(self, fingerprint: str):
        """Remove fraud flag from a fingerprint."""
        cache.delete(f'fp_fraud:{fingerprint}')

    def link_fingerprint_to_conversion(self, click_id: str,
                                         conversion_id: str, fingerprint: str):
        """
        Link a fingerprint to a conversion.
        Enables matching orphaned conversions to their original clicks.
        """
        cache.set(
            f'fp_conversion:{fingerprint}:{click_id}',
            conversion_id,
            self.CACHE_TTL
        )
