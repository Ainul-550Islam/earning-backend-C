# api/admin_panel/serializers/ReportScheduleSerializer.py
"""ReportSchedule serializer."""
from rest_framework import serializers
from ..models.reports import ReportSchedule


class ReportScheduleSerializer(serializers.ModelSerializer):
    report_name = serializers.CharField(source='report.name', read_only=True)
    created_by_username = serializers.CharField(source='created_by.username', read_only=True, default='')
    format_display = serializers.CharField(source='get_format_display', read_only=True)

    class Meta:
        model = ReportSchedule
        fields = [
            'id', 'report', 'report_name', 'name', 'cron_expr',
            'recipients', 'format', 'format_display',
            'extra_filters', 'is_active',
            'last_run_at', 'next_run_at',
            'run_count', 'failure_count',
            'created_by', 'created_by_username',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'created_by', 'last_run_at', 'next_run_at',
            'run_count', 'failure_count', 'created_at', 'updated_at',
        ]

    def validate_cron_expr(self, value):
        parts = value.strip().split()
        if len(parts) != 5:
            raise serializers.ValidationError(
                'Cron expression must have exactly 5 parts: minute hour day month weekday.'
            )
        return value

    def validate_recipients(self, value):
        if not isinstance(value, list) or not value:
            raise serializers.ValidationError('At least one recipient email is required.')
        import re
        email_re = re.compile(r'^[^@]+@[^@]+\.[^@]+$')
        for email in value:
            if not email_re.match(email):
                raise serializers.ValidationError(f'Invalid email: {email}')
        return value