# api/offer_inventory/urls.py
from django.urls import path, include
from rest_framework.routers import SimpleRouter as DefaultRouter
from . import views

app_name = 'offer_inventory'

router = DefaultRouter()
router.register(r'offers',          views.OfferViewSet,           basename='offer')
router.register(r'networks',        views.OfferNetworkViewSet,    basename='network')
router.register(r'categories',      views.OfferCategoryViewSet,   basename='category')
router.register(r'conversions',     views.ConversionViewSet,      basename='conversion')
router.register(r'withdrawals',     views.WithdrawalViewSet,      basename='withdrawal')
router.register(r'payment-methods', views.PaymentMethodViewSet,   basename='payment-method')
router.register(r'notifications',   views.NotificationViewSet,    basename='notification')
router.register(r'blacklisted-ips', views.BlacklistedIPViewSet,   basename='blacklisted-ip')
router.register(r'fraud-attempts',  views.FraudAttemptViewSet,    basename='fraud-attempt')
router.register(r'risk-profiles',   views.UserRiskProfileViewSet, basename='risk-profile')
router.register(r'network-stats',   views.NetworkStatViewSet,     basename='network-stat')
router.register(r'master-switches', views.MasterSwitchViewSet,    basename='master-switch')
router.register(r'settings',        views.SystemSettingViewSet,   basename='setting')
router.register(r'campaigns',       views.CampaignViewSet,        basename='campaign')
router.register(r'smart-links',     views.SmartLinkViewSet,       basename='smart-link')
router.register(r'tickets',         views.FeedbackTicketViewSet,  basename='ticket')
router.register(r'ab-tests',        views.ABTestViewSet,          basename='ab-test')

