"""
api/ad_networks/crawlers/IronSourceCrawler.py
IronSource offer crawler
SaaS-ready with tenant support
"""

import requests
from django.utils import timezone
from decimal import Decimal
import logging

from .OfferCrawler import OfferCrawler

logger = logging.getLogger(__name__)


class IronSourceCrawler(OfferCrawler):
    """IronSource offer crawler"""
    
    def __init__(self, ad_network):
        super().__init__(ad_network)
        self.base_url = "https://platform.ironsrc.com"
        self.api_key = ad_network.api_key
        self.api_secret = ad_network.api_secret
    
    def crawl(self):
        """Crawl offers from IronSource"""
        try:
            logger.info(f"Starting IronSource crawl for tenant {self.tenant_id}")
            
            # Create sync log
            sync_log = self._create_sync_log()
            
            offers_found = 0
            offers_updated = 0
            
            try:
                # Get offers from IronSource API
                offers = self._fetch_offers()
                
                for offer_data in offers:
                    result = self.save_offer(offer_data)
                    if result:
                        if result.get('created'):
                            offers_found += 1
                        else:
                            offers_updated += 1
                
                # Update sync log
                sync_log.status = 'completed'
                sync_log.offers_found = offers_found
                sync_log.offers_updated = offers_updated
                sync_log.completed_at = timezone.now()
                sync_log.save()
                
                logger.info(f"IronSource crawl completed: {offers_found} found, {offers_updated} updated")
                
                return {
                    'success': True,
                    'offers_found': offers_found,
                    'offers_updated': offers_updated,
                    'sync_log_id': sync_log.id
                }
                
            except Exception as e:
                sync_log.status = 'failed'
                sync_log.error_message = str(e)
                sync_log.completed_at = timezone.now()
                sync_log.save()
                
                logger.error(f"IronSource crawl failed: {str(e)}")
                return {
                    'success': False,
                    'error': str(e),
                    'sync_log_id': sync_log.id
                }
                
        except Exception as e:
            logger.error(f"IronSource crawler initialization failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _fetch_offers(self):
        """Fetch offers from IronSource API"""
        try:
            # Mock implementation for IronSource offers
            offers = [
                {
                    'external_id': 'ironsrc_001',
                    'title': 'IronSource - Play Game',
                    'description': 'Download and play this mobile game',
                    'reward_amount': Decimal('200.00'),
                    'category': 'Mobile Games',
                    'platform': 'android',
                    'country': 'BD',
                    'requirements': 'Reach level 10 in the game',
                    'tracking_url': f'{self.base_url}/track/ironsrc_001',
                    'expires_at': timezone.now() + timezone.timedelta(days=45)
                },
                {
                    'external_id': 'ironsrc_002',
                    'title': 'IronSource - Complete Survey',
                    'description': 'Complete market research survey',
                    'reward_amount': Decimal('75.00'),
                    'category': 'Surveys',
                    'platform': 'web',
                    'country': 'BD',
                    'requirements': 'Complete 15-minute survey',
                    'tracking_url': f'{self.base_url}/track/ironsrc_002',
                    'expires_at': timezone.now() + timezone.timedelta(days=14)
                }
            ]
            
            return offers
            
        except Exception as e:
            logger.error(f"Error fetching IronSource offers: {str(e)}")
            return []
    
    def _create_sync_log(self):
        """Create sync log entry"""
        from ..models import OfferSyncLog
        
        return OfferSyncLog.objects.create(
            ad_network=self.ad_network,
            tenant_id=self.tenant_id,
            started_at=timezone.now(),
            status='running'
        )
