# api/offer_inventory/affiliate_advanced/tracking_link_generator.py
"""Tracking Link Generator — Generate signed tracking URLs."""
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


class TrackingLinkGenerator:
    """Generate tracking URLs for offers, SmartLinks, and campaigns."""

    @staticmethod
    def generate(offer_id: str, user_id=None,
                  source: str = '', s1: str = '',
                  s2: str = '', s3: str = '',
                  base_url: str = '') -> str:
        """Generate a full tracking URL for an offer."""
        base   = base_url or getattr(settings, 'SITE_URL', 'https://yourplatform.com')
        params = [f'offer={offer_id}']
        if user_id:  params.append(f'uid={user_id}')
        if source:   params.append(f'src={source}')
        if s1:       params.append(f's1={s1}')
        if s2:       params.append(f's2={s2}')
        if s3:       params.append(f's3={s3}')
        return f'{base}/api/offer-inventory/track/?{"&".join(params)}'

    @staticmethod
    def generate_smartlink(slug: str, user_id=None,
                            source: str = '', base_url: str = '') -> str:
        """Generate SmartLink tracking URL."""
        base   = base_url or getattr(settings, 'SITE_URL', 'https://yourplatform.com')
        params = []
        if user_id: params.append(f'uid={user_id}')
        if source:  params.append(f'src={source}')
        query  = f'?{"&".join(params)}' if params else ''
        return f'{base}/api/offer-inventory/go/{slug}/{query}'

    @staticmethod
    def generate_batch(offer_ids: list, user_id=None) -> list:
        """Generate tracking URLs for multiple offers."""
        return [
            {'offer_id': oid, 'url': TrackingLinkGenerator.generate(oid, user_id)}
            for oid in offer_ids
        ]

    @staticmethod
    def generate_postback_url(network_slug: str = None,
                               base_url: str = '') -> str:
        """Generate S2S postback URL for network configuration."""
        base = base_url or getattr(settings, 'SITE_URL', 'https://yourplatform.com')
        path = f'/api/offer-inventory/postback/{network_slug}/' if network_slug else '/api/offer-inventory/postback/'
        return f'{base}{path}?click_id={{click_id}}&transaction_id={{transaction_id}}&payout={{payout}}'
