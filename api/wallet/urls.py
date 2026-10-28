# api/wallet/urls.py
"""
FINAL — All wallet URLs wired.
Include in main urls.py:
    path("api/wallet/", include("api.wallet.urls")),
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .viewsets import (
    WalletViewSet, WalletTransactionViewSet,
    WithdrawalRequestViewSet, WithdrawalMethodViewSet,
    BalanceHistoryViewSet, BalanceBonusViewSet,
    LedgerEntryViewSet, ReconciliationViewSet,
    EarningRecordViewSet, EarningSummaryViewSet,
    WithdrawalBatchViewSet, WalletInsightViewSet,
    LiabilityReportViewSet, AdminWalletViewSet,
    PublicWalletViewSet,
)

try:
    from .views_extra import (
        KYCVerificationViewSet, PayoutScheduleViewSet,
        PublisherLevelViewSet, PointsLedgerViewSet,
        PerformanceBonusViewSet, GeoRateViewSet,
        ReferralProgramViewSet, InstantPayoutViewSet,
        MassPayoutJobViewSet, DisputeCaseViewSet,
        RefundRequestViewSet, FraudScoreViewSet,
        AMLFlagViewSet, EarningOfferViewSet,
        WithdrawalWhitelistViewSet, SecurityEventViewSet,
        WebhookEndpointViewSet, TaxRecordViewSet,
    )
    EXTRA = True
except ImportError:
    EXTRA = False

router = DefaultRouter()

# ── Core ───────────────────────────────────────────────────────
router.register(r"wallets",             WalletViewSet,            basename="wallet")
router.register(r"transactions",        WalletTransactionViewSet, basename="transaction")

# ── Withdrawal ─────────────────────────────────────────────────
router.register(r"withdrawal-requests", WithdrawalRequestViewSet,  basename="withdrawal-request")
router.register(r"withdrawal-methods",  WithdrawalMethodViewSet,   basename="withdrawal-method")
router.register(r"withdrawal-batches",  WithdrawalBatchViewSet,    basename="withdrawal-batch")

# ── Balance ────────────────────────────────────────────────────
router.register(r"balance-history",     BalanceHistoryViewSet,     basename="balance-history")
router.register(r"balance-bonuses",     BalanceBonusViewSet,       basename="balance-bonus")

# ── Ledger ─────────────────────────────────────────────────────
router.register(r"ledger-entries",      LedgerEntryViewSet,        basename="ledger-entry")
router.register(r"reconciliations",     ReconciliationViewSet,     basename="reconciliation")

# ── Earning ────────────────────────────────────────────────────
router.register(r"earning-records",     EarningRecordViewSet,      basename="earning-record")
router.register(r"earning-summaries",   EarningSummaryViewSet,     basename="earning-summary")

# ── Analytics ──────────────────────────────────────────────────
router.register(r"wallet-insights",     WalletInsightViewSet,      basename="wallet-insight")
router.register(r"liability-reports",   LiabilityReportViewSet,    basename="liability-report")

# ── Admin ──────────────────────────────────────────────────────
router.register(r"admin-wallets",       AdminWalletViewSet,        basename="admin-wallet")
router.register(r"public",             PublicWalletViewSet,        basename="public-wallet")

# ── CPAlead + World-class ──────────────────────────────────────
if EXTRA:
    router.register(r"kyc",                 KYCVerificationViewSet,    basename="kyc")
    router.register(r"payout-schedules",    PayoutScheduleViewSet,     basename="payout-schedule")
    router.register(r"publisher-levels",    PublisherLevelViewSet,     basename="publisher-level")
    router.register(r"points",              PointsLedgerViewSet,       basename="points")
    router.register(r"performance-bonuses", PerformanceBonusViewSet,   basename="performance-bonus")
    router.register(r"geo-rates",           GeoRateViewSet,            basename="geo-rate")
    router.register(r"referral-programs",   ReferralProgramViewSet,    basename="referral-program")
    router.register(r"instant-payouts",     InstantPayoutViewSet,      basename="instant-payout")
    router.register(r"mass-payouts",        MassPayoutJobViewSet,      basename="mass-payout")
    router.register(r"disputes",            DisputeCaseViewSet,        basename="dispute")
    router.register(r"refunds",             RefundRequestViewSet,      basename="refund")
    router.register(r"fraud-scores",        FraudScoreViewSet,         basename="fraud-score")
    router.register(r"aml-flags",           AMLFlagViewSet,            basename="aml-flag")
    router.register(r"offers",              EarningOfferViewSet,       basename="offer")
    router.register(r"whitelist",           WithdrawalWhitelistViewSet, basename="whitelist")
    router.register(r"security-events",     SecurityEventViewSet,      basename="security-event")
    router.register(r"webhook-endpoints",   WebhookEndpointViewSet,    basename="webhook-endpoint")
    router.register(r"tax-records",         TaxRecordViewSet,          basename="tax-record")

# ── AI Insights ────────────────────────────────────────────────
try:
    from .viewsets.AIInsightViewSet import AIInsightViewSet
    router.register(r"ai-insights", AIInsightViewSet, basename="ai-insight")
except Exception:
    pass

urlpatterns = [
    path("", include(router.urls)),
    # path("webhook/<str:gateway>/", ...receive_webhook...),  # Removed: not in new api_views
    # path("health/", ...wallet_health...),  # Removed: not in new api_views
]

# ── Offerwall Postbacks ────────────────────────────────────────
try:
    from .views.postback_views import PostbackView, OfferwallListView, SmartwallUrlView
    urlpatterns += [
        path("postback/<str:platform>/", PostbackView.as_view(),     name="wallet-postback"),
        path("offerwall/",               OfferwallListView.as_view(), name="wallet-offers"),
        path("smartwall-urls/",          SmartwallUrlView.as_view(),  name="wallet-smartwall-urls"),
    ]
except Exception:
    pass

# ── Smart Link + Click Tracking ────────────────────────────────
try:
    from .resources import SmartLinkRouter, ClickTracker, SubIDTracker
    from rest_framework.decorators import api_view, permission_classes
    from rest_framework.permissions import IsAuthenticated, AllowAny
    from rest_framework.response import Response

    @api_view(["GET"])
    @permission_classes([IsAuthenticated])
    def smart_link_view(request):
        result = SmartLinkRouter.route(
            publisher_id=request.user.id,
            country_code=request.query_params.get("country", "BD"),
            device_type=request.query_params.get("device", "desktop"),
            sub_id=request.query_params.get("sub_id", ""),
        )
        return Response(result)

    @api_view(["POST"])
    @permission_classes([AllowAny])
    def record_click_view(request):
        from .validators import safe_ip_address
        ip = safe_ip_address(request.META.get("REMOTE_ADDR", ""))
        ok = ClickTracker.record_click(
            click_id=request.data.get("click_id", ""),
            offer_id=int(request.data.get("offer_id", 0)),
            publisher_id=int(request.data.get("pub_id", 0)),
            ip_address=ip,
            sub_id=request.data.get("sub_id", ""),
            country_code=request.data.get("country", ""),
            device_type=request.data.get("device", ""),
        )
        return Response({"recorded": ok})

    @api_view(["GET"])
    @permission_classes([IsAuthenticated])
    def sub_id_report_view(request):
        report = SubIDTracker.get_report(request.user.id)
        return Response({"success": True, "data": report})

    urlpatterns += [
        path("smart-link/", smart_link_view,    name="wallet-smart-link"),
        path("clicks/",     record_click_view,  name="wallet-click-record"),
        path("sub-ids/",    sub_id_report_view, name="wallet-sub-id-report"),
    ]
except Exception:
    pass

# ── Gamification: Scratchcard + Spin Wheel ─────────────────────
try:
    from .viewsets.GamificationViewSet import (
        ScratchcardView, SpinWheelView, GamificationHistoryView,
    )
    urlpatterns += [
        path("scratchcard/",          ScratchcardView.as_view(),          name="wallet-scratchcard"),
        path("scratchcard/claim/",    ScratchcardView.as_view(),          name="wallet-scratchcard-claim"),
        path("spinwheel/config/",     SpinWheelView.as_view(),            name="wallet-spinwheel-config"),
        path("spinwheel/",            SpinWheelView.as_view(),            name="wallet-spinwheel"),
        path("spinwheel/spin/",       SpinWheelView.as_view(),            name="wallet-spinwheel-spin"),
        path("gamification/history/", GamificationHistoryView.as_view(),  name="wallet-gamification-history"),
    ]
except Exception:
    pass

# ── Revenue Sharing: Advertiser + Publisher ────────────────────
try:
    from .viewsets.RevenueSharingViewSet import (
        AdvertiserAccountView, AdvertiserDepositView, CampaignListView,
        AdvertiserInvoiceListView, PublisherEarningsSummaryView, PublisherEarningsListView,
    )
    urlpatterns += [
        path("advertiser/account/",         AdvertiserAccountView.as_view(),      name="wallet-advertiser-account"),
        path("advertiser/deposit/",         AdvertiserDepositView.as_view(),      name="wallet-advertiser-deposit"),
        path("advertiser/campaigns/",       CampaignListView.as_view(),           name="wallet-advertiser-campaigns"),
        path("advertiser/invoices/",        AdvertiserInvoiceListView.as_view(),  name="wallet-advertiser-invoices"),
        path("publisher/earnings/summary/", PublisherEarningsSummaryView.as_view(), name="wallet-publisher-summary"),
        path("publisher/earnings/",         PublisherEarningsListView.as_view(),  name="wallet-publisher-earnings"),
    ]
except Exception:
    pass

# ── Push Notification Device Token Management ──────────────────
try:
    from rest_framework.decorators import api_view, permission_classes
    from rest_framework.permissions import IsAuthenticated
    from rest_framework.response import Response
    from .push_notification_service import PushNotificationService

    @api_view(["POST"])
    @permission_classes([IsAuthenticated])
    def register_device_token(request):
        token_str   = request.data.get("token", "").strip()
        platform    = request.data.get("platform", "android")
        device_name = request.data.get("device_name", "")
        app_version = request.data.get("app_version", "")
        if not token_str:
            return Response({"error": "token required"}, status=400)
        dt = PushNotificationService.register_token(
            request.user, platform, token_str, device_name, app_version,
        )
        return Response({"id": str(dt.id), "platform": dt.platform, "registered": True})

    @api_view(["POST"])
    @permission_classes([IsAuthenticated])
    def unregister_device_token(request):
        PushNotificationService.unregister_token(request.data.get("token", ""))
        return Response({"unregistered": True})

    @api_view(["POST"])
    @permission_classes([IsAuthenticated])
    def mark_push_opened(request):
        PushNotificationService.mark_opened(request.data.get("log_id", ""))
        return Response({"ok": True})

    urlpatterns += [
        path("push/register/",   register_device_token,   name="wallet-push-register"),
        path("push/unregister/", unregister_device_token, name="wallet-push-unregister"),
        path("push/opened/",     mark_push_opened,        name="wallet-push-opened"),
    ]
except Exception:
    pass
