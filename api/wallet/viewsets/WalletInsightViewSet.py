# api/wallet/viewsets/WalletInsightViewSet.py
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from ..models import WalletInsight
from ..filters import WalletInsightFilter
from ..pagination import WalletPagePagination


class WalletInsightViewSet(viewsets.ReadOnlyModelViewSet):
    """GET /api/wallet/wallet-insights/ — daily wallet analytics."""
    filterset_class  = WalletInsightFilter
    pagination_class = WalletPagePagination

    def get_serializer_class(self):
        from ..serializers.WalletInsightSerializer import WalletInsightSerializer
        return WalletInsightSerializer

    def get_queryset(self):
        u = self.request.user
        qs = WalletInsight.objects.select_related("wallet__user")
        if u.is_staff:
            return qs
        return qs.filter(wallet__user=u)

    @action(detail=False, methods=["post"], permission_classes=[IsAdminUser])
    def compute(self, request):
        """POST /api/wallet/wallet-insights/compute/ — trigger computation."""
        from ..services import WalletAnalyticsService
        from datetime import date, timedelta
        d = date.today() - timedelta(days=1)
        result = WalletAnalyticsService.compute_all_wallet_insights(d)
        return Response({"success": True, "data": result})