urlpatterns = [
    # ── Router ──────────────────────────────────────────────────────────
    path('', include(router.urls)),

    # ── Postback & Pixel ────────────────────────────────────────────────
    path('postback/',                      views.PostbackView.as_view(),                  name='postback'),
    path('postback/<str:network_slug>/',   views.PostbackView.as_view(),                  name='postback-network'),
    path('pixel/impression/<str:offer_id>/', views.PixelImpressionView.as_view(),        name='pixel-impression'),
    path('pixel/conversion/<str:token>/',  views.PixelConversionView.as_view(),           name='pixel-conversion'),

    # ── SmartLink ────────────────────────────────────────────────────────
    path('go/<slug:slug>/',                views.SmartLinkRedirectView.as_view(),          name='smartlink-redirect'),

    # ── User endpoints ───────────────────────────────────────────────────
    path('me/profile/',                    views.MyProfileView.as_view(),                 name='my-profile'),
    path('me/kyc/',                        views.MyKYCView.as_view(),                     name='my-kyc'),
    path('me/conversions/',                views.MyConversionsView.as_view(),             name='my-conversions'),
    path('me/transactions/',               views.TransactionHistoryView.as_view(),        name='my-transactions'),
    path('me/referrals/',                  views.ReferralsView.as_view(),                 name='my-referrals'),
    path('me/achievements/',               views.AchievementsView.as_view(),              name='my-achievements'),
    path('me/wallet/',                     views.MyWalletView.as_view(),                  name='my-wallet'),
    path('me/heatmap/',                    views.UserHeatmapView.as_view(),               name='my-heatmap'),
    path('me/engagement/',                 views.EngagementScoreView.as_view(),           name='my-engagement'),
    path('me/dashboard/',                  views.UserAnalyticsDashboardView.as_view(),    name='my-dashboard'),
    path('me/language/',                   views.LanguageView.as_view(),                  name='my-language'),
    path('me/theme/',                      views.ThemeView.as_view(),                     name='my-theme'),

    # ── Compliance ───────────────────────────────────────────────────────
    path('compliance/tos/',                views.TOSAcceptanceView.as_view(),             name='tos'),
    path('compliance/privacy-consent/',    views.PrivacyConsentView.as_view(),            name='privacy-consent'),
    path('compliance/kyc/verify/',         views.KYCVerifyView.as_view(),                 name='kyc-verify'),

    # ── Analytics ────────────────────────────────────────────────────────
    path('analytics/dashboard/',           views.DashboardStatsView.as_view(),            name='dashboard-stats'),
    path('analytics/kpis/',                views.PlatformKPIView.as_view(),               name='platform-kpis'),
    path('analytics/revenue-forecast/',    views.RevenueForecastView.as_view(),           name='revenue-forecast'),
    path('analytics/cohorts/',             views.CohortAnalysisView.as_view(),            name='cohort-analysis'),
    path('analytics/network-roi/',         views.NetworkROIView.as_view(),                name='network-roi'),
    path('analytics/heatmap/',             views.PlatformHeatmapView.as_view(),           name='platform-heatmap'),
    path('analytics/retention/',           views.RetentionView.as_view(),                 name='retention'),
    path('analytics/churn/',               views.ChurnView.as_view(),                     name='churn'),
    path('analytics/full/',                views.FullAnalyticsDashboardView.as_view(),    name='full-analytics'),

    # ── Reports (CSV + JSON) ─────────────────────────────────────────────
    path('reports/revenue/',               views.RevenueReportView.as_view(),             name='report-revenue'),
    path('reports/conversions/',           views.ConversionReportView.as_view(),          name='report-conversions'),
    path('reports/conversions/summary/',   views.ConversionSummaryView.as_view(),         name='report-conv-summary'),
    path('reports/withdrawals/',           views.WithdrawalReportView.as_view(),          name='report-withdrawals'),
    path('reports/fraud/',                 views.FraudReportView.as_view(),               name='report-fraud'),
    path('reports/networks/',              views.NetworkComparisonView.as_view(),         name='report-networks'),
    path('reports/user-earnings/',         views.UserEarningsReportView.as_view(),        name='report-user-earnings'),
    path('reports/user-growth/',           views.UserGrowthReportView.as_view(),          name='report-user-growth'),
    path('reports/user-ltv/',              views.UserLTVReportView.as_view(),             name='report-user-ltv'),
    path('reports/postback-delivery/',     views.PostbackDeliveryReportView.as_view(),    name='report-postback-delivery'),
    path('reports/payout-reconciliation/', views.PayoutReconciliationView.as_view(),      name='report-payout-recon'),

    # ── Marketing ────────────────────────────────────────────────────────
    path('marketing/campaign/',            views.MarketingCampaignView.as_view(),         name='marketing-campaign'),
    path('marketing/promo/redeem/',        views.PromoCodeRedeemView.as_view(),           name='promo-redeem'),
    path('marketing/push/subscribe/',      views.PushSubscribeView.as_view(),             name='push-subscribe'),
    path('marketing/push/unsubscribe/',    views.PushUnsubscribeView.as_view(),           name='push-unsubscribe'),
    path('marketing/leaderboard/',         views.LeaderboardView.as_view(),               name='leaderboard'),

    # ── Business ─────────────────────────────────────────────────────────
    path('business/executive-summary/',    views.ExecutiveSummaryView.as_view(),          name='executive-summary'),
    path('business/advertiser/',           views.AdvertiserPortalView.as_view(),          name='advertiser-portal'),
    path('business/billing/',              views.BillingView.as_view(),                   name='billing'),
    path('business/compliance/gdpr/',      views.GDPRView.as_view(),                      name='gdpr'),

    # ── Affiliate Advanced ───────────────────────────────────────────────
    path('affiliate/payout-bump/',         views.PayoutBumpView.as_view(),                name='payout-bump'),
    path('affiliate/tracking-links/',      views.TrackingLinkView.as_view(),              name='tracking-links'),
    path('affiliate/postback-test/',       views.PostbackTesterView.as_view(),            name='postback-test'),
    path('affiliate/offer-scheduler/',     views.OfferSchedulerView.as_view(),            name='offer-scheduler'),

    # ── SDK ──────────────────────────────────────────────────────────────
    path('sdk/token/',                     views.SDKTokenView.as_view(),                  name='sdk-token'),
    path('sdk/offers/',                    views.SDKOffersView.as_view(),                 name='sdk-offers'),
    path('sdk/config/',                    views.SDKConfigView.as_view(),                 name='sdk-config'),

    # ── Optimization ─────────────────────────────────────────────────────
    path('ops/workers/',                   views.WorkerPoolView.as_view(),                name='worker-pool'),
    path('ops/bandwidth/',                 views.BandwidthView.as_view(),                 name='bandwidth'),
    path('ops/query-optimizer/',           views.QueryOptimizerView.as_view(),            name='query-optimizer'),

    # ── Webhook Management ───────────────────────────────────────────────
    path('webhooks/',                      views.WebhookConfigListView.as_view(),         name='webhook-list'),
    path('webhooks/test/',                 views.WebhookTestView.as_view(),               name='webhook-test'),

    # ── Master Switch ────────────────────────────────────────────────────
    path('features/',                      views.MasterSwitchListView.as_view(),          name='feature-flags'),

    # ── Bulk Operations ──────────────────────────────────────────────────
    path('bulk/offers/activate/',          views.BulkOfferActivateView.as_view(),         name='bulk-offer-activate'),
    path('bulk/offers/pause/',             views.BulkOfferPauseView.as_view(),            name='bulk-offer-pause'),
    path('bulk/conversions/approve/',      views.BulkConversionApproveView.as_view(),     name='bulk-conv-approve'),
    path('bulk/ips/block/',                views.BulkIPBlockView.as_view(),               name='bulk-ip-block'),

    # ── System ───────────────────────────────────────────────────────────
    path('circuits/',                      views.CircuitStatusView.as_view(),             name='circuit-status'),
    path('health/',                        views.HealthCheckView.as_view(),               name='health'),
    path('emergency/',                     views.EmergencyShutdownView.as_view(),         name='emergency-shutdown'),
    path('security-audit/',                views.SecurityAuditView.as_view(),             name='security-audit'),
    path('recovery/',                      views.SystemRecoveryView.as_view(),            name='system-recovery'),

    # ── RTB Engine ───────────────────────────────────────────────────────────
    path('rtb/bid/',                       views.RTBBidView.as_view(),            name='rtb-bid'),
    path('rtb/win/',                       views.RTBWinView.as_view(),            name='rtb-win'),
    path('rtb/stats/',                     views.RTBStatsView.as_view(),          name='rtb-stats'),
    path('rtb/floor/',                     views.RTBBidFloorView.as_view(),       name='rtb-floor'),

    # ── ML Fraud ─────────────────────────────────────────────────────────────
    path('ml/fraud/score/',                views.MLFraudScoreView.as_view(),      name='ml-fraud-score'),
    path('ml/fraud/train/',                views.MLFraudTrainView.as_view(),      name='ml-fraud-train'),
    path('ml/fraud/anomalies/',            views.MLAnomalyView.as_view(),         name='ml-anomalies'),

    # ── Publisher SDK ─────────────────────────────────────────────────────────
    path('publisher/register/',            views.PublisherRegisterView.as_view(), name='publisher-register'),
    path('publisher/<str:publisher_id>/approve/', views.PublisherApproveView.as_view(), name='publisher-approve'),
    path('publisher/dashboard/',           views.PublisherDashboardView.as_view(),name='publisher-dashboard'),
    path('publisher/apps/',                views.PublisherAppView.as_view(),      name='publisher-apps'),
    path('publisher/sdk-config/',          views.SDKConfigView.as_view(),         name='publisher-sdk-config'),
    path('publisher/payout/',              views.PublisherPayoutView.as_view(),   name='publisher-payout'),

    # ── Offer Search & Discovery ─────────────────────────────────────────────
    path('search/',                        views.OfferSearchView.as_view(),        name='offer-search'),
    path('search/autocomplete/',           views.OfferAutocompleteView.as_view(),  name='offer-autocomplete'),
    path('search/filters/',                views.SearchFiltersView.as_view(),       name='search-filters'),
    path('trending/',                      views.TrendingOffersView.as_view(),      name='trending-offers'),

    # ── Offer Approval Workflow ──────────────────────────────────────────────
    path('offers/<uuid:offer_id>/submit-review/', views.OfferSubmitReviewView.as_view(), name='offer-submit-review'),
    path('offers/<uuid:offer_id>/approve-reject/', views.OfferApproveRejectView.as_view(), name='offer-approve-reject'),
    path('admin/review-queue/',            views.OfferReviewQueueView.as_view(),   name='offer-review-queue'),
    path('admin/offers/bulk-approve/',     views.OfferBulkApproveView.as_view(),   name='offer-bulk-approve'),

    # ── Multi-Currency Wallet ────────────────────────────────────────────────
    path('wallet/balances/',               views.MultiCurrencyBalanceView.as_view(), name='wallet-balances'),
    path('wallet/exchange/',               views.CurrencyExchangeView.as_view(),   name='currency-exchange'),
    path('wallet/rates/',                  views.ExchangeRatesView.as_view(),       name='exchange-rates'),
    path('wallet/local-payout/',           views.LocalPayoutView.as_view(),         name='local-payout'),

    # ── Notification Preferences ─────────────────────────────────────────────
    path('me/notification-prefs/',         views.NotificationPrefsView.as_view(),  name='notification-prefs'),

    # ── A/B Testing ──────────────────────────────────────────────────────────
    path('ab-tests/<str:test_name>/results/', views.ABTestResultsView.as_view(),   name='ab-test-results'),

    # ── System Health & Recovery ─────────────────────────────────────────────
    path('admin/health/',                  views.SystemHealthDetailView.as_view(), name='system-health-detail'),
    path('admin/recovery/',                views.SystemRecoveryView.as_view(),     name='system-recovery'),
    path('admin/master-switch/',           views.MasterSwitchView.as_view(),       name='master-switch'),
    path('admin/security-audit/',          views.SecurityAuditView.as_view(),      name='security-audit'),

    # ── Export ───────────────────────────────────────────────────────────────
    path('admin/export/',                  views.ExportView.as_view(),              name='data-export'),
]
