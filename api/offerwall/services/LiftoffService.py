"""
api/offerwall/services/LiftoffService.py

Liftoff (Vungle) offer processor.
Liftoff focuses on mobile gaming CPI offers, 2M+ users/month.
Merged with Vungle in 2021. Strong in gaming vertical.

API Docs: https://support.vungle.com/hc/en-us/sections/360004653551
"""
import hashlib
import hmac
import logging
from decimal import Decimal

from .OfferProcessor import OfferProcessor
from ..constants import (
    PROVIDER_LIFTOFF,
    STATUS_ACTIVE,
    LIFTOFF_API_BASE,
)
from ..exceptions import (
    ProviderAPIException,
    InvalidWebhookSignatureException,
)

logger = logging.getLogger(__name__)


class LiftoffService(OfferProcessor):
    """
    Liftoff (Vungle) offer processor.

    Liftoff uses app_id + api_key for authentication.
    Webhook callbacks signed with HMAC-SHA256.
    Primary focus: mobile gaming app installs + in-app events.
    """

    OFFER_TYPE_MAP = {
        'install':    'app_install',
        'engagement': 'engagement',
        'purchase':   'purchase',
        'event':      'event',
        'other':      'other',
    }

    def __init__(self, provider):
        super().__init__(provider)
        self.api_base   = LIFTOFF_API_BASE
        self.app_id     = provider.app_id
        self.api_key    = provider.api_key
        self.secret_key = provider.secret_key or ''

    # ─────────────────────────────────────────────────────────
    # Offer sync
    # ─────────────────────────────────────────────────────────

    def fetch_offers(self, country: str = 'US', platform: str = 'android', **kwargs):
        """
        Fetch active campaigns from Liftoff/Vungle API.
        GET /api/pub/campaigns?api_key=<key>&app_id=<id>&country=<cc>
        """
        import requests

        params = {
            'api_key':  self.api_key,
            'app_id':   self.app_id,
            'country':  country,
            'platform': platform,
        }

        try:
            resp = requests.get(self.api_base, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            logger.error(f'[LiftoffService] fetch_offers failed: {exc}')
            raise ProviderAPIException(f'Liftoff API error: {exc}')

        campaigns = data.get('campaigns', data.get('data', []))
        return [self._normalize_offer(c) for c in campaigns]

    def _normalize_offer(self, raw: dict) -> dict:
        """Map Liftoff/Vungle campaign fields to internal schema."""
        offer_type = self.OFFER_TYPE_MAP.get(
            raw.get('campaign_type', raw.get('type', 'install')).lower(),
            'app_install')

        return {
            'external_offer_id': str(raw.get('campaign_id', raw.get('id', ''))),
            'title':             raw.get('app_name', raw.get('name', '')),
            'description':       raw.get('description', ''),
            'short_description': raw.get('short_description',
                                         raw.get('description', ''))[:200],
            'offer_type':        offer_type,
            'platform':          raw.get('platform', 'android'),
            'countries':         raw.get('target_countries', []),
            'click_url':         raw.get('click_url', raw.get('tracking_url', '')),
            'tracking_url':      raw.get('impression_url', raw.get('click_url', '')),
            'image_url':         raw.get('icon_url', raw.get('image', '')),
            'thumbnail_url':     raw.get('icon_url', ''),
            'payout':            Decimal(str(raw.get('payout',
                                            raw.get('bid', '0')))),
            'reward_amount':     Decimal(str(raw.get('reward',
                                            raw.get('payout', '0')))),
            'status':            STATUS_ACTIVE if raw.get('status') in
                                     ('active', 'running', 'live') else 'paused',
            'provider_data':     raw,
        }

    # ─────────────────────────────────────────────────────────
    # Webhook signature verification
    # ─────────────────────────────────────────────────────────

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """
        Liftoff HMAC-SHA256 signature on raw body bytes.
        Header: X-Vungle-Signature: <hex>
        """
        if not self.secret_key:
            return True

        expected = hmac.new(
            self.secret_key.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(expected, signature):
            raise InvalidWebhookSignatureException(
                'Liftoff webhook signature mismatch')
        return True

    # ─────────────────────────────────────────────────────────
    # Conversion parsing
    # ─────────────────────────────────────────────────────────

    def parse_webhook(self, request_data: dict) -> dict:
        """
        Parse Liftoff/Vungle postback payload.

        Fields:
          - ext_campaign_id: campaign/offer id
          - ext_user_id: our user id (passed via tracking link sub parameter)
          - transaction_id: unique conversion ID
          - payout: USD payout
          - event_type: 'install' | 'event' | 'purchase'
          - timestamp: epoch ms
        """
        return {
            'user_id':       str(request_data.get('ext_user_id',
                                  request_data.get('user_id', ''))),
            'offer_id':      str(request_data.get('ext_campaign_id',
                                  request_data.get('campaign_id', ''))),
            'conversion_id': str(request_data.get('transaction_id',
                                  request_data.get('idfa', ''))),
            'payout_amount': Decimal(str(request_data.get('payout', '0'))),
            'reward_amount': Decimal(str(request_data.get('reward',
                                          request_data.get('payout', '0')))),
            'status':        'approved',  # Liftoff sends only final approved events
            'provider_data': request_data,
            'provider_type': PROVIDER_LIFTOFF,
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
