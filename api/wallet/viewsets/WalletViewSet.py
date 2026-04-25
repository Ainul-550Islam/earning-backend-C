# api/wallet/viewsets/WalletViewSet.py
import logging
from decimal import Decimal
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from django.db import transaction

from ..models import Wallet, WalletTransaction
from ..services import WalletService, BalanceService
from ..permissions import IsWalletOwnerOrAdmin, WalletNotLocked
from ..filters import WalletFilter
from ..pagination import WalletPagePagination
from ..exceptions import WalletLockedError, InsufficientBalanceError, InvalidAmountError

logger = logging.getLogger("wallet.viewset.wallet")


class WalletViewSet(viewsets.ModelViewSet):
    """
    /api/wallet/wallets/
    GET    /wallets/             — admin: list all wallets
    GET    /wallets/me/          — current user's wallet
    GET    /wallets/summary/     — full balance summary
    POST   /wallets/transfer/    — wallet-to-wallet transfer
    POST   /wallets/{id}/lock/   — admin: lock wallet
    POST   /wallets/{id}/unlock/ — admin: unlock wallet
    POST   /wallets/{id}/freeze_balance/   — admin: freeze amount
    POST   /wallets/{id}/unfreeze_balance/ — admin: unfreeze amount
    POST   /wallets/{id}/admin_credit/     — admin: credit
    POST   /wallets/{id}/admin_debit/      — admin: debit
    POST   /wallets/bulk_lock/             — admin: bulk lock
    POST   /wallets/bulk_unlock/           — admin: bulk unlock
    POST   /wallets/generate_report/       — admin: generate daily report
    """
    queryset         = Wallet.objects.select_related("user").all()
    filterset_class  = WalletFilter
    pagination_class = WalletPagePagination
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_serializer_class(self):
        from ..serializers.WalletSerializer import WalletSerializer
        return WalletSerializer

    def get_permissions(self):
        if self.action in ("list", "retrieve", "lock", "unlock",
                           "freeze_balance", "unfreeze_balance",
                           "admin_credit", "admin_debit",
                           "bulk_lock", "bulk_unlock", "generate_report"):
            return [IsAdminUser()]
        return [IsAuthenticated()]

    def get_queryset(self):
        u = self.request.user
        if u.is_staff:
            return Wallet.objects.select_related("user").all()
        return Wallet.objects.filter(user=u)

    # ── User-facing endpoints ─────────────────────────────────────────

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def me(self, request):
        """GET /api/wallet/wallets/me/ — current user wallet."""
        try:
            wallet = WalletService.get_or_create(request.user)
            from ..serializers.WalletSerializer import WalletSerializer
            return Response({"success": True, "data": WalletSerializer(wallet).data})
        except Exception as e:
            return Response({"success": False, "error": str(e)}, status=400)

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def summary(self, request):
        """GET /api/wallet/wallets/summary/ — full balance summary."""
        data = WalletService.get_summary(request.user)
        if not data:
            return Response({"success": False, "error": "Wallet not found"}, status=404)
        return Response({"success": True, "data": data})

    @action(detail=False, methods=["post"],
            permission_classes=[IsAuthenticated, WalletNotLocked])
    def transfer(self, request):
        """POST /api/wallet/wallets/transfer/ — send money to another user."""
        try:
            recipient = request.data.get("recipient")
            amount    = Decimal(str(request.data.get("amount", 0)))
            note      = request.data.get("note", "")
            if not recipient:
                return Response({"success": False, "error": "recipient required"}, status=400)
            result = WalletService.transfer(request.user, recipient, amount, note=note)
            return Response({"success": True, "data": result})
        except (WalletLockedError, InsufficientBalanceError, InvalidAmountError) as e:
            return Response({"success": False, "error": str(e)}, status=400)
        except ValueError as e:
            return Response({"success": False, "error": str(e)}, status=404)
        except Exception as e:
            logger.error(f"transfer error: {e}", exc_info=True)
            return Response({"success": False, "error": "Transfer failed"}, status=500)

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def balance_breakdown(self, request):
        """GET /api/wallet/wallets/balance_breakdown/ — all 5 balance types."""
        try:
            wallet = Wallet.objects.get(user=request.user)
            return Response({"success": True, "data": BalanceService.get_balance_breakdown(wallet)})
        except Wallet.DoesNotExist:
            return Response({"success": False, "error": "Wallet not found"}, status=404)

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def cap_status(self, request):
        """GET /api/wallet/wallets/cap_status/ — today's earning cap status."""
        try:
            from ..services import EarningCapService
            wallet = Wallet.objects.get(user=request.user)
            data = EarningCapService.get_cap_status(wallet)
            return Response({"success": True, "data": data})
        except Exception as e:
            return Response({"success": False, "error": str(e)}, status=400)

    # ── Admin endpoints ───────────────────────────────────────────────

    @action(detail=True, methods=["post"], permission_classes=[IsAdminUser])
    def lock(self, request, pk=None):
        """POST /api/wallet/wallets/{id}/lock/"""
        wallet = self.get_object()
        reason = request.data.get("reason", "Admin lock")
        wallet.lock(reason, locked_by=request.user)
        return Response({"success": True, "wallet_id": wallet.id, "reason": reason})

    @action(detail=True, methods=["post"], permission_classes=[IsAdminUser])
    def unlock(self, request, pk=None):
        """POST /api/wallet/wallets/{id}/unlock/"""
        wallet = self.get_object()
        wallet.unlock()
        return Response({"success": True, "wallet_id": wallet.id})

    @action(detail=True, methods=["post"], permission_classes=[IsAdminUser])
    def freeze_balance(self, request, pk=None):
        """POST /api/wallet/wallets/{id}/freeze_balance/"""
        wallet = self.get_object()
        try:
            amount = Decimal(str(request.data.get("amount", 0)))
            reason = request.data.get("reason", "Admin freeze")
            wallet.freeze(amount, reason)
            return Response({"success": True, "frozen": float(amount), "reason": reason})
        except ValueError as e:
            return Response({"success": False, "error": str(e)}, status=400)

    @action(detail=True, methods=["post"], permission_classes=[IsAdminUser])
    def unfreeze_balance(self, request, pk=None):
        """POST /api/wallet/wallets/{id}/unfreeze_balance/"""
        wallet = self.get_object()
        try:
            amount = Decimal(str(request.data.get("amount", 0)))
            reason = request.data.get("reason", "Admin unfreeze")
            wallet.unfreeze(amount, reason)
            return Response({"success": True, "unfrozen": float(amount)})
        except ValueError as e:
            return Response({"success": False, "error": str(e)}, status=400)

    @action(detail=True, methods=["post"], permission_classes=[IsAdminUser])
    def admin_credit(self, request, pk=None):
        """POST /api/wallet/wallets/{id}/admin_credit/"""
        wallet = self.get_object()
        try:
            amount = Decimal(str(request.data.get("amount", 0)))
            desc   = request.data.get("description", "Admin credit")
            txn    = WalletService.admin_credit(wallet, amount, desc, request.user)
            return Response({"success": True, "txn_id": str(txn.txn_id), "amount": float(amount)})
        except Exception as e:
            return Response({"success": False, "error": str(e)}, status=400)

    @action(detail=True, methods=["post"], permission_classes=[IsAdminUser])
    def admin_debit(self, request, pk=None):
        """POST /api/wallet/wallets/{id}/admin_debit/"""
        wallet = self.get_object()
        try:
            amount = Decimal(str(request.data.get("amount", 0)))
            desc   = request.data.get("description", "Admin debit")
            txn    = WalletService.admin_debit(wallet, amount, desc, request.user)
            return Response({"success": True, "txn_id": str(txn.txn_id), "amount": float(amount)})
        except Exception as e:
            return Response({"success": False, "error": str(e)}, status=400)

    @action(detail=False, methods=["post"], permission_classes=[IsAdminUser])
    def bulk_lock(self, request):
        """POST /api/wallet/wallets/bulk_lock/ — lock multiple wallets."""
        ids    = request.data.get("wallet_ids", [])
        reason = request.data.get("reason", "Bulk admin lock")
        count  = 0
        for wid in ids:
            try:
                w = Wallet.objects.get(id=wid)
                w.lock(reason, locked_by=request.user)
                count += 1
            except Wallet.DoesNotExist:
                pass
        return Response({"success": True, "locked": count})

    @action(detail=False, methods=["post"], permission_classes=[IsAdminUser])
    def bulk_unlock(self, request):
        """POST /api/wallet/wallets/bulk_unlock/"""
        ids = request.data.get("wallet_ids", [])
        count = 0
        for wid in ids:
            try:
                w = Wallet.objects.get(id=wid)
                w.unlock()
                count += 1
            except Wallet.DoesNotExist:
                pass
        return Response({"success": True, "unlocked": count})

    @action(detail=False, methods=["post"], permission_classes=[IsAdminUser])
    def generate_report(self, request):
        """POST /api/wallet/wallets/generate_report/ — generate today's daily report."""
        try:
            from ..services import WalletAnalyticsService
            from datetime import date
            d = date.today()
            liability = WalletAnalyticsService.compute_liability(d)
            return Response({
                "success": True,
                "date": str(d),
                "total_liability": float(liability.total_liability),
                "total_wallets": liability.total_wallets,
            })
        except Exception as e:
            return Response({"success": False, "error": str(e)}, status=500)
