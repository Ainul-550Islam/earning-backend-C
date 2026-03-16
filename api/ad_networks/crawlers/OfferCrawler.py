import requests
from bs4 import BeautifulSoup
from ..models import Offer, AdNetwork, OfferCategory
import logging

logger = logging.getLogger(__name__)


class OfferCrawler:
    """Base crawler for scraping offers from ad networks"""
    
    def __init__(self, ad_network):
        self.ad_network = ad_network
    
    def crawl(self):
        """Override in subclasses"""
        raise NotImplementedError
    
    def save_offer(self, offer_data):
        """Save or update offer in database"""
        try:
            offer, created = Offer.objects.update_or_create(
                external_id=offer_data['external_id'],
                ad_network=self.ad_network,
                defaults=offer_data
            )
            
            if created:
                logger.info(f"Created new offer: {offer.title}")
            else:
                logger.info(f"Updated offer: {offer.title}")
            
            return offer
        except Exception as e:
            logger.error(f"Error saving offer: {e}")
            return None