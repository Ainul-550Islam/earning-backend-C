# djoyalty/viewsets/advanced/SubscriptionViewSet.py
"""
Subscription Loyalty ViewSet -- exposes services/advanced/SubscriptionLoyaltyService.py
and models/advanced.py LoyaltySubscription।
Previously: full service + model, zero API routes।
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import serializers as drf_serializers
from ...permissions import IsLoyaltyAdmin
from ...mixins import DjoyaltyBaseViewSet


class LoyaltySubscriptionSerializer(drf_serializers.Serializer):
    id           = drf_serializers.IntegerField()
    plan_name    = drf_serializers.CharField()
    multiplier   = drf_serializers.DecimalField(max_digits=5, decimal_places=2)
    monthly_fee  = drf_serializers.DecimalField(max_digits=10, decimal_places=2)
    bonus_points_monthly = drf_serializers.DecimalField(max_digits=12, decimal_places=2)
    is_active    = drf_serializers.BooleanField()
    started_at   = drf_serializers.DateTimeField()
    expires_at   = drf_serializers.DateTimeField(allow_null=True)
    next_renewal_at = drf_serializers.DateTimeField(allow_null=True)


class SubscriptionViewSet(DjoyaltyBaseViewSet, viewsets.ViewSet):
    """
    GET  /subscriptions/my/               -- my active loyalty subscription
    GET  /subscriptions/plans/            -- available plans
    POST /subscriptions/subscribe/        -- subscribe
    POST /subscriptions/cancel/           -- cancel
    GET  /subscriptions/admin/active/     -- all active subscriptions (admin)
    POST /subscriptions/admin/process-renewals/ -- trigger renewal processing
    """
    permission_classes = [IsAuthenticated]

    def _get_customer(self, request):
        c = getattr(request, 'loyalty_customer', None)
        if c:
            return c
        cid = (request.query_params.get('customer_id') or
               request.data.get('customer_id'))
        if cid:
            from ...models.core import Customer
            return Customer.objects.filter(pk=cid).first()
        return None

    @action(detail=False, methods=['get'], url_path='my')
    def my_subscription(self, request):
        customer = self._get_customer(request)
        if not customer:
            return Response({'subscription': None})
        from ...models.advanced import LoyaltySubscription
        sub = LoyaltySubscription.objects.filter(
            customer=customer, is_active=True
        ).order_by('-started_at').first()
        if not sub:
            return Response({'subscription': None})
        return Response({'subscription': LoyaltySubscriptionSerializer(sub).data})

    @action(detail=False, methods=['post'], url_path='subscribe')
    def subscribe(self, request):
        customer    = self._get_customer(request)
        plan_name   = request.data.get('plan_name', 'Premium')
        payment_ref = request.data.get('payment_reference', '')
        if not customer:
            return self.not_found('Customer not found')
        from ...models.advanced import LoyaltySubscription
        existing = LoyaltySubscription.objects.filter(
            customer=customer, is_active=True
        ).first()
        if existing:
            return self.err('Already subscribed')
        try:
            from ...services.advanced.SubscriptionLoyaltyService import SubscriptionLoyaltyService
            sub = SubscriptionLoyaltyService.create_subscription(
                customer=customer,
                plan_name=plan_name,
                payment_reference=payment_ref,
            )
            return Response({
                'status': 'subscribed',
                'plan': sub.plan_name,
                'subscription_id': sub.id,
                'next_renewal_at': str(sub.next_renewal_at) if sub.next_renewal_at else None,
            }, status=201)
        except Exception as e:
            return self.err(str(e))

    @action(detail=False, methods=['post'], url_path='cancel')
    def cancel(self, request):
        customer = self._get_customer(request)
        if not customer:
            return self.not_found('Customer not found')
        from ...models.advanced import LoyaltySubscription
        sub = LoyaltySubscription.objects.filter(
            customer=customer, is_active=True
        ).first()
        if not sub:
            return self.err('No active subscription')
        try:
            from ...services.advanced.SubscriptionLoyaltyService import SubscriptionLoyaltyService
            SubscriptionLoyaltyService.cancel(sub, reason=request.data.get('reason', ''))
            return Response({'status': 'cancelled'})
        except Exception as e:
            return self.err(str(e))

    @action(detail=False, methods=['get'], url_path='admin/active',
            permission_classes=[IsLoyaltyAdmin])
    def admin_active(self, request):
        from ...models.advanced import LoyaltySubscription
        qs = LoyaltySubscription.objects.filter(is_active=True).select_related('customer')
        data = [{
            'id': s.id,
            'customer_code': s.customer.code if s.customer else '',
            'plan_name': s.plan_name,
            'multiplier': str(s.multiplier),
            'expires_at': str(s.expires_at) if s.expires_at else None,
        } for s in qs[:100]]
        return Response({'count': len(data), 'subscriptions': data})

    @action(detail=False, methods=['post'], url_path='admin/process-renewals',
            permission_classes=[IsLoyaltyAdmin])
    def process_renewals(self, request):
        try:
            from ...tasks.subscription_tasks import process_subscription_renewals_task
            process_subscription_renewals_task()
            return Response({'status': 'queued'})
        except Exception as e:
            return Response({'error': str(e)}, status=500)
