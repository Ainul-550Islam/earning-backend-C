# api/payment_gateways/tracking/serializers.py
from rest_framework import serializers
from .models import Click, Conversion, PostbackLog, PublisherDailyStats

class ClickSerializer(serializers.ModelSerializer):
    publisher_email = serializers.EmailField(source='publisher.email', read_only=True, default=None)
    class Meta:
        model  = Click
        fields = ['id','click_id','offer','publisher_email','ip_address','country_code',
                  'device_type','os_name','is_converted','is_fraud','is_bot','is_duplicate',
                  'payout','sub1','sub2','traffic_id','created_at']
        read_only_fields = ['click_id','created_at']

class ConversionSerializer(serializers.ModelSerializer):
    publisher_email = serializers.EmailField(source='publisher.email', read_only=True, default=None)
    status_display  = serializers.CharField(source='get_status_display', read_only=True)
    class Meta:
        model  = Conversion
        fields = ['id','conversion_id','click_id_raw','offer','publisher_email','conversion_type',
                  'status','status_display','payout','cost','revenue','currency',
                  'country_code','device_type','publisher_paid','postback_received',
                  'approved_at','created_at']
        read_only_fields = ['conversion_id','revenue','created_at']

class PostbackLogSerializer(serializers.ModelSerializer):
    class Meta:
        model  = PostbackLog
        fields = ['id','offer','click_id','raw_url','ip_address','status',
                  'error_message','response_code','created_at']
        read_only_fields = '__all__'

class PublisherStatsSerializer(serializers.ModelSerializer):
    class Meta:
        model  = PublisherDailyStats
        fields = ['date','impressions','clicks','conversions','revenue','ctr','cr','epc']
