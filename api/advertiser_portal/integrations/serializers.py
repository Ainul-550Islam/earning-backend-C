"""
Integrations Serializers

This module provides comprehensive serializers for third-party integrations with
enterprise-grade validation, security, and performance optimization following
industry standards from Zapier, Segment, and MuleSoft.
"""

from typing import Optional, List, Dict, Any, Union, Tuple
from decimal import Decimal
from datetime import datetime, date, timedelta
from uuid import UUID
import json

from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models import Sum, Count, Avg, Q, F
from django.db.models.functions import Coalesce

from ..database_models.advertiser_model import Advertiser
from ..database_models.campaign_model import Campaign
from ..database_models.creative_model import Creative
from ..database_models.integration_model import (
    SocialMediaIntegration, AdNetworkIntegration, AnalyticsIntegration,
    PaymentIntegration, WebhookIntegration, APIIntegration
)
from ..models import AdvertiserPortalBaseModel
from ..enums import *
from ..utils import *
from ..validators import *
from ..exceptions import *

User = get_user_model()


class SocialMediaIntegrationSerializer(serializers.ModelSerializer):
    """
    Enterprise-grade serializer for SocialMediaIntegration model.
    
    Features:
    - Comprehensive field validation
    - Security checks and sanitization
    - Performance optimization
    - Type-safe Python code
    """
    
    advertiser_name = serializers.CharField(source='advertiser.company_name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    updated_by_name = serializers.CharField(source='updated_by.username', read_only=True)
    last_sync_formatted = serializers.SerializerMethodField()
    
    class Meta:
        model = SocialMediaIntegration
        fields = [
            'id', 'advertiser', 'advertiser_name', 'platform', 'account_id',
            'account_name', 'credentials', 'settings', 'sync_frequency',
            'is_active', 'last_sync', 'last_sync_formatted',
            'created_at', 'updated_at', 'created_by', 'created_by_name',
            'updated_by', 'updated_by_name'
        ]
        read_only_fields = [
            'id', 'account_id', 'last_sync', 'last_sync_formatted',
            'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
    
    def get_last_sync_formatted(self, obj: SocialMediaIntegration) -> str:
        """Get formatted last sync time."""
        try:
            if obj.last_sync:
                return obj.last_sync.strftime('%Y-%m-%d %H:%M:%S UTC')
            return 'Never'
        except Exception:
            return 'Unknown'
    
    def validate_platform(self, value: str) -> str:
        """Validate platform with security checks."""
        valid_platforms = ['facebook', 'instagram', 'twitter', 'linkedin', 'tiktok']
        if value not in valid_platforms:
            raise serializers.ValidationError(f"Invalid platform. Must be one of: {valid_platforms}")
        return value
    
    def validate_credentials(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate credentials with security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Credentials must be a dictionary")
        
        # Security: Check for prohibited content
        credentials_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
            r'data:text/html',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, credentials_str, re.IGNORECASE):
                raise serializers.ValidationError("Credentials contain prohibited content")
        
        return value
    
    def validate_settings(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate settings with security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Settings must be a dictionary")
        
        # Security: Check for prohibited content
        settings_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, settings_str, re.IGNORECASE):
                raise serializers.ValidationError("Settings contain prohibited content")
        
        return value
    
    def validate_sync_frequency(self, value: int) -> int:
        """Validate sync frequency."""
        if not isinstance(value, int) or value < 60:  # Minimum 1 minute
            raise serializers.ValidationError("Sync frequency must be at least 60 seconds")
        
        if value > 86400:  # Maximum 24 hours
            raise serializers.ValidationError("Sync frequency cannot exceed 86400 seconds")
        
        return value
    
    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Comprehensive validation with business logic checks."""
        # Security: Validate advertiser access
        advertiser = attrs.get('advertiser')
        if advertiser and hasattr(self, 'context') and 'request' in self.context:
            user = self.context['request'].user
            if not user.is_superuser and advertiser.user != user:
                raise serializers.ValidationError("User does not have access to this advertiser")
        
        # Business logic: Validate platform-specific requirements
        platform = attrs.get('platform')
        credentials = attrs.get('credentials', {})
        settings = attrs.get('settings', {})
        
        if platform == 'facebook':
            required_creds = ['access_token', 'app_id', 'app_secret']
            for cred in required_creds:
                if cred not in credentials:
                    raise serializers.ValidationError(f"Facebook integration requires {cred}")
        
        elif platform == 'instagram':
            required_creds = ['access_token', 'user_id']
            for cred in required_creds:
                if cred not in credentials:
                    raise serializers.ValidationError(f"Instagram integration requires {cred}")
        
        elif platform == 'twitter':
            required_creds = ['api_key', 'api_secret', 'access_token', 'access_token_secret']
            for cred in required_creds:
                if cred not in credentials:
                    raise serializers.ValidationError(f"Twitter integration requires {cred}")
        
        elif platform == 'linkedin':
            required_creds = ['client_id', 'client_secret', 'access_token']
            for cred in required_creds:
                if cred not in credentials:
                    raise serializers.ValidationError(f"LinkedIn integration requires {cred}")
        
        elif platform == 'tiktok':
            required_creds = ['app_id', 'app_secret', 'access_token']
            for cred in required_creds:
                if cred not in credentials:
                    raise serializers.ValidationError(f"TikTok integration requires {cred}")
        
        return attrs


class SocialMediaIntegrationCreateSerializer(serializers.Serializer):
    """
    Enterprise-grade serializer for creating social media integrations.
    
    Features:
    - Comprehensive input validation
    - Security checks and sanitization
    - Performance optimization
    - Type-safe Python code
    """
    
    platform = serializers.ChoiceField(
        choices=['facebook', 'instagram', 'twitter', 'linkedin', 'tiktok'],
        required=True
    )
    advertiser_id = serializers.UUIDField(required=False, allow_null=True)
    credentials = serializers.JSONField(required=True)
    settings = serializers.JSONField(required=False, default=dict)
    sync_frequency = serializers.IntegerField(required=False, default=3600)
    
    def validate_platform(self, value: str) -> str:
        """Validate platform with comprehensive security checks."""
        valid_platforms = ['facebook', 'instagram', 'twitter', 'linkedin', 'tiktok']
        if value not in valid_platforms:
            raise serializers.ValidationError(f"Invalid platform. Must be one of: {valid_platforms}")
        return value
    
    def validate_advertiser_id(self, value: Optional[UUID]) -> Optional[UUID]:
        """Validate advertiser ID with security checks."""
        if value is not None:
            try:
                advertiser = Advertiser.objects.get(id=value, is_deleted=False)
                
                # Security: Check user permissions
                if hasattr(self, 'context') and 'request' in self.context:
                    user = self.context['request'].user
                    if not user.is_superuser and advertiser.user != user:
                        raise serializers.ValidationError("User does not have access to this advertiser")
                
                return value
                
            except Advertiser.DoesNotExist:
                raise serializers.ValidationError("Advertiser not found")
            except ValueError:
                raise serializers.ValidationError("Invalid advertiser ID format")
        
        return value
    
    def validate_credentials(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate credentials with comprehensive security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Credentials must be a dictionary")
        
        # Security: Check for prohibited content
        credentials_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',  # Script tags
            r'javascript:',              # JavaScript protocol
            r'on\w+\s*=',               # Event handlers
            r'data:text/html',           # Data protocol
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, credentials_str, re.IGNORECASE):
                raise serializers.ValidationError("Credentials contain prohibited content")
        
        # Validate credentials structure
        platform = self.initial_data.get('platform')
        if platform == 'facebook':
            required_creds = ['access_token', 'app_id', 'app_secret']
            for cred in required_creds:
                if cred not in value:
                    raise serializers.ValidationError(f"Facebook integration requires {cred}")
            
            # Validate access token format
            access_token = value.get('access_token')
            if not isinstance(access_token, str) or len(access_token) < 10:
                raise serializers.ValidationError("Invalid Facebook access token format")
        
        elif platform == 'instagram':
            required_creds = ['access_token', 'user_id']
            for cred in required_creds:
                if cred not in value:
                    raise serializers.ValidationError(f"Instagram integration requires {cred}")
        
        elif platform == 'twitter':
            required_creds = ['api_key', 'api_secret', 'access_token', 'access_token_secret']
            for cred in required_creds:
                if cred not in value:
                    raise serializers.ValidationError(f"Twitter integration requires {cred}")
        
        elif platform == 'linkedin':
            required_creds = ['client_id', 'client_secret', 'access_token']
            for cred in required_creds:
                if cred not in value:
                    raise serializers.ValidationError(f"LinkedIn integration requires {cred}")
        
        elif platform == 'tiktok':
            required_creds = ['app_id', 'app_secret', 'access_token']
            for cred in required_creds:
                if cred not in value:
                    raise serializers.ValidationError(f"TikTok integration requires {cred}")
        
        return value
    
    def validate_settings(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate settings with comprehensive security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Settings must be a dictionary")
        
        # Security: Check for prohibited content
        settings_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
            r'data:text/html',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, settings_str, re.IGNORECASE):
                raise serializers.ValidationError("Settings contain prohibited content")
        
        # Validate settings structure
        valid_setting_keys = [
            'auto_sync', 'sync_pages', 'sync_posts', 'sync_analytics',
            'publish_permissions', 'webhook_url', 'custom_fields'
        ]
        
        for key in value.keys():
            if key not in valid_setting_keys:
                raise serializers.ValidationError(f"Invalid setting key: {key}")
        
        return value
    
    def validate_sync_frequency(self, value: int) -> int:
        """Validate sync frequency with business logic."""
        if not isinstance(value, int) or value < 60:  # Minimum 1 minute
            raise serializers.ValidationError("Sync frequency must be at least 60 seconds")
        
        if value > 86400:  # Maximum 24 hours
            raise serializers.ValidationError("Sync frequency cannot exceed 86400 seconds")
        
        # Validate common sync frequencies
        common_frequencies = [300, 600, 900, 1800, 3600, 7200, 14400, 28800, 43200, 86400]
        if value not in common_frequencies:
            raise serializers.ValidationError(f"Sync frequency should be one of: {common_frequencies}")
        
        return value
    
    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Comprehensive validation with business logic checks."""
        # Business logic: Validate platform vs settings
        platform = attrs.get('platform')
        settings = attrs.get('settings', {})
        
        if platform == 'facebook' and 'sync_pages' in settings:
            if not isinstance(settings['sync_pages'], bool):
                raise serializers.ValidationError("sync_pages must be a boolean")
        
        elif platform == 'instagram' and 'sync_stories' in settings:
            if not isinstance(settings['sync_stories'], bool):
                raise serializers.ValidationError("sync_stories must be a boolean")
        
        elif platform == 'twitter' and 'sync_tweets' in settings:
            if not isinstance(settings['sync_tweets'], bool):
                raise serializers.ValidationError("sync_tweets must be a boolean")
        
        # Business logic: Validate advertiser access
        advertiser_id = attrs.get('advertiser_id')
        if advertiser_id:
            try:
                advertiser = Advertiser.objects.get(id=advertiser_id, is_deleted=False)
                
                if hasattr(self, 'context') and 'request' in self.context:
                    user = self.context['request'].user
                    if not user.is_superuser and advertiser.user != user:
                        raise serializers.ValidationError("User does not have access to this advertiser")
                
            except Advertiser.DoesNotExist:
                raise serializers.ValidationError("Advertiser not found")
        
        return attrs


class AdNetworkIntegrationSerializer(serializers.ModelSerializer):
    """
    Enterprise-grade serializer for AdNetworkIntegration model.
    
    Features:
    - Comprehensive field validation
    - Security checks and sanitization
    - Performance optimization
    - Type-safe Python code
    """
    
    advertiser_name = serializers.CharField(source='advertiser.company_name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    updated_by_name = serializers.CharField(source='updated_by.username', read_only=True)
    last_sync_formatted = serializers.SerializerMethodField()
    
    class Meta:
        model = AdNetworkIntegration
        fields = [
            'id', 'advertiser', 'advertiser_name', 'network', 'account_id',
            'account_name', 'credentials', 'settings', 'sync_frequency',
            'is_active', 'last_sync', 'last_sync_formatted',
            'created_at', 'updated_at', 'created_by', 'created_by_name',
            'updated_by', 'updated_by_name'
        ]
        read_only_fields = [
            'id', 'account_id', 'last_sync', 'last_sync_formatted',
            'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
    
    def get_last_sync_formatted(self, obj: AdNetworkIntegration) -> str:
        """Get formatted last sync time."""
        try:
            if obj.last_sync:
                return obj.last_sync.strftime('%Y-%m-%d %H:%M:%S UTC')
            return 'Never'
        except Exception:
            return 'Unknown'
    
    def validate_network(self, value: str) -> str:
        """Validate network with security checks."""
        valid_networks = ['google_ads', 'facebook_ads', 'tiktok_ads', 'linkedin_ads', 'microsoft_ads']
        if value not in valid_networks:
            raise serializers.ValidationError(f"Invalid network. Must be one of: {valid_networks}")
        return value
    
    def validate_credentials(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate credentials with security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Credentials must be a dictionary")
        
        # Security: Check for prohibited content
        credentials_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
            r'data:text/html',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, credentials_str, re.IGNORECASE):
                raise serializers.ValidationError("Credentials contain prohibited content")
        
        return value
    
    def validate_settings(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate settings with security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Settings must be a dictionary")
        
        # Security: Check for prohibited content
        settings_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, settings_str, re.IGNORECASE):
                raise serializers.ValidationError("Settings contain prohibited content")
        
        return value
    
    def validate_sync_frequency(self, value: int) -> int:
        """Validate sync frequency."""
        if not isinstance(value, int) or value < 300:  # Minimum 5 minutes
            raise serializers.ValidationError("Sync frequency must be at least 300 seconds")
        
        if value > 3600:  # Maximum 1 hour
            raise serializers.ValidationError("Sync frequency cannot exceed 3600 seconds")
        
        return value
    
    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Comprehensive validation with business logic checks."""
        # Security: Validate advertiser access
        advertiser = attrs.get('advertiser')
        if advertiser and hasattr(self, 'context') and 'request' in self.context:
            user = self.context['request'].user
            if not user.is_superuser and advertiser.user != user:
                raise serializers.ValidationError("User does not have access to this advertiser")
        
        # Business logic: Validate network-specific requirements
        network = attrs.get('network')
        credentials = attrs.get('credentials', {})
        
        if network == 'google_ads':
            required_creds = ['developer_token', 'client_id', 'client_secret', 'refresh_token']
            for cred in required_creds:
                if cred not in credentials:
                    raise serializers.ValidationError(f"Google Ads integration requires {cred}")
        
        elif network == 'facebook_ads':
            required_creds = ['access_token', 'ad_account_id']
            for cred in required_creds:
                if cred not in credentials:
                    raise serializers.ValidationError(f"Facebook Ads integration requires {cred}")
        
        elif network == 'tiktok_ads':
            required_creds = ['app_id', 'app_secret', 'access_token', 'advertiser_id']
            for cred in required_creds:
                if cred not in credentials:
                    raise serializers.ValidationError(f"TikTok Ads integration requires {cred}")
        
        return attrs


class AdNetworkIntegrationCreateSerializer(serializers.Serializer):
    """
    Enterprise-grade serializer for creating ad network integrations.
    
    Features:
    - Comprehensive input validation
    - Security checks and sanitization
    - Performance optimization
    - Type-safe Python code
    """
    
    network = serializers.ChoiceField(
        choices=['google_ads', 'facebook_ads', 'tiktok_ads', 'linkedin_ads', 'microsoft_ads'],
        required=True
    )
    advertiser_id = serializers.UUIDField(required=False, allow_null=True)
    credentials = serializers.JSONField(required=True)
    settings = serializers.JSONField(required=False, default=dict)
    sync_frequency = serializers.IntegerField(required=False, default=1800)
    
    def validate_network(self, value: str) -> str:
        """Validate network with comprehensive security checks."""
        valid_networks = ['google_ads', 'facebook_ads', 'tiktok_ads', 'linkedin_ads', 'microsoft_ads']
        if value not in valid_networks:
            raise serializers.ValidationError(f"Invalid network. Must be one of: {valid_networks}")
        return value
    
    def validate_advertiser_id(self, value: Optional[UUID]) -> Optional[UUID]:
        """Validate advertiser ID with security checks."""
        if value is not None:
            try:
                advertiser = Advertiser.objects.get(id=value, is_deleted=False)
                
                # Security: Check user permissions
                if hasattr(self, 'context') and 'request' in self.context:
                    user = self.context['request'].user
                    if not user.is_superuser and advertiser.user != user:
                        raise serializers.ValidationError("User does not have access to this advertiser")
                
                return value
                
            except Advertiser.DoesNotExist:
                raise serializers.ValidationError("Advertiser not found")
            except ValueError:
                raise serializers.ValidationError("Invalid advertiser ID format")
        
        return value
    
    def validate_credentials(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate credentials with comprehensive security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Credentials must be a dictionary")
        
        # Security: Check for prohibited content
        credentials_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',  # Script tags
            r'javascript:',              # JavaScript protocol
            r'on\w+\s*=',               # Event handlers
            r'data:text/html',           # Data protocol
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, credentials_str, re.IGNORECASE):
                raise serializers.ValidationError("Credentials contain prohibited content")
        
        # Validate credentials structure
        network = self.initial_data.get('network')
        if network == 'google_ads':
            required_creds = ['developer_token', 'client_id', 'client_secret', 'refresh_token']
            for cred in required_creds:
                if cred not in value:
                    raise serializers.ValidationError(f"Google Ads integration requires {cred}")
        
        elif network == 'facebook_ads':
            required_creds = ['access_token', 'ad_account_id']
            for cred in required_creds:
                if cred not in value:
                    raise serializers.ValidationError(f"Facebook Ads integration requires {cred}")
        
        elif network == 'tiktok_ads':
            required_creds = ['app_id', 'app_secret', 'access_token', 'advertiser_id']
            for cred in required_creds:
                if cred not in value:
                    raise serializers.ValidationError(f"TikTok Ads integration requires {cred}")
        
        return value
    
    def validate_settings(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate settings with comprehensive security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Settings must be a dictionary")
        
        # Security: Check for prohibited content
        settings_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
            r'data:text/html',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, settings_str, re.IGNORECASE):
                raise serializers.ValidationError("Settings contain prohibited content")
        
        # Validate settings structure
        valid_setting_keys = [
            'auto_sync', 'sync_campaigns', 'sync_ad_groups', 'sync_ads',
            'sync_performance', 'auto_optimize', 'budget_alerts'
        ]
        
        for key in value.keys():
            if key not in valid_setting_keys:
                raise serializers.ValidationError(f"Invalid setting key: {key}")
        
        return value
    
    def validate_sync_frequency(self, value: int) -> int:
        """Validate sync frequency with business logic."""
        if not isinstance(value, int) or value < 300:  # Minimum 5 minutes
            raise serializers.ValidationError("Sync frequency must be at least 300 seconds")
        
        if value > 3600:  # Maximum 1 hour
            raise serializers.ValidationError("Sync frequency cannot exceed 3600 seconds")
        
        # Validate common sync frequencies
        common_frequencies = [300, 600, 900, 1800, 3600]
        if value not in common_frequencies:
            raise serializers.ValidationError(f"Sync frequency should be one of: {common_frequencies}")
        
        return value
    
    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Comprehensive validation with business logic checks."""
        # Business logic: Validate network vs settings
        network = attrs.get('network')
        settings = attrs.get('settings', {})
        
        if network == 'google_ads' and 'auto_optimize' in settings:
            if not isinstance(settings['auto_optimize'], bool):
                raise serializers.ValidationError("auto_optimize must be a boolean")
        
        elif network == 'facebook_ads' and 'budget_alerts' in settings:
            if not isinstance(settings['budget_alerts'], bool):
                raise serializers.ValidationError("budget_alerts must be a boolean")
        
        return attrs


class AnalyticsIntegrationSerializer(serializers.ModelSerializer):
    """
    Enterprise-grade serializer for AnalyticsIntegration model.
    
    Features:
    - Comprehensive field validation
    - Security checks and sanitization
    - Performance optimization
    - Type-safe Python code
    """
    
    advertiser_name = serializers.CharField(source='advertiser.company_name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    updated_by_name = serializers.CharField(source='updated_by.username', read_only=True)
    last_sync_formatted = serializers.SerializerMethodField()
    
    class Meta:
        model = AnalyticsIntegration
        fields = [
            'id', 'advertiser', 'advertiser_name', 'platform', 'account_id',
            'account_name', 'credentials', 'settings', 'sync_frequency',
            'is_active', 'last_sync', 'last_sync_formatted',
            'created_at', 'updated_at', 'created_by', 'created_by_name',
            'updated_by', 'updated_by_name'
        ]
        read_only_fields = [
            'id', 'account_id', 'last_sync', 'last_sync_formatted',
            'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
    
    def get_last_sync_formatted(self, obj: AnalyticsIntegration) -> str:
        """Get formatted last sync time."""
        try:
            if obj.last_sync:
                return obj.last_sync.strftime('%Y-%m-%d %H:%M:%S UTC')
            return 'Never'
        except Exception:
            return 'Unknown'
    
    def validate_platform(self, value: str) -> str:
        """Validate platform with security checks."""
        valid_platforms = ['google_analytics', 'adobe_analytics', 'mixpanel', 'segment']
        if value not in valid_platforms:
            raise serializers.ValidationError(f"Invalid platform. Must be one of: {valid_platforms}")
        return value
    
    def validate_credentials(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate credentials with security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Credentials must be a dictionary")
        
        # Security: Check for prohibited content
        credentials_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
            r'data:text/html',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, credentials_str, re.IGNORECASE):
                raise serializers.ValidationError("Credentials contain prohibited content")
        
        return value
    
    def validate_settings(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate settings with security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Settings must be a dictionary")
        
        # Security: Check for prohibited content
        settings_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, settings_str, re.IGNORECASE):
                raise serializers.ValidationError("Settings contain prohibited content")
        
        return value
    
    def validate_sync_frequency(self, value: int) -> int:
        """Validate sync frequency."""
        if not isinstance(value, int) or value < 600:  # Minimum 10 minutes
            raise serializers.ValidationError("Sync frequency must be at least 600 seconds")
        
        if value > 86400:  # Maximum 24 hours
            raise serializers.ValidationError("Sync frequency cannot exceed 86400 seconds")
        
        return value


class PaymentIntegrationSerializer(serializers.ModelSerializer):
    """
    Enterprise-grade serializer for PaymentIntegration model.
    
    Features:
    - Comprehensive field validation
    - Security checks and sanitization
    - Performance optimization
    - Type-safe Python code
    """
    
    advertiser_name = serializers.CharField(source='advertiser.company_name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    updated_by_name = serializers.CharField(source='updated_by.username', read_only=True)
    
    class Meta:
        model = PaymentIntegration
        fields = [
            'id', 'advertiser', 'advertiser_name', 'gateway', 'account_id',
            'account_name', 'credentials', 'settings', 'is_active',
            'created_at', 'updated_at', 'created_by', 'created_by_name',
            'updated_by', 'updated_by_name'
        ]
        read_only_fields = [
            'id', 'account_id', 'created_at', 'updated_at',
            'created_by', 'updated_by'
        ]
    
    def validate_gateway(self, value: str) -> str:
        """Validate gateway with security checks."""
        valid_gateways = ['stripe', 'paypal', 'square', 'braintree', 'adyen']
        if value not in valid_gateways:
            raise serializers.ValidationError(f"Invalid gateway. Must be one of: {valid_gateways}")
        return value
    
    def validate_credentials(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate credentials with security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Credentials must be a dictionary")
        
        # Security: Check for prohibited content
        credentials_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
            r'data:text/html',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, credentials_str, re.IGNORECASE):
                raise serializers.ValidationError("Credentials contain prohibited content")
        
        return value
    
    def validate_settings(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate settings with security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Settings must be a dictionary")
        
        # Security: Check for prohibited content
        settings_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, settings_str, re.IGNORECASE):
                raise serializers.ValidationError("Settings contain prohibited content")
        
        return value


class WebhookIntegrationSerializer(serializers.ModelSerializer):
    """
    Enterprise-grade serializer for WebhookIntegration model.
    
    Features:
    - Comprehensive field validation
    - Security checks and sanitization
    - Performance optimization
    - Type-safe Python code
    """
    
    advertiser_name = serializers.CharField(source='advertiser.company_name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    updated_by_name = serializers.CharField(source='updated_by.username', read_only=True)
    
    class Meta:
        model = WebhookIntegration
        fields = [
            'id', 'advertiser', 'advertiser_name', 'name', 'endpoint_url',
            'event_types', 'secret_key', 'settings', 'is_active',
            'created_at', 'updated_at', 'created_by', 'created_by_name',
            'updated_by', 'updated_by_name'
        ]
        read_only_fields = [
            'id', 'secret_key', 'created_at', 'updated_at',
            'created_by', 'updated_by'
        ]
    
    def validate_name(self, value: str) -> str:
        """Validate webhook name with security checks."""
        if not value or len(value.strip()) < 3:
            raise serializers.ValidationError("Webhook name must be at least 3 characters long")
        
        # Security: Sanitize input
        value = value.strip()
        
        # Check for prohibited characters
        prohibited_chars = ['<', '>', '&', '"', "'", '/', '\\']
        if any(char in value for char in prohibited_chars):
            raise serializers.ValidationError("Webhook name contains prohibited characters")
        
        return value
    
    def validate_endpoint_url(self, value: str) -> str:
        """Validate endpoint URL with security checks."""
        if not value:
            raise serializers.ValidationError("Endpoint URL is required")
        
        # Security: Validate URL format
        if not value.startswith(('http://', 'https://')):
            raise serializers.ValidationError("Endpoint URL must be a valid HTTP/HTTPS URL")
        
        # Security: Check for suspicious patterns
        suspicious_patterns = [
            r'<script',  # Script injection
            r'javascript:',  # JavaScript protocol
            r'data:',  # Data protocol
            r'file://',  # File protocol
        ]
        
        import re
        for pattern in suspicious_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                raise serializers.ValidationError("Endpoint URL contains suspicious content")
        
        return value
    
    def validate_event_types(self, value: List[str]) -> List[str]:
        """Validate event types with security checks."""
        if not isinstance(value, list):
            raise serializers.ValidationError("Event types must be a list")
        
        # Validate event type format
        valid_event_types = [
            'campaign.created', 'campaign.updated', 'campaign.deleted',
            'ad.created', 'ad.updated', 'ad.deleted',
            'payment.completed', 'payment.failed', 'payment.refunded',
            'user.created', 'user.updated', 'user.deleted',
            'integration.connected', 'integration.disconnected'
        ]
        
        for event_type in value:
            if event_type not in valid_event_types:
                raise serializers.ValidationError(f"Invalid event type: {event_type}")
        
        return value
    
    def validate_settings(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate settings with security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Settings must be a dictionary")
        
        # Security: Check for prohibited content
        settings_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, settings_str, re.IGNORECASE):
                raise serializers.ValidationError("Settings contain prohibited content")
        
        return value


class WebhookIntegrationCreateSerializer(serializers.Serializer):
    """
    Enterprise-grade serializer for creating webhook integrations.
    
    Features:
    - Comprehensive input validation
    - Security checks and sanitization
    - Performance optimization
    - Type-safe Python code
    """
    
    name = serializers.CharField(max_length=255, required=True)
    advertiser_id = serializers.UUIDField(required=False, allow_null=True)
    endpoint_url = serializers.URLField(required=True)
    event_types = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=[]
    )
    settings = serializers.JSONField(required=False, default=dict)
    
    def validate_name(self, value: str) -> str:
        """Validate webhook name with comprehensive security checks."""
        if not value or len(value.strip()) < 3:
            raise serializers.ValidationError("Webhook name must be at least 3 characters long")
        
        # Security: Sanitize input
        value = value.strip()
        
        # Check for prohibited characters and patterns
        prohibited_patterns = [
            r'<script.*?>.*?</script>',  # Script tags
            r'javascript:',              # JavaScript protocol
            r'on\w+\s*=',               # Event handlers
            r'data:text/html',           # Data protocol
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                raise serializers.ValidationError("Webhook name contains prohibited content")
        
        # Check for prohibited characters
        prohibited_chars = ['<', '>', '&', '"', "'", '/', '\\']
        if any(char in value for char in prohibited_chars):
            raise serializers.ValidationError("Webhook name contains prohibited characters")
        
        return value
    
    def validate_advertiser_id(self, value: Optional[UUID]) -> Optional[UUID]:
        """Validate advertiser ID with security checks."""
        if value is not None:
            try:
                advertiser = Advertiser.objects.get(id=value, is_deleted=False)
                
                # Security: Check user permissions
                if hasattr(self, 'context') and 'request' in self.context:
                    user = self.context['request'].user
                    if not user.is_superuser and advertiser.user != user:
                        raise serializers.ValidationError("User does not have access to this advertiser")
                
                return value
                
            except Advertiser.DoesNotExist:
                raise serializers.ValidationError("Advertiser not found")
            except ValueError:
                raise serializers.ValidationError("Invalid advertiser ID format")
        
        return value
    
    def validate_endpoint_url(self, value: str) -> str:
        """Validate endpoint URL with comprehensive security checks."""
        if not value:
            raise serializers.ValidationError("Endpoint URL is required")
        
        # Security: Validate URL format
        if not value.startswith(('http://', 'https://')):
            raise serializers.ValidationError("Endpoint URL must be a valid HTTP/HTTPS URL")
        
        # Security: Check for suspicious patterns
        suspicious_patterns = [
            r'<script',  # Script injection
            r'javascript:',  # JavaScript protocol
            r'data:',  # Data protocol
            r'file://',  # File protocol
            r'ftp://',  # FTP protocol
        ]
        
        import re
        for pattern in suspicious_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                raise serializers.ValidationError("Endpoint URL contains suspicious content")
        
        # Validate URL length
        if len(value) > 2048:
            raise serializers.ValidationError("Endpoint URL is too long")
        
        return value
    
    def validate_event_types(self, value: List[str]) -> List[str]:
        """Validate event types with comprehensive security checks."""
        if not isinstance(value, list):
            raise serializers.ValidationError("Event types must be a list")
        
        # Validate event type format
        valid_event_types = [
            'campaign.created', 'campaign.updated', 'campaign.deleted',
            'ad.created', 'ad.updated', 'ad.deleted',
            'payment.completed', 'payment.failed', 'payment.refunded',
            'user.created', 'user.updated', 'user.deleted',
            'integration.connected', 'integration.disconnected'
        ]
        
        for event_type in value:
            if not isinstance(event_type, str):
                raise serializers.ValidationError("Event types must be strings")
            
            if event_type not in valid_event_types:
                raise serializers.ValidationError(f"Invalid event type: {event_type}")
        
        # Check for duplicates
        if len(value) != len(set(value)):
            raise serializers.ValidationError("Event types must be unique")
        
        return value
    
    def validate_settings(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate settings with comprehensive security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Settings must be a dictionary")
        
        # Security: Check for prohibited content
        settings_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
            r'data:text/html',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, settings_str, re.IGNORECASE):
                raise serializers.ValidationError("Settings contain prohibited content")
        
        # Validate settings structure
        valid_setting_keys = [
            'retry_attempts', 'retry_delay', 'timeout', 'custom_headers',
            'signature_validation', 'ip_whitelist', 'rate_limiting'
        ]
        
        for key in value.keys():
            if key not in valid_setting_keys:
                raise serializers.ValidationError(f"Invalid setting key: {key}")
        
        # Validate specific settings
        if 'retry_attempts' in value:
            retry_attempts = value['retry_attempts']
            if not isinstance(retry_attempts, int) or retry_attempts < 0 or retry_attempts > 10:
                raise serializers.ValidationError("retry_attempts must be between 0 and 10")
        
        if 'retry_delay' in value:
            retry_delay = value['retry_delay']
            if not isinstance(retry_delay, int) or retry_delay < 1 or retry_delay > 3600:
                raise serializers.ValidationError("retry_delay must be between 1 and 3600 seconds")
        
        if 'timeout' in value:
            timeout = value['timeout']
            if not isinstance(timeout, int) or timeout < 1 or timeout > 300:
                raise serializers.ValidationError("timeout must be between 1 and 300 seconds")
        
        return value
    
    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Comprehensive validation with business logic checks."""
        # Business logic: Validate advertiser access
        advertiser_id = attrs.get('advertiser_id')
        if advertiser_id:
            try:
                advertiser = Advertiser.objects.get(id=advertiser_id, is_deleted=False)
                
                if hasattr(self, 'context') and 'request' in self.context:
                    user = self.context['request'].user
                    if not user.is_superuser and advertiser.user != user:
                        raise serializers.ValidationError("User does not have access to this advertiser")
                
            except Advertiser.DoesNotExist:
                raise serializers.ValidationError("Advertiser not found")
        
        # Business logic: Validate endpoint URL vs event types
        endpoint_url = attrs.get('endpoint_url')
        event_types = attrs.get('event_types', [])
        
        if endpoint_url and not event_types:
            raise serializers.ValidationError("At least one event type must be specified")
        
        return attrs


class APIIntegrationSerializer(serializers.ModelSerializer):
    """
    Enterprise-grade serializer for APIIntegration model.
    
    Features:
    - Comprehensive field validation
    - Security checks and sanitization
    - Performance optimization
    - Type-safe Python code
    """
    
    advertiser_name = serializers.CharField(source='advertiser.company_name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    updated_by_name = serializers.CharField(source='updated_by.username', read_only=True)
    
    class Meta:
        model = APIIntegration
        fields = [
            'id', 'advertiser', 'advertiser_name', 'name', 'base_url',
            'authentication_type', 'credentials', 'settings', 'is_active',
            'created_at', 'updated_at', 'created_by', 'created_by_name',
            'updated_by', 'updated_by_name'
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
    
    def validate_name(self, value: str) -> str:
        """Validate API integration name with security checks."""
        if not value or len(value.strip()) < 3:
            raise serializers.ValidationError("API integration name must be at least 3 characters long")
        
        # Security: Sanitize input
        value = value.strip()
        
        # Check for prohibited characters
        prohibited_chars = ['<', '>', '&', '"', "'", '/', '\\']
        if any(char in value for char in prohibited_chars):
            raise serializers.ValidationError("API integration name contains prohibited characters")
        
        return value
    
    def validate_base_url(self, value: str) -> str:
        """Validate base URL with security checks."""
        if not value:
            raise serializers.ValidationError("Base URL is required")
        
        # Security: Validate URL format
        if not value.startswith(('http://', 'https://')):
            raise serializers.ValidationError("Base URL must be a valid HTTP/HTTPS URL")
        
        # Security: Check for suspicious patterns
        suspicious_patterns = [
            r'<script',  # Script injection
            r'javascript:',  # JavaScript protocol
            r'data:',  # Data protocol
            r'file://',  # File protocol
        ]
        
        import re
        for pattern in suspicious_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                raise serializers.ValidationError("Base URL contains suspicious content")
        
        return value
    
    def validate_authentication_type(self, value: str) -> str:
        """Validate authentication type."""
        valid_auth_types = ['api_key', 'oauth2', 'basic', 'bearer', 'custom']
        if value not in valid_auth_types:
            raise serializers.ValidationError(f"Invalid authentication type. Must be one of: {valid_auth_types}")
        return value
    
    def validate_credentials(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate credentials with security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Credentials must be a dictionary")
        
        # Security: Check for prohibited content
        credentials_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
            r'data:text/html',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, credentials_str, re.IGNORECASE):
                raise serializers.ValidationError("Credentials contain prohibited content")
        
        return value
    
    def validate_settings(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate settings with security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Settings must be a dictionary")
        
        # Security: Check for prohibited content
        settings_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, settings_str, re.IGNORECASE):
                raise serializers.ValidationError("Settings contain prohibited content")
        
        return value


class APIIntegrationCreateSerializer(serializers.Serializer):
    """
    Enterprise-grade serializer for creating API integrations.
    
    Features:
    - Comprehensive input validation
    - Security checks and sanitization
    - Performance optimization
    - Type-safe Python code
    """
    
    name = serializers.CharField(max_length=255, required=True)
    advertiser_id = serializers.UUIDField(required=False, allow_null=True)
    base_url = serializers.URLField(required=True)
    authentication_type = serializers.ChoiceField(
        choices=['api_key', 'oauth2', 'basic', 'bearer', 'custom'],
        required=True
    )
    credentials = serializers.JSONField(required=False, default=dict)
    settings = serializers.JSONField(required=False, default=dict)
    
    def validate_name(self, value: str) -> str:
        """Validate API integration name with comprehensive security checks."""
        if not value or len(value.strip()) < 3:
            raise serializers.ValidationError("API integration name must be at least 3 characters long")
        
        # Security: Sanitize input
        value = value.strip()
        
        # Check for prohibited characters and patterns
        prohibited_patterns = [
            r'<script.*?>.*?</script>',  # Script tags
            r'javascript:',              # JavaScript protocol
            r'on\w+\s*=',               # Event handlers
            r'data:text/html',           # Data protocol
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                raise serializers.ValidationError("API integration name contains prohibited content")
        
        # Check for prohibited characters
        prohibited_chars = ['<', '>', '&', '"', "'", '/', '\\']
        if any(char in value for char in prohibited_chars):
            raise serializers.ValidationError("API integration name contains prohibited characters")
        
        return value
    
    def validate_advertiser_id(self, value: Optional[UUID]) -> Optional[UUID]:
        """Validate advertiser ID with security checks."""
        if value is not None:
            try:
                advertiser = Advertiser.objects.get(id=value, is_deleted=False)
                
                # Security: Check user permissions
                if hasattr(self, 'context') and 'request' in self.context:
                    user = self.context['request'].user
                    if not user.is_superuser and advertiser.user != user:
                        raise serializers.ValidationError("User does not have access to this advertiser")
                
                return value
                
            except Advertiser.DoesNotExist:
                raise serializers.ValidationError("Advertiser not found")
            except ValueError:
                raise serializers.ValidationError("Invalid advertiser ID format")
        
        return value
    
    def validate_base_url(self, value: str) -> str:
        """Validate base URL with comprehensive security checks."""
        if not value:
            raise serializers.ValidationError("Base URL is required")
        
        # Security: Validate URL format
        if not value.startswith(('http://', 'https://')):
            raise serializers.ValidationError("Base URL must be a valid HTTP/HTTPS URL")
        
        # Security: Check for suspicious patterns
        suspicious_patterns = [
            r'<script',  # Script injection
            r'javascript:',  # JavaScript protocol
            r'data:',  # Data protocol
            r'file://',  # File protocol
            r'ftp://',  # FTP protocol
        ]
        
        import re
        for pattern in suspicious_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                raise serializers.ValidationError("Base URL contains suspicious content")
        
        # Validate URL length
        if len(value) > 2048:
            raise serializers.ValidationError("Base URL is too long")
        
        return value
    
    def validate_authentication_type(self, value: str) -> str:
        """Validate authentication type with security checks."""
        valid_auth_types = ['api_key', 'oauth2', 'basic', 'bearer', 'custom']
        if value not in valid_auth_types:
            raise serializers.ValidationError(f"Invalid authentication type. Must be one of: {valid_auth_types}")
        return value
    
    def validate_credentials(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate credentials with comprehensive security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Credentials must be a dictionary")
        
        # Security: Check for prohibited content
        credentials_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
            r'data:text/html',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, credentials_str, re.IGNORECASE):
                raise serializers.ValidationError("Credentials contain prohibited content")
        
        # Validate credentials structure based on auth type
        auth_type = self.initial_data.get('authentication_type')
        if auth_type == 'api_key':
            required_creds = ['api_key', 'header_name']
            for cred in required_creds:
                if cred not in value:
                    raise serializers.ValidationError(f"API key authentication requires {cred}")
        
        elif auth_type == 'oauth2':
            required_creds = ['client_id', 'client_secret', 'token_url']
            for cred in required_creds:
                if cred not in value:
                    raise serializers.ValidationError(f"OAuth2 authentication requires {cred}")
        
        elif auth_type == 'basic':
            required_creds = ['username', 'password']
            for cred in required_creds:
                if cred not in value:
                    raise serializers.ValidationError(f"Basic authentication requires {cred}")
        
        elif auth_type == 'bearer':
            required_creds = ['token']
            for cred in required_creds:
                if cred not in value:
                    raise serializers.ValidationError(f"Bearer authentication requires {cred}")
        
        return value
    
    def validate_settings(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate settings with comprehensive security checks."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Settings must be a dictionary")
        
        # Security: Check for prohibited content
        settings_str = json.dumps(value)
        prohibited_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
            r'data:text/html',
        ]
        
        import re
        for pattern in prohibited_patterns:
            if re.search(pattern, settings_str, re.IGNORECASE):
                raise serializers.ValidationError("Settings contain prohibited content")
        
        # Validate settings structure
        valid_setting_keys = [
            'timeout', 'retry_attempts', 'retry_delay', 'custom_headers',
            'rate_limiting', 'response_format', 'data_transformation'
        ]
        
        for key in value.keys():
            if key not in valid_setting_keys:
                raise serializers.ValidationError(f"Invalid setting key: {key}")
        
        # Validate specific settings
        if 'timeout' in value:
            timeout = value['timeout']
            if not isinstance(timeout, int) or timeout < 1 or timeout > 300:
                raise serializers.ValidationError("timeout must be between 1 and 300 seconds")
        
        if 'retry_attempts' in value:
            retry_attempts = value['retry_attempts']
            if not isinstance(retry_attempts, int) or retry_attempts < 0 or retry_attempts > 10:
                raise serializers.ValidationError("retry_attempts must be between 0 and 10")
        
        if 'retry_delay' in value:
            retry_delay = value['retry_delay']
            if not isinstance(retry_delay, int) or retry_delay < 1 or retry_delay > 3600:
                raise serializers.ValidationError("retry_delay must be between 1 and 3600 seconds")
        
        return value
    
    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Comprehensive validation with business logic checks."""
        # Business logic: Validate advertiser access
        advertiser_id = attrs.get('advertiser_id')
        if advertiser_id:
            try:
                advertiser = Advertiser.objects.get(id=advertiser_id, is_deleted=False)
                
                if hasattr(self, 'context') and 'request' in self.context:
                    user = self.context['request'].user
                    if not user.is_superuser and advertiser.user != user:
                        raise serializers.ValidationError("User does not have access to this advertiser")
                
            except Advertiser.DoesNotExist:
                raise serializers.ValidationError("Advertiser not found")
        
        # Business logic: Validate authentication type vs credentials
        auth_type = attrs.get('authentication_type')
        credentials = attrs.get('credentials', {})
        
        if auth_type == 'api_key':
            if 'api_key' not in credentials:
                raise serializers.ValidationError("API key authentication requires api_key")
        
        elif auth_type == 'oauth2':
            required_creds = ['client_id', 'client_secret', 'token_url']
            for cred in required_creds:
                if cred not in credentials:
                    raise serializers.ValidationError(f"OAuth2 authentication requires {cred}")
        
        elif auth_type == 'basic':
            if 'username' not in credentials or 'password' not in credentials:
                raise serializers.ValidationError("Basic authentication requires username and password")
        
        elif auth_type == 'bearer':
            if 'token' not in credentials:
                raise serializers.ValidationError("Bearer authentication requires token")
        
        return attrs


# Request/Response Serializers for API Endpoints

class SocialMediaSyncRequestSerializer(serializers.Serializer):
    """Serializer for social media sync requests."""
    
    sync_type = serializers.ChoiceField(
        choices=['full', 'incremental', 'analytics', 'content'],
        default='full'
    )


class SocialMediaPublishRequestSerializer(serializers.Serializer):
    """Serializer for social media publish requests."""
    
    content_type = serializers.ChoiceField(
        choices=['text', 'image', 'video', 'carousel', 'story'],
        required=True
    )
    content = serializers.CharField(required=True)
    media_urls = serializers.ListField(
        child=serializers.URLField(),
        required=False,
        default=[]
    )
    schedule_time = serializers.DateTimeField(required=False, allow_null=True)
    targeting = serializers.JSONField(required=False, default=dict)


class AdNetworkSyncRequestSerializer(serializers.Serializer):
    """Serializer for ad network sync requests."""
    
    sync_type = serializers.ChoiceField(
        choices=['campaigns', 'ad_groups', 'ads', 'performance'],
        default='campaigns'
    )


class AdNetworkOptimizationRequestSerializer(serializers.Serializer):
    """Serializer for ad network optimization requests."""
    
    optimization_type = serializers.ChoiceField(
        choices=['bids', 'budget', 'targeting', 'creative'],
        required=True
    )
    target_metric = serializers.ChoiceField(
        choices=['cpa', 'roas', 'ctr', 'conversions'],
        required=True
    )
    target_value = serializers.DecimalField(max_digits=10, decimal_places=2, required=True)
    campaign_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        default=[]
    )


class AnalyticsEventRequestSerializer(serializers.Serializer):
    """Serializer for analytics event requests."""
    
    event_name = serializers.CharField(max_length=255, required=True)
    event_type = serializers.ChoiceField(
        choices=['pageview', 'event', 'transaction', 'user'],
        required=True
    )
    properties = serializers.JSONField(required=False, default=dict)
    user_id = serializers.UUIDField(required=False, allow_null=True)
    timestamp = serializers.DateTimeField(required=False, allow_null=True)


class PaymentProcessRequestSerializer(serializers.Serializer):
    """Serializer for payment processing requests."""
    
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=True)
    currency = serializers.CharField(max_length=3, default='USD')
    payment_method_id = serializers.CharField(required=True)
    description = serializers.CharField(required=False, allow_blank=True)
    metadata = serializers.JSONField(required=False, default=dict)


# Response Serializers

class SyncResultResponseSerializer(serializers.Serializer):
    """Serializer for sync result responses."""
    
    integration_id = serializers.UUIDField()
    sync_type = serializers.CharField()
    records_processed = serializers.IntegerField()
    records_created = serializers.IntegerField()
    records_updated = serializers.IntegerField()
    records_failed = serializers.IntegerField()
    errors = serializers.ListField()
    sync_timestamp = serializers.DateTimeField()
    duration = serializers.FloatField()


class IntegrationConnectionResponseSerializer(serializers.Serializer):
    """Serializer for integration connection responses."""
    
    integration_id = serializers.UUIDField()
    platform = serializers.CharField()
    account_id = serializers.CharField()
    account_name = serializers.CharField()
    is_active = serializers.BooleanField()
    sync_frequency = serializers.IntegerField()
    created_at = serializers.DateTimeField()


class PublishResultResponseSerializer(serializers.Serializer):
    """Serializer for publish result responses."""
    
    success = serializers.BooleanField()
    post_id = serializers.CharField()
    platform = serializers.CharField()
    url = serializers.URLField()
    published_at = serializers.DateTimeField()


class OptimizationResultResponseSerializer(serializers.Serializer):
    """Serializer for optimization result responses."""
    
    optimization_id = serializers.UUIDField()
    optimization_type = serializers.CharField()
    target_metric = serializers.CharField()
    target_value = serializers.DecimalField(max_digits=10, decimal_places=2)
    actual_value = serializers.DecimalField(max_digits=10, decimal_places=2)
    improvement_percentage = serializers.FloatField()
    optimized_campaigns = serializers.IntegerField()
    estimated_savings = serializers.DecimalField(max_digits=10, decimal_places=2)


class EventTrackingResponseSerializer(serializers.Serializer):
    """Serializer for event tracking responses."""
    
    success = serializers.BooleanField()
    event_id = serializers.CharField()
    event_name = serializers.CharField()
    tracked_at = serializers.DateTimeField()
    properties = serializers.JSONField()
