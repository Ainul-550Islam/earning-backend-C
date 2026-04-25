import requests
from bs4 import BeautifulSoup
from django.utils import timezone
from django.db import transaction
from decimal import Decimal, InvalidOperation
import logging

from ..models import Offer, AdNetwork, OfferCategory, OfferSyncLog

logger = logging.getLogger(__name__)


class OfferCrawler:
    """Base crawler for scraping offers from ad networks"""
    
    def __init__(self, ad_network):
        self.ad_network = ad_network
        self.tenant_id = getattr(ad_network, 'tenant_id', 'default')
        self.session = requests.Session()
        self.session.timeout = 30
        self.session.headers.update({
            'User-Agent': 'AdNetworks-Crawler/1.0'
        })
    
    def crawl(self):
        """Override in subclasses"""
        raise NotImplementedError("Subclasses must implement crawl method")
    
    def save_offer(self, offer_data):
        """Save or update offer in database with tenant isolation"""
        try:
            # Ensure tenant_id is set
            if 'tenant_id' not in offer_data:
                offer_data['tenant_id'] = self.tenant_id
            
            # Validate required fields
            if not offer_data.get('external_id'):
                logger.error("Offer missing external_id")
                return None
            
            if not offer_data.get('title'):
                logger.error("Offer missing title")
                return None
            
            # Validate reward amount
            if 'reward_amount' in offer_data:
                try:
                    if isinstance(offer_data['reward_amount'], str):
                        offer_data['reward_amount'] = Decimal(offer_data['reward_amount'])
                    elif isinstance(offer_data['reward_amount'], (int, float)):
                        offer_data['reward_amount'] = Decimal(str(offer_data['reward_amount']))
                except (InvalidOperation, ValueError):
                    logger.error(f"Invalid reward amount: {offer_data['reward_amount']}")
                    return None
            
            # Set default values
            defaults = {
                'title': offer_data.get('title', 'Unknown Offer'),
                'description': offer_data.get('description', ''),
                'reward_amount': offer_data.get('reward_amount', Decimal('0.00')),
                'reward_currency': offer_data.get('reward_currency', 'BDT'),
                'click_url': offer_data.get('click_url', ''),
                'status': offer_data.get('status', 'active'),
                'tenant_id': self.tenant_id,
                'updated_at': timezone.now(),
            }
            
            # Add optional fields if present
            optional_fields = [
                'category', 'difficulty', 'estimated_time', 'steps_required',
                'platforms', 'device_type', 'countries', 'min_age', 'max_age',
                'max_conversions', 'user_daily_limit', 'user_lifetime_limit',
                'starts_at', 'expires_at', 'preview_url', 'terms_url', 'privacy_url',
                'is_featured', 'is_hot', 'is_new', 'is_exclusive', 'requires_approval',
                'tags', 'requirements', 'metadata'
            ]
            
            for field in optional_fields:
                if field in offer_data and offer_data[field] is not None:
                    defaults[field] = offer_data[field]
            
            # Use transaction for atomic operation
            with transaction.atomic():
                # Filter by tenant to ensure isolation
                offer, created = Offer.objects.update_or_create(
                    external_id=offer_data['external_id'],
                    ad_network=self.ad_network,
                    tenant_id=self.tenant_id,
                    defaults=defaults
                )
                
                if created:
                    logger.info(f"Created new offer: {offer.title} (ID: {offer.id})")
                else:
                    logger.info(f"Updated offer: {offer.title} (ID: {offer.id})")
                
                return offer
                
        except Exception as e:
            logger.error(f"Error saving offer {offer_data.get('external_id', 'unknown')}: {str(e)}")
            return None
    
    def log_sync_result(self, status, offers_fetched=0, offers_added=0, offers_updated=0, 
                       offers_removed=0, error_message=None, sync_duration=0):
        """Log synchronization result"""
        try:
            OfferSyncLog.objects.create(
                tenant_id=self.tenant_id,
                ad_network=self.ad_network,
                status=status,
                offers_fetched=offers_fetched,
                offers_added=offers_added,
                offers_updated=offers_updated,
                offers_removed=offers_removed,
                error_message=error_message,
                sync_duration=sync_duration
            )
        except Exception as e:
            logger.error(f"Error logging sync result: {str(e)}")
    
    def validate_offer_data(self, offer_data):
        """Validate offer data before saving"""
        errors = []
        
        # Required fields
        required_fields = ['external_id', 'title', 'reward_amount']
        for field in required_fields:
            if not offer_data.get(field):
                errors.append(f"Missing required field: {field}")
        
        # Validate reward amount
        if 'reward_amount' in offer_data:
            try:
                amount = Decimal(str(offer_data['reward_amount']))
                if amount < 0:
                    errors.append("Reward amount cannot be negative")
                if amount > Decimal('10000'):  # Reasonable upper limit
                    errors.append("Reward amount too high")
            except (InvalidOperation, ValueError):
                errors.append("Invalid reward amount format")
        
        # Validate URLs
        url_fields = ['click_url', 'preview_url', 'terms_url', 'privacy_url']
        for field in url_fields:
            if field in offer_data and offer_data[field]:
                if not offer_data[field].startswith(('http://', 'https://')):
                    errors.append(f"Invalid {field}: must start with http:// or https://")
        
        # Validate age limits
        if 'min_age' in offer_data and 'max_age' in offer_data:
            if offer_data['min_age'] > offer_data['max_age']:
                errors.append("min_age cannot be greater than max_age")
        
        return errors
    
    def clean_offer_data(self, offer_data):
        """Clean and normalize offer data"""
        cleaned = offer_data.copy()
        
        # Clean title
        if 'title' in cleaned:
            cleaned['title'] = str(cleaned['title']).strip()[:255]
        
        # Clean description
        if 'description' in cleaned:
            cleaned['description'] = str(cleaned['description']).strip()[:2000]
        
        # Normalize platforms
        if 'platforms' in cleaned and isinstance(cleaned['platforms'], str):
            cleaned['platforms'] = [p.strip() for p in cleaned['platforms'].split(',')]
        
        # Normalize countries
        if 'countries' in cleaned and isinstance(cleaned['countries'], str):
            cleaned['countries'] = [c.strip() for c in cleaned['countries'].split(',')]
        
        # Clean tags
        if 'tags' in cleaned and isinstance(cleaned['tags'], str):
            cleaned['tags'] = [t.strip() for t in cleaned['tags'].split(',')]
        
        # Ensure list fields are lists
        list_fields = ['platforms', 'countries', 'tags', 'requirements']
        for field in list_fields:
            if field in cleaned and cleaned[field] is None:
                cleaned[field] = []
        
        return cleaned
    
    def get_category_by_name(self, category_name):
        """Get or create offer category by name"""
        try:
            if not category_name:
                return None
            
            category, created = OfferCategory.objects.get_or_create(
                name__iexact=category_name,
                defaults={
                    'name': category_name,
                    'slug': category_name.lower().replace(' ', '-'),
                    'category_type': 'offer'
                }
            )
            
            if created:
                logger.info(f"Created new category: {category.name}")
            
            return category
            
        except Exception as e:
            logger.error(f"Error getting category {category_name}: {str(e)}")
            return None
    
    def make_api_request(self, url, method='GET', params=None, data=None, headers=None):
        """Make API request with error handling"""
        try:
            request_headers = self.session.headers.copy()
            if headers:
                request_headers.update(headers)
            
            if method.upper() == 'GET':
                response = self.session.get(url, params=params, headers=request_headers)
            elif method.upper() == 'POST':
                response = self.session.post(url, json=data, params=params, headers=request_headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            return response
            
        except requests.RequestException as e:
            logger.error(f"API request failed: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in API request: {str(e)}")
            return None
    
    def validate_network_config(self):
        """Validate network configuration"""
        errors = []
        
        if not self.ad_network.api_key:
            errors.append("API key is required")
        
        if not self.ad_network.base_url:
            errors.append("Base URL is required")
        
        return errors