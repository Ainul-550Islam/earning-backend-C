from .OfferCrawler import OfferCrawler
import requests
import logging
import hashlib
import hmac
from datetime import datetime, timedelta
from decimal import Decimal
from django.utils import timezone
from urllib.parse import urlencode

logger = logging.getLogger(__name__)


class TapjoyCrawler(OfferCrawler):
    """Tapjoy specific crawler for mobile app and game offers"""
    
    def __init__(self, ad_network):
        super().__init__(ad_network)
        self.base_url = "https://api.tapjoy.com/v4"
        self.api_key = ad_network.api_key
        self.api_secret = ad_network.api_secret
    
    def crawl(self):
        """Crawl offers from Tapjoy API"""
        try:
            logger.info(f"Starting Tapjoy crawl for network: {self.ad_network.name}")
            
            # Validate API credentials
            if not self.api_key or not self.api_secret:
                logger.error("Tapjoy API credentials missing")
                return []
            
            # Get offers from Tapjoy API
            offers_data = self._get_offers_from_api()
            if not offers_data:
                logger.warning("No offers found from Tapjoy API")
                return []
            
            # Process and save offers
            saved_offers = []
            for offer_data in offers_data:
                processed_offer = self._process_tapjoy_offer(offer_data)
                if processed_offer:
                    saved_offer = self.save_offer(processed_offer)
                    if saved_offer:
                        saved_offers.append(saved_offer)
            
            logger.info(f"Tapjoy crawl completed. Saved {len(saved_offers)} offers")
            return saved_offers
            
        except Exception as e:
            logger.error(f"Tapjoy crawl failed: {str(e)}")
            return []
    
    def _get_offers_from_api(self):
        """Get offers from Tapjoy API"""
        try:
            # Build API URL
            url = f"{self.base_url}/offers"
            
            # Prepare parameters
            params = {
                'api_key': self.api_key,
                'timestamp': int(timezone.now().timestamp()),
                'format': 'json'
            }
            
            # Generate signature
            signature = self._generate_signature(params)
            params['signature'] = signature
            
            # Make API request
            headers = {
                'User-Agent': 'AdNetworks-Crawler/1.0',
                'Accept': 'application/json'
            }
            
            response = requests.get(url, params=params, headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                return data.get('offers', [])
            else:
                logger.error(f"Tapjoy API error: {response.status_code} - {response.text}")
                return []
                
        except requests.RequestException as e:
            logger.error(f"Tapjoy API request failed: {str(e)}")
            return []
    
    def _generate_signature(self, params):
        """Generate HMAC-SHA1 signature for API request"""
        try:
            # Sort parameters alphabetically
            sorted_params = sorted(params.items())
            query_string = urlencode(sorted_params)
            
            # Generate signature
            signature = hmac.new(
                self.api_secret.encode('utf-8'),
                query_string.encode('utf-8'),
                hashlib.sha1
            ).hexdigest()
            
            return signature
            
        except Exception as e:
            logger.error(f"Signature generation failed: {str(e)}")
            return None
    
    def _process_tapjoy_offer(self, offer_data):
        """Process Tapjoy offer data into standard format"""
        try:
            # Extract Tapjoy specific data
            tapjoy_id = offer_data.get('id', '')
            title = offer_data.get('name', 'Unknown Offer')
            description = offer_data.get('description', '')
            
            # Get payout information
            payout_info = offer_data.get('payout', {})
            amount = Decimal(str(payout_info.get('amount', 0)))
            currency = payout_info.get('currency', 'USD')
            
            # Convert to BDT if needed (assuming 1 USD = 105 BDT)
            if currency == 'USD':
                amount = amount * Decimal('105')
                currency = 'BDT'
            
            # Get platform information
            platforms = offer_data.get('platforms', [])
            if isinstance(platforms, str):
                platforms = [platforms]
            
            # Get country restrictions
            countries = offer_data.get('countries', [])
            if not countries:
                countries = ['US', 'GB', 'CA', 'AU', 'BD']  # Default supported countries
            
            # Create standard offer data
            processed_offer = {
                'external_id': f"tapjoy_{tapjoy_id}",
                'title': title,
                'description': description,
                'reward_amount': amount,
                'reward_currency': currency,
                'click_url': offer_data.get('click_url', ''),
                'preview_url': offer_data.get('preview_url', ''),
                'status': 'active' if offer_data.get('is_active', True) else 'paused',
                'tenant_id': getattr(self.ad_network, 'tenant_id', 'default'),
                
                # Offer details
                'difficulty': self._determine_difficulty(offer_data),
                'estimated_time': offer_data.get('estimated_time', 10),  # minutes
                'steps_required': offer_data.get('steps_required', 1),
                
                # Targeting
                'platforms': platforms if platforms else ['android', 'ios'],
                'device_type': self._map_device_type(offer_data.get('device_type', 'mobile')),
                'countries': countries,
                'min_age': offer_data.get('min_age', 13),
                'max_age': offer_data.get('max_age', 100),
                
                # Limits
                'max_conversions': offer_data.get('max_conversions', 10000),
                'user_daily_limit': offer_data.get('user_daily_limit', 1),
                'user_lifetime_limit': offer_data.get('user_lifetime_limit', 1),
                
                # Time settings
                'starts_at': self._parse_date(offer_data.get('start_time')),
                'expires_at': self._parse_date(offer_data.get('end_time')),
                
                # Categories and tags
                'category': self._map_category(offer_data.get('category', 'offer')),
                'tags': offer_data.get('tags', []),
                
                # Metadata
                'metadata': {
                    'tapjoy_id': tapjoy_id,
                    'original_currency': payout_info.get('currency', 'USD'),
                    'original_amount': str(payout_info.get('amount', 0)),
                    'crawled_at': timezone.now().isoformat(),
                    'source': 'tapjoy_api',
                    'offer_type': offer_data.get('type', 'unknown')
                }
            }
            
            return processed_offer
            
        except Exception as e:
            logger.error(f"Error processing Tapjoy offer: {str(e)}")
            return None
    
    def _determine_difficulty(self, offer_data):
        """Determine offer difficulty based on Tapjoy data"""
        offer_type = offer_data.get('type', '').lower()
        time_required = offer_data.get('estimated_time', 10)
        
        if offer_type in ['video', 'simple']:
            return 'very_easy'
        elif offer_type in ['survey', 'quiz']:
            return 'medium'
        elif time_required > 20:
            return 'hard'
        else:
            return 'easy'
    
    def _map_device_type(self, device_type):
        """Map Tapjoy device type to standard format"""
        device_map = {
            'mobile': 'mobile',
            'tablet': 'tablet',
            'desktop': 'desktop',
            'all': 'any'
        }
        return device_map.get(device_type.lower(), 'any')
    
    def _map_category(self, category):
        """Map Tapjoy category to standard format"""
        category_map = {
            'app_install': 'app_install',
            'survey': 'survey',
            'video': 'video',
            'game': 'gaming',
            'offer': 'offer',
            'trial': 'offer'
        }
        return category_map.get(category.lower(), 'offer')
    
    def _parse_date(self, date_string):
        """Parse date string from Tapjoy API"""
        if not date_string:
            return None
        
        try:
            # Handle different date formats
            if isinstance(date_string, str):
                # Try ISO format first
                try:
                    return datetime.fromisoformat(date_string.replace('Z', '+00:00'))
                except ValueError:
                    pass
                
                # Try Unix timestamp
                try:
                    return datetime.fromtimestamp(float(date_string))
                except ValueError:
                    pass
            
            return None
            
        except Exception:
            return None
    
    def validate_api_credentials(self):
        """Validate Tapjoy API credentials"""
        try:
            if not self.api_key or not self.api_secret:
                return False, "API key and secret are required"
            
            # Test API call with minimal parameters
            params = {
                'api_key': self.api_key,
                'timestamp': int(timezone.now().timestamp()),
                'format': 'json'
            }
            
            signature = self._generate_signature(params)
            if not signature:
                return False, "Failed to generate signature"
            
            params['signature'] = signature
            
            # Make test request
            url = f"{self.base_url}/offers"
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                return True, "Credentials valid"
            elif response.status_code == 401:
                return False, "Invalid API credentials"
            else:
                return False, f"API error: {response.status_code}"
                
        except Exception as e:
            return False, f"Validation error: {str(e)}"