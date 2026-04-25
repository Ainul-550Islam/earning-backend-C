# viewsets/GatewayAnalyticsViewSet.py
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from core.views import BaseViewSet
from api.payment_gateways.models.reconciliation import PaymentAnalytics
from rest_framework import serializers


class PaymentAnalyticsSerializer(serializers.ModelSerializer):
    gateway_name = serializers.CharField(source='gateway.name', read_only=True)
    success_rate_pct = serializers.SerializerMethodField()

    class Meta:
        model  = PaymentAnalytics
        fields = ['date','gateway_name','transaction_type','success_count','failed_count',
                  'total_amount','avg_amount','success_rate_pct']

    def get_success_rate_pct(self, obj):
        return round(float(obj.success_rate) * 100, 1)


class GatewayAnalyticsViewSet(BaseViewSet):
    queryset           = PaymentAnalytics.objects.all().order_by('-date')
    serializer_class   = PaymentAnalyticsSerializer
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """7-day gateway performance summary."""
        from api.payment_gateways.services.GatewayAnalyticsService import GatewayAnalyticsService
        days    = int(request.GET.get('days', 7))
        summary = GatewayAnalyticsService().get_gateway_summary(days)
        return self.success_response(data=summary)

    @action(detail=False, methods=['post'], permission_classes=[IsAdminUser])
    def aggregate_now(self, request):
        """Manually trigger analytics aggregation."""
        from api.payment_gateways.services.GatewayAnalyticsService import GatewayAnalyticsService
        result = GatewayAnalyticsService().aggregate_daily()
        return self.success_response(data={'updated': len(result)}, message='Analytics updated')
