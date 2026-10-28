# djoyalty/viewsets/advanced/CardLinkingViewSet.py
"""
Card Linking ViewSet -- exposes card_linking.py CardLinkingService,
LinkedCard model। Previously: full auto-earn on card swipe built, zero API।
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import serializers as drf_serializers
from ...permissions import IsLoyaltyAdmin
from ...mixins import DjoyaltyBaseViewSet


class CardLinkSerializer(drf_serializers.Serializer):
    card_token   = drf_serializers.CharField(max_length=200)
    card_scheme  = drf_serializers.ChoiceField(
        choices=['visa', 'mastercard', 'amex', 'local'], default='visa'
    )
    card_last4   = drf_serializers.CharField(max_length=4, required=False, allow_blank=True)
    card_brand   = drf_serializers.CharField(max_length=50, required=False, allow_blank=True)


class CardTransactionWebhookSerializer(drf_serializers.Serializer):
    transaction_id = drf_serializers.CharField()
    card_token     = drf_serializers.CharField()
    amount         = drf_serializers.DecimalField(max_digits=14, decimal_places=2)
    currency       = drf_serializers.CharField(default='BDT')
    merchant_name  = drf_serializers.CharField(required=False, allow_blank=True)
    merchant_mcc   = drf_serializers.CharField(required=False, allow_blank=True)


class CardLinkingViewSet(DjoyaltyBaseViewSet, viewsets.ViewSet):
    """
    GET  /card-linking/my-cards/         -- list linked cards
    POST /card-linking/link/             -- link a new card
    DELETE /card-linking/unlink/         -- unlink a card
    POST /card-linking/transaction/      -- process card transaction webhook
    GET  /card-linking/admin/all/        -- all linked cards (admin)
    """
    permission_classes = [IsAuthenticated]

    def _get_customer(self, request):
        c = getattr(request, 'loyalty_customer', None)
        if c:
            return c
        cid = request.query_params.get('customer_id') or request.data.get('customer_id')
        if cid:
            from ...models.core import Customer
            return Customer.objects.filter(pk=cid).first()
        return None

    @action(detail=False, methods=['get'], url_path='my-cards')
    def my_cards(self, request):
        customer = self._get_customer(request)
        if not customer:
            return Response({'cards': []})
        try:
            from ...card_linking import CardLinkingService
            cards = CardLinkingService.get_customer_cards(customer)
            return Response({'cards': cards})
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    @action(detail=False, methods=['post'], url_path='link')
    def link_card(self, request):
        customer = self._get_customer(request)
        if not customer:
            return self.not_found('Customer not found')
        serializer = CardLinkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            from ...card_linking import CardLinkingService
            card = CardLinkingService.link_card(
                customer=customer,
                card_token=data['card_token'],
                card_scheme=data.get('card_scheme', 'visa'),
                card_last4=data.get('card_last4', ''),
                card_brand=data.get('card_brand', ''),
            )
            return Response({
                'status':   'linked',
                'card_id':  card.id,
                'masked':   card.masked_number(),
                'scheme':   card.card_scheme,
            }, status=201)
        except Exception as e:
            return self.err(str(e))

    @action(detail=False, methods=['delete'], url_path='unlink')
    def unlink_card(self, request):
        customer   = self._get_customer(request)
        card_token = request.data.get('card_token', '')
        if not card_token:
            return self.err('card_token required')
        try:
            from ...card_linking import CardLinkingService
            success = CardLinkingService.unlink_card(card_token=card_token, customer=customer)
            return Response({'status': 'unlinked' if success else 'not_found'})
        except Exception as e:
            return self.err(str(e))

    @action(detail=False, methods=['post'], url_path='transaction')
    def process_transaction(self, request):
        """Webhook from card network -- auto-earn points on card swipe."""
        serializer = CardTransactionWebhookSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            from ...card_linking import CardLinkingService
            result = CardLinkingService.process_transaction(
                transaction_id=data['transaction_id'],
                card_token=data['card_token'],
                amount=data['amount'],
                currency=data.get('currency', 'BDT'),
                merchant_name=data.get('merchant_name', ''),
                merchant_mcc=data.get('merchant_mcc', ''),
            )
            return Response({'processed': True, 'result': result}, status=201)
        except Exception as e:
            return self.err(str(e))

    @action(detail=False, methods=['get'], url_path='admin/all',
            permission_classes=[IsLoyaltyAdmin])
    def admin_all(self, request):
        from ...card_linking import LinkedCard
        qs = LinkedCard.objects.select_related('customer').order_by('-linked_at')[:100]
        data = [{
            'id':           c.id,
            'customer_code': c.customer.code if c.customer else '',
            'masked':       c.masked_number(),
            'scheme':       c.card_scheme,
            'is_active':    c.is_active,
        } for c in qs]
        return Response({'count': len(data), 'cards': data})
