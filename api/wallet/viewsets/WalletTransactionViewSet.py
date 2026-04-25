# api/wallet/viewsets/WalletTransactionViewSet.py
import logging
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response

from ..models import WalletTransaction
from ..filters import WalletTransactionFilter
from ..pagination import TransactionCursorPagination
from ..permissions import IsWalletOwnerOrAdmin

logger = logging.getLogger("wallet.viewset.transaction")


class WalletTransactionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    /api/wallet/transactions/
    GET  /transactions/          — list (cursor paginated, most recent first)
    GET  /transactions/{id}/     — retrieve
    POST /transactions/{id}/approve/  — admin
    POST /transactions/{id}/reject/   — admin
    POST /transactions/{id}/reverse/  — admin
    GET  /transactions/stats/    — aggregated stats
    """
    filterset_class  = WalletTransactionFilter
    pagination_class = TransactionCursorPagination

    def get_serializer_class(self):
        from ..serializers.WalletTransactionSerializer import WalletTransactionSerializer
        return WalletTransactionSerializer

    def get_permissions(self):
        if self.action in ("approve", "reject", "reverse"):
            return [IsAdminUser()]
        return [IsAuthenticated()]

    def get_queryset(self):
        u = self.request.user
        qs = WalletTransaction.objects.select_related(
            "wallet", "wallet__user", "created_by", "approved_by"
        )
        if u.is_staff:
            return qs
        return qs.filter(wallet__user=u)

    @action(detail=True, methods=["post"], permission_classes=[IsAdminUser])
    def approve(self, request, pk=None):
        txn = self.get_object()
        try:
            txn.approve(approved_by=request.user)
            return Response({"success": True, "txn_id": str(txn.txn_id), "status": txn.status})
        except ValueError as e:
            return Response({"success": False, "error": str(e)}, status=400)

    @action(detail=True, methods=["post"], permission_classes=[IsAdminUser])
    def reject(self, request, pk=None):
        txn = self.get_object()
        try:
            reason = request.data.get("reason", "Admin reject")
            txn.reject(reason=reason)
            return Response({"success": True, "txn_id": str(txn.txn_id), "status": txn.status})
        except ValueError as e:
            return Response({"success": False, "error": str(e)}, status=400)

    @action(detail=True, methods=["post"], permission_classes=[IsAdminUser])
    def reverse(self, request, pk=None):
        txn = self.get_object()
        try:
            reason   = request.data.get("reason", "Admin reversal")
            reversal = txn.reverse(reason=reason, reversed_by=request.user)
            return Response({"success": True, "reversal_txn_id": str(reversal.txn_id)})
        except ValueError as e:
            return Response({"success": False, "error": str(e)}, status=400)

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def stats(self, request):
        """GET /api/wallet/transactions/stats/ — earning breakdown."""
        try:
            from ..services import EarningService
            from ..models import Wallet
            wallet = Wallet.objects.get(user=request.user)
            days   = int(request.query_params.get("days", 30))
            data   = EarningService.get_breakdown(wallet, days=days)
            return Response({"success": True, "data": data})
        except Exception as e:
            return Response({"success": False, "error": str(e)}, status=400)
