"""
api/offerwall/services/FyberService.py

Fyber (Digital Turbine) offer processor.
Fyber specialises in app install offers, 3M+ users/month.
Acquired by Digital Turbine in 2021; API base remains the same.

API Docs: https://developer.fyber.com/hc/en-us/articles/360012445957
"""
import hashlib
import hmac
import logging
from decimal import Decimal

from .OfferProcessor import OfferProcessor
from ..constants import (
    PROVIDER_FYBER,
    STATUS_ACTIVE,
    FYBER_API_BASE,
)
from ..exceptions import (
    ProviderAPIException,
    InvalidWebhookSignatureException,
)

logger = logging.getLogger(__name__)


class FyberService(OfferProcessor):
    """
    Fyber (Digital Turbine) offer processor.

    Fyber uses app_id + security_token for API auth.
    Webhook postbacks signed with SHA1 hash.
    Primary offer type: app installs (CPI).
    """

    OFFER_TYPE_MAP = {
        'cpi':     'app_install',
        'cpa':     'signup',
        'cpe':     'engagement',
        'survey':  'survey',
        'other':   'other',
    }

    def __init__(self, provider):
        super().__init__(provider)
        self.api_base        = FYBER_API_BASE
        self.app_id          = provider.app_id
        self.security_token  = provider.secret_key or ''
        self.publisher_id    = provider.publisher_id
        self.api_key         = provider.api_key

    # ─────────────────────────────────────────────────────────
    # Offer sync
    # ─────────────────────────────────────────────────────────

    def fetch_offers(self, uid: str = 'test_user', device_id: str = '',
                     locale: str = 'en', ip: str = '0.0.0.0', **kwargs):
        """
        Fetch offers from Fyber offerwall API.
        GET /feed/v1?appid=<app_id>&uid=<uid>&ip=<ip>&locale=<locale>&hashkey=<hash>
        hashkey = SHA1(appid + ip + locale + uid + security_token)
        """
        import requests

        hashkey = self._build_hashkey(uid, ip, locale)
        params  = {
            'appid':    self.app_id,
            'uid':      uid,
            'ip':       ip,
            'locale':   locale,
            'hashkey':  hashkey,
            'os':       kwargs.get('os', 'android'),
            'page':     kwargs.get('page', 1),
        }

        try:
            resp = requests.get(self.api_base, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            logger.error(f'[FyberService] fetch_offers failed: {exc}')
            raise ProviderAPIException(f'Fyber API error: {exc}')

        offers = data.get('offers', [])
        return [self._normalize_offer(o) for o in offers]

    def _build_hashkey(self, uid: str, ip: str, locale: str) -> str:
        """
        Build Fyber API hashkey.
        SHA1(appid + ip + locale + uid + security_token)
        """
        raw = f"{self.app_id}{ip}{locale}{uid}{self.security_token}"
        return hashlib.sha1(raw.encode()).hexdigest()

    def _normalize_offer(self, raw: dict) -> dict:
        """Map Fyber offer fields to internal schema."""
        return {
            'external_offer_id': str(raw.get('offerId', '')),
            'title':             raw.get('title', ''),
            'description':       raw.get('teaser', ''),
            'short_description': raw.get('teaser', '')[:200],
            'offer_type':        self.OFFER_TYPE_MAP.get(
                                     raw.get('type', {}).get('gaid', '').lower(),
                                     'app_install'),
            'platform':          raw.get('os', 'android'),
            'countries':         [],
            'click_url':         raw.get('link', ''),
            'tracking_url':      raw.get('link', ''),
            'image_url':         raw.get('thumbnail', {}).get('lowres', ''),
            'thumbnail_url':     raw.get('thumbnail', {}).get('lowres', ''),
            'payout':            Decimal(str(raw.get('payout', {}).get('gross', '0'))),
            'reward_amount':     Decimal(str(raw.get('payout', {}).get('net', '0'))),
            'status':            STATUS_ACTIVE,
            'provider_data':     raw,
        }

    # ─────────────────────────────────────────────────────────
    # Webhook signature verification
    # ─────────────────────────────────────────────────────────

    def verify_webhook_signature(self, data: dict, signature: str) -> bool:
        """
        Fyber callback signature verification.
        Signature = SHA1(uid + ':' + sid + ':' + security_token)
        """
        if not self.security_token:
            return True

        uid = str(data.get('uid', ''))
        sid = str(data.get('sid', ''))
        raw = f"{uid}:{sid}:{self.security_token}"
        expected = hashlib.sha1(raw.encode()).hexdigest()

        if not hmac.compare_digest(expected.lower(), signature.lower()):
            raise InvalidWebhookSignatureException(
                f'Fyber signature mismatch for uid={uid}')
        return True

    # ─────────────────────────────────────────────────────────
    # Conversion parsing
    # ─────────────────────────────────────────────────────────

    def parse_webhook(self, request_data: dict) -> dict:
        """
        Parse Fyber callback (server-side reward callback).

        Fyber callback params:
          - uid: our user identifier
          - sid: unique session/conversion ID
          - pub0..pub9: custom sub-parameters (we use pub0=offer_id)
          - virtualCurrency: reward amount
          - grossAmount: USD payout to publisher
          - netAmount: net payout
          - orderId: unique transaction ID
          - _hash: SHA1 signature
        """
        signature = request_data.get('_hash', '')
        if signature:
            self.verify_webhook_signature(request_data, signature)

        return {
            'user_id':       str(request_data.get('uid', '')),
            'offer_id':      str(request_data.get('pub0',
                                  request_data.get('offerId', ''))),
            'conversion_id': str(request_data.get('orderId',
                                  request_data.get('sid', ''))),
            'payout_amount': Decimal(str(request_data.get('grossAmount', '0'))),
            'reward_amount': Decimal(str(request_data.get('virtualCurrency', '0'))),
            'status':        'approved',  # Fyber only sends approved callbacks
            'provider_data': request_data,
            'provider_type': PROVIDER_FYBER,
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
