"""
Advertiser Management Serializers

This module contains Django REST Framework serializers for advertiser
management data validation and serialization.
"""

from typing import Optional, List, Dict, Any, Union
from decimal import Decimal
from datetime import datetime, date
from uuid import UUID

from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from ..database_models.advertiser_model import Advertiser, AdvertiserVerification, AdvertiserCredit
from ..database_models.user_model import AdvertiserUser, UserActivityLog
from ..database_models.billing_model import BillingProfile
from ..database_models.notification_model import Notification
from ..enums import *
from ..validators import *

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model."""
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']
        read_only_fields = ['id']


class AdvertiserUserSerializer(serializers.ModelSerializer):
    """Serializer for AdvertiserUser model."""
    
    user = UserSerializer(read_only=True)
    advertiser_name = serializers.CharField(source='advertiser.company_name', read_only=True)
    
    class Meta:
        model = AdvertiserUser
        fields = [
            'id', 'user_id', 'username', 'email', 'first_name', 'last_name',
            'display_name', 'phone_number', 'mobile_number', 'job_title',
            'department', 'advertiser', 'advertiser_name', 'role', 'permissions',
            'can_create_campaigns', 'can_edit_campaigns', 'can_view_billing',
            'can_manage_billing', 'can_manage_users', 'can_view_reports',
            'can_export_data', 'is_active', 'is_verified', 'two_factor_enabled',
            'last_login', 'login_count', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'user_id', 'username', 'advertiser', 'advertiser_name',
            'last_login', 'login_count', 'created_at', 'updated_at'
        ]


class AdvertiserUserCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating AdvertiserUser."""
    
    password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True)
    
    class Meta:
        model = AdvertiserUser
        fields = [
            'username', 'email', 'password', 'confirm_password', 'first_name',
            'last_name', 'phone_number', 'job_title', 'department', 'role'
        ]
    
    def validate(self, attrs):
        """Validate password confirmation."""
        if attrs['password'] != attrs['confirm_password']:
            raise serializers.ValidationError("Passwords don't match")
        return attrs
    
    def validate_email(self, value):
        """Validate email uniqueness."""
        if AdvertiserUser.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already exists")
        return value
    
    def validate_username(self, value):
        """Validate username uniqueness."""
        if AdvertiserUser.objects.filter(username=value).exists():
            raise serializers.ValidationError("Username already exists")
        return value
    
    def create(self, validated_data):
        """Create user with hashed password."""
        validated_data.pop('confirm_password')
        password = validated_data.pop('password')
        
        user = AdvertiserUser.objects.create_user(
            password=password,
            **validated_data
        )
        return user


class BillingProfileSerializer(serializers.ModelSerializer):
    """Serializer for BillingProfile model."""
    
    class Meta:
        model = BillingProfile
        fields = [
            'id', 'company_name', 'trade_name', 'billing_email', 'billing_phone',
            'billing_contact', 'billing_title', 'billing_address_line1',
            'billing_address_line2', 'billing_city', 'billing_state',
            'billing_country', 'billing_postal_code', 'billing_cycle',
            'payment_terms', 'auto_charge', 'auto_charge_threshold',
            'credit_limit', 'credit_available', 'spending_limit',
            'tax_exempt', 'tax_rate', 'tax_region', 'default_currency',
            'pricing_model', 'is_verified', 'verification_date',
            'status', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'credit_available', 'is_verified', 'verification_date',
            'created_at', 'updated_at'
        ]


class AdvertiserVerificationSerializer(serializers.ModelSerializer):
    """Serializer for AdvertiserVerification model."""
    
    advertiser_name = serializers.CharField(source='advertiser.company_name', read_only=True)
    reviewed_by_username = serializers.CharField(source='reviewed_by.username', read_only=True)
    
    class Meta:
        model = AdvertiserVerification
        fields = [
            'id', 'advertiser', 'advertiser_name', 'verification_type',
            'status', 'submitted_documents', 'verification_notes',
            'reviewed_by', 'reviewed_by_username', 'reviewed_at',
            'expires_at', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'reviewed_by_username', 'created_at', 'updated_at']


class AdvertiserCreditSerializer(serializers.ModelSerializer):
    """Serializer for AdvertiserCredit model."""
    
    advertiser_name = serializers.CharField(source='advertiser.company_name', read_only=True)
    
    class Meta:
        model = AdvertiserCredit
        fields = [
            'id', 'advertiser', 'advertiser_name', 'amount', 'credit_type',
            'description', 'reference_id', 'balance_after', 'created_at'
        ]
        read_only_fields = ['id', 'advertiser_name', 'balance_after', 'created_at']


