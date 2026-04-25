# api/payment_gateways/bonuses/views.py
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from core.views import BaseViewSet
from .models import PerformanceTier, PublisherBonus
from .serializers import PerformanceTierSerializer, PublisherBonusSerializer, PublisherTierStatusSerializer, MonthlyBonusRunSerializer
from rest_framework import serializers


class TierSerializer(serializers.ModelSerializer):
    class Meta:
        model  = PerformanceTier
        fields = ['id','name','min_monthly_earnings','bonus_percent','min_payout_threshold',
                  'priority_support','exclusive_offers','badge_color','sort_order']

class BonusSerializer(serializers.ModelSerializer):
    class Meta:
        model  = PublisherBonus
        fields = ['id','bonus_type','amount','currency','status','description','paid_at','period','created_at']


class PerformanceTierViewSet(BaseViewSet):
    queryset           = PerformanceTier.objects.all()
    serializer_class   = PerformanceTierSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def my_tier(self, request):
        from .BonusEngine import BonusEngine
        tier = BonusEngine().get_publisher_tier(request.user)
        return self.success_response(data=TierSerializer(tier).data if tier else None)


class PublisherBonusViewSet(BaseViewSet):
    queryset           = PublisherBonus.objects.all().order_by('-created_at')
    serializer_class   = PublisherBonusSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            return super().get_queryset()
        return super().get_queryset().filter(publisher=self.request.user)

    @action(detail=False, methods=['post'], permission_classes=[IsAdminUser])
    def run_monthly(self, request):
        from .BonusEngine import BonusEngine
        year  = int(request.data.get('year', __import__('django.utils.timezone',fromlist=['timezone']).timezone.now().year))
        month = int(request.data.get('month', __import__('django.utils.timezone',fromlist=['timezone']).timezone.now().month))
        result = BonusEngine().award_monthly_bonuses(year, month)
        return self.success_response(data=result, message=f'{result["awarded"]} bonuses awarded')
