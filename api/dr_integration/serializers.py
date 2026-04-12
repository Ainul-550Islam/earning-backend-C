"""
DR Integration Serializers — DRF serializers for DR models.
"""
from rest_framework import serializers
from .models import DRBackupRecord, DRRestoreRecord, DRFailoverEvent, DRAlert, DRDrillRecord, DRSystemStatus


class DRSystemStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = DRSystemStatus
        fields = ['overall_health', 'last_backup_at', 'last_failover_at',
                  'replication_lag_seconds', 'active_incidents', 'active_alerts',
                  'rto_achieved_seconds', 'rpo_achieved_seconds', 'synced_at']
        read_only_fields = fields


class DRBackupRecordSerializer(serializers.ModelSerializer):
    duration_seconds = serializers.ReadOnlyField()
    size_mb = serializers.ReadOnlyField()
    triggered_by_name = serializers.SerializerMethodField()

    class Meta:
        model = DRBackupRecord
        fields = ['id', 'dr_job_id', 'backup_type', 'status', 'size_mb',
                  'duration_seconds', 'is_verified', 'encryption_enabled',
                  'compression_enabled', 'error_message', 'started_at',
                  'completed_at', 'created_at', 'triggered_by_name']
        read_only_fields = ['id', 'dr_job_id', 'created_at', 'duration_seconds']

    def get_triggered_by_name(self, obj):
        return str(obj.triggered_by) if obj.triggered_by else None


class DRRestoreRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = DRRestoreRecord
        fields = ['id', 'restore_type', 'status', 'target_database', 'point_in_time',
                  'approval_status', 'error_message', 'started_at', 'completed_at',
                  'created_at', 'notes']
        read_only_fields = ['id', 'created_at']


class DRRestoreRequestSerializer(serializers.Serializer):
    """Input serializer for restore requests."""
    restore_type = serializers.ChoiceField(choices=['full', 'partial', 'table', 'point_in_time'])
    backup_id = serializers.CharField(required=False, allow_blank=True)
    target_database = serializers.CharField(default='default')
    point_in_time = serializers.DateTimeField(required=False, allow_null=True)
    require_approval = serializers.BooleanField(default=True)


class DRFailoverEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = DRFailoverEvent
        fields = ['id', 'failover_type', 'status', 'primary_node', 'secondary_node',
                  'trigger_reason', 'rto_achieved_seconds', 'is_drill',
                  'initiated_at', 'completed_at', 'notes']
        read_only_fields = ['id', 'initiated_at']


class DRAlertSerializer(serializers.ModelSerializer):
    acknowledged_by_name = serializers.SerializerMethodField()

    class Meta:
        model = DRAlert
        fields = ['id', 'rule_name', 'severity', 'message', 'metric',
                  'metric_value', 'threshold', 'is_acknowledged', 'acknowledged_by_name',
                  'acknowledged_at', 'fired_at', 'resolved_at']
        read_only_fields = ['id', 'fired_at']

    def get_acknowledged_by_name(self, obj):
        return str(obj.acknowledged_by) if obj.acknowledged_by else None


class DRDrillRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = DRDrillRecord
        fields = ['id', 'name', 'scenario_type', 'status', 'passed',
                  'scheduled_at', 'achieved_rto_seconds', 'target_rto_seconds',
                  'achieved_rpo_seconds', 'target_rpo_seconds', 'lessons_learned']
        read_only_fields = ['id']
