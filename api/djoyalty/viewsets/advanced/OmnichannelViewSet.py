# djoyalty/viewsets/advanced/OmnichannelViewSet.py
"""
Omnichannel + Notifications Push + Points Stacking ViewSet
omnichannel.py: channel-aware earn/redeem, unified customer view
notifications_push.py: push notification delivery management
points_stacking.py: stacking rules -- max daily, source limits, cap enforcement
Previously: all 3 built, zero API routes।
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import serializers as drf_serializers
from ...serializers.AnalyticsSerializer import (
    OmnichannelEarnInputSerializer, OmnichannelEarnResultSerializer,
    PendingPointsHoldInputSerializer, PendingBucketSerializer,
    PointsStackingRuleSerializer,
)
from ...permissions import IsLoyaltyAdmin
from ...mixins import DjoyaltyBaseViewSet


# ─── Omnichannel ViewSet ───────────────────────────────────────────────────────

class OmnichannelViewSet(DjoyaltyBaseViewSet, viewsets.ViewSet):
    """
    GET  /omnichannel/customer/{id}/unified/   -- unified cross-channel view
    POST /omnichannel/earn/                    -- channel-aware earn
    GET  /omnichannel/channels/                -- configured channels
    GET  /omnichannel/customer/{id}/channel-history/ -- per-channel activity
    """
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'],
            url_path='customer/(?P<customer_id>[0-9]+)/unified')
    def unified_view(self, request, customer_id=None):
        from django.shortcuts import get_object_or_404
        from ...models.core import Customer
        from ...omnichannel import OmnichannelService
        customer = get_object_or_404(Customer, pk=customer_id)
        try:
            return Response(OmnichannelService.get_unified_customer_view(customer))
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    @action(detail=False, methods=['post'], url_path='earn')
    def channel_earn(self, request):
        customer_id  = request.data.get('customer_id')
        order_amount = request.data.get('order_amount', 0)
        channel      = request.data.get('channel', 'web')
        reference    = request.data.get('reference', '')
        if not customer_id:
            return self.err('customer_id required')
        from ...models.core import Customer
        customer = Customer.objects.filter(pk=customer_id).first()
        if not customer:
            return self.not_found('Customer not found')
        try:
            from decimal import Decimal
            from ...omnichannel import OmnichannelService
            result = OmnichannelService.process_channel_earn(
                customer=customer,
                order_amount=Decimal(str(order_amount)),
                channel=channel,
                reference=reference,
            )
            return Response(result, status=201)
        except Exception as e:
            return self.err(str(e))

    @action(detail=False, methods=['get'], url_path='channels')
    def channels(self, request):
        try:
            from ...omnichannel import OmnichannelService
            return Response({'channels': OmnichannelService.get_configured_channels()})
        except Exception as e:
            return Response({'channels': ['web', 'mobile', 'pos', 'api']})

    @action(detail=False, methods=['get'],
            url_path='customer/(?P<customer_id>[0-9]+)/channel-history')
    def channel_history(self, request, customer_id=None):
        from django.shortcuts import get_object_or_404
        from ...models.core import Customer
        from ...omnichannel import OmnichannelService
        customer = get_object_or_404(Customer, pk=customer_id)
        channel  = request.query_params.get('channel', '')
        try:
            return Response(OmnichannelService.get_channel_activity(
                customer=customer, channel=channel
            ))
        except Exception as e:
            return Response({'error': str(e)}, status=500)


# ─── Push Notifications ViewSet ────────────────────────────────────────────────

class PushNotificationViewSet(DjoyaltyBaseViewSet, viewsets.ViewSet):
    """
    POST /push/send/                 -- send push to customer(s)
    POST /push/batch/                -- batch push to segment
    GET  /push/delivery-stats/       -- delivery rate stats (admin)
    POST /push/register-token/       -- register device FCM token
    DELETE /push/unregister-token/   -- unregister token
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

    @action(detail=False, methods=['post'], url_path='register-token')
    def register_token(self, request):
        customer = self._get_customer(request)
        if not customer:
            return self.not_found('Customer not found')
        token   = request.data.get('token', '')
        platform = request.data.get('platform', 'android')
        if not token:
            return self.err('token required')
        try:
            from ...notifications_push import PushNotificationService
            PushNotificationService.register_token(
                customer=customer, token=token, platform=platform
            )
            return Response({'status': 'registered'}, status=201)
        except Exception as e:
            return self.err(str(e))

    @action(detail=False, methods=['delete'], url_path='unregister-token')
    def unregister_token(self, request):
        customer = self._get_customer(request)
        token    = request.data.get('token', '')
        if not token:
            return self.err('token required')
        try:
            from ...notifications_push import PushNotificationService
            PushNotificationService.unregister_token(customer=customer, token=token)
            return Response({'status': 'unregistered'})
        except Exception as e:
            return self.err(str(e))

    @action(detail=False, methods=['post'], url_path='send',
            permission_classes=[IsLoyaltyAdmin])
    def send_push(self, request):
        customer_id = request.data.get('customer_id')
        title       = request.data.get('title', '')
        body        = request.data.get('body', '')
        data        = request.data.get('data', {})
        if not customer_id or not title or not body:
            return self.err('customer_id, title, body required')
        from ...models.core import Customer
        customer = Customer.objects.filter(pk=customer_id).first()
        if not customer:
            return self.not_found('Customer not found')
        try:
            from ...notifications_push import PushNotificationService
            result = PushNotificationService.send(
                customer=customer, title=title, body=body, data=data
            )
            return Response({'status': 'sent', 'result': result})
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    @action(detail=False, methods=['post'], url_path='batch',
            permission_classes=[IsLoyaltyAdmin])
    def batch_push(self, request):
        title        = request.data.get('title', '')
        body         = request.data.get('body', '')
        customer_ids = request.data.get('customer_ids', [])
        segment      = request.data.get('segment', '')
        if not title or not body:
            return self.err('title and body required')
        try:
            from ...notifications_push import PushNotificationService
            result = PushNotificationService.send_batch(
                title=title, body=body,
                customer_ids=customer_ids, segment=segment,
            )
            return Response({'status': 'queued', 'result': result})
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    @action(detail=False, methods=['get'], url_path='delivery-stats',
            permission_classes=[IsLoyaltyAdmin])
    def delivery_stats(self, request):
        try:
            from ...notifications_push import PushNotificationService
            return Response(PushNotificationService.get_delivery_stats())
        except Exception as e:
            return Response({'error': str(e)}, status=500)


