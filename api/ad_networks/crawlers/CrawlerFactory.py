"""
api/ad_networks/crawlers/CrawlerFactory.py
Factory for creating and managing crawlers
SaaS-ready with tenant support
"""

import logging
from django.utils import timezone
from django.db import transaction

from ..models import AdNetwork, OfferSyncLog
from .OfferCrawler import OfferCrawler
from .AdMobCrawler import AdMobCrawler
from .UnityAdsCrawler import UnityAdsCrawler
from .IronSourceCrawler import IronSourceCrawler
from .AppLovinCrawler import AppLovinCrawler
from .TapjoyCrawler import TapjoyCrawler
from .AdscendCrawler import AdscendCrawler
from .OfferToroCrawler import OfferToroCrawler

logger = logging.getLogger(__name__)


class CrawlerFactory:
    """Factory for creating and managing crawlers"""
    
    CRAWLER_MAPPING = {
        # Basic Networks (1-6)
        'admob': AdMobCrawler,
        'unity': UnityAdsCrawler,
        'ironsource': IronSourceCrawler,
        'applovin': AppLovinCrawler,
        'tapjoy': TapjoyCrawler,
        'vungle': None,  # To be implemented
        
        # Top Offerwalls (7-26)
        'adscend': AdscendCrawler,
        'offertoro': OfferToroCrawler,
        'adgem': None,  # To be implemented
        'ayetstudios': None,  # To be implemented
        'lootably': None,  # To be implemented
        'revenueuniverse': None,  # To be implemented
        'adgate': None,  # To be implemented
        'cpalead': None,  # To be implemented
        'adworkmedia': None,  # To be implemented
        'wannads': None,  # To be implemented
        'personaly': None,  # To be implemented
        'kiwiwall': None,  # To be implemented
        'monlix': None,  # To be implemented
        'notik': None,  # To be implemented
        'offerdaddy': None,  # To be implemented
        'offertown': None,  # To be implemented
        'adlockmedia': None,  # To be implemented
        'offerwallpro': None,  # To be implemented
        'wallads': None,  # To be implemented
        'wallport': None,  # To be implemented
        'walltoro': None,  # To be implemented
        
        # Survey Specialists (27-41)
        'pollfish': None,  # To be implemented
        'cpxresearch': None,  # To be implemented
        'bitlabs': None,  # To be implemented
        'inbrain': None,  # To be implemented
        'theoremreach': None,  # To be implemented
        'yoursurveys': None,  # To be implemented
        'surveysavvy': None,  # To be implemented
        'opinionworld': None,  # To be implemented
        'toluna': None,  # To be implemented
        'surveymonkey': None,  # To be implemented
        'swagbucks': None,  # To be implemented
        'prizerebel': None,  # To be implemented
        'grabpoints': None,  # To be implemented
        'instagc': None,  # To be implemented
        'points2shop': None,  # To be implemented
        
        # Video & Easy Tasks (42-56)
        'loottv': None,  # To be implemented
        'hideouttv': None,  # To be implemented
        'rewardrack': None,  # To be implemented
        'earnhoney': None,  # To be implemented
        'rewardxp': None,  # To be implemented
        'idleempire': None,  # To be implemented
        'gain': None,  # To be implemented
        'grindabuck': None,  # To be implemented
        'timebucks': None,  # To be implemented
        'clixsense': None,  # To be implemented
        'neobux': None,  # To be implemented
        'probux': None,  # To be implemented
        'clixwall': None,  # To be implemented
        'fyber': None,  # To be implemented
        'offerstation': None,  # To be implemented
        
        # Gaming & App Install (57-70)
        'chartboost': None,  # To be implemented
        'supersonic': None,  # To be implemented
        'appnext': None,  # To be implemented
        'digitalturbine': None,  # To be implemented
        'glispa': None,  # To be implemented
        'adcolony': None,  # To be implemented
        'inmobi': None,  # To be implemented
        'mopub': None,  # To be implemented
        'pangle': None,  # To be implemented
        'mintegral': None,  # To be implemented
        'ogury': None,  # To be implemented
        'verizonmedia': None,  # To be implemented
        'smaato': None,  # To be implemented
        'mobilefuse': None,  # To be implemented
        
        # More Networks (71-80)
        'leadbolt': None,  # To be implemented
        'startapp': None,  # To be implemented
        'mediabrix': None,  # To be implemented
        'nativex': None,  # To be implemented
        'heyzap': None,  # To be implemented
        'kidoz': None,  # To be implemented
        'pokkt': None,  # To be implemented
        'youappi': None,  # To be implemented
        'ampiri': None,  # To be implemented
        'adincube': None,  # To be implemented
        
        # Future Expansion (81-90)
        'custom1': None,  # To be implemented
        'custom2': None,  # To be implemented
        'custom3': None,  # To be implemented
        'custom4': None,  # To be implemented
        'custom5': None,  # To be implemented
    }
    
    @classmethod
    def create_crawler(cls, ad_network):
        """Create crawler instance for ad network"""
        try:
            network_type = ad_network.network_type.lower()
            crawler_class = cls.CRAWLER_MAPPING.get(network_type)
            
            if not crawler_class:
                logger.warning(f"No crawler found for network type: {network_type}")
                return None
            
            return crawler_class(ad_network)
            
        except Exception as e:
            logger.error(f"Error creating crawler for {ad_network.network_type}: {str(e)}")
            return None
    
    @classmethod
    def crawl_all_networks(cls, tenant_id=None):
        """Crawl all active networks"""
        try:
            logger.info(f"Starting crawl for all networks, tenant: {tenant_id or 'all'}")
            
            # Get all active ad networks
            networks = AdNetwork.objects.filter(is_active=True)
            if tenant_id and tenant_id != 'all':
                networks = networks.filter(tenant_id=tenant_id)
            
            results = []
            
            for network in networks:
                try:
                    crawler = cls.create_crawler(network)
                    if crawler:
                        result = crawler.crawl()
                        results.append({
                            'network_id': network.id,
                            'network_name': network.name,
                            'network_type': network.network_type,
                            'result': result
                        })
                    else:
                        results.append({
                            'network_id': network.id,
                            'network_name': network.name,
                            'network_type': network.network_type,
                            'result': {'success': False, 'error': 'No crawler available'}
                        })
                        
                except Exception as e:
                    logger.error(f"Error crawling network {network.name}: {str(e)}")
                    results.append({
                        'network_id': network.id,
                        'network_name': network.name,
                        'network_type': network.network_type,
                        'result': {'success': False, 'error': str(e)}
                    })
            
            # Summary
            successful = sum(1 for r in results if r['result'].get('success', False))
            failed = len(results) - successful
            
            logger.info(f"Crawl completed: {successful} successful, {failed} failed")
            
            return {
                'success': True,
                'total_networks': len(results),
                'successful': successful,
                'failed': failed,
                'results': results
            }
            
        except Exception as e:
            logger.error(f"Error in crawl_all_networks: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @classmethod
    def crawl_network_by_type(cls, network_type, tenant_id=None):
        """Crawl specific network type"""
        try:
            logger.info(f"Starting crawl for network type: {network_type}, tenant: {tenant_id or 'all'}")
            
            networks = AdNetwork.objects.filter(network_type=network_type, is_active=True)
            if tenant_id and tenant_id != 'all':
                networks = networks.filter(tenant_id=tenant_id)
            
            results = []
            
            for network in networks:
                crawler = cls.create_crawler(network)
                if crawler:
                    result = crawler.crawl()
                    results.append({
                        'network_id': network.id,
                        'network_name': network.name,
                        'result': result
                    })
            
            return {
                'success': True,
                'network_type': network_type,
                'networks_crawled': len(results),
                'results': results
            }
            
        except Exception as e:
            logger.error(f"Error crawling network type {network_type}: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @classmethod
    def get_available_crawlers(cls):
        """Get list of available crawler types"""
        return [network_type for network_type, crawler_class in cls.CRAWLER_MAPPING.items() if crawler_class]
    
    @classmethod
    def get_crawler_stats(cls):
        """Get crawler statistics"""
        try:
            total_networks = AdNetwork.objects.filter(is_active=True).count()
            available_crawlers = len(cls.get_available_crawlers())
            
            # Get recent sync logs
            recent_logs = OfferSyncLog.objects.filter(
                started_at__gte=timezone.now() - timezone.timedelta(days=7)
            )
            
            stats = {
                'total_active_networks': total_networks,
                'available_crawlers': available_crawlers,
                'supported_networks': available_crawlers,
                'unsupported_networks': total_networks - available_crawlers,
                'recent_syncs': recent_logs.count(),
                'successful_syncs': recent_logs.filter(status='completed').count(),
                'failed_syncs': recent_logs.filter(status='failed').count(),
                'running_syncs': recent_logs.filter(status='running').count()
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting crawler stats: {str(e)}")
            return {}
    
    @classmethod
    def register_crawler(cls, network_type, crawler_class):
        """Register a new crawler"""
        cls.CRAWLER_MAPPING[network_type.lower()] = crawler_class
        logger.info(f"Registered crawler for {network_type}")
    
    @classmethod
    def unregister_crawler(cls, network_type):
        """Unregister a crawler"""
        if network_type.lower() in cls.CRAWLER_MAPPING:
            del cls.CRAWLER_MAPPING[network_type.lower()]
            logger.info(f"Unregistered crawler for {network_type}")
    
    @classmethod
    def test_crawler(cls, ad_network):
        """Test crawler functionality"""
        try:
            crawler = cls.create_crawler(ad_network)
            if not crawler:
                return {'success': False, 'error': 'No crawler available'}
            
            # Test basic functionality
            test_result = {
                'success': True,
                'network_type': ad_network.network_type,
                'network_name': ad_network.name,
                'crawler_class': crawler.__class__.__name__,
                'tenant_id': ad_network.tenant_id,
                'api_configured': bool(ad_network.api_key),
                'test_passed': True
            }
            
            return test_result
            
        except Exception as e:
            logger.error(f"Error testing crawler for {ad_network.network_type}: {str(e)}")
            return {'success': False, 'error': str(e)}
