"""
api/offerwall/services/survey/SurveyProviderService.py

Native survey provider integrations:
  - CPXResearchService  (CPX Research)
  - BitLabsService      (BitLabs)
  - PollfishService     (Pollfish)

All inherit from BaseSurveyService which defines the common interface.

Usage::

    provider = OfferProvider.objects.get(provider_type='cpx')
    svc = SurveyProviderFactory.create(provider)
    surveys = svc.fetch_surveys(user)
    click_url = svc.build_survey_url(survey, user)
    ok = svc.verify_postback(request.data)
"""
import hashlib
import hmac
import logging
import uuid
from decimal import Decimal
from urllib.parse import urlencode

import requests

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 15  # seconds


# ─────────────────────────────────────────────────────────────
# Base class
# ─────────────────────────────────────────────────────────────

class BaseSurveyService:
    """Common interface for all survey providers."""

    provider_type = 'unknown'

    def __init__(self, provider):
        self.provider = provider
        self.api_key    = getattr(provider, 'api_key',    '') or ''
        self.api_secret = getattr(provider, 'api_secret', '') or ''
        self.app_id     = getattr(provider, 'app_id',     '') or ''
        self.session    = requests.Session()
        self.session.timeout = REQUEST_TIMEOUT

    # ── Must override ────────────────────────────────────────

    def fetch_surveys(self, user=None, country='US', language='en', **kwargs) -> list:
        """Return list of survey dicts: {id, title, loi, payout, url}"""
        raise NotImplementedError

    def build_survey_url(self, survey: dict, user) -> str:
        """Return the survey click URL for `user`."""
        raise NotImplementedError

    def verify_postback(self, data: dict) -> bool:
        """Verify incoming postback signature. Return True if valid."""
        raise NotImplementedError

    def parse_postback(self, data: dict) -> dict:
        """Parse postback → canonical dict: {user_id, survey_id, payout, status}"""
        raise NotImplementedError

    # ── Helpers ──────────────────────────────────────────────

    def _hmac_sha1(self, key: str, message: str) -> str:
        return hmac.new(key.encode(), message.encode(), hashlib.sha1).hexdigest()

    def _hmac_sha256(self, key: str, message: str) -> str:
        return hmac.new(key.encode(), message.encode(), hashlib.sha256).hexdigest()

    def _safe_decimal(self, value, default=Decimal('0')) -> Decimal:
        try:
            return Decimal(str(value))
        except Exception:
            return default


# ─────────────────────────────────────────────────────────────
# CPX Research
# ─────────────────────────────────────────────────────────────

