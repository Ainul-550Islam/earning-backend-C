# api/wallet/viewsets/EarningRecordViewSet.py
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from ..models import EarningRecord, Wallet
from ..filters import EarningRecordFilter
from ..pagination import WalletPagePagination


class EarningRecordViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET /api/wallet/earning-records/ — earning history
    GET /api/wallet/earning-records/breakdown/ — breakdown by source
    """
    filterset_class  = EarningRecordFilter
    pagination_class = WalletPagePagination

    def get_serializer_class(self):
        from ..serializers.EarningRecordSerializer import EarningRecordSerializer
        return EarningRecordSerializer

    def get_queryset(self):
        u = self.request.user
        qs = EarningRecord.objects.select_related("wallet__user", "source")
        if u.is_staff:
            return qs
        return qs.filter(wallet__user=u)

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def breakdown(self, request):
        """GET /api/wallet/earning-records/breakdown/?days=30"""
        try:
            from ..services import EarningService
            wallet = Wallet.objects.get(user=request.user)
            days   = int(request.query_params.get("days", 30))
            data   = EarningService.get_breakdown(wallet, days=days)
            return Response({"success": True, "data": data})
        except Exception as e:
            return Response({"success": False, "error": str(e)}, status=400)
