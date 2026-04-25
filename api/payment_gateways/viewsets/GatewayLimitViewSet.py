# viewsets/GatewayLimitViewSet.py
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from core.views import BaseViewSet
from api.payment_gateways.models.gateway_config import GatewayLimit, GatewayFeeRule
from rest_framework import serializers


class GatewayLimitSerializer(serializers.ModelSerializer):
    gateway_name = serializers.CharField(source='gateway.name', read_only=True)
    class Meta:
        model  = GatewayLimit
        fields = ['id','gateway_name','transaction_type','min_amount','max_amount',
                  'daily_limit','monthly_limit','per_txn_count_daily','currency','is_active']

class GatewayFeeRuleSerializer(serializers.ModelSerializer):
    gateway_name = serializers.CharField(source='gateway.name', read_only=True)
    class Meta:
        model  = GatewayFeeRule
        fields = ['id','gateway_name','transaction_type','fee_type','fee_value',
                  'fixed_component','min_fee','max_fee','currency','is_active','tiers']


class GatewayLimitViewSet(BaseViewSet):
    queryset           = GatewayLimit.objects.all().order_by('gateway__name')
    serializer_class   = GatewayLimitSerializer
    permission_classes = [IsAdminUser]


class GatewayFeeRuleViewSet(BaseViewSet):
    queryset           = GatewayFeeRule.objects.all().order_by('gateway__name')
    serializer_class   = GatewayFeeRuleSerializer
    permission_classes = [IsAdminUser]

    def get_fee_for_amount(self, request):
        """Calculate fee for a given amount and gateway."""
        from decimal import Decimal
        gateway_id = request.data.get('gateway_id')
        amount     = Decimal(str(request.data.get('amount', '0')))
        try:
            rule = GatewayFeeRule.objects.get(id=gateway_id, is_active=True)
            fee  = rule.calculate(amount)
            return self.success_response(data={'fee': str(fee), 'net': str(amount - fee)})
        except Exception as e:
            return self.error_response(message=str(e), status_code=400)
