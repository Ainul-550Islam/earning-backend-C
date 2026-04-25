# api/wallet/urls.py
"""
All wallet URLs — original routes + new viewset routes.
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

# ── Core ──────────────────────────────────────────────────────
router.register(r"wallets",              WalletViewSet,             basename="wallet")
router.register(r"transactions",         WalletTransactionViewSet,  basename="transaction")

# ── Withdrawal ────────────────────────────────────────────────
router.register(r"withdrawal-requests",  WithdrawalRequestViewSet,  basename="withdrawal-request")
router.register(r"withdrawal-methods",   WithdrawalMethodViewSet,   basename="withdrawal-method")
router.register(r"withdrawal-batches",   WithdrawalBatchViewSet,    basename="withdrawal-batch")

# ── Balance ───────────────────────────────────────────────────
router.register(r"balance-history",      BalanceHistoryViewSet,     basename="balance-history")
router.register(r"balance-bonuses",      BalanceBonusViewSet,       basename="balance-bonus")

# ── Ledger ────────────────────────────────────────────────────
router.register(r"ledger-entries",       LedgerEntryViewSet,        basename="ledger-entry")
router.register(r"reconciliations",      ReconciliationViewSet,     basename="reconciliation")

# ── Earning ───────────────────────────────────────────────────
router.register(r"earning-records",      EarningRecordViewSet,      basename="earning-record")
router.register(r"earning-summaries",    EarningSummaryViewSet,     basename="earning-summary")

# ── Analytics ─────────────────────────────────────────────────
router.register(r"wallet-insights",      WalletInsightViewSet,      basename="wallet-insight")
router.register(r"liability-reports",    LiabilityReportViewSet,    basename="liability-report")

# ── Admin ─────────────────────────────────────────────────────
router.register(r"admin-wallets",        AdminWalletViewSet,        basename="admin-wallet")
router.register(r"public",              PublicWalletViewSet,        basename="public-wallet")

# ── CPAlead + World-class ─────────────────────────────────────
if EXTRA:
    router.register(r"kyc",                  KYCVerificationViewSet,    basename="kyc")
    router.register(r"payout-schedules",     PayoutScheduleViewSet,     basename="payout-schedule")
    router.register(r"publisher-levels",     PublisherLevelViewSet,     basename="publisher-level")
    router.register(r"points",               PointsLedgerViewSet,       basename="points")
    router.register(r"performance-bonuses",  PerformanceBonusViewSet,   basename="performance-bonus")
    router.register(r"geo-rates",            GeoRateViewSet,            basename="geo-rate")
    router.register(r"referral-programs",    ReferralProgramViewSet,    basename="referral-program")
    router.register(r"instant-payouts",      InstantPayoutViewSet,      basename="instant-payout")
    router.register(r"mass-payouts",         MassPayoutJobViewSet,      basename="mass-payout")
    router.register(r"disputes",             DisputeCaseViewSet,        basename="dispute")
    router.register(r"refunds",              RefundRequestViewSet,      basename="refund")
    router.register(r"fraud-scores",         FraudScoreViewSet,         basename="fraud-score")
    router.register(r"aml-flags",            AMLFlagViewSet,            basename="aml-flag")
    router.register(r"offers",               EarningOfferViewSet,       basename="offer")
    router.register(r"whitelist",            WithdrawalWhitelistViewSet,basename="whitelist")
    router.register(r"security-events",      SecurityEventViewSet,      basename="security-event")
    router.register(r"webhook-endpoints",    WebhookEndpointViewSet,    basename="webhook-endpoint")
    router.register(r"tax-records",          TaxRecordViewSet,          basename="tax-record")

urlpatterns = [
    path("", include(router.urls)),
    path("webhook/<str:gateway>/", __import__("api.wallet.api_views", fromlist=["receive_webhook"]).receive_webhook, name="wallet-webhook"),
    path("health/",                __import__("api.wallet.api_views", fromlist=["wallet_health"]).wallet_health,    name="wallet-health"),
]


# ── Smart Link + Click Tracking URLs ─────────────────────────
try:
    from .resources import SmartLinkRouter, ClickTracker, SubIDTracker
    from rest_framework.decorators import api_view, permission_classes
    from rest_framework.permissions import IsAuthenticated, AllowAny
    from rest_framework.response import Response

    @api_view(["GET"])
    @permission_classes([IsAuthenticated])
    def smart_link_view(request):
        """GET /api/wallet/smart-link/?country=BD&device=mobile&sub_id=abc"""
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
        """POST /api/wallet/clicks/ — record affiliate click"""
        from .validators import safe_ip_address
        ip = safe_ip_address(request.META.get("REMOTE_ADDR",""))
        ok = ClickTracker.record_click(
            click_id=request.data.get("click_id",""),
            offer_id=int(request.data.get("offer_id",0)),
            publisher_id=int(request.data.get("pub_id",0)),
            ip_address=ip,
            sub_id=request.data.get("sub_id",""),
            country_code=request.data.get("country",""),
            device_type=request.data.get("device",""),
        )
        return Response({"recorded": ok})

    @api_view(["GET"])
    @permission_classes([IsAuthenticated])
    def sub_id_report_view(request):
        """GET /api/wallet/sub-ids/ — publisher sub-ID performance"""
        report = SubIDTracker.get_report(request.user.id)
        return Response({"success": True, "data": report})

    urlpatterns += [
        path("smart-link/",  smart_link_view,   name="wallet-smart-link"),
        path("clicks/",      record_click_view, name="wallet-click-record"),
        path("sub-ids/",     sub_id_report_view,name="wallet-sub-id-report"),
    ]
except Exception:
    pass
