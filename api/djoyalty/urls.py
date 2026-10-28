# api/djoyalty/urls.py
"""
Djoyalty -- Complete URL configuration।
Include in project: path('api/loyalty/', include('djoyalty.urls'))

FIXED: api_versioning.py (DjoyaltyURLVersioning) was orphaned।
Now registered as DEFAULT_VERSIONING_CLASS per-app।
Add to DRF settings:
  REST_FRAMEWORK = {
      'DEFAULT_VERSIONING_CLASS': 'djoyalty.api_versioning.DjoyaltyURLVersioning',
      'DEFAULT_VERSION': 'v1',
      'ALLOWED_VERSIONS': ['v1', 'v2'],
  }
Or use version-namespaced URLs below (v1/ and v2/ prefixes)।
"""
from django.urls import path, include
from .routers import router
from .views import (
    DjoyaltyHealthView,
    smart_link_redirect,
    offerwall_postback,
    WebhookReceiverView,
)
from .atachment_upload_view import (
    ReceiptUploadView,
    CustomerAvatarUploadView,
    CatalogItemImageUploadView,
)
from .endpoint import LoyaltyAPIRootView

app_name = 'djoyalty'

# ─── API versioning (from api_versioning.py) ──────────────────────────────────
# FIXED: api_versioning.py was an orphan -- DjoyaltyURLVersioning now usable।
# Import it so it's importable from djoyalty.urls for DRF settings।
try:
    from .api_versioning import DjoyaltyURLVersioning  # noqa: F401 -- re-export
except ImportError:
    DjoyaltyURLVersioning = None

urlpatterns = [

    # ─── API Root ─────────────────────────────────────────────────────────────
    path('', LoyaltyAPIRootView.as_view(), name='api_root'),

    # ─── Health Checks ────────────────────────────────────────────────────────
    path('health/', DjoyaltyHealthView.as_view(), name='health'),
    path('health/detailed/', DjoyaltyHealthView.as_view(), {'detailed': True},
         name='health_detailed'),

    # ─── All REST API routes via DRF Router ───────────────────────────────────
    path('', include(router.urls)),

    # ─── SmartLink Redirect ───────────────────────────────────────────────────
    path('ref/<slug:slug>/', smart_link_redirect, name='smart_link_redirect'),

    # ─── OfferWall Postback ───────────────────────────────────────────────────
    path('offerwall/postback/', offerwall_postback, name='offerwall_postback'),
    path('offerwall/<int:wall_id>/postback/', offerwall_postback,
         name='offerwall_postback_specific'),

    # ─── Inbound Webhooks ─────────────────────────────────────────────────────
    path('webhooks/receive/', WebhookReceiverView.as_view(), name='webhook_receive'),

    # ─── File Uploads ─────────────────────────────────────────────────────────
    path('upload/receipt/', ReceiptUploadView.as_view(), name='upload_receipt'),
    path('upload/avatar/', CustomerAvatarUploadView.as_view(), name='upload_avatar'),
    path('upload/catalog-image/', CatalogItemImageUploadView.as_view(),
         name='upload_catalog_image'),

    # ─── Versioned URL namespaces (optional -- for URL-based versioning) ───────
    # Uncomment if you want explicit /v1/ and /v2/ prefixes:
    # path('v1/', include((router.urls, 'v1'), namespace='v1')),
    # path('v2/', include((router.urls, 'v2'), namespace='v2')),
]
