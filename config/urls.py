from django.contrib import admin
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
from django.urls import path, include
from admob_ssv.views import AdmobSSVView
from django.conf import settings
from django.conf.urls.static import static
from api.admin_panel.views import admin_dashboard
from api.admin_panel.admin import admin_site
from api.cms import views
from django.contrib.sitemaps.views import sitemap, index as sitemap_index
from api.cms.admin import cms_admin_site
from api.wallet import views as wallet_views
from api.backup.admin import Backup_admin_site as backup_admin
from api.security.admin import security_admin_site

handler404 = wallet_views.handler404
handler500 = wallet_views.handler500

sitemaps = {}

urlpatterns = [

    # ── Django Admin ────────────────────────────────────────────────────
    path('admin/',          admin.site.urls),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    path('task-admin/',     admin_site.urls),
    path('api/cms-admin/',  cms_admin_site.urls),
    path('api/security-admin/', security_admin_site.urls),

    # ── Main API router ─────────────────────────────────────────────────
    # ✅ FIXED: was duplicated (appeared twice) — keep only once
    path('api/', include('api.urls')),
    path('api/tenants/', include('api.tenants.urls')),
    path('auth/social/complete/google-oauth2/', __import__('api.users.oauth_views', fromlist=['google_callback']).google_callback),
    path('auth/social/login/google-oauth2/', __import__('api.users.oauth_views', fromlist=['google_login']).google_login),
    path('auth/social/', include('social_django.urls', namespace='social')),

    # ── Auth / Users ────────────────────────────────────────────────────
        path('api/users/dashboard-stats/', __import__('api.users.views', fromlist=['AdminUserViewSet']).AdminUserViewSet.as_view({'get': 'system_statistics'})),

    path('api/auth/', include(('api.users.urls', 'users'), namespace='users')),

    # ── Wallet ──────────────────────────────────────────────────────────
    # ✅ FIXED: was duplicated without namespace + with namespace — keep namespaced version only
    path('api/wallet/', include(('api.wallet.urls', 'wallet'), namespace='wallet')),

    # ── Analytics apps ──────────────────────────────────────────────────
    # ✅ FIXED: api.analytics (old app) stays at /api/analytics/
    path('api/analytics/', include(('api.analytics.urls', 'analytics'), namespace='analytics')),

    # ✅ FIXED: behavior_analytics was at /api/behavior-analytics/ in urls.py
    #           but frontend was calling /api/analytics/ → 404
    #           Solution: keep mount at /api/behavior-analytics/ (correct)
    #           AND fix frontend BASE = "/behavior-analytics" (not "/analytics")
    path('api/behavior-analytics/', include('api.behavior_analytics.urls')),

    # ── Fraud Detection ─────────────────────────────────────────────────
    path('api/fraud_detection/', include('api.fraud_detection.urls')),
    path('api/fraud-detection/', include(('api.fraud_detection.urls', 'fraud_detection'), namespace='fraud_detection')),
    # ✅ FIXED: removed duplicate bare path('fraud_detection/', ...) below

    # ── Offers / Tasks ──────────────────────────────────────────────────
    path('api/offers/',     include(('api.offerwall.urls', 'offerwall'), namespace='offerwall')),
    path('api/tasks/',      include('api.tasks.urls')),
    path('tasks/',          include('api.tasks.urls')),   # legacy bare path kept

    # ── Other API apps ──────────────────────────────────────────────────

    path('api/customers/', include('api.djoyalty.urls')),
    path('api/ad-networks/',      include('api.ad_networks.urls')),
    path('api/cms/',              include(('api.cms.urls', 'cms'), namespace='cms')),
    path('api/alerts/',           include(('api.alerts.urls', 'alerts'), namespace='alerts')),
    path('api/admin-panel/',      include(('api.admin_panel.urls', 'admin_panel'), namespace='admin_panel')),
    path('api/engagement/',       include(('api.engagement.urls', 'engagement'), namespace='engagement')),
    path('api/support/',          include(('api.support.urls', 'support'), namespace='support')),
    path('api/notifications/',    include(('api.notifications.urls', 'notifications'), namespace='notifications')),
    path('api/referral/',         include(('api.referral.urls', 'referral'), namespace='referral')),
    path('api/localization/',     include(('api.localization.urls', 'localization'), namespace='localization')),
    path('api/kyc/',              include(('api.kyc.urls', 'kyc'), namespace='kyc')),
    path('api/djoyalty/',         include(('api.djoyalty.urls', 'djoyalty'), namespace='djoyalty')),
    path('api/backup/',           include(('api.backup.urls', 'backup'), namespace='backup')),
    path('api/audit_logs/',       include(('api.audit_logs.urls', 'audit_logs'), namespace='audit_logs')),
    path('api/cache/',            include(('api.cache.urls', 'cache'), namespace='cache')),
    path('api/security/',         include(('api.security.urls', 'security'), namespace='security')),
    path('api/tests/',            include(('api.tests.urls', 'tests'), namespace='tests')),

    # ✅ FIXED: rate_limit — was duplicated with two different paths (hyphen vs underscore)
    #           Keep ONE namespaced version only
    path('api/rate-limit/',       include(('api.rate_limit.urls', 'limit'), namespace='limit')),

    path('api/subscription/',     include('api.subscription.urls')),
    path('api/gamification/',     include('api.gamification.urls')),
    path('api/auto-mod/',         include('api.auto_mod.urls')),
    path('api/version-control/',  include('api.version_control.urls')),
    path('api/postback/',         include('api.postback.urls')),
    path('api/inventory/',        include('api.inventory.urls')),
    path('api/messaging/',        include('api.messaging.urls')),
    path('api/payout-queue/',     include('api.payout_queue.urls')),
    path('api/promotions/',       include('api.promotions.urls')),
    path('api/payment_gateways/', include(('api.payment_gateways.urls', 'payment_gateways'), namespace='payment_gateways')),

    # ── Misc ────────────────────────────────────────────────────────────
    path('admin-dashboard/',      admin_dashboard, name='admin_dashboard'),
    path('api/admob/verify/',     AdmobSSVView.as_view(), name='admob_ssv'),
    path('security/',             include('api.security.urls')),   # legacy bare path kept

    # ── Sitemaps & Feeds ────────────────────────────────────────────────
    path('sitemap.xml',           sitemap_index, {'sitemaps': sitemaps}, name='sitemap_index'),
    path('sitemap-<section>.xml', sitemap,       {'sitemaps': sitemaps}, name='sitemap_section'),
    path('feed/latest-content/',  views.LatestContentFeed(),     name='content_feed'),
    path('feed/latest-content/atom/', views.AtomLatestContentFeed(), name='content_feed_atom'),
    path('ckeditor/',             include('ckeditor_uploader.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)