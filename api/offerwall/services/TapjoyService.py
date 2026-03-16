"""
Tapjoy offer processor
"""
import hashlib
import hmac
import logging
from decimal import Decimal
from .OfferProcessor import OfferProcessor
from ..constants import *
from ..exceptions import *

logger = logging.getLogger(__name__)


class TapjoyService(OfferProcessor):
    """Tapjoy offer processor"""
    
    def __init__(self, provider):
        super().__init__(provider)
        self.api_base = TAPJOY_API_BASE
        self.app_id = provider.app_id
        self.api_key = provider.api_key
        self.secret_key = provider.secret_key
    
    def fetch_offers(self, **kwargs):
        """
        Fetch offers from Tapjoy API
        
        Returns:
            list: Raw offer data
        """
        url = f"{self.api_base}/offers"
        
        params = {
            'app_id': self.app_id,
            'api_key': self.api_key,
            'format': 'json',
        }
        
        # Add optional filters
        if kwargs.get('country'):
            params['country'] = kwargs['country']
        
        if kwargs.get('platform'):
            params['platform'] = kwargs['platform']
        
        try:
            response = self.make_api_request(url, params=params)
            
            return response.get('offers', [])
        
        except Exception as e:
            logger.error(f"Failed to fetch Tapjoy offers: {e}")
            raise ProviderAPIException(f"Tapjoy API error: {e}")
    
    def parse_offer_data(self, raw_data):
        """
        Parse Tapjoy offer data
        
        Args:
            raw_data: Raw offer from Tapjoy
        
        Returns:
            dict: Normalized offer data
        """
        offer_data = {
            'external_offer_id': str(raw_data.get('id', '')),
            'title': raw_data.get('name', ''),
            'description': self.clean_html(raw_data.get('description', '')),
            'short_description': self.clean_html(raw_data.get('teaser', ''))[:500],
            
            # Media
            'image_url': self.extract_image_url(raw_data.get('image_url')),
            'icon_url': raw_data.get('icon_url', ''),
            'thumbnail_url': raw_data.get('thumbnail_url', ''),
            
            # Click URL
            'click_url': raw_data.get('click_url', ''),
            
            # Payout
            'payout': self.validate_payout(raw_data.get('amount', 0)),
            'currency': raw_data.get('currency', 'USD'),
            
            # Type and platform
            'offer_type': self.normalize_offer_type(raw_data.get('type', 'other')),
            'platform': self.normalize_platform(raw_data.get('platform', 'all')),
            
            # Requirements
            'requires_signup': raw_data.get('requires_email', False),
            'requires_card': raw_data.get('requires_credit_card', False),
            
            # Time
            'estimated_time_minutes': raw_data.get('time_to_payout_minutes', 5),
            
            # Countries
            'countries': self._parse_countries(raw_data.get('countries', [])),
            
            # Status
            'status': STATUS_ACTIVE if raw_data.get('active', True) else STATUS_PAUSED,
            
            # Instructions
            'instructions': self.clean_html(raw_data.get('instructions', '')),
            
            # Metadata
            'metadata': {
                'tapjoy_id': raw_data.get('id'),
                'store_id': raw_data.get('store_id'),
                'category': raw_data.get('category'),
            }
        }
        
        return offer_data
    
    def build_click_url(self, offer, user):
        """
        Build Tapjoy click URL with tracking
        
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
            'user_id': user.id,
            'app_id': self.app_id,
        }
        
        # Build URL
        url_parts = list(urllib.parse.urlparse(base_url))
        query = dict(urllib.parse.parse_qsl(url_parts[4]))
        query.update(params)
        url_parts[4] = urllib.parse.urlencode(query)
        
        return urllib.parse.urlunparse(url_parts)
    
    def verify_postback(self, data):
        """
        Verify Tapjoy postback signature
        
        Args:
            data: Postback data
        
        Returns:
            bool: True if valid
        """
        if not self.secret_key:
            logger.warning("No secret key configured for Tapjoy verification")
            return True
        
        # Get signature from data
        provided_signature = data.get('verifier', '')
        
        if not provided_signature:
            raise InvalidWebhookSignatureException("No signature provided")
        
        # Build verification string
        verification_params = [
            data.get('id', ''),
            data.get('snuid', ''),
            data.get('currency', ''),
            self.secret_key
        ]
        
        verification_string = ':'.join(str(p) for p in verification_params)
        
        # Calculate expected signature
        expected_signature = hashlib.sha256(
            verification_string.encode('utf-8')
        ).hexdigest()
        
        # Compare signatures
        if not hmac.compare_digest(provided_signature, expected_signature):
            raise InvalidWebhookSignatureException("Invalid Tapjoy signature")
        
        return True
    
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
OfferProcessorFactory.register(PROVIDER_TAPJOY, TapjoyService)