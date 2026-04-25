# FILE 83 of 257 — fraud/serializers.py
from rest_framework import serializers
from .models import FraudAlert, BlockedIP, RiskRule

class FraudAlertSerializer(serializers.ModelSerializer):
    user_email   = serializers.EmailField(source='user.email', read_only=True)
    risk_level_display = serializers.CharField(source='get_risk_level_display', read_only=True)
    action_display     = serializers.CharField(source='get_action_display',     read_only=True)
    class Meta:
        model  = FraudAlert
        fields = ['id','gateway','user_email','amount','ip_address','risk_score',
                  'risk_level','risk_level_display','action','action_display',
                  'reasons','resolved','notes','created_at']
        read_only_fields = ['id','created_at']

class BlockedIPSerializer(serializers.ModelSerializer):
    blocked_by_email = serializers.EmailField(source='blocked_by.email', read_only=True, default=None)
    class Meta:
        model  = BlockedIP
        fields = ['id','ip_address','reason','is_active','blocked_by_email','expires_at','created_at']
        read_only_fields = ['created_at']

class RiskRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model  = RiskRule
        fields = '__all__'
        read_only_fields = ['created_at','updated_at']
