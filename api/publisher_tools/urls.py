# api/publisher_tools/urls.py
"""
Publisher Tools — URL Configuration।
সব ViewSet এখানে router-এ register হয়।
"""
from django.urls import path, include
from rest_framework.routers import SimpleRouter as DefaultRouter

from .views import (
    PublisherViewSet,
    SiteViewSet,
    AppViewSet,
    InventoryVerificationViewSet,
    AdUnitViewSet,
    AdPlacementViewSet,
    MediationGroupViewSet,
    WaterfallItemViewSet,
    HeaderBiddingConfigViewSet,
    PublisherEarningViewSet,
    PayoutThresholdViewSet,
    PublisherInvoiceViewSet,
    TrafficSafetyLogViewSet,
    SiteQualityMetricViewSet,
)

router = DefaultRouter()

# ── Publisher & Inventory ──────────────────────────────────────────────────────
router.register(r'publishers',            PublisherViewSet,            basename='publisher')
router.register(r'sites',                 SiteViewSet,                 basename='site')
router.register(r'apps',                  AppViewSet,                  basename='app')
router.register(r'verifications',         InventoryVerificationViewSet,basename='verification')

# ── Ad Units & Placements ─────────────────────────────────────────────────────
router.register(r'ad-units',              AdUnitViewSet,               basename='ad-unit')
router.register(r'placements',            AdPlacementViewSet,          basename='placement')

# ── Mediation & Waterfall ─────────────────────────────────────────────────────
router.register(r'mediation-groups',      MediationGroupViewSet,       basename='mediation-group')
router.register(r'waterfall-items',       WaterfallItemViewSet,        basename='waterfall-item')
router.register(r'header-bidding',        HeaderBiddingConfigViewSet,  basename='header-bidding')

# ── Earnings & Payments ───────────────────────────────────────────────────────
router.register(r'earnings',              PublisherEarningViewSet,     basename='earning')
router.register(r'payout-thresholds',     PayoutThresholdViewSet,      basename='payout-threshold')
router.register(r'invoices',              PublisherInvoiceViewSet,     basename='invoice')

# ── Fraud & Quality ───────────────────────────────────────────────────────────
router.register(r'traffic-safety-logs',   TrafficSafetyLogViewSet,     basename='traffic-safety-log')
router.register(r'quality-metrics',       SiteQualityMetricViewSet,    basename='quality-metric')

urlpatterns = [
    path('', include(router.urls)),
]

