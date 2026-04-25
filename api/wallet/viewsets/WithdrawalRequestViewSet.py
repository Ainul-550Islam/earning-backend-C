# api/wallet/viewsets/WithdrawalRequestViewSet.py
import logging
from decimal import Decimal
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response

from ..models import Wallet, WithdrawalRequest, WithdrawalMethod
from ..services import WithdrawalService, WithdrawalLimitService, WithdrawalFeeService
from ..filters import WithdrawalFilter
from ..pagination import WalletPagePagination
from ..permissions import IsWalletOwnerOrAdmin, WalletNotLocked

logger = logging.getLogger("wallet.viewset.withdrawal")


class WithdrawalRequestViewSet(viewsets.ModelViewSet):
    """
    /api/wallet/withdrawal-requests/
    POST   /withdrawal-requests/            — create
    GET    /withdrawal-requests/            — list own (user) / all (admin)
    GET    /withdrawal-requests/{id}/       — retrieve
    POST   /withdrawal-requests/{id}/cancel/   — user cancel own
    POST   /withdrawal-requests/{id}/approve/  — admin approve
    POST   /withdrawal-requests/{id}/reject/   — admin reject
    POST   /withdrawal-requests/{id}/complete/ — admin mark complete
    GET    /withdrawal-requests/pending_count/ — admin count
    GET    /withdrawal-requests/fee_preview/   — fee estimate before submit
    GET    /withdrawal-requests/limits/        — remaining daily limits
    """
    filterset_class  = WithdrawalFilter
    pagination_class = WalletPagePagination
    http_method_names = ["get", "post", "head", "options"]

    def get_serializer_class(self):
        from ..serializers.WithdrawalRequestSerializer import WithdrawalRequestSerializer
        return WithdrawalRequestSerializer

    def get_permissions(self):
        if self.action in ("approve", "reject", "complete", "pending_count"):
            return [IsAdminUser()]
        return [IsAuthenticated()]

    def get_queryset(self):
        u  = self.request.user
        qs = WithdrawalRequest.objects.select_related(
            "user", "wallet", "payment_method", "transaction", "processed_by"
        )
        if u.is_staff:
            return qs
        return qs.filter(user=u)

    def create(self, request, *args, **kwargs):
        """POST /api/wallet/withdrawal-requests/ — user creates withdrawal."""
        try:
            wallet    = Wallet.objects.get(user=request.user)
            pm_id     = request.data.get("payment_method_id")
            amount    = Decimal(str(request.data.get("amount", 0)))
            note      = request.data.get("note", "")
            idem_key  = request.META.get("HTTP_IDEMPOTENCY_KEY", "")

            pm = WithdrawalMethod.objects.get(id=pm_id, user=request.user)
            wr = WithdrawalService.create(
                wallet=wallet, amount=amount, payment_method=pm,
                created_by=request.user,
                ip_address=getattr(request, "safe_ip", request.META.get("REMOTE_ADDR")),
                idempotency_key=idem_key,
                note=note,
            )
            from ..serializers.WithdrawalRequestSerializer import WithdrawalRequestSerializer
            return Response({"success": True, "data": WithdrawalRequestSerializer(wr).data}, status=201)
        except WithdrawalMethod.DoesNotExist:
            return Response({"success": False, "error": "Payment method not found"}, status=404)
        except Wallet.DoesNotExist:
            return Response({"success": False, "error": "Wallet not found"}, status=404)
        except Exception as e:
            return Response({"success": False, "error": str(e)}, status=400)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def cancel(self, request, pk=None):
        wr = self.get_object()
        if wr.user != request.user and not request.user.is_staff:
            return Response({"success": False, "error": "Permission denied"}, status=403)
        try:
            reason = request.data.get("reason", "User cancelled")
            WithdrawalService.cancel(wr, reason=reason)
            return Response({"success": True, "status": wr.status})
        except ValueError as e:
            return Response({"success": False, "error": str(e)}, status=400)

    @action(detail=True, methods=["post"], permission_classes=[IsAdminUser])
    def approve(self, request, pk=None):
        wr = self.get_object()
        try:
            WithdrawalService.approve(wr, by=request.user)
            return Response({"success": True, "status": wr.status})
        except ValueError as e:
            return Response({"success": False, "error": str(e)}, status=400)

    @action(detail=True, methods=["post"], permission_classes=[IsAdminUser])
    def reject(self, request, pk=None):
        wr = self.get_object()
        try:
            reason = request.data.get("reason", "Admin rejected")
            WithdrawalService.reject(wr, reason=reason, by=request.user)
            return Response({"success": True, "status": wr.status})
        except ValueError as e:
            return Response({"success": False, "error": str(e)}, status=400)

    @action(detail=True, methods=["post"], permission_classes=[IsAdminUser])
    def complete(self, request, pk=None):
        wr  = self.get_object()
        ref = request.data.get("gateway_reference", "")
        try:
            WithdrawalService.complete(wr, gateway_ref=ref)
            return Response({"success": True, "status": wr.status})
        except ValueError as e:
            return Response({"success": False, "error": str(e)}, status=400)

    @action(detail=False, methods=["get"], permission_classes=[IsAdminUser])
    def pending_count(self, request):
        count = WithdrawalRequest.objects.filter(status="pending").count()
        return Response({"success": True, "pending_count": count})

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def fee_preview(self, request):
        """GET ?amount=500&gateway=bkash — estimate fee before submit."""
        try:
            amount  = Decimal(str(request.query_params.get("amount", 0)))
            gateway = request.query_params.get("gateway", "bkash")
            data    = WithdrawalFeeService.get_fee_breakdown(amount, gateway, request.user)
            return Response({"success": True, "data": data})
        except Exception as e:
            return Response({"success": False, "error": str(e)}, status=400)

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def limits(self, request):
        """GET /api/wallet/withdrawal-requests/limits/ — remaining limits."""
        try:
            wallet  = Wallet.objects.get(user=request.user)
            gateway = request.query_params.get("gateway", "ALL")
            data    = WithdrawalLimitService.get_remaining(request.user, wallet, gateway)
            return Response({"success": True, "data": data})
        except Exception as e:
            return Response({"success": False, "error": str(e)}, status=400)
