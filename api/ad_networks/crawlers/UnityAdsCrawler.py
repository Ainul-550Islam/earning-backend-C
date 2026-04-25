"""
api/ad_networks/crawlers/UnityAdsCrawler.py
Unity Ads offer crawler
SaaS-ready with tenant support
"""

import requests
from django.utils import timezone
from decimal import Decimal
import logging

from .OfferCrawler import OfferCrawler

logger = logging.getLogger(__name__)


class UnityAdsCrawler(OfferCrawler):
    """Unity Ads offer crawler"""
    
    def __init__(self, ad_network):
        super().__init__(ad_network)
        self.base_url = "https://unityads.unity3d.com"
        self.api_key = ad_network.api_key
        self.api_secret = ad_network.api_secret
    
    def crawl(self):
        """Crawl offers from Unity Ads"""
        try:
            logger.info(f"Starting Unity Ads crawl for tenant {self.tenant_id}")
            
            # Create sync log
            sync_log = self._create_sync_log()
            
            offers_found = 0
            offers_updated = 0
            
            try:
                # Get offers from Unity Ads API
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
                
                logger.info(f"Unity Ads crawl completed: {offers_found} found, {offers_updated} updated")
                
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
                
                logger.error(f"Unity Ads crawl failed: {str(e)}")
                return {
                    'success': False,
                    'error': str(e),
                    'sync_log_id': sync_log.id
                }
                
        except Exception as e:
            logger.error(f"Unity Ads crawler initialization failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _fetch_offers(self):
        """Fetch offers from Unity Ads API"""
        try:
            # This is a mock implementation
            # In a real implementation, you would use Unity Ads API
            
            offers = [
                {
                    'external_id': 'unity_001',
                    'title': 'Unity Ads - Install Game',
                    'description': 'Install and play this Unity game',
                    'reward_amount': Decimal('150.00'),
                    'category': 'Mobile Games',
                    'platform': 'android',
                    'country': 'BD',
                    'requirements': 'Install game and complete tutorial',
                    'tracking_url': f'{self.base_url}/track/unity_001',
                    'expires_at': timezone.now() + timezone.timedelta(days=30)
                },
                {
                    'external_id': 'unity_002',
                    'title': 'Unity Ads - Watch Video',
                    'description': 'Watch promotional video for rewards',
                    'reward_amount': Decimal('25.00'),
                    'category': 'Video Ads',
                    'platform': 'android',
                    'country': 'BD',
                    'requirements': 'Watch 30 seconds video',
                    'tracking_url': f'{self.base_url}/track/unity_002',
                    'expires_at': timezone.now() + timezone.timedelta(days=7)
                }
            ]
            
            return offers
            
        except Exception as e:
            logger.error(f"Error fetching Unity Ads offers: {str(e)}")
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
