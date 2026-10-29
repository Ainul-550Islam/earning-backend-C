# config/urls.py  ── FIXED & CLEANED VERSION
# Changes from original:
#   ✅ notifications + subscription → uncommented
#   ✅ smartlink + webhooks → added
#   ✅ 11 bare-path modules → moved under /api/
#   ✅ fraud_detection underscore duplicate → removed (hyphen kept)
#   ✅ djoyalty /api/customers/ → given explicit namespace
#   ✅ Legacy bare paths kept as aliases (clearly labelled)
#   ✅ Imports re-ordered to fail-fast at startup

from config.url_converter_patch import install_url_converter_patch

install_url_converter_patch()

# ── Standard imports ────────────────────────────────────────────────────────
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic.base import RedirectView
from django.http import JsonResponse
from django.contrib.sitemaps.views import sitemap, index as sitemap_index

from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)

# ── Project-specific imports ────────────────────────────────────────────────
from admob_ssv.views import AdmobSSVView
from api.admin_panel.views import admin_dashboard
from api.admin_panel.admin import admin_site  # noqa: F401  (side effect: admin.site = ModernAdminSite)
from api.cms import views as cms_views
from api.cms.admin import cms_admin_site
from api.cms.public_views import public_tenant_settings
from api.wallet import views as wallet_views
from api.backup.admin import Backup_admin_site as backup_admin      # noqa: F401
from api.security.admin import security_admin_site
from api.users.oauth_views import google_callback, google_login

# ── Custom error handlers ────────────────────────────────────────────────────
handler404 = wallet_views.handler404
handler500 = wallet_views.handler500

# ── Sitemaps registry ────────────────────────────────────────────────────────
sitemaps = {}

def root(request):
    return JsonResponse({"status": "ok"})

