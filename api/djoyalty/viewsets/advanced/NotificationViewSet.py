# api/djoyalty/viewsets/advanced/NotificationViewSet.py
"""
NotificationViewSet -- admin notification management + trigger API।

FIXED: NotificationTriggerService was fully built with 8 trigger methods
(tier_upgrade, tier_downgrade, streak_broken, expiry_warning, points_earned,
cashout_approved, cashout_rejected, birthday) but no viewset called them।
Admin API added: POST /notifications/admin/trigger/ fires any event।
"""
import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from ...models.notifications import NotificationCenter
from ...permissions import IsLoyaltyAdmin
from ...mixins import DjoyaltyBaseViewSet
from ...serializers.NotificationSerializer import (
    NotificationCenterSerializer, NotificationCenterSerializer,
    NotificationPreferenceSerializer,
)

logger = logging.getLogger(__name__)


class NotificationViewSet(DjoyaltyBaseViewSet, viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def _get_customer(self, request):
        c = getattr(request, 'loyalty_customer', None)
        if c: return c
        cid = request.query_params.get('customer_id') or request.data.get('customer_id')
        if cid:
            from ...models.core import Customer
            return Customer.objects.filter(pk=cid).first()
        return None

    @action(detail=False, methods=['get'], url_path='my')
    def my_notifications(self, request):
        customer = self._get_customer(request)
        if not customer: return Response({'results': []})
        qs = NotificationCenter.objects.filter(customer=customer).order_by('is_read', '-created_at')[:50]
        return Response({'results': NotificationCenterSerializer(qs, many=True).data,
                         'unread_count': qs.filter(is_read=False).count()})

    @action(detail=False, methods=['post'], url_path='mark-read')
    def mark_read(self, request):
        nid = request.data.get('notification_id')
        customer = self._get_customer(request)
        if not nid: return self.err('notification_id required')
        updated = NotificationCenter.objects.filter(pk=nid, customer=customer, is_read=False).update(is_read=True)
        return Response({'status': 'ok', 'updated': updated})

    @action(detail=False, methods=['post'], url_path='mark-all-read')
    def mark_all_read(self, request):
        customer = self._get_customer(request)
        if not customer: return self.not_found('Customer not found')
        updated = NotificationCenter.objects.filter(customer=customer, is_read=False).update(is_read=True)
        return Response({'status': 'ok', 'marked_read': updated})

    @action(detail=False, methods=['get', 'put'], url_path='preferences')
    def preferences(self, request):
        from ...models.notifications import NotificationPreference
        customer = self._get_customer(request)
        if not customer: return self.not_found('Customer not found')
        pref, _ = NotificationPreference.objects.get_or_create(customer=customer)
        if request.method == 'PUT':
            ser = NotificationPreferenceSerializer(pref, data=request.data, partial=True)
            ser.is_valid(raise_exception=True)
            ser.save()
        return Response(NotificationPreferenceSerializer(pref).data)

    @action(detail=False, methods=['post'], url_path='admin/send', permission_classes=[IsLoyaltyAdmin])
    def admin_send(self, request):
        """Admin sends manual notification using NotificationCenterSerializer."""
        ser = NotificationCenterSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        from django.shortcuts import get_object_or_404
        from ...models.core import Customer
        from ...services.NotificationService import NotificationService
        customer = get_object_or_404(Customer, pk=data['customer_id'])
        try:
            NotificationService.send(customer=customer, notification_type=data['notification_type'],
                                     title=data['title'], body=data['body'],
                                     icon=data.get('icon', '🔔'), metadata=data.get('metadata', {}),
                                     priority=data.get('priority', 'normal'))
            return Response({'status': 'sent', 'customer': customer.code})
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    @action(detail=False, methods=['post'], url_path='admin/trigger', permission_classes=[IsLoyaltyAdmin])
    def admin_trigger(self, request):
        """
        FIXED: NotificationTriggerService had 8 trigger methods, none callable via API.
        POST { "customer_id": 1, "event": "tier_upgrade", "params": {"from_tier":"silver","to_tier":"gold"} }
        Valid events: tier_upgrade, tier_downgrade, streak_broken, expiry_warning,
                      points_earned, cashout_approved, cashout_rejected, birthday
        """
        from django.shortcuts import get_object_or_404
        from ...models.core import Customer
        from ...services.NotificationTriggerService import NotificationTriggerService
        customer_id = request.data.get('customer_id')
        event       = request.data.get('event', '')
        params      = request.data.get('params', {})
        if not customer_id or not event:
            return self.err('customer_id and event required')
        customer = get_object_or_404(Customer, pk=customer_id)
        trigger_map = {
            'tier_upgrade':   lambda: NotificationTriggerService.trigger_tier_upgrade(customer,
                from_tier=params.get('from_tier',''), to_tier=params.get('to_tier',''), tenant=customer.tenant),
            'tier_downgrade': lambda: NotificationTriggerService.trigger_tier_downgrade(customer,
                from_tier=params.get('from_tier',''), to_tier=params.get('to_tier',''), tenant=customer.tenant),
            'streak_broken':  lambda: NotificationTriggerService.trigger_streak_broken(customer,
                streak_days=params.get('streak_days',0), tenant=customer.tenant),
            'expiry_warning': lambda: NotificationTriggerService.trigger_expiry_warning(customer,
                points=params.get('points',0), days_left=params.get('days_left',7), tenant=customer.tenant),
            'points_earned':  lambda: NotificationTriggerService.trigger_points_earned(customer,
                points=params.get('points',0), tenant=customer.tenant),
            'cashout_approved': lambda: NotificationTriggerService.trigger_cashout_approved(customer,
                amount=params.get('amount',0), method=params.get('method',''), tenant=customer.tenant),
            'cashout_rejected': lambda: NotificationTriggerService.trigger_cashout_rejected(customer,
                reason=params.get('reason',''), tenant=customer.tenant),
            'birthday': lambda: NotificationTriggerService.trigger_birthday(customer, tenant=customer.tenant),
        }
        if event not in trigger_map:
            return Response({'error': f'Unknown event: {event}', 'valid': list(trigger_map)}, status=400)
        try:
            trigger_map[event]()
            return Response({'status': 'triggered', 'event': event, 'customer': customer.code})
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    @action(detail=False, methods=['post'], url_path='admin/test', permission_classes=[IsLoyaltyAdmin])
    def admin_test(self, request):
        """Test a delivery channel (push/email/sms)."""
        from django.shortcuts import get_object_or_404
        from ...models.core import Customer
        from ...services.NotificationService import NotificationService
        customer_id = request.data.get('customer_id')
        channel     = request.data.get('channel', 'push')
        customer    = get_object_or_404(Customer, pk=customer_id)
        try:
            NotificationService.send(customer=customer, notification_type='test',
                title='🧪 Test Notification',
                body=f'Test via {channel}. If you see this, the channel works!', priority='high')
            return Response({'status': 'test_sent', 'channel': channel})
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    @action(detail=False, methods=['get'], url_path='admin/queue', permission_classes=[IsLoyaltyAdmin])
    def admin_queue(self, request):
        qs = NotificationCenter.objects.filter(is_sent=False).select_related('customer').order_by('created_at')[:100]
        return Response({'count': qs.count(), 'queue': NotificationCenterSerializer(qs, many=True).data})
    @action(detail=False, methods=['get'], url_path='points-alerts')
    def points_alerts(self, request):
        """
        FIXED: PointsAlert had NO API endpoint.
        Customers can now query their own points alerts (low balance, expiry etc).
        """
        from ...models.advanced import PointsAlert
        cid = request.query_params.get('customer_id')
        if not cid:
            return self.err('customer_id required')
        qs = PointsAlert.objects.filter(customer_id=cid).order_by('-created_at')[:20]
        return Response({'alerts': [{
            'id': a.id, 'alert_type': a.alert_type, 'message': a.message,
            'is_read': a.is_read, 'created_at': str(a.created_at),
        } for a in qs]})

    @action(detail=False, methods=['get'], url_path='loyalty-notifications', permission_classes=[IsLoyaltyAdmin])
    def loyalty_notifications(self, request):
        """
        FIXED: LoyaltyNotification had NO API endpoint.
        Admin view of all outgoing loyalty event notifications.
        """
        from ...models.advanced import LoyaltyNotification
        qs = LoyaltyNotification.objects.select_related('customer').order_by('-created_at')[:100]
        ntype = request.query_params.get('type')
        if ntype: qs = qs.filter(notification_type=ntype)
        return Response({'count': qs.count(), 'results': [{
            'id': n.id, 'customer_code': n.customer.code if n.customer else '',
            'notification_type': n.notification_type, 'title': n.title,
            'is_sent': n.is_sent, 'created_at': str(n.created_at),
        } for n in qs]})
    @action(detail=False, methods=['get', 'post'], url_path='templates', permission_classes=[IsLoyaltyAdmin])
    def templates(self, request):
        """
        FIXED: NotificationTemplate had NO API endpoint.
        Manage notification message templates (title/body with placeholders).
        """
        from ...models.notifications import NotificationTemplate
        if request.method == 'GET':
            qs = NotificationTemplate.objects.all().order_by('notification_type')
            return Response({'templates': [{
                'id': t.id, 'notification_type': t.notification_type,
                'title_template': t.title_template, 'body_template': t.body_template,
                'icon': t.icon, 'is_active': t.is_active,
            } for t in qs]})
        tmpl = NotificationTemplate.objects.update_or_create(
            notification_type=request.data.get('notification_type'),
            defaults={
                'title_template': request.data.get('title_template', ''),
                'body_template':  request.data.get('body_template', ''),
                'icon':           request.data.get('icon', '🔔'),
                'is_active':      request.data.get('is_active', True),
            },
        )[0]
        return Response({'id': tmpl.id, 'notification_type': tmpl.notification_type},
                        status=status.HTTP_201_CREATED)
