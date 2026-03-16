from rest_framework import serializers
from .models import (
    FraudRule, FraudAttempt, FraudPattern, 
    UserRiskProfile, DeviceFingerprint, 
    IPReputation, FraudAlert
)
from api.users.serializers import UserSerializer

class FraudRuleSerializer(serializers.ModelSerializer):
    """Serializer for FraudRule model"""
    rule_type_display = serializers.CharField(source='get_rule_type_display', read_only=True)
    severity_display = serializers.CharField(source='get_severity_display', read_only=True)
    
    class Meta:
        model = FraudRule
        fields = [
            'id', 'name', 'description', 'rule_type', 'rule_type_display',
            'severity', 'severity_display', 'condition', 'weight', 'threshold',
            'action_on_trigger', 'is_active', 'run_frequency',
            'last_triggered', 'trigger_count', 'false_positive_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['last_triggered', 'trigger_count', 'false_positive_count']

class FraudAttemptSerializer(serializers.ModelSerializer):
    """Serializer for FraudAttempt model"""
    user_details = UserSerializer(source='user', read_only=True)
    attempt_type_display = serializers.CharField(source='get_attempt_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    fraud_rules_details = FraudRuleSerializer(source='fraud_rules', many=True, read_only=True)
    
    class Meta:
        model = FraudAttempt
        fields = [
            'id', 'attempt_id', 'user', 'user_details', 'attempt_type', 'attempt_type_display',
            'description', 'detected_by', 'fraud_rules', 'fraud_rules_details',
            'evidence_data', 'metadata', 'fraud_score', 'confidence_score',
            'status', 'status_display', 'is_resolved', 'resolved_at',
            'resolved_by', 'resolution_notes', 'amount_involved',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['attempt_id', 'created_at', 'updated_at']

class FraudPatternSerializer(serializers.ModelSerializer):
    """Serializer for FraudPattern model"""
    pattern_type_display = serializers.CharField(source='get_pattern_type_display', read_only=True)
    
    class Meta:
        model = FraudPattern
        fields = [
            'id', 'name', 'pattern_type', 'pattern_type_display',
            'description', 'pattern_data', 'features',
            'occurrence_count', 'accuracy_rate', 'is_trained',
            'last_trained', 'model_version', 'created_at', 'updated_at'
        ]

class UserRiskProfileSerializer(serializers.ModelSerializer):
    """Serializer for UserRiskProfile model"""
    user_details = UserSerializer(source='user', read_only=True)
    monitoring_level_display = serializers.CharField(source='get_monitoring_level_display', read_only=True)
    
    class Meta:
        model = UserRiskProfile
        fields = [
            'id', 'user', 'user_details', 'overall_risk_score',
            'account_risk_score', 'payment_risk_score', 'behavior_risk_score',
            'risk_factors', 'warning_flags', 'total_fraud_attempts',
            'confirmed_fraud_attempts', 'false_positives', 'is_flagged',
            'is_restricted', 'restrictions', 'last_risk_assessment',
            'next_assessment_due', 'monitoring_level', 'monitoring_level_display',
            'created_at', 'updated_at'
        ]

class DeviceFingerprintSerializer(serializers.ModelSerializer):
    """Serializer for DeviceFingerprint model"""
    user_details = UserSerializer(source='user', read_only=True)
    
    class Meta:
        model = DeviceFingerprint
        fields = [
            'id', 'user', 'user_details', 'device_id', 'device_hash',
            'user_agent', 'platform', 'browser', 'browser_version',
            'os', 'os_version', 'screen_resolution', 'language',
            'timezone', 'cpu_cores', 'device_memory', 'max_touch_points',
            'canvas_fingerprint', 'webgl_fingerprint', 'audio_fingerprint',
            'ip_address', 'location_data', 'is_vpn', 'is_proxy',
            'is_tor', 'is_mobile', 'is_bot', 'trust_score',
            'last_seen', 'created_at'
        ]
        read_only_fields = ['device_hash', 'trust_score', 'last_seen']

class IPReputationSerializer(serializers.ModelSerializer):
    """Serializer for IPReputation model"""
    class Meta:
        model = IPReputation
        fields = [
            'id', 'ip_address', 'fraud_score', 'spam_score',
            'malware_score', 'total_requests', 'fraud_attempts',
            'unique_users', 'is_blacklisted', 'blacklist_reason',
            'blacklisted_at', 'country', 'region', 'city', 'isp',
            'threat_types', 'last_threat_check', 'created_at', 'updated_at'
        ]

class FraudAlertSerializer(serializers.ModelSerializer):
    """Serializer for FraudAlert model"""
    alert_type_display = serializers.CharField(source='get_alert_type_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    user_details = UserSerializer(source='user', read_only=True)
    fraud_attempt_details = FraudAttemptSerializer(source='fraud_attempt', read_only=True)
    
    class Meta:
        model = FraudAlert
        fields = [
            'id', 'alert_id', 'alert_type', 'alert_type_display', 'priority',
            'priority_display', 'title', 'description', 'user', 'user_details',
            'fraud_attempt', 'fraud_attempt_details', 'related_rules',
            'data', 'is_resolved', 'resolved_at', 'resolved_by',
            'resolution_notes', 'notification_sent', 'created_at', 'updated_at'
        ]
        read_only_fields = ['alert_id', 'notification_sent']

class FraudDetectionResponseSerializer(serializers.Serializer):
    """Serializer for fraud detection API responses"""
    is_fraud = serializers.BooleanField()
    fraud_score = serializers.IntegerField(min_value=0, max_value=100)
    confidence = serializers.IntegerField(min_value=0, max_value=100)
    reasons = serializers.ListField(child=serializers.CharField())
    warnings = serializers.ListField(child=serializers.CharField(), required=False)
    recommendations = serializers.ListField(child=serializers.CharField(), required=False)
    action_required = serializers.BooleanField(default=False)
    action_type = serializers.CharField(required=False)
    fraud_attempt_id = serializers.UUIDField(required=False)

class FraudStatisticsSerializer(serializers.Serializer):
    """Serializer for fraud statistics"""
    total_detections = serializers.IntegerField()
    confirmed_fraud = serializers.IntegerField()
    false_positives = serializers.IntegerField()
    detection_rate = serializers.FloatField()
    average_fraud_score = serializers.FloatField()
    top_fraud_types = serializers.DictField(child=serializers.IntegerField())
    risk_distribution = serializers.DictField(child=serializers.IntegerField())
    monthly_trend = serializers.ListField(child=serializers.DictField())