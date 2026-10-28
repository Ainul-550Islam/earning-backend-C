"""
SmartLink URL Configuration
==============================
ALL router.register() calls must come BEFORE include(router.urls).
"""
from django.urls import path, include
from django.views.decorators.csrf import csrf_exempt
try:
    from drf_spectacular.views import (
        SpectacularAPIView,
        SpectacularSwaggerView,
        SpectacularRedocView,
    )
    _SPECTACULAR_AVAILABLE = True
except ImportError:
    _SPECTACULAR_AVAILABLE = False
    SpectacularAPIView = SpectacularSwaggerView = SpectacularRedocView = None

from rest_framework.routers import DefaultRouter
from rest_framework_nested import routers as nested_routers

# ── Core ViewSet imports ──────────────────────────────────────────────────────
from .viewsets import (
    SmartLinkViewSet, SmartLinkGroupViewSet, TargetingRuleViewSet,
    GeoTargetingViewSet, DeviceTargetingViewSet, OfferPoolViewSet,
    OfferPoolEntryViewSet, ClickViewSet, RedirectLogViewSet,
    SmartLinkStatViewSet, ABTestViewSet, DomainViewSet,
    PublisherSmartLinkViewSet, PublisherAPIViewSet,
    LandingPageViewSet, PreLanderViewSet, OfferBlacklistViewSet,
    HeatmapViewSet, InsightViewSet,
    AdminSmartLinkViewSet,
    ScheduleViewSet, TemplateViewSet, PublisherTierViewSet,
    IntegrationViewSet,
    CurrencyViewSet, GeoIPViewSet, CacheViewSet,
    SecurityViewSet, NotificationViewSet,
)
from .viewsets.BusinessViewSets import (
    APIKeyViewSet, WebhookViewSet, PayoutViewSet, PublisherProfileViewSet,
)
from .viewsets.AttributionViewSet import AttributionViewSet
from .viewsets.RegistrationAndUtilsViewSets import (
    RegistrationViewSet, QRCodeView, UTMBuilderView, DeepLinkViewSet,
)
from .viewsets.PublicRedirectView import PublicRedirectView
from .viewsets.ReportViewSet import ReportViewSet
from .viewsets.PostbackViewSet import PostbackLogViewSet
from .viewsets.MLInsightViewSet import MLInsightViewSet
from .viewsets.ReportExportView import ReportExportView
from .viewsets.GDPRView import GDPRDataAccessView
from .viewsets.SubPublisherViewSet import SubPublisherViewSet
from .viewsets.FloatingModelViewSets import (
    SmartLinkRotationViewSet,
    SmartLinkFallbackViewSet,
    SmartLinkVersionViewSet,
    ClickSessionViewSet,
    ClickMetadataViewSet,
    BotClickViewSet,
    PublisherAllowListViewSet,
    PublisherBlockListViewSet,
    RedirectChainViewSet,
)
from .viewsets.ImpressionViewSet import ImpressionViewSet
from .viewsets.v2 import SmartLinkV2ViewSet
from .monitoring.views import HealthCheckView, ReadinessView, LivenessView
from .postback.views import PostbackView, PostbackPixelView
from .postback.v2.views import PostbackV2View

# ── NEW: Missing viewsets ─────────────────────────────────────────────────────
from .viewsets.MissingViewSets import (
    RedirectRuleViewSet,
    PublisherSubIDViewSet,
    BrowserTargetingViewSet,
    OSTargetingViewSet,
    TimeTargetingViewSet,
    ISPTargetingViewSet,
    LanguageTargetingViewSet,
    ClickFraudFlagViewSet,
    UniqueClickViewSet,
    SmartLinkDomainViewSet,
    SmartLinkTaggingViewSet,
    OfferPerformanceStatViewSet,
    GeoPerformanceStatViewSet,
    DevicePerformanceStatViewSet,
    OfferCapTrackerViewSet,
    OfferRotationLogViewSet,
    OfferScoreCacheViewSet,
)

