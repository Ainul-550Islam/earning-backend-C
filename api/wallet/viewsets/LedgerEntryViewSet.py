# api/wallet/viewsets/LedgerEntryViewSet.py
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.decorators import action
from rest_framework.response import Response
from ..models import LedgerEntry, WalletLedger
from ..filters import LedgerEntryFilter
from ..pagination import WalletPagePagination


class LedgerEntryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET /api/wallet/ledger-entries/ — read-only double-entry audit log.
    Admins see all. Users see own.
    """
    filterset_class  = LedgerEntryFilter
    pagination_class = WalletPagePagination

    def get_serializer_class(self):
        from ..serializers.LedgerEntrySerializer import LedgerEntrySerializer
        return LedgerEntrySerializer

    def get_permissions(self):
        return [IsAuthenticated()]

    def get_queryset(self):
        u = self.request.user
        qs = LedgerEntry.objects.select_related("ledger__wallet__user")
        if u.is_staff:
            return qs
        return qs.filter(ledger__wallet__user=u)

    @action(detail=False, methods=["get"], permission_classes=[IsAdminUser])
    def unbalanced(self, request):
        """GET /api/wallet/ledger-entries/unbalanced/ — ledgers where is_balanced=False."""
        unbalanced = WalletLedger.objects.filter(is_balanced=False).select_related("wallet__user")[:100]
        data = [{"id": l.id, "ledger_id": str(l.ledger_id),
                 "wallet": l.wallet.user.username, "created_at": l.created_at} for l in unbalanced]
        return Response({"success": True, "count": len(data), "data": data})
