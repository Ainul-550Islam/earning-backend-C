# publisher_tools/ad_network_integration/__init__.py
# ============================================================
# Exports ad network integration logic.
# Used by: services.py (MediationService), views.py (WaterfallItemViewSet)
#
# Usage:
#   from .ad_network_integration import get_enabled_networks
#   from .ad_network_integration import get_network_performance
# ============================================================

# ── Network manager (core) ────────────────────────────────────────────────────
from .network_manager import (
    get_enabled_networks,
    get_network_performance,
)

# ── Individual network config classes (lazy imports to avoid circular deps) ───
# Access via: from publisher_tools.ad_network_integration.admob_integration import AdMobConfig

def get_admob_config():
    from .admob_integration import AdMobConfig
    return AdMobConfig

def get_applovin_config():
    from .applovin_integration import AppLovinConfig
    return AppLovinConfig

def get_facebook_an_config():
    from .facebook_audience import FacebookAudienceNetworkConfig
    return FacebookAudienceNetworkConfig

def get_ironsource_config():
    from .ironsource_integration import IronSourceConfig
    return IronSourceConfig

def get_unity_ads_config():
    from .unity_ads_integration import UnityAdsConfig
    return UnityAdsConfig

def get_google_ad_manager_config():
    from .google_ad_manager import GoogleAdManagerConfig
    return GoogleAdManagerConfig

def get_prebid_config():
    from .prebid_integration import PrebidConfig
    return PrebidConfig

# ── Network name → config class mapping ──────────────────────────────────────
NETWORK_CONFIG_MAP = {
    'admob':            'admob_integration.AdMobConfig',
    'applovin':         'applovin_integration.AppLovinConfig',
    'facebook_an':      'facebook_audience.FacebookAudienceNetworkConfig',
    'ironsource':       'ironsource_integration.IronSourceConfig',
    'unity_ads':        'unity_ads_integration.UnityAdsConfig',
    'google_ad_manager':'google_ad_manager.GoogleAdManagerConfig',
    'prebid':           'prebid_integration.PrebidConfig',
    'amazon_publisher': 'amazon_publisher.AmazonPublisherServicesConfig',
    'pubmatic':         'pubmatic_integration.PubMaticConfig',
    'rubicon':          'rubicon_project.RubiconProjectConfig',
    'index_exchange':   'index_exchange.IndexExchangeConfig',
    'openx':            'openx_integration.OpenXConfig',
    'sovrn':            'sovrn_integration.SovrnConfig',
    'vungle':           'vungle_integration.VungleConfig',
    'tapjoy':           'tapjoy_integration.TapjoyConfig',
    'chartboost':       'chartboost_integration.ChartboostConfig',
    'fyber':            'fyber_integration.FyberConfig',
    'triplelift':       'triplelift_integration.TripleLiftConfig',
    'verizon_media':    'verizon_media.VerizonMediaConfig',
}

def get_network_config_class(network_name: str):
    """Dynamically load a network config class by name."""
    mapping = NETWORK_CONFIG_MAP.get(network_name.lower())
    if not mapping:
        raise ValueError(f'Unknown network: {network_name}. Available: {list(NETWORK_CONFIG_MAP.keys())}')
    module_name, class_name = mapping.rsplit('.', 1)
    import importlib
    mod = importlib.import_module(f'.{module_name}', package='publisher_tools.ad_network_integration')
    return getattr(mod, class_name)

__all__ = [
    'get_enabled_networks',
    'get_network_performance',
    'get_network_config_class',
    'NETWORK_CONFIG_MAP',
    'get_admob_config',
    'get_applovin_config',
    'get_facebook_an_config',
    'get_ironsource_config',
    'get_unity_ads_config',
    'get_google_ad_manager_config',
    'get_prebid_config',
]