# ── Root router ───────────────────────────────────────────────────────────────
router = DefaultRouter()

# SmartLink core CRUD
router.register(r'smartlinks', SmartLinkViewSet,      basename='smartlink')
router.register(r'groups',     SmartLinkGroupViewSet, basename='smartlink-group')
router.register(r'domains',    DomainViewSet,         basename='domain')

# Publisher self-management
router.register(r'publisher/smartlinks',      PublisherSmartLinkViewSet, basename='publisher-smartlink')
router.register(r'publisher/api',             PublisherAPIViewSet,       basename='publisher-api')
router.register(r'publisher/tier',            PublisherTierViewSet,      basename='publisher-tier')
router.register(r'publisher/api-keys',        APIKeyViewSet,             basename='api-key')
router.register(r'publisher/profile',         PublisherProfileViewSet,   basename='publisher-profile')
router.register(r'publisher/sub-publishers',  SubPublisherViewSet,       basename='sub-publisher')
router.register(r'publisher/sub-id-labels',   PublisherSubIDViewSet,     basename='sub-id-label')
router.register(r'publisher/allow-list',      PublisherAllowListViewSet, basename='allow-list')
router.register(r'publisher/block-list',      PublisherBlockListViewSet, basename='block-list')

# Registration + KYC
router.register(r'register', RegistrationViewSet, basename='registration')

# Admin
router.register(r'admin/smartlinks', AdminSmartLinkViewSet, basename='admin-smartlink')
router.register(r'admin/tiers',      PublisherTierViewSet,  basename='admin-tier')

# Reports, postback, ML
router.register(r'reports',       ReportViewSet,      basename='report')
router.register(r'postback-logs', PostbackLogViewSet, basename='postback-log')
router.register(r'ml',            MLInsightViewSet,   basename='ml-insight')

# Templates
router.register(r'templates', TemplateViewSet, basename='template')

# Business — billing and webhooks
router.register(r'webhooks', WebhookViewSet, basename='webhook')
router.register(r'payouts',  PayoutViewSet,  basename='payout')

# Deep links
router.register(r'deep-links', DeepLinkViewSet, basename='deep-link')

# Attribution
router.register(r'attribution', AttributionViewSet, basename='attribution')

# Utility
router.register(r'currency',      CurrencyViewSet,     basename='currency')
router.register(r'geoip',         GeoIPViewSet,        basename='geoip')
router.register(r'cache',         CacheViewSet,        basename='cache')
router.register(r'security',      SecurityViewSet,     basename='security')
router.register(r'notifications', NotificationViewSet, basename='notification')

# Impression tracking
router.register(r'impressions', ImpressionViewSet, basename='impression')

