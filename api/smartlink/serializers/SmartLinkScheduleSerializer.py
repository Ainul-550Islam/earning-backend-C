from rest_framework import serializers
from django.utils import timezone
from api.smartlink.models.extensions.smartlink_schedule import SmartLinkSchedule


class SmartLinkScheduleSerializer(serializers.ModelSerializer):
    """
    Full serializer for SmartLinkSchedule.
    Controls automatic activation/deactivation of a SmartLink on a schedule.
    """
    smartlink_slug = serializers.CharField(source='smartlink.slug', read_only=True)
    is_currently_active = serializers.SerializerMethodField()
    next_event = serializers.SerializerMethodField()
    time_until_next_event_seconds = serializers.SerializerMethodField()

    class Meta:
        model = SmartLinkSchedule
        fields = [
            'id',
            'smartlink',
            'smartlink_slug',
            'is_enabled',
            'schedule_type',
            'activate_at',
            'deactivate_at',
            'daily_start_hour',
            'daily_end_hour',
            'max_total_clicks',
            'max_total_revenue',
            'last_activated_at',
            'last_deactivated_at',
            'activation_count',
            'is_currently_active',
            'next_event',
            'time_until_next_event_seconds',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'smartlink_slug',
            'last_activated_at',
            'last_deactivated_at',
            'activation_count',
            'is_currently_active',
            'next_event',
            'time_until_next_event_seconds',
            'created_at',
            'updated_at',
        ]

    def get_is_currently_active(self, obj):
        try:
            return obj.should_be_active()
        except Exception:
            return None

    def get_next_event(self, obj):
        """Return the label of the next scheduled event."""
        now = timezone.now()
        if obj.schedule_type == 'once':
            if obj.activate_at and now < obj.activate_at:
                return 'activation'
            if obj.deactivate_at and now < obj.deactivate_at:
                return 'deactivation'
        elif obj.schedule_type == 'daily':
            if obj.daily_start_hour is not None:
                return 'daily_activation' if now.hour < obj.daily_start_hour else 'daily_deactivation'
        return None

    def get_time_until_next_event_seconds(self, obj):
        """Seconds until next schedule event fires."""
        now = timezone.now()
        if obj.schedule_type == 'once':
            if obj.activate_at and now < obj.activate_at:
                return int((obj.activate_at - now).total_seconds())
            if obj.deactivate_at and now < obj.deactivate_at:
                return int((obj.deactivate_at - now).total_seconds())
        return None

    def validate(self, attrs):
        schedule_type = attrs.get('schedule_type', getattr(self.instance, 'schedule_type', 'once'))

        if schedule_type == 'once':
            activate_at = attrs.get('activate_at', getattr(self.instance, 'activate_at', None))
            deactivate_at = attrs.get('deactivate_at', getattr(self.instance, 'deactivate_at', None))
            if activate_at and deactivate_at and activate_at >= deactivate_at:
                raise serializers.ValidationError(
                    'activate_at must be before deactivate_at.'
                )

        if schedule_type == 'daily':
            start = attrs.get('daily_start_hour', getattr(self.instance, 'daily_start_hour', None))
            end = attrs.get('daily_end_hour', getattr(self.instance, 'daily_end_hour', None))
            if start is not None and end is not None:
                if not (0 <= start <= 23) or not (0 <= end <= 23):
                    raise serializers.ValidationError(
                        'daily_start_hour and daily_end_hour must be between 0 and 23.'
                    )
                if start >= end:
                    raise serializers.ValidationError(
                        'daily_start_hour must be less than daily_end_hour.'
                    )

        return attrs

    def validate_max_total_clicks(self, value):
        if value is not None and value <= 0:
            raise serializers.ValidationError(
                'max_total_clicks must be a positive integer.'
            )
        return value

    def validate_max_total_revenue(self, value):
        if value is not None and value <= 0:
            raise serializers.ValidationError(
                'max_total_revenue must be a positive value.'
            )
        return value


class SmartLinkScheduleListSerializer(serializers.ModelSerializer):
    """Compact schedule list serializer for the SmartLink detail page."""
    smartlink_slug = serializers.CharField(source='smartlink.slug', read_only=True)
    is_currently_active = serializers.SerializerMethodField()

    class Meta:
        model = SmartLinkSchedule
        fields = [
            'id', 'smartlink_slug', 'is_enabled',
            'schedule_type', 'activate_at', 'deactivate_at',
            'activation_count', 'is_currently_active',
        ]
        read_only_fields = fields

    def get_is_currently_active(self, obj):
        try:
            return obj.should_be_active()
        except Exception:
            return None
