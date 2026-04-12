# api/offer_inventory/optimization_scale/static_file_cdn.py
"""Static File CDN — CDN URL management for offer images and static assets."""
import logging
from django.core.cache import cache

logger = logging.getLogger(__name__)


class StaticFileCDN:
    """CDN URL rewriting for static assets and offer images."""

    _cdn_base  = ''
    _use_cdn   = False
    _setup_done = False

    @classmethod
    def _setup(cls):
        if cls._setup_done:
            return
        from django.conf import settings
        cls._cdn_base   = getattr(settings, 'CDN_BASE_URL', '').rstrip('/')
        cls._use_cdn    = bool(cls._cdn_base)
        cls._setup_done = True

    @classmethod
    def url(cls, path: str) -> str:
        """Convert a relative path to CDN URL."""
        cls._setup()
        if not path:
            return path
        if not cls._use_cdn:
            return path
        if path.startswith(('http://', 'https://')):
            return path
        return f'{cls._cdn_base}/{path.lstrip("/")}'

    @classmethod
    def offer_image_url(cls, offer) -> str:
        """Get CDN URL for an offer image."""
        return cls.url(offer.image_url or '')

    @classmethod
    def rewrite_offer_list(cls, offers: list) -> list:
        """Rewrite all image URLs in an offer list to CDN URLs."""
        cls._setup()
        if not cls._use_cdn:
            return offers
        for offer in offers:
            if hasattr(offer, 'image_url') and offer.image_url:
                offer.image_url = cls.url(offer.image_url)
        return offers

    @classmethod
    def purge(cls, path: str) -> bool:
        """Purge CDN cache for a specific URL (Cloudflare)."""
        from django.conf import settings
        zone_id = getattr(settings, 'CLOUDFLARE_ZONE_ID', '')
        token   = getattr(settings, 'CLOUDFLARE_API_TOKEN', '')
        if not all([zone_id, token]):
            return False
        try:
            import requests
            full_url = cls.url(path)
            resp = requests.post(
                f'https://api.cloudflare.com/client/v4/zones/{zone_id}/purge_cache',
                headers={'Authorization': f'Bearer {token}'},
                json={'files': [full_url]},
                timeout=5,
            )
            return resp.ok
        except Exception as e:
            logger.error(f'CDN purge error: {e}')
            return False

    @classmethod
    def get_cdn_status(cls) -> dict:
        cls._setup()
        return {
            'cdn_enabled' : cls._use_cdn,
            'cdn_base_url': cls._cdn_base or '(none)',
        }
