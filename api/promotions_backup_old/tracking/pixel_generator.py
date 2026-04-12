# api/promotions/tracking/pixel_generator.py
# Tracking Pixel — 1×1 GIF + JS pixel + S2S postback URLs
import base64, hashlib, hmac, logging, time
from django.conf import settings
logger = logging.getLogger('tracking.pixel')

TRANSPARENT_GIF = base64.b64decode('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7')
PIXEL_SECRET    = getattr(settings, 'PIXEL_SECRET', settings.SECRET_KEY[:32])
SITE_URL        = getattr(settings, 'SITE_URL', 'https://example.com')

class PixelGenerator:
    def pixel_url(self, campaign_id: int, user_id: int = None) -> str:
        ts  = int(time.time())
        sig = self._sign(campaign_id, user_id, ts)
        return f'{SITE_URL}/track/px/?c={campaign_id}&u={user_id or 0}&t={ts}&s={sig}'

    def gif_bytes(self) -> bytes:
        return TRANSPARENT_GIF

    def js_snippet(self, campaign_id: int) -> str:
        url = self.pixel_url(campaign_id)
        return f'<script>new Image().src="{url}&r="+Math.random();</script>'

    def postback_url(self, campaign_id: int) -> str:
        ts  = int(time.time())
        sig = self._sign(campaign_id, None, ts)
        return f'{SITE_URL}/track/pb/?c={campaign_id}&t={ts}&s={sig}&uid={{user_id}}&payout={{payout}}'

    def verify(self, campaign_id: int, user_id: int, ts: int, sig: str) -> bool:
        return hmac.compare_digest(self._sign(campaign_id, user_id, ts), sig)

    def _sign(self, campaign_id, user_id, ts) -> str:
        return hmac.new(PIXEL_SECRET.encode(), f'{campaign_id}:{user_id}:{ts}'.encode(), hashlib.sha256).hexdigest()[:16]
