"""
conversion_tracking/conversion_pixel.py
─────────────────────────────────────────
Conversion tracking pixel generator.
Generates tracking pixel URLs for advertisers to embed in their
thank-you/confirmation pages for browser-based conversion tracking.
Complements S2S postbacks for extra reliability.
"""
from __future__ import annotations
import logging
import secrets
from django.conf import settings
from ..utils import expand_url_macros

logger = logging.getLogger(__name__)


class ConversionPixel:

    def generate_pixel_url(
        self,
        network_key: str,
        offer_id: str,
        click_id: str = "",
        user_id: str = "",
        payout: str = "0",
        extra_params: dict = None,
    ) -> str:
        """
        Generate a 1×1 pixel URL for conversion tracking.
        Embed in advertiser's thank-you page:
            <img src="{pixel_url}" width="1" height="1">
        """
        base_url = self._get_base_url()
        params = {
            "network": network_key,
            "offer_id": offer_id,
            "click_id": click_id,
            "user_id": user_id,
            "payout": payout,
            "nonce": secrets.token_hex(8),
        }
        if extra_params:
            params.update(extra_params)

        from urllib.parse import urlencode
        qs = urlencode({k: v for k, v in params.items() if v})
        return f"{base_url}/api/postback_engine/pixel/?{qs}"

    def generate_js_tag(self, network_key: str, offer_id: str, click_id: str = "") -> str:
        """Generate a JavaScript conversion tag for embedding in advertiser pages."""
        pixel_url = self.generate_pixel_url(network_key, offer_id, click_id)
        return (
            f'<script>(function(){{'
            f'var img=new Image();img.src="{pixel_url}";'
            f'}})();</script>'
            f'<noscript><img src="{pixel_url}" width="1" height="1"></noscript>'
        )

    def generate_iframe_tag(self, network_key: str, offer_id: str, click_id: str = "") -> str:
        """Generate an iFrame conversion tag."""
        pixel_url = self.generate_pixel_url(network_key, offer_id, click_id)
        return (
            f'<iframe src="{pixel_url}" width="1" height="1" '
            f'frameborder="0" scrolling="no"></iframe>'
        )

    @staticmethod
    def _get_base_url() -> str:
        base = getattr(settings, "BASE_URL", "")
        if not base:
            base = getattr(settings, "SITE_URL", "https://yourdomain.com")
        return base.rstrip("/")


conversion_pixel = ConversionPixel()
