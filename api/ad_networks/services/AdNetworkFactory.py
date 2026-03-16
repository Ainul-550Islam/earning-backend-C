from .AdmobService import AdmobService
from .UnityAdsService import UnityAdsService
from .IronSourceService import IronSourceService
from .AppLovinService import AppLovinService
from ..models import AdNetwork


class AdNetworkFactory:
    """Factory to get appropriate ad network service"""
    
    SERVICES = {
        'admob': AdmobService,
        'unity': UnityAdsService,
        'ironsource': IronSourceService,
        'applovin': AppLovinService,
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