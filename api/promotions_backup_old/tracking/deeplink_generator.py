# api/promotions/tracking/deeplink_generator.py
# Deep Link Generator — Android App Links + iOS Universal Links + short URLs
import hashlib, logging
from urllib.parse import urlencode, urlparse, urlunparse, parse_qs
from django.conf import settings
from django.core.cache import cache
logger  = logging.getLogger('tracking.deeplink')
SITE_URL = getattr(settings, 'SITE_URL', 'https://example.com')

class DeepLinkGenerator:
    def generate(self, campaign_id: int, target_url: str, user_id: int = None,
                 platform: str = 'android', fallback_url: str = None, extra: dict = None) -> dict:
        params = {'c': campaign_id, 'u': user_id or 0,
                  'utm_source': 'promotions', 'utm_campaign': str(campaign_id)}
        if extra:
            params.update(extra)
        tracked   = self._add_params(target_url, params)
        short_code = hashlib.md5(f'{tracked}{campaign_id}'.encode()).hexdigest()[:8]
        cache.set(f'track:dl:{short_code}', tracked, timeout=86400*90)

        if platform == 'android':
            deeplink = f'intent:{tracked}#Intent;scheme=https;end'
        else:
            deeplink = tracked   # iOS Universal Link

        return {'deeplink': deeplink, 'short_url': f'{SITE_URL}/l/{short_code}',
                'tracked_url': tracked, 'fallback_url': fallback_url or target_url}

    def resolve(self, code: str) -> str | None:
        return cache.get(f'track:dl:{code}')

    def _add_params(self, url: str, params: dict) -> str:
        p = urlparse(url)
        q = parse_qs(p.query)
        q.update({k: [str(v)] for k, v in params.items()})
        new_q = urlencode({k: v[0] for k, v in q.items()})
        return urlunparse(p._replace(query=new_q))
