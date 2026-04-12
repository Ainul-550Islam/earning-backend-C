"""
Reporting Serializers
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model

from ..models.reporting import (
    AlertReport, MTTRMetric, MTTDMetric, SLABreach
)

User = get_user_model()


class AlertReportSerializer(serializers.ModelSerializer):
    """AlertReport serializer"""
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    file_size_display = serializers.SerializerMethodField()
    
    class Meta:
        model = AlertReport
        fields = [
            'id', 'title', 'description', 'report_type', 'status', 'start_date',
            'end_date', 'content', 'summary', 'included_metrics', 'rule_filters',
            'severity_filters', 'status_filters', 'format_type', 'recipients',
            'auto_distribute', 'is_recurring', 'recurrence_pattern', 'next_run',
            'generated_at', 'generation_duration_ms', 'file_path', 'file_size_bytes',
            'error_message', 'retry_count', 'max_retries', 'created_by',
            'created_by_name', 'created_at', 'updated_at', 'file_size_display'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by', 'generated_at',
                          'generation_duration_ms', 'file_path', 'file_size_bytes',
                          'error_message', 'retry_count', 'next_run']
    
    def get_file_size_display(self, obj):
        if obj.file_size_bytes:
            if obj.file_size_bytes < 1024:
                return f"{obj.file_size_bytes} B"
            elif obj.file_size_bytes < 1024 * 1024:
                return f"{obj.file_size_bytes / 1024:.1f} KB"
            else:
                return f"{obj.file_size_bytes / (1024 * 1024):.1f} MB"
        return "N/A"
    
    def validate_report_type(self, value):
        valid_types = ['daily', 'weekly', 'monthly', 'quarterly', 'custom', 'sla', 'performance', 'trend']
        if value not in valid_types:
            raise serializers.ValidationError(f"Report type must be one of: {valid_types}")
        return value
    
    def validate_status(self, value):
        valid_statuses = ['pending', 'generating', 'completed', 'failed', 'scheduled']
        if value not in valid_statuses:
            raise serializers.ValidationError(f"Status must be one of: {valid_statuses}")
        return value
    
    def validate_format_type(self, value):
        valid_formats = ['json', 'pdf', 'csv', 'html']
        if value not in valid_formats:
            raise serializers.ValidationError(f"Format type must be one of: {valid_formats}")
        return value
    
    def validate_max_retries(self, value):
        if not 0 <= value <= 10:
            raise serializers.ValidationError("Max retries must be between 0 and 10")
        return value


class MTTRMetricSerializer(serializers.ModelSerializer):
    """MTTRMetric serializer"""
    mttr_by_severity_display = serializers.SerializerMethodField()
    mttr_by_rule_display = serializers.SerializerMethodField()
    
    class Meta:
        model = MTTRMetric
        fields = [
            'id', 'name', 'description', 'calculation_period_days', 'target_mttr_minutes',
            'current_mttr_minutes', 'mttr_by_severity', 'mttr_by_rule', 'mttr_trend_7_days',
            'mttr_trend_30_days', 'alerts_within_target', 'total_resolved_alerts',
            'target_compliance_percentage', 'last_calculated', 'created_at', 'updated_at',
            'mttr_by_severity_display', 'mttr_by_rule_display'
        ]
        read_only_fields = ['created_at', 'updated_at', 'current_mttr_minutes',
                          'alerts_within_target', 'total_resolved_alerts',
                          'target_compliance_percentage', 'last_calculated']
    
    def get_mttr_by_severity_display(self, obj):
        return obj.mttr_by_severity
    
    def get_mttr_by_rule_display(self, obj):
        return obj.mttr_by_rule
    
    def validate_calculation_period_days(self, value):
        if not 1 <= value <= 365:
            raise serializers.ValidationError("Calculation period must be between 1 and 365 days")
        return value
    
    def validate_target_mttr_minutes(self, value):
        if value < 1:
            raise serializers.ValidationError("Target MTTR must be positive")
        return value


class MTTDMetricSerializer(serializers.ModelSerializer):
    """MTTDMetric serializer"""
    mttd_by_severity_display = serializers.SerializerMethodField()
    mttd_by_rule_display = serializers.SerializerMethodField()
    
    class Meta:
        model = MTTDMetric
        fields = [
            'id', 'name', 'description', 'calculation_period_days', 'target_mttd_minutes',
            'current_mttd_minutes', 'mttd_by_severity', 'mttd_by_rule', 'mttd_trend_7_days',
            'mttd_trend_30_days', 'detection_rate', 'false_positive_rate',
            'target_compliance_percentage', 'last_calculated', 'created_at', 'updated_at',
            'mttd_by_severity_display', 'mttd_by_rule_display'
        ]
        read_only_fields = ['created_at', 'updated_at', 'current_mttd_minutes',
                          'detection_rate', 'false_positive_rate',
                          'target_compliance_percentage', 'last_calculated']
    
    def get_mttd_by_severity_display(self, obj):
        return obj.mttd_by_severity
    
    def get_mttd_by_rule_display(self, obj):
        return obj.mttd_by_rule
    
    def validate_calculation_period_days(self, value):
        if not 1 <= value <= 365:
            raise serializers.ValidationError("Calculation period must be between 1 and 365 days")
        return value
    
    def validate_target_mttd_minutes(self, value):
        if value < 1:
            raise serializers.ValidationError("Target MTTD must be positive")
        return value


class SLABreachSerializer(serializers.ModelSerializer):
    """SLABreach serializer"""
    alert_log_rule_name = serializers.CharField(source='alert_log.rule.name', read_only=True)
    acknowledged_by_name = serializers.CharField(source='acknowledged_by.get_full_name', read_only=True)
    resolved_by_name = serializers.CharField(source='resolved_by.get_full_name', read_only=True)
    breach_severity = serializers.SerializerMethodField()
    duration_minutes = serializers.SerializerMethodField()
    
    class Meta:
        model = SLABreach
        fields = [
            'id', 'name', 'sla_type', 'severity', 'status', 'alert_log',
            'alert_log_rule_name', 'breach_time', 'breach_duration_minutes',
            'breach_percentage', 'acknowledged_at', 'acknowledged_by',
            'acknowledged_by_name', 'resolved_at', 'resolved_by', 'resolved_by_name',
            'resolution_time_minutes', 'business_impact', 'financial_impact',
            'customer_impact', 'escalation_level', 'escalated_at', 'escalation_reason',
            'stakeholder_notified', 'communication_sent', 'root_cause',
            'preventive_actions', 'created_by', 'created_at', 'updated_at',
            'breach_severity', 'duration_minutes'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by', 'breach_time',
                          'acknowledged_at', 'acknowledged_by', 'resolved_at', 'resolved_by',
                          'escalated_at', 'escalation_level']
    
    def get_breach_severity(self, obj):
        return obj.get_breach_severity()
    
    def get_duration_minutes(self, obj):
        return obj.get_duration_minutes()
    
    def validate_sla_type(self, value):
        valid_types = ['resolution_time', 'response_time', 'detection_time', 'availability', 'custom']
        if value not in valid_types:
            raise serializers.ValidationError(f"SLA type must be one of: {valid_types}")
        return value
    
    def validate_severity(self, value):
        valid_severities = ['low', 'medium', 'high', 'critical']
        if value not in valid_severities:
            raise serializers.ValidationError(f"Severity must be one of: {valid_severities}")
        return value
    
    def validate_status(self, value):
        valid_statuses = ['active', 'resolved', 'escalated', 'acknowledged']
        if value not in valid_statuses:
            raise serializers.ValidationError(f"Status must be one of: {valid_statuses}")
        return value


# Simplified serializers for list views
class AlertReportListSerializer(serializers.ModelSerializer):
    """Simplified AlertReport serializer for list views"""
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    
    class Meta:
        model = AlertReport
        fields = [
            'id', 'title', 'report_type', 'status', 'format_type',
            'created_at', 'generated_at', 'created_by_name'
        ]


class MTTRMetricListSerializer(serializers.ModelSerializer):
    """Simplified MTTRMetric serializer for list views"""
    
    class Meta:
        model = MTTRMetric
        fields = [
            'id', 'name', 'calculation_period_days', 'target_mttr_minutes',
            'current_mttr_minutes', 'target_compliance_percentage', 'last_calculated'
        ]


class MTTDMetricListSerializer(serializers.ModelSerializer):
    """Simplified MTTDMetric serializer for list views"""
    
    class Meta:
        model = MTTDMetric
        fields = [
            'id', 'name', 'calculation_period_days', 'target_mttd_minutes',
            'current_mttd_minutes', 'detection_rate', 'false_positive_rate', 'last_calculated'
        ]


class SLABreachListSerializer(serializers.ModelSerializer):
    """Simplified SLABreach serializer for list views"""
    alert_log_rule_name = serializers.CharField(source='alert_log.rule.name', read_only=True)
    breach_severity = serializers.SerializerMethodField()
    
    class Meta:
        model = SLABreach
        fields = [
            'id', 'name', 'sla_type', 'severity', 'alert_log_rule_name',
            'breach_time', 'breach_percentage', 'status', 'escalation_level'
        ]
    
    def get_breach_severity(self, obj):
        return obj.get_breach_severity()


# Action serializers
class AlertReportGenerateSerializer(serializers.Serializer):
    """Serializer for generating reports (no additional fields needed)"""
    pass


class AlertReportExportSerializer(serializers.Serializer):
    """Serializer for exporting reports (no additional fields needed)"""
    pass


class AlertReportScheduleNextRunSerializer(serializers.Serializer):
    """Serializer for scheduling next run (no additional fields needed)"""
    pass


class AlertReportCreateDailySerializer(serializers.Serializer):
    """Serializer for creating daily reports"""
    format_type = serializers.CharField(max_length=10, default='json')
    auto_distribute = serializers.BooleanField(default=False)
    
    def validate_format_type(self, value):
        valid_formats = ['json', 'pdf', 'csv', 'html']
        if value not in valid_formats:
            raise serializers.ValidationError(f"Format type must be one of: {valid_formats}")
        return value


class AlertReportCreateWeeklySerializer(serializers.Serializer):
    """Serializer for creating weekly reports"""
    format_type = serializers.CharField(max_length=10, default='json')
    auto_distribute = serializers.BooleanField(default=False)
    
    def validate_format_type(self, value):
        valid_formats = ['json', 'pdf', 'csv', 'html']
        if value not in valid_formats:
            raise serializers.ValidationError(f"Format type must be one of: {valid_formats}")
        return value


class AlertReportCreateSLASerializer(serializers.Serializer):
    """Serializer for creating SLA reports"""
    days = serializers.IntegerField(default=30, min_value=1, max_value=365)
    format_type = serializers.CharField(max_length=10, default='json')
    auto_distribute = serializers.BooleanField(default=False)
    
    def validate_format_type(self, value):
        valid_formats = ['json', 'pdf', 'csv', 'html']
        if value not in valid_formats:
            raise serializers.ValidationError(f"Format type must be one of: {valid_formats}")
        return value


class MTTRMetricCalculateSerializer(serializers.Serializer):
    """Serializer for calculating MTTR (no additional fields needed)"""
    pass


class MTTRMetricTrendsSerializer(serializers.Serializer):
    """Serializer for getting MTTR trends (no additional fields needed)"""
    pass


class MTTDMetricCalculateSerializer(serializers.Serializer):
    """Serializer for calculating MTTD (no additional fields needed)"""
    pass


class MTTDMetricTrendsSerializer(serializers.Serializer):
    """Serializer for getting MTTD trends (no additional fields needed)"""
    pass


class SLABreachAcknowledgeSerializer(serializers.Serializer):
    """Serializer for acknowledging SLA breaches (no additional fields needed)"""
    pass


class SLABreachEscalateSerializer(serializers.Serializer):
    """Serializer for escalating SLA breaches"""
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True)


class SLABreachResolveSerializer(serializers.Serializer):
    """Serializer for resolving SLA breaches"""
    resolution_time_minutes = serializers.FloatField(required=False, allow_null=True)


class SLABreachBreachSeveritySerializer(serializers.Serializer):
    """Serializer for getting breach severity (no additional fields needed)"""
    pass


class ReportingDashboardOverviewSerializer(serializers.Serializer):
    """Serializer for dashboard overview (no additional fields needed)"""
    pass


class ReportingDashboardMetricsSummarySerializer(serializers.Serializer):
    """Serializer for metrics summary"""
    days = serializers.IntegerField(default=30, min_value=1, max_value=365)
