# api/payment_gateways/blacklist/serializers.py
from rest_framework import serializers
from .models import TrafficBlacklist, OfferQualityScore


class TrafficBlacklistSerializer(serializers.ModelSerializer):
    owner_email    = serializers.EmailField(source='owner.email', read_only=True)
    offer_name     = serializers.CharField(source='offer.name', read_only=True, default=None)
    block_type_display = serializers.CharField(source='get_block_type_display', read_only=True)

    class Meta:
        model  = TrafficBlacklist
        fields = ['id','block_type','block_type_display','value','reason',
                  'created_by_type','is_active','expires_at','block_count',
                  'offer','offer_name','owner_email','created_at']
        read_only_fields = ['block_count','created_at']


class CreateBlacklistRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model  = TrafficBlacklist
        fields = ['block_type','value','reason','expires_at','offer']

    def validate_block_type(self, value):
        allowed = [t[0] for t in TrafficBlacklist.BLOCK_TYPES]
        if value not in allowed:
            raise serializers.ValidationError(f'Invalid block_type. Choices: {allowed}')
        return value

    def create(self, validated_data):
        validated_data['owner'] = self.context['request'].user
        validated_data['created_by_type'] = 'advertiser'
        return super().create(validated_data)


class OfferQualityScoreSerializer(serializers.ModelSerializer):
    publisher_email = serializers.EmailField(source='publisher.email', read_only=True)
    offer_name      = serializers.CharField(source='offer.name', read_only=True)
    quality_label   = serializers.SerializerMethodField()

    class Meta:
        model  = OfferQualityScore
        fields = ['id','publisher_email','offer_name','total_clicks',
                  'total_conversions','total_reversals','conversion_rate',
                  'reversal_rate','fraud_rate','quality_score','quality_label',
                  'is_blacklisted','blacklisted_at','last_updated']

    def get_quality_label(self, obj):
        s = obj.quality_score
        if s >= 80: return 'Excellent'
        if s >= 60: return 'Good'
        if s >= 40: return 'Average'
        if s >= 20: return 'Poor'
        return 'Very Poor'
