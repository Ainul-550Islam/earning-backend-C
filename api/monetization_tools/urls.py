"""
api/monetization_tools/urls.py
================================
URL routing for all monetization_tools viewsets.
"""

from django.urls import path, include
from rest_framework.routers import SimpleRouter as DefaultRouter

from .views import (
    AdCampaignViewSet,
    AdUnitViewSet,
    AdNetworkViewSet,
    AdPlacementViewSet,
    OfferwallViewSet,
    OfferViewSet,
    OfferCompletionViewSet,
    RewardTransactionViewSet,
    ImpressionLogViewSet,
    ClickLogViewSet,
    ConversionLogViewSet,
    RevenueDailySummaryViewSet,
    SubscriptionPlanViewSet,
    UserSubscriptionViewSet,
    InAppPurchaseViewSet,
    PaymentTransactionViewSet,
    RecurringBillingViewSet,
    UserLevelViewSet,
    AchievementViewSet,
    LeaderboardRankViewSet,
    SpinWheelViewSet,
    ABTestViewSet,
    WaterfallConfigViewSet,
    FloorPriceConfigViewSet,
)

router = DefaultRouter()

# ── Ad Core ────────────────────────────────────────────────────────────────
router.register(r'campaigns',       AdCampaignViewSet,      basename='mt-campaign')
router.register(r'ad-units',        AdUnitViewSet,          basename='mt-ad-unit')
router.register(r'ad-networks',     AdNetworkViewSet,       basename='mt-ad-network')
router.register(r'ad-placements',   AdPlacementViewSet,     basename='mt-ad-placement')

# ── Offerwall ──────────────────────────────────────────────────────────────
router.register(r'offerwalls',      OfferwallViewSet,       basename='mt-offerwall')
router.register(r'offers',          OfferViewSet,           basename='mt-offer')
router.register(r'completions',     OfferCompletionViewSet, basename='mt-completion')
router.register(r'reward-txns',     RewardTransactionViewSet, basename='mt-reward-txn')

# ── Revenue Tracking ───────────────────────────────────────────────────────
router.register(r'impressions',     ImpressionLogViewSet,       basename='mt-impression')
router.register(r'clicks',          ClickLogViewSet,            basename='mt-click')
router.register(r'conversions',     ConversionLogViewSet,       basename='mt-conversion')
router.register(r'revenue-summary', RevenueDailySummaryViewSet, basename='mt-revenue-summary')

# ── Subscription & Payment ─────────────────────────────────────────────────
router.register(r'plans',           SubscriptionPlanViewSet,    basename='mt-plan')
router.register(r'subscriptions',   UserSubscriptionViewSet,    basename='mt-subscription')
router.register(r'purchases',       InAppPurchaseViewSet,       basename='mt-purchase')
router.register(r'payments',        PaymentTransactionViewSet,  basename='mt-payment')
router.register(r'billing',         RecurringBillingViewSet,    basename='mt-billing')

# ── Gamification ───────────────────────────────────────────────────────────
router.register(r'user-levels',     UserLevelViewSet,       basename='mt-user-level')
router.register(r'achievements',    AchievementViewSet,     basename='mt-achievement')
router.register(r'leaderboard',     LeaderboardRankViewSet, basename='mt-leaderboard')
router.register(r'spin-wheel',      SpinWheelViewSet,       basename='mt-spin-wheel')

# ── A/B Testing & Optimization ─────────────────────────────────────────────
router.register(r'ab-tests',        ABTestViewSet,          basename='mt-ab-test')
router.register(r'waterfall',       WaterfallConfigViewSet, basename='mt-waterfall')
router.register(r'floor-prices',    FloorPriceConfigViewSet, basename='mt-floor-price')

urlpatterns = [
    path('', include(router.urls)),
]

# ── Phase-2 routes ───────────────────────────────────────────────────────────
from .views import (
    AdPerformanceHourlyViewSet, AdPerformanceDailyViewSet, AdNetworkDailyStatViewSet,
    PointLedgerSnapshotViewSet, ABTestAssignmentViewSet, MonetizationConfigViewSet,
    AdCreativeViewSet, UserSegmentViewSet, UserSegmentMembershipViewSet,
    PostbackLogViewSet, PayoutMethodViewSet, PayoutRequestViewSet,
    ReferralProgramViewSet, ReferralLinkViewSet, ReferralCommissionViewSet,
    DailyStreakViewSet, SpinWheelConfigViewSet, PrizeConfigViewSet,
    FlashSaleViewSet, CouponViewSet, CouponUsageViewSet,
    FraudAlertViewSet, RevenueGoalViewSet, PublisherAccountViewSet,
    MonetizationNotificationTemplateViewSet,
)

router.register(r'perf/hourly',           AdPerformanceHourlyViewSet,       basename='mt-perf-hourly')
router.register(r'perf/daily',            AdPerformanceDailyViewSet,        basename='mt-perf-daily')
router.register(r'network-stats',         AdNetworkDailyStatViewSet,        basename='mt-network-stats')
router.register(r'ledger-snapshots',      PointLedgerSnapshotViewSet,       basename='mt-ledger-snap')
router.register(r'ab-assignments',        ABTestAssignmentViewSet,          basename='mt-ab-assign')
router.register(r'config',                MonetizationConfigViewSet,        basename='mt-config')
router.register(r'creatives',             AdCreativeViewSet,                basename='mt-creative')
router.register(r'segments',              UserSegmentViewSet,               basename='mt-segment')
router.register(r'segment-members',       UserSegmentMembershipViewSet,     basename='mt-seg-member')
router.register(r'postback-logs',         PostbackLogViewSet,               basename='mt-postback-log')
router.register(r'payout-methods',        PayoutMethodViewSet,              basename='mt-payout-method')
router.register(r'payout-requests',       PayoutRequestViewSet,             basename='mt-payout-request')
router.register(r'referral-programs',     ReferralProgramViewSet,           basename='mt-ref-program')
router.register(r'referral-links',        ReferralLinkViewSet,              basename='mt-ref-link')
router.register(r'referral-commissions',  ReferralCommissionViewSet,        basename='mt-ref-commission')
router.register(r'daily-streaks',         DailyStreakViewSet,               basename='mt-streak')
router.register(r'spin-configs',          SpinWheelConfigViewSet,           basename='mt-spin-config')
router.register(r'prizes',                PrizeConfigViewSet,               basename='mt-prize')
router.register(r'flash-sales',           FlashSaleViewSet,                 basename='mt-flash-sale')
router.register(r'coupons',               CouponViewSet,                    basename='mt-coupon')
router.register(r'coupon-usages',         CouponUsageViewSet,               basename='mt-coupon-usage')
router.register(r'fraud-alerts',          FraudAlertViewSet,                basename='mt-fraud-alert')
router.register(r'revenue-goals',         RevenueGoalViewSet,               basename='mt-rev-goal')
router.register(r'publisher-accounts',    PublisherAccountViewSet,          basename='mt-pub-account')
router.register(r'notif-templates',       MonetizationNotificationTemplateViewSet, basename='mt-notif-tmpl')
