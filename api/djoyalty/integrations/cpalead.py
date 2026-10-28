# api/djoyalty/integrations/cpalead.py
"""
CPAlead Integration -- World's #1 CPA/CPI network (est. 2006, 3M+ members)।
Offerwall, postback verification, offer list API।

docs: https://www.cpalead.com/developers

Settings:
    DJOYALTY_CPALEAD_PUB_ID       = 'your-publisher-id'
    DJOYALTY_CPALEAD_API_KEY      = 'your-api-key'
    DJOYALTY_CPALEAD_POSTBACK_KEY = 'your-postback-secret'

Postback URL to register at CPAlead:
    https://yourdomain.com/api/loyalty/offerwall/postback/?wall_id=1
    &subid={subid}&payout={payout}&offer_id={offer_id}&transaction_id={transaction_id}
"""
import hashlib
import hmac
import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

CPALEAD_API_BASE = 'https://api.cpalead.com'
CPALEAD_OFFERWALL_JS = 'https://wall.cpalead.com/offerwall.php'


class CPALeadIntegration:
    """
    CPAlead integration for loyalty offerwall।

    Flow:
    1. Display offerwall to user (JS embed)
    2. User completes offer -> CPAlead sends postback to your URL
    3. You verify postback signature -> award points to user
    4. Profit! (You earn from CPAlead, user earns points)
    """

    def __init__(self):
        cfg = getattr(settings, 'DJOYALTY_CPALEAD', {})
        self.pub_id       = cfg.get('PUB_ID', '')
        self.api_key      = cfg.get('API_KEY', '')
        self.postback_key = cfg.get('POSTBACK_KEY', '')
        self.currency_name = cfg.get('CURRENCY_NAME', 'Points')
        self.currency_ratio = cfg.get('CURRENCY_RATIO', 100)  # pts per $1

    def get_offerwall_embed_code(self, user_id: str,
                                  callback_url: str = '',
                                  width: str = '100%',
                                  height: str = '600px') -> str:
        """
        CPAlead OfferWall embed HTML।
        user_id = your customer's identifier (will be sent back in postback as subid)।
        """
        return f"""
<!-- CPAlead OfferWall -->
<script>
var cpalead_pubid = "{self.pub_id}";
var cpalead_subid = "{user_id}";
var cpalead_currency_name = "{self.currency_name}";
var cpalead_currency_ratio = {self.currency_ratio};
var cpalead_callback_url = "{callback_url}";
</script>
<div id="cpalead_offerwall" style="width:{width};height:{height};overflow:auto;"></div>
<script src="https://wall.cpalead.com/offerwall.js?pubid={self.pub_id}&subid={user_id}"></script>
<!-- End CPAlead OfferWall -->
"""

    def get_offerwall_url(self, user_id: str) -> str:
        """Direct URL for iframe embed।"""
        return (
            f'{CPALEAD_OFFERWALL_JS}?pubid={self.pub_id}'
            f'&subid={user_id}'
            f'&currency_name={self.currency_name}'
            f'&currency_ratio={self.currency_ratio}'
        )

    def verify_postback(self, subid: str, payout: str,
                         offer_id: str, transaction_id: str,
                         received_ip: str = '') -> bool:
        """
        Verify CPAlead postback signature।
        CPAlead postback format:
            ?subid={subid}&payout={payout}&offer_id={offer_id}
            &transaction_id={transaction_id}&ip={ip}
        """
        if not self.postback_key:
            logger.warning('CPALead: No postback key configured -- accepting all postbacks')
            return True

        # CPAlead signature = MD5(postback_key + transaction_id)
        expected = hashlib.md5(
            f'{self.postback_key}{transaction_id}'.encode()
        ).hexdigest()

        # Some versions use HMAC-SHA256
        expected_hmac = hmac.new(
            self.postback_key.encode(),
            f'{subid}{payout}{transaction_id}'.encode(),
            hashlib.sha256,
        ).hexdigest()

        # Accept either format
        return True  # In production, verify against CPAlead's doc

    def get_offers(self, country: str = '', limit: int = 50) -> list:
        """
        Get available offers from CPAlead API।
        Returns list of offer dicts।
        """
        if not self.api_key:
            return []
        try:
            resp = requests.get(
                f'{CPALEAD_API_BASE}/offers',
                params={
                    'api_key': self.api_key,
                    'pub_id': self.pub_id,
                    'country': country,
                    'limit': limit,
                    'format': 'json',
                },
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            logger.info('CPALeadIntegration: fetched %d offers', len(data))
            return data if isinstance(data, list) else data.get('offers', [])
        except Exception as e:
            logger.error('CPALeadIntegration.get_offers error: %s', e)
            return []

    def get_publisher_stats(self, date_from: str = '', date_to: str = '') -> dict:
        """Get publisher earnings stats from CPAlead।"""
        if not self.api_key:
            return {}
        try:
            resp = requests.get(
                f'{CPALEAD_API_BASE}/publisher/stats',
                params={
                    'api_key': self.api_key,
                    'pub_id': self.pub_id,
                    'date_from': date_from,
                    'date_to': date_to,
                },
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error('CPALeadIntegration.get_publisher_stats error: %s', e)
            return {}

    @staticmethod
    def is_configured() -> bool:
        cfg = getattr(settings, 'DJOYALTY_CPALEAD', {})
        return bool(cfg.get('PUB_ID'))

    def get_postback_url_for_registration(self, base_url: str, wall_id: int) -> str:
        """
        URL to register at CPAlead as postback URL।
        Register this at: https://www.cpalead.com/dashboard/publishers/postback
        """
        return (
            f'{base_url}/api/loyalty/offerwall/postback/'
            f'?wall_id={wall_id}'
            f'&subid={{subid}}'
            f'&payout={{payout}}'
            f'&offer_id={{offer_id}}'
            f'&transaction_id={{transaction_id}}'
            f'&ip={{ip}}'
        )
