# api/djoyalty/viewsets/advanced/AdminLoyaltyViewSet.py
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from ...models.core import Customer
from ...models.advanced import PointsAbuseLog
from ...serializers.AdminSerializer import AdminCustomerDetailSerializer
from ...serializers.InsightSerializer import FraudLogSerializer
from ...services.advanced.LoyaltyFraudService import LoyaltyFraudService
from ...services.tiers.TierEvaluationService import TierEvaluationService
from ...permissions import IsLoyaltyAdmin
from ...pagination import DjoyaltyPagePagination

class AdminLoyaltyViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated, IsLoyaltyAdmin]

    @action(detail=False, methods=['get'])
    def customer_overview(self, request):
        customer_id = request.query_params.get('customer_id')
        customer = get_object_or_404(Customer, pk=customer_id)
        return Response(AdminCustomerDetailSerializer(customer).data)

    @action(detail=False, methods=['post'])
    def recalculate_tier(self, request):
        customer_id = request.data.get('customer_id')
        customer = get_object_or_404(Customer, pk=customer_id)
        user_tier = TierEvaluationService.evaluate(customer, tenant=customer.tenant)
        return Response({'tier': str(user_tier.tier) if user_tier else 'No change'})

    @action(detail=False, methods=['get'])
    def fraud_logs(self, request):
        qs = PointsAbuseLog.objects.select_related('customer').order_by('-created_at')
        is_resolved = request.query_params.get('is_resolved')
        risk_level = request.query_params.get('risk_level')
        if is_resolved is not None:
            qs = qs.filter(is_resolved=is_resolved.lower() == 'true')
        if risk_level:
            qs = qs.filter(risk_level=risk_level)
        return Response(FraudLogSerializer(qs[:50], many=True).data)