# ════════════════════════════════════════════════════════════════════════════
urlpatterns = [
    path('', root, name='root'),

    # ── Favicon ─────────────────────────────────────────────────────────────
    path('favicon.ico', RedirectView.as_view(url='/static/favicon.ico', permanent=True)),

    # ── Django Admin sites ───────────────────────────────────────────────────
    path('admin/',              admin.site.urls),
    # [W005 fix 2026-10-25: admin_site is admin.site, duplicate modern_admin mount] path('task-admin/',         admin_site.urls),
    path('api/cms-admin/',      cms_admin_site.urls),
    path('api/security-admin/', security_admin_site.urls),

    # ── OpenAPI / Docs ───────────────────────────────────────────────────────
    path('api/schema/', SpectacularAPIView.as_view(),                                name='schema'),
    path('api/docs/',   SpectacularSwaggerView.as_view(url_name='schema'),           name='swagger-ui'),
    path('api/redoc/',  SpectacularRedocView.as_view(url_name='schema'),             name='redoc'),

    # ── Social Auth ──────────────────────────────────────────────────────────
    path('auth/social/', include('social_django.urls', namespace='social')),
    path('auth/social/complete/google-oauth2/', google_callback),
    path('auth/social/login/google-oauth2/',   google_login),

    # ════════════════════════════════════════════════════════════════════════
    # MAIN API ROUTER  →  api/urls.py handles internal sub-routing
    # ════════════════════════════════════════════════════════════════════════
    path('api/', include('api.urls')),

    # ── Public tenant settings (no auth) ────────────────────────────────────
    path('api/public/tenant-settings/', public_tenant_settings, name='public-tenant-settings'),

    # ════════════════════════════════════════════════════════════════════════
    # USERS / AUTH
    # ════════════════════════════════════════════════════════════════════════
    path('api/auth/',  include(('api.users.urls', 'users'),       namespace='users')),
    path('api/users/', include(('api.users.urls', 'users_admin'), namespace='users_admin')),
    path('api/users/dashboard-stats/',
         __import__('api.users.views', fromlist=['AdminUserViewSet'])
             .AdminUserViewSet.as_view({'get': 'system_statistics'})),
    path('api/tenants/', include('api.tenants.urls')),

    # ════════════════════════════════════════════════════════════════════════
    # FINANCIAL LAYER
    # ════════════════════════════════════════════════════════════════════════
    path('api/wallet/',       include(('api.wallet.urls',       'wallet'),    namespace='wallet')),
    path('api/payout-queue/', include(('api.payout_queue.urls', 'payout'),   namespace='payout')),
    path('api/payment-gateways/', include(('api.payment_gateways.urls', 'payment_gateways'), namespace='payment_gateways')),
    path('api/subscription/', include(('api.subscription.urls', 'subscription'), namespace='subscription')),  # ✅ FIXED: was commented out

    # ════════════════════════════════════════════════════════════════════════
    # OFFER / EARNING LAYER
    # ════════════════════════════════════════════════════════════════════════
    path('api/offers/',         include(('api.offerwall.urls',       'offerwall'),    namespace='offerwall')),
    path('api/ad-networks/',    include(('api.ad_networks.urls',     'ad_networks'),  namespace='ad_networks')),
    path('api/postback/',       include(('api.postback.urls',        'postback'),     namespace='postback')),
    path('api/inventory/',      include(('api.inventory.urls',       'inventory'),    namespace='inventory')),
    path('api/tasks/',          include(('api.tasks.urls',           'tasks'),        namespace='tasks')),
    path('api/smartlink/',      include(('api.smartlink.urls',       'smartlink'),    namespace='smartlink')),       # ✅ FIXED: was commented out

    # ── These were on bare root paths — now properly under /api/ ────────────
    path('api/postback-engine/',   include(('api.postback_engine.urls',   'postback_engine'),   namespace='postback_engine')),   # ✅ was: postback-engine/
    path('api/offer-inventory/',   include(('api.offer_inventory.urls',   'offer_inventory'),   namespace='offer_inventory')),   # ✅ was: offer-inventory/
    path('api/offer-routing/',     include(('api.offer_routing.urls',     'offer_routing'),     namespace='offer_routing')),     # ✅ was: offer-routing/
    path('api/ai-engine/',         include(('api.ai_engine.urls',         'ai_engine'),         namespace='ai_engine')),         # ✅ was: ai-engine/

    # ════════════════════════════════════════════════════════════════════════
    # LOYALTY / GAMIFICATION
    # ════════════════════════════════════════════════════════════════════════
    path('api/djoyalty/',      include(('api.djoyalty.urls',      'djoyalty'),     namespace='djoyalty')),
    path('api/customers/',     include(('api.djoyalty.urls',      'djoyalty_cust'),namespace='djoyalty_cust')),  # ✅ FIXED: added namespace
    path('api/gamification/',  include(('api.gamification.urls',  'gamification'), namespace='gamification')),
    path('api/referral/',      include(('api.referral.urls',      'referral'),     namespace='referral')),
    path('api/engagement/',    include(('api.engagement.urls',    'engagement'),   namespace='engagement')),

    # ════════════════════════════════════════════════════════════════════════
    # COMMUNICATION LAYER
    # ════════════════════════════════════════════════════════════════════════
    path('api/notifications/', include(('api.notifications.urls', 'notifications'), namespace='notifications')),  # ✅ FIXED: was commented out
    path('api/messaging/',     include(('api.messaging.urls',     'messaging'),    namespace='messaging')),
    path('api/support/',       include(('api.support.urls',       'support'),      namespace='support')),
    path('api/alerts/',        include(('api.alerts.urls',        'alerts'),       namespace='alerts')),
    path('api/webhooks/',      include(('api.webhooks.urls',      'webhooks'),     namespace='webhooks')),         # ✅ FIXED: was missing entirely

    # ════════════════════════════════════════════════════════════════════════
    # ANALYTICS / INTELLIGENCE
    # ════════════════════════════════════════════════════════════════════════
    path('api/analytics/',          include(('api.analytics.urls',         'analytics'),          namespace='analytics')),
    path('api/behavior-analytics/', include(('api.behavior_analytics.urls','behavior_analytics'), namespace='behavior_analytics')),
    path('api/fraud-detection/',    include(('api.fraud_detection.urls',   'fraud_detection'),    namespace='fraud_detection')),  # ✅ FIXED: removed duplicate underscore version
    path('api/audit-logs/',         include(('api.audit_logs.urls',        'audit_logs'),         namespace='audit_logs')),
    path('api/proxy-intelligence/', include(('api.proxy_intelligence.urls','proxy_intelligence'), namespace='proxy_intelligence')),  # ✅ was: proxy-intelligence/

    # ════════════════════════════════════════════════════════════════════════
    # PARTNER PORTALS
    # ════════════════════════════════════════════════════════════════════════
    path('api/publisher-tools/',    include(('api.publisher_tools.urls',   'publisher_tools'),  namespace='publisher_tools')),   # ✅ was: publisher-tools/
    path('api/advertiser-portal/',  include(('api.advertiser_portal.urls', 'advertiser_portal'),namespace='advertiser_portal')), # ✅ was: advertiser-portal/
    path('api/marketplace/',        include(('api.marketplace.urls',       'marketplace'),      namespace='marketplace')),       # ✅ was: marketplace/

    # ════════════════════════════════════════════════════════════════════════
    # PLATFORM / CONTENT
    # ════════════════════════════════════════════════════════════════════════
    path('api/cms/',              include(('api.cms.urls',              'cms'),              namespace='cms')),
    path('api/promotions/',       include(('api.promotions.urls',       'promotions'),       namespace='promotions')),
    path('api/localization/',     include(('api.localization.urls',     'localization'),     namespace='localization')),
    path('api/kyc/',              include(('api.kyc.urls',              'kyc'),              namespace='kyc')),

    # ════════════════════════════════════════════════════════════════════════
    # ADMIN / SYSTEM
    # ════════════════════════════════════════════════════════════════════════
    path('api/admin-panel/',        include(('api.admin_panel.urls',      'admin_panel'),    namespace='admin_panel')),
    path('api/rate-limit/',         include(('api.rate_limit.urls',       'limit'),          namespace='limit')),
    path('api/monetization-tools/', include(('api.monetization_tools.urls','monetization'),  namespace='monetization')),          # ✅ was: monetization-tools/
    path('api/version-control/',    include(('api.version_control.urls',  'version_control'),namespace='version_control')),
    path('api/auto-mod/',           include(('api.auto_mod.urls',         'auto_mod'),       namespace='auto_mod')),
    path('api/security/',           include(('api.security.urls',         'security'),       namespace='security')),
    path('api/cache/',              include(('api.cache.urls',            'cache'),          namespace='cache')),
    path('api/backup/',             include(('api.backup.urls',           'backup'),         namespace='backup')),
    path('api/audit_logs/',         include(('api.audit_logs.urls',       'audit_logs_ul'),  namespace='audit_logs_ul')),  # legacy underscore alias
    path('api/tests/',              include(('api.tests.urls',            'tests'),          namespace='tests')),
    path('api/feature-flags/',       include(('api.feature_flags.urls',    'feature_flags'),  namespace='feature_flags')), # ✅ was: feature-flags/
    path('api/realtime-dashboard/', include(('api.realtime_dashboard.urls', 'realtime_dashboard'), namespace='realtime_dashboard')),  # ✅ was: realtime-dashboard/
    path('api/telemetry-observability/', include(('api.telemetry_observability.urls', 'telemetry_observability'), namespace='telemetry_observability')),  # ✅ was: telemetry-observability/
 
 
    # ── Disaster Recovery (admin-only, bare path intentional for ops scripts) ─
    path('api/disaster-recovery/', include(('api.disaster_recovery.urls', 'disaster_recovery'), namespace='disaster_recovery')),  # ✅ was: disaster-recovery/
    path('api/dr-integration/',    include(('api.dr_integration.urls', 'dr_integration'),  namespace='dr_integration')),    # ✅ was: dr-integration/

    # ════════════════════════════════════════════════════════════════════════
    # MISC
    # ════════════════════════════════════════════════════════════════════════
    path('admin-dashboard/',     admin_dashboard,                           name='admin_dashboard'),
    path('api/admob/verify/',    AdmobSSVView.as_view(),                    name='admob_ssv'),

    # ── Legacy bare paths (kept for backward compat — deprecate in v2) ─────
    path('tasks/',               include('api.tasks.urls')),                # legacy
    path('security/',            include('api.security.urls')),             # legacy

    # ── Sitemaps & Feeds ─────────────────────────────────────────────────────
    path('sitemap.xml',            sitemap_index, {'sitemaps': sitemaps},   name='sitemap_index'),
    path('sitemap-<section>.xml',  sitemap,       {'sitemaps': sitemaps},   name='sitemap_section'),
    path('feed/latest-content/',       cms_views.LatestContentFeed(),       name='content_feed'),
    path('feed/latest-content/atom/',  cms_views.AtomLatestContentFeed(),  name='content_feed_atom'),
    path('ckeditor/', include('ckeditor_uploader.urls')),
]

