from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .viewsets import (
    SmartLinkViewSet, SmartLinkGroupViewSet, TargetingRuleViewSet,
    GeoTargetingViewSet, DeviceTargetingViewSet, OfferPoolViewSet,
    OfferPoolEntryViewSet, ClickViewSet, RedirectLogViewSet,
    SmartLinkStatViewSet, ABTestViewSet, DomainViewSet,
    PublisherSmartLinkViewSet, LandingPageViewSet, PreLanderViewSet,
    OfferBlacklistViewSet, HeatmapViewSet, InsightViewSet,
    AdminSmartLinkViewSet, PublisherAPIViewSet,
)
from .viewsets.PublicRedirectView import PublicRedirectView
from .viewsets.ReportViewSet import ReportViewSet
from .viewsets.PostbackViewSet import PostbackLogViewSet
from .viewsets.MLInsightViewSet import MLInsightViewSet
from .monitoring.views import HealthCheckView, ReadinessView, LivenessView
from .postback.views import PostbackView, PostbackPixelView
from .postback.v2.views import PostbackV2View

router = DefaultRouter()

# Core SmartLink CRUD
router.register(r'smartlinks', SmartLinkViewSet, basename='smartlink')
router.register(r'smartlinks/(?P<smartlink_pk>[^/.]+)/targeting', TargetingRuleViewSet, basename='targeting-rule')
router.register(r'smartlinks/(?P<smartlink_pk>[^/.]+)/geo-targeting', GeoTargetingViewSet, basename='geo-targeting')
router.register(r'smartlinks/(?P<smartlink_pk>[^/.]+)/device-targeting', DeviceTargetingViewSet, basename='device-targeting')
router.register(r'smartlinks/(?P<smartlink_pk>[^/.]+)/pool', OfferPoolViewSet, basename='offer-pool')
router.register(r'smartlinks/(?P<smartlink_pk>[^/.]+)/pool/entries', OfferPoolEntryViewSet, basename='pool-entry')
router.register(r'smartlinks/(?P<smartlink_pk>[^/.]+)/clicks', ClickViewSet, basename='click')
router.register(r'smartlinks/(?P<smartlink_pk>[^/.]+)/redirect-logs', RedirectLogViewSet, basename='redirect-log')
router.register(r'smartlinks/(?P<smartlink_pk>[^/.]+)/stats', SmartLinkStatViewSet, basename='smartlink-stat')
router.register(r'smartlinks/(?P<smartlink_pk>[^/.]+)/ab-test', ABTestViewSet, basename='ab-test')
router.register(r'smartlinks/(?P<smartlink_pk>[^/.]+)/landing-pages', LandingPageViewSet, basename='landing-page')
router.register(r'smartlinks/(?P<smartlink_pk>[^/.]+)/pre-landers', PreLanderViewSet, basename='pre-lander')
router.register(r'smartlinks/(?P<smartlink_pk>[^/.]+)/blacklist', OfferBlacklistViewSet, basename='offer-blacklist')
router.register(r'smartlinks/(?P<smartlink_pk>[^/.]+)/heatmap', HeatmapViewSet, basename='heatmap')
router.register(r'smartlinks/(?P<smartlink_pk>[^/.]+)/insights', InsightViewSet, basename='insight')
router.register(r'groups', SmartLinkGroupViewSet, basename='smartlink-group')
router.register(r'domains', DomainViewSet, basename='domain')
router.register(r'publisher/smartlinks', PublisherSmartLinkViewSet, basename='publisher-smartlink')
router.register(r'publisher/api', PublisherAPIViewSet, basename='publisher-api')
router.register(r'admin/smartlinks', AdminSmartLinkViewSet, basename='admin-smartlink')
router.register(r'reports', ReportViewSet, basename='report')
router.register(r'postback-logs', PostbackLogViewSet, basename='postback-log')
router.register(r'ml', MLInsightViewSet, basename='ml-insight')

app_name = 'api.smartlink'

urlpatterns = [
    path('go/<slug:slug>/', PublicRedirectView.as_view(), name='public-redirect'),
    path('api/smartlink/', include(router.urls)),
    path('postback/', PostbackView.as_view(), name='postback'),
    path('pixel/', PostbackPixelView.as_view(), name='postback-pixel'),
    path('api/v2/postback/', PostbackV2View.as_view(), name='postback-v2'),
    path('health/', HealthCheckView.as_view(), name='health'),
    path('ready/', ReadinessView.as_view(), name='ready'),
    path('live/', LivenessView.as_view(), name='live'),
]

# V2 API
from .viewsets.v2 import SmartLinkV2ViewSet
router_v2 = DefaultRouter()
router_v2.register(r'smartlinks', SmartLinkV2ViewSet, basename='smartlink-v2')
urlpatterns += [
    path('api/v2/smartlink/', include(router_v2.urls)),
]
