# viewsets/GatewayStatementViewSet.py
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from core.views import BaseViewSet
from api.payment_gateways.models.reconciliation import GatewayStatement
from rest_framework import serializers


class GatewayStatementSerializer(serializers.ModelSerializer):
    gateway_name  = serializers.CharField(source='gateway.name', read_only=True)
    class Meta:
        model  = GatewayStatement
        fields = ['id','gateway_name','period_start','period_end','total_amount',
                  'total_count','currency','format','is_reconciled','imported_at']

class GatewayStatementViewSet(BaseViewSet):
    """Admin: import and manage gateway statements for reconciliation."""
    queryset           = GatewayStatement.objects.all().order_by('-period_start')
    serializer_class   = GatewayStatementSerializer
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['post'])
    def import_json(self, request):
        """Import gateway statement as JSON."""
        from api.payment_gateways.models.core import PaymentGateway
        from decimal import Decimal

        gateway_name = request.data.get('gateway')
        period_start = request.data.get('period_start')
        period_end   = request.data.get('period_end')
        transactions = request.data.get('transactions', [])

        try:
            gw    = PaymentGateway.objects.get(name=gateway_name)
            total = sum(Decimal(str(t.get('amount', 0))) for t in transactions)

            stmt  = GatewayStatement.objects.create(
                gateway=gw, period_start=period_start, period_end=period_end,
                raw_data=transactions, total_amount=total,
                total_count=len(transactions), imported_by=request.user
            )
            return self.success_response(
                data=GatewayStatementSerializer(stmt).data,
                message=f'Imported {len(transactions)} transactions for {gateway_name}.'
            )
        except Exception as e:
            return self.error_response(message=str(e), status_code=400)

    @action(detail=True, methods=['post'])
    def reconcile(self, request, pk=None):
        """Trigger reconciliation for this statement."""
        stmt = self.get_object()
        from api.payment_gateways.tasks.reconciliation_tasks import reconcile_gateway
        reconcile_gateway.delay(stmt.gateway.name, str(stmt.period_start))
        return self.success_response(message='Reconciliation started in background.')