# ── Media / Static (dev only) ────────────────────────────────────────────────
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL,  document_root=settings.MEDIA_ROOT)



# from django.urls import converters

# _original_register_converter = converters.register_converter

# def _patched_register_converter(converter, type_name):
#     if type_name not in converters._converters:
#         _original_register_converter(converter, type_name)

# converters.register_converter = _patched_register_converter

# from django.contrib import admin
# from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
# from django.urls import path, include
# from admob_ssv.views import AdmobSSVView
# from django.conf import settings
# from django.conf.urls.static import static
# from api.admin_panel.views import admin_dashboard
# from api.admin_panel.admin import admin_site
# from api.cms import views
# from django.contrib.sitemaps.views import sitemap, index as sitemap_index
# from api.cms.admin import cms_admin_site
# from api.wallet import views as wallet_views
# from api.backup.admin import Backup_admin_site as backup_admin
# from api.security.admin import security_admin_site
# from api.cms.public_views import public_tenant_settings

# handler404 = wallet_views.handler404
# handler500 = wallet_views.handler500

# sitemaps = {}

# from django.views.generic.base import RedirectView
# urlpatterns = [
#     path('favicon.ico', RedirectView.as_view(url='/static/favicon.ico', permanent=True)),
#     # path('', include('api.smartlink.urls')),
#     # path('', include('api.smartlink.postback.urls')),

