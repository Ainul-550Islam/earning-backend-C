# viewsets/GatewayHealthViewSet.py
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework.response import Response
from core.views import BaseViewSet
from api.payment_gateways.models.core import PaymentGateway
from api.payment_gateways.models.gateway_config import GatewayHealthLog
from rest_framework import serializers


class GatewayHealthLogSerializer(serializers.ModelSerializer):
    gateway_name = serializers.CharField(source='gateway.name', read_only=True)
    class Meta:
        model  = GatewayHealthLog
        fields = ['id','gateway_name','status','response_time_ms','http_status_code','error','checked_at']


class GatewayHealthViewSet(BaseViewSet):
    """Gateway health monitoring — status dashboard."""
    queryset           = GatewayHealthLog.objects.all().order_by('-checked_at')
    serializer_class   = GatewayHealthLogSerializer
    permission_classes = [IsAdminUser]

    def list(self, request, *args, **kwargs):
        """Latest health status for each gateway."""
        from api.payment_gateways.services.GatewayHealthService import GatewayHealthService
        summary = GatewayHealthService().get_status_summary()
        return self.success_response(data=summary)

    @action(detail=False, methods=['post'], permission_classes=[IsAdminUser])
    def run_check(self, request):
        """Manually trigger health check for all gateways."""
        from api.payment_gateways.services.GatewayHealthService import GatewayHealthService
        results = GatewayHealthService().check_all()
        return self.success_response(data=results, message='Health check completed')

    @action(detail=False, methods=['post'], permission_classes=[IsAdminUser])
    def check_gateway(self, request):
        """Check health of specific gateway."""
        gateway = request.data.get('gateway')
        if not gateway:
            return self.error_response(message='gateway required', status_code=400)
        from api.payment_gateways.services.GatewayHealthService import GatewayHealthService
        result = GatewayHealthService().check_single(gateway)
        return self.success_response(data=result)


class GatewayHealthAPIView(APIView):
    """Public status page — no auth required."""
    permission_classes = [AllowAny]

    def get(self, request):
        from api.payment_gateways.services.GatewayHealthService import GatewayHealthService
        summary = GatewayHealthService().get_status_summary()
        all_ok  = all(v.get('status') == 'healthy' for v in summary.values())
        return Response({
            'status':   'operational' if all_ok else 'degraded',
            'gateways': summary,
        })
