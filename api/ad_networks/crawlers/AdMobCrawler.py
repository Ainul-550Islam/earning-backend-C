from .OfferCrawler import OfferCrawler
import requests
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from django.utils import timezone

logger = logging.getLogger(__name__)


class AdMobCrawler(OfferCrawler):
    """AdMob specific crawler for mobile app install offers"""
    
    def __init__(self, ad_network):
        super().__init__(ad_network)
        self.base_url = "https://developers.google.com/admob/api/v3"
        self.api_version = "v3"
    
    def crawl(self):
        """Crawl offers from AdMob API"""
        try:
            logger.info(f"Starting AdMob crawl for network: {self.ad_network.name}")
            
            # Validate API credentials
            if not self.ad_network.api_key or not self.ad_network.publisher_id:
                logger.error("AdMob API credentials missing")
                return []
            
            # Get AdMob account info first
            account_info = self._get_account_info()
            if not account_info:
                logger.error("Failed to get AdMob account info")
                return []
            
            # Get ad units (offer sources)
            ad_units = self._get_ad_units()
            if not ad_units:
                logger.warning("No ad units found")
                return []
            
            # Generate offers from ad units
            offers = []
            for ad_unit in ad_units:
                offer_data = self._create_offer_from_ad_unit(ad_unit)
                if offer_data:
                    offers.append(offer_data)
            
            # Save offers to database
            saved_offers = []
            for offer_data in offers:
                saved_offer = self.save_offer(offer_data)
                if saved_offer:
                    saved_offers.append(saved_offer)
            
            logger.info(f"AdMob crawl completed. Saved {len(saved_offers)} offers")
            return saved_offers
            
        except Exception as e:
            logger.error(f"AdMob crawl failed: {str(e)}")
            return []
    
    def _get_account_info(self):
        """Get AdMob account information"""
        try:
            headers = {
                'Authorization': f'Bearer {self.ad_network.api_key}',
                'Content-Type': 'application/json'
            }
            
            url = f"{self.base_url}/accounts/{self.ad_network.publisher_id}"
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"AdMob API error: {response.status_code} - {response.text}")
                return None
                
        except requests.RequestException as e:
            logger.error(f"AdMob API request failed: {str(e)}")
            return None
    
    def _get_ad_units(self):
        """Get ad units from AdMob account"""
        try:
            headers = {
                'Authorization': f'Bearer {self.ad_network.api_key}',
                'Content-Type': 'application/json'
            }
            
            url = f"{self.base_url}/accounts/{self.ad_network.publisher_id}/adUnits"
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                return data.get('adUnits', [])
            else:
                logger.error(f"Failed to get ad units: {response.status_code}")
                return []
                
        except requests.RequestException as e:
            logger.error(f"Ad units request failed: {str(e)}")
            return []
    
    def _create_offer_from_ad_unit(self, ad_unit):
        """Create offer data from AdMob ad unit"""
        try:
            # Extract relevant data from ad unit
            ad_unit_id = ad_unit.get('name', '').split('/')[-1]  # Extract ID from name
            display_name = ad_unit.get('displayName', 'Unknown Ad Unit')
            ad_format = ad_unit.get('adFormat', 'unknown')
            
            # Create offer data
            offer_data = {
                'external_id': f"admob_{ad_unit_id}",
                'title': f"Install App - {display_name}",
                'description': f"Complete app installation for {display_name} ({ad_format})",
                'reward_amount': self._calculate_reward_amount(ad_format),
                'click_url': self._generate_click_url(ad_unit),
                'status': 'active',
                'tenant_id': getattr(self.ad_network, 'tenant_id', 'default'),
                'difficulty': 'easy',
                'estimated_time': 5,  # 5 minutes for app install
                'platforms': ['android', 'ios'],
                'device_type': 'mobile',
                'countries': ['US', 'GB', 'CA', 'AU'],  # Tier 1 countries
                'max_conversions': 1000,
                'user_daily_limit': 1,
                'user_lifetime_limit': 1,
                'expires_at': timezone.now() + timedelta(days=30),
                'metadata': {
                    'ad_unit_id': ad_unit_id,
                    'ad_format': ad_format,
                    'crawled_at': timezone.now().isoformat(),
                    'source': 'admob_api'
                }
            }
            
            return offer_data
            
        except Exception as e:
            logger.error(f"Error creating offer from ad unit: {str(e)}")
            return None
    
    def _calculate_reward_amount(self, ad_format):
        """Calculate reward amount based on ad format"""
        reward_map = {
            'banner': Decimal('0.50'),
            'interstitial': Decimal('1.00'),
            'rewarded': Decimal('2.00'),
            'native': Decimal('1.50'),
            'app_open': Decimal('0.75')
        }
        
        return reward_map.get(ad_format, Decimal('1.00'))
    
    def _generate_click_url(self, ad_unit):
        """Generate click URL for offer"""
        ad_unit_id = ad_unit.get('name', '').split('/')[-1]
        base_url = getattr(self.ad_network, 'base_url', 'https://admob.google.com')
        
        return f"{base_url}/ad-unit/{ad_unit_id}?publisher={self.ad_network.publisher_id}"
    
    def validate_api_credentials(self):
        """Validate AdMob API credentials"""
        try:
            if not self.ad_network.api_key or not self.ad_network.publisher_id:
                return False, "API key and publisher ID are required"
            
            # Test API call
            account_info = self._get_account_info()
            if account_info:
                return True, "Credentials valid"
            else:
                return False, "Invalid API credentials"
                
        except Exception as e:
            return False, f"Validation error: {str(e)}"