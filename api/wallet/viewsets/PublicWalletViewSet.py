# api/wallet/viewsets/PublicWalletViewSet.py
"""
Public wallet endpoints — no authentication required.
Used by mobile apps to check minimum withdrawal amounts, gateway info, etc.
"""
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from ..models import WithdrawalLimit, WithdrawalFee
from ..choices import GatewayType
from ..constants import MIN_WITHDRAWAL, MAX_WITHDRAWAL, GATEWAY_MIN


class PublicWalletViewSet(viewsets.ViewSet):
    """
    /api/wallet/public/
    GET /public/gateway_info/     — available gateways + min amounts
    GET /public/withdrawal_limits/ — min/max withdrawal amounts by gateway
    GET /public/fee_table/        — fee schedule by gateway + tier
    """
    permission_classes = [AllowAny]

    @action(detail=False, methods=["get"])
    def gateway_info(self, request):
        """Public: list all available payment gateways and minimum amounts."""
        gateways = []
        for choice in GatewayType.choices:
            code, label = choice
            gateways.append({
                "code":       code,
                "label":      label,
                "min_amount": float(GATEWAY_MIN.get(code, MIN_WITHDRAWAL)),
            })
        return Response({"success": True, "gateways": gateways})

    @action(detail=False, methods=["get"])
    def withdrawal_limits(self, request):
        """Public: withdrawal limit info."""
        return Response({
            "success": True,
            "data": {
                "global_min": float(MIN_WITHDRAWAL),
                "global_max": float(MAX_WITHDRAWAL),
                "gateway_mins": {k: float(v) for k, v in GATEWAY_MIN.items()},
            }
        })

    @action(detail=False, methods=["get"])
    def fee_table(self, request):
        """Public: fee table by gateway."""
        fees = []
        for fee in WithdrawalFee.objects.filter(is_active=True).order_by("gateway","tier"):
            fees.append({
                "gateway":     fee.gateway,
                "tier":        fee.tier,
                "fee_type":    fee.fee_type,
                "fee_percent": float(fee.fee_percent),
                "flat_fee":    float(fee.flat_fee),
                "min_fee":     float(fee.min_fee),
                "max_fee":     float(fee.max_fee) if fee.max_fee else None,
            })
        return Response({"success": True, "fees": fees})

    @action(detail=False, methods=["post"])
    def receive_webhook(self, request, gateway: str = ""):
        """POST /api/wallet/public/receive_webhook/{gateway}/ — gateway callback."""
        from django.utils import timezone
        try:
            from ..models import WalletWebhookLog
            gateway_param = request.query_params.get("gateway", gateway or "unknown")
            log = WalletWebhookLog.objects.create(
                webhook_type=gateway_param,
                event_type=request.data.get("event_type", "unknown"),
                payload=request.data if isinstance(request.data, dict) else {},
                headers=dict(request.headers),
                ip_address=getattr(request, "safe_ip", request.META.get("REMOTE_ADDR")),
            )
            # Async process
            try:
                from ..tasks import process_webhook
                process_webhook.delay(log.id)
            except Exception:
                pass
            return Response({"received": True, "log_id": log.id})
        except Exception as e:
            return Response({"received": False, "error": str(e)}, status=500)
