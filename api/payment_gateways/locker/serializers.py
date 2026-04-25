# api/payment_gateways/locker/serializers.py
from rest_framework import serializers
from .models import ContentLocker, OfferWall, UserVirtualBalance, VirtualReward


class ContentLockerSerializer(serializers.ModelSerializer):
    embed_code   = serializers.ReadOnlyField()
    unlock_rate  = serializers.FloatField(read_only=True)
    publisher    = serializers.StringRelatedField(read_only=True)

    class Meta:
        model  = ContentLocker
        fields = ['id','name','locker_type','status','locker_key','destination_url',
                  'unlock_duration_hours','show_offer_count','title','description',
                  'theme','primary_color','total_impressions','total_unlocks',
                  'total_earnings','embed_code','unlock_rate','publisher','created_at']
        read_only_fields = ['locker_key','total_impressions','total_unlocks',
                            'total_earnings','created_at']


class OfferWallSerializer(serializers.ModelSerializer):
    api_url      = serializers.ReadOnlyField()
    embed_script = serializers.ReadOnlyField()
    publisher    = serializers.StringRelatedField(read_only=True)

    class Meta:
        model  = OfferWall
        fields = ['id','name','status','wall_key','currency_name','currency_icon_url',
                  'exchange_rate','min_payout_usd','title','description','theme',
                  'primary_color','android_app_id','postback_url','target_countries',
                  'target_devices','total_completions','total_earnings',
                  'api_url','embed_script','publisher','created_at']
        read_only_fields = ['wall_key','total_completions','total_earnings','created_at']


class UserVirtualBalanceSerializer(serializers.ModelSerializer):
    currency_name= serializers.CharField(source='offer_wall.currency_name', read_only=True)
    wall_name    = serializers.CharField(source='offer_wall.name', read_only=True)

    class Meta:
        model  = UserVirtualBalance
        fields = ['id','wall_name','currency_name','balance','total_earned','total_spent']


class VirtualRewardSerializer(serializers.ModelSerializer):
    currency_name= serializers.CharField(source='offer_wall.currency_name', read_only=True)

    class Meta:
        model  = VirtualReward
        fields = ['id','reward_type','amount','currency_name','usd_equivalent',
                  'description','created_at']
