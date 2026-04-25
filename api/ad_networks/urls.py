# api/ad_networks/urls.py
# SaaS-Ready Multi-Tenant URL Configuration with Complete ViewSet Registration

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_nested import routers

from .views import (
    # Core ViewSets
    OfferCategoryViewSet,
    OfferViewSet,
    UserOfferEngagementViewSet,
    OfferConversionViewSet,
    OfferWallViewSet,
    
    # Network ViewSets
    AdNetworkViewSet,
    NetworkHealthCheckViewSet,
    
    # Analytics ViewSets
    AnalyticsViewSet,
    NetworkStatisticViewSet,
    SmartOfferRecommendationViewSet,
    
    # Fraud Detection ViewSets
    FraudDetectionRuleViewSet,
    BlacklistedIPViewSet,
    KnownBadIPViewSet,
    
    # User Management ViewSets
    UserOfferLimitViewSet,
    
    # Offer Management ViewSets
    OfferClickViewSet,
    OfferRewardViewSet,
    OfferTagViewSet,
    OfferTaggingViewSet,
    
    # System Management ViewSets
    OfferSyncLogViewSet,
    AdNetworkWebhookLogViewSet,
    OfferDailyLimitViewSet,
    
    # Additional ViewSets
    OfferAttachmentViewSet,
    UserWalletViewSet,
    
    # Utility ViewSets
    UtilityViewSet,
)

# ============================================================================
# MAIN ROUTER
# ============================================================================

router = DefaultRouter()

# Core API Endpoints
router.register(r'categories', OfferCategoryViewSet, basename='offer-category')
router.register(r'offers', OfferViewSet, basename='offer')
router.register(r'engagements', UserOfferEngagementViewSet, basename='engagement')
router.register(r'conversions', OfferConversionViewSet, basename='conversion')
router.register(r'walls', OfferWallViewSet, basename='offer-wall')

# Network Management
router.register(r'networks', AdNetworkViewSet, basename='ad-network')
router.register(r'network-health', NetworkHealthCheckViewSet, basename='network-health')

# Analytics & Reporting
router.register(r'analytics', AnalyticsViewSet, basename='analytics')
router.register(r'statistics', NetworkStatisticViewSet, basename='network-statistic')
router.register(r'recommendations', SmartOfferRecommendationViewSet, basename='smart-recommendation')

# Fraud Detection & Security
router.register(r'fraud-rules', FraudDetectionRuleViewSet, basename='fraud-rule')
router.register(r'blacklisted-ips', BlacklistedIPViewSet, basename='blacklisted-ip')
router.register(r'known-bad-ips', KnownBadIPViewSet, basename='known-bad-ip')

# User Management
router.register(r'user-limits', UserOfferLimitViewSet, basename='user-limit')

# Offer Management
router.register(r'clicks', OfferClickViewSet, basename='offer-click')
router.register(r'rewards', OfferRewardViewSet, basename='offer-reward')
router.register(r'tags', OfferTagViewSet, basename='offer-tag')
router.register(r'tagging', OfferTaggingViewSet, basename='offer-tagging')

# System Management
router.register(r'sync-logs', OfferSyncLogViewSet, basename='offer-sync')
router.register(r'webhook-logs', AdNetworkWebhookLogViewSet, basename='webhook-log')
router.register(r'daily-limits', OfferDailyLimitViewSet, basename='daily-limit')

# Additional Endpoints
router.register(r'attachments', OfferAttachmentViewSet, basename='offer-attachment')
router.register(r'wallets', UserWalletViewSet, basename='user-wallet')
router.register(r'users', UserOfferEngagementViewSet, basename='user')

# Utility Endpoints
router.register(r'utilities', UtilityViewSet, basename='utility')

# ============================================================================
# NESTED ROUTERS
# ============================================================================

# Offers nested router
offers_router = routers.NestedDefaultRouter(router, r'offers', lookup='offer')
offers_router.register(r'clicks', OfferClickViewSet, basename='offer-clicks')
offers_router.register(r'rewards', OfferRewardViewSet, basename='offer-rewards')
offers_router.register(r'tags', OfferTaggingViewSet, basename='offer-taggings')

# Categories nested router
categories_router = routers.NestedDefaultRouter(router, r'categories', lookup='category')
categories_router.register(r'offers', OfferViewSet, basename='category-offers')

# Networks nested router
networks_router = routers.NestedDefaultRouter(router, r'networks', lookup='network')
networks_router.register(r'health-checks', NetworkHealthCheckViewSet, basename='network-health-checks')
networks_router.register(r'statistics', NetworkStatisticViewSet, basename='network-statistics')
networks_router.register(r'sync-logs', OfferSyncLogViewSet, basename='network-sync-logs')
networks_router.register(r'webhook-logs', AdNetworkWebhookLogViewSet, basename='network-webhook-logs')

# Users nested router (for user-specific endpoints)
users_router = routers.NestedDefaultRouter(router, r'users', lookup='user')
users_router.register(r'engagements', UserOfferEngagementViewSet, basename='user-engagements')
users_router.register(r'limits', UserOfferLimitViewSet, basename='user-limits')
users_router.register(r'recommendations', SmartOfferRecommendationViewSet, basename='user-recommendations')
users_router.register(r'daily-limits', OfferDailyLimitViewSet, basename='user-daily-limits')

