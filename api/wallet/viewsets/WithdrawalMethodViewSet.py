# api/wallet/viewsets/WithdrawalMethodViewSet.py
import logging
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from django.utils import timezone

from ..models import WithdrawalMethod
from ..filters import WithdrawalFilter
from ..pagination import WalletPagePagination

logger = logging.getLogger("wallet.viewset.payment_method")


class WithdrawalMethodViewSet(viewsets.ModelViewSet):
    """
    /api/wallet/withdrawal-methods/
    POST /withdrawal-methods/                  — add method
    GET  /withdrawal-methods/                  — list own methods
    POST /withdrawal-methods/{id}/set_default/ — set as default
    POST /withdrawal-methods/{id}/verify/      — admin verify
    POST /withdrawal-methods/{id}/unverify/    — admin unverify
    DELETE /withdrawal-methods/{id}/           — remove
    """
    filterset_class  = WithdrawalFilter
    pagination_class = WalletPagePagination

    def get_serializer_class(self):
        from ..serializers.WithdrawalMethodSerializer import WithdrawalMethodSerializer
        return WithdrawalMethodSerializer

    def get_permissions(self):
        if self.action in ("verify", "unverify"):
            return [IsAdminUser()]
        return [IsAuthenticated()]

    def get_queryset(self):
        u = self.request.user
        if u.is_staff:
            return WithdrawalMethod.objects.select_related("user").all()
        return WithdrawalMethod.objects.filter(user=u)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def set_default(self, request, pk=None):
        pm = self.get_object()
        if pm.user != request.user and not request.user.is_staff:
            return Response({"success": False, "error": "Permission denied"}, status=403)
        pm.set_default()
        return Response({"success": True, "id": pm.id, "is_default": True})

    @action(detail=True, methods=["post"], permission_classes=[IsAdminUser])
    def verify(self, request, pk=None):
        pm = self.get_object()
        pm.verify(verified_by=request.user)
        return Response({"success": True, "id": pm.id, "is_verified": True, "verified_at": pm.verified_at})

    @action(detail=True, methods=["post"], permission_classes=[IsAdminUser])
    def unverify(self, request, pk=None):
        pm = self.get_object()
        pm.is_verified = False
        pm.verified_at = None
        pm.save(update_fields=["is_verified","verified_at","updated_at"])
        return Response({"success": True, "id": pm.id, "is_verified": False})
