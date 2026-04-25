# api/payment_gateways/integrations/serializers.py
from rest_framework import serializers
from .models import AdvertiserTrackerIntegration


class TrackerIntegrationSerializer(serializers.ModelSerializer):
    postback_template = serializers.SerializerMethodField()
    offer_name        = serializers.CharField(source='offer.name', read_only=True)
    advertiser_email  = serializers.EmailField(source='advertiser.email', read_only=True)

    class Meta:
        model  = AdvertiserTrackerIntegration
        fields = ['id','tracker','app_id','offer','offer_name','advertiser_email',
                  'is_active','postback_url','postback_template','created_at']
        read_only_fields = ['postback_url','created_at']

    def get_postback_template(self, obj):
        return obj.get_postback_url()


class CreateTrackerIntegrationSerializer(serializers.ModelSerializer):
    class Meta:
        model  = AdvertiserTrackerIntegration
        fields = ['tracker','app_id','dev_key','offer','is_active']

    def create(self, validated_data):
        validated_data['advertiser'] = self.context['request'].user
        return super().create(validated_data)


class TrackerSetupGuideSerializer(serializers.Serializer):
    tracker       = serializers.CharField()
    postback_url  = serializers.CharField()
    app_id        = serializers.CharField()
    instructions  = serializers.ListField(child=serializers.CharField())
