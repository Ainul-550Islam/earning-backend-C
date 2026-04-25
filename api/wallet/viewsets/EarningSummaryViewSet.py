# api/wallet/viewsets/EarningSummaryViewSet.py
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from ..models import EarningSummary
from ..filters import EarningSummaryFilter
from ..pagination import WalletPagePagination


class EarningSummaryViewSet(viewsets.ReadOnlyModelViewSet):
    """GET /api/wallet/earning-summaries/ — pre-computed period summaries."""
    filterset_class  = EarningSummaryFilter
    pagination_class = WalletPagePagination

    def get_serializer_class(self):
        from ..serializers.EarningSummarySerializer import EarningSummarySerializer
        return EarningSummarySerializer

    def get_queryset(self):
        u = self.request.user
        qs = EarningSummary.objects.select_related("wallet__user")
        if u.is_staff:
            return qs
        return qs.filter(wallet__user=u)
