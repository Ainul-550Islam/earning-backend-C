# api/payment_gateways/bonuses/serializers.py
from rest_framework import serializers
from .models import PerformanceTier, PublisherBonus


class PerformanceTierSerializer(serializers.ModelSerializer):
    class Meta:
        model  = PerformanceTier
        fields = ['id','name','min_monthly_earnings','bonus_percent',
                  'min_payout_threshold','priority_support','exclusive_offers',
                  'custom_payout_negotiation','badge_color','sort_order']


class PublisherBonusSerializer(serializers.ModelSerializer):
    publisher_email = serializers.EmailField(source='publisher.email', read_only=True)
    bonus_type_display = serializers.CharField(source='get_bonus_type_display', read_only=True)

    class Meta:
        model  = PublisherBonus
        fields = ['id','publisher_email','bonus_type','bonus_type_display',
                  'amount','currency','status','description','period',
                  'paid_at','created_at']
        read_only_fields = ['status','paid_at','created_at']


class PublisherTierStatusSerializer(serializers.Serializer):
    """Current tier status for a publisher."""
    current_tier         = PerformanceTierSerializer(allow_null=True)
    next_tier            = PerformanceTierSerializer(allow_null=True)
    last_30d_earnings    = serializers.FloatField()
    earnings_needed      = serializers.FloatField()
    bonus_percent        = serializers.FloatField()
    is_fast_pay_eligible = serializers.BooleanField()


class MonthlyBonusRunSerializer(serializers.Serializer):
    year  = serializers.IntegerField(min_value=2020, max_value=2099)
    month = serializers.IntegerField(min_value=1, max_value=12)
