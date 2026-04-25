# api/payment_gateways/smartlink/serializers.py
from rest_framework import serializers
from decimal import Decimal
from .models import SmartLink, SmartLinkRotation


class SmartLinkRotationSerializer(serializers.ModelSerializer):
    offer_name  = serializers.CharField(source='offer.name', read_only=True)
    offer_payout= serializers.DecimalField(source='offer.publisher_payout',
                   max_digits=10, decimal_places=4, read_only=True)

    class Meta:
        model  = SmartLinkRotation
        fields = ['id','offer','offer_name','offer_payout','weight','is_control',
                  'clicks','conversions','earnings']
        read_only_fields = ['clicks','conversions','earnings']


class SmartLinkSerializer(serializers.ModelSerializer):
    url            = serializers.ReadOnlyField()
    publisher_email= serializers.EmailField(source='publisher.email', read_only=True)
    rotations      = SmartLinkRotationSerializer(many=True, read_only=True)
    epc_display    = serializers.SerializerMethodField()

    class Meta:
        model  = SmartLink
        fields = ['id','name','slug','url','status','rotation_mode',
                  'offer_types','categories','min_payout','manual_offers',
                  'target_countries','target_devices','fallback_url',
                  'total_clicks','total_conversions','total_earnings','epc',
                  'epc_display','publisher_email','rotations','created_at']
        read_only_fields = ['slug','total_clicks','total_conversions',
                            'total_earnings','epc','created_at']

    def get_epc_display(self, obj):
        return f'${float(obj.epc):.4f}'


class SmartLinkCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = SmartLink
        fields = ['name','rotation_mode','offer_types','categories','min_payout',
                  'manual_offers','target_countries','target_devices','fallback_url']

    def create(self, validated_data):
        validated_data['publisher'] = self.context['request'].user
        return super().create(validated_data)


class SmartLinkStatsSerializer(serializers.Serializer):
    total_clicks       = serializers.IntegerField()
    total_conversions  = serializers.IntegerField()
    total_earnings     = serializers.FloatField()
    epc                = serializers.FloatField()
    conversion_rate    = serializers.FloatField()
    url                = serializers.CharField()
    rotation_mode      = serializers.CharField()
