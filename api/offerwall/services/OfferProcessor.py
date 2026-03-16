"""
Abstract base class for offer processors
"""
import logging
import requests
from abc import ABC, abstractmethod
from decimal import Decimal
from django.utils import timezone
from ..constants import *
from ..exceptions import *

logger = logging.getLogger(__name__)


class OfferProcessor(ABC):
    """Abstract base class for processing offers from different providers"""
    
    def __init__(self, provider):
        """
        Initialize processor with provider
        
        Args:
            provider: OfferProvider instance
        """
        self.provider = provider
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'EarningPlatform/1.0',
            'Accept': 'application/json',
        })
    
    @abstractmethod
    def fetch_offers(self, **kwargs):
        """
        Fetch offers from provider API
        
        Returns:
            list: List of offer dictionaries
        """
        pass
    
    @abstractmethod
    def parse_offer_data(self, raw_data):
        """
        Parse raw offer data from provider
        
        Args:
            raw_data: Raw offer data from API
        
        Returns:
            dict: Normalized offer data
        """
        pass
    
    @abstractmethod
    def verify_postback(self, data):
        """
        Verify postback/callback from provider
        
        Args:
            data: Postback data
        
        Returns:
            bool: True if valid
        """
        pass
    
    @abstractmethod
    def build_click_url(self, offer, user):
        """
        Build click URL with tracking parameters
        
        Args:
            offer: Offer instance
            user: User instance
        
        Returns:
            str: Click URL with tracking
        """
        pass
    
    def sync_offers(self, **filters):
        """
        Sync offers from provider
        
        Args:
            **filters: Optional filters for syncing
        
        Returns:
            dict: Sync results
        """
        try:
            logger.info(f"Starting offer sync for {self.provider.name}")
            
            # Fetch offers from API
            raw_offers = self.fetch_offers(**filters)
            
            if not raw_offers:
                logger.warning(f"No offers fetched from {self.provider.name}")
                return {
                    'success': True,
                    'synced': 0,
                    'created': 0,
                    'updated': 0,
                    'errors': []
                }
            
            # Process each offer
            results = {
                'success': True,
                'synced': 0,
                'created': 0,
                'updated': 0,
                'errors': []
            }
            
            for raw_offer in raw_offers:
                try:
                    result = self.process_offer(raw_offer)
                    
                    results['synced'] += 1
                    if result['created']:
                        results['created'] += 1
                    else:
                        results['updated'] += 1
                
                except Exception as e:
                    logger.error(f"Error processing offer: {e}")
                    results['errors'].append(str(e))
            
            # Update provider sync time
            self.provider.last_sync = timezone.now()
            self.provider.total_offers = results['synced']
            self.provider.save()
            
            logger.info(
                f"Sync completed for {self.provider.name}: "
                f"{results['created']} created, {results['updated']} updated"
            )
            
            return results
        
        except Exception as e:
            logger.error(f"Sync failed for {self.provider.name}: {e}")
            return {
                'success': False,
                'synced': 0,
                'created': 0,
                'updated': 0,
                'errors': [str(e)]
            }
    
    def process_offer(self, raw_data):
        """
        Process a single offer
        
        Args:
            raw_data: Raw offer data
        
        Returns:
            dict: Processing result
        """
        from ..models import Offer
        from ..utils.RewardCalculator import RewardCalculator
        
        # Parse offer data
        offer_data = self.parse_offer_data(raw_data)
        
        # Calculate user reward
        calculator = RewardCalculator(provider=self.provider)
        user_reward = calculator.calculate_user_reward(
            offer_data['payout'],
            offer_data.get('currency', 'USD')
        )
        
        offer_data['reward_amount'] = user_reward
        offer_data['provider_data'] = raw_data
        
        # Create or update offer
        offer, created = Offer.objects.update_or_create(
            provider=self.provider,
            external_offer_id=offer_data['external_offer_id'],
            defaults=offer_data
        )
        
        return {
            'offer': offer,
            'created': created
        }
    
    def make_api_request(self, url, method='GET', params=None, data=None, timeout=API_TIMEOUT_DEFAULT):
        """
        Make API request to provider
        
        Args:
            url: API endpoint URL
            method: HTTP method
            params: Query parameters
            data: Request body data
            timeout: Request timeout
        
        Returns:
            dict: Response data
        """
        try:
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                json=data,
                timeout=timeout
            )
            
            response.raise_for_status()
            
            return response.json()
        
        except requests.exceptions.Timeout:
            raise ProviderTimeoutException()
        
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                raise ProviderAuthenticationException()
            else:
                raise ProviderAPIException(f"HTTP {e.response.status_code}: {e.response.text}")
        
        except requests.exceptions.RequestException as e:
            raise ProviderAPIException(str(e))
    
    def get_auth_headers(self):
        """
        Get authentication headers for API requests
        
        Returns:
            dict: Auth headers
        """
        return {}
    
    def normalize_country_code(self, country):
        """
        Normalize country code to ISO 2-letter format
        
        Args:
            country: Country code or name
        
        Returns:
            str: ISO 2-letter country code
        """
        if not country:
            return ''
        
        country = country.strip().upper()
        
        # If already 2 letters, return as is
        if len(country) == 2:
            return country
        
        # Country name to code mapping (add more as needed)
        country_map = {
            'UNITED STATES': 'US',
            'UNITED KINGDOM': 'GB',
            'CANADA': 'CA',
            'AUSTRALIA': 'AU',
            'GERMANY': 'DE',
            'FRANCE': 'FR',
            'INDIA': 'IN',
            'BANGLADESH': 'BD',
        }
        
        return country_map.get(country, country[:2])
    
    def normalize_platform(self, platform):
        """
        Normalize platform value
        
        Args:
            platform: Platform string from provider
        
        Returns:
            str: Normalized platform constant
        """
        if not platform:
            return PLATFORM_ALL
        
        platform = platform.lower()
        
        if 'android' in platform:
            return PLATFORM_ANDROID
        elif 'ios' in platform or 'iphone' in platform or 'ipad' in platform:
            return PLATFORM_IOS
        elif 'mobile' in platform:
            return PLATFORM_MOBILE
        elif 'web' in platform:
            return PLATFORM_WEB
        elif 'desktop' in platform:
            return PLATFORM_DESKTOP
        
        return PLATFORM_ALL
    
    def normalize_offer_type(self, offer_type):
        """
        Normalize offer type
        
        Args:
            offer_type: Offer type from provider
        
        Returns:
            str: Normalized offer type constant
        """
        if not offer_type:
            return OFFER_TYPE_OTHER
        
        offer_type = offer_type.lower()
        
        type_map = {
            'app': OFFER_TYPE_APP_INSTALL,
            'install': OFFER_TYPE_APP_INSTALL,
            'signup': OFFER_TYPE_SIGNUP,
            'registration': OFFER_TYPE_SIGNUP,
            'survey': OFFER_TYPE_SURVEY,
            'video': OFFER_TYPE_VIDEO,
            'game': OFFER_TYPE_GAME,
            'trial': OFFER_TYPE_TRIAL,
            'purchase': OFFER_TYPE_PURCHASE,
            'subscription': OFFER_TYPE_SUBSCRIPTION,
            'quiz': OFFER_TYPE_QUIZ,
            'download': OFFER_TYPE_DOWNLOAD,
            'cashback': OFFER_TYPE_CASHBACK,
        }
        
        for key, value in type_map.items():
            if key in offer_type:
                return value
        
        return OFFER_TYPE_OTHER
    
    def validate_payout(self, payout):
        """
        Validate and convert payout value
        
        Args:
            payout: Payout value (string or number)
        
        Returns:
            Decimal: Valid payout amount
        """
        try:
            payout = Decimal(str(payout))
            
            if payout <= 0:
                raise InvalidRewardException("Payout must be greater than 0")
            
            return payout
        
        except (ValueError, TypeError):
            raise InvalidRewardException(f"Invalid payout value: {payout}")
    
    def clean_html(self, html_text):
        """
        Clean HTML from text
        
        Args:
            html_text: Text with HTML tags
        
        Returns:
            str: Cleaned text
        """
        if not html_text:
            return ''
        
        import re
        
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', html_text)
        
        # Decode HTML entities
        import html
        text = html.unescape(text)
        
        # Remove extra whitespace
        text = ' '.join(text.split())
        
        return text.strip()
    
    def extract_image_url(self, images):
        """
        Extract best image URL from images data
        
        Args:
            images: Images data (dict, list, or string)
        
        Returns:
            str: Image URL
        """
        if not images:
            return ''
        
        # If string, return as is
        if isinstance(images, str):
            return images
        
        # If dict, look for common keys
        if isinstance(images, dict):
            for key in ['large', 'medium', 'small', 'url', 'image']:
                if key in images:
                    return images[key]
        
        # If list, return first item
        if isinstance(images, list) and images:
            return images[0] if isinstance(images[0], str) else images[0].get('url', '')
        
        return ''
    
    def __del__(self):
        """Cleanup session on deletion"""
        if hasattr(self, 'session'):
            self.session.close()


class OfferProcessorFactory:
    """Factory for creating offer processors"""
    
    _processors = {}
    
    @classmethod
    def register(cls, provider_type, processor_class):
        """
        Register a processor class
        
        Args:
            provider_type: Provider type constant
            processor_class: Processor class
        """
        cls._processors[provider_type] = processor_class
    
    @classmethod
    def create(cls, provider):
        """
        Create processor instance for provider
        
        Args:
            provider: OfferProvider instance
        
        Returns:
            OfferProcessor: Processor instance
        """
        processor_class = cls._processors.get(provider.provider_type)
        
        if not processor_class:
            raise InvalidProviderConfigException(
                f"No processor registered for provider type: {provider.provider_type}"
            )
        
        return processor_class(provider)
    
    @classmethod
    def get_available_processors(cls):
        """
        Get list of available processors
        
        Returns:
            list: Available provider types
        """
        return list(cls._processors.keys())