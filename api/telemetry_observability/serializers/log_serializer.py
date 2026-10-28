"""
Log Entry serializer. DRY: inherits BaseSerializer.
"""
from rest_framework import serializers

from ..models.log_entry import LogEntry
from ..choices import LogLevelChoices
from .base_serializer import BaseSerializer


class LogEntrySerializer(BaseSerializer):
    class Meta:
        model  = LogEntry
        fields = [
            'id', 'level', 'message', 'logger_name',
            'source', 'service', 'environment', 'timestamp',
            'stack_trace', 'context', 'tags',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'timestamp', 'created_at', 'updated_at']

    def validate_level(self, value):
        if value not in LogLevelChoices.values:
            raise serializers.ValidationError(
                f"Invalid level. Must be one of: {LogLevelChoices.values}."
            )
        return value

    def validate_message(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Log message cannot be empty.")
        return value


class LogEntryCreateSerializer(BaseSerializer):
    class Meta:
        model  = LogEntry
        fields = ['level', 'message', 'logger_name',
                  'source', 'service', 'environment',
                  'stack_trace', 'context', 'tags']

    def validate_level(self, value):
        if value not in LogLevelChoices.values:
            raise serializers.ValidationError(
                f"Invalid level. Must be one of: {LogLevelChoices.values}."
            )
        return value

    def validate_message(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Log message cannot be empty.")
        return value


class LogBatchCreateSerializer(serializers.Serializer):
    logs = LogEntryCreateSerializer(many=True)

    def validate_logs(self, value):
        if not value:
            raise serializers.ValidationError("At least one log entry must be provided.")
        return value
