# api/wallet/viewsets/WithdrawalBatchViewSet.py
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from ..models import WithdrawalBatch
from ..services import WithdrawalBatchService
from ..pagination import WalletPagePagination


class WithdrawalBatchViewSet(viewsets.ModelViewSet):
    """
    GET  /api/wallet/withdrawal-batches/           — list batches
    POST /api/wallet/withdrawal-batches/create_batch/ — create batch
    POST /api/wallet/withdrawal-batches/{id}/process/ — process batch
    """
    permission_classes = [IsAdminUser]
    pagination_class   = WalletPagePagination
    http_method_names  = ["get", "post", "head", "options"]

    def get_serializer_class(self):
        from rest_framework import serializers
        class S(serializers.ModelSerializer):
            class Meta:
                model  = WithdrawalBatch
                fields = ["id","batch_id","gateway","status","total_amount","total_count",
                          "processed_count","failed_count","gateway_batch_id","created_at",
                          "started_at","completed_at","notes"]
        return S

    def get_queryset(self):
        return WithdrawalBatch.objects.select_related("created_by").order_by("-created_at")

    @action(detail=False, methods=["post"])
    def create_batch(self, request):
        gateway = request.data.get("gateway", "bkash")
        ids     = request.data.get("withdrawal_ids", [])
        notes   = request.data.get("notes", "")
        try:
            batch = WithdrawalBatchService.create_batch(gateway, ids, request.user, notes)
            return Response({"success": True, "batch_id": str(batch.batch_id),
                             "count": batch.total_count, "total": float(batch.total_amount)}, status=201)
        except Exception as e:
            return Response({"success": False, "error": str(e)}, status=400)

    @action(detail=True, methods=["post"])
    def process(self, request, pk=None):
        batch     = self.get_object()
        gw_resp   = request.data.get("gateway_response", {})
        try:
            result = WithdrawalBatchService.process_batch(batch, gw_resp)
            return Response({"success": True, "data": result})
        except Exception as e:
            return Response({"success": False, "error": str(e)}, status=400)
