# djoyalty/viewsets/advanced/POSViewSet.py
"""
POS Integration ViewSet -- exposes pos_integration.py POSLoyaltyService।
Previously: full POS checkout flow built, zero API routes।
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import serializers as drf_serializers
from ...permissions import IsLoyaltyAdmin
from ...mixins import DjoyaltyBaseViewSet


class POSIdentifySerializer(drf_serializers.Serializer):
    identifier      = drf_serializers.CharField(max_length=100)
    identifier_type = drf_serializers.ChoiceField(
        choices=['code', 'phone', 'email', 'card_token', 'qr'],
        default='code',
    )


class POSCheckoutSerializer(drf_serializers.Serializer):
    customer_identifier = drf_serializers.CharField()
    identifier_type     = drf_serializers.CharField(default='code')
    order_amount        = drf_serializers.DecimalField(max_digits=14, decimal_places=2)
    txn_id              = drf_serializers.CharField(required=False, allow_blank=True)
    source              = drf_serializers.CharField(default='pos')
    items               = drf_serializers.ListField(
        child=drf_serializers.DictField(), required=False
    )
    redeem_points       = drf_serializers.DecimalField(
        max_digits=14, decimal_places=2, required=False, default=0
    )


class POSViewSet(DjoyaltyBaseViewSet, viewsets.ViewSet):
    """
    POST /pos/identify/     -- look up customer by code/phone/email/card
    POST /pos/checkout/     -- process POS transaction (earn + optional redeem)
    GET  /pos/customer/     -- get customer info for POS display
    GET  /pos/health/       -- POS integration health check
    """
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['post'], url_path='identify')
    def identify(self, request):
        serializer = POSIdentifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            from ...pos_integration import POSLoyaltyService
            result = POSLoyaltyService.identify_customer(
                identifier=data['identifier'],
                identifier_type=data['identifier_type'],
            )
            if not result:
                return Response({'found': False, 'customer': None}, status=200)
            return Response({'found': True, 'customer': result})
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    @action(detail=False, methods=['post'], url_path='checkout')
    def checkout(self, request):
        serializer = POSCheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            from ...pos_integration import POSLoyaltyService, POSCheckoutPayload
            payload = POSCheckoutPayload(
                customer_identifier=data['customer_identifier'],
                order_amount=data['order_amount'],
                txn_id=data.get('txn_id', ''),
                source=data.get('source', 'pos'),
                items=data.get('items', []),
                redeem_points=data.get('redeem_points', 0),
                identifier_type=data.get('identifier_type', 'code'),
            )
            result = POSLoyaltyService.process_checkout(payload=payload)
            return Response(result.to_dict(), status=201)
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    @action(detail=False, methods=['get'], url_path='customer')
    def pos_customer(self, request):
        identifier      = request.query_params.get('identifier', '')
        identifier_type = request.query_params.get('type', 'code')
        if not identifier:
            return self.err('identifier required')
        try:
            from ...pos_integration import POSLoyaltyService
            info = POSLoyaltyService.get_customer_info_for_pos(
                identifier=identifier, identifier_type=identifier_type
            )
            return Response(info if info else {'found': False})
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    @action(detail=False, methods=['get'], url_path='health')
    def health(self, request):
        return Response({'status': 'ok', 'integration': 'pos'})