# ─── Points Stacking ViewSet ───────────────────────────────────────────────────

class PointsStackingViewSet(DjoyaltyBaseViewSet, viewsets.ViewSet):
    """
    GET  /points-stacking/rules/              -- stacking rules config
    POST /points-stacking/evaluate/           -- evaluate stacking for transaction
    GET  /points-stacking/customer/{id}/caps/ -- customer's daily/monthly caps
    """
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'], url_path='rules',
            permission_classes=[IsLoyaltyAdmin])
    def rules(self, request):
        try:
            from ...points_stacking import PointsStackingEngine
            return Response(PointsStackingEngine.get_active_rules())
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    @action(detail=False, methods=['post'], url_path='evaluate')
    def evaluate_stacking(self, request):
        customer_id    = request.data.get('customer_id')
        raw_points     = request.data.get('raw_points', 0)
        source         = request.data.get('source', 'purchase')
        if not customer_id:
            return self.err('customer_id required')
        from ...models.core import Customer
        customer = Customer.objects.filter(pk=customer_id).first()
        if not customer:
            return self.not_found('Customer not found')
        try:
            from decimal import Decimal
            from ...points_stacking import PointsStackingEngine
            result = PointsStackingEngine.evaluate(
                customer=customer,
                raw_points=Decimal(str(raw_points)),
                source=source,
            )
            return Response({'evaluation': result})
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    @action(detail=False, methods=['get'],
            url_path='customer/(?P<customer_id>[0-9]+)/caps')
    def customer_caps(self, request, customer_id=None):
        from django.shortcuts import get_object_or_404
        from ...models.core import Customer
        from ...points_stacking import PointsStackingEngine
        customer = get_object_or_404(Customer, pk=customer_id)
        try:
            return Response(PointsStackingEngine.get_customer_usage(customer))
        except Exception as e:
            return Response({'error': str(e)}, status=500)
