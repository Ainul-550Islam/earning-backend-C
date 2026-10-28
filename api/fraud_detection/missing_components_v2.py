# =============================================================================
# fraud_detection/missing_components_v2.py — DRY SHIM
#
# All Views and Services from this file have been promoted to:
#   Views    → views_offerwall_v2.py   (API endpoint classes)
#   Services → offerwall_services.py   (business logic)
#
# Import from those modules directly.
# =============================================================================
from api.fraud_detection.views_offerwall_v2 import (  # noqa: F401
    OfferwallEmbedView, OfferFeedAPIView, ConversionPixelView,
    RevenueReportExportView, PINSubmitOfferView, VideoOfferPostbackView,
    TrialOfferPostbackView, AdvertiserBillingView,
    OfferCatalogListAPIView, OfferCatalogDetailAPIView,
)