class AdvertiserSerializer(serializers.ModelSerializer):
    """Serializer for Advertiser model."""
    
    user = UserSerializer(read_only=True)
    billing_profile = BillingProfileSerializer(read_only=True)
    
    class Meta:
        model = Advertiser
        fields = [
            'id', 'user', 'company_name', 'trade_name', 'industry', 'sub_industry',
            'contact_email', 'contact_phone', 'contact_name', 'contact_title',
            'website', 'description', 'company_size', 'annual_revenue',
            'billing_address', 'billing_city', 'billing_state', 'billing_country',
            'billing_postal_code', 'is_verified', 'verification_date',
            'verified_by', 'verification_documents', 'compliance_score',
            'account_type', 'account_manager', 'timezone', 'currency',
            'language', 'credit_limit', 'account_balance', 'auto_charge_enabled',
            'billing_cycle', 'total_spend', 'total_campaigns', 'active_campaigns',
            'quality_score', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'user', 'billing_profile', 'verification_date', 'verified_by',
            'total_spend', 'total_campaigns', 'active_campaigns', 'quality_score',
            'created_at', 'updated_at'
        ]


class AdvertiserDetailSerializer(AdvertiserSerializer):
    """Detailed serializer for Advertiser model with additional fields."""
    
    verifications = AdvertiserVerificationSerializer(
        source='advertiser_verifications',
        many=True,
        read_only=True
    )
    credits = AdvertiserCreditSerializer(
        source='advertiser_credits',
        many=True,
        read_only=True
    )
    recent_notifications = serializers.SerializerMethodField()
    
    class Meta(AdvertiserSerializer.Meta):
        fields = AdvertiserSerializer.Meta.fields + [
            'verifications', 'credits', 'recent_notifications'
        ]
    
    def get_recent_notifications(self, obj):
        """Get recent notifications for advertiser."""
        notifications = obj.notifications.filter(
            is_read=False
        ).order_by('-created_at')[:5]
        
        return [
            {
                'id': str(notif.id),
                'title': notif.title,
                'message': notif.message,
                'priority': notif.priority,
                'created_at': notif.created_at
            }
            for notif in notifications
        ]


class AdvertiserCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating Advertiser."""
    
    user = AdvertiserUserCreateSerializer(write_only=True)
    billing_profile = BillingProfileSerializer(required=False)
    
    class Meta:
        model = Advertiser
        fields = [
            'company_name', 'trade_name', 'industry', 'sub_industry',
            'contact_email', 'contact_phone', 'contact_name', 'contact_title',
            'website', 'description', 'company_size', 'annual_revenue',
            'billing_address', 'billing_city', 'billing_state', 'billing_country',
            'billing_postal_code', 'account_type', 'timezone', 'currency',
            'language', 'user', 'billing_profile'
        ]
    
    def validate(self, attrs):
        """Validate advertiser data."""
        # Validate email uniqueness
        email = attrs.get('contact_email')
        if email and Advertiser.objects.filter(contact_email=email).exists():
            raise serializers.ValidationError("Advertiser with this email already exists")
        
        # Validate company name uniqueness
        company_name = attrs.get('company_name')
        if company_name and Advertiser.objects.filter(company_name=company_name).exists():
            raise serializers.ValidationError("Advertiser with this company name already exists")
        
        return attrs
    
    def create(self, validated_data):
        """Create advertiser with user and billing profile."""
        user_data = validated_data.pop('user')
        billing_profile_data = validated_data.pop('billing_profile', {})
        
        # Create advertiser (service layer will handle user creation)
        from ..services import AdvertiserService
        advertiser = AdvertiserService.create_advertiser(
            {
                **validated_data,
                'user': user_data,
                'billing_profile': billing_profile_data
            }
        )
        
        return advertiser


class AdvertiserUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating Advertiser."""
    
    billing_profile = BillingProfileSerializer(required=False)
    
    class Meta:
        model = Advertiser
        fields = [
            'trade_name', 'industry', 'sub_industry', 'contact_phone',
            'contact_name', 'contact_title', 'website', 'description',
            'company_size', 'annual_revenue', 'billing_address',
            'billing_city', 'billing_state', 'billing_country',
            'billing_postal_code', 'timezone', 'currency', 'language',
            'billing_profile'
        ]
    
    def update(self, instance, validated_data):
        """Update advertiser with nested billing profile."""
        billing_profile_data = validated_data.pop('billing_profile', {})
        
        # Update advertiser
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Update billing profile if provided
        if billing_profile_data:
            billing_profile = instance.get_billing_profile()
            if billing_profile:
                for attr, value in billing_profile_data.items():
                    setattr(billing_profile, attr, value)
                billing_profile.save()
        
        return instance


