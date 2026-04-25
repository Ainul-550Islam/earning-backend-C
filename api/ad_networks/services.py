"""
api/ad_networks/services.py
Main services module - imports all service classes
SaaS-ready with tenant support
"""

# Core Services
from .services.ConversionService import ConversionService
from .services.FraudDetectionService import FraudDetectionService
from .services.NetworkHealthService import NetworkHealthService
from .services.OfferSyncService import OfferSyncService
from .services.RewardService import RewardService
from .services.OfferRecommendService import OfferRecommendService

# Network-Specific Services
from .services.AdNetworkBase import AdNetworkBase
from .services.AdNetworkFactory import AdNetworkFactory
from .services.AdmobService import AdmobService
from .services.UnityAdsService import UnityAdsService
from .services.IronSourceService import IronSourceService
from .services.AppLovinService import AppLovinService

# Utility Services
from .services.OfferAnalyticsService import OfferAnalyticsService
from .services.UserService import UserService
from .services.ReportService import ReportService
from .services.NotificationService import NotificationService

__all__ = [
    # Core Services
    'ConversionService',
    'FraudDetectionService',
    'NetworkHealthService',
    'OfferSyncService',
    'RewardService',
    'OfferRecommendService',
    
    # Network Services
    'AdNetworkBase',
    'AdNetworkFactory',
    'AdmobService',
    'UnityAdsService',
    'IronSourceService',
    'AppLovinService',
    
    # Utility Services
    'OfferAnalyticsService',
    'UserService',
    'ReportService',
    'NotificationService',
]

# Service registry for easy access
SERVICE_REGISTRY = {
    'conversion': ConversionService,
    'fraud_detection': FraudDetectionService,
    'network_health': NetworkHealthService,
    'offer_sync': OfferSyncService,
    'reward': RewardService,
    'offer_recommend': OfferRecommendService,
    'offer_analytics': OfferAnalyticsService,
    'user': UserService,
    'report': ReportService,
    'notification': NotificationService,
}

def get_service(service_name: str, tenant_id: str = None, **kwargs):
    """
    Get service instance by name
    
    Args:
        service_name: Name of the service
        tenant_id: Tenant ID for multi-tenant support
        **kwargs: Additional arguments for service initialization
    
    Returns:
        Service instance or None if not found
    """
    service_class = SERVICE_REGISTRY.get(service_name)
    if not service_class:
        raise ValueError(f"Service '{service_name}' not found")
    
    return service_class(tenant_id=tenant_id, **kwargs)

def list_available_services():
    """
    Get list of all available services
    
    Returns:
        List of service names
    """
    return list(SERVICE_REGISTRY.keys())
