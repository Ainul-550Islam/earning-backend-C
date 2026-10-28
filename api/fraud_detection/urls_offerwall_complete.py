# =============================================================================
# fraud_detection/urls_offerwall_complete.py
#
# Connects ALL offerwall / offer-catalog / revenue / advertiser views.
# WAS FLOATING: views_offerwall_v2.py had 10 view classes with zero URLs.
#
# Included by master urls.py under: path("offerwall-v2/", include(...))
# =============================================================================
from django.urls import path
from .views_offerwall_v2 import (
    OfferwallEmbedView,
    OfferFeedAPIView,
    ConversionPixelView,
    RevenueReportExportView,
    PINSubmitOfferView,
    VideoOfferPostbackView,
    TrialOfferPostbackView,
    AdvertiserBillingView,
    OfferCatalogListAPIView,
    OfferCatalogDetailAPIView,
)

app_name = "offerwall_v2"

urlpatterns = [
    # ── Offerwall embed ───────────────────────────────────────────────────────
    path("embed/",                 OfferwallEmbedView.as_view(),         name="embed"),
    path("feed/",                  OfferFeedAPIView.as_view(),           name="feed"),
    path("conversion-pixel/",      ConversionPixelView.as_view(),        name="conversion-pixel"),

    # ── Offer catalog ─────────────────────────────────────────────────────────
    path("catalog/",               OfferCatalogListAPIView.as_view(),    name="catalog-list"),
    path("catalog/<int:offer_id>/", OfferCatalogDetailAPIView.as_view(), name="catalog-detail"),

    # ── Offer types (postbacks / submit) ─────────────────────────────────────
    path("pin-submit/",            PINSubmitOfferView.as_view(),         name="pin-submit"),
    path("video-postback/",        VideoOfferPostbackView.as_view(),     name="video-postback"),
    path("trial-postback/",        TrialOfferPostbackView.as_view(),     name="trial-postback"),

    # ── Revenue / billing ─────────────────────────────────────────────────────
    path("revenue/export/",        RevenueReportExportView.as_view(),    name="revenue-export"),
    path("advertiser/billing/",    AdvertiserBillingView.as_view(),      name="advertiser-billing"),
]
