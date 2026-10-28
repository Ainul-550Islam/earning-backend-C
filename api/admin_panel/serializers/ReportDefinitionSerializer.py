# api/admin_panel/serializers/ReportDefinitionSerializer.py
"""ReportDefinition serializer."""
from rest_framework import serializers
from ..models.reports import ReportDefinition


class ReportDefinitionSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source='created_by.username', read_only=True, default='')
    report_type_display = serializers.CharField(source='get_report_type_display', read_only=True)

    class Meta:
        model = ReportDefinition
        fields = [
            'id', 'name', 'report_type', 'report_type_display',
            'description', 'query_config', 'columns', 'filters',
            'allowed_formats', 'is_active', 'is_system',
            'created_by', 'created_by_username',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_by', 'is_system', 'created_at', 'updated_at']

    def validate_allowed_formats(self, value):
        allowed = {'csv', 'xlsx', 'pdf', 'json'}
        for fmt in value:
            if fmt not in allowed:
                raise serializers.ValidationError(f'Invalid format "{fmt}". Allowed: {", ".join(allowed)}')
        return value

    def validate(self, data):
        is_system = getattr(self.instance, 'is_system', False)
        if is_system and self.instance:
            raise serializers.ValidationError('System report definitions cannot be modified.')
        return data