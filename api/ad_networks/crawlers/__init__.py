"""
api/ad_networks/crawlers package
SaaS-Ready Multi-Tenant Offer Crawlers
"""

# Base crawler
from .OfferCrawler import OfferCrawler

# Network-specific crawlers
from .AdMobCrawler import AdMobCrawler
from .UnityAdsCrawler import UnityAdsCrawler
from .IronSourceCrawler import IronSourceCrawler
from .AppLovinCrawler import AppLovinCrawler
from .TapjoyCrawler import TapjoyCrawler
from .AdscendCrawler import AdscendCrawler
from .OfferToroCrawler import OfferToroCrawler

# Factory
from .CrawlerFactory import CrawlerFactory

__all__ = [
    # Base
    'OfferCrawler',
    
    # Network Crawlers
    'AdMobCrawler',
    'UnityAdsCrawler',
    'IronSourceCrawler',
    'AppLovinCrawler',
    'TapjoyCrawler',
    'AdscendCrawler',
    'OfferToroCrawler',
    
    # Factory
    'CrawlerFactory',
]

# Crawler registry for dynamic loading
CRAWLER_REGISTRY = {
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

def get_crawler(network_type: str, ad_network):
    """
    Get crawler instance for network type
    
    Args:
        network_type: Type of ad network (e.g., 'admob', 'tapjoy')
        ad_network: AdNetwork model instance
    
    Returns:
        Crawler instance or None if not found
    """
    crawler_class = CRAWLER_REGISTRY.get(network_type.lower())
    if crawler_class:
        return crawler_class(ad_network)
    return None

def register_crawler(network_type: str, crawler_class):
    """
    Register a new crawler
    
    Args:
        network_type: Network type identifier
        crawler_class: Crawler class
    """
    CRAWLER_REGISTRY[network_type.lower()] = crawler_class

def get_available_crawlers():
    """
    Get list of available crawler types
    
    Returns:
        List of registered crawler types
    """
    return list(CRAWLER_REGISTRY.keys())
