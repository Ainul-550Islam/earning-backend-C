"""
api/ad_networks/urls_modern_features.py
URL configuration for modern features based on internet research
SaaS-ready with tenant support
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views_modern_features import (
    RealTimeBidViewSet, PredictiveAnalyticsViewSet, PrivacyComplianceViewSet,
    ProgrammaticCampaignViewSet, MLFraudDetectionViewSet, CrossPlatformAttributionViewSet,
    DynamicCreativeViewSet, VoiceAdViewSet, Web3TransactionViewSet,
    MetaverseAdViewSet, UserPrivacyComplianceViewSet, UserAttributionViewSet
)

# ==================== ROUTER CONFIGURATION ====================

router = DefaultRouter()

# Admin/API ViewSets
router.register(r'realtime-bids', RealTimeBidViewSet, basename='realtime-bid')
router.register(r'predictive-analytics', PredictiveAnalyticsViewSet, basename='predictive-analytics')
router.register(r'privacy-compliance', PrivacyComplianceViewSet, basename='privacy-compliance')
router.register(r'programmatic-campaigns', ProgrammaticCampaignViewSet, basename='programmatic-campaign')
router.register(r'fraud-detection', MLFraudDetectionViewSet, basename='fraud-detection')
router.register(r'cross-platform-attribution', CrossPlatformAttributionViewSet, basename='cross-platform-attribution')
router.register(r'dynamic-creative', DynamicCreativeViewSet, basename='dynamic-creative')
router.register(r'voice-ads', VoiceAdViewSet, basename='voice-ad')
router.register(r'web3-transactions', Web3TransactionViewSet, basename='web3-transaction')
router.register(r'metaverse-ads', MetaverseAdViewSet, basename='metaverse-ad')

# User-facing ViewSets
router.register(r'user/privacy-compliance', UserPrivacyComplianceViewSet, basename='user-privacy-compliance')
router.register(r'user/attribution', UserAttributionViewSet, basename='user-attribution')

# ==================== URL PATTERNS ====================

app_name = 'ad_networks'

urlpatterns = [
    # Modern Features API endpoints
    path('api/v1/', include(router.urls)),
    
    # Real-time Bidding endpoints
    path('api/v1/rtb/', include([
        path('bids/', RealTimeBidViewSet.as_view({'get': 'list', 'post': 'create'}), name='rtb-bid-list'),
        path('bids/<uuid:pk>/', RealTimeBidViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='rtb-bid-detail'),
        path('bids/statistics/', RealTimeBidViewSet.as_view({'get': 'statistics'}), name='rtb-statistics'),
        path('bids/bulk-create/', RealTimeBidViewSet.as_view({'post': 'bulk_create'}), name='rtb-bulk-create'),
    ])),
    
    # Predictive Analytics endpoints
    path('api/v1/analytics/', include([
        path('predictions/', PredictiveAnalyticsViewSet.as_view({'get': 'list', 'post': 'create'}), name='analytics-prediction-list'),
        path('predictions/<uuid:pk>/', PredictiveAnalyticsViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='analytics-prediction-detail'),
        path('predictions/<uuid:pk>/train/', PredictiveAnalyticsViewSet.as_view({'post': 'train_model'}), name='analytics-train-model'),
        path('predictions/performance/', PredictiveAnalyticsViewSet.as_view({'get': 'model_performance'}), name='analytics-model-performance'),
    ])),
    
    # Privacy Compliance endpoints
    path('api/v1/privacy/', include([
        path('consents/', PrivacyComplianceViewSet.as_view({'get': 'list', 'post': 'create'}), name='privacy-consent-list'),
        path('consents/<uuid:pk>/', PrivacyComplianceViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='privacy-consent-detail'),
        path('consents/record/', PrivacyComplianceViewSet.as_view({'post': 'record_consent'}), name='privacy-record-consent'),
        path('consents/<uuid:pk>/revoke/', PrivacyComplianceViewSet.as_view({'post': 'revoke_consent'}), name='privacy-revoke-consent'),
        path('consents/report/', PrivacyComplianceViewSet.as_view({'get': 'compliance_report'}), name='privacy-compliance-report'),
    ])),
    
    # Programmatic Campaign endpoints
    path('api/v1/programmatic/', include([
        path('campaigns/', ProgrammaticCampaignViewSet.as_view({'get': 'list', 'post': 'create'}), name='programmatic-campaign-list'),
        path('campaigns/<uuid:pk>/', ProgrammaticCampaignViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='programmatic-campaign-detail'),
        path('campaigns/<uuid:pk>/launch/', ProgrammaticCampaignViewSet.as_view({'post': 'launch_campaign'}), name='programmatic-launch-campaign'),
        path('campaigns/<uuid:pk>/pause/', ProgrammaticCampaignViewSet.as_view({'post': 'pause_campaign'}), name='programmatic-pause-campaign'),
        path('campaigns/performance/', ProgrammaticCampaignViewSet.as_view({'get': 'campaign_performance'}), name='programmatic-campaign-performance'),
    ])),
    
    # Fraud Detection endpoints
    path('api/v1/fraud/', include([
        path('detections/', MLFraudDetectionViewSet.as_view({'get': 'list', 'post': 'create'}), name='fraud-detection-list'),
        path('detections/<uuid:pk>/', MLFraudDetectionViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='fraud-detection-detail'),
        path('detections/<uuid:pk>/review/', MLFraudDetectionViewSet.as_view({'post': 'review_detection'}), name='fraud-review-detection'),
        path('detections/statistics/', MLFraudDetectionViewSet.as_view({'get': 'fraud_statistics'}), name='fraud-statistics'),
    ])),
    
    # Cross-Platform Attribution endpoints
    path('api/v1/attribution/', include([
        path('attributions/', CrossPlatformAttributionViewSet.as_view({'get': 'list', 'post': 'create'}), name='attribution-list'),
        path('attributions/<uuid:pk>/', CrossPlatformAttributionViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='attribution-detail'),
        path('attributions/create/', CrossPlatformAttributionViewSet.as_view({'post': 'create_attribution'}), name='attribution-create'),
        path('attributions/report/', CrossPlatformAttributionViewSet.as_view({'get': 'attribution_report'}), name='attribution-report'),
    ])),
    
    # Dynamic Creative endpoints
    path('api/v1/creative/', include([
        path('creatives/', DynamicCreativeViewSet.as_view({'get': 'list', 'post': 'create'}), name='creative-list'),
        path('creatives/<uuid:pk>/', DynamicCreativeViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='creative-detail'),
        path('creatives/<uuid:pk>/optimize/', DynamicCreativeViewSet.as_view({'post': 'optimize_creative'}), name='creative-optimize'),
        path('creatives/<uuid:pk>/winner/', DynamicCreativeViewSet.as_view({'post': 'declare_winner'}), name='creative-declare-winner'),
        path('creatives/performance/', DynamicCreativeViewSet.as_view({'get': 'creative_performance'}), name='creative-performance'),
    ])),
    
    # Voice Ad endpoints
    path('api/v1/voice/', include([
        path('ads/', VoiceAdViewSet.as_view({'get': 'list', 'post': 'create'}), name='voice-ad-list'),
        path('ads/<uuid:pk>/', VoiceAdViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='voice-ad-detail'),
        path('ads/<uuid:pk>/play/', VoiceAdViewSet.as_view({'post': 'play_ad'}), name='voice-play-ad'),
        path('ads/performance/', VoiceAdViewSet.as_view({'get': 'voice_performance'}), name='voice-performance'),
    ])),
    
    # Web3 Transaction endpoints
    path('api/v1/web3/', include([
        path('transactions/', Web3TransactionViewSet.as_view({'get': 'list', 'post': 'create'}), name='web3-transaction-list'),
        path('transactions/<uuid:pk>/', Web3TransactionViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='web3-transaction-detail'),
        path('transactions/<uuid:pk>/confirm/', Web3TransactionViewSet.as_view({'post': 'confirm_transaction'}), name='web3-confirm-transaction'),
        path('transactions/blockchain-stats/', Web3TransactionViewSet.as_view({'get': 'blockchain_stats'}), name='web3-blockchain-stats'),
    ])),
    
    # Metaverse Ad endpoints
    path('api/v1/metaverse/', include([
        path('ads/', MetaverseAdViewSet.as_view({'get': 'list', 'post': 'create'}), name='metaverse-ad-list'),
        path('ads/<uuid:pk>/', MetaverseAdViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='metaverse-ad-detail'),
        path('ads/<uuid:pk>/place/', MetaverseAdViewSet.as_view({'post': 'place_ad'}), name='metaverse-place-ad'),
        path('ads/performance/', MetaverseAdViewSet.as_view({'get': 'metaverse_performance'}), name='metaverse-performance'),
    ])),
    
    # User-facing endpoints
    path('api/v1/user/', include([
        path('privacy/consents/', UserPrivacyComplianceViewSet.as_view({'get': 'my_consents'}), name='user-my-consents'),
        path('privacy/consents/update/', UserPrivacyComplianceViewSet.as_view({'post': 'update_consent_preferences'}), name='user-update-consent'),
        path('attribution/attributions/', UserAttributionViewSet.as_view({'get': 'my_attributions'}), name='user-my-attributions'),
    ])),
    
    # WebSocket endpoints for real-time features
    path('ws/rtb/', include('api.ad_networks.routing.websocket_urls')),
    path('ws/analytics/', include('api.ad_networks.routing.websocket_urls')),
    path('ws/fraud/', include('api.ad_networks.routing.websocket_urls')),
]

# ==================== API VERSIONING ====================

# API v1 URLs (current version)
api_v1_urls = [
    path('api/v1/', include([
        path('networks/', include(router.urls)),
        path('rtb/', include([
            path('bids/', RealTimeBidViewSet.as_view({'get': 'list'}), name='rtb-bids-v1'),
            path('bids/<uuid:pk>/', RealTimeBidViewSet.as_view({'get': 'retrieve'}), name='rtb-bid-detail-v1'),
        ])),
        path('analytics/', include([
            path('predictions/', PredictiveAnalyticsViewSet.as_view({'get': 'list'}), name='analytics-predictions-v1'),
            path('predictions/<uuid:pk>/', PredictiveAnalyticsViewSet.as_view({'get': 'retrieve'}), name='analytics-prediction-detail-v1'),
        ])),
    ])),
]

# API v2 URLs (future version with additional features)
api_v2_urls = [
    path('api/v2/', include([
        path('networks/', include(router.urls)),
        path('ml/', include([
            path('fraud-detection/', MLFraudDetectionViewSet.as_view({'get': 'list'}), name='ml-fraud-detection-v2'),
            path('predictive-analytics/', PredictiveAnalyticsViewSet.as_view({'get': 'list'}), name='ml-predictive-analytics-v2'),
        ])),
        path('web3/', include([
            path('transactions/', Web3TransactionViewSet.as_view({'get': 'list'}), name='web3-transactions-v2'),
            path('smart-contracts/', include('api.ad_networks.web3.urls')),
        ])),
        path('metaverse/', include([
            path('ads/', MetaverseAdViewSet.as_view({'get': 'list'}), name='metaverse-ads-v2'),
            path('virtual-worlds/', include('api.ad_networks.metaverse.urls')),
        ])),
    ])),
]

# ==================== URL INCLUDES ====================

# For inclusion in main urls.py
modern_features_urls = [
    path('ad-networks/', include('api.ad_networks.urls_modern_features')),
]

# ==================== EXPORTS ====================

__all__ = [
    'router',
    'urlpatterns',
    'api_v1_urls',
    'api_v2_urls',
    'modern_features_urls',
]
