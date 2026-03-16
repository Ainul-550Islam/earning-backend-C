"""
AdGate Media offer processor
"""
import hashlib
import hmac
import logging
from .OfferProcessor import OfferProcessor
from ..constants import *

logger = logging.getLogger(__name__)


class AdGateService(OfferProcessor):
    """AdGate Media offer processor"""
    
    def __init__(self, provider):
        super().__init__(provider)
        self.api_base = ADGATE_API_BASE
        self.wall_code = provider.app_id
        self.api_key = provider.api_key
        self.secret_key = provider.secret_key
    
    def fetch_offers(self, **kwargs):
        """Fetch offers from AdGate API"""
        url = f"{self.api_base}/v3/wall/{self.wall_code}"
        
        params = {
            'user_id': kwargs.get('user_id', 'default'),
        }
        
        try:
            response = self.make_api_request(url, params=params)
            return response.get('offers', [])
        except Exception as e:
            logger.error(f"AdGate fetch error: {e}")
            raise ProviderAPIException(f"AdGate: {e}")
    
    def parse_offer_data(self, raw_data):
        """Parse AdGate offer data"""
        return {
            'external_offer_id': str(raw_data.get('adgate_id', '')),
            'title': raw_data.get('name', ''),
            'description': self.clean_html(raw_data.get('description', '')),
            'short_description': self.clean_html(raw_data.get('short_description', ''))[:500],
            'image_url': raw_data.get('creative_url', ''),
            'icon_url': raw_data.get('icon', ''),
            'click_url': raw_data.get('click_url', ''),
            'payout': self.validate_payout(raw_data.get('points', 0)),
            'currency': 'Points',
            'offer_type': self.normalize_offer_type(raw_data.get('category', '')),
            'platform': self.normalize_platform(raw_data.get('anchor', 'all')),
            'countries': [raw_data.get('country', '')] if raw_data.get('country') else [],
            'estimated_time_minutes': raw_data.get('epc', 5),
            'status': STATUS_ACTIVE,
            'instructions': self.clean_html(raw_data.get('requirements', '')),
            'metadata': {'adgate_id': raw_data.get('adgate_id')}
        }
    
    def build_click_url(self, offer, user):
        """Build AdGate click URL"""
        import urllib.parse
        params = {'user_id': user.id, 'wall': self.wall_code}
        url_parts = list(urllib.parse.urlparse(offer.click_url))
        query = dict(urllib.parse.parse_qsl(url_parts[4]))
        query.update(params)
        url_parts[4] = urllib.parse.urlencode(query)
        return urllib.parse.urlunparse(url_parts)
    
    def verify_postback(self, data):
        """Verify AdGate postback"""
        if not self.secret_key:
            return True
        signature = data.get('hash', '')
        if not signature:
            raise InvalidWebhookSignatureException("No signature")
        verify_string = f"{data.get('pointvalue')}{data.get('adgateid')}{data.get('userid')}{self.secret_key}"
        expected = hashlib.sha256(verify_string.encode()).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise InvalidWebhookSignatureException("Invalid signature")
        return True


from .OfferProcessor import OfferProcessorFactory
OfferProcessorFactory.register(PROVIDER_ADGATE, AdGateService)