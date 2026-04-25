# api/wallet/viewsets/BalanceBonusViewSet.py
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from ..models import BalanceBonus, Wallet
from ..pagination import WalletPagePagination


class BalanceBonusViewSet(viewsets.ModelViewSet):
    """
    GET  /api/wallet/balance-bonuses/      — list own bonuses
    POST /api/wallet/balance-bonuses/      — admin: grant bonus
    POST /api/wallet/balance-bonuses/{id}/claim/ — claim pending bonus
    POST /api/wallet/balance-bonuses/{id}/revoke/ — admin revoke
    """
    pagination_class = WalletPagePagination

    def get_serializer_class(self):
        from ..serializers.BalanceBonusSerializer import BalanceBonusSerializer
        return BalanceBonusSerializer

    def get_permissions(self):
        if self.action in ("create", "revoke"):
            return [IsAdminUser()]
        return [IsAuthenticated()]

    def get_queryset(self):
        u = self.request.user
        qs = BalanceBonus.objects.select_related("wallet__user", "granted_by")
        if u.is_staff:
            return qs
        return qs.filter(wallet__user=u)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def claim(self, request, pk=None):
        bonus = self.get_object()
        if bonus.wallet.user != request.user:
            return Response({"success": False, "error": "Permission denied"}, status=403)
        if bonus.status != "pending":
            return Response({"success": False, "error": f"Cannot claim: status='{bonus.status}'"}, status=400)
        try:
            bonus.activate()
            return Response({"success": True, "amount": float(bonus.amount), "status": bonus.status})
        except Exception as e:
            return Response({"success": False, "error": str(e)}, status=400)

    @action(detail=True, methods=["post"], permission_classes=[IsAdminUser])
    def revoke(self, request, pk=None):
        bonus = self.get_object()
        reason = request.data.get("reason", "Admin revoke")
        bonus.revoke(revoked_by=request.user)
        return Response({"success": True, "id": bonus.id, "status": bonus.status})
