"""
Tracking Serializers

This module contains serializers for tracking-related models
including TrackingPixel, S2SPostback, Conversion, ConversionEvent, and TrackingDomain.
"""

from rest_framework import serializers
from django.utils import timezone
from ..models.tracking import TrackingPixel, S2SPostback, Conversion, ConversionEvent, TrackingDomain


class TrackingPixelSerializer(serializers.ModelSerializer):
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
    
    def validate_url(self, value):
        """Validate pixel URL."""
        if not value.startswith(('http://', 'https://')):
            raise serializers.ValidationError("URL must start with http:// or https://")
        return value


class S2SPostbackSerializer(serializers.ModelSerializer):
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
    
    def validate_postback_url(self, value):
        """Validate postback URL."""
        if not value.startswith(('http://', 'https://')):
            raise serializers.ValidationError("Postback URL must start with http:// or https://")
        return value
    
    def validate_payout(self, value):
        """Validate payout amount."""
        if value < 0:
            raise serializers.ValidationError("Payout cannot be negative.")
        return value


class ConversionSerializer(serializers.ModelSerializer):
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
    
    def validate_revenue(self, value):
        """Validate revenue amount."""
        if value < 0:
            raise serializers.ValidationError("Revenue cannot be negative.")
        return value
    
    def validate_fraud_score(self, value):
        """Validate fraud score."""
        if not 0 <= value <= 1:
            raise serializers.ValidationError("Fraud score must be between 0 and 1.")
        return value
    
    def validate_quality_score(self, value):
        """Validate quality score."""
        if not 0 <= value <= 1:
            raise serializers.ValidationError("Quality score must be between 0 and 1.")
        return value


class ConversionEventSerializer(serializers.ModelSerializer):
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
    
    def validate_payout_amount(self, value):
        """Validate payout amount."""
        if value < 0:
            raise serializers.ValidationError("Payout amount cannot be negative.")
        return value


class TrackingDomainSerializer(serializers.ModelSerializer):
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
    
    def validate_domain(self, value):
        """Validate domain format."""
        if not value:
            raise serializers.ValidationError("Domain is required.")
        return value.lower()
    
    def validate_ssl_certificate(self, value):
        """Validate SSL certificate."""
        if value and len(value) > 10000:
            raise serializers.ValidationError("SSL certificate cannot be larger than 10KB.")
        return value