#     # ── Django Admin ────────────────────────────────────────────────────
#     path('admin/',          admin.site.urls),
#     path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
#     path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
#     path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
#     path('task-admin/',     admin_site.urls),
#     path('api/cms-admin/',  cms_admin_site.urls),
#     path('api/security-admin/', security_admin_site.urls),

#     # ── Main API router ─────────────────────────────────────────────────
#     # ✅ FIXED: was duplicated (appeared twice) — keep only once
#     path('api/', include('api.urls')),
#     path('api/tenants/', include('api.tenants.urls')),
#     path('auth/social/complete/google-oauth2/', __import__('api.users.oauth_views', fromlist=['google_callback']).google_callback),
#     path('auth/social/login/google-oauth2/', __import__('api.users.oauth_views', fromlist=['google_login']).google_login),
#     path('api/public/tenant-settings/', public_tenant_settings, name='public-tenant-settings'),

#     path('auth/social/', include('social_django.urls', namespace='social')),

#     # ── Auth / Users ────────────────────────────────────────────────────
#         path('api/users/dashboard-stats/', __import__('api.users.views', fromlist=['AdminUserViewSet']).AdminUserViewSet.as_view({'get': 'system_statistics'})),

#     path('api/auth/', include(('api.users.urls', 'users'), namespace='users')),
#     path('api/users/', include(('api.users.urls', 'users_admin'), namespace='users_admin')),

#     # ── Wallet ──────────────────────────────────────────────────────────
#     # ✅ FIXED: was duplicated without namespace + with namespace — keep namespaced version only
#     path('api/wallet/', include(('api.wallet.urls', 'wallet'), namespace='wallet')),

#     # ── Analytics apps ──────────────────────────────────────────────────
#     # ✅ FIXED: api.analytics (old app) stays at /api/analytics/
#     path('api/analytics/', include(('api.analytics.urls', 'analytics'), namespace='analytics')),

#     # ✅ FIXED: behavior_analytics was at /api/behavior-analytics/ in urls.py
#     #           but frontend was calling /api/analytics/ → 404
#     #           Solution: keep mount at /api/behavior-analytics/ (correct)
#     #           AND fix frontend BASE = "/behavior-analytics" (not "/analytics")
#     path('api/behavior-analytics/', include('api.behavior_analytics.urls')),

#     # ── Fraud Detection ─────────────────────────────────────────────────
#     path('api/fraud_detection/', include('api.fraud_detection.urls')),
#     path('api/fraud-detection/', include(('api.fraud_detection.urls', 'fraud_detection'), namespace='fraud_detection')),
#     # ✅ FIXED: removed duplicate bare path('fraud_detection/', ...) below

#     # ── Offers / Tasks ──────────────────────────────────────────────────
#     path('api/offers/',     include(('api.offerwall.urls', 'offerwall'), namespace='offerwall')),
#     path('api/tasks/',      include('api.tasks.urls')),
#     path('tasks/',          include('api.tasks.urls')),   # legacy bare path kept

#     # ── Other API apps ──────────────────────────────────────────────────

