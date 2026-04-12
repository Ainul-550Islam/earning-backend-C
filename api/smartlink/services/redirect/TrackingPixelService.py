import logging
import threading
import urllib.request
from django.conf import settings
from ...constants import S2S_PIXEL_TIMEOUT_SECONDS, PIXEL_ENDPOINT

logger = logging.getLogger('smartlink.tracking_pixel')


class TrackingPixelService:
    """
    Fire S2S (server-to-server) tracking pixel on redirect.
    Executed in a background thread to avoid blocking the redirect response.
    """

    def fire_async(self, pixel_url: str, context: dict = None):
        """Fire S2S pixel in a background thread (non-blocking)."""
        thread = threading.Thread(
            target=self._fire,
            args=(pixel_url, context or {}),
            daemon=True,
        )
        thread.start()

    def fire_postback(self, offer, click_id: int, payout: float = 0):
        """
        Fire conversion postback to the offer's configured postback URL.
        Called by ClickAttributionService on conversion.
        """
        postback_url = getattr(offer, 'postback_url', None)
        if not postback_url:
            return

        from ...utils import build_tracking_url
        url = build_tracking_url(postback_url, {
            'click_id': str(click_id),
            'payout': str(payout),
            'status': 'approved',
        })
        self.fire_async(url)
        logger.debug(f"Postback fired: offer#{offer.pk} click#{click_id} payout={payout}")

    def fire_impression_pixel(self, smartlink_id: int, offer_id: int, context: dict):
        """Fire an impression pixel when a redirect occurs."""
        base_url = getattr(settings, 'SMARTLINK_PIXEL_BASE_URL', '')
        if not base_url:
            return

        from ...utils import build_tracking_url
        url = build_tracking_url(f"{base_url}{PIXEL_ENDPOINT}", {
            'sl': str(smartlink_id),
            'offer': str(offer_id),
            'country': context.get('country', ''),
            'device': context.get('device_type', ''),
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
