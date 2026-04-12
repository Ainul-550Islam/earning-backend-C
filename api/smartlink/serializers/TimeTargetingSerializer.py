from rest_framework import serializers
from ..models import TimeTargeting


class TimeTargetingSerializer(serializers.ModelSerializer):
    class Meta:
        model = TimeTargeting
        fields = ['id', 'days_of_week', 'start_hour', 'end_hour', 'timezone_name', 'updated_at']
        read_only_fields = ['id', 'updated_at']

    def validate(self, data):
        start = data.get('start_hour', 0)
        end = data.get('end_hour', 23)
        if start >= end:
            raise serializers.ValidationError('start_hour must be less than end_hour.')
        return data