#     path('api/customers/', include('api.djoyalty.urls')),
#     path('api/ad-networks/',      include('api.ad_networks.urls')),
#     path('api/cms/',              include(('api.cms.urls', 'cms'), namespace='cms')),
#     path('api/alerts/',           include(('api.alerts.urls', 'alerts'), namespace='alerts')),
#     path('api/admin-panel/',      include(('api.admin_panel.urls', 'admin_panel'), namespace='admin_panel')),
#     path('api/engagement/',       include(('api.engagement.urls', 'engagement'), namespace='engagement')),
#     path('api/support/',          include(('api.support.urls', 'support'), namespace='support')),
#     # path('api/notifications/',    include(('api.notifications.urls', 'notifications'), namespace='notifications')),
#     path('api/referral/',         include(('api.referral.urls', 'referral'), namespace='referral')),
#     path('api/localization/',     include(('api.localization.urls', 'localization'), namespace='localization')),
#     path('api/kyc/',              include(('api.kyc.urls', 'kyc'), namespace='kyc')),
#     path('api/djoyalty/',         include(('api.djoyalty.urls', 'djoyalty'), namespace='djoyalty')),
#     path('api/backup/',           include(('api.backup.urls', 'backup'), namespace='backup')),
#     path('api/audit_logs/',       include(('api.audit_logs.urls', 'audit_logs'), namespace='audit_logs')),
#     path('api/cache/',            include(('api.cache.urls', 'cache'), namespace='cache')),
#     path('api/security/',         include(('api.security.urls', 'security'), namespace='security')),
#     path('api/tests/',            include(('api.tests.urls', 'tests'), namespace='tests')),

#     # ✅ FIXED: rate_limit — was duplicated with two different paths (hyphen vs underscore)
#     #           Keep ONE namespaced version only
#     path('api/rate-limit/',       include(('api.rate_limit.urls', 'limit'), namespace='limit')),

#     # path('api/subscription/',     include('api.subscription.urls')),
#     path('api/gamification/',     include('api.gamification.urls')),
#     path('api/auto-mod/',         include('api.auto_mod.urls')),
#     path('api/version-control/',  include('api.version_control.urls')),
#     path('api/postback/',         include('api.postback.urls')),
#     path('api/inventory/',        include('api.inventory.urls')),
#     path('api/messaging/',        include('api.messaging.urls')),
#     path('api/payout-queue/',     include('api.payout_queue.urls')),
#     path('api/promotions/',       include('api.promotions.urls')),
#     path('api/payment_gateways/', include(('api.payment_gateways.urls', 'payment_gateways'), namespace='payment_gateways')),

#     # ── Misc ────────────────────────────────────────────────────────────
#     path('admin-dashboard/',      admin_dashboard, name='admin_dashboard'),
#     path('api/admob/verify/',     AdmobSSVView.as_view(), name='admob_ssv'),
#     path('security/',             include('api.security.urls')),   # legacy bare path kept
#     path('publisher-tools/',      include('api.publisher_tools.urls')),
#     path('monetization-tools/',   include('api.monetization_tools.urls')),
#     path('marketplace/',          include('api.marketplace.urls')),
#     path('postback-engine/',      include('api.postback_engine.urls')),
#     path('proxy-intelligence/',   include('api.proxy_intelligence.urls')),
#     path('ai-engine/',            include('api.ai_engine.urls')),
#     path('advertiser-portal/',    include('api.advertiser_portal.urls')),
#     path('offer-inventory/',      include('api.offer_inventory.urls')),
#     path('disaster-recovery/',    include('api.disaster_recovery.urls')),
#     path('dr-integration/',        include('api.dr_integration.urls')),
#     path('offer-routing/',         include('api.offer_routing.urls')),

#     # ── Sitemaps & Feeds ────────────────────────────────────────────────
#     path('sitemap.xml',           sitemap_index, {'sitemaps': sitemaps}, name='sitemap_index'),
#     path('sitemap-<section>.xml', sitemap,       {'sitemaps': sitemaps}, name='sitemap_section'),
#     path('feed/latest-content/',  views.LatestContentFeed(),     name='content_feed'),
#     path('feed/latest-content/atom/', views.AtomLatestContentFeed(), name='content_feed_atom'),
#     path('ckeditor/',             include('ckeditor_uploader.urls')),
# ]

# if settings.DEBUG:
#     urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
#     urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# --- admin guard (2026-10-28): drop admin registrations whose app label is not installed ---
def _purge_orphan_admin_models():
    import logging
    from collections import Counter
    from django.apps import apps as _apps
    from django.contrib import admin as _admin
    from django.contrib.admin.sites import all_sites
    _log = logging.getLogger(__name__)
    _sites = {id(s): s for s in [*all_sites, _admin.site, _admin.sites.site]}.values()
    for _s in _sites:
        _bad = [m for m in list(_s._registry) if m._meta.app_label not in _apps.app_configs]
        for _m in _bad:
            try:
                _s.unregister(_m)
            except Exception:
                _s._registry.pop(_m, None)
        if _bad:
            _log.warning(
                "admin guard: removed %d model(s) from admin site '%s' (app label not installed): %s",
                len(_bad), getattr(_s, "name", "?"), dict(Counter(m._meta.app_label for m in _bad)),
            )


_purge_orphan_admin_models()
