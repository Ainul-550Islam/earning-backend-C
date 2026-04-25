# viewsets/AdminPaymentViewSet.py
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from core.views import BaseViewSet
from rest_framework.response import Response
from rest_framework import serializers


class AdminPaymentViewSet(BaseViewSet):
    """Superadmin payment overview dashboard."""
    permission_classes = [IsAdminUser]

    def list(self, request):
        """Overview stats for admin dashboard."""
        from api.payment_gateways.services.GatewayAnalyticsService import GatewayAnalyticsService
        from api.payment_gateways.models.core import GatewayTransaction, PayoutRequest
        from django.db.models import Sum, Count
        from django.utils import timezone
        from datetime import timedelta

        today = timezone.now().date()
        yesterday = today - timedelta(days=1)

        today_stats = GatewayTransaction.objects.filter(
            created_at__date=today
        ).aggregate(
            deposits=Sum('amount', filter=__import__('django.db.models',fromlist=['Q']).Q(transaction_type='deposit', status='completed')),
            withdrawals=Sum('amount', filter=__import__('django.db.models',fromlist=['Q']).Q(transaction_type='withdrawal', status='completed')),
            total_txns=Count('id'),
            failed=Count('id', filter=__import__('django.db.models',fromlist=['Q']).Q(status='failed')),
        )

        pending_payouts = PayoutRequest.objects.filter(status='pending').count()
        gateway_summary = GatewayAnalyticsService().get_gateway_summary(7)

        return Response({'success': True, 'data': {
            'today': today_stats,
            'pending_payouts': pending_payouts,
            'gateway_summary': gateway_summary,
        }})

    @action(detail=False, methods=['get'])
    def pending_payouts(self, request):
        from api.payment_gateways.models.core import PayoutRequest
        from rest_framework import serializers as s
        class PS(s.ModelSerializer):
            user_email = s.EmailField(source='user.email', read_only=True)
            class Meta:
                model  = PayoutRequest
                fields = ['id','user_email','amount','payout_method','status','created_at']
        qs = PayoutRequest.objects.filter(status='pending').order_by('created_at')
        return Response({'success': True, 'data': PS(qs, many=True).data})

    @action(detail=False, methods=['post'])
    def bulk_approve_payouts(self, request):
        from api.payment_gateways.models.core import PayoutRequest
        ids = request.data.get('payout_ids', [])
        approved = PayoutRequest.objects.filter(id__in=ids, status='pending').update(status='approved')
        return Response({'success': True, 'message': f'{approved} payouts approved.'})

    @action(detail=False, methods=['get'])
    def failed_transactions(self, request):
        from api.payment_gateways.models.core import GatewayTransaction
        from django.utils import timezone
        from datetime import timedelta
        since = timezone.now() - timedelta(hours=24)
        qs    = GatewayTransaction.objects.filter(status='failed', created_at__gte=since)
        return Response({'success': True, 'count': qs.count(),
                         'data': [{'id':t.id,'gateway':t.gateway,'amount':str(t.amount),
                                   'reference_id':t.reference_id} for t in qs[:50]]})
