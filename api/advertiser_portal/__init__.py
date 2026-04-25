"""
Advertiser Portal - High-end Advertising Management System

A comprehensive Django REST Framework application for managing advertisers,
campaigns, creatives, targeting, bidding, analytics, and billing.

Core Features:
- Advertiser Management & Verification
- Campaign Management & Optimization
- Creative Management & Approval
- Advanced Targeting Engines
- Real-time Bidding & Optimization
- Performance Analytics & Reporting
- Billing & Payment Processing
- Fraud Prevention & Detection
- A/B Testing & Multivariate Testing
- Third-party Integrations
"""

__version__ = "1.0.0"
__author__ = "Advertiser Portal Team"
__email__ = "tech@advertiserportal.com"

default_app_config = "api.advertiser_portal.apps.AdvertiserPortalConfig"

# All modules are imported through Django's app registry
# No direct imports needed here to avoid "Apps aren't loaded yet" error

# Export all main components
__all__ = [
    # Version info
    '__version__',
    '__author__',
    '__email__',
    'default_app_config',
    'AdvertiserProfile', 
    'AdvertiserVerification',
    'AdvertiserAgreement',
    'AdCampaign',
    'CampaignCreative',
    'CampaignTargeting',
    'CampaignBid',
    'CampaignSchedule',
    'AdvertiserOffer',
    'OfferRequirement',
    'OfferCreative',
    'OfferBlacklist',
    'TrackingPixel',
    'S2SPostback',
    'Conversion',
    'ConversionEvent',
    'TrackingDomain',
    'AdvertiserWallet',
    'AdvertiserTransaction',
    'AdvertiserDeposit',
    'AdvertiserInvoice',
    'CampaignSpend',
    'BillingAlert',
    'AdvertiserReport',
    'CampaignReport',
    'PublisherBreakdown',
    'GeoBreakdown',
    'CreativePerformance',
    'ConversionQualityScore',
    'AdvertiserFraudConfig',
    'InvalidClickLog',
    'ClickFraudSignal',
    'OfferQualityScore',
    'RoutingBlacklist',
    'AdvertiserNotification',
    'AdvertiserAlert',
    'NotificationTemplate',
    'UserJourneyStep',
    'NetworkPerformanceCache',
    'MLModel',
    'MLPrediction',
    
    # Core classes (will be imported from their respective modules)
    # 'BaseAPIView',
    # 'StandardResultsSetPagination',
    # 'BaseValidator',
    # 'BaseAdvertiserPortalException',
    # 'ExceptionHandler',
    # 'ValidatorFactory',
    
    # Utility classes
    'AdvertiserUtils',
    'CampaignUtils',
    'OfferUtils',
    'TrackingUtils',
    'BillingUtils',
    'FraudUtils',
    'NotificationUtils',
    'ReportUtils',
    'MLUtils',
    
    # Constants classes
    'StatusConstants',
    'CampaignConstants',
    'OfferConstants',
    'TrackingConstants',
    'BillingConstants',
    'FraudConstants',
    'NotificationConstants',
    'ReportConstants',
    'MLConstants',
    'CreativeConstants',
    'TargetingConstants',
    'ValidationConstants',
    'SystemConstants',
    'CacheConstants',
    'APIConstants',
]
