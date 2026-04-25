# api/payment_gateways/publisher/serializers.py
from rest_framework import serializers
from .models import PublisherProfile, AdvertiserProfile

class PublisherProfileSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    username   = serializers.CharField(source='user.username', read_only=True)
    class Meta:
        model  = PublisherProfile
        fields = ['id','user_email','username','website_url','traffic_types','monthly_traffic',
                  'primary_geos','primary_devices','postback_url','payment_email',
                  'preferred_payment','payment_currency','minimum_payout',
                  'status','is_fast_pay_eligible','quality_score','tier',
                  'lifetime_earnings','lifetime_clicks','lifetime_conversions']
        read_only_fields = ['status','is_fast_pay_eligible','quality_score','tier',
                            'lifetime_earnings','lifetime_clicks','lifetime_conversions']

class AdvertiserProfileSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    available_balance = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    class Meta:
        model  = AdvertiserProfile
        fields = ['id','user_email','company_name','website_url','status',
                  'balance','currency','total_spent','credit_limit','available_balance',
                  'default_postback_url','allowed_postback_ips','invoice_email']
        read_only_fields = ['balance','total_spent','status']
