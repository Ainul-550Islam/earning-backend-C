from django.contrib import admin
from .models import (
    IPIntelligence, VPNDetectionLog, ProxyDetectionLog, TorExitNode,
    DatacenterIPRange, FraudAttempt, ClickFraudRecord, DeviceFingerprint,
    MultiAccountLink, VelocityMetric, IPBlacklist, IPWhitelist,
    ThreatFeedProvider, MaliciousIPDatabase, UserRiskProfile,
    RiskScoreHistory, MLModelMetadata, AnomalyDetectionLog,
    FraudRule, AlertConfiguration, IntegrationCredential,
    APIRequestLog, PerformanceMetric, SystemAuditTrail
)


@admin.register(IPIntelligence)
class IPIntelligenceAdmin(admin.ModelAdmin):
    list_display = ['ip_address', 'country_code', 'risk_score', 'risk_level',
                    'is_vpn', 'is_proxy', 'is_tor', 'is_datacenter', 'last_checked']
    list_filter = ['risk_level', 'is_vpn', 'is_proxy', 'is_tor', 'is_datacenter', 'country_code']
    search_fields = ['ip_address', 'isp', 'asn']
    readonly_fields = ['id', 'created_at', 'updated_at', 'last_checked', 'check_count']
    ordering = ['-risk_score']


@admin.register(IPBlacklist)
class IPBlacklistAdmin(admin.ModelAdmin):
    list_display = ['ip_address', 'reason', 'is_permanent', 'is_active', 'source', 'created_at']
    list_filter = ['reason', 'is_permanent', 'is_active']
    search_fields = ['ip_address', 'description']
    readonly_fields = ['id', 'created_at', 'updated_at']


@admin.register(IPWhitelist)
class IPWhitelistAdmin(admin.ModelAdmin):
    list_display = ['ip_address', 'cidr', 'label', 'is_active', 'created_at']
    search_fields = ['ip_address', 'label']


@admin.register(TorExitNode)
class TorExitNodeAdmin(admin.ModelAdmin):
    list_display = ['ip_address', 'is_active', 'first_seen', 'last_seen']
    list_filter = ['is_active']
    search_fields = ['ip_address']


@admin.register(DatacenterIPRange)
class DatacenterIPRangeAdmin(admin.ModelAdmin):
    list_display = ['cidr', 'provider_name', 'asn', 'country_code', 'is_active']
    list_filter = ['provider_name', 'is_active']
    search_fields = ['cidr', 'provider_name']


@admin.register(FraudAttempt)
class FraudAttemptAdmin(admin.ModelAdmin):
    list_display = ['ip_address', 'fraud_type', 'status', 'risk_score', 'created_at']
    list_filter = ['fraud_type', 'status']
    search_fields = ['ip_address', 'description']
    readonly_fields = ['id', 'created_at', 'updated_at']


@admin.register(UserRiskProfile)
class UserRiskProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'overall_risk_score', 'risk_level', 'is_high_risk',
                    'vpn_usage_detected', 'fraud_attempts_count']
    list_filter = ['risk_level', 'is_high_risk', 'vpn_usage_detected']
    search_fields = ['user__email', 'user__username']


@admin.register(MLModelMetadata)
class MLModelMetadataAdmin(admin.ModelAdmin):
    list_display = ['name', 'version', 'model_type', 'is_active', 'accuracy', 'trained_at']
    list_filter = ['model_type', 'is_active']


@admin.register(ThreatFeedProvider)
class ThreatFeedProviderAdmin(admin.ModelAdmin):
    list_display = ['display_name', 'is_active', 'priority', 'total_entries', 'used_today', 'last_sync']
    list_filter = ['is_active']


@admin.register(FraudRule)
class FraudRuleAdmin(admin.ModelAdmin):
    list_display = ['name', 'rule_code', 'condition_type', 'action', 'priority', 'is_active', 'trigger_count']
    list_filter = ['condition_type', 'action', 'is_active']
    search_fields = ['name', 'rule_code']


@admin.register(AlertConfiguration)
class AlertConfigurationAdmin(admin.ModelAdmin):
    list_display = ['name', 'trigger', 'channel', 'is_active', 'threshold_score']
    list_filter = ['trigger', 'channel', 'is_active']


@admin.register(SystemAuditTrail)
class SystemAuditTrailAdmin(admin.ModelAdmin):
    list_display = ['user', 'action', 'model_name', 'object_repr', 'created_at']
    list_filter = ['action', 'model_name']
    search_fields = ['user__email', 'model_name', 'object_repr']
    readonly_fields = ['id', 'created_at', 'updated_at']

    def has_change_permission(self, request, obj=None):
        return False  # Audit trail is read-only


@admin.register(IntegrationCredential)
class IntegrationCredentialAdmin(admin.ModelAdmin):
    list_display = ['service', 'tenant', 'is_active', 'daily_limit', 'used_today']
    list_filter = ['service', 'is_active']

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ['api_key', 'id', 'created_at', 'updated_at']
        return ['id', 'created_at', 'updated_at']


# Register remaining models simply
for model in [VPNDetectionLog, ProxyDetectionLog, ClickFraudRecord,
              DeviceFingerprint, MultiAccountLink, VelocityMetric,
              MaliciousIPDatabase, RiskScoreHistory, AnomalyDetectionLog,
              APIRequestLog, PerformanceMetric]:
    try:
        admin.site.register(model)
    except admin.sites.AlreadyRegistered:
        pass


def _force_register_proxy_intelligence():
    try:
        from api.admin_panel.admin import admin_site as modern_site
        if modern_site is None:
            return
        pairs = [(IPIntelligence, IPIntelligenceAdmin), (IPBlacklist, IPBlacklistAdmin), (IPWhitelist, IPWhitelistAdmin), (TorExitNode, TorExitNodeAdmin), (DatacenterIPRange, DatacenterIPRangeAdmin), (FraudAttempt, FraudAttemptAdmin), (UserRiskProfile, UserRiskProfileAdmin), (MLModelMetadata, MLModelMetadataAdmin), (ThreatFeedProvider, ThreatFeedProviderAdmin), (FraudRule, FraudRuleAdmin), (AlertConfiguration, AlertConfigurationAdmin), (SystemAuditTrail, SystemAuditTrailAdmin), (IntegrationCredential, IntegrationCredentialAdmin)]
        registered = 0
        for model, model_admin in pairs:
            try:
                if model not in modern_site._registry:
                    modern_site.register(model, model_admin)
                    registered += 1
            except Exception as ex:
                pass
        print(f"[OK] proxy_intelligence registered {registered} models")
    except Exception as e:
        print(f"[WARN] proxy_intelligence: {e}")
