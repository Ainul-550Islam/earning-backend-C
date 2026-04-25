from .AdmobService import AdmobService
from .UnityAdsService import UnityAdsService
from .IronSourceService import IronSourceService
from .AppLovinService import AppLovinService
from .AdscendService import AdscendService
from .OfferToroService import OfferToroService
from .AdGemService import AdGemService
from ..models import AdNetwork


class AdNetworkFactory:
    """Factory to get appropriate ad network service"""
    
    SERVICES = {
        # Basic Networks (1-6)
        'admob': AdmobService,
        'unity': UnityAdsService,
        'ironsource': IronSourceService,
        'applovin': AppLovinService,
        'tapjoy': None,  # To be implemented
        'vungle': None,  # To be implemented
        
        # Top Offerwalls (7-26)
        'adscend': AdscendService,
        'offertoro': OfferToroService,
        'adgem': AdGemService,
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
    
    @staticmethod
    def get_service(network_type):
        """Get service instance for network type"""
        try:
            ad_network = AdNetwork.objects.get(network_type=network_type)
            service_class = AdNetworkFactory.SERVICES.get(network_type)
            
            if not service_class:
                raise ValueError(f"Unsupported ad network: {network_type}")
            
            return service_class(ad_network)
        except AdNetwork.DoesNotExist:
            raise ValueError(f"Ad network not configured: {network_type}")