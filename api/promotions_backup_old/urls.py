# =============================================================================
# api/promotions/urls.py
# =============================================================================

from django.urls import path, include
from rest_framework.routers import SimpleRouter as DefaultRouter
from . import views
from .views import (
    PromotionCategoryViewSet, PlatformViewSet,
    RewardPolicyViewSet, CurrencyRateViewSet,
    CampaignViewSet,
    TaskSubmissionViewSet, DisputeViewSet,
    PromotionTransactionViewSet, EscrowWalletViewSet,
    ReferralCommissionLogViewSet,
    BlacklistViewSet, FraudReportViewSet,
    DeviceFingerprintViewSet, UserReputationViewSet,
    CampaignAnalyticsViewSet,
)

app_name = 'promotions'

router = DefaultRouter()
router.register(r'categories',           PromotionCategoryViewSet,      basename='category')
router.register(r'platforms',            PlatformViewSet,               basename='platform')
router.register(r'reward-policies',      RewardPolicyViewSet,           basename='reward-policy')
router.register(r'currency-rates',       CurrencyRateViewSet,           basename='currency-rate')
router.register(r'campaigns',            CampaignViewSet,               basename='campaign')
router.register(r'submissions',          TaskSubmissionViewSet,         basename='submission')
router.register(r'disputes',             DisputeViewSet,                basename='dispute')
router.register(r'transactions',         PromotionTransactionViewSet,   basename='transaction')
router.register(r'escrow',               EscrowWalletViewSet,           basename='escrow')
router.register(r'referral-commissions', ReferralCommissionLogViewSet,  basename='referral-commission')
router.register(r'blacklist',            BlacklistViewSet,              basename='blacklist')
router.register(r'fraud-reports',        FraudReportViewSet,            basename='fraud-report')
router.register(r'device-fingerprints',  DeviceFingerprintViewSet,      basename='device-fingerprint')
router.register(r'reputation',           UserReputationViewSet,         basename='reputation')
router.register(r'analytics',            CampaignAnalyticsViewSet,      basename='analytics')

urlpatterns = [
    # ── Standalone views (must be before router) ──────────────────────────────
    path('user-offers/',                views.user_offers,                   name='user-offers'),
    path('bidding/',                    views.bidding_list,                  name='bidding-list'),
    path('bidding/<int:pk>/resolve/',   views.bidding_resolve,               name='bidding-resolve'),
    path('quick-create/',               views.campaign_quick_create,         name='campaign-quick-create'),
    path('quick-update/<int:pk>/',      views.campaign_quick_update,         name='campaign-quick-update'),
    path('quick-delete/<int:pk>/',      views.campaign_quick_delete,         name='campaign-quick-delete'),
    path('analytics/overall/',          views.promotions_analytics_overall,  name='analytics-overall'),
    path('stats/',                      views.promotions_stats,              name='promotions-stats'),
    path('<int:pk>/sparkline/',          views.promotions_sparkline,          name='promotions-sparkline'),

    # ── Frontend shortcut aliases (/promotions/ → /promotions/campaigns/) ────
    # Frontend calls GET /api/promotions/ for list
    # We alias it to campaign list + quick create/update/delete
    path('',                            views.promotions_list_alias,         name='promotions-list'),
    path('<int:pk>/',                   views.promotions_detail_alias,       name='promotions-detail'),
    path('<int:pk>/pause/',             views.promotions_pause_alias,        name='promotions-pause'),
    path('<int:pk>/resume/',            views.promotions_resume_alias,       name='promotions-resume'),
    path('<int:pk>/archive/',           views.promotions_archive_alias,      name='promotions-archive'),

    # ── Router URLs ───────────────────────────────────────────────────────────
    path('', include(router.urls)),
]

# =============================================================================
# FULL URL REFERENCE:
# GET/POST   /api/promotions/                    ← alias for campaigns list/create
# GET        /api/promotions/:id/                ← campaign detail
# POST       /api/promotions/:id/pause/          ← pause
# POST       /api/promotions/:id/resume/         ← resume
# POST       /api/promotions/:id/archive/        ← archive
# GET        /api/promotions/stats/              ← dashboard stats
# GET        /api/promotions/:id/sparkline/      ← chart data
# GET/POST   /api/promotions/campaigns/          ← full campaign CRUD
# POST       /api/promotions/campaigns/:id/approve/
# POST       /api/promotions/campaigns/:id/duplicate/
# POST       /api/promotions/campaigns/:id/budget_top_up/
# GET/POST   /api/promotions/submissions/
# POST       /api/promotions/submissions/:id/approve/
# POST       /api/promotions/submissions/:id/reject/
# GET/POST   /api/promotions/disputes/
# POST       /api/promotions/disputes/:id/resolve/
# GET        /api/promotions/transactions/
# GET        /api/promotions/analytics/?campaign=1
# =============================================================================