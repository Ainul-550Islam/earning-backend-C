# viewsets/ReconciliationViewSet.py
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from core.views import BaseViewSet
from api.payment_gateways.models.reconciliation import ReconciliationBatch, ReconciliationMismatch
from rest_framework import serializers


class ReconciliationBatchSerializer(serializers.ModelSerializer):
    gateway_name = serializers.CharField(source='gateway.name', read_only=True)
    match_rate   = serializers.FloatField(read_only=True)
    class Meta:
        model  = ReconciliationBatch
        fields = ['id','date','gateway_name','status','total_matched','total_mismatched',
                  'discrepancy_amount','match_rate','started_at','completed_at']

class MismatchSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ReconciliationMismatch
        fields = ['id','mismatch_type','our_reference_id','our_amount','gateway_txn_id',
                  'gateway_amount','amount_difference','resolution_status','resolved']


class ReconciliationViewSet(BaseViewSet):
    queryset           = ReconciliationBatch.objects.all().order_by('-date')
    serializer_class   = ReconciliationBatchSerializer
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['post'])
    def run(self, request):
        """Manually trigger reconciliation."""
        from api.payment_gateways.services.ReconciliationService import ReconciliationService
        from datetime import datetime, date
        gateway   = request.data.get('gateway', 'bkash')
        date_str  = request.data.get('date', str((date.today() - __import__('datetime').timedelta(days=1))))
        try:
            target = datetime.strptime(date_str, '%Y-%m-%d').date()
            result = ReconciliationService().reconcile(gateway, target)
            return self.success_response(data=result, message='Reconciliation completed')
        except Exception as e:
            return self.error_response(message=str(e), status_code=400)

    @action(detail=True, methods=['get'])
    def mismatches(self, request, pk=None):
        """Get mismatches for a reconciliation batch."""
        batch = self.get_object()
        qs    = batch.mismatches.all()
        return self.success_response(data=MismatchSerializer(qs, many=True).data)

    @action(detail=True, methods=['post'])
    def resolve_mismatch(self, request, pk=None):
        """Mark a mismatch as resolved."""
        batch      = self.get_object()
        mismatch_id= request.data.get('mismatch_id')
        note       = request.data.get('note', '')
        from django.utils import timezone
        try:
            mm = batch.mismatches.get(id=mismatch_id)
            mm.resolved           = True
            mm.resolution_status  = 'resolved'
            mm.resolved_at        = timezone.now()
            mm.resolved_by        = request.user
            mm.resolution_note    = note
            mm.save()
            return self.success_response(message='Mismatch resolved')
        except ReconciliationMismatch.DoesNotExist:
            return self.error_response(message='Mismatch not found', status_code=404)
