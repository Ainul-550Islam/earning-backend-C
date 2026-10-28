# djoyalty/viewsets/advanced/PromotionViewSet.py
"""
Promotion Engine ViewSet -- exposes promotion_engine.py PromotionEngine।
Dynamic rule-based bonus points promotion engine।
Previously: full evaluation engine built, zero API routes।
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import serializers as drf_serializers
from ...permissions import IsLoyaltyAdmin
from ...mixins import DjoyaltyBaseViewSet


class PromotionEvaluateSerializer(drf_serializers.Serializer):
    customer_id  = drf_serializers.IntegerField()
    order_amount = drf_serializers.DecimalField(max_digits=14, decimal_places=2)
    base_points  = drf_serializers.DecimalField(max_digits=14, decimal_places=2, default=0)
    items        = drf_serializers.ListField(child=drf_serializers.DictField(), required=False)
    channel      = drf_serializers.CharField(default='web', required=False)
    metadata     = drf_serializers.DictField(required=False, default=dict)


class PromotionViewSet(DjoyaltyBaseViewSet, viewsets.ViewSet):
    """
    POST /promotions/evaluate/       -- evaluate promotions for a transaction
    GET  /promotions/active-rules/   -- list all active promotion rules
    GET  /promotions/preview/        -- preview points before checkout
    """
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['post'], url_path='evaluate')
    def evaluate(self, request):
        serializer = PromotionEvaluateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        from ...models.core import Customer
        customer = Customer.objects.filter(pk=data['customer_id']).first()
        if not customer:
            return self.not_found('Customer not found')
        try:
            from ...promotion_engine import PromotionEngine
            from decimal import Decimal
            context = PromotionEngine.build_context(
                customer=customer,
                order_amount=data['order_amount'],
                items=data.get('items', []),
                channel=data.get('channel', 'web'),
                metadata=data.get('metadata', {}),
            )
            result = PromotionEngine.evaluate(
                customer=customer,
                order_amount=data['order_amount'],
                base_points=data.get('base_points', Decimal('0')),
                items=data.get('items', []),
            )
            return Response({'evaluation': result})
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    @action(detail=False, methods=['get'], url_path='active-rules',
            permission_classes=[IsLoyaltyAdmin])
    def active_rules(self, request):
        try:
            from ...promotion_engine import PromotionEngine
            rules = PromotionEngine.get_active_rules()
            return Response({
                'count': len(rules),
                'rules': [{'name': r.name, 'priority': r.priority} for r in rules],
            })
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    @action(detail=False, methods=['get'], url_path='preview')
    def preview(self, request):
        customer_id  = request.query_params.get('customer_id')
        order_amount = request.query_params.get('order_amount', '0')
        if not customer_id:
            return self.err('customer_id required')
        from ...models.core import Customer
        from decimal import Decimal
        customer = Customer.objects.filter(pk=customer_id).first()
        if not customer:
            return self.not_found('Customer not found')
        try:
            from ...promotion_engine import PromotionEngine
            result = PromotionEngine.evaluate(
                customer=customer,
                order_amount=Decimal(order_amount),
                base_points=Decimal('0'),
            )
            return Response({'preview': result})
        except Exception as e:
            return Response({'error': str(e)}, status=500)
