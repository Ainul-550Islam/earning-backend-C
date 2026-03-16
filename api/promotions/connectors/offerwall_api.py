# api/promotions/connectors/offerwall_api.py
# Offerwall API — Tapjoy, IronSource, AdGate offerwall integration
import hashlib, hmac, logging, requests
from dataclasses import dataclass
from decimal import Decimal
from django.conf import settings
logger = logging.getLogger('connectors.offerwall')

@dataclass
class OfferwallOffer:
    offer_id: str; title: str; payout_usd: Decimal
    category: str; icon_url: str; instructions: str
    platform: str; country_restrictions: list

class OfferwallConnector:
    """
    Third-party offerwall integration.
    Providers: Tapjoy, IronSource, AdGate, Fyber, SuperRewards
    """
    PROVIDERS = {
        'tapjoy':      'https://ws.tapjoyads.com/get_offers',
        'ironsource':  'https://supply.ironbeast.io/v1/offers',
        'adgate':      'https://wall.adgaterewards.com/ocontent',
    }

    def __init__(self, provider: str = 'tapjoy'):
        self.provider = provider
        self.api_key  = getattr(settings, f'OFFERWALL_{provider.upper()}_API_KEY', '')
        self.base_url = self.PROVIDERS.get(provider, '')

    def get_offers(self, user_id: int, country: str, platform: str = 'android') -> list:
        if not self.api_key:
            return self._mock_offers()
        try:
            params = {'api_key': self.api_key, 'user_id': str(user_id), 'country': country, 'device': platform}
            resp   = requests.get(self.base_url, params=params, timeout=10)
            resp.raise_for_status()
            return self._parse_offers(resp.json())
        except Exception as e:
            logger.error(f'Offerwall {self.provider} failed: {e}')
            return []

    def verify_completion(self, user_id: str, offer_id: str, sig: str) -> bool:
        expected = hmac.new(self.api_key.encode(), f'{user_id}{offer_id}'.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, sig)

    def _parse_offers(self, data: dict) -> list:
        return [OfferwallOffer(o.get('id',''), o.get('name',''), Decimal(str(o.get('payout',0))),
                o.get('category',''), o.get('icon',''), o.get('instructions',''), o.get('platform',''), [])
                for o in data.get('offers', [])]

    def _mock_offers(self) -> list:
        return [OfferwallOffer('mock_1','Complete Survey',Decimal('0.25'),'survey','','Complete a 5-min survey','web',[])]
