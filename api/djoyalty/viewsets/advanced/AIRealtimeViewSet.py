# djoyalty/viewsets/advanced/AIRealtimeViewSet.py
"""
AI Realtime Offers ViewSet -- exposes ai_realtime_offers.py
AIRealtimeOfferEngine (55KB of ML inference + rule-based scoring)।
Previously: full engine built, zero API routes।
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import serializers as drf_serializers
from ...serializers.AnalyticsSerializer import (
    AIOfferSerializer, AIOfferFeedbackInputSerializer, AIEngineMetricsSerializer,
)
from ...permissions import IsLoyaltyAdmin
from ...mixins import DjoyaltyBaseViewSet


class AIRealtimeViewSet(DjoyaltyBaseViewSet, viewsets.ViewSet):
    """
    GET  /ai-realtime/offers/               -- get real-time personalized offers
    POST /ai-realtime/score/                -- score a specific offer for a customer
    POST /ai-realtime/feedback/             -- record offer feedback (improves model)
    GET  /ai-realtime/context/{id}/         -- customer's real-time ML context
    POST /ai-realtime/admin/generate/       -- generate new real-time offers batch
    GET  /ai-realtime/admin/metrics/        -- engine performance metrics
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

    @action(detail=False, methods=['get'], url_path='offers')
    def realtime_offers(self, request):
        customer = self._get_customer(request)
        if not customer:
            return Response({'offers': []})
        channel  = request.query_params.get('channel', 'app')
        limit    = int(request.query_params.get('limit', 5))
        try:
            from ...ai_realtime_offers import AIRealtimeOfferEngine
            offers = AIRealtimeOfferEngine.get_offers(
                customer=customer, channel=channel, limit=limit
            )
            return Response({'offers': offers, 'channel': channel})
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    @action(detail=False, methods=['post'], url_path='score')
    def score_offer(self, request):
        customer   = self._get_customer(request)
        offer_id   = request.data.get('offer_id')
        offer_type = request.data.get('offer_type', 'personalized')
        if not customer or not offer_id:
            return self.err('customer_id and offer_id required')
        try:
            from ...ai_realtime_offers import AIRealtimeOfferEngine
            score = AIRealtimeOfferEngine.score_offer(
                customer=customer, offer_id=offer_id, offer_type=offer_type
            )
            return Response({'offer_id': offer_id, 'score': score})
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    @action(detail=False, methods=['post'], url_path='feedback')
    def offer_feedback(self, request):
        customer  = self._get_customer(request)
        offer_id  = request.data.get('offer_id')
        action    = request.data.get('action')  # 'clicked', 'dismissed', 'claimed'
        if not customer or not offer_id or not action:
            return self.err('customer_id, offer_id, action required')
        try:
            from ...ai_realtime_offers import AIRealtimeOfferEngine
            AIRealtimeOfferEngine.record_feedback(
                customer=customer, offer_id=offer_id, action=action
            )
            return Response({'status': 'recorded'})
        except Exception as e:
            return self.err(str(e))

    @action(detail=False, methods=['get'],
            url_path='context/(?P<customer_id>[0-9]+)')
    def customer_context(self, request, customer_id=None):
        from django.shortcuts import get_object_or_404
        from ...models.core import Customer
        from ...ai_realtime_offers import AIRealtimeOfferEngine
        customer = get_object_or_404(Customer, pk=customer_id)
        try:
            ctx = AIRealtimeOfferEngine.get_customer_context(customer)
            return Response({'context': ctx})
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    @action(detail=False, methods=['post'], url_path='admin/generate',
            permission_classes=[IsLoyaltyAdmin])
    def generate_batch(self, request):
        segment     = request.data.get('segment', '')
        trigger     = request.data.get('trigger', 'scheduled')
        max_per_cus = int(request.data.get('max_per_customer', 3))
        try:
            from ...ai_realtime_offers import AIRealtimeOfferEngine
            count = AIRealtimeOfferEngine.generate_batch(
                segment=segment, trigger=trigger, max_per_customer=max_per_cus
            )
            return Response({'status': 'generated', 'count': count})
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    @action(detail=False, methods=['get'], url_path='admin/metrics',
            permission_classes=[IsLoyaltyAdmin])
    def engine_metrics(self, request):
        try:
            from ...ai_realtime_offers import AIRealtimeOfferEngine
            return Response(AIRealtimeOfferEngine.get_metrics())
        except Exception as e:
            return Response({'error': str(e)}, status=500)
