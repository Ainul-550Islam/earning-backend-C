# FILE 84 of 257 — fraud/views.py
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.decorators import action
from rest_framework import filters
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from core.views import BaseViewSet
from .models import FraudAlert, BlockedIP, RiskRule
from .serializers import FraudAlertSerializer, BlockedIPSerializer, RiskRuleSerializer

class FraudAlertViewSet(BaseViewSet):
    queryset           = FraudAlert.objects.all().order_by('-created_at')
    serializer_class   = FraudAlertSerializer
    permission_classes = [IsAdminUser]
    filter_backends    = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields   = ['risk_level','action','gateway','resolved']

    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        alert             = self.get_object()
        alert.resolved    = True
        alert.resolved_by = request.user
        alert.resolved_at = timezone.now()
        alert.notes       = request.data.get('notes','')
        alert.save()
        return self.success_response(data=FraudAlertSerializer(alert).data, message='Alert resolved')

    @action(detail=False, methods=['get'])
    def unresolved(self, request):
        qs = self.get_queryset().filter(resolved=False)
        return self.success_response(data=FraudAlertSerializer(qs, many=True).data)

class BlockedIPViewSet(BaseViewSet):
    queryset           = BlockedIP.objects.all().order_by('-created_at')
    serializer_class   = BlockedIPSerializer
    permission_classes = [IsAdminUser]
    filter_backends    = [DjangoFilterBackend]
    filterset_fields   = ['is_active']

    def perform_create(self, serializer):
        serializer.save(blocked_by=self.request.user)

    @action(detail=True, methods=['post'])
    def unblock(self, request, pk=None):
        ip            = self.get_object()
        ip.is_active  = False
        ip.save()
        from django.core.cache import cache
        cache.delete(f'fraud:ip:{ip.ip_address}')
        return self.success_response(message=f'{ip.ip_address} unblocked')

class RiskRuleViewSet(BaseViewSet):
    queryset           = RiskRule.objects.all().order_by('priority')
    serializer_class   = RiskRuleSerializer
    permission_classes = [IsAdminUser]
    filter_backends    = [DjangoFilterBackend]
    filterset_fields   = ['is_active','condition_type']

    @action(detail=True, methods=['post'])
    def toggle(self, request, pk=None):
        rule           = self.get_object()
        rule.is_active = not rule.is_active
        rule.save()
        return self.success_response(data=RiskRuleSerializer(rule).data,
                                     message=f'Rule {"enabled" if rule.is_active else "disabled"}')
