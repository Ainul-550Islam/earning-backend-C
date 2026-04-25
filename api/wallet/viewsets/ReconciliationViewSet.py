# api/wallet/viewsets/ReconciliationViewSet.py
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from ..models import LedgerReconciliation
from ..services import ReconciliationService
from ..pagination import WalletPagePagination


class ReconciliationViewSet(viewsets.ModelViewSet):
    """
    GET  /api/wallet/reconciliations/     — list all reconciliation runs
    POST /api/wallet/reconciliations/run/ — admin: run reconciliation now
    POST /api/wallet/reconciliations/{id}/resolve/ — admin: resolve discrepancy
    GET  /api/wallet/reconciliations/unresolved/  — list open discrepancies
    """
    permission_classes = [IsAdminUser]
    pagination_class   = WalletPagePagination
    http_method_names  = ["get", "post", "head", "options"]

    def get_serializer_class(self):
        from rest_framework import serializers
        class S(serializers.ModelSerializer):
            has_discrepancy = serializers.BooleanField(read_only=True)
            class Meta:
                model  = LedgerReconciliation
                fields = ["id","wallet","reconciled_at","period_start","period_end",
                          "expected_balance","actual_balance","discrepancy","status",
                          "notes","resolved_at","has_discrepancy"]
        return S

    def get_queryset(self):
        return LedgerReconciliation.objects.select_related("wallet__user").order_by("-reconciled_at")

    @action(detail=False, methods=["post"])
    def run(self, request):
        """POST /api/wallet/reconciliations/run/ — run full reconciliation."""
        result = ReconciliationService.run_all()
        return Response({"success": True, "data": result})

    @action(detail=True, methods=["post"])
    def resolve(self, request, pk=None):
        notes = request.data.get("notes", "")
        recon = ReconciliationService.resolve(int(pk), notes=notes, resolved_by=request.user)
        return Response({"success": True, "status": recon.status})

    @action(detail=False, methods=["get"])
    def unresolved(self, request):
        qs   = ReconciliationService.get_unresolved()
        data = [{"id": r.id, "wallet": r.wallet.user.username,
                 "discrepancy": float(r.discrepancy), "at": r.reconciled_at} for r in qs]
        return Response({"success": True, "count": len(data), "data": data})
