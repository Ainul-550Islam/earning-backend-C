"""
api/offerwall/services/AppLiftService.py

AppLift offer processor.
AppLift is strong in EU/APAC markets with 2M+ users/month.
Specialises in performance marketing for mobile apps.

API Docs: https://tracking.applift.com/aff_lsr (HasOffers/TUNE based)
"""
import hashlib
import hmac
import logging
from decimal import Decimal

from .OfferProcessor import OfferProcessor
from ..constants import (
    PROVIDER_APPLIFT,
    STATUS_ACTIVE,
    APPLIFT_API_BASE,
)
from ..exceptions import (
    ProviderAPIException,
    InvalidWebhookSignatureException,
)

logger = logging.getLogger(__name__)


class AppLiftService(OfferProcessor):
    """
    AppLift offer processor.

    AppLift runs on HasOffers (TUNE) platform.
    Uses api_key + publisher_id for auth.
    Webhook postbacks can include an optional md5 hash.
    """

    OFFER_TYPE_MAP = {
        'install':   'app_install',
        'cpi':       'app_install',
        'cpa':       'signup',
        'video':     'video',
        'engage':    'engagement',
        'other':     'other',
    }

    def __init__(self, provider):
        super().__init__(provider)
        self.api_base     = APPLIFT_API_BASE
        self.api_key      = provider.api_key
        self.publisher_id = provider.publisher_id
        self.secret_key   = provider.secret_key or ''
        self.network_id   = provider.app_id or ''

    # ─────────────────────────────────────────────────────────
    # Offer sync
    # ─────────────────────────────────────────────────────────

    def fetch_offers(self, country: str = 'US', page: int = 1, **kwargs):
        """
        Fetch offers from AppLift (HasOffers) affiliate API.
        GET /aff_lsr?api_key=<key>&affiliate_id=<pub_id>&country=<cc>
        """
        import requests

        params = {
            'api_key':      self.api_key,
            'affiliate_id': self.publisher_id,
            'country':      country,
            'page':         page,
            'status':       'active',
        }

        try:
            resp = requests.get(self.api_base, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            logger.error(f'[AppLiftService] fetch_offers failed: {exc}')
            raise ProviderAPIException(f'AppLift API error: {exc}')

        # HasOffers response format: {"request": {...}, "data": {"data": [...]}}
        offers = (data.get('data', {}).get('data', [])
                  if isinstance(data.get('data'), dict)
                  else data.get('data', []))
        return [self._normalize_offer(o) for o in offers]

    def _normalize_offer(self, raw: dict) -> dict:
        """Map AppLift/HasOffers offer fields to internal schema."""
        offer_type = self.OFFER_TYPE_MAP.get(
            raw.get('vertical', raw.get('type', 'cpi')).lower(),
            'app_install')

        return {
            'external_offer_id': str(raw.get('id', raw.get('offer_id', ''))),
            'title':             raw.get('name', ''),
            'description':       raw.get('description', ''),
            'short_description': raw.get('preview_url', raw.get('description', ''))[:200],
            'offer_type':        offer_type,
            'platform':          raw.get('platforms', ['android'])[0]
                                 if isinstance(raw.get('platforms'), list)
                                 else raw.get('platforms', 'android'),
            'countries':         raw.get('countries', []),
            'click_url':         raw.get('preview_url', raw.get('click_url', '')),
            'tracking_url':      raw.get('default_payout_url', raw.get('click_url', '')),
            'image_url':         raw.get('thumbnail_url', ''),
            'thumbnail_url':     raw.get('thumbnail_url', ''),
            'payout':            Decimal(str(raw.get('payout', {}).get('amount', '0'))
                                        if isinstance(raw.get('payout'), dict)
                                        else str(raw.get('payout', '0'))),
            'reward_amount':     Decimal(str(raw.get('payout', {}).get('amount', '0'))
                                        if isinstance(raw.get('payout'), dict)
                                        else str(raw.get('payout', '0'))),
            'status':            STATUS_ACTIVE
                                 if raw.get('status') in ('active', 'Active') else 'paused',
            'provider_data':     raw,
        }

    # ─────────────────────────────────────────────────────────
    # Webhook signature verification
    # ─────────────────────────────────────────────────────────

    def verify_webhook_signature(self, data: dict, signature: str) -> bool:
        """
        AppLift (HasOffers) optional MD5 verification.
        Signature = MD5(secret_key + transaction_id + payout)
        """
        if not self.secret_key:
            return True

        tid    = str(data.get('transaction_id', data.get('aff_click_id', '')))
        payout = str(data.get('payout', data.get('amount', '0')))
        raw    = f"{self.secret_key}{tid}{payout}"
        expected = hashlib.md5(raw.encode()).hexdigest()

        if not hmac.compare_digest(expected.lower(), signature.lower()):
            raise InvalidWebhookSignatureException(
                f'AppLift signature mismatch for tid={tid}')
        return True

    # ─────────────────────────────────────────────────────────
    # Conversion parsing
    # ─────────────────────────────────────────────────────────

    def parse_webhook(self, request_data: dict) -> dict:
        """
        Parse AppLift (HasOffers) postback payload.

        HasOffers postback fields:
          - aff_sub: our user_id (set in tracking link as sub-parameter)
          - aff_sub2: offer_id
          - transaction_id / aff_click_id: unique conversion ID
          - payout / amount: USD payout
          - status: 'approved' | 'pending' | 'rejected'
          - security_token: optional MD5 hash
        """
        signature = request_data.get('security_token',
                     request_data.get('md5', ''))
        if signature:
            self.verify_webhook_signature(request_data, signature)

        status_raw = request_data.get('status', 'pending')
        status     = {
            'approved': 'approved',
            'pending':  'pending',
            'rejected': 'rejected',
            'reversed': 'chargeback',
        }.get(str(status_raw).lower(), 'pending')

        return {
            'user_id':       str(request_data.get('aff_sub',
                                  request_data.get('user_id', ''))),
            'offer_id':      str(request_data.get('aff_sub2',
                                  request_data.get('offer_id', ''))),
            'conversion_id': str(request_data.get('transaction_id',
                                  request_data.get('aff_click_id', ''))),
            'payout_amount': Decimal(str(request_data.get('payout',
                                          request_data.get('amount', '0')))),
            'reward_amount': Decimal(str(request_data.get('payout',
                                          request_data.get('amount', '0')))),
            'status':        status,
            'provider_data': request_data,
            'provider_type': PROVIDER_APPLIFT,
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
