from ...permissions import IsLoyaltyAdmin
# api/djoyalty/viewsets/advanced/OfferWallViewSet.py
"""
OfferWall ViewSet -- CPAlead-style offer wall API।
GET  /offerwall/              -- List active offer walls
GET  /offerwall/{id}/offers/  -- Get offers for customer
POST /offerwall/postback/     -- Receive postback from CPAlead/Tapjoy
POST /offerwall/{id}/complete/ -- Self-report completion (no postback)
GET  /offerwall/{id}/stats/   -- Customer offer stats
"""
import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from ...mixins import DjoyaltyBaseViewSet

logger = logging.getLogger(__name__)


class OfferWallViewSet(DjoyaltyBaseViewSet, viewsets.ReadOnlyModelViewSet):

    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        from ...models.offerwall import OfferWall
        return OfferWall.objects.filter(is_active=True)

    @action(detail=True, methods=['get'])
    def offers(self, request, pk=None):
        """Get available offers for authenticated customer।"""
        from ...models.core import Customer
        from ...services.OfferWallService import OfferWallService
        from ...serializers.OfferWallSerializer import OfferSerializer

        customer_id = request.query_params.get('customer_id')
        if not customer_id:
            return self.err('customer_id required')

        try:
            customer = Customer.objects.get(id=customer_id, is_active=True)
        except Customer.DoesNotExist:
            return self.not_found('Customer not found')

        country = request.query_params.get('country', '')
        device = request.query_params.get('device', 'android')

        offers = OfferWallService.get_available_offers(
            customer=customer,
            offer_wall_id=int(pk),
            country_code=country,
            device_type=device,
        )
        return Response({
            'offer_wall_id': pk,
            'count': len(offers),
            'offers': OfferSerializer(offers, many=True).data,
        })

    @action(detail=False, methods=['post', 'get'], permission_classes=[AllowAny])
    def postback(self, request):
        """
        Receive postback from CPAlead/Tapjoy/Xsolla।
        GET or POST -- CPAlead uses GET by default।

        Expected params: subid, payout, offer_id, transaction_id, ip
        """
        from ...services.OfferWallService import OfferWallService

        data = request.GET.dict() if request.method == 'GET' else request.data
        wall_id = data.get('wall_id') or request.query_params.get('wall_id', 1)
        signature = request.META.get('HTTP_X_DJOYALTY_SIGNATURE', '')
        ip = request.META.get('REMOTE_ADDR', '')

        try:
            result = OfferWallService.process_postback(
                offer_wall_id=int(wall_id),
                raw_data=dict(data),
                signature=signature,
                ip_address=ip,
            )
            if result.get('success'):
                return Response('1', status=status.HTTP_200_OK, content_type='text/plain')
            return Response('0', status=status.HTTP_200_OK, content_type='text/plain')
        except Exception as e:
            logger.error('OfferWallViewSet.postback error: %s', e)
            return Response('0', status=status.HTTP_200_OK, content_type='text/plain')

    @action(detail=False, methods=['get'])
    def customer_stats(self, request):
        """Customer offer completion stats।"""
        from ...models.core import Customer
        from ...services.OfferWallService import OfferWallService

        customer_id = request.query_params.get('customer_id')
        if not customer_id:
            return self.err('customer_id required')

        try:
            customer = Customer.objects.get(id=customer_id)
            stats = OfferWallService.get_customer_offer_stats(customer)
            return Response(stats)
        except Customer.DoesNotExist:
            return self.not_found('Customer not found')
    @action(detail=False, methods=['get'], url_path='completions')
    def offer_completions(self, request):
        """FIXED: OfferCompletion had NO API endpoint."""
        from ...models.offerwall import OfferCompletion
        cid = request.query_params.get('customer_id')
        qs  = OfferCompletion.objects.select_related('customer', 'offer').order_by('-completed_at')
        if cid: qs = qs.filter(customer_id=cid)
        return Response({'results': [{
            'id': c.id, 'offer_id': c.offer_id,
            'customer_code': c.customer.code if c.customer else '',
            'points_awarded': str(c.points_awarded), 'status': c.status,
            'completed_at': str(c.completed_at),
        } for c in qs[:50]]})

    @action(detail=False, methods=['get'], url_path='postback-log', permission_classes=[IsLoyaltyAdmin])
    def postback_log(self, request):
        """FIXED: OfferPostbackLog had NO API endpoint."""
        from ...models.offerwall import OfferPostbackLog
        qs = OfferPostbackLog.objects.order_by('-received_at')[:100]
        return Response({'results': [{
            'id': p.id, 'offer_id': p.offer_id, 'status': p.status,
            'retry_count': p.retry_count, 'received_at': str(p.received_at),
        } for p in qs]})
