"""
Advertiser Portal URL Configuration

This module contains the main URL configuration for the Advertiser Portal,
including all module URL patterns and API routing.
"""

from django.urls import path, include
from rest_framework.routers import SimpleRouter as DefaultRouter
from django.conf import settings
from django.conf.urls.static import static

# Import module URL patterns
from .advertiser_management.urls import advertiser_urls
from .campaign_management.urls import campaign_urls
from .creative_management.urls import creative_urls
from .targeting_management.urls import targeting_urls
from .analytics_management.urls import analytics_urls
from .billing_management.urls import billing_urls

# Import main views
from .views import (
    # Advertiser views
    advertiser_list_create, advertiser_detail, advertiser_profile, advertiser_verification,
    # Campaign views
    campaign_list_create, campaign_detail, campaign_creatives, campaign_targeting,
    # Offer views
    offer_list_create, offer_detail,
    # Tracking views
    tracking_pixel_list_create, tracking_pixel_detail, tracking_pixel_fire, conversion_list_create,
    # Billing views
    wallet_detail, transaction_list_create, deposit_create, invoice_list, invoice_detail,
    # Reporting views
    report_list_create, report_detail, dashboard_metrics, performance_metrics,
    # Fraud detection views
    fraud_metrics, conversion_quality_scores,
    # Notification views
    notification_list_create, notification_mark_read,
    # Utility views
    system_health, system_stats
)

# Create main router
router = DefaultRouter()

# Register all 18 viewsets
from api.advertiser_portal.viewsets.AdvertiserViewSet import AdvertiserViewSet
from api.advertiser_portal.viewsets.AdminAdvertiserViewSet import AdminAdvertiserViewSet
from api.advertiser_portal.viewsets.AdvertiserProfileViewSet import AdvertiserProfileViewSet
from api.advertiser_portal.viewsets.AdvertiserVerificationViewSet import AdvertiserVerificationViewSet
from api.advertiser_portal.viewsets.AdvertiserOfferViewSet import AdvertiserOfferViewSet
from api.advertiser_portal.viewsets.AdvertiserWalletViewSet import AdvertiserWalletViewSet
from api.advertiser_portal.viewsets.AdvertiserInvoiceViewSet import AdvertiserInvoiceViewSet
from api.advertiser_portal.viewsets.AdvertiserNotificationViewSet import AdvertiserNotificationViewSet
from api.advertiser_portal.viewsets.AdCampaignViewSet import AdCampaignViewSet
from api.advertiser_portal.viewsets.CampaignBidViewSet import CampaignBidViewSet
from api.advertiser_portal.viewsets.CampaignCreativeViewSet import CampaignCreativeViewSet
from api.advertiser_portal.viewsets.CampaignTargetingViewSet import CampaignTargetingViewSet
from api.advertiser_portal.viewsets.CampaignReportViewSet import CampaignReportViewSet
from api.advertiser_portal.viewsets.OfferRequirementViewSet import OfferRequirementViewSet
from api.advertiser_portal.viewsets.TrackingPixelViewSet import TrackingPixelViewSet
from api.advertiser_portal.viewsets.S2SPostbackViewSet import S2SPostbackViewSet
from api.advertiser_portal.viewsets.ConversionQualityViewSet import ConversionQualityViewSet
from api.advertiser_portal.viewsets.PublisherBreakdownViewSet import PublisherBreakdownViewSet

# Register viewsets with router
router.register(r'advertisers', AdvertiserViewSet, basename='advertiser')
router.register(r'admin-advertisers', AdminAdvertiserViewSet, basename='admin-advertiser')
router.register(r'advertiser-profiles', AdvertiserProfileViewSet, basename='advertiser-profile')
router.register(r'advertiser-verifications', AdvertiserVerificationViewSet, basename='advertiser-verification')
router.register(r'advertiser-offers', AdvertiserOfferViewSet, basename='advertiser-offer')
router.register(r'advertiser-wallets', AdvertiserWalletViewSet, basename='advertiser-wallet')
router.register(r'advertiser-invoices', AdvertiserInvoiceViewSet, basename='advertiser-invoice')
router.register(r'advertiser-notifications', AdvertiserNotificationViewSet, basename='advertiser-notification')
router.register(r'campaigns', AdCampaignViewSet)
router.register(r'campaign-bids', CampaignBidViewSet)
router.register(r'campaign-creatives', CampaignCreativeViewSet)
router.register(r'campaign-targeting', CampaignTargetingViewSet)
router.register(r'campaign-reports', CampaignReportViewSet)
router.register(r'offer-requirements', OfferRequirementViewSet)
router.register(r'tracking-pixels', TrackingPixelViewSet)
router.register(r's2s-postbacks', S2SPostbackViewSet)
router.register(r'conversion-quality', ConversionQualityViewSet)
router.register(r'publisher-breakdowns', PublisherBreakdownViewSet)

