"""
Offer Serializers

This module contains serializers for offer-related models
including AdvertiserOffer, OfferRequirement, OfferCreative, and OfferBlacklist.
"""

from rest_framework import serializers
from django.utils import timezone
from ..models.offer import AdvertiserOffer, OfferRequirement, OfferCreative, OfferBlacklist


class AdvertiserOfferSerializer(serializers.ModelSerializer):
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
    
    def validate_payout_amount(self, value):
        """Validate payout amount."""
        if value < 0:
            raise serializers.ValidationError("Payout amount cannot be negative.")
        return value
    
    def validate_landing_page(self, value):
        """Validate landing page URL."""
        if not value.startswith(('http://', 'https://')):
            raise serializers.ValidationError("Landing page must start with http:// or https://")
        return value
    
    def validate(self, data):
        """Validate offer data."""
        if data.get('start_date') and data.get('end_date'):
            if data['start_date'] >= data['end_date']:
                raise serializers.ValidationError("Start date must be before end date.")
        return data


class OfferRequirementSerializer(serializers.ModelSerializer):
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
    
    def validate_validation_rule(self, value):
        """Validate validation rule."""
        if value and len(value) > 1000:
            raise serializers.ValidationError("Validation rule cannot be larger than 1000 characters.")
        return value


class OfferCreativeSerializer(serializers.ModelSerializer):
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
    
    def validate_creative_file(self, value):
        """Validate creative file size and format."""
        if value and value.size > 10 * 1024 * 1024:  # 10MB limit
            raise serializers.ValidationError("Creative file cannot be larger than 10MB.")
        return value
    
    def validate_click_url(self, value):
        """Validate click URL."""
        if value and not value.startswith(('http://', 'https://')):
            raise serializers.ValidationError("Click URL must start with http:// or https://")
        return value


class OfferBlacklistSerializer(serializers.ModelSerializer):
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
    
    def validate_entity_value(self, value):
        """Validate entity value."""
        if not value:
            raise serializers.ValidationError("Entity value is required.")
        return value.strip()
    
    def validate(self, data):
        """Validate blacklist data."""
        blacklist_type = data.get('blacklist_type')
        entity_value = data.get('entity_value')
        
        if blacklist_type == 'ip_address' and entity_value:
            # Basic IP validation
            parts = entity_value.split('.')
            if len(parts) != 4 or not all(part.isdigit() and 0 <= int(part) <= 255 for part in parts):
                raise serializers.ValidationError("Invalid IP address format.")
        
        return data
