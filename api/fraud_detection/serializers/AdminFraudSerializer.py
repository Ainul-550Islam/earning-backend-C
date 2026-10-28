# =============================================================================
# fraud_detection/serializers/AdminFraudSerializer.py
#
# Admin-only serializers with full field exposure + write capability.
# Never expose these to regular-user endpoints.
# =============================================================================
from __future__ import annotations

from rest_framework import serializers

from api.fraud_detection.models import (
    ChargebackDispute,
    ConversionCap,
    DeviceFingerprint,
    FraudAlert,
    FraudAttempt,
    FraudCase,
    FraudCaseAction,
    FraudCaseEvidence,
    FraudNotification,
    FraudPattern,
    FraudRule,
    FraudSettings,
    FraudWhitelist,
    IPReputation,
    OfferCompletion,
    UserRiskProfile,
)


class AdminFraudRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model   = FraudRule
        fields  = '__all__'


class AdminFraudAttemptSerializer(serializers.ModelSerializer):
    user_display     = serializers.SerializerMethodField()
    resolved_by_name = serializers.SerializerMethodField()

    class Meta:
        model   = FraudAttempt
        fields  = '__all__'

    def get_user_display(self, obj):
        return str(obj.user) if obj.user_id else None

    def get_resolved_by_name(self, obj):
        return str(obj.resolved_by) if obj.resolved_by_id else None


class AdminUserRiskProfileSerializer(serializers.ModelSerializer):
    username = serializers.SerializerMethodField()

    class Meta:
        model   = UserRiskProfile
        fields  = '__all__'

    def get_username(self, obj):
        return obj.user.username if obj.user_id else None


class AdminFraudAlertSerializer(serializers.ModelSerializer):
    class Meta:
        model   = FraudAlert
        fields  = '__all__'


class AdminFraudCaseSerializer(serializers.ModelSerializer):
    class Meta:
        model   = FraudCase
        fields  = '__all__'


class AdminFraudCaseActionSerializer(serializers.ModelSerializer):
    class Meta:
        model   = FraudCaseAction
        fields  = '__all__'


class AdminFraudCaseEvidenceSerializer(serializers.ModelSerializer):
    class Meta:
        model   = FraudCaseEvidence
        fields  = '__all__'


class AdminFraudWhitelistSerializer(serializers.ModelSerializer):
    is_expired = serializers.ReadOnlyField()

    class Meta:
        model   = FraudWhitelist
        fields  = '__all__'


class AdminDeviceFingerprintSerializer(serializers.ModelSerializer):
    class Meta:
        model   = DeviceFingerprint
        fields  = '__all__'


class AdminIPReputationSerializer(serializers.ModelSerializer):
    class Meta:
        model   = IPReputation
        fields  = '__all__'


class AdminFraudPatternSerializer(serializers.ModelSerializer):
    class Meta:
        model   = FraudPattern
        fields  = '__all__'


class AdminOfferCompletionSerializer(serializers.ModelSerializer):
    class Meta:
        model   = OfferCompletion
        fields  = '__all__'


class AdminFraudNotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model   = FraudNotification
        fields  = '__all__'


class AdminFraudSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model   = FraudSettings
        fields  = '__all__'


class AdminChargebackDisputeSerializer(serializers.ModelSerializer):
    class Meta:
        model   = ChargebackDispute
        fields  = '__all__'


class AdminConversionCapSerializer(serializers.ModelSerializer):
    is_exceeded = serializers.ReadOnlyField()

    class Meta:
        model   = ConversionCap
        fields  = '__all__'


# ---------------------------------------------------------------------------
# Admin Dashboard aggregate serializers
# ---------------------------------------------------------------------------

class AdminDashboardStatsSerializer(serializers.Serializer):
    total_attempts       = serializers.IntegerField()
    pending_review       = serializers.IntegerField()
    confirmed_fraud      = serializers.IntegerField()
    dismissed            = serializers.IntegerField()
    high_risk_users      = serializers.IntegerField()
    flagged_users        = serializers.IntegerField()
    active_rules         = serializers.IntegerField()
    unresolved_alerts    = serializers.IntegerField()
    open_cases           = serializers.IntegerField()
    chargebacks_received = serializers.IntegerField()
    generated_at         = serializers.DateTimeField()


class AdminBulkActionSerializer(serializers.Serializer):
    ids     = serializers.ListField(child=serializers.IntegerField(), min_length=1, max_length=500)
    action  = serializers.CharField()
    params  = serializers.DictField(required=False, default=dict)


class AdminUserRiskOverrideSerializer(serializers.Serializer):
    user_id           = serializers.IntegerField()
    overall_risk_score = serializers.IntegerField(min_value=0, max_value=100)
    reason            = serializers.CharField()
    monitoring_level  = serializers.CharField(required=False)


# ---------------------------------------------------------------------------
# Aliases expected by serializers/__init__.py
# ---------------------------------------------------------------------------

# Overview = lightweight dashboard stats
AdminFraudOverviewSerializer = AdminDashboardStatsSerializer


class AdminSystemSettingsSerializer(serializers.ModelSerializer):
    """Full FraudSettings admin write serializer."""
    class Meta:
        model   = FraudSettings
        fields  = '__all__'


class AdminDashboardConfigSerializer(serializers.Serializer):
    """Configuration payload for the admin dashboard widget layout."""
    widgets           = serializers.ListField(child=serializers.CharField(), required=False)
    refresh_interval  = serializers.IntegerField(default=30)
    default_page_size = serializers.IntegerField(default=20)
    show_charts       = serializers.BooleanField(default=True)


class AdminActivityLogSerializer(serializers.Serializer):
    """One row in the admin activity feed."""
    action      = serializers.CharField()
    performed_by = serializers.CharField()
    target      = serializers.CharField(required=False)
    ip_address  = serializers.IPAddressField(required=False)
    timestamp   = serializers.DateTimeField()
    details     = serializers.DictField(required=False)


class AdminQuickActionSerializer(serializers.Serializer):
    """Payload for admin quick-action buttons (ban, flag, clear)."""
    user_id     = serializers.IntegerField()
    action      = serializers.ChoiceField(choices=['ban', 'suspend', 'flag', 'clear', 'restrict'])
    reason      = serializers.CharField(required=False, allow_blank=True)
    duration    = serializers.IntegerField(required=False, help_text='Days (for suspend)')


class AdminStatisticsSerializer(serializers.Serializer):
    """Extended statistics for the admin analytics panel."""
    period              = serializers.CharField()
    total_attempts      = serializers.IntegerField()
    confirmed_fraud     = serializers.IntegerField()
    false_positives     = serializers.IntegerField()
    precision           = serializers.FloatField()
    recall              = serializers.FloatField()
    f1_score            = serializers.FloatField()
    revenue_protected   = serializers.FloatField()
    avg_resolution_time = serializers.FloatField(help_text='Hours')