# ── Nested router: /smartlinks/{sl_pk}/... ────────────────────────────────────
sl_router = nested_routers.NestedSimpleRouter(router, r'smartlinks', lookup='smartlink')
sl_router.register(r'targeting',         TargetingRuleViewSet,         basename='targeting-rule')
sl_router.register(r'geo-targeting',     GeoTargetingViewSet,          basename='geo-targeting')
sl_router.register(r'device-targeting',  DeviceTargetingViewSet,       basename='device-targeting')
sl_router.register(r'os-targeting',      OSTargetingViewSet,           basename='os-targeting')      # NEW
sl_router.register(r'browser-targeting', BrowserTargetingViewSet,      basename='browser-targeting') # NEW
sl_router.register(r'time-targeting',    TimeTargetingViewSet,         basename='time-targeting')    # NEW
sl_router.register(r'isp-targeting',     ISPTargetingViewSet,          basename='isp-targeting')     # NEW
sl_router.register(r'language-targeting',LanguageTargetingViewSet,     basename='lang-targeting')    # NEW
sl_router.register(r'pool',              OfferPoolViewSet,             basename='offer-pool')
sl_router.register(r'pool/entries',      OfferPoolEntryViewSet,        basename='pool-entry')
sl_router.register(r'clicks',            ClickViewSet,                 basename='click')
sl_router.register(r'redirect-logs',     RedirectLogViewSet,           basename='redirect-log')
sl_router.register(r'redirect-rules',    RedirectRuleViewSet,          basename='redirect-rule')     # NEW
sl_router.register(r'stats',             SmartLinkStatViewSet,         basename='smartlink-stat')
sl_router.register(r'ab-test',           ABTestViewSet,                basename='ab-test')
sl_router.register(r'landing-pages',     LandingPageViewSet,           basename='landing-page')
sl_router.register(r'pre-landers',       PreLanderViewSet,             basename='pre-lander')
sl_router.register(r'blacklist',         OfferBlacklistViewSet,        basename='offer-blacklist')
sl_router.register(r'heatmap',           HeatmapViewSet,               basename='heatmap')
sl_router.register(r'insights',          InsightViewSet,               basename='insight')
sl_router.register(r'schedule',          ScheduleViewSet,              basename='schedule')
sl_router.register(r'integrations',      IntegrationViewSet,           basename='integration')
sl_router.register(r'fraud-flags',       ClickFraudFlagViewSet,        basename='fraud-flag')        # NEW
sl_router.register(r'unique-clicks',     UniqueClickViewSet,           basename='unique-click')      # NEW
sl_router.register(r'custom-domains',    SmartLinkDomainViewSet,       basename='custom-domain')     # NEW
sl_router.register(r'tags',              SmartLinkTaggingViewSet,      basename='sl-tag')            # NEW
sl_router.register(r'offer-stats',       OfferPerformanceStatViewSet,  basename='offer-stat')        # NEW
sl_router.register(r'geo-stats',         GeoPerformanceStatViewSet,    basename='geo-stat')          # NEW
sl_router.register(r'device-stats',      DevicePerformanceStatViewSet, basename='device-stat')       # NEW
sl_router.register(r'cap-trackers',      OfferCapTrackerViewSet,       basename='cap-tracker')       # NEW
sl_router.register(r'rotation-log',      OfferRotationLogViewSet,      basename='rotation-log')      # NEW

# Previously floating models — now wired
sl_router.register(r'versions',         SmartLinkVersionViewSet,   basename='sl-version')
sl_router.register(r'sessions',         ClickSessionViewSet,       basename='click-session')
sl_router.register(r'bot-clicks',       BotClickViewSet,           basename='bot-click')
sl_router.register(r'redirect-chains',  RedirectChainViewSet,      basename='redirect-chain')
sl_router.register(r'offer-scores',      OfferScoreCacheViewSet,       basename='offer-score')       # NEW

# ── V2 router ─────────────────────────────────────────────────────────────────
router_v2 = DefaultRouter()
router_v2.register(r'smartlinks', SmartLinkV2ViewSet, basename='smartlink-v2')


# ── Helpers ───────────────────────────────────────────────────────────────────
from django.http import JsonResponse


def _pixel_fire_view(request):
    view = ImpressionViewSet()
    view.kwargs = {}
    view.request = request
    view.format_kwarg = None
    return view.fire_pixel(request)


def _apple_app_site_association(request):
    from django.conf import settings
    bundle_ids = getattr(settings, 'SMARTLINK_IOS_BUNDLE_IDS', [])
    return JsonResponse({
        'applinks': {
            'apps': [],
            'details': [{'appID': bid, 'paths': ['/go/*']} for bid in bundle_ids],
        }
    })


def _android_assetlinks(request):
    from django.conf import settings
    android_apps = getattr(settings, 'SMARTLINK_ANDROID_APPS', [])
    return JsonResponse([
        {
            'relation': ['delegate_permission/common.handle_all_urls'],
            'target': {
                'namespace': 'android_app',
                'package_name': app.get('package_name', ''),
                'sha256_cert_fingerprints': [app.get('sha256_cert', '')],
            },
        }
        for app in android_apps
    ], safe=False)


