# viewsets/PaymentAnalyticsViewSet.py
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from core.views import BaseViewSet
from api.payment_gateways.models.reconciliation import PaymentAnalytics
from rest_framework import serializers


class PaymentAnalyticsSerializer(serializers.ModelSerializer):
    gateway_name     = serializers.CharField(source='gateway.name', read_only=True)
    success_rate_pct = serializers.SerializerMethodField()

    class Meta:
        model  = PaymentAnalytics
        fields = ['date','gateway_name','transaction_type','currency',
                  'success_count','failed_count','total_count',
                  'total_amount','total_fees','avg_amount',
                  'success_rate_pct','failure_rate']

    def get_success_rate_pct(self, obj):
        return round(float(obj.success_rate) * 100, 1)


class PaymentAnalyticsViewSet(BaseViewSet):
    """Payment analytics per gateway per day."""
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

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def my_earnings(self, request):
        """Current user's earnings summary (for publishers)."""
        from django.db.models import Sum
        from tracking.models import Conversion
        from django.utils import timezone
        from datetime import timedelta

        days  = int(request.GET.get('days', 30))
        since = timezone.now() - timedelta(days=days)

        agg = Conversion.objects.filter(
            publisher=request.user,
            status='approved',
            created_at__gte=since,
        ).aggregate(
            total_revenue=Sum('payout'),
            total_conversions=Sum('revenue') - Sum('revenue') + Sum('id') * 0,
        )
        count = Conversion.objects.filter(
            publisher=request.user, status='approved', created_at__gte=since
        ).count()

        return self.success_response(data={
            'days':          days,
            'total_revenue': float(agg['total_revenue'] or 0),
            'conversions':   count,
        })

    @action(detail=False, methods=['post'], permission_classes=[IsAdminUser])
    def trigger_aggregation(self, request):
        """Manually trigger analytics aggregation."""
        from api.payment_gateways.services.GatewayAnalyticsService import GatewayAnalyticsService
        result = GatewayAnalyticsService().aggregate_daily()
        return self.success_response(data={'updated': len(result)}, message='Aggregated.')
