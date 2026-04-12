from rest_framework import serializers
from .models import (
    IPIntelligence, VPNDetectionLog, ProxyDetectionLog, TorExitNode,
    DatacenterIPRange, FraudAttempt, ClickFraudRecord, DeviceFingerprint,
    MultiAccountLink, VelocityMetric, IPBlacklist, IPWhitelist,
    ThreatFeedProvider, MaliciousIPDatabase, UserRiskProfile,
    RiskScoreHistory, MLModelMetadata, AnomalyDetectionLog,
    FraudRule, AlertConfiguration, IntegrationCredential,
    APIRequestLog, PerformanceMetric, SystemAuditTrail
)


class IPIntelligenceSerializer(serializers.ModelSerializer):
    risk_level_display = serializers.CharField(source='get_risk_level_display', read_only=True)

    class Meta:
        model = IPIntelligence
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class IPIntelligenceSummarySerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views."""
    class Meta:
        model = IPIntelligence
        fields = [
            'id', 'ip_address', 'country_code', 'risk_score', 'risk_level',
            'is_vpn', 'is_proxy', 'is_tor', 'is_datacenter', 'last_checked'
        ]


class VPNDetectionLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = VPNDetectionLog
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class ProxyDetectionLogSerializer(serializers.ModelSerializer):
    proxy_type_display = serializers.CharField(source='get_proxy_type_display', read_only=True)

    class Meta:
        model = ProxyDetectionLog
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class TorExitNodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = TorExitNode
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class DatacenterIPRangeSerializer(serializers.ModelSerializer):
    class Meta:
        model = DatacenterIPRange
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class FraudAttemptSerializer(serializers.ModelSerializer):
    fraud_type_display = serializers.CharField(source='get_fraud_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = FraudAttempt
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class ClickFraudRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClickFraudRecord
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class DeviceFingerprintSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceFingerprint
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class MultiAccountLinkSerializer(serializers.ModelSerializer):
    primary_user_email = serializers.EmailField(source='primary_user.email', read_only=True)
    linked_user_email = serializers.EmailField(source='linked_user.email', read_only=True)

    class Meta:
        model = MultiAccountLink
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class VelocityMetricSerializer(serializers.ModelSerializer):
    class Meta:
        model = VelocityMetric
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class IPBlacklistSerializer(serializers.ModelSerializer):
    reason_display = serializers.CharField(source='get_reason_display', read_only=True)
    is_expired = serializers.BooleanField(read_only=True)

    class Meta:
        model = IPBlacklist
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class IPWhitelistSerializer(serializers.ModelSerializer):
    class Meta:
        model = IPWhitelist
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class ThreatFeedProviderSerializer(serializers.ModelSerializer):
    class Meta:
        model = ThreatFeedProvider
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'used_today', 'total_entries']


class MaliciousIPDatabaseSerializer(serializers.ModelSerializer):
    threat_type_display = serializers.CharField(source='get_threat_type_display', read_only=True)
    feed_name = serializers.CharField(source='threat_feed.display_name', read_only=True)

    class Meta:
        model = MaliciousIPDatabase
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class UserRiskProfileSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    risk_level_display = serializers.CharField(source='get_risk_level_display', read_only=True)

    class Meta:
        model = UserRiskProfile
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class RiskScoreHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = RiskScoreHistory
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'score_delta']


class MLModelMetadataSerializer(serializers.ModelSerializer):
    class Meta:
        model = MLModelMetadata
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class AnomalyDetectionLogSerializer(serializers.ModelSerializer):
    anomaly_type_display = serializers.CharField(source='get_anomaly_type_display', read_only=True)

    class Meta:
        model = AnomalyDetectionLog
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class FraudRuleSerializer(serializers.ModelSerializer):
    condition_type_display = serializers.CharField(source='get_condition_type_display', read_only=True)
    action_display = serializers.CharField(source='get_action_display', read_only=True)

    class Meta:
        model = FraudRule
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'trigger_count', 'last_triggered']


class AlertConfigurationSerializer(serializers.ModelSerializer):
    class Meta:
        model = AlertConfiguration
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'last_sent']


class IntegrationCredentialSerializer(serializers.ModelSerializer):
    """Masks the API key in responses."""
    api_key = serializers.SerializerMethodField()

    class Meta:
        model = IntegrationCredential
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'used_today']

    def get_api_key(self, obj):
        # Mask the API key: show first 4 chars + asterisks
        if obj.api_key:
            return obj.api_key[:4] + '****' + obj.api_key[-4:]
        return None


class IntegrationCredentialWriteSerializer(serializers.ModelSerializer):
    """Allows writing the full API key."""
    class Meta:
        model = IntegrationCredential
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'used_today']


class APIRequestLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = APIRequestLog
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class PerformanceMetricSerializer(serializers.ModelSerializer):
    class Meta:
        model = PerformanceMetric
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class SystemAuditTrailSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    action_display = serializers.CharField(source='get_action_display', read_only=True)

    class Meta:
        model = SystemAuditTrail
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


# ---- Special request/response serializers ----

class IPCheckRequestSerializer(serializers.Serializer):
    ip_address = serializers.IPAddressField()
    include_geo = serializers.BooleanField(default=True)
    include_threat_feeds = serializers.BooleanField(default=False)
    user_id = serializers.IntegerField(required=False)


class IPCheckResponseSerializer(serializers.Serializer):
    ip_address = serializers.IPAddressField()
    risk_score = serializers.IntegerField()
    risk_level = serializers.CharField()
    is_vpn = serializers.BooleanField()
    is_proxy = serializers.BooleanField()
    is_tor = serializers.BooleanField()
    is_datacenter = serializers.BooleanField()
    is_blacklisted = serializers.BooleanField()
    is_whitelisted = serializers.BooleanField()
    country_code = serializers.CharField(allow_blank=True)
    isp = serializers.CharField(allow_blank=True)
    recommended_action = serializers.CharField()
    details = serializers.DictField()


class BulkIPCheckSerializer(serializers.Serializer):
    ip_addresses = serializers.ListField(
        child=serializers.IPAddressField(),
        max_length=100
    )
