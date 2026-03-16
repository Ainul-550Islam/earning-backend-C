"""
AdGem offer processor
"""
import hashlib
import hmac
import logging
from decimal import Decimal
from .OfferProcessor import OfferProcessor
from ..constants import *
from ..exceptions import *

logger = logging.getLogger(__name__)


class AdGemService(OfferProcessor):
    """AdGem offer processor"""
    
    def __init__(self, provider):
        super().__init__(provider)
        self.api_base = ADGEM_API_BASE
        self.app_id = provider.app_id
        self.api_key = provider.api_key
        self.secret_key = provider.secret_key
    
    def fetch_offers(self, **kwargs):
        """
        Fetch offers from AdGem API
        
        Returns:
            list: Raw offer data
        """
        url = f"{self.api_base}/wall"
        
        params = {
            'appid': self.app_id,
            'userid': kwargs.get('user_id', 'default'),
            'format': 'json',
        }
        
        headers = self.get_auth_headers()
        
        try:
            self.session.headers.update(headers)
            response = self.make_api_request(url, params=params)
            
            return response.get('data', {}).get('offers', [])
        
        except Exception as e:
            logger.error(f"Failed to fetch AdGem offers: {e}")
            raise ProviderAPIException(f"AdGem API error: {e}")
    
    def get_auth_headers(self):
        """Get AdGem authentication headers"""
        return {
            'Authorization': f'Bearer {self.api_key}'
        }
    
    def parse_offer_data(self, raw_data):
        """
        Parse AdGem offer data
        
        Args:
            raw_data: Raw offer from AdGem
        
        Returns:
            dict: Normalized offer data
        """
        offer_data = {
            'external_offer_id': str(raw_data.get('campaign_id', '')),
            'title': raw_data.get('name', ''),
            'description': self.clean_html(raw_data.get('description', '')),
            'short_description': self.clean_html(raw_data.get('short_description', ''))[:500],
            
            # Media
            'image_url': raw_data.get('creative_url', ''),
            'icon_url': raw_data.get('icon_url', ''),
            'thumbnail_url': raw_data.get('thumbnail', ''),
            
            # Click URL
            'click_url': raw_data.get('click_url', ''),
            'tracking_url': raw_data.get('tracking_url', ''),
            
            # Payout
            'payout': self.validate_payout(raw_data.get('payout', 0)),
            'currency': raw_data.get('currency_name', 'USD'),
            
            # Type and platform
            'offer_type': self._parse_adgem_type(raw_data.get('type', '')),
            'platform': self.normalize_platform(raw_data.get('device', 'all')),
            
            # Categories
            'tags': raw_data.get('categories', []),
            
            # Requirements
            'min_age': raw_data.get('min_age', 18),
            'requires_card': 'credit card' in raw_data.get('requirements', '').lower(),
            
            # Countries
            'countries': self._parse_countries(raw_data.get('countries', [])),
            'excluded_countries': raw_data.get('excluded_countries', []),
            
            # Limits
            'daily_cap': raw_data.get('daily_cap', 0),
            'total_cap': raw_data.get('total_cap', 0),
            'user_limit': raw_data.get('user_cap', 1),
            
            # Status
            'status': STATUS_ACTIVE if raw_data.get('status') == 'active' else STATUS_PAUSED,
            
            # Instructions
            'instructions': self.clean_html(raw_data.get('instructions', '')),
            'requirements_text': self.clean_html(raw_data.get('requirements', '')),
            
            # Estimated time
            'estimated_time_minutes': raw_data.get('time_to_complete', 10),
            
            # Metadata
            'metadata': {
                'adgem_id': raw_data.get('campaign_id'),
                'advertiser': raw_data.get('advertiser_name'),
                'conversion_type': raw_data.get('conversion_type'),
            }
        }
        
        return offer_data
    
    def build_click_url(self, offer, user):
        """
        Build AdGem click URL with tracking
        
        Args:
            offer: Offer instance
            user: User instance
        
        Returns:
            str: Complete click URL
        """
        import urllib.parse
        
        base_url = offer.click_url
        
        # Add tracking parameters
        params = {
            'playerid': user.id,
            'appid': self.app_id,
        }
        
        # Build URL
        url_parts = list(urllib.parse.urlparse(base_url))
        query = dict(urllib.parse.parse_qsl(url_parts[4]))
        query.update(params)
        url_parts[4] = urllib.parse.urlencode(query)
        
        return urllib.parse.urlunparse(url_parts)
    
    def verify_postback(self, data):
        """
        Verify AdGem postback signature
        
        Args:
            data: Postback data
        
        Returns:
            bool: True if valid
        """
        if not self.secret_key:
            logger.warning("No secret key configured for AdGem verification")
            return True
        
        # Get signature from data
        provided_signature = data.get('signature', '')
        
        if not provided_signature:
            raise InvalidWebhookSignatureException("No signature provided")
        
        # Build verification string
        verification_string = (
            f"{data.get('user_id')}"
            f"{data.get('offer_id')}"
            f"{data.get('points')}"
            f"{self.secret_key}"
        )
        
        # Calculate expected signature
        expected_signature = hashlib.md5(
            verification_string.encode('utf-8')
        ).hexdigest()
        
        # Compare signatures
        if not hmac.compare_digest(provided_signature, expected_signature):
            raise InvalidWebhookSignatureException("Invalid AdGem signature")
        
        return True
    
    def _parse_adgem_type(self, offer_type):
        """Parse AdGem specific offer type"""
        type_map = {
            'cpi': OFFER_TYPE_APP_INSTALL,
            'cpa': OFFER_TYPE_SIGNUP,
            'survey': OFFER_TYPE_SURVEY,
            'video': OFFER_TYPE_VIDEO,
            'cpe': OFFER_TYPE_GAME,
        }
        
        return type_map.get(offer_type.lower(), OFFER_TYPE_OTHER)
    
    def _parse_countries(self, countries_data):
        """Parse countries list"""
        if not countries_data:
            return []
        
        if isinstance(countries_data, str):
            return [self.normalize_country_code(countries_data)]
        
        if isinstance(countries_data, list):
            return [self.normalize_country_code(c) for c in countries_data]
        
        return []


# Register with factory
from .OfferProcessor import OfferProcessorFactory
OfferProcessorFactory.register(PROVIDER_ADGEM, AdGemService)