# api/payment_gateways/referral/views.py
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from core.views import BaseViewSet
from .models import ReferralLink, Referral, ReferralCommission, ReferralProgram
from .serializers import (ReferralLinkSerializer, ReferralSerializer,
                           ReferralCommissionSerializer, ReferralStatsSerializer,
                           ReferralProgramSerializer)
from .ReferralEngine import ReferralEngine

class ReferralViewSet(BaseViewSet):
    queryset           = Referral.objects.all().order_by('-created_at')
    serializer_class   = ReferralSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            return super().get_queryset()
        return super().get_queryset().filter(referrer=self.request.user)

    @action(detail=False, methods=['get'])
    def my_link(self, request):
        engine = ReferralEngine()
        link   = engine.get_or_create_referral_link(request.user)
        return self.success_response(data=ReferralLinkSerializer(link).data)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        engine = ReferralEngine()
        stats  = engine.get_referral_stats(request.user)
        return self.success_response(data=ReferralStatsSerializer(stats).data)

    @action(detail=False, methods=['get'])
    def commissions(self, request):
        qs = ReferralCommission.objects.filter(referrer=request.user).order_by('-created_at')
        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(ReferralCommissionSerializer(page, many=True).data)
        return self.success_response(data=ReferralCommissionSerializer(qs, many=True).data)

    @action(detail=False, methods=['get'])
    def program(self, request):
        prog = ReferralProgram.objects.filter(is_active=True).first()
        if not prog:
            return self.success_response(data={})
        return self.success_response(data=ReferralProgramSerializer(prog).data)