class CPXResearchService(BaseSurveyService):
    """
    CPX Research survey integration.
    Docs: https://developer.cpx-research.com/
    """

    provider_type = 'cpx'
    BASE_URL      = 'https://live-api.cpx-research.com/api/get-surveys.php'
    WIDGET_URL    = 'https://cint.com/surveys/'

    def fetch_surveys(self, user=None, country='US', language='en', **kw) -> list:
        params = {
            'app_id':      self.app_id,
            'ext_user_id': str(user.id) if user else 'anonymous',
            'ip_user':     kw.get('ip', ''),
            'country':     country,
            'language':    language,
            'output_method': 'api',
        }
        try:
            resp = self.session.get(self.BASE_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
            surveys = data.get('status', {}).get('surveys', [])
            return [self._normalise(s) for s in surveys]
        except Exception as e:
            logger.error(f'[CPX] fetch_surveys failed: {e}')
            return []

    def _normalise(self, raw: dict) -> dict:
        return {
            'id':             raw.get('id', ''),
            'title':          raw.get('survey_name', 'Survey'),
            'loi':            int(raw.get('loi', 5)),        # minutes
            'payout':         self._safe_decimal(raw.get('payout_publisher', 0)),
            'reward':         self._safe_decimal(raw.get('payout_user', 0)),
            'currency':       raw.get('currency_name_singular', 'Points'),
            'ir':             float(raw.get('ir', 50)),       # incidence rate
            'provider':       'cpx',
            'raw':            raw,
        }

    def build_survey_url(self, survey: dict, user) -> str:
        params = {
            'app_id':      self.app_id,
            'ext_user_id': str(user.id),
            'survey_id':   survey['id'],
        }
        return f'https://live.cpx-research.com/index.php?{urlencode(params)}'

    def verify_postback(self, data: dict) -> bool:
        """CPX sends hash=MD5(app_id + subid + secret)."""
        try:
            import hashlib
            expected = hashlib.md5(
                f"{self.app_id}{data.get('subid', '')}{self.api_secret}".encode()
            ).hexdigest()
            return hmac.compare_digest(expected, data.get('hash', ''))
        except Exception:
            return False

    def parse_postback(self, data: dict) -> dict:
        return {
            'user_id':   data.get('subid'),
            'survey_id': data.get('survey_id'),
            'payout':    self._safe_decimal(data.get('payout', 0)),
            'status':    'approved' if data.get('status') == '1' else 'rejected',
            'tx_id':     data.get('transaction_id', ''),
        }


# ─────────────────────────────────────────────────────────────
# BitLabs
# ─────────────────────────────────────────────────────────────

class BitLabsService(BaseSurveyService):
    """
    BitLabs survey integration.
    Docs: https://developer.bitlabs.ai/
    """

    provider_type = 'bitlabs'
    API_BASE      = 'https://api.bitlabs.ai/v2'
    SDK_URL       = 'https://web.bitlabs.ai'

    def fetch_surveys(self, user=None, country='US', language='en', **kw) -> list:
        headers = {'X-Api-Token': self.api_key,
                   'X-User-Id':   str(user.id) if user else 'anonymous'}
        try:
            resp = self.session.get(
                f'{self.API_BASE}/client/surveys',
                headers=headers,
                params={'country': country, 'language': language},
            )
            resp.raise_for_status()
            data = resp.json()
            return [self._normalise(s) for s in data.get('data', {}).get('surveys', [])]
        except Exception as e:
            logger.error(f'[BitLabs] fetch_surveys failed: {e}')
            return []

    def _normalise(self, raw: dict) -> dict:
        return {
            'id':       raw.get('id', ''),
            'title':    raw.get('category', {}).get('name', 'Survey'),
            'loi':      int(raw.get('loi', 5)),
            'payout':   self._safe_decimal(raw.get('value', 0)),
            'reward':   self._safe_decimal(raw.get('cpi', 0)),
            'currency': 'USD',
            'ir':       float(raw.get('rating', 50)),
            'provider': 'bitlabs',
            'raw':      raw,
        }

    def build_survey_url(self, survey: dict, user) -> str:
        return (f'{self.SDK_URL}?token={self.api_key}'
                f'&uid={user.id}&survey_id={survey["id"]}')

    def verify_postback(self, data: dict) -> bool:
        """BitLabs HMAC-SHA256 on sorted query string."""
        try:
            incoming_sig = data.pop('signature', '')
            sorted_qs    = urlencode(sorted(data.items()))
            expected     = self._hmac_sha256(self.api_secret, sorted_qs)
            return hmac.compare_digest(expected, incoming_sig)
        except Exception:
            return False

    def parse_postback(self, data: dict) -> dict:
        return {
            'user_id':   data.get('uid'),
            'survey_id': data.get('survey_id'),
            'payout':    self._safe_decimal(data.get('reward', 0)),
            'status':    'approved',
            'tx_id':     data.get('transaction_id', str(uuid.uuid4())),
        }


# ─────────────────────────────────────────────────────────────
# Pollfish
# ─────────────────────────────────────────────────────────────

class PollfishService(BaseSurveyService):
    """
    Pollfish survey integration.
    Docs: https://www.pollfish.com/docs/api-documentation
    """

    provider_type = 'pollfish'
    API_BASE      = 'https://api.pollfish.com/v2'

    def fetch_surveys(self, user=None, country='US', language='en', **kw) -> list:
        """Pollfish is SDK-driven; surveys are delivered client-side."""
        # Return SDK initialisation config rather than a list
        return [{
            'id':       'sdk',
            'title':    'Pollfish surveys',
            'loi':      5,
            'payout':   Decimal('0'),
            'reward':   Decimal('0'),
            'currency': 'Points',
            'ir':       60.0,
            'provider': 'pollfish',
            'sdk_config': {
                'api_key':   self.api_key,
                'user_id':   str(user.id) if user else '',
                'country':   country,
                'language':  language,
            },
        }]

    def build_survey_url(self, survey: dict, user) -> str:
        return (f'https://wss.pollfish.com/v2/device/register/true?'
                f'api_key={self.api_key}&device_id={user.id}')

    def verify_postback(self, data: dict) -> bool:
        """Pollfish HMAC-SHA1 of 'CPA+user_id+api_key' joined by ':'. """
        try:
            sig      = data.get('signature', '')
            message  = (f"{data.get('cpa', '')}:"
                        f"{data.get('user_id', '')}:"
                        f"{self.api_key}")
            expected = self._hmac_sha1(self.api_secret, message)
            return hmac.compare_digest(expected, sig)
        except Exception:
            return False

    def parse_postback(self, data: dict) -> dict:
        return {
            'user_id':   data.get('user_id'),
            'survey_id': data.get('survey_id', ''),
            'payout':    self._safe_decimal(data.get('cpa', 0)) / 100,  # cents → dollars
            'status':    'approved',
            'tx_id':     data.get('tx_id', str(uuid.uuid4())),
        }


# ─────────────────────────────────────────────────────────────
# Factory
# ─────────────────────────────────────────────────────────────

_REGISTRY = {
    'cpx':      CPXResearchService,
    'bitlabs':  BitLabsService,
    'pollfish': PollfishService,
}


class SurveyProviderFactory:
    """Create a survey service from an OfferProvider instance."""


    @classmethod
    def supported_types(cls) -> list:
        """FIX: missing method — survey_views.py calls this."""
        return list(cls._registry.keys())

    @classmethod
    def is_supported(cls, provider_type: str) -> bool:
        """FIX: missing method — survey_views.py calls this."""
        return provider_type in cls._registry

    @classmethod
    def create(cls, provider) -> BaseSurveyService:
        svc_cls = _REGISTRY.get(provider.provider_type)
        if not svc_cls:
            raise ValueError(
                f'No survey service registered for provider_type={provider.provider_type!r}. '
                f'Available: {list(_REGISTRY)}'
            )
        return svc_cls(provider)

    @classmethod
    def supported_types(cls) -> list:
        return list(_REGISTRY.keys())

    @classmethod
    def is_supported(cls, provider_type: str) -> bool:
        return provider_type in _REGISTRY