# ── Full Endpoint Reference ───────────────────────────────────────────────────
# PREFIX: /api/publisher-tools/
#
# PUBLISHER
# GET    /publishers/                       — List all publishers (admin)
# POST   /publishers/                       — Register publisher profile
# GET    /publishers/{id}/                  — Publisher detail
# PATCH  /publishers/{id}/                  — Update publisher
# GET    /publishers/{id}/stats/            — Dashboard stats
# POST   /publishers/{id}/approve/          — Approve (admin)
# POST   /publishers/{id}/suspend/          — Suspend (admin)
# POST   /publishers/{id}/regenerate_api_key/ — New API key
# GET    /publishers/{id}/payout_eligibility/ — Payout check
#
# SITE
# GET    /sites/                            — List sites
# POST   /sites/                            — Register site
# GET    /sites/{id}/                       — Site detail
# PATCH  /sites/{id}/                       — Update site
# POST   /sites/{id}/verify/               — Trigger verification
# POST   /sites/{id}/approve/              — Approve (admin)
# POST   /sites/{id}/reject/               — Reject (admin)
# POST   /sites/{id}/refresh_ads_txt/      — Refresh ads.txt
# GET    /sites/{id}/analytics/            — Site analytics
# GET    /sites/{id}/quality_metrics/      — Quality metrics
# GET    /sites/{id}/ad_units/             — Site ad units
#
# APP
# GET    /apps/                             — List apps
# POST   /apps/                             — Register app
# GET    /apps/{id}/                        — App detail
# PATCH  /apps/{id}/                        — Update app
# POST   /apps/{id}/approve/               — Approve (admin)
# POST   /apps/{id}/reject/                — Reject (admin)
# GET    /apps/{id}/ad_units/              — App ad units
#
# VERIFICATION
# GET    /verifications/                    — List verifications
# GET    /verifications/{id}/              — Verification detail
# POST   /verifications/{id}/check/        — Re-check verification
#
# AD UNIT
# GET    /ad-units/                         — List ad units
# POST   /ad-units/                         — Create ad unit
# GET    /ad-units/{id}/                    — Ad unit detail
# PATCH  /ad-units/{id}/                    — Update ad unit
# POST   /ad-units/{id}/pause/             — Pause ad unit
# POST   /ad-units/{id}/activate/          — Activate ad unit
# GET    /ad-units/{id}/tag_code/          — Get JS tag code
# GET    /ad-units/{id}/performance/       — Performance stats
# GET/POST /ad-units/{id}/targeting/       — Get/Update targeting
# GET    /ad-units/{id}/placements/        — List placements
# GET    /ad-units/{id}/mediation/         — Mediation group
#
# PLACEMENT
# GET    /placements/                       — List placements
# POST   /placements/                       — Create placement
# PATCH  /placements/{id}/                 — Update placement
# POST   /placements/{id}/toggle/          — Toggle active status
#
# MEDIATION GROUP
# GET    /mediation-groups/                 — List groups
# POST   /mediation-groups/                 — Create group
# GET    /mediation-groups/{id}/            — Group detail
# POST   /mediation-groups/{id}/optimize/  — Auto-optimize waterfall
# GET    /mediation-groups/{id}/waterfall/ — Get ordered waterfall
# POST   /mediation-groups/{id}/reorder/   — Reorder waterfall
#
# WATERFALL ITEM
# GET    /waterfall-items/                  — List items
# POST   /waterfall-items/                  — Add item
# PATCH  /waterfall-items/{id}/            — Update item
# DELETE /waterfall-items/{id}/            — Remove item
# POST   /waterfall-items/{id}/toggle_status/ — Active/Paused toggle
#
# HEADER BIDDING
# GET    /header-bidding/                   — List configs
# POST   /header-bidding/                   — Add config
# PATCH  /header-bidding/{id}/             — Update config
# DELETE /header-bidding/{id}/             — Remove config
#
# EARNINGS
# GET    /earnings/                         — List earnings
# GET    /earnings/summary/                 — Aggregated summary
# GET    /earnings/by_country/             — Country breakdown
# GET    /earnings/by_ad_unit/             — Ad unit breakdown
#
# PAYOUT THRESHOLD
# GET    /payout-thresholds/               — List payment methods
# POST   /payout-thresholds/               — Add payment method
# PATCH  /payout-thresholds/{id}/          — Update
# DELETE /payout-thresholds/{id}/          — Remove
# POST   /payout-thresholds/{id}/set_primary/ — Set as primary
# POST   /payout-thresholds/{id}/verify/   — Verify (admin)
#
# INVOICE
# GET    /invoices/                         — List invoices
# GET    /invoices/{id}/                    — Invoice detail
# POST   /invoices/generate/               — Generate invoice (admin)
# POST   /invoices/{id}/issue/             — Issue invoice (admin)
# POST   /invoices/{id}/mark_paid/         — Mark paid (admin)
# POST   /invoices/{id}/dispute/           — Dispute invoice
#
# TRAFFIC SAFETY LOG
# GET    /traffic-safety-logs/             — List IVT logs
# GET    /traffic-safety-logs/{id}/        — Log detail
# POST   /traffic-safety-logs/{id}/take_action/ — Take action (admin)
# POST   /traffic-safety-logs/{id}/mark_false_positive/ — Mark FP (admin)
# GET    /traffic-safety-logs/summary/     — IVT summary by type
#
# QUALITY METRIC
# GET    /quality-metrics/                  — List metrics
# GET    /quality-metrics/{id}/             — Metric detail
# GET    /quality-metrics/alerts/           — Sites with alerts
# GET    /quality-metrics/trend/            — Quality trend
