# api/offer_inventory/publisher_sdk/__init__.py
"""
Publisher SDK — Self-serve publisher portal and SDK integration.
Publishers are app developers/website owners who embed the offerwall.
Handles: publisher registration, app management, revenue reporting,
SDK config generation, and payout to publishers.

This is the "supply side" — publishers supply traffic, advertisers supply offers.
"""
from .publisher_portal    import PublisherPortal
from .app_manager         import AppManager
from .publisher_analytics import PublisherAnalytics
from .sdk_config_generator import SDKConfigGenerator
from .publisher_payout    import PublisherPayoutManager

__all__ = [
    'PublisherPortal', 'AppManager', 'PublisherAnalytics',
    'SDKConfigGenerator', 'PublisherPayoutManager',
]
