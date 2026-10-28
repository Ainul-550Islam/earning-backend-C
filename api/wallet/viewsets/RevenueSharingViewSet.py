# api/wallet/viewsets/RevenueSharingViewSet.py
"""
Revenue Sharing API — Advertiser & Publisher earnings endpoints.

Advertiser endpoints:
  GET  /api/wallet/advertiser/account/         → account info + balance
  POST /api/wallet/advertiser/deposit/         → top up balance (post-payment)
  GET  /api/wallet/advertiser/campaigns/       → list campaigns
  POST /api/wallet/advertiser/campaigns/       → create campaign
  GET  /api/wallet/advertiser/invoices/        → list invoices
  GET  /api/wallet/advertiser/invoices/<id>/   → invoice detail

Publisher endpoints:
  GET  /api/wallet/publisher/earnings/summary/ → 30-day summary
  GET  /api/wallet/publisher/earnings/         → RevenueTransaction list
"""
from decimal import Decimal

from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..revenue_sharing import (
    AdvertiserAccount,
    AdvertiserInvoice,
    CampaignBudget,
    RevenueTransaction,
    RevenueSharingService,
)


# ── Serializers ───────────────────────────────────────────────────

class AdvertiserAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model  = AdvertiserAccount
        fields = ["id", "company_name", "balance", "total_deposited",
                  "total_spent", "status", "low_balance_alert", "created_at"]
        read_only_fields = ["id", "balance", "total_deposited", "total_spent",
                             "status", "created_at"]


class CampaignBudgetSerializer(serializers.ModelSerializer):
    remaining_budget = serializers.ReadOnlyField()
    can_convert      = serializers.ReadOnlyField()

    class Meta:
        model  = CampaignBudget
        fields = ["id", "name", "offer_type", "payout_amount", "daily_budget",
                  "total_budget", "spent_today", "spent_total", "conversions",
                  "remaining_budget", "can_convert", "status", "created_at"]
        read_only_fields = ["id", "spent_today", "spent_total", "conversions",
                             "status", "created_at"]


class AdvertiserInvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model  = AdvertiserInvoice
        fields = ["id", "invoice_number", "period_start", "period_end",
                  "total_amount", "conversions", "status", "generated_at", "paid_at"]
        read_only_fields = fields


class RevenueTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model  = RevenueTransaction
        fields = ["id", "transaction_type", "gross_amount", "platform_fee",
                  "publisher_net", "currency", "offer_type", "created_at"]
        read_only_fields = fields


# ── Advertiser Views ──────────────────────────────────────────────

class AdvertiserAccountView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            account = AdvertiserAccount.objects.get(user=request.user)
            return Response(AdvertiserAccountSerializer(account).data)
        except AdvertiserAccount.DoesNotExist:
            return Response({"detail": "No advertiser account found."}, status=404)

    def post(self, request):
        """Create advertiser account."""
        company = request.data.get("company_name", "").strip()
        if not company:
            return Response({"error": "company_name required"}, status=400)
        account, created = AdvertiserAccount.objects.get_or_create(
            user=request.user,
            defaults={"company_name": company},
        )
        return Response(AdvertiserAccountSerializer(account).data,
                        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class AdvertiserDepositView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        POST /advertiser/deposit/
        Body: {amount: "100.00", payment_ref: "TXN-123"}
        Call this after payment gateway confirms the charge.
        """
        try:
            account = AdvertiserAccount.objects.get(user=request.user)
        except AdvertiserAccount.DoesNotExist:
            return Response({"error": "No advertiser account."}, status=404)

        amount_raw = request.data.get("amount")
        payment_ref = request.data.get("payment_ref", "")
        try:
            amount = Decimal(str(amount_raw))
            if amount <= 0:
                raise ValueError
        except Exception:
            return Response({"error": "Invalid amount."}, status=400)

        result = RevenueSharingService.deposit_advertiser_funds(account, amount, payment_ref)
        return Response(result)


class CampaignListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            account = AdvertiserAccount.objects.get(user=request.user)
        except AdvertiserAccount.DoesNotExist:
            return Response({"results": []})
        campaigns = CampaignBudget.objects.filter(advertiser=account).order_by("-created_at")
        return Response({"results": CampaignBudgetSerializer(campaigns, many=True).data})

    def post(self, request):
        try:
            account = AdvertiserAccount.objects.get(user=request.user)
        except AdvertiserAccount.DoesNotExist:
            return Response({"error": "Create an advertiser account first."}, status=400)

        serializer = CampaignBudgetSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        campaign = serializer.save(advertiser=account)
        return Response(CampaignBudgetSerializer(campaign).data, status=201)


class AdvertiserInvoiceListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            account = AdvertiserAccount.objects.get(user=request.user)
        except AdvertiserAccount.DoesNotExist:
            return Response({"results": []})
        invoices = AdvertiserInvoice.objects.filter(advertiser=account)
        return Response({"results": AdvertiserInvoiceSerializer(invoices, many=True).data})


# ── Publisher Views ───────────────────────────────────────────────

class PublisherEarningsSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        days = int(request.query_params.get("days", 30))
        summary = RevenueSharingService.get_publisher_earnings_summary(request.user, days)
        return Response(summary)


class PublisherEarningsListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        limit = min(int(request.query_params.get("limit", 50)), 200)
        txns = RevenueTransaction.objects.filter(
            publisher=request.user,
        ).order_by("-created_at")[:limit]
        return Response({
            "results": RevenueTransactionSerializer(txns, many=True).data,
            "count": len(txns),
        })


# ── URL additions ─────────────────────────────────────────────────
"""
Add to wallet/urls.py:

from .viewsets.RevenueSharingViewSet import (
    AdvertiserAccountView, AdvertiserDepositView, CampaignListView,
    AdvertiserInvoiceListView, PublisherEarningsSummaryView, PublisherEarningsListView,
)

urlpatterns += [
    # Advertiser
    path("advertiser/account/",  AdvertiserAccountView.as_view(),     name="wallet-advertiser-account"),
    path("advertiser/deposit/",  AdvertiserDepositView.as_view(),      name="wallet-advertiser-deposit"),
    path("advertiser/campaigns/", CampaignListView.as_view(),          name="wallet-advertiser-campaigns"),
    path("advertiser/invoices/",  AdvertiserInvoiceListView.as_view(), name="wallet-advertiser-invoices"),
    # Publisher
    path("publisher/earnings/summary/", PublisherEarningsSummaryView.as_view(), name="wallet-publisher-summary"),
    path("publisher/earnings/",         PublisherEarningsListView.as_view(),    name="wallet-publisher-earnings"),
]
"""
