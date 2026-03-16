"""
OfferToro offer processor
"""
import hashlib
import hmac
import logging

from api.offerwall.exceptions import InvalidWebhookSignatureException
from .OfferProcessor import OfferProcessor
from ..constants import *

logger = logging.getLogger(__name__)


class OfferwallService(OfferProcessor):
    """OfferToro processor"""
    
    def __init__(self, provider):
        super().__init__(provider)
        self.api_base = OFFERWALL_API_BASE
        self.app_id = provider.app_id
        self.api_key = provider.api_key
        self.secret_key = provider.secret_key
    
    def fetch_offers(self, **kwargs):
        """Fetch from OfferToro"""
        url = f"{self.api_base}/v1/offers"
        params = {
            'pubid': self.app_id,
            'appid': self.api_key,
            'userid': kwargs.get('user_id', 'default'),
        }
        try:
            response = self.make_api_request(url, params=params)
            return response.get('offers', [])
        except Exception as e:
            logger.error(f"OfferToro error: {e}")
            raise ProviderAPIException(f"OfferToro: {e}")
    
    def parse_offer_data(self, raw_data):
        """Parse OfferToro data"""
        return {
            'external_offer_id': str(raw_data.get('offer_id', '')),
            'title': raw_data.get('offer_name', ''),
            'description': self.clean_html(raw_data.get('offer_desc', '')),
            'image_url': raw_data.get('image_url', ''),
            'click_url': raw_data.get('link', ''),
            'payout': self.validate_payout(raw_data.get('payout_usd', 0)),
            'currency': 'USD',
            'offer_type': self.normalize_offer_type(raw_data.get('category', '')),
            'platform': self.normalize_platform(raw_data.get('device', 'all')),
            'countries': self._parse_countries(raw_data.get('country_code', '')),
            'estimated_time_minutes': 10,
            'status': STATUS_ACTIVE,
            'metadata': {'offertoro_id': raw_data.get('offer_id')}
        }
    
    def build_click_url(self, offer, user):
        """Build OfferToro URL"""
        import urllib.parse
        params = {'user_id': user.id}
        url_parts = list(urllib.parse.urlparse(offer.click_url))
        query = dict(urllib.parse.parse_qsl(url_parts[4]))
        query.update(params)
        url_parts[4] = urllib.parse.urlencode(query)
        return urllib.parse.urlunparse(url_parts)
    
    def verify_postback(self, data):
        """Verify OfferToro postback"""
        if not self.secret_key:
            return True
        sig = data.get('sig', '')
        if not sig:
            raise InvalidWebhookSignatureException("No signature")
        verify_str = f"{data.get('oid')}{data.get('amount')}{self.secret_key}"
        expected = hashlib.sha1(verify_str.encode()).hexdigest()
        if not hmac.compare_digest(sig, expected):
            raise InvalidWebhookSignatureException("Invalid signature")
        return True
    
    def _parse_countries(self, country_str):
        """Parse country codes"""
        if not country_str:
            return []
        return [c.strip().upper() for c in country_str.split(',') if c.strip()]


from .OfferProcessor import OfferProcessorFactory
OfferProcessorFactory.register(PROVIDER_OFFERWALL, OfferwallService)