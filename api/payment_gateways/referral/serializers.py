# api/payment_gateways/referral/serializers.py
from rest_framework import serializers
from .models import ReferralLink, Referral, ReferralCommission, ReferralProgram

class ReferralLinkSerializer(serializers.ModelSerializer):
    full_url = serializers.ReadOnlyField()
    class Meta:
        model  = ReferralLink
        fields = ['id','code','full_url','total_clicks','total_signups','total_earned','is_active']
        read_only_fields = ['code','total_clicks','total_signups','total_earned']

class ReferralSerializer(serializers.ModelSerializer):
    referred_email  = serializers.EmailField(source='referred_user.email', read_only=True)
    days_remaining  = serializers.SerializerMethodField()
    class Meta:
        model  = Referral
        fields = ['id','referred_email','is_active','commission_start','commission_end',
                  'total_commission_paid','days_remaining']
    def get_days_remaining(self, obj):
        from django.utils import timezone
        if obj.commission_end:
            delta = (obj.commission_end - timezone.now().date()).days
            return max(0, delta)
        return 0

class ReferralCommissionSerializer(serializers.ModelSerializer):
    referred_email = serializers.EmailField(source='referred_user.email', read_only=True)
    class Meta:
        model  = ReferralCommission
        fields = ['id','referred_email','original_amount','commission_amount',
                  'commission_percent','status','paid_at','transaction_ref','created_at']

class ReferralStatsSerializer(serializers.Serializer):
    referral_code       = serializers.CharField()
    referral_url        = serializers.URLField()
    total_clicks        = serializers.IntegerField()
    total_signups       = serializers.IntegerField()
    active_referrals    = serializers.IntegerField()
    total_referrals     = serializers.IntegerField()
    total_earned        = serializers.FloatField()
    pending_commission  = serializers.FloatField()

class ReferralProgramSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ReferralProgram
        fields = ['commission_percent','commission_months','minimum_payout',
                  'cookie_duration_days','description','is_active']
