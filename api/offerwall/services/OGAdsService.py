"""
api/offerwall/services/OGAdsService.py

OGAds offer processor.
OGAds is the largest mobile content locker & CPA network, 8M+ users/month.
Supports: app installs, content lockers, banner offers, video offers.

API Docs: https://ogads.com/#!/api
"""
import hashlib
import hmac
import logging
from decimal import Decimal

from .OfferProcessor import OfferProcessor
from ..constants import (
    PROVIDER_OGADS,
    STATUS_ACTIVE,
    OGADS_API_BASE,
)
from ..exceptions import (
    ProviderAPIException,
    InvalidWebhookSignatureException,
)

logger = logging.getLogger(__name__)


class OGAdsService(OfferProcessor):
    """
    OGAds offer processor.

    OGAds uses API key + pub_id for authentication.
    Webhook postbacks include MD5 signature.
    Known for large banner + video offer inventory.
    """

    OFFER_TYPE_MAP = {
        'cpi':     'app_install',
        'cpa':     'signup',
        'survey':  'survey',
        'video':   'video',
        'content': 'content_lock',
        'other':   'other',
    }

    def __init__(self, provider):
        super().__init__(provider)
        self.api_base     = OGADS_API_BASE
        self.pub_id       = provider.publisher_id
        self.api_key      = provider.api_key
        self.secret_key   = provider.secret_key or ''

    # ─────────────────────────────────────────────────────────
    # Offer sync
    # ─────────────────────────────────────────────────────────

    def fetch_offers(self, country: str = 'US', os: str = 'android', **kwargs):
        """
        Fetch offers from OGAds API.
        GET /api/feed?api_key=<key>&pub_id=<id>&country=<cc>&os=<platform>
        """
        import requests

        url    = f"{self.api_base}/feed"
        params = {
            'api_key': self.api_key,
            'pub_id':  self.pub_id,
            'country': country,
            'os':      os,
        }

        try:
            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            logger.error(f'[OGAdsService] fetch_offers failed: {exc}')
            raise ProviderAPIException(f'OGAds API error: {exc}')

        offers = data.get('data', data.get('offers', []))
        return [self._normalize_offer(o) for o in offers]

    def _normalize_offer(self, raw: dict) -> dict:
        """Map OGAds offer fields to internal schema."""
        offer_type = self.OFFER_TYPE_MAP.get(
            raw.get('type', raw.get('category', '')).lower(), 'other')
        return {
            'external_offer_id': str(raw.get('id', '')),
            'title':             raw.get('name', raw.get('title', '')),
            'description':       raw.get('description', ''),
            'short_description': raw.get('short_description',
                                         raw.get('description', ''))[:200],
            'offer_type':        offer_type,
            'platform':          raw.get('os', 'all'),
            'countries':         raw.get('countries', [raw.get('country', 'US')]),
            'click_url':         raw.get('link', raw.get('offer_url', '')),
            'tracking_url':      raw.get('tracking_link', raw.get('link', '')),
            'image_url':         raw.get('image', raw.get('icon', '')),
            'thumbnail_url':     raw.get('thumbnail', raw.get('image', '')),
            'payout':            Decimal(str(raw.get('payout', '0'))),
            'reward_amount':     Decimal(str(raw.get('points',
                                            raw.get('payout', '0')))),
            'daily_cap':         int(raw.get('daily_cap', 0)),
            'total_cap':         int(raw.get('total_conversions', 0)),
            'status':            STATUS_ACTIVE,
            'provider_data':     raw,
        }

    # ─────────────────────────────────────────────────────────
    # Webhook signature verification
    # ─────────────────────────────────────────────────────────

    def verify_webhook_signature(self, data: dict, signature: str) -> bool:
        """
        OGAds MD5 signature verification.
        Signature = MD5(api_key + ':' + transaction_id)
        """
        if not self.secret_key and not self.api_key:
            return True

        transaction_id = str(data.get('transaction_id', data.get('tid', '')))
        key            = self.secret_key or self.api_key
        expected       = hashlib.md5(
            f"{key}:{transaction_id}".encode()).hexdigest()

        if not hmac.compare_digest(expected.lower(), signature.lower()):
            raise InvalidWebhookSignatureException(
                f'OGAds signature mismatch for tid={transaction_id}')
        return True

    # ─────────────────────────────────────────────────────────
    # Conversion parsing
    # ─────────────────────────────────────────────────────────

    def parse_webhook(self, request_data: dict) -> dict:
        """
        Parse OGAds postback payload.

        OGAds postback fields:
          - sub1: our user_id (set when creating tracking link)
          - aff_sub: offer id
          - transaction_id / tid: unique conversion ID
          - payout: USD payout to publisher
          - status: 'approved' | 'pending' | 'reversed'
          - hash: MD5 signature
        """
        signature = request_data.get('hash', request_data.get('sig', ''))
        if signature:
            self.verify_webhook_signature(request_data, signature)

        return {
            'user_id':       str(request_data.get('sub1',
                                  request_data.get('aff_sub2',
                                  request_data.get('user_id', '')))),
            'offer_id':      str(request_data.get('aff_sub',
                                  request_data.get('offer_id', ''))),
            'conversion_id': str(request_data.get('transaction_id',
                                  request_data.get('tid', ''))),
            'payout_amount': Decimal(str(request_data.get('payout', '0'))),
            'reward_amount': Decimal(str(request_data.get('payout', '0'))),
            'status':        request_data.get('status', 'pending'),
            'provider_data': request_data,
            'provider_type': PROVIDER_OGADS,
        }

    # ── Abstract method implementations ───────────────────────────────────────

    def parse_offer_data(self, raw_data: dict) -> dict:
        """Delegate to _normalize_offer."""
        return self._normalize_offer(raw_data)

    def verify_postback(self, data: dict) -> bool:
        """Verify postback signature if secret_key is configured."""
        sig = data.get('signature', data.get('hash', data.get('_hash', '')))
        if sig and self.secret_key:
            try:
                self.verify_webhook_signature(data if not isinstance(data, (bytes,)) else data, sig)
                return True
            except Exception:
                return False
        return True   # no secret configured → accept

    def build_click_url(self, offer, user) -> str:
        """Build a tracking click URL embedding user sub-parameters."""
        base = getattr(offer, 'click_url', '') or getattr(offer, 'tracking_url', '')
        if not base:
            return ''
        sep = '&' if '?' in base else '?'
        return f"{base}{sep}sub1={user.pk}&sub2={offer.external_offer_id}"
