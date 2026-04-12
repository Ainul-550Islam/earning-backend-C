# api/offer_inventory/affiliate_advanced/conversion_pixel_v2.py
"""Conversion Pixel v2 — Enhanced server-side and client-side pixel firing."""
import logging
import base64
import json
from django.conf import settings

logger = logging.getLogger(__name__)


class ConversionPixelV2:
    """Server-side, client-side, and hybrid conversion pixel system."""

    @staticmethod
    def generate_img_tag(offer_id: str, user_id=None,
                          click_token: str = '',
                          base_url: str = '') -> str:
        """Generate an HTML img pixel tag for client-side firing."""
        site = base_url or getattr(settings, 'SITE_URL', 'https://yourplatform.com')
        payload = json.dumps({
            'o': offer_id,
            'u': str(user_id) if user_id else '',
            'c': click_token,
        })
        token = base64.urlsafe_b64encode(payload.encode()).decode().rstrip('=')
        url   = f'{site}/api/offer-inventory/pixel/conversion/{token}/'
        return (
            f'<img src="{url}" width="1" height="1" border="0" '
            f'alt="" style="position:absolute;visibility:hidden;" />'
        )

    @staticmethod
    def generate_js_pixel(offer_id: str, user_id=None,
                           click_token: str = '') -> str:
        """Generate async JavaScript pixel snippet."""
        return (
            f'<script type="text/javascript">\n'
            f'(function() {{\n'
            f'  var img = new Image(1,1);\n'
            f'  img.src = \'/api/offer-inventory/pixel/conversion/?'
            f'o={offer_id}&u={user_id}&c={click_token}&ts=\' + Date.now();\n'
            f'  document.body.appendChild(img);\n'
            f'}})();\n'
            f'</script>'
        )

    @staticmethod
    def fire_server_side(conversion_id: str) -> bool:
        """Fire conversion pixel server-to-server."""
        from api.offer_inventory.webhooks.pixel_tracking import PixelTracker
        return PixelTracker.fire(conversion_id)

    @staticmethod
    def decode_pixel_token(token: str) -> dict:
        """Decode and validate a pixel token."""
        try:
            padded  = token + '=' * (4 - len(token) % 4)
            decoded = base64.urlsafe_b64decode(padded).decode()
            return json.loads(decoded)
        except Exception:
            return {}

    @staticmethod
    def batch_fire(conversion_ids: list) -> dict:
        """Fire pixels for multiple conversions."""
        from api.offer_inventory.webhooks.pixel_tracking import PixelTracker
        results = {'fired': 0, 'failed': 0}
        for cid in conversion_ids:
            if PixelTracker.fire(str(cid)):
                results['fired'] += 1
            else:
                results['failed'] += 1
        return results
