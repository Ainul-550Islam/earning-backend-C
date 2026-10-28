# api/djoyalty/viewsets/audit/CustomerDeviceViewSet.py
"""
CustomerDeviceViewSet -- Push token registration + device management。
FIXED: CustomerDevice had NO API endpoint -- push notifications could not
be registered from mobile apps via API。
"""
import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from ...models.audit import CustomerDevice
from ...permissions import IsLoyaltyAdmin
from ...mixins import DjoyaltyBaseViewSet

logger = logging.getLogger(__name__)


class CustomerDeviceViewSet(DjoyaltyBaseViewSet, viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def _customer(self, request):
        cid = request.data.get('customer_id') or request.query_params.get('customer_id')
        if cid:
            from ...models.core import Customer
            return Customer.objects.filter(pk=cid).first()
        return getattr(request, 'loyalty_customer', None)

    @action(detail=False, methods=['post'], url_path='register')
    def register(self, request):
        """Register/update push notification token for a device。"""
        customer = self._customer(request)
        if not customer:
            return self.err('customer_id required')
        token        = request.data.get('token', '').strip()
        platform     = request.data.get('platform', 'android')
        device_id    = request.data.get('device_id', '')
        app_version  = request.data.get('app_version', '')
        if not token:
            return self.err('token required')
        if platform not in ('android', 'ios', 'web'):
            return self.err('platform must be android|ios|web')
        device, created = CustomerDevice.objects.update_or_create(
            customer=customer, device_id=device_id or token[:64],
            defaults={
                'push_token':   token,
                'platform':     platform,
                'app_version':  app_version,
                'is_active':    True,
                'tenant':       getattr(customer, 'tenant', None),
            },
        )
        return Response({
            'status':    'registered' if created else 'updated',
            'device_id': device.device_id,
            'platform':  device.platform,
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='deregister')
    def deregister(self, request):
        """Deactivate push token (on logout)。"""
        token    = request.data.get('token', '')
        customer = self._customer(request)
        if not token:
            return self.err('token required')
        updated = CustomerDevice.objects.filter(
            push_token=token, customer=customer
        ).update(is_active=False)
        return Response({'status': 'deregistered', 'updated': updated})

    @action(detail=False, methods=['get'], url_path='my-devices')
    def my_devices(self, request):
        """List all active devices for a customer。"""
        customer = self._customer(request)
        if not customer:
            return Response({'devices': []})
        qs = CustomerDevice.objects.filter(customer=customer, is_active=True)
        return Response({'devices': [{
            'device_id': d.device_id, 'platform': d.platform,
            'app_version': d.app_version, 'registered_at': str(d.created_at),
        } for d in qs]})

    @action(detail=False, methods=['get'], url_path='admin/all', permission_classes=[IsLoyaltyAdmin])
    def admin_all(self, request):
        """Admin: list all devices (for push campaign targeting)。"""
        platform = request.query_params.get('platform')
        qs = CustomerDevice.objects.filter(is_active=True)
        if platform: qs = qs.filter(platform=platform)
        qs = qs.select_related('customer').order_by('-created_at')[:500]
        return Response({'count': qs.count(), 'devices': [{
            'device_id':      d.device_id,
            'platform':       d.platform,
            'customer_code':  d.customer.code if d.customer else '',
            'app_version':    d.app_version,
        } for d in qs]})
