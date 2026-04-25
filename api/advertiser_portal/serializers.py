"""
Advertiser Portal Serializers

This module contains all core serializers for the advertiser portal
including advertisers, campaigns, offers, tracking, billing, and reporting.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.exceptions import ValidationError

from .models.advertiser import Advertiser, AdvertiserProfile, AdvertiserVerification, AdvertiserAgreement
from .models.campaign import AdCampaign, CampaignCreative, CampaignTargeting, CampaignBid, CampaignSchedule
from .models.offer import AdvertiserOffer, OfferRequirement, OfferCreative, OfferBlacklist
from .models.tracking import TrackingPixel, S2SPostback, Conversion, ConversionEvent, TrackingDomain
from .models.billing import AdvertiserWallet, AdvertiserTransaction, AdvertiserDeposit, AdvertiserInvoice, CampaignSpend, BillingAlert
from .models.reporting import AdvertiserReport, CampaignReport, PublisherBreakdown, GeoBreakdown, CreativePerformance
from .models.fraud import ConversionQualityScore, AdvertiserFraudConfig, InvalidClickLog, ClickFraudSignal, OfferQualityScore, RoutingBlacklist
from .models.notification import AdvertiserNotification, AdvertiserAlert, NotificationTemplate
from .models.ml import UserJourneyStep, NetworkPerformanceCache, MLModel, MLPrediction

User = get_user_model()


class BaseSerializer(serializers.ModelSerializer):
    """Base serializer with common functionality."""
    
    def create(self, validated_data):
        """Override create to add created_by if user is authenticated."""
        if 'request' in self.context and self.context['request'].user.is_authenticated:
            validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        """Override update to add updated_by if user is authenticated."""
        if 'request' in self.context and self.context['request'].user.is_authenticated:
            validated_data['updated_by'] = self.context['request'].user
        return super().update(instance, validated_data)


# Advertiser Serializers
class AdvertiserSerializer(BaseSerializer):
    """Serializer for Advertiser model with Data Bridge integration."""
    
    full_name = serializers.CharField(source='user.get_full_name', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    date_joined = serializers.DateTimeField(source='user.date_joined', read_only=True)
    is_active = serializers.BooleanField(source='user.is_active', read_only=True)
    completion_percentage = serializers.ReadOnlyField()
    
    # Data Bridge integration fields
    legacy_id = serializers.CharField(source='metadata.legacy_id', read_only=True)
    legacy_synced = serializers.BooleanField(source='metadata.legacy_synced', read_only=True)
    last_sync_at = serializers.DateTimeField(source='metadata.last_sync_at', read_only=True)
    
    # Wallet balance for quick access
    wallet_balance = serializers.DecimalField(source='wallet.balance', max_digits=20, decimal_places=2, read_only=True)
    wallet_currency = serializers.CharField(source='wallet.currency', read_only=True)
    
    # Performance metrics
    total_campaigns = serializers.SerializerMethodField()
    active_campaigns = serializers.SerializerMethodField()
    total_conversions = serializers.SerializerMethodField()
    total_revenue = serializers.SerializerMethodField()
    
    class Meta:
        model = Advertiser
        fields = [
            'id', 'user', 'company_name', 'industry', 'website', 'contact_email',
            'contact_phone', 'description', 'verification_status', 'is_active',
            'full_name', 'email', 'date_joined', 'completion_percentage',
            'legacy_id', 'legacy_synced', 'last_sync_at',
            'wallet_balance', 'wallet_currency',
            'total_campaigns', 'active_campaigns', 'total_conversions', 'total_revenue',
            'created_at', 'updated_at', 'verified_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'verified_at']
    
    def get_total_campaigns(self, obj):
        """Get total campaigns count."""
        try:
            return obj.adcampaign_set.count()
        except:
            return 0
    
    def get_active_campaigns(self, obj):
        """Get active campaigns count."""
        try:
            return obj.adcampaign_set.filter(status='active').count()
        except:
            return 0
    
    def get_total_conversions(self, obj):
        """Get total conversions count."""
        try:
            return Conversion.objects.filter(
                campaign__advertiser=obj
            ).count()
        except:
            return 0
    
    def get_total_revenue(self, obj):
        """Get total revenue."""
        try:
            return Conversion.objects.filter(
                campaign__advertiser=obj
            ).aggregate(total=models.Sum('revenue'))['total'] or 0
        except:
            return 0
    
    class Meta:
        model = Advertiser
        fields = [
            'id', 'user', 'company_name', 'website', 'business_type', 'industry',
            'company_size', 'country', 'timezone', 'language', 'currency',
            'verification_status', 'is_active', 'is_verified', 'created_at',
            'updated_at', 'full_name', 'email', 'date_joined', 'completion_percentage'
        ]
        read_only_fields = ['id', 'user', 'verification_status', 'is_verified', 'created_at', 'updated_at']


class AdvertiserProfileSerializer(BaseSerializer):
    """Serializer for AdvertiserProfile model."""
    
    completion_percentage = serializers.ReadOnlyField()
    
    class Meta:
        model = AdvertiserProfile
        fields = [
            'id', 'advertiser', 'company_description', 'company_logo', 'contact_email',
            'contact_phone', 'address', 'city', 'state', 'postal_code', 'country',
            'website', 'social_media', 'business_hours', 'timezone', 'language',
            'currency', 'payment_methods', 'billing_address', 'tax_id',
            'completion_percentage', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'advertiser', 'completion_percentage', 'created_at', 'updated_at']


class AdvertiserVerificationSerializer(BaseSerializer):
    """Serializer for AdvertiserVerification model."""
    
    advertiser_company = serializers.CharField(source='advertiser.company_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = AdvertiserVerification
        fields = [
            'id', 'advertiser', 'advertiser_company', 'verification_type',
            'status', 'status_display', 'submitted_at', 'reviewed_at', 'reviewed_by',
            'rejection_reason', 'notes', 'documents', 'verification_data',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'advertiser', 'submitted_at', 'reviewed_at', 'reviewed_by', 'created_at', 'updated_at']


class AdvertiserAgreementSerializer(BaseSerializer):
    """Serializer for AdvertiserAgreement model."""
    
    advertiser_company = serializers.CharField(source='advertiser.company_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = AdvertiserAgreement
        fields = [
            'id', 'advertiser', 'advertiser_company', 'agreement_type',
            'title', 'content', 'version', 'status', 'status_display', 'signed_at',
            'signed_by', 'accepted_at', 'accepted_by', 'effective_date',
            'expiry_date', 'terms_accepted', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'advertiser', 'signed_at', 'signed_by', 'accepted_at', 'accepted_by', 'created_at', 'updated_at']


# Campaign Serializers
class AdCampaignSerializer(BaseSerializer):
    """Serializer for AdCampaign model."""
    
    advertiser_name = serializers.CharField(source='advertiser.company_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    performance_metrics = serializers.ReadOnlyField()
    
    class Meta:
        model = AdCampaign
        fields = [
            'id', 'advertiser', 'advertiser_name', 'name', 'description',
            'status', 'status_display', 'start_date', 'end_date', 'daily_budget',
            'total_budget', 'bid_strategy', 'target_cpa', 'target_roas',
            'performance_metrics', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'advertiser', 'performance_metrics', 'created_at', 'updated_at']


class CampaignCreativeSerializer(BaseSerializer):
    """Serializer for CampaignCreative model."""
    
    campaign_name = serializers.CharField(source='campaign.name', read_only=True)
    creative_type_display = serializers.CharField(source='get_creative_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = CampaignCreative
        fields = [
            'id', 'campaign', 'campaign_name', 'creative_type', 'creative_type_display',
            'name', 'description', 'creative_file', 'creative_url',
            'width', 'height', 'file_size', 'file_format',
            'status', 'status_display', 'is_active', 'click_url',
            'impression_url', 'third_party_tracking', 'custom_parameters',
            'start_date', 'end_date', 'approval_status', 'rejection_reason',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'campaign', 'file_size', 'approval_status', 'rejection_reason', 'created_at', 'updated_at']


class CampaignTargetingSerializer(BaseSerializer):
    """Serializer for CampaignTargeting model."""
    
    campaign_name = serializers.CharField(source='campaign.name', read_only=True)
    targeting_type_display = serializers.CharField(source='get_targeting_type_display', read_only=True)
    
    class Meta:
        model = CampaignTargeting
        fields = [
            'id', 'campaign', 'campaign_name', 'targeting_type', 'targeting_type_display',
            'targeting_criteria', 'exclusion_criteria', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'campaign', 'created_at', 'updated_at']


class CampaignBidSerializer(BaseSerializer):
    """Serializer for CampaignBid model."""
    
    campaign_name = serializers.CharField(source='campaign.name', read_only=True)
    bid_type_display = serializers.CharField(source='get_bid_type_display', read_only=True)
    bid_strategy_display = serializers.CharField(source='get_bid_strategy_display', read_only=True)
    
    class Meta:
        model = CampaignBid
        fields = [
            'id', 'campaign', 'campaign_name', 'bid_type', 'bid_type_display',
            'bid_amount', 'max_bid', 'min_bid', 'bid_strategy', 'bid_strategy_display',
            'target_cpa', 'target_roas', 'performance_data', 'optimization_settings',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'campaign', 'performance_data', 'created_at', 'updated_at']


class CampaignScheduleSerializer(BaseSerializer):
    """Serializer for CampaignSchedule model."""
    
    campaign_name = serializers.CharField(source='campaign.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = CampaignSchedule
        fields = [
            'id', 'campaign', 'campaign_name', 'start_date', 'end_date',
            'status', 'status_display', 'schedule_type', 'recurrence_pattern',
            'timezone', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'campaign', 'created_at', 'updated_at']


# Offer Serializers
class AdvertiserOfferSerializer(BaseSerializer):
    """Serializer for AdvertiserOffer model."""
    
    advertiser_name = serializers.CharField(source='advertiser.company_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    offer_type_display = serializers.CharField(source='get_offer_type_display', read_only=True)
    pricing_model_display = serializers.CharField(source='get_pricing_model_display', read_only=True)
    
    class Meta:
        model = AdvertiserOffer
        fields = [
            'id', 'advertiser', 'advertiser_name', 'name', 'description',
            'offer_type', 'offer_type_display', 'pricing_model', 'pricing_model_display',
            'payout_amount', 'currency', 'status', 'status_display', 'landing_page',
            'preview_url', 'category', 'sub_category', 'country_targeting',
            'device_targeting', 'os_targeting', 'browser_targeting',
            'carrier_targeting', 'language_targeting', 'age_restrictions',
            'daily_cap', 'total_cap', 'monthly_cap', 'is_private',
            'requires_approval', 'auto_approve', 'conversion_tracking',
            'pixel_fire_delay', 'postback_delay', 'custom_parameters',
            'terms_and_conditions', 'creative_requirements', 'restrictions',
            'compliance_notes', 'start_date', 'end_date', 'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'advertiser', 'created_at', 'updated_at']


class OfferRequirementSerializer(BaseSerializer):
    """Serializer for OfferRequirement model."""
    
    offer_name = serializers.CharField(source='offer.name', read_only=True)
    requirement_type_display = serializers.CharField(source='get_requirement_type_display', read_only=True)
    
    class Meta:
        model = OfferRequirement
        fields = [
            'id', 'offer', 'offer_name', 'requirement_type', 'requirement_type_display',
            'name', 'description', 'is_required', 'validation_rule',
            'validation_message', 'default_value', 'allowed_values',
            'min_length', 'max_length', 'pattern', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'offer', 'created_at', 'updated_at']


class OfferCreativeSerializer(BaseSerializer):
    """Serializer for OfferCreative model."""
    
    offer_name = serializers.CharField(source='offer.name', read_only=True)
    creative_type_display = serializers.CharField(source='get_creative_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = OfferCreative
        fields = [
            'id', 'offer', 'offer_name', 'creative_type', 'creative_type_display',
            'name', 'description', 'creative_file', 'creative_url',
            'width', 'height', 'file_size', 'file_format',
            'status', 'status_display', 'is_active', 'click_url',
            'impression_url', 'third_party_tracking', 'custom_parameters',
            'start_date', 'end_date', 'approval_status', 'rejection_reason',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'offer', 'file_size', 'approval_status', 'rejection_reason', 'created_at', 'updated_at']


class OfferBlacklistSerializer(BaseSerializer):
    """Serializer for OfferBlacklist model."""
    
    offer_name = serializers.CharField(source='offer.name', read_only=True)
    blacklist_type_display = serializers.CharField(source='get_blacklist_type_display', read_only=True)
    
    class Meta:
        model = OfferBlacklist
        fields = [
            'id', 'offer', 'offer_name', 'blacklist_type', 'blacklist_type_display',
            'entity_value', 'reason', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'offer', 'created_at', 'updated_at']


# Tracking Serializers
class TrackingPixelSerializer(BaseSerializer):
    """Serializer for TrackingPixel model."""
    
    advertiser_name = serializers.CharField(source='advertiser.company_name', read_only=True)
    offer_title = serializers.CharField(source='offer.title', read_only=True)
    pixel_type_display = serializers.CharField(source='get_pixel_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = TrackingPixel
        fields = [
            'id', 'advertiser', 'advertiser_name', 'offer', 'offer_title',
            'pixel_type', 'pixel_type_display', 'pixel_id', 'status',
            'status_display', 'name', 'description', 'url', 'postback_url',
            'conversion_url', 'redirect_url', 'is_secure', 'custom_parameters',
            'tracking_domain', 'firing_count', 'last_fired_at', 'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'advertiser', 'pixel_id', 'firing_count', 'last_fired_at', 'created_at', 'updated_at']


class S2SPostbackSerializer(BaseSerializer):
    """Serializer for S2SPostback model."""
    
    advertiser_name = serializers.CharField(source='advertiser.company_name', read_only=True)
    offer_title = serializers.CharField(source='offer.title', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = S2SPostback
        fields = [
            'id', 'advertiser', 'advertiser_name', 'offer', 'offer_title',
            'postback_url', 'status', 'status_display', 'event_type',
            'conversion_type', 'payout', 'currency', 'custom_parameters',
            'success_count', 'failure_count', 'last_success_at', 'last_failure_at',
            'is_active', 'retry_count', 'timeout_seconds', 'use_hmac',
            'hmac_algorithm', 'hmac_secret', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'advertiser', 'success_count', 'failure_count', 'last_success_at', 'last_failure_at', 'created_at', 'updated_at']


class ConversionSerializer(BaseSerializer):
    """Serializer for Conversion model."""
    
    advertiser_name = serializers.CharField(source='advertiser.company_name', read_only=True)
    offer_title = serializers.CharField(source='offer.title', read_only=True)
    campaign_name = serializers.CharField(source='campaign.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = Conversion
        fields = [
            'id', 'advertiser', 'advertiser_name', 'offer', 'offer_title',
            'campaign', 'campaign_name', 'pixel', 'conversion_id', 'revenue',
            'currency', 'ip_address', 'user_agent', 'referrer', 'click_id',
            'affiliate_id', 'sub_id', 'source', 'medium', 'campaign_name',
            'custom_parameters', 'fraud_score', 'quality_score', 'is_flagged',
            'status', 'status_display', 'rejection_reason', 'created_at',
            'updated_at', 'approved_at', 'rejected_at'
        ]
        read_only_fields = ['id', 'advertiser', 'created_at', 'updated_at', 'approved_at', 'rejected_at']


class ConversionEventSerializer(BaseSerializer):
    """Serializer for ConversionEvent model."""
    
    offer_title = serializers.CharField(source='offer.title', read_only=True)
    event_type_display = serializers.CharField(source='get_event_type_display', read_only=True)
    
    class Meta:
        model = ConversionEvent
        fields = [
            'id', 'offer', 'offer_title', 'event_name', 'event_type',
            'event_type_display', 'payout_amount', 'currency', 'deduplication_window',
            'deduplication_type', 'is_active', 'custom_parameters', 'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class TrackingDomainSerializer(BaseSerializer):
    """Serializer for TrackingDomain model."""
    
    advertiser_name = serializers.CharField(source='advertiser.company_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = TrackingDomain
        fields = [
            'id', 'advertiser', 'advertiser_name', 'domain', 'status',
            'status_display', 'is_secure', 'ssl_certificate', 'ssl_expiry',
            'custom_headers', 'tracking_pixels_count', 'postbacks_count',
            'conversions_count', 'last_verified_at', 'verification_status',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'advertiser', 'tracking_pixels_count', 'postbacks_count', 'conversions_count', 'last_verified_at', 'created_at', 'updated_at']


# Billing Serializers
class AdvertiserWalletSerializer(BaseSerializer):
    """Serializer for AdvertiserWallet model."""
    
    advertiser_name = serializers.CharField(source='advertiser.company_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = AdvertiserWallet
        fields = [
            'id', 'advertiser', 'advertiser_name', 'balance', 'currency',
            'status', 'status_display', 'auto_refill_enabled', 'auto_refill_threshold',
            'auto_refill_amount', 'last_refill_at', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'advertiser', 'last_refill_at', 'created_at', 'updated_at']


class AdvertiserTransactionSerializer(BaseSerializer):
    """Serializer for AdvertiserTransaction model."""
    
    advertiser_name = serializers.CharField(source='wallet.advertiser.company_name', read_only=True)
    transaction_type_display = serializers.CharField(source='get_transaction_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = AdvertiserTransaction
        fields = [
            'id', 'wallet', 'advertiser_name', 'transaction_type', 'transaction_type_display',
            'amount', 'currency', 'status', 'status_display', 'payment_method',
            'reference_id', 'description', 'metadata', 'processed_at',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'wallet', 'processed_at', 'created_at', 'updated_at']


class AdvertiserDepositSerializer(BaseSerializer):
    """Serializer for AdvertiserDeposit model."""
    
    advertiser_name = serializers.CharField(source='wallet.advertiser.company_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = AdvertiserDeposit
        fields = [
            'id', 'wallet', 'advertiser_name', 'amount', 'currency',
            'payment_method', 'status', 'status_display', 'transaction_id',
            'reference_id', 'description', 'processed_at', 'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'wallet', 'processed_at', 'created_at', 'updated_at']


class AdvertiserInvoiceSerializer(BaseSerializer):
    """Serializer for AdvertiserInvoice model."""
    
    advertiser_name = serializers.CharField(source='advertiser.company_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = AdvertiserInvoice
        fields = [
            'id', 'advertiser', 'advertiser_name', 'invoice_number', 'invoice_date',
            'due_date', 'amount', 'currency', 'tax_amount', 'total_amount',
            'status', 'status_display', 'billing_address', 'line_items',
            'notes', 'paid_at', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'advertiser', 'invoice_number', 'paid_at', 'created_at', 'updated_at']


class CampaignSpendSerializer(BaseSerializer):
    """Serializer for CampaignSpend model."""
    
    campaign_name = serializers.CharField(source='campaign.name', read_only=True)
    
    class Meta:
        model = CampaignSpend
        fields = [
            'id', 'campaign', 'campaign_name', 'spend_date', 'daily_spend',
            'total_spend', 'impressions', 'clicks', 'conversions',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'campaign', 'created_at', 'updated_at']


class BillingAlertSerializer(BaseSerializer):
    """Serializer for BillingAlert model."""
    
    advertiser_name = serializers.CharField(source='advertiser.company_name', read_only=True)
    alert_type_display = serializers.CharField(source='get_alert_type_display', read_only=True)
    
    class Meta:
        model = BillingAlert
        fields = [
            'id', 'advertiser', 'advertiser_name', 'alert_type', 'alert_type_display',
            'message', 'severity', 'is_read', 'metadata', 'sent_at',
            'read_at', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'advertiser', 'sent_at', 'created_at', 'updated_at']


# Reporting Serializers
class AdvertiserReportSerializer(BaseSerializer):
    """Serializer for AdvertiserReport model."""
    
    advertiser_name = serializers.CharField(source='advertiser.company_name', read_only=True)
    report_type_display = serializers.CharField(source='get_report_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = AdvertiserReport
        fields = [
            'id', 'advertiser', 'advertiser_name', 'report_type', 'report_type_display',
            'title', 'description', 'start_date', 'end_date', 'status',
            'status_display', 'file_url', 'file_size', 'generated_at',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'advertiser', 'file_url', 'file_size', 'generated_at', 'created_at', 'updated_at']


class CampaignReportSerializer(BaseSerializer):
    """Serializer for CampaignReport model."""
    
    campaign_name = serializers.CharField(source='campaign.name', read_only=True)
    report_type_display = serializers.CharField(source='get_report_type_display', read_only=True)
    
    class Meta:
        model = CampaignReport
        fields = [
            'id', 'campaign', 'campaign_name', 'report_type', 'report_type_display',
            'title', 'description', 'start_date', 'end_date', 'file_url',
            'file_size', 'generated_at', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'campaign', 'file_url', 'file_size', 'generated_at', 'created_at', 'updated_at']


class PublisherBreakdownSerializer(BaseSerializer):
    """Serializer for PublisherBreakdown model."""
    
    class Meta:
        model = PublisherBreakdown
        fields = [
            'id', 'report', 'publisher_id', 'publisher_name', 'impressions',
            'clicks', 'conversions', 'revenue', 'cost', 'profit',
            'ctr', 'conversion_rate', 'cpc', 'cpa', 'roas',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'report', 'created_at', 'updated_at']


class GeoBreakdownSerializer(BaseSerializer):
    """Serializer for GeoBreakdown model."""
    
    class Meta:
        model = GeoBreakdown
        fields = [
            'id', 'report', 'country', 'region', 'city', 'impressions',
            'clicks', 'conversions', 'revenue', 'cost', 'profit',
            'ctr', 'conversion_rate', 'cpc', 'cpa', 'roas',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'report', 'created_at', 'updated_at']


class CreativePerformanceSerializer(BaseSerializer):
    """Serializer for CreativePerformance model."""
    
    class Meta:
        model = CreativePerformance
        fields = [
            'id', 'report', 'creative_id', 'creative_name', 'impressions',
            'clicks', 'conversions', 'revenue', 'cost', 'profit',
            'ctr', 'conversion_rate', 'cpc', 'cpa', 'roas',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'report', 'created_at', 'updated_at']


# Fraud Serializers
class ConversionQualityScoreSerializer(BaseSerializer):
    """Serializer for ConversionQualityScore model."""
    
    offer_title = serializers.CharField(source='offer.title', read_only=True)
    quality_level_display = serializers.CharField(source='get_quality_level_display', read_only=True)
    
    class Meta:
        model = ConversionQualityScore
        fields = [
            'id', 'offer', 'offer_title', 'conversion', 'date', 'overall_score',
            'behavioral_score', 'technical_score', 'timing_score', 'engagement_score',
            'quality_level', 'quality_level_display', 'is_valid', 'fraud_indicators',
            'quality_factors', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'offer', 'conversion', 'created_at', 'updated_at']


class AdvertiserFraudConfigSerializer(BaseSerializer):
    """Serializer for AdvertiserFraudConfig model."""
    
    advertiser_name = serializers.CharField(source='advertiser.company_name', read_only=True)
    
    class Meta:
        model = AdvertiserFraudConfig
        fields = [
            'id', 'advertiser', 'advertiser_name', 'config_name', 'rules',
            'thresholds', 'actions', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'advertiser', 'created_at', 'updated_at']


class InvalidClickLogSerializer(BaseSerializer):
    """Serializer for InvalidClickLog model."""
    
    class Meta:
        model = InvalidClickLog
        fields = [
            'id', 'advertiser', 'offer', 'ip_address', 'user_agent',
            'referrer', 'click_id', 'fraud_type', 'fraud_reason',
        read_only_fields = ['id', 'created_at', 'updated_at']

# ... (rest of the code remains the same)
    
    offer_title = serializers.CharField(source='offer.title', read_only=True)
    
    class Meta:
        model = OfferQualityScore
        fields = [
            'id', 'offer', 'offer_title', 'date', 'overall_score',
            'conversion_quality', 'traffic_quality', 'compliance_score',
            'performance_score', 'quality_level', 'recommendations',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'offer', 'created_at', 'updated_at']


class RoutingBlacklistSerializer(BaseSerializer):
    """Serializer for RoutingBlacklist model."""
    
    class Meta:
        model = RoutingBlacklist
        fields = [
            'id', 'advertiser', 'blacklist_type', 'entity_value',
            'reason', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'advertiser', 'created_at', 'updated_at']


# Notification Serializers
class AdvertiserNotificationSerializer(BaseSerializer):
    """Serializer for AdvertiserNotification model."""
    
    advertiser_name = serializers.CharField(source='advertiser.company_name', read_only=True)
    notification_type_display = serializers.CharField(source='get_notification_type_display', read_only=True)
    
    class Meta:
        model = AdvertiserNotification
        fields = [
            'id', 'advertiser', 'advertiser_name', 'notification_type', 'notification_type_display',
            'title', 'message', 'priority', 'is_read', 'metadata',
            'sent_at', 'read_at', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'advertiser', 'sent_at', 'created_at', 'updated_at']


class AdvertiserAlertSerializer(BaseSerializer):
    """Serializer for AdvertiserAlert model."""
    
    advertiser_name = serializers.CharField(source='advertiser.company_name', read_only=True)
    alert_type_display = serializers.CharField(source='get_alert_type_display', read_only=True)
    
    class Meta:
        model = AdvertiserAlert
        fields = [
            'id', 'advertiser', 'advertiser_name', 'alert_type', 'alert_type_display',
            'title', 'message', 'severity', 'is_read', 'metadata',
            'triggered_at', 'read_at', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'advertiser', 'triggered_at', 'created_at', 'updated_at']


class NotificationTemplateSerializer(BaseSerializer):
    """Serializer for NotificationTemplate model."""
    
    template_type_display = serializers.CharField(source='get_template_type_display', read_only=True)
    
    class Meta:
        model = NotificationTemplate
        fields = [
            'id', 'template_type', 'template_type_display', 'name', 'subject',
            'body_template', 'variables', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


# ML Serializers
class UserJourneyStepSerializer(BaseSerializer):
    """Serializer for UserJourneyStep model."""
    
    class Meta:
        model = UserJourneyStep
        fields = [
            'id', 'user_id', 'session_id', 'step_type', 'step_data',
            'timestamp', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class NetworkPerformanceCacheSerializer(BaseSerializer):
    """Serializer for NetworkPerformanceCache model."""
    
    class Meta:
        model = NetworkPerformanceCache
        fields = [
            'id', 'cache_key', 'performance_data', 'expires_at',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class MLModelSerializer(BaseSerializer):
    """Serializer for MLModel model."""
    
    model_type_display = serializers.CharField(source='get_model_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = MLModel
        fields = [
            'id', 'name', 'model_type', 'model_type_display', 'version',
            'description', 'model_file', 'config', 'metrics', 'status',
            'status_display', 'is_active', 'trained_at', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'trained_at', 'created_at', 'updated_at']


class MLPredictionSerializer(BaseSerializer):
    """Serializer for MLPrediction model."""
    
    model_name = serializers.CharField(source='model.name', read_only=True)
    
    class Meta:
        model = MLPrediction
        fields = [
            'id', 'model', 'model_name', 'input_data', 'prediction',
            'confidence_score', 'metadata', 'created_at'
        ]
        read_only_fields = ['id', 'model', 'created_at']


# Summary Serializers for nested relationships
class AdvertiserDetailSerializer(AdvertiserSerializer):
    """Detailed advertiser serializer with nested relationships."""
    
    profile = AdvertiserProfileSerializer(read_only=True)
    verification = AdvertiserVerificationSerializer(read_only=True)
    wallet = AdvertiserWalletSerializer(read_only=True)
    campaigns = AdCampaignSerializer(many=True, read_only=True)
    
    class Meta(AdvertiserSerializer.Meta):
        fields = AdvertiserSerializer.Meta.fields + [
            'profile', 'verification', 'wallet', 'campaigns'
        ]


class CampaignDetailSerializer(AdCampaignSerializer):
    """Detailed campaign serializer with nested relationships."""
    
    creatives = CampaignCreativeSerializer(many=True, read_only=True)
    targeting = CampaignTargetingSerializer(many=True, read_only=True)
    bids = CampaignBidSerializer(many=True, read_only=True)
    spend = CampaignSpendSerializer(many=True, read_only=True)
    
    class Meta(AdCampaignSerializer.Meta):
        fields = AdCampaignSerializer.Meta.fields + [
            'creatives', 'targeting', 'bids', 'spend'
        ]


class OfferDetailSerializer(AdvertiserOfferSerializer):
    """Detailed offer serializer with nested relationships."""
    
    requirements = OfferRequirementSerializer(many=True, read_only=True)
    creatives = OfferCreativeSerializer(many=True, read_only=True)
    blacklist = OfferBlacklistSerializer(many=True, read_only=True)
    tracking_pixels = TrackingPixelSerializer(many=True, read_only=True)
    
    class Meta(AdvertiserOfferSerializer.Meta):
        fields = AdvertiserOfferSerializer.Meta.fields + [
            'requirements', 'creatives', 'blacklist', 'tracking_pixels'
        ]


# Utility Serializers
class BulkCreateSerializer(serializers.Serializer):
    """Serializer for bulk create operations."""
    
    items = serializers.ListField(child=serializers.DictField())
    
    def validate_items(self, value):
        """Validate items list."""
        if not value:
            raise serializers.ValidationError("Items list cannot be empty.")
        if len(value) > 100:
            raise serializers.ValidationError("Cannot process more than 100 items at once.")
        return value


class BulkUpdateSerializer(serializers.Serializer):
    """Serializer for bulk update operations."""
    
    updates = serializers.ListField(child=serializers.DictField())
    
    def validate_updates(self, value):
        """Validate updates list."""
        if not value:
            raise serializers.ValidationError("Updates list cannot be empty.")
        if len(value) > 100:
            raise serializers.ValidationError("Cannot process more than 100 updates at once.")
        return value


class DateRangeSerializer(serializers.Serializer):
    """Serializer for date range filtering."""
    
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    
    def validate(self, data):
        """Validate date range."""
        if data.get('start_date') and data.get('end_date'):
            if data['start_date'] > data['end_date']:
                raise serializers.ValidationError("Start date must be before end date.")
        return data


class MetricsSerializer(serializers.Serializer):
    """Serializer for metrics aggregation."""
    
    total_count = serializers.IntegerField(read_only=True)
    sum_amount = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    avg_amount = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    min_amount = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    max_amount = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)


# Export all serializers
__all__ = [
    # Base serializers
    'BaseSerializer',
    
    # Advertiser serializers
    'AdvertiserSerializer',
    'AdvertiserProfileSerializer',
    'AdvertiserVerificationSerializer',
    'AdvertiserAgreementSerializer',
    'AdvertiserDetailSerializer',
    
    # Campaign serializers
    'AdCampaignSerializer',
    'CampaignCreativeSerializer',
    'CampaignTargetingSerializer',
    'CampaignBidSerializer',
    'CampaignScheduleSerializer',
    'CampaignDetailSerializer',
    
    # Offer serializers
    'AdvertiserOfferSerializer',
    'OfferRequirementSerializer',
    'OfferCreativeSerializer',
    'OfferBlacklistSerializer',
    'OfferDetailSerializer',
    
    # Tracking serializers
    'TrackingPixelSerializer',
    'S2SPostbackSerializer',
    'ConversionSerializer',
    'ConversionEventSerializer',
    'TrackingDomainSerializer',
    
    # Billing serializers
    'AdvertiserWalletSerializer',
    'AdvertiserTransactionSerializer',
    'AdvertiserDepositSerializer',
    'AdvertiserInvoiceSerializer',
    'CampaignSpendSerializer',
    'BillingAlertSerializer',
    
    # Reporting serializers
    'AdvertiserReportSerializer',
    'CampaignReportSerializer',
    'PublisherBreakdownSerializer',
    'GeoBreakdownSerializer',
    'CreativePerformanceSerializer',
    
    # Fraud serializers
    'ConversionQualityScoreSerializer',
    'AdvertiserFraudConfigSerializer',
    'InvalidClickLogSerializer',
    'ClickFraudSignalSerializer',
    'OfferQualityScoreSerializer',
    'RoutingBlacklistSerializer',
    
    # Notification serializers
    'AdvertiserNotificationSerializer',
    'AdvertiserAlertSerializer',
    'NotificationTemplateSerializer',
    
    # ML serializers
    'UserJourneyStepSerializer',
    'NetworkPerformanceCacheSerializer',
    'MLModelSerializer',
    'MLPredictionSerializer',
    
    # Utility serializers
    'BulkCreateSerializer',
    'BulkUpdateSerializer',
    'DateRangeSerializer',
    'MetricsSerializer',
]
