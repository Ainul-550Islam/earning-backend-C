from rest_framework import serializers
from ..models import TargetingRule, GeoTargeting, DeviceTargeting, OSTargeting, TimeTargeting, ISPTargeting, LanguageTargeting


class GeoTargetingInlineSerializer(serializers.ModelSerializer):
    class Meta:
        model = GeoTargeting
        fields = ['id', 'mode', 'countries', 'regions', 'cities']


class DeviceTargetingInlineSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceTargeting
        fields = ['id', 'mode', 'device_types']


class OSTargetingInlineSerializer(serializers.ModelSerializer):
    class Meta:
        model = OSTargeting
        fields = ['id', 'mode', 'os_types']


class TimeTargetingInlineSerializer(serializers.ModelSerializer):
    class Meta:
        model = TimeTargeting
        fields = ['id', 'days_of_week', 'start_hour', 'end_hour', 'timezone_name']


class ISPTargetingInlineSerializer(serializers.ModelSerializer):
    class Meta:
        model = ISPTargeting
        fields = ['id', 'mode', 'isps', 'asns']


class LanguageTargetingInlineSerializer(serializers.ModelSerializer):
    class Meta:
        model = LanguageTargeting
        fields = ['id', 'mode', 'languages']


class TargetingRuleSerializer(serializers.ModelSerializer):
    geo_targeting = GeoTargetingInlineSerializer(read_only=True)
    device_targeting = DeviceTargetingInlineSerializer(read_only=True)
    os_targeting = OSTargetingInlineSerializer(read_only=True)
    time_targeting = TimeTargetingInlineSerializer(read_only=True)
    isp_targeting = ISPTargetingInlineSerializer(read_only=True)
    language_targeting = LanguageTargetingInlineSerializer(read_only=True)

    class Meta:
        model = TargetingRule
        fields = [
            'id', 'logic', 'is_active', 'priority',
            'geo_targeting', 'device_targeting', 'os_targeting',
            'time_targeting', 'isp_targeting', 'language_targeting',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
