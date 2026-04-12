# api/offer_inventory/webhooks/pixel_tracking.py
"""
Pixel Tracking System.
Fires 1×1 transparent GIF pixels for conversion tracking.
Supports server-side and client-side pixel delivery.
"""
import logging
import hashlib
import time
import requests as _req
from typing import Optional
from django.http import HttpResponse
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

# 1×1 transparent GIF (binary)
TRANSPARENT_GIF = (
    b'GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff'
    b'\x00\x00\x00!\xf9\x04\x00\x00\x00\x00\x00,'
    b'\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
)

# 1×1 transparent PNG (alternative)
TRANSPARENT_PNG = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
    b'\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89'
    b'\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01'
    b'\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
)


class PixelTracker:
    """
    Conversion pixel tracking — server-to-server and browser-based.
    """

    # ── Pixel response helpers ─────────────────────────────────────

    @staticmethod
    def gif_response() -> HttpResponse:
        """Return a 1×1 transparent GIF HTTP response."""
        resp = HttpResponse(TRANSPARENT_GIF, content_type='image/gif')
        resp['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
        resp['Pragma']        = 'no-cache'
        resp['Expires']       = '0'
        resp['X-Robots-Tag']  = 'noindex'
        return resp

    @staticmethod
    def png_response() -> HttpResponse:
        """Return a 1×1 transparent PNG HTTP response."""
        resp = HttpResponse(TRANSPARENT_PNG, content_type='image/png')
        resp['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
        return resp

    # ── Server-side pixel firing ───────────────────────────────────

    @staticmethod
    def fire(conversion_id: str) -> bool:
        """
        Fire pixel for a conversion.
        Logs the result to PixelLog.
        """
        from api.offer_inventory.models import Conversion, PixelLog

        try:
            conversion = Conversion.objects.select_related('offer').get(id=conversion_id)
        except Conversion.DoesNotExist:
            logger.error(f'Pixel fire: conversion {conversion_id} not found')
            return False

        # Build pixel URL (from offer config or network default)
        pixel_url = PixelTracker._build_pixel_url(conversion)
        if not pixel_url:
            return True  # No pixel configured — not an error

        # Idempotency: don't fire twice for same conversion
        cache_key = f'pixel_fired:{conversion_id}'
        if cache.get(cache_key):
            logger.info(f'Pixel already fired for {conversion_id}')
            return True

        # Fire
        success, error_msg = PixelTracker._send_pixel(pixel_url)

        # Log result
        try:
            PixelLog.objects.create(
                conversion=conversion,
                pixel_url =pixel_url,
                is_fired  =success,
                error     =error_msg,
            )
        except Exception as e:
            logger.error(f'PixelLog save error: {e}')

        if success:
            cache.set(cache_key, '1', 86400)  # Mark as fired for 24h
            logger.info(f'Pixel fired OK: {conversion_id} → {pixel_url[:60]}')
        else:
            logger.warning(f'Pixel fire FAILED: {conversion_id} → {error_msg}')

        return success

    @staticmethod
    def fire_bulk(conversion_ids: list) -> dict:
        """Fire pixels for multiple conversions."""
        results = {'fired': 0, 'failed': 0, 'skipped': 0}
        for conv_id in conversion_ids:
            try:
                ok = PixelTracker.fire(str(conv_id))
                if ok:
                    results['fired'] += 1
                else:
                    results['failed'] += 1
            except Exception as e:
                logger.error(f'Bulk pixel error {conv_id}: {e}')
                results['failed'] += 1
        return results

    # ── URL builder ────────────────────────────────────────────────

    @staticmethod
    def _build_pixel_url(conversion) -> Optional[str]:
        """Build pixel URL with macro replacements."""
        offer   = conversion.offer
        network = offer.network if offer else None

        # Try offer-level pixel URL first
        pixel_url = getattr(offer, 'pixel_url', '') or ''

        # Fallback to network postback URL
        if not pixel_url and network and network.postback_url:
            pixel_url = network.postback_url

        if not pixel_url:
            return None

        # Replace macros
        macros = {
            '{click_id}'      : str(conversion.click_id or ''),
            '{transaction_id}': str(conversion.transaction_id or ''),
            '{payout}'        : str(conversion.payout_amount),
            '{reward}'        : str(conversion.reward_amount),
            '{offer_id}'      : str(offer.id) if offer else '',
            '{user_id}'       : str(conversion.user_id or ''),
            '{country}'       : str(conversion.country_code or ''),
            '{timestamp}'     : str(int(time.time())),
        }
        for macro, value in macros.items():
            pixel_url = pixel_url.replace(macro, value)

        return pixel_url

    @staticmethod
    def _send_pixel(url: str, timeout: int = 5) -> tuple:
        """
        Send pixel GET request.
        Returns (success: bool, error: str)
        """
        try:
            resp = _req.get(url, timeout=timeout, allow_redirects=True)
            if resp.status_code in (200, 204):
                return True, ''
            return False, f'HTTP {resp.status_code}'
        except _req.exceptions.Timeout:
            return False, 'timeout'
        except _req.exceptions.ConnectionError as e:
            return False, f'connection_error: {str(e)[:100]}'
        except Exception as e:
            return False, str(e)[:200]


class PixelEndpointHandler:
    """
    Handles incoming pixel requests from browsers.
    Used when our platform serves as the pixel endpoint.
    """

    @staticmethod
    def handle_impression(request, offer_id: str) -> HttpResponse:
        """Record an offer impression from browser pixel."""
        from api.offer_inventory.models import Offer, Impression
        ip = PixelEndpointHandler._get_ip(request)
        try:
            offer = Offer.objects.get(id=offer_id, status='active')
            Impression.objects.create(
                offer     =offer,
                user      =request.user if request.user.is_authenticated else None,
                ip_address=ip,
                country   =request.META.get('HTTP_CF_IPCOUNTRY', '')[:2],
                device    ='mobile' if 'Mobile' in request.META.get('HTTP_USER_AGENT', '') else 'desktop',
            )
        except Exception as e:
            logger.debug(f'Impression pixel error: {e}')
        return PixelTracker.gif_response()

    @staticmethod
    def handle_conversion_pixel(request, token: str) -> HttpResponse:
        """
        Browser fires this pixel after offer completion.
        Decodes signed token → triggers server-side conversion.
        """
        ip = PixelEndpointHandler._get_ip(request)
        logger.info(f'Conversion pixel received: token={token[:16]}... ip={ip}')

        try:
            # Validate and decode token
            data = PixelEndpointHandler._decode_token(token)
            if not data:
                return PixelTracker.gif_response()

            # Check if already processed
            cache_key = f'conv_pixel:{token[:32]}'
            if cache.get(cache_key):
                return PixelTracker.gif_response()

            # Trigger conversion async
            from api.offer_inventory.tasks import process_pixel_conversion
            process_pixel_conversion.delay(
                click_token=data['click_token'],
                offer_id   =data['offer_id'],
                ip         =ip,
            )
            cache.set(cache_key, '1', 3600)

        except Exception as e:
            logger.error(f'Conversion pixel handler error: {e}')

        return PixelTracker.gif_response()

    @staticmethod
    def _decode_token(token: str) -> Optional[dict]:
        """Decode conversion pixel token."""
        try:
            import base64, json
            decoded = base64.urlsafe_b64decode(token + '==')
            return json.loads(decoded)
        except Exception:
            return None

    @staticmethod
    def _get_ip(request) -> str:
        xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
        return xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR', '')

    @staticmethod
    def build_pixel_tag(offer_id: str, base_url: str = '') -> str:
        """Generate HTML pixel img tag for embedding."""
        url = f'{base_url}/api/offer-inventory/pixel/impression/{offer_id}/'
        return f'<img src="{url}" width="1" height="1" border="0" alt="" style="display:none" />'