# API endpoints
urlpatterns = [
    # Direct API Views
    # Advertiser endpoints
    path('api/v1/advertisers/', advertiser_list_create, name='advertiser-list-create'),
    path('api/v1/advertisers/<uuid:pk>/', advertiser_detail, name='advertiser-detail'),
    path('api/v1/advertisers/profile/', advertiser_profile, name='advertiser-profile'),
    path('api/v1/advertisers/verification/', advertiser_verification, name='advertiser-verification'),
    
    # Campaign endpoints
    path('api/v1/campaigns/', campaign_list_create, name='campaign-list-create'),
    path('api/v1/campaigns/<uuid:pk>/', campaign_detail, name='campaign-detail'),
    path('api/v1/campaigns/<uuid:campaign_id>/creatives/', campaign_creatives, name='campaign-creatives'),
    path('api/v1/campaigns/<uuid:campaign_id>/targeting/', campaign_targeting, name='campaign-targeting'),
    
    # Offer endpoints
    path('api/v1/offers/', offer_list_create, name='offer-list-create'),
    path('api/v1/offers/<uuid:pk>/', offer_detail, name='offer-detail'),
    
    # Tracking endpoints
    path('api/v1/tracking/pixels/', tracking_pixel_list_create, name='tracking-pixel-list-create'),
    path('api/v1/tracking/pixels/<uuid:pk>/', tracking_pixel_detail, name='tracking-pixel-detail'),
    path('api/v1/tracking/pixels/<uuid:pixel_id>/fire/', tracking_pixel_fire, name='tracking-pixel-fire'),
    path('api/v1/tracking/conversions/', conversion_list_create, name='conversion-list-create'),
    
    # Billing endpoints
    path('api/v1/billing/wallet/', wallet_detail, name='wallet-detail'),
    path('api/v1/billing/transactions/', transaction_list_create, name='transaction-list-create'),
    path('api/v1/billing/deposits/', deposit_create, name='deposit-create'),
    path('api/v1/billing/invoices/', invoice_list, name='invoice-list'),
    path('api/v1/billing/invoices/<uuid:pk>/', invoice_detail, name='invoice-detail'),
    
    # Reporting endpoints
    path('api/v1/reports/', report_list_create, name='report-list-create'),
    path('api/v1/reports/<uuid:pk>/', report_detail, name='report-detail'),
    path('api/v1/reports/dashboard/', dashboard_metrics, name='dashboard-metrics'),
    path('api/v1/reports/performance/', performance_metrics, name='performance-metrics'),
    
    # Fraud detection endpoints
    path('api/v1/fraud/metrics/', fraud_metrics, name='fraud-metrics'),
    path('api/v1/fraud/conversion-quality/', conversion_quality_scores, name='conversion-quality-scores'),
    
    # Notification endpoints
    path('api/v1/notifications/', notification_list_create, name='notification-list-create'),
    path('api/v1/notifications/<uuid:pk>/mark-read/', notification_mark_read, name='notification-mark-read'),
    
    # Utility endpoints
    path('api/v1/system/health/', system_health, name='system-health'),
    path('api/v1/system/stats/', system_stats, name='system-stats'),
    
    # Module-based URL patterns (existing structure)
    # Advertiser Management
    path('api/v1/advertiser/', include(advertiser_urls)),
    
    # Campaign Management
    path('api/v1/campaign/', include(campaign_urls)),
    
    # Creative Management
    path('api/v1/creative/', include(creative_urls)),
    
    # Targeting Management
    path('api/v1/targeting/', include(targeting_urls)),
    
    # Analytics Management
    path('api/v1/analytics/', include(analytics_urls)),
    
    # Billing Management
    path('api/v1/billing/', include(billing_urls)),
    
    # Router URLs (ViewSets)
    path('api/v1/', include(router.urls)),
    
    # API Documentation
    path('api/v1/docs/', include('rest_framework.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
