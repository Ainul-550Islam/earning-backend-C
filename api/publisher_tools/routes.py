# api/publisher_tools/routes.py
"""Publisher Tools — Central URL routing configuration."""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    PublisherViewSet, SiteViewSet, AppViewSet, InventoryVerificationViewSet,
    AdUnitViewSet, AdPlacementViewSet, MediationGroupViewSet,
    WaterfallItemViewSet, HeaderBiddingConfigViewSet,
    PublisherEarningViewSet, PayoutThresholdViewSet, PublisherInvoiceViewSet,
    TrafficSafetyLogViewSet, SiteQualityMetricViewSet,
)
from .api_endpoints.publisher_api import PublisherDashboardView, PublisherStatsAPIView
from .api_endpoints.analytics_api import AnalyticsAPIView, ReportAPIView
from .api_endpoints.payment_api import PaymentAPIView, PayoutRequestAPIView
from .api_endpoints.fraud_api import FraudSummaryAPIView, IPBlockAPIView
from .api_endpoints.reporting_api import CustomReportAPIView, ScheduledReportAPIView
from .api_endpoints.settings_api import PublisherSettingsAPIView
from .api_endpoints.site_api import SiteBulkAPIView
from .api_endpoints.app_api import AppBulkAPIView
from .api_endpoints.ad_unit_api import AdUnitBulkAPIView
from .api_endpoints.placement_api import PlacementBulkAPIView

router = DefaultRouter()

# ── Core Resources ────────────────────────────────────────────────────────────
router.register(r'publishers',          PublisherViewSet,            basename='publisher')
router.register(r'sites',               SiteViewSet,                 basename='site')
router.register(r'apps',                AppViewSet,                  basename='app')
router.register(r'verifications',       InventoryVerificationViewSet,basename='verification')

# ── Ad Units & Placements ─────────────────────────────────────────────────────
router.register(r'ad-units',            AdUnitViewSet,               basename='ad-unit')
router.register(r'placements',          AdPlacementViewSet,          basename='placement')

# ── Mediation ─────────────────────────────────────────────────────────────────
router.register(r'mediation-groups',    MediationGroupViewSet,       basename='mediation-group')
router.register(r'waterfall-items',     WaterfallItemViewSet,        basename='waterfall-item')
router.register(r'header-bidding',      HeaderBiddingConfigViewSet,  basename='header-bidding')

# ── Earnings & Payments ───────────────────────────────────────────────────────
router.register(r'earnings',            PublisherEarningViewSet,     basename='earning')
router.register(r'payout-thresholds',   PayoutThresholdViewSet,      basename='payout-threshold')
router.register(r'invoices',            PublisherInvoiceViewSet,     basename='invoice')

# ── Fraud & Quality ───────────────────────────────────────────────────────────
router.register(r'traffic-safety-logs', TrafficSafetyLogViewSet,     basename='traffic-safety-log')
router.register(r'quality-metrics',     SiteQualityMetricViewSet,    basename='quality-metric')

# ── Extra API patterns ────────────────────────────────────────────────────────
extra_urlpatterns = [
    # Dashboard
    path('dashboard/',                      PublisherDashboardView.as_view(), name='publisher-dashboard'),
    path('publishers/<str:pub_id>/stats/',  PublisherStatsAPIView.as_view(),  name='publisher-stats'),
    # Analytics
    path('analytics/',                      AnalyticsAPIView.as_view(),       name='analytics'),
    path('reports/',                        ReportAPIView.as_view(),           name='report'),
    path('reports/custom/',                 CustomReportAPIView.as_view(),     name='custom-report'),
    path('reports/scheduled/',              ScheduledReportAPIView.as_view(),  name='scheduled-report'),
    # Payments
    path('payments/',                       PaymentAPIView.as_view(),          name='payment'),
    path('payments/payout-request/',        PayoutRequestAPIView.as_view(),    name='payout-request'),
    # Fraud
    path('fraud/summary/',                  FraudSummaryAPIView.as_view(),     name='fraud-summary'),
    path('fraud/ip-block/',                 IPBlockAPIView.as_view(),          name='ip-block'),
    # Settings
    path('settings/',                       PublisherSettingsAPIView.as_view(), name='settings'),
    # Bulk operations
    path('sites/bulk/',                     SiteBulkAPIView.as_view(),         name='site-bulk'),
    path('apps/bulk/',                      AppBulkAPIView.as_view(),          name='app-bulk'),
    path('ad-units/bulk/',                  AdUnitBulkAPIView.as_view(),       name='ad-unit-bulk'),
    path('placements/bulk/',                PlacementBulkAPIView.as_view(),    name='placement-bulk'),
]

urlpatterns = [
    path('', include(router.urls)),
    *extra_urlpatterns,
]
