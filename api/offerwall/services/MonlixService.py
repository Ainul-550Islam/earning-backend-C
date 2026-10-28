"""
api/offerwall/services/MonlixService.py

Monlix offer processor.
Monlix is one of the largest CPA networks in MENA/LatAm, serving 5M+ users/month.
Supports: app installs, surveys, video views, signups.

API Docs: https://publishers.monlix.com/api/docs
"""
import hashlib
import hmac
import logging
from decimal import Decimal

from .OfferProcessor import OfferProcessor
from ..constants import (
    PROVIDER_MONLIX,
    STATUS_ACTIVE,
    MONLIX_API_BASE,
)
from ..exceptions import (
    ProviderAPIException,
    InvalidWebhookSignatureException,
)

logger = logging.getLogger(__name__)


class MonlixService(OfferProcessor):
    """
    Monlix offer processor.

    Monlix API uses publisher_id + api_key for authentication.
    Webhook postbacks include HMAC-SHA256 signature using secret_key.
    """

    OFFER_TYPE_MAP = {
        'app':     'app_install',
        'survey':  'survey',
        'video':   'video',
        'signup':  'signup',
        'trial':   'trial',
        'other':   'other',
    }

    def __init__(self, provider):
        super().__init__(provider)
        self.api_base      = MONLIX_API_BASE
        self.publisher_id  = provider.publisher_id
        self.api_key       = provider.api_key
        self.secret_key    = provider.secret_key or ''
        self.app_id        = provider.app_id

    # ─────────────────────────────────────────────────────────
    # Offer sync
    # ─────────────────────────────────────────────────────────

    def fetch_offers(self, country: str = 'US', device: str = 'mobile', **kwargs):
        """
        Fetch active offers from Monlix API.
        GET /api/offers?publisher_id=<id>&api_key=<key>&country=<cc>&device=<type>
        Returns JSON list of offer objects.
        """
        import requests

        url    = f"{self.api_base}/offers"
        params = {
            'publisher_id': self.publisher_id,
            'api_key':      self.api_key,
            'country':      country,
            'device':       device,
        }

        try:
            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            logger.error(f'[MonlixService] fetch_offers failed: {exc}')
            raise ProviderAPIException(f'Monlix API error: {exc}')

        offers = data.get('offers', data) if isinstance(data, dict) else data
        return [self._normalize_offer(o) for o in offers]

    def _normalize_offer(self, raw: dict) -> dict:
        """Map Monlix offer fields to internal schema."""
        return {
            'external_offer_id': str(raw.get('id', '')),
            'title':             raw.get('name', ''),
            'description':       raw.get('description', ''),
            'short_description': raw.get('short_description', raw.get('description', ''))[:200],
            'offer_type':        self.OFFER_TYPE_MAP.get(raw.get('type', ''), 'other'),
            'platform':          raw.get('device', 'all'),
            'countries':         raw.get('countries', []),
            'click_url':         raw.get('link', ''),
            'tracking_url':      raw.get('tracking_url', raw.get('link', '')),
            'image_url':         raw.get('image', ''),
            'thumbnail_url':     raw.get('thumbnail', raw.get('image', '')),
            'payout':            Decimal(str(raw.get('payout', '0'))),
            'reward_amount':     Decimal(str(raw.get('reward', raw.get('payout', '0')))),
            'daily_cap':         int(raw.get('daily_cap', 0)),
            'total_cap':         int(raw.get('total_cap', 0)),
            'status':            STATUS_ACTIVE if raw.get('status') == 'active' else 'paused',
            'provider_data':     raw,
        }

    # ─────────────────────────────────────────────────────────
    # Webhook signature verification
    # ─────────────────────────────────────────────────────────

    def verify_webhook_signature(self, data: dict, signature: str) -> bool:
        """
        Monlix HMAC-SHA256 signature verification.
        Signature = HMAC_SHA256(secret_key, user_id + ':' + offer_id + ':' + payout)
        """
        if not self.secret_key:
            return True  # If no secret configured, skip verification

        user_id  = str(data.get('user_id', ''))
        offer_id = str(data.get('offer_id', ''))
        payout   = str(data.get('payout', ''))

        message  = f"{user_id}:{offer_id}:{payout}"
        expected = hmac.new(
            self.secret_key.encode(),
            message.encode(),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(expected, signature):
            raise InvalidWebhookSignatureException(
                f'Monlix webhook signature mismatch for offer={offer_id}')
        return True

    # ─────────────────────────────────────────────────────────
    # Conversion parsing
    # ─────────────────────────────────────────────────────────

    def parse_webhook(self, request_data: dict) -> dict:
        """
        Parse Monlix postback payload into internal conversion dict.

        Monlix postback fields:
          - user_id: our sub_id (user pk)
          - offer_id: Monlix offer id
          - transaction_id: unique conversion ID
          - payout: USD payout to publisher
          - reward: currency reward to user
          - status: 'approved' | 'pending' | 'rejected'
          - signature: HMAC-SHA256 hash
        """
        signature = request_data.get('signature', '')
        if signature:
            self.verify_webhook_signature(request_data, signature)

        return {
            'user_id':            str(request_data.get('user_id', '')),
            'offer_id':           str(request_data.get('offer_id', '')),
            'conversion_id':      str(request_data.get('transaction_id', '')),
            'payout_amount':      Decimal(str(request_data.get('payout', '0'))),
            'reward_amount':      Decimal(str(request_data.get('reward',
                                            request_data.get('payout', '0')))),
            'status':             request_data.get('status', 'pending'),
            'provider_data':      request_data,
            'provider_type':      PROVIDER_MONLIX,
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