app_name = 'api.smartlink'

# ── urlpatterns ───────────────────────────────────────────────────────────────
urlpatterns = [
    # Public redirect
    path('go/<slug:slug>/', PublicRedirectView.as_view(), name='public-redirect'),

    # Impression pixel (no auth)
    path('api/smartlink/pixel/fire/', _pixel_fire_view, name='impression-pixel'),

    # Singleton SmartLink config endpoints (OneToOne — no {pk} in URL)
    path(
        'api/smartlink/smartlinks/<int:smartlink_pk>/rotation/',
        SmartLinkRotationViewSet.as_view({'get': 'retrieve', 'patch': 'partial_update'}),
        name='sl-rotation',
    ),
    path(
        'api/smartlink/smartlinks/<int:smartlink_pk>/fallback/',
        SmartLinkFallbackViewSet.as_view({
            'get': 'retrieve', 'post': 'create',
            'patch': 'partial_update', 'delete': 'destroy',
        }),
        name='sl-fallback',
    ),
    path(
        'api/smartlink/smartlinks/<int:smartlink_pk>/fallback/toggle/',
        SmartLinkFallbackViewSet.as_view({'post': 'toggle'}),
        name='sl-fallback-toggle',
    ),

    # API v1
    path('api/smartlink/', include(router.urls)),
    path('api/smartlink/', include(sl_router.urls)),

    # API v2
    path('api/v2/smartlink/', include(router_v2.urls)),
    path('api/v2/postback/',  PostbackV2View.as_view(), name='postback-v2'),

    # Postback S2S
    path('postback/', PostbackView.as_view(),      name='postback'),
    path('pixel/',    PostbackPixelView.as_view(), name='postback-pixel'),

    # QR code
    path('api/smartlink/smartlinks/<slug:slug>/qr/', QRCodeView.as_view(), name='smartlink-qr'),

    # UTM builder
    path('api/smartlink/utm/build/', UTMBuilderView.as_view(), name='utm-builder'),

    # Report export
    path('api/smartlink/reports/export/<str:export_type>/',
         ReportExportView.as_view(), name='report-export'),

    # GDPR
    path('api/smartlink/publisher/gdpr/my-data/',
         GDPRDataAccessView.as_view(), name='gdpr-data-access'),

    # Well-known files
    path('.well-known/apple-app-site-association', _apple_app_site_association),
    path('.well-known/assetlinks.json',            _android_assetlinks),


    # Payment gateway webhooks — external servers POST here (no CSRF, no auth)
    # Signature verification is handled inside each action via HMAC
    path(
        'api/smartlink/payouts/paypal-webhook/',
        csrf_exempt(PayoutViewSet.as_view({'post': 'paypal_webhook'})),
        name='paypal-webhook',
    ),
    path(
        'api/smartlink/payouts/wise-webhook/',
        csrf_exempt(PayoutViewSet.as_view({'post': 'wise_webhook'})),
        name='wise-webhook',
    ),


    # OpenAPI docs (only when drf-spectacular is installed)
    *([  # noqa — list spread so missing drf-spectacular doesn't crash startup
        path("api/smartlink/schema/",  SpectacularAPIView.as_view(),               name="openapi-schema"),
        path("api/smartlink/docs/",    SpectacularSwaggerView.as_view(url_name="openapi-schema"), name="swagger-ui"),
        path("api/smartlink/redoc/",   SpectacularRedocView.as_view(url_name="openapi-schema"),   name="redoc"),
    ] if _SPECTACULAR_AVAILABLE else []),

    # Health probes
    path('health/', HealthCheckView.as_view(), name='health'),
    path('ready/',  ReadinessView.as_view(),   name='ready'),
    path('live/',   LivenessView.as_view(),    name='live'),
]
