import logging
import re
import threading
import urllib.request
from urllib.parse import urlparse, urlencode, parse_qs, urlunparse
from django.conf import settings
from ...constants import S2S_PIXEL_TIMEOUT_SECONDS, PIXEL_ENDPOINT

logger = logging.getLogger('smartlink.tracking_pixel')


# All macro tokens supported in offer postback URLs
POSTBACK_MACROS = {
    '{click_id}',
    '{payout}',
    '{currency}',
    '{offer_id}',
    '{transaction_id}',
    '{status}',
    '{sub1}',
    '{sub2}',
    '{sub3}',
    '{sub4}',
    '{sub5}',
    '{country}',
    '{device}',
    '{ip}',
    '{pub_id}',
    '{sl_id}',
}


class TrackingPixelService:
    """
    Fire S2S (server-to-server) tracking pixel on redirect.
    Executed in a background thread to avoid blocking the redirect response.

    Supports postback macro replacement in offer URLs:
      {click_id}       → SmartLink click primary key
      {payout}         → conversion payout amount
      {currency}       → payout currency (default USD)
      {offer_id}       → offer primary key
      {transaction_id} → advertiser-provided transaction reference
      {status}         → 'approved' | 'rejected' | 'pending'
      {sub1}–{sub5}    → publisher sub IDs from click metadata
      {country}        → 2-letter ISO country code
      {device}         → mobile | desktop | tablet
      {ip}             → masked click IP
      {pub_id}         → publisher user ID
      {sl_id}          → SmartLink slug
    """

    def fire_async(self, pixel_url: str, context: dict = None):
        """Fire S2S pixel in a background thread (non-blocking)."""
        thread = threading.Thread(
            target=self._fire,
            args=(pixel_url, context or {}),
            daemon=True,
        )
        thread.start()

    def fire_postback(self, offer, click_id: int, payout: float = 0,
                      currency: str = 'USD', transaction_id: str = '',
                      status: str = 'approved', click=None):
        """
        Fire conversion postback to the offer's configured postback URL.
        Called by ClickAttributionService on conversion.

        FIX: Previously used build_tracking_url() which appended params as query string.
        Now uses replace_macros() which replaces {token} placeholders in-place,
        matching standard affiliate network postback URL format.
        """
        postback_url = getattr(offer, 'postback_url', None)
        if not postback_url:
            return

        # Build macro value map
        macro_values = {
            '{click_id}':       str(click_id),
            '{payout}':         str(round(payout, 4)),
            '{currency}':       currency,
            '{offer_id}':       str(offer.pk),
            '{transaction_id}': transaction_id or '',
            '{status}':         status,
            '{country}':        '',
            '{device}':         '',
            '{ip}':             '',
            '{pub_id}':         '',
            '{sl_id}':          '',
        }

        # Enrich with click metadata if available
        if click is not None:
            macro_values['{country}'] = getattr(click, 'country', '')
            macro_values['{device}']  = getattr(click, 'device_type', '')
            macro_values['{sub1}']    = getattr(click, 'sub1', '')
            macro_values['{sub2}']    = getattr(click, 'sub2', '')
            macro_values['{sub3}']    = getattr(click, 'sub3', '')
            macro_values['{sub4}']    = getattr(click, 'sub4', '')
            macro_values['{sub5}']    = getattr(click, 'sub5', '')
            macro_values['{pub_id}']  = str(getattr(click.smartlink, 'publisher_id', ''))
            macro_values['{sl_id}']   = getattr(click.smartlink, 'slug', '')
            # Mask last octet for GDPR
            raw_ip = getattr(click, 'ip', '')
            macro_values['{ip}'] = self._mask_ip(raw_ip)
        else:
            # Provide empty fallbacks for all sub macros
            for sub in ('{sub1}', '{sub2}', '{sub3}', '{sub4}', '{sub5}'):
                macro_values[sub] = ''

        fired_url = self.replace_macros(postback_url, macro_values)
        self.fire_async(fired_url)
        logger.debug(
            f"Postback fired: offer#{offer.pk} click#{click_id} "
            f"payout={payout} url={fired_url[:80]}"
        )

    def replace_macros(self, url: str, macro_values: dict) -> str:
        """
        Replace all {macro} tokens in a URL with their values.
        Tokens with empty values are replaced with empty string (not removed).
        Any remaining unreplaced tokens are replaced with empty string.

        Example:
          'https://offer.com/cb?cid={click_id}&payout={payout}'
          → 'https://offer.com/cb?cid=12345&payout=3.5'
        """
        result = url
        for token, value in macro_values.items():
            result = result.replace(token, str(value) if value is not None else '')
        # Clean up any remaining unrecognised macro tokens
        result = re.sub(r'\{[a-z0-9_]+\}', '', result)
        return result

    def has_macros(self, url: str) -> bool:
        """Return True if the URL contains any recognised macro tokens."""
        if not url:
            return False
        return any(macro in url for macro in POSTBACK_MACROS)

    def fire_impression_pixel(self, smartlink_id: int, offer_id: int, context: dict):
        """Fire an impression pixel when a redirect occurs."""
        base_url = getattr(settings, 'SMARTLINK_PIXEL_BASE_URL', '')
        if not base_url:
            return

        from ...utils import build_tracking_url
        url = build_tracking_url(f"{base_url}{PIXEL_ENDPOINT}", {
            'sl':      str(smartlink_id),
            'offer':   str(offer_id),
            'country': context.get('country', ''),
            'device':  context.get('device_type', ''),
        })
        self.fire_async(url)

    def _fire(self, url: str, context: dict):
        """Synchronously fire HTTP GET to pixel URL."""
        try:
            req = urllib.request.Request(
                url,
                headers={'User-Agent': 'SmartLink-Pixel/1.0'},
            )
            with urllib.request.urlopen(req, timeout=S2S_PIXEL_TIMEOUT_SECONDS) as resp:
                status = resp.getcode()
                logger.debug(f"Pixel fired: {url[:80]} → {status}")
        except Exception as e:
            logger.warning(f"Pixel fire failed: {url[:80]} — {e}")

    def _mask_ip(self, ip: str) -> str:
        """Mask last octet of IPv4 for GDPR-safe logging."""
        parts = ip.split('.')
        if len(parts) == 4:
            return f"{parts[0]}.{parts[1]}.{parts[2]}.***"
        return ip
