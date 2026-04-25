# api/wallet/viewsets/AdminWalletViewSet.py
"""
Admin-only wallet management viewset.
Adjust balances, freeze/unfreeze, block withdrawals, view full history.
"""
import logging
from decimal import Decimal
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from ..models import Wallet, WithdrawalBlock
from ..services import WalletService, ReconciliationService

logger = logging.getLogger("wallet.viewset.admin")


class AdminWalletViewSet(viewsets.ModelViewSet):
    """
    /api/wallet/admin-wallets/
    Full admin control over wallets.
    """
    permission_classes = [IsAdminUser]
    http_method_names  = ["get", "post", "head", "options"]

    def get_serializer_class(self):
        from ..serializers.AdminWalletSerializer import AdminWalletSerializer
        return AdminWalletSerializer

    def get_queryset(self):
        return Wallet.objects.select_related("user").order_by("-created_at")

    @action(detail=True, methods=["post"])
    def adjust_balance(self, request, pk=None):
        """POST — admin adjust any balance field directly (with audit)."""
        wallet    = self.get_object()
        operation = request.data.get("operation")  # "credit" or "debit"
        amount    = Decimal(str(request.data.get("amount", 0)))
        desc      = request.data.get("description", "Admin adjustment")
        try:
            if operation == "credit":
                txn = WalletService.admin_credit(wallet, amount, desc, request.user)
            elif operation == "debit":
                txn = WalletService.admin_debit(wallet, amount, desc, request.user)
            else:
                return Response({"success": False, "error": "operation must be 'credit' or 'debit'"}, status=400)
            return Response({"success": True, "txn_id": str(txn.txn_id),
                             "new_balance": float(wallet.current_balance)})
        except Exception as e:
            return Response({"success": False, "error": str(e)}, status=400)

    @action(detail=True, methods=["post"])
    def block_withdrawals(self, request, pk=None):
        """POST — block user from withdrawing."""
        wallet  = self.get_object()
        reason  = request.data.get("reason", "admin")
        detail  = request.data.get("detail", "")
        hours   = request.data.get("hours")  # None = permanent
        from django.utils import timezone
        from datetime import timedelta
        unblock_at = timezone.now() + timedelta(hours=int(hours)) if hours else None

        block = WithdrawalBlock.objects.create(
            user=wallet.user, wallet=wallet,
            reason=reason, detail=detail,
            blocked_by=request.user, unblock_at=unblock_at,
        )
        return Response({"success": True, "block_id": block.id, "until": str(unblock_at) if unblock_at else "permanent"})

    @action(detail=True, methods=["post"])
    def unblock_withdrawals(self, request, pk=None):
        """POST — release withdrawal block."""
        wallet = self.get_object()
        reason = request.data.get("reason", "Admin unblock")
        count  = 0
        for block in WithdrawalBlock.objects.filter(user=wallet.user, is_active=True):
            block.release(by=request.user, reason=reason)
            count += 1
        return Response({"success": True, "released": count})

    @action(detail=True, methods=["post"])
    def reconcile(self, request, pk=None):
        """POST — run ledger reconciliation for this wallet."""
        wallet = self.get_object()
        result = ReconciliationService.run_one(wallet)
        return Response({"success": True, "data": result})

    @action(detail=True, methods=["get"])
    def full_history(self, request, pk=None):
        """GET — full transaction history for a wallet (admin view)."""
        from ..models import WalletTransaction
        wallet = self.get_object()
        txns   = WalletTransaction.objects.filter(wallet=wallet).order_by("-created_at")[:200]
        from ..serializers.WalletTransactionSerializer import WalletTransactionSerializer
        return Response({"success": True, "count": txns.count(),
                         "data": WalletTransactionSerializer(txns, many=True).data})
