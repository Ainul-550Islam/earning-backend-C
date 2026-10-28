# api/admin_panel/serializers/DataExportSerializer.py
"""DataExport and ReportExport serializers."""
from rest_framework import serializers
from ..models.reports import DataExport, ReportExport


class DataExportSerializer(serializers.ModelSerializer):
    requested_by_username = serializers.CharField(source='requested_by.username', read_only=True, default='')
    file_size_human = serializers.CharField(read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    format_display = serializers.CharField(source='get_format_display', read_only=True)
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = DataExport
        fields = [
            'id', 'export_id', 'model_name', 'label',
            'filters', 'selected_fields', 'format', 'format_display',
            'status', 'status_display',
            'file_url', 'file_size_bytes', 'file_size_human',
            'row_count', 'error_message',
            'requested_by', 'requested_by_username',
            'task_id', 'expires_at', 'is_expired',
            'created_at', 'completed_at', 'download_url',
        ]
        read_only_fields = [
            'id', 'export_id', 'status', 'file_url', 'file_size_bytes',
            'file_size_human', 'row_count', 'error_message',
            'requested_by', 'task_id', 'expires_at', 'is_expired',
            'created_at', 'completed_at', 'download_url',
        ]

    def get_download_url(self, obj) -> str:
        if obj.status == 'ready' and not obj.is_expired:
            return f'/api/admin-panel/data-exports/{obj.pk}/download/'
        return ''


class DataExportRequestSerializer(serializers.Serializer):
    """Serializer for requesting a new data export."""
    model_name = serializers.CharField(max_length=100)
    format = serializers.ChoiceField(choices=['csv', 'xlsx', 'json'], default='csv')
    filters = serializers.DictField(required=False, default=dict)
    selected_fields = serializers.ListField(
        child=serializers.CharField(), required=False, default=list
    )
    label = serializers.CharField(max_length=200, required=False, default='')

    def validate_model_name(self, value):
        from django.apps import apps
        parts = value.split('.')
        if len(parts) != 2:
            raise serializers.ValidationError('model_name must be in format "app_label.ModelName".')
        try:
            apps.get_model(parts[0], parts[1])
        except LookupError:
            raise serializers.ValidationError(f'Model "{value}" not found.')
        return value


class ReportExportSerializer(serializers.ModelSerializer):
    report_name = serializers.CharField(source='report.name', read_only=True, default='')
    generated_by_username = serializers.CharField(source='generated_by.username', read_only=True, default='')
    file_size_human = serializers.CharField(read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    format_display = serializers.CharField(source='get_format_display', read_only=True)
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = ReportExport
        fields = [
            'id', 'export_id', 'report', 'report_name', 'title',
            'format', 'format_display', 'status', 'status_display',
            'row_count', 'file_size_bytes', 'file_size_human',
            'file_url', 'error_message',
            'applied_filters', 'generated_by', 'generated_by_username',
            'expires_at', 'is_expired', 'created_at', 'completed_at', 'download_url',
        ]
        read_only_fields = [
            'id', 'export_id', 'status', 'row_count', 'file_size_bytes',
            'file_url', 'error_message', 'generated_by',
            'expires_at', 'is_expired', 'created_at', 'completed_at',
        ]

    def get_download_url(self, obj) -> str:
        if obj.status == 'completed' and not obj.is_expired:
            return f'/api/admin-panel/reports/exports/{obj.export_id}/download/'
        return ''