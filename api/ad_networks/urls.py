# api/ad_networks/urls.py — এই file টা পুরোটা REPLACE করো
from django.urls import path, include
from rest_framework.routers import SimpleRouter as DefaultRouter

from .views import (
    OfferCategoryViewSet,
    OfferViewSet,
    UserOfferEngagementViewSet,
    AdNetworkViewSet,
    PostbackView,
    OfferConversionViewSet,
    OfferWallAdminViewSet,
    BlacklistedIPViewSet,
    FraudRuleViewSet,
    WebhookLogViewSet,
    SyncLogViewSet,
)
from .views_extra import (
    NetworkStatisticViewSet,
    KnownBadIPViewSet,
    SmartOfferRecommendationViewSet,
)

router = DefaultRouter()

# ── Existing ─────────────────────────────────────────────────
router.register(r'networks',      AdNetworkViewSet,          basename='ad-network')
router.register(r'categories',    OfferCategoryViewSet,      basename='offer-category')
router.register(r'offers',        OfferViewSet,              basename='offer')
router.register(r'engagements',   UserOfferEngagementViewSet, basename='engagement')

# ── New ───────────────────────────────────────────────────────
router.register(r'conversions',     OfferConversionViewSet,  basename='conversion')
router.register(r'walls',           OfferWallAdminViewSet,   basename='offerwall-admin')
router.register(r'blacklisted-ips', BlacklistedIPViewSet,    basename='blacklisted-ip')
router.register(r'fraud-rules',     FraudRuleViewSet,        basename='fraud-rule')
router.register(r'webhooks',        WebhookLogViewSet,       basename='webhook-log')
router.register(r'sync-logs',       SyncLogViewSet,          basename='sync-log')
router.register(r'statistics',      NetworkStatisticViewSet, basename='statistic')
router.register(r'known-bad-ips',   KnownBadIPViewSet,       basename='known-bad-ip')
router.register(r'recommendations', SmartOfferRecommendationViewSet, basename='recommendation')

urlpatterns = [
    path('', include(router.urls)),
    path('postback-receive/', PostbackView.as_view(), name='postback-receive'),
]