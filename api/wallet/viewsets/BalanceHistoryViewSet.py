# api/wallet/viewsets/BalanceHistoryViewSet.py
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from ..models import BalanceHistory
from ..filters import BalanceHistoryFilter
from ..pagination import WalletPagePagination


class BalanceHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    """GET /api/wallet/balance-history/ — read-only balance change log."""
    filterset_class  = BalanceHistoryFilter
    pagination_class = WalletPagePagination

    def get_serializer_class(self):
        from ..serializers.BalanceHistorySerializer import BalanceHistorySerializer
        return BalanceHistorySerializer

    def get_queryset(self):
        u = self.request.user
        qs = BalanceHistory.objects.select_related("wallet__user")
        if u.is_staff:
            return qs
        return qs.filter(wallet__user=u)