class UserActivityLogSerializer(serializers.ModelSerializer):
    """Serializer for UserActivityLog model."""
    
    user_username = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = UserActivityLog
        fields = [
            'id', 'activity_type', 'object_type', 'object_id', 'object_name',
            'description', 'details', 'ip_address', 'user_agent',
            'success', 'error_message', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class NotificationSerializer(serializers.ModelSerializer):
    """Serializer for Notification model."""
    
    user_username = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = Notification
        fields = [
            'id', 'title', 'message', 'notification_type', 'priority',
            'channels', 'status', 'scheduled_at', 'sent_at', 'delivered_at',
            'read_at', 'expires_at', 'is_read', 'is_archived', 'is_starred',
            'action_url', 'action_text', 'related_object_type',
            'related_object_id', 'user_username', 'created_at'
        ]
        read_only_fields = ['id', 'sent_at', 'delivered_at', 'read_at', 'created_at']


class CampaignSummarySerializer(serializers.Serializer):
    """Serializer for campaign summary in advertiser response."""
    
    total_campaigns = serializers.IntegerField(read_only=True)
    active_campaigns = serializers.IntegerField(read_only=True)
    total_budget = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    current_spend = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    remaining_budget = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    budget_utilization = serializers.FloatField(read_only=True)


class PerformanceMetricsSerializer(serializers.Serializer):
    """Serializer for performance metrics."""
    
    total_impressions = serializers.IntegerField(read_only=True)
    total_clicks = serializers.IntegerField(read_only=True)
    total_conversions = serializers.IntegerField(read_only=True)
    total_cost = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    total_revenue = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    ctr = serializers.FloatField(read_only=True)
    cpc = serializers.FloatField(read_only=True)
    cpa = serializers.FloatField(read_only=True)
    conversion_rate = serializers.FloatField(read_only=True)
    roas = serializers.FloatField(read_only=True)
    roi = serializers.FloatField(read_only=True)


class AdvertiserPerformanceSerializer(serializers.Serializer):
    """Serializer for advertiser performance summary."""
    
    basic_info = serializers.DictField(read_only=True)
    campaign_summary = CampaignSummarySerializer(read_only=True)
    performance_metrics = PerformanceMetricsSerializer(read_only=True)
    quality_metrics = serializers.DictField(read_only=True)


# Response serializers for API responses

class AdvertiserListResponseSerializer(serializers.Serializer):
    """Serializer for advertiser list response."""
    
    advertisers = AdvertiserSerializer(many=True, read_only=True)
    total_count = serializers.IntegerField(read_only=True)
    page = serializers.IntegerField(read_only=True)
    page_size = serializers.IntegerField(read_only=True)
    total_pages = serializers.IntegerField(read_only=True)
    has_next = serializers.BooleanField(read_only=True)
    has_previous = serializers.BooleanField(read_only=True)


class AdvertiserDetailResponseSerializer(serializers.Serializer):
    """Serializer for advertiser detail response."""
    
    advertiser = AdvertiserDetailSerializer(read_only=True)
    performance = AdvertiserPerformanceSerializer(read_only=True)
    billing_profile = BillingProfileSerializer(read_only=True, required=False)


class VerificationResponseSerializer(serializers.Serializer):
    """Serializer for verification response."""
    
    verification = AdvertiserVerificationSerializer(read_only=True)
    message = serializers.CharField(read_only=True)
    success = serializers.BooleanField(read_only=True)


class UserListResponseSerializer(serializers.Serializer):
    """Serializer for user list response."""
    
    users = AdvertiserUserSerializer(many=True, read_only=True)
    total_count = serializers.IntegerField(read_only=True)
    page = serializers.IntegerField(read_only=True)
    page_size = serializers.IntegerField(read_only=True)
    total_pages = serializers.IntegerField(read_only=True)


class SettingsResponseSerializer(serializers.Serializer):
    """Serializer for settings response."""
    
    settings = serializers.DictField(read_only=True)
    message = serializers.CharField(read_only=True)


class ActionResponseSerializer(serializers.Serializer):
    """Serializer for action responses."""
    
    message = serializers.CharField(read_only=True)
    success = serializers.BooleanField(read_only=True)
    error = serializers.CharField(read_only=True, required=False)