# ============================================================================
# WEBHOOK ROUTES
# ============================================================================

# Webhook endpoints for external integrations
webhook_patterns = [
    # Network webhooks
    path('webhooks/networks/<str:network_id>/', AdNetworkWebhookLogViewSet.as_view({'post': 'create'}), name='network-webhook'),
    path('webhooks/networks/<str:network_id>/callback/', AdNetworkWebhookLogViewSet.as_view({'post': 'callback'}), name='network-webhook-callback'),
    
    # Offer webhooks
    path('webhooks/offers/<str:offer_id>/', AdNetworkWebhookLogViewSet.as_view({'post': 'offer_webhook'}), name='offer-webhook'),
    path('webhooks/offers/<str:offer_id>/conversion/', AdNetworkWebhookLogViewSet.as_view({'post': 'conversion_webhook'}), name='offer-conversion-webhook'),
    
    # Conversion webhooks
    path('webhooks/conversions/<str:conversion_id>/', AdNetworkWebhookLogViewSet.as_view({'post': 'conversion_update'}), name='conversion-webhook'),
    
    # Generic webhook endpoint
    path('webhooks/', AdNetworkWebhookLogViewSet.as_view({'post': 'generic_webhook'}), name='generic-webhook'),
]

# ============================================================================
# API VERSIONING
# ============================================================================

# API Version 1
v1_router = DefaultRouter()
# v1_router merged with main router

# ============================================================================
# URL PATTERNS
# ============================================================================

app_name = 'ad_networks'

urlpatterns = [
    # Main API endpoint
    path('api/v1/', include(router.urls)),
    
    # Versioned endpoints
    path('api/', include([
        path('v1/', include(router.urls)),
    ])),
    
    # Webhook endpoints
    path('api/v1/', include(webhook_patterns)),
    
    # Network-specific webhooks
    path('webhooks/', include('api.ad_networks.webhooks.urls')),
    
    # Direct endpoint (for backward compatibility)
    path('', include(router.urls)),
]

# ============================================================================
# API METADATA
# ============================================================================

API_DESCRIPTION = """
Ad Networks API - SaaS-Ready Multi-Tenant Architecture

This API provides comprehensive functionality for managing ad networks, offers, 
user engagements, conversions, and analytics with full multi-tenant support.

Features:
- Multi-tenant isolation
- Fraud detection and prevention
- Real-time analytics
- Advanced filtering and search
- Bulk operations support
- Webhook integration
- Performance optimization
"""

API_VERSIONS = {
    'v1': {
        'status': 'current',
        'deprecated': False,
        'description': 'Current stable version with full SaaS features'
    }
}

ENDPOINT_PERMISSIONS = {
    'public': [
        'categories.list',
        'offers.list',
        'offers.retrieve',
        'walls.list',
        'walls.default',
        'utilities.choices'
    ],
    'user': [
        'engagements.*',
        'conversions.*',
        'clicks.*',
        'rewards.my_rewards',
        'recommendations.for_user',
        'analytics.user_stats'
    ],
    'admin': [
        'networks.*',
        'fraud-rules.*',
        'blacklisted-ips.*',
        'known-bad-ips.*',
        'user-limits.*',
        'sync-logs.*',
        'webhook-logs.*',
        'daily-limits.*',
        'utilities.clear_cache',
        'analytics.dashboard'
    ],
    'super_admin': [
        '*.*'  # Full access
    ]
}

RATE_LIMITS = {
    'public': {
        'requests_per_minute': 100,
        'requests_per_hour': 1000,
        'requests_per_day': 10000
    },
    'user': {
        'requests_per_minute': 200,
        'requests_per_hour': 2000,
        'requests_per_day': 20000
    },
    'admin': {
        'requests_per_minute': 500,
        'requests_per_hour': 5000,
        'requests_per_day': 50000
    },
    'super_admin': {
        'requests_per_minute': 1000,
        'requests_per_hour': 10000,
        'requests_per_day': 100000
    }
}

# ============================================================================
# WEBHOOK CONFIGURATION
# ============================================================================

WEBHOOK_EVENTS = {
    'network.created': 'Network created',
    'network.updated': 'Network updated',
    'network.deleted': 'Network deleted',
    'offer.created': 'Offer created',
    'offer.updated': 'Offer updated',
    'offer.deleted': 'Offer deleted',
    'engagement.started': 'User started offer',
    'engagement.completed': 'User completed offer',
    'conversion.pending': 'Conversion pending',
    'conversion.approved': 'Conversion approved',
    'conversion.rejected': 'Conversion rejected',
    'reward.paid': 'Reward paid',
    'fraud.detected': 'Fraud detected',
    'system.alert': 'System alert'
}

WEBHOOK_SECURITY = {
    'signature_required': True,
    'signature_header': 'X-Webhook-Signature',
    'timestamp_header': 'X-Webhook-Timestamp',
    'tolerance_seconds': 300,  # 5 minutes
    'allowed_ips': [],  # Empty means allow all IPs
    'rate_limit': {
        'per_minute': 100,
        'per_hour': 1000
    }
}

# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    'urlpatterns',
    'app_name',
    'API_DESCRIPTION',
    'API_VERSIONS',
    'ENDPOINT_PERMISSIONS',
    'RATE_LIMITS',
    'WEBHOOK_EVENTS',
    'WEBHOOK_SECURITY'
]
