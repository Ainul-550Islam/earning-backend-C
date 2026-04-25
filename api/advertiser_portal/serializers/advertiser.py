"""
Advertiser Serializers

This module contains serializers for advertiser-related models
including Advertiser, AdvertiserProfile, AdvertiserVerification, and AdvertiserAgreement.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils import timezone
from ..models.advertiser import Advertiser, AdvertiserProfile, AdvertiserVerification, AdvertiserAgreement

User = get_user_model()


class AdvertiserSerializer(serializers.ModelSerializer):
    """Serializer for Advertiser model."""
    
    full_name = serializers.CharField(source='user.get_full_name', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    date_joined = serializers.DateTimeField(source='user.date_joined', read_only=True)
    is_active = serializers.BooleanField(source='user.is_active', read_only=True)
    
    class Meta:
        model = Advertiser
        fields = [
            'id', 'user', 'company_name', 'website', 'business_type', 'industry',
            'company_size', 'country', 'timezone', 'language', 'currency',
            'verification_status', 'is_active', 'is_verified', 'created_at',
            'updated_at', 'full_name', 'email', 'date_joined'
        ]
        read_only_fields = ['id', 'user', 'verification_status', 'is_verified', 'created_at', 'updated_at']
    
    def create(self, validated_data):
        """Create advertiser with user."""
        user = self.context['request'].user
        validated_data['user'] = user
        return super().create(validated_data)


class AdvertiserProfileSerializer(serializers.ModelSerializer):
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
    
    def validate_company_logo(self, value):
        """Validate company logo size and format."""
        if value and value.size > 5 * 1024 * 1024:  # 5MB limit
            raise serializers.ValidationError("Company logo cannot be larger than 5MB.")
        return value


class AdvertiserVerificationSerializer(serializers.ModelSerializer):
    """Serializer for AdvertiserVerification model."""
    
    advertiser_company = serializers.CharField(source='advertiser.company_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = AdvertiserVerification
        fields = [
            'id', 'advertiser', 'advertiser_company', 'verification_type',
            'status', 'submitted_at', 'reviewed_at', 'reviewed_by',
            'rejection_reason', 'notes', 'documents', 'verification_data',
            'status_display', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'advertiser', 'submitted_at', 'reviewed_at', 'reviewed_by', 'created_at', 'updated_at']
    
    def validate_documents(self, value):
        """Validate verification documents."""
        if value and len(value) > 10:
            raise serializers.ValidationError("Cannot upload more than 10 documents.")
        return value


class AdvertiserAgreementSerializer(serializers.ModelSerializer):
    """Serializer for AdvertiserAgreement model."""
    
    advertiser_company = serializers.CharField(source='advertiser.company_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = AdvertiserAgreement
        fields = [
            'id', 'advertiser', 'advertiser_company', 'agreement_type',
            'title', 'content', 'version', 'status', 'signed_at',
            'signed_by', 'accepted_at', 'accepted_by', 'effective_date',
            'expiry_date', 'terms_accepted', 'status_display', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'advertiser', 'signed_at', 'signed_by', 'accepted_at', 'accepted_by', 'created_at', 'updated_at']
    
    def validate(self, data):
        """Validate agreement data."""
        if data.get('effective_date') and data.get('expiry_date'):
            if data['effective_date'] >= data['expiry_date']:
                raise serializers.ValidationError("Effective date must be before expiry date.")
        return data
