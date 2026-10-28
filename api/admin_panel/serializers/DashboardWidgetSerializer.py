# api/admin_panel/serializers/DashboardWidgetSerializer.py
"""DashboardWidget serializer."""
from rest_framework import serializers
from ..models.dashboard import DashboardWidget, DashboardLayout, DashboardAlert, QuickAction


class DashboardWidgetSerializer(serializers.ModelSerializer):
    widget_type_display = serializers.CharField(source='get_widget_type_display', read_only=True)
    size_display = serializers.CharField(source='get_size_display', read_only=True)

    class Meta:
        model = DashboardWidget
        fields = [
            'id', 'user', 'title', 'widget_type', 'widget_type_display',
            'config', 'position', 'size', 'size_display',
            'is_visible', 'refresh_interval', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']

    def validate_position(self, value):
        if value:
            required = {'x', 'y', 'w', 'h'}
            missing = required - set(value.keys())
            if missing:
                raise serializers.ValidationError(f'Position must include: {", ".join(missing)}')
            for k in required:
                if not isinstance(value.get(k), int):
                    raise serializers.ValidationError(f'Position.{k} must be an integer.')
        return value

    def validate_refresh_interval(self, value):
        if value < 0:
            raise serializers.ValidationError('refresh_interval cannot be negative.')
        return value


class DashboardLayoutSerializer(serializers.ModelSerializer):
    class Meta:
        model = DashboardLayout
        fields = ['id', 'user', 'name', 'layout', 'is_default', 'created_at', 'updated_at']
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']


class DashboardAlertSerializer(serializers.ModelSerializer):
    metric_key = serializers.CharField(source='metric.metric_key', read_only=True)
    metric_value = serializers.DecimalField(
        source='metric.value', max_digits=20, decimal_places=4, read_only=True
    )
    operator_display = serializers.CharField(source='get_operator_display', read_only=True)
    is_triggered = serializers.SerializerMethodField()

    class Meta:
        model = DashboardAlert
        fields = [
            'id', 'metric', 'metric_key', 'metric_value',
            'label', 'threshold', 'operator', 'operator_display',
            'is_active', 'notify_admins',
            'last_triggered', 'trigger_count',
            'created_at', 'updated_at', 'is_triggered',
        ]
        read_only_fields = ['id', 'last_triggered', 'trigger_count', 'created_at', 'updated_at']

    def get_is_triggered(self, obj) -> bool:
        try:
            return obj.check_condition(obj.metric.value)
        except Exception:
            return False


class QuickActionSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuickAction
        fields = [
            'id', 'label', 'description', 'icon', 'url',
            'permission_required', 'sort_order', 'is_active',
            'open_in_new_tab', 'color', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']