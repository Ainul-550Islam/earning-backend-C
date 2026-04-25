# viewsets/GatewayFeeRuleViewSet.py
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from core.views import BaseViewSet
from api.payment_gateways.models.gateway_config import GatewayFeeRule
from rest_framework import serializers
from decimal import Decimal


class GatewayFeeRuleSerializer(serializers.ModelSerializer):
    gateway_name = serializers.CharField(source='gateway.name', read_only=True)

    class Meta:
        model  = GatewayFeeRule
        fields = ['id','gateway_name','transaction_type','fee_type','fee_value',
                  'fixed_component','min_fee','max_fee','currency','tiers',
                  'is_active','valid_from','valid_until']


class GatewayFeeRuleViewSet(BaseViewSet):
    """Admin: manage gateway fee rules."""
    queryset           = GatewayFeeRule.objects.all().order_by('gateway__name')
    serializer_class   = GatewayFeeRuleSerializer
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def calculate(self, request):
        """Calculate fee for given gateway + amount."""
        gateway_name = request.data.get('gateway')
        amount_str   = request.data.get('amount', '0')
        txn_type     = request.data.get('transaction_type', 'deposit')

        try:
            amount = Decimal(str(amount_str))
            from api.payment_gateways.models.core import PaymentGateway
            gw   = PaymentGateway.objects.get(name=gateway_name)
            rule = GatewayFeeRule.objects.filter(
                gateway=gw, transaction_type=txn_type, is_active=True
            ).first()

            if rule:
                fee = rule.calculate(amount)
            else:
                fee = (amount * gw.transaction_fee_percentage) / 100

            return self.success_response(data={
                'gateway':    gateway_name,
                'amount':     str(amount),
                'fee':        str(fee),
                'net_amount': str(amount - fee),
                'fee_source': 'rule' if rule else 'gateway_default',
            })
        except Exception as e:
            return self.error_response(message=str(e), status_code=400)
