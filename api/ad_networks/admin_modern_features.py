"""
api/ad_networks/admin_modern_features.py
Admin configuration for modern features based on internet research
SaaS-ready with tenant support
"""

from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Sum, Avg
from django.urls import reverse
from django.utils.safestring import mark_safe

from .models_modern_features import (
    RealTimeBid, PredictiveAnalytics, PrivacyCompliance, ProgrammaticCampaign,
    MLFraudDetection, CrossPlatformAttribution, DynamicCreative, VoiceAd,
    Web3Transaction, MetaverseAd
)


# ==================== MODERN FEATURES ADMIN ====================

@admin.register(RealTimeBid)
class RealTimeBidAdmin(admin.ModelAdmin):
    """Admin for Real-time Bidding"""
    
    list_display = [
        'bid_id', 'ad_network', 'offer', 'user', 'bid_amount', 
        'bid_type', 'bid_time', 'response_time_ms', 'win_notification_sent'
    ]
    list_filter = [
        'bid_type', 'win_notification_sent', 'bid_time', 'ad_network'
    ]
    search_fields = [
        'bid_id', 'user__username', 'offer__title', 'ad_network__name'
    ]
    readonly_fields = [
        'bid_time', 'response_time_ms', 'created_at', 'updated_at'
    ]
    date_hierarchy = 'bid_time'
    
    fieldsets = (
        ('Bid Information', {
            'fields': ('bid_id', 'ad_network', 'offer', 'user', 'bid_amount', 'floor_price', 'bid_type')
        }),
        ('Real-time Data', {
            'fields': ('bid_time', 'response_time_ms', 'win_notification_sent')
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).filter(tenant_id=getattr(request, 'tenant_id', 'default'))


@admin.register(PredictiveAnalytics)
class PredictiveAnalyticsAdmin(admin.ModelAdmin):
    """Admin for Predictive Analytics"""
    
    list_display = [
        'prediction_id', 'offer', 'model_type', 'model_version', 
        'confidence_score', 'prediction_value', 'actual_value', 'last_trained_at'
    ]
    list_filter = [
        'model_type', 'confidence_score', 'last_trained_at'
    ]
    search_fields = [
        'prediction_id', 'offer__title', 'model_name', 'model_version'
    ]
    readonly_fields = [
        'training_data_points', 'created_at', 'updated_at'
    ]
    date_hierarchy = 'last_trained_at'
    
    fieldsets = (
        ('Prediction Details', {
            'fields': ('prediction_id', 'offer', 'model_type', 'model_version')
        }),
        ('AI Model Data', {
            'fields': ('confidence_score', 'prediction_value', 'actual_value', 'training_data_points')
        }),
        ('Training Information', {
            'fields': ('last_trained_at',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).filter(tenant_id=getattr(request, 'tenant_id', 'default'))


@admin.register(PrivacyCompliance)
class PrivacyComplianceAdmin(admin.ModelAdmin):
    """Admin for Privacy Compliance"""
    
    list_display = [
        'consent_id', 'user', 'compliance_framework', 'consent_given', 
        'consent_timestamp', 'data_retention_days', 'do_not_sell', 'data_deletion_requested'
    ]
    list_filter = [
        'compliance_framework', 'consent_given', 'do_not_sell', 'data_deletion_requested'
    ]
    search_fields = [
        'consent_id', 'user__username', 'consent_purpose', 'ip_address'
    ]
    readonly_fields = [
        'consent_timestamp', 'created_at', 'updated_at'
    ]
    date_hierarchy = 'consent_timestamp'
    
    fieldsets = (
        ('Consent Information', {
            'fields': ('consent_id', 'user', 'compliance_framework', 'consent_given', 'consent_timestamp')
        }),
        ('Privacy Settings', {
            'fields': ('consent_purpose', 'data_retention_days', 'do_not_sell', 'data_deletion_requested', 'data_deletion_completed')
        }),
        ('Audit Trail', {
            'fields': ('ip_address', 'user_agent', 'geolocation')
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).filter(tenant_id=getattr(request, 'tenant_id', 'default'))


@admin.register(ProgrammaticCampaign)
class ProgrammaticCampaignAdmin(admin.ModelAdmin):
    """Admin for Programmatic Campaigns"""
    
    list_display = [
        'campaign_id', 'name', 'ad_network', 'bidding_strategy', 
        'impressions', 'clicks', 'conversions', 'spend'
    ]
    list_filter = [
        'bidding_strategy', 'ad_network', 'created_at'
    ]
    search_fields = [
        'campaign_id', 'name', 'demand_side_platform', 'supply_side_platform'
    ]
    readonly_fields = [
        'impressions', 'clicks', 'conversions', 'created_at', 'updated_at'
    ]
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Campaign Details', {
            'fields': ('campaign_id', 'name', 'ad_network', 'demand_side_platform', 'supply_side_platform', 'ad_exchange')
        }),
        ('Bidding Strategy', {
            'fields': ('bidding_strategy',)
        }),
        ('Targeting Parameters', {
            'fields': ('target_audience', 'target_geography', 'target_devices', 'target_time')
        }),
        ('Performance Metrics', {
            'fields': ('impressions', 'clicks', 'conversions', 'spend')
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).filter(tenant_id=getattr(request, 'tenant_id', 'default'))


@admin.register(MLFraudDetection)
class MLFraudDetectionAdmin(admin.ModelAdmin):
    """Admin for ML Fraud Detection"""
    
    list_display = [
        'detection_id', 'user', 'fraud_type', 'risk_score', 'risk_level', 
        'action_taken', 'reviewed_by', 'created_at'
    ]
    list_filter = [
        'fraud_type', 'risk_level', 'action_taken', 'reviewed_at'
    ]
    search_fields = [
        'detection_id', 'user__username', 'model_name', 'ip_address', 'device_fingerprint'
    ]
    readonly_fields = [
        'confidence_score', 'evidence_data', 'created_at', 'updated_at'
    ]
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Detection Details', {
            'fields': ('detection_id', 'user', 'offer', 'fraud_type', 'risk_score', 'risk_level')
        }),
        ('ML Model Data', {
            'fields': ('model_name', 'model_version', 'confidence_score')
        }),
        ('Evidence', {
            'fields': ('evidence_data', 'ip_address', 'device_fingerprint', 'user_agent')
        }),
        ('Action Taken', {
            'fields': ('action_taken', 'reviewed_by', 'reviewed_at', 'review_notes')
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).filter(tenant_id=getattr(request, 'tenant_id', 'default'))


@admin.register(CrossPlatformAttribution)
class CrossPlatformAttributionAdmin(admin.ModelAdmin):
    """Admin for Cross-Platform Attribution"""
    
    list_display = [
        'attribution_id', 'user', 'attribution_model', 'conversion_value', 
        'conversion_currency', 'source_platform', 'conversion_time'
    ]
    list_filter = [
        'attribution_model', 'source_platform', 'attributed_network', 'conversion_time'
    ]
    search_fields = [
        'attribution_id', 'user__username', 'source_campaign', 'source_ad'
    ]
    readonly_fields = [
        'first_touch_time', 'last_touch_time', 'created_at', 'updated_at'
    ]
    date_hierarchy = 'conversion_time'
    
    fieldsets = (
        ('Attribution Details', {
            'fields': ('attribution_id', 'user', 'attribution_model', 'conversion_value', 'conversion_currency')
        }),
        ('Touch Points', {
            'fields': ('touchpoints',)
        }),
        ('Platform Data', {
            'fields': ('source_platform', 'source_campaign', 'source_ad_group', 'source_ad', 'source_keyword')
        }),
        ('Attribution Results', {
            'fields': ('attributed_platform', 'attributed_network', 'attributed_offer')
        }),
        ('Time Data', {
            'fields': ('first_touch_time', 'last_touch_time', 'conversion_time', 'attribution_window_hours')
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).filter(tenant_id=getattr(request, 'tenant_id', 'default'))


@admin.register(DynamicCreative)
class DynamicCreativeAdmin(admin.ModelAdmin):
    """Admin for Dynamic Creative"""
    
    list_display = [
        'creative_id', 'ad_network', 'offer', 'creative_type', 'optimization_goal', 
        'impressions', 'clicks', 'conversions', 'ctr', 'conversion_rate'
    ]
    list_filter = [
        'creative_type', 'optimization_goal', 'test_group', 'is_winner'
    ]
    search_fields = [
        'creative_id', 'base_creative_url', 'optimization_model', 'test_group'
    ]
    readonly_fields = [
        'ctr', 'conversion_rate', 'confidence_level', 'created_at', 'updated_at'
    ]
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Creative Details', {
            'fields': ('creative_id', 'ad_network', 'offer', 'creative_type', 'base_creative_url')
        }),
        ('Dynamic Elements', {
            'fields': ('dynamic_elements', 'personalization_rules')
        }),
        ('AI Optimization', {
            'fields': ('optimization_model', 'optimization_goal')
        }),
        ('Performance Tracking', {
            'fields': ('impressions', 'clicks', 'conversions', 'ctr', 'conversion_rate')
        }),
        ('A/B Testing', {
            'fields': ('test_group', 'is_winner', 'confidence_level')
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).filter(tenant_id=getattr(request, 'tenant_id', 'default'))


@admin.register(VoiceAd)
class VoiceAdAdmin(admin.ModelAdmin):
    """Admin for Voice Ads"""
    
    list_display = [
        'ad_id', 'ad_network', 'offer', 'voice_platform', 'ad_format', 
        'audio_duration', 'audio_format', 'plays', 'completions', 'clicks'
    ]
    list_filter = [
        'voice_platform', 'ad_format', 'audio_format'
    ]
    search_fields = [
        'ad_id', 'voice_platform', 'target_genres', 'ad_network__name'
    ]
    readonly_fields = [
        'plays', 'completions', 'clicks', 'conversions', 'created_at', 'updated_at'
    ]
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Voice Ad Details', {
            'fields': ('ad_id', 'ad_network', 'offer', 'voice_platform', 'ad_format')
        }),
        ('Audio Content', {
            'fields': ('audio_url', 'audio_duration', 'audio_file_size', 'audio_format')
        }),
        ('Targeting', {
            'fields': ('target_demographics', 'target_genres', 'target_time_of_day')
        }),
        ('Performance', {
            'fields': ('plays', 'completions', 'clicks', 'conversions')
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).filter(tenant_id=getattr(request, 'tenant_id', 'default'))


@admin.register(Web3Transaction)
class Web3TransactionAdmin(admin.ModelAdmin):
    """Admin for Web3 Transactions"""
    
    list_display = [
        'transaction_hash', 'ad_network', 'offer', 'user', 'blockchain_network', 
        'amount', 'token_symbol', 'gas_fee', 'status'
    ]
    list_filter = [
        'blockchain_network', 'status', 'created_at'
    ]
    search_fields = [
        'transaction_hash', 'contract_address', 'function_called', 'block_number'
    ]
    readonly_fields = [
        'gas_fee', 'block_number', 'created_at', 'updated_at'
    ]
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Transaction Details', {
            'fields': ('transaction_hash', 'ad_network', 'offer', 'user', 'blockchain_network')
        }),
        ('Transaction Data', {
            'fields': ('amount', 'token_symbol', 'gas_fee', 'status')
        }),
        ('Smart Contract Data', {
            'fields': ('contract_address', 'function_called', 'block_number')
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).filter(tenant_id=getattr(request, 'tenant_id', 'default'))


@admin.register(MetaverseAd)
class MetaverseAdAdmin(admin.ModelAdmin):
    """Admin for Metaverse Ads"""
    
    list_display = [
        'ad_id', 'ad_network', 'offer', 'metaverse_platform', 'placement_type', 
        'asset_type', 'virtual_world', 'views', 'interactions'
    ]
    list_filter = [
        'metaverse_platform', 'placement_type', 'asset_type'
    ]
    search_fields = [
        'ad_id', 'virtual_world', 'virtual_coordinates', 'ad_network__name'
    ]
    readonly_fields = [
        'views', 'interactions', 'conversions', 'created_at', 'updated_at'
    ]
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Metaverse Details', {
            'fields': ('ad_id', 'ad_network', 'offer', 'metaverse_platform', 'virtual_world')
        }),
        ('3D/VR Content', {
            'fields': ('asset_url', 'asset_type')
        }),
        ('Placement Data', {
            'fields': ('virtual_coordinates', 'placement_type')
        }),
        ('Performance', {
            'fields': ('views', 'interactions', 'conversions')
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).filter(tenant_id=getattr(request, 'tenant_id', 'default'))


# ==================== ADMIN CUSTOMIZATION ====================

class ModernFeaturesAdminMixin:
    """Mixin for modern features admin customization"""
    
    def get_queryset(self, request):
        """Filter by tenant"""
        qs = super().get_queryset(request)
        if hasattr(request, 'tenant_id'):
            qs = qs.filter(tenant_id=request.tenant_id)
        return qs
    
    def get_readonly_fields(self, request, obj=None):
        """Make fields readonly based on object state"""
        readonly = list(self.readonly_fields)
        if obj and hasattr(obj, 'status'):
            if obj.status in ['completed', 'confirmed', 'processed']:
                readonly.extend(['status', 'processed_data'])
        return readonly
    
    def response_change(self, request, obj):
        """Custom response messages"""
        self.message_user(request, f"{obj._meta.verbose_name} updated successfully!", level='success')
        return super().response_change(request, obj)


# ==================== INLINE ADMIN CLASSES ====================

class PredictiveAnalyticsInline(admin.TabularInline):
    """Inline for predictive analytics in offers"""
    model = PredictiveAnalytics
    extra = 0
    readonly_fields = ['prediction_id', 'model_type', 'confidence_score', 'prediction_value']
    fields = ['prediction_id', 'model_type', 'confidence_score', 'prediction_value', 'last_trained_at']
    
    def get_queryset(self, request):
        return super().get_queryset(request).filter(tenant_id=getattr(request, 'tenant_id', 'default'))


class MLFraudDetectionInline(admin.TabularInline):
    """Inline for fraud detection in users"""
    model = MLFraudDetection
    extra = 0
    readonly_fields = ['detection_id', 'fraud_type', 'risk_score', 'risk_level']
    fields = ['detection_id', 'fraud_type', 'risk_score', 'action_taken', 'created_at']
    
    def get_queryset(self, request):
        return super().get_queryset(request).filter(tenant_id=getattr(request, 'tenant_id', 'default'))


class CrossPlatformAttributionInline(admin.TabularInline):
    """Inline for attribution in users"""
    model = CrossPlatformAttribution
    extra = 0
    readonly_fields = ['attribution_id', 'attribution_model', 'conversion_value']
    fields = ['attribution_id', 'attribution_model', 'conversion_value', 'conversion_time']
    
    def get_queryset(self, request):
        return super().get_queryset(request).filter(tenant_id=getattr(request, 'tenant_id', 'default'))
