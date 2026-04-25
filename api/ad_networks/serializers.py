# api/ad_networks/serializers.py
# SaaS-Ready Multi-Tenant Serializers with Complete Coverage

from django.core.cache import cache
from rest_framework import serializers
from django.db import transaction
from django.contrib.auth import get_user_model
from decimal import Decimal, InvalidOperation
import uuid
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import Throttled, ValidationError
import hashlib
import hmac
import json
from django.utils import timezone
from django.db.models import Q, Count, Sum, Avg, F, Prefetch
from django.core.validators import RegexValidator
from django.conf import settings

from .models import (
    AdNetwork, OfferCategory, Offer, UserOfferEngagement,
    OfferConversion, OfferWall, AdNetworkWebhookLog,
    NetworkStatistic, UserOfferLimit, OfferSyncLog,
    SmartOfferRecommendation, OfferPerformanceAnalytics,
    FraudDetectionRule, BlacklistedIP, KnownBadIP, OfferClick,
    OfferReward, NetworkAPILog, OfferTag, OfferTagging,
    NetworkHealthCheck, OfferDailyLimit, OfferAttachment, UserWallet
)

User = get_user_model()

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_currency_symbol(currency_code):
    """Get currency symbol for display"""
    currency_map = {
        'BDT': 'BDT',
        'USD': 'USD',
        'EUR': 'EUR',
        'GBP': 'GBP',
        'INR': 'INR',
        'PKR': 'PKR',
        'JPY': 'JPY',
        'CNY': 'CNY',
        'CAD': 'CAD',
        'AUD': 'AUD',
    }
    return currency_map.get(currency_code.upper() if currency_code else 'USD', 'USD')

def validate_ip_address(ip):
    """Validate IP address format"""
    import ipaddress
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False

def validate_json_field(value):
    """Validate JSON field"""
    try:
        if isinstance(value, str):
            json.loads(value)
        elif isinstance(value, dict):
            json.dumps(value)
        else:
            raise ValueError("JSON must be string or dict")
        return True
    except (json.JSONDecodeError, ValueError):
        return False

def calculate_fraud_risk_score(data):
    """Calculate fraud risk score for given data"""
    score = 0
    
    # IP-based risk
    if 'ip_address' in data:
        ip = data['ip_address']
        if BlacklistedIP.objects.filter(ip_address=ip, is_active=True).exists():
            score += 50
    
    # User behavior risk
    if 'user' in data:
        user = data['user']
        recent_engagements = UserOfferEngagement.objects.filter(
            user=user,
            created_at__gte=timezone.now() - timezone.timedelta(hours=1)
        ).count()
        if recent_engagements > 10:
            score += 30
    
    # Device-based risk
    if 'device_info' in data:
        device_info = data['device_info']
        if device_info.get('is_emulator', False):
            score += 25
    
    return min(score, 100)  # Cap at 100

# ============================================================================
# CUSTOM FIELD SERIALIZERS
# ============================================================================

class DecimalField(serializers.DecimalField):
    """Custom Decimal field with better validation"""
    
    def to_internal_value(self, data):
        try:
            if isinstance(data, str):
                data = data.strip().replace(',', '')
            return Decimal(str(data))
        except (InvalidOperation, ValueError, TypeError) as e:
            raise serializers.ValidationError(
                f"Invalid decimal value. {str(e)}"
            )
    
    def to_representation(self, value):
        if value is None:
            return None
        return float(value)

class UUIDField(serializers.Field):
    """Custom UUID field for better validation"""
    
    def to_internal_value(self, data):
        try:
            return uuid.UUID(str(data))
        except (ValueError, AttributeError, TypeError) as e:
            raise serializers.ValidationError(f"Invalid UUID: {str(e)}")
    
    def to_representation(self, value):
        if value is None:
            return None
        return str(value)

class CurrencyDecimalField(DecimalField):
    """Enhanced Decimal field with currency formatting"""
    
    def __init__(self, *args, **kwargs):
        self.currency = kwargs.pop('currency', None)
        self.show_currency_symbol = kwargs.pop('show_currency_symbol', False)
        super().__init__(*args, **kwargs)
    
    def to_representation(self, value):
        if value is None:
            return None
        
        decimal_value = super().to_representation(value)
        
        if self.show_currency_symbol and self.currency:
            symbol = get_currency_symbol(self.currency)
            return f"{symbol}{decimal_value}"
        
        return decimal_value

class JSONField(serializers.JSONField):
    """Enhanced JSON field with validation"""
    
    def to_internal_value(self, data):
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                raise serializers.ValidationError("Invalid JSON string")
        
        # Validate JSON structure
        if not isinstance(data, (dict, list)):
            raise serializers.ValidationError("JSON must be object or array")
        
        return super().to_internal_value(data)

class IPAddressField(serializers.CharField):
    """Custom IP Address field with validation"""
    
    def to_internal_value(self, data):
        if not validate_ip_address(data):
            raise serializers.ValidationError("Invalid IP address format")
        return data

class TenantAwareField(serializers.Field):
    """Field that automatically includes tenant_id"""
    
    def __init__(self, **kwargs):
        self.read_only = kwargs.pop('read_only', True)
        super().__init__(**kwargs)
    
    def get_attribute(self, instance):
        return getattr(instance, 'tenant_id', 'default')
    
    def to_representation(self, value):
        return value

# ============================================================================
# BASE SERIALIZER CLASSES
# ============================================================================

class BaseTenantSerializer(serializers.ModelSerializer):
    """
    Base serializer with tenant support
    """
    tenant_id = TenantAwareField(read_only=True)
    
    def __init__(self, *args, **kwargs):
        self.tenant_id = kwargs.pop('tenant_id', 'default')
        super().__init__(*args, **kwargs)
    
    def create(self, validated_data):
        """Add tenant_id to created objects"""
        if hasattr(self.Meta.model, 'tenant_id'):
            validated_data['tenant_id'] = self.tenant_id
        return super().create(validated_data)

class BaseFraudSerializer(BaseTenantSerializer):
    """
    Base serializer with fraud detection
    """
    fraud_score = serializers.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        read_only=True,
        help_text="Fraud risk score (0-100)"
    )
    
    def validate(self, attrs):
        """Perform fraud validation"""
        data = dict(attrs)
        if hasattr(self, 'context') and 'request' in self.context:
            data['user'] = self.context['request'].user
        
        fraud_score = calculate_fraud_risk_score(data)
        attrs['fraud_score'] = fraud_score
        
        # Check if fraud score exceeds threshold
        if fraud_score > 80:
            raise ValidationError(
                "High fraud risk detected. Action blocked.",
                code='fraud_detected'
            )
        
        return attrs

# ============================================================================
# AD NETWORK SERIALIZERS
# ============================================================================

class AdNetworkSerializer(BaseTenantSerializer):
    """
    SaaS-Ready Ad Network Serializer
    """
    logo_url = serializers.SerializerMethodField()
    active_offers_count = serializers.SerializerMethodField()
    total_conversions = serializers.SerializerMethodField()
    health_status = serializers.SerializerMethodField()
    
    class Meta:
        model = AdNetwork
        fields = [
            'id', 'tenant_id', 'name', 'network_type', 'logo_url',
            'description', 'api_key', 'api_secret', 'webhook_url',
            'is_active', 'priority', 'config', 'active_offers_count',
            'total_conversions', 'health_status', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'tenant_id', 'created_at', 'updated_at',
            'active_offers_count', 'total_conversions', 'health_status'
        ]
        extra_kwargs = {
            'api_secret': {'write_only': True},
            'config': {'required': False}
        }
    
    def get_logo_url(self, obj):
        """Get logo URL with fallback"""
        if hasattr(obj, 'logo') and obj.logo:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.logo.url)
        return f"https://ui-avatars.com/api/?name={obj.name}&background=random"
    
    def get_active_offers_count(self, obj):
        """Get count of active offers"""
        return Offer.objects.filter(
            ad_network=obj,
            status='active',
            tenant_id=obj.tenant_id
        ).count()
    
    def get_total_conversions(self, obj):
        """Get total conversions for network"""
        return UserOfferEngagement.objects.filter(
            offer__ad_network=obj,
            status__in=['completed', 'approved'],
            tenant_id=obj.tenant_id
        ).count()
    
    def get_health_status(self, obj):
        """Get network health status"""
        latest_check = NetworkHealthCheck.objects.filter(
            network=obj,
            tenant_id=obj.tenant_id
        ).order_by('-checked_at').first()
        
        if not latest_check:
            return {'status': 'unknown', 'message': 'No health checks performed'}
        
        return {
            'status': 'healthy' if latest_check.is_healthy else 'unhealthy',
            'message': latest_check.error or 'Network is operational',
            'last_checked': latest_check.checked_at,
            'response_time': latest_check.response_time_ms
        }
    
    def validate_api_key(self, value):
        """Validate API key format"""
        if not value or len(value) < 10:
            raise serializers.ValidationError("API key must be at least 10 characters long")
        return value
    
    def validate_config(self, value):
        """Validate configuration JSON"""
        if value and not validate_json_field(value):
            raise serializers.ValidationError("Configuration must be valid JSON")
        return value

class AdNetworkDetailSerializer(AdNetworkSerializer):
    """Detailed Ad Network Serializer with additional fields"""
    
    recent_offers = serializers.SerializerMethodField()
    performance_stats = serializers.SerializerMethodField()
    webhook_logs = serializers.SerializerMethodField()
    
    class Meta(AdNetworkSerializer.Meta):
        fields = AdNetworkSerializer.Meta.fields + [
            'recent_offers', 'performance_stats', 'webhook_logs'
        ]
    
    def get_recent_offers(self, obj):
        """Get recent offers for this network"""
        offers = Offer.objects.filter(
            ad_network=obj,
            tenant_id=obj.tenant_id
        ).order_by('-created_at')[:5]
        
        return OfferListSerializer(
            offers,
            many=True,
            context=self.context
        ).data
    
    def get_performance_stats(self, obj):
        """Get performance statistics"""
        last_30_days = timezone.now() - timezone.timedelta(days=30)
        
        stats = UserOfferEngagement.objects.filter(
            offer__ad_network=obj,
            tenant_id=obj.tenant_id,
            created_at__gte=last_30_days
        ).aggregate(
            total_clicks=Count('id'),
            total_conversions=Count('id', filter=Q(status__in=['completed', 'approved'])),
            total_revenue=Sum('reward_earned', filter=Q(status='approved')),
            avg_conversion_time=Avg('completed_at' - 'started_at', filter=Q(status='completed'))
        )
        
        conversion_rate = 0
        if stats['total_clicks'] > 0:
            conversion_rate = (stats['total_conversions'] / stats['total_clicks']) * 100
        
        return {
            'total_clicks': stats['total_clicks'] or 0,
            'total_conversions': stats['total_conversions'] or 0,
            'total_revenue': float(stats['total_revenue'] or 0),
            'conversion_rate': round(conversion_rate, 2),
            'avg_conversion_time': str(stats['avg_conversion_time'] or timezone.timedelta(0))
        }
    
    def get_webhook_logs(self, obj):
        """Get recent webhook logs"""
        logs = AdNetworkWebhookLog.objects.filter(
            ad_network=obj,
            tenant_id=obj.tenant_id
        ).order_by('-created_at')[:5]
        
        return [
            {
                'id': log.id,
                'event_type': log.event_type,
                'processed': log.processed,
                'created_at': log.created_at
            }
            for log in logs
        ]

# ============================================================================
# OFFER CATEGORY SERIALIZERS
# ============================================================================

class OfferCategorySerializer(BaseTenantSerializer):
    """
    SaaS-Ready Offer Category Serializer
    """
    offers_count = serializers.SerializerMethodField()
    total_conversions = serializers.SerializerMethodField()
    avg_reward = serializers.SerializerMethodField()
    
    class Meta:
        model = OfferCategory
        fields = [
            'id', 'tenant_id', 'name', 'slug', 'description', 'icon',
            'color', 'category_type', 'is_active', 'is_featured',
            'order', 'config', 'offers_count', 'total_conversions',
            'avg_reward', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'tenant_id', 'created_at', 'updated_at',
            'offers_count', 'total_conversions', 'avg_reward'
        ]
    
    def get_offers_count(self, obj):
        """Get count of active offers in category"""
        return Offer.objects.filter(
            category=obj,
            status='active',
            tenant_id=obj.tenant_id
        ).count()
    
    def get_total_conversions(self, obj):
        """Get total conversions for category"""
        return UserOfferEngagement.objects.filter(
            offer__category=obj,
            status__in=['completed', 'approved'],
            tenant_id=obj.tenant_id
        ).count()
    
    def get_avg_reward(self, obj):
        """Get average reward amount for category"""
        avg_reward = Offer.objects.filter(
            category=obj,
            status='active',
            tenant_id=obj.tenant_id
        ).aggregate(avg_reward=Avg('reward_amount'))['avg_reward']
        
        return float(avg_reward) if avg_reward else 0
    
    def validate_color(self, value):
        """Validate color format"""
        if not value:
            return '#000000'
        
        if not value.startswith('#') or len(value) != 7:
            raise serializers.ValidationError("Color must be in hex format (#RRGGBB)")
        return value

# ============================================================================
# OFFER SERIALIZERS
# ============================================================================

class OfferSerializer(BaseTenantSerializer):
    """
    SaaS-Ready Offer Serializer with full validation
    """
    ad_network_name = serializers.CharField(source='ad_network.name', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    formatted_reward = serializers.SerializerMethodField()
    conversion_rate = serializers.SerializerMethodField()
    user_status = serializers.SerializerMethodField()
    time_remaining = serializers.SerializerMethodField()
    
    class Meta:
        model = Offer
        fields = [
            'id', 'tenant_id', 'title', 'description', 'ad_network',
            'category', 'ad_network_name', 'category_name',
            'reward_amount', 'reward_currency', 'formatted_reward',
            'difficulty', 'estimated_time', 'thumbnail', 'countries',
            'platforms', 'device_type', 'offer_type', 'requirements',
            'instructions', 'click_url', 'tracking_url', 'status',
            'is_featured', 'is_hot', 'priority', 'click_count',
            'total_conversions', 'conversion_rate', 'user_status',
            'time_remaining', 'config', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'tenant_id', 'created_at', 'updated_at',
            'ad_network_name', 'category_name', 'formatted_reward',
            'conversion_rate', 'user_status', 'time_remaining',
            'click_count', 'total_conversions'
        ]
    
    def get_formatted_reward(self, obj):
        """Get formatted reward amount with currency"""
        symbol = get_currency_symbol(obj.reward_currency)
        return f"{symbol}{obj.reward_amount}"
    
    def get_conversion_rate(self, obj):
        """Calculate conversion rate"""
        if obj.click_count == 0:
            return 0
        return round((obj.total_conversions / obj.click_count) * 100, 2)
    
    def get_user_status(self, obj):
        """Get user's engagement status for this offer"""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None
        
        engagement = UserOfferEngagement.objects.filter(
            user=request.user,
            offer=obj,
            tenant_id=obj.tenant_id
        ).first()
        
        return engagement.status if engagement else None
    
    def get_time_remaining(self, obj):
        """Get time remaining until offer expiry"""
        if not hasattr(obj, 'expires_at') or not obj.expires_at:
            return None
        
        remaining = obj.expires_at - timezone.now()
        if remaining.total_seconds() <= 0:
            return "Expired"
        
        days = remaining.days
        hours = remaining.seconds // 3600
        
        if days > 0:
            return f"{days} days {hours} hours"
        else:
            return f"{hours} hours"
    
    def validate_reward_amount(self, value):
        """Validate reward amount"""
        if value <= 0:
            raise serializers.ValidationError("Reward amount must be greater than 0")
        
        if value > 1000:  # Max reward limit
            raise serializers.ValidationError("Reward amount cannot exceed 1000")
        
        return value
    
    def validate_countries(self, value):
        """Validate countries list"""
        if not value:
            return []
        
        if not isinstance(value, list):
            raise serializers.ValidationError("Countries must be a list")
        
        # Validate country codes (basic validation)
        valid_countries = ['US', 'GB', 'CA', 'AU', 'BD', 'IN', 'PK', 'JP', 'CN', 'DE', 'FR']
        invalid_countries = [c for c in value if c not in valid_countries]
        
        if invalid_countries:
            raise serializers.ValidationError(
                f"Invalid country codes: {', '.join(invalid_countries)}"
            )
        
        return value
    
    def validate_platforms(self, value):
        """Validate platforms list"""
        if not value:
            return []
        
        if not isinstance(value, list):
            raise serializers.ValidationError("Platforms must be a list")
        
        valid_platforms = ['android', 'ios', 'web', 'desktop']
        invalid_platforms = [p for p in value if p not in valid_platforms]
        
        if invalid_platforms:
            raise serializers.ValidationError(
                f"Invalid platforms: {', '.join(invalid_platforms)}"
            )
        
        return value

class OfferDetailSerializer(OfferSerializer):
    """Detailed Offer Serializer with additional fields"""
    
    engagement_history = serializers.SerializerMethodField()
    similar_offers = serializers.SerializerMethodField()
    completion_stats = serializers.SerializerMethodField()
    
    class Meta(OfferSerializer.Meta):
        fields = OfferSerializer.Meta.fields + [
            'engagement_history', 'similar_offers', 'completion_stats'
        ]
    
    def get_engagement_history(self, obj):
        """Get user's engagement history for this offer"""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None
        
        engagements = UserOfferEngagement.objects.filter(
            user=request.user,
            offer=obj,
            tenant_id=obj.tenant_id
        ).order_by('-created_at')
        
        return UserOfferEngagementSerializer(
            engagements,
            many=True,
            context=self.context
        ).data
    
    def get_similar_offers(self, obj):
        """Get similar offers"""
        similar_offers = Offer.objects.filter(
            category=obj.category,
            status='active',
            tenant_id=obj.tenant_id
        ).exclude(id=obj.id)[:5]
        
        return OfferListSerializer(
            similar_offers,
            many=True,
            context=self.context
        ).data
    
    def get_completion_stats(self, obj):
        """Get completion statistics"""
        last_7_days = timezone.now() - timezone.timedelta(days=7)
        last_30_days = timezone.now() - timezone.timedelta(days=30)
        
        stats = UserOfferEngagement.objects.filter(
            offer=obj,
            tenant_id=obj.tenant_id,
            status__in=['completed', 'approved']
        ).aggregate(
            total_completed=Count('id'),
            completed_7d=Count('id', filter=Q(completed_at__gte=last_7_days)),
            completed_30d=Count('id', filter=Q(completed_at__gte=last_30_days)),
            avg_completion_time=Avg('completed_at' - 'started_at'),
            total_rewards=Sum('reward_earned')
        )
        
        return {
            'total_completed': stats['total_completed'] or 0,
            'completed_last_7_days': stats['completed_7d'] or 0,
            'completed_last_30_days': stats['completed_30d'] or 0,
            'avg_completion_time': str(stats['avg_completion_time'] or timezone.timedelta(0)),
            'total_rewards_paid': float(stats['total_rewards'] or 0)
        }

class OfferListSerializer(OfferSerializer):
    """Lightweight Offer Serializer for list views"""
    
    class Meta(OfferSerializer.Meta):
        fields = [
            'id', 'title', 'reward_amount', 'reward_currency',
            'formatted_reward', 'difficulty', 'estimated_time',
            'thumbnail', 'ad_network_name', 'category_name',
            'is_featured', 'is_hot', 'conversion_rate',
            'user_status', 'time_remaining'
        ]

# ============================================================================
# USER OFFER ENGAGEMENT SERIALIZERS
# ============================================================================

class UserOfferEngagementSerializer(BaseFraudSerializer):
    """
    SaaS-Ready User Offer Engagement Serializer with fraud detection
    """
    offer_title = serializers.CharField(source='offer.title', read_only=True)
    ad_network_name = serializers.CharField(source='offer.ad_network.name', read_only=True)
    category_name = serializers.CharField(source='offer.category.name', read_only=True)
    reward_formatted = serializers.SerializerMethodField()
    time_spent = serializers.SerializerMethodField()
    progress_percentage = serializers.SerializerMethodField()
    
    class Meta:
        model = UserOfferEngagement
        fields = [
            'id', 'tenant_id', 'user', 'offer', 'offer_title',
            'ad_network_name', 'category_name', 'click_id', 'status',
            'ip_address', 'user_agent', 'device_info', 'reward_earned',
            'reward_formatted', 'progress', 'progress_percentage',
            'started_at', 'completed_at', 'verified_at', 'rewarded_at',
            'rejection_reason', 'fraud_score', 'time_spent',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'tenant_id', 'created_at', 'updated_at',
            'verified_at', 'rewarded_at', 'fraud_score', 'time_spent'
        ]
    
    def get_reward_formatted(self, obj):
        """Get formatted reward amount"""
        if not obj.reward_earned:
            return None
        
        symbol = get_currency_symbol(obj.offer.reward_currency)
        return f"{symbol}{obj.reward_earned}"
    
    def get_time_spent(self, obj):
        """Calculate time spent on engagement"""
        if not obj.started_at:
            return None
        
        end_time = obj.completed_at or timezone.now()
        time_spent = end_time - obj.started_at
        
        hours = time_spent.seconds // 3600
        minutes = (time_spent.seconds % 3600) // 60
        
        if hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"
    
    def get_progress_percentage(self, obj):
        """Get progress as percentage"""
        return obj.progress or 0
    
    def validate_ip_address(self, value):
        """Validate IP address"""
        if not validate_ip_address(value):
            raise serializers.ValidationError("Invalid IP address format")
        return value
    
    def validate_status(self, value):
        """Validate status transition"""
        if not self.instance:
            return value  # New engagement
        
        current_status = self.instance.status
        
        # Define valid status transitions
        valid_transitions = {
            'clicked': ['started', 'expired'],
            'started': ['in_progress', 'completed', 'expired'],
            'in_progress': ['completed', 'expired'],
            'completed': ['approved', 'rejected'],
            'approved': ['rewarded'],
            'rejected': [],
            'expired': [],
            'rewarded': []
        }
        
        if value not in valid_transitions.get(current_status, []):
            raise serializers.ValidationError(
                f"Invalid status transition from {current_status} to {value}"
            )
        
        return value

class UserOfferEngagementDetailSerializer(UserOfferEngagementSerializer):
    """Detailed Engagement Serializer with additional fields"""
    
    conversion = serializers.SerializerMethodField()
    reward = serializers.SerializerMethodField()
    fraud_details = serializers.SerializerMethodField()
    
    class Meta(UserOfferEngagementSerializer.Meta):
        fields = UserOfferEngagementSerializer.Meta.fields + [
            'conversion', 'reward', 'fraud_details'
        ]
    
    def get_conversion(self, obj):
        """Get conversion details"""
        conversion = OfferConversion.objects.filter(
            engagement=obj,
            tenant_id=obj.tenant_id
        ).first()
        
        if not conversion:
            return None
        
        return OfferConversionSerializer(conversion, context=self.context).data
    
    def get_reward(self, obj):
        """Get reward details"""
        reward = OfferReward.objects.filter(
            engagement=obj,
            tenant_id=obj.tenant_id
        ).first()
        
        if not reward:
            return None
        
        return {
            'id': reward.id,
            'amount': float(reward.amount),
            'currency': reward.currency,
            'status': reward.status,
            'payment_reference': reward.payment_reference,
            'processed_at': reward.processed_at
        }
    
    def get_fraud_details(self, obj):
        """Get fraud detection details"""
        if not obj.fraud_score or obj.fraud_score < 50:
            return None
        
        return {
            'risk_level': 'high' if obj.fraud_score > 80 else 'medium',
            'score': float(obj.fraud_score),
            'factors': self._analyze_fraud_factors(obj)
        }
    
    def _analyze_fraud_factors(self, obj):
        """Analyze fraud factors for this engagement"""
        factors = []
        
        # Check IP-based factors
        if BlacklistedIP.objects.filter(ip_address=obj.ip_address, is_active=True).exists():
            factors.append('blacklisted_ip')
        
        # Check frequency factors
        recent_engagements = UserOfferEngagement.objects.filter(
            user=obj.user,
            created_at__gte=obj.created_at - timezone.timedelta(hours=1)
        ).count()
        
        if recent_engagements > 10:
            factors.append('high_frequency')
        
        # Check device factors
        if obj.device_info:
            device_info = obj.device_info
            if device_info.get('is_emulator'):
                factors.append('emulator_detected')
            if device_info.get('is_rooted'):
                factors.append('rooted_device')
        
        return factors

# ============================================================================
# OFFER CONVERSION SERIALIZERS
# ============================================================================

class OfferConversionSerializer(BaseTenantSerializer):
    """
    SaaS-Ready Offer Conversion Serializer
    """
    engagement_details = serializers.SerializerMethodField()
    user_info = serializers.SerializerMethodField()
    offer_info = serializers.SerializerMethodField()
    risk_assessment = serializers.SerializerMethodField()
    
    class Meta:
        model = OfferConversion
        fields = [
            'id', 'tenant_id', 'engagement', 'engagement_details',
            'user_info', 'offer_info', 'conversion_id', 'conversion_status',
            'payout', 'currency', 'commission', 'risk_level',
            'risk_assessment', 'is_verified', 'verified_by',
            'verified_at', 'chargeback_at', 'chargeback_reason',
            'chargeback_processed', 'tracking_data', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'tenant_id', 'created_at', 'updated_at',
            'engagement_details', 'user_info', 'offer_info',
            'risk_assessment', 'verified_by', 'verified_at'
        ]
    
    def get_engagement_details(self, obj):
        """Get engagement details"""
        engagement = obj.engagement
        return {
            'id': engagement.id,
            'click_id': engagement.click_id,
            'status': engagement.status,
            'ip_address': engagement.ip_address,
            'completed_at': engagement.completed_at
        }
    
    def get_user_info(self, obj):
        """Get user information"""
        user = obj.engagement.user
        return {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'join_date': user.date_joined
        }
    
    def get_offer_info(self, obj):
        """Get offer information"""
        offer = obj.engagement.offer
        return {
            'id': offer.id,
            'title': offer.title,
            'reward_amount': float(offer.reward_amount),
            'currency': offer.reward_currency,
            'ad_network': offer.ad_network.name
        }
    
    def get_risk_assessment(self, obj):
        """Get risk assessment details"""
        if obj.risk_level == 'low':
            return None
        
        return {
            'level': obj.risk_level,
            'factors': self._assess_risk_factors(obj),
            'recommendation': self._get_risk_recommendation(obj)
        }
    
    def _assess_risk_factors(self, obj):
        """Assess risk factors for conversion"""
        factors = []
        
        # Check engagement fraud score
        if obj.engagement.fraud_score > 50:
            factors.append('high_fraud_score')
        
        # Check IP reputation
        if BlacklistedIP.objects.filter(ip_address=obj.engagement.ip_address).exists():
            factors.append('suspicious_ip')
        
        # Check conversion speed
        if obj.engagement.completed_at and obj.engagement.started_at:
            completion_time = obj.engagement.completed_at - obj.engagement.started_at
            if completion_time.total_seconds() < 30:  # Too fast completion
                factors.append('too_fast_completion')
        
        return factors
    
    def _get_risk_recommendation(self, obj):
        """Get recommendation based on risk level"""
        recommendations = {
            'medium': 'Manual review recommended',
            'high': 'Manual verification required',
            'critical': 'Block and investigate'
        }
        return recommendations.get(obj.risk_level, 'No action needed')

# ============================================================================
# OFFER WALL SERIALIZERS
# ============================================================================

class OfferWallSerializer(BaseTenantSerializer):
    """
    SaaS-Ready Offer Wall Serializer
    """
    networks_info = serializers.SerializerMethodField()
    categories_info = serializers.SerializerMethodField()
    offers_count = serializers.SerializerMethodField()
    avg_reward = serializers.SerializerMethodField()
    
    class Meta:
        model = OfferWall
        fields = [
            'id', 'tenant_id', 'name', 'description', 'wall_type',
            'config', 'countries', 'min_payout', 'max_payout',
            'is_active', 'is_default', 'priority', 'networks_info',
            'categories_info', 'offers_count', 'avg_reward',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'tenant_id', 'created_at', 'updated_at',
            'networks_info', 'categories_info', 'offers_count', 'avg_reward'
        ]
    
    def get_networks_info(self, obj):
        """Get networks information"""
        networks = obj.ad_networks.filter(is_active=True, tenant_id=obj.tenant_id)
        return [
            {
                'id': network.id,
                'name': network.name,
                'logo_url': AdNetworkSerializer(network, context=self.context).get_logo_url(network)
            }
            for network in networks
        ]
    
    def get_categories_info(self, obj):
        """Get categories information"""
        categories = obj.categories.filter(is_active=True, tenant_id=obj.tenant_id)
        return [
            {
                'id': category.id,
                'name': category.name,
                'icon': category.icon,
                'color': category.color
            }
            for category in categories
        ]
    
    def get_offers_count(self, obj):
        """Get total offers count"""
        return Offer.objects.filter(
            ad_network__in=obj.ad_networks.all(),
            status='active',
            tenant_id=obj.tenant_id
        ).count()
    
    def get_avg_reward(self, obj):
        """Get average reward amount"""
        avg_reward = Offer.objects.filter(
            ad_network__in=obj.ad_networks.all(),
            status='active',
            tenant_id=obj.tenant_id
        ).aggregate(avg_reward=Avg('reward_amount'))['avg_reward']
        
        return float(avg_reward) if avg_reward else 0

# ============================================================================
# FRAUD DETECTION SERIALIZERS
# ============================================================================

class FraudDetectionRuleSerializer(BaseTenantSerializer):
    """
    SaaS-Ready Fraud Detection Rule Serializer
    """
    rule_type_display = serializers.CharField(source='get_rule_type_display', read_only=True)
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    severity_display = serializers.CharField(source='get_severity_display', read_only=True)
    is_active_display = serializers.SerializerMethodField()
    
    class Meta:
        model = FraudDetectionRule
        fields = [
            'id', 'tenant_id', 'name', 'description', 'rule_type',
            'rule_type_display', 'conditions', 'action', 'action_display',
            'severity', 'severity_display', 'is_active', 'is_active_display',
            'priority', 'config', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'tenant_id', 'created_at', 'updated_at',
            'rule_type_display', 'action_display', 'severity_display'
        ]
    
    def get_is_active_display(self, obj):
        """Get active status display"""
        return "Active" if obj.is_active else "Inactive"
    
    def validate_conditions(self, value):
        """Validate conditions JSON"""
        if not validate_json_field(value):
            raise serializers.ValidationError("Conditions must be valid JSON")
        
        # Validate required fields in conditions
        if isinstance(value, dict):
            if 'field' not in value:
                raise serializers.ValidationError("Conditions must include 'field'")
            if 'operator' not in value:
                raise serializers.ValidationError("Conditions must include 'operator'")
        
        return value
    
    def validate_priority(self, value):
        """Validate priority"""
        if value < 1 or value > 100:
            raise serializers.ValidationError("Priority must be between 1 and 100")
        return value

class BlacklistedIPSerializer(BaseTenantSerializer):
    """
    SaaS-Ready Blacklisted IP Serializer
    """
    reason_display = serializers.CharField(source='get_reason_display', read_only=True)
    is_active_display = serializers.SerializerMethodField()
    expiry_countdown = serializers.SerializerMethodField()
    threat_level = serializers.SerializerMethodField()
    
    class Meta:
        model = BlacklistedIP
        fields = [
            'id', 'tenant_id', 'ip_address', 'reason', 'reason_display',
            'is_active', 'is_active_display', 'expiry_date',
            'expiry_countdown', 'metadata', 'threat_level',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'tenant_id', 'created_at', 'updated_at',
            'reason_display', 'is_active_display', 'expiry_countdown',
            'threat_level'
        ]
    
    def get_is_active_display(self, obj):
        """Get active status display"""
        return "Active" if obj.is_active else "Inactive"
    
    def get_expiry_countdown(self, obj):
        """Get expiry countdown"""
        if not hasattr(obj, 'expiry_date') or not obj.expiry_date:
            return "Never"
        
        remaining = obj.expiry_date - timezone.now()
        if remaining.total_seconds() <= 0:
            return "Expired"
        
        days = remaining.days
        hours = remaining.seconds // 3600
        
        if days > 0:
            return f"{days} days {hours} hours"
        else:
            return f"{hours} hours"
    
    def get_threat_level(self, obj):
        """Calculate threat level"""
        base_score = 50
        
        # Increase score based on reason
        reason_scores = {
            'fraud': 30,
            'spam': 20,
            'abuse': 25,
            'malware': 35,
            'other': 10
        }
        
        score = base_score + reason_scores.get(obj.reason, 0)
        
        # Check if IP is in known bad IPs
        if KnownBadIP.objects.filter(ip_address=obj.ip_address).exists():
            score += 20
        
        return min(score, 100)

# ============================================================================
# MISSING SERIALIZERS - NOW INCLUDED
# ============================================================================

class KnownBadIPSerializer(BaseTenantSerializer):
    """
    SaaS-Ready Known Bad IP Serializer
    """
    threat_level_display = serializers.CharField(source='get_threat_level_display', read_only=True)
    source_display = serializers.CharField(source='get_source_display', read_only=True)
    
    class Meta:
        model = KnownBadIP
        fields = [
            'id', 'tenant_id', 'ip_address', 'threat_type', 'source', 'source_display',
            'confidence_score', 'threat_level_display', 'first_seen', 'last_seen',
            'is_active', 'description', 'metadata', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'tenant_id', 'created_at', 'updated_at',
            'first_seen', 'last_seen', 'threat_level_display', 'source_display'
        ]
    
    def validate_confidence_score(self, value):
        """Validate confidence score"""
        if not (0 <= value <= 100):
            raise serializers.ValidationError("Confidence score must be between 0 and 100")
        return value

class OfferClickSerializer(BaseTenantSerializer):
    """
    SaaS-Ready Offer Click Serializer
    """
    user_display = serializers.CharField(source='user.username', read_only=True)
    offer_title = serializers.CharField(source='offer.title', read_only=True)
    fraud_level = serializers.SerializerMethodField()
    
    class Meta:
        model = OfferClick
        fields = [
            'id', 'tenant_id', 'user', 'user_display', 'offer', 'offer_title',
            'click_id', 'ip_address', 'user_agent', 'device', 'browser',
            'is_unique', 'is_fraud', 'fraud_score', 'fraud_level',
            'clicked_at', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'tenant_id', 'created_at', 'updated_at',
            'user_display', 'offer_title', 'fraud_level'
        ]
    
    def get_fraud_level(self, obj):
        """Get fraud level based on score"""
        if obj.fraud_score >= 80:
            return 'high'
        elif obj.fraud_score >= 50:
            return 'medium'
        elif obj.fraud_score >= 20:
            return 'low'
        return 'none'
    
    def validate_ip_address(self, value):
        """Validate IP address"""
        import ipaddress
        try:
            ipaddress.ip_address(value)
            return value
        except ValueError:
            raise serializers.ValidationError("Invalid IP address format")

class OfferRewardSerializer(BaseTenantSerializer):
    """
    SaaS-Ready Offer Reward Serializer
    """
    user_display = serializers.CharField(source='user.username', read_only=True)
    offer_title = serializers.CharField(source='offer.title', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    formatted_amount = serializers.SerializerMethodField()
    
    class Meta:
        model = OfferReward
        fields = [
            'id', 'tenant_id', 'user', 'user_display', 'offer', 'offer_title',
            'engagement', 'amount', 'currency', 'formatted_amount', 'status',
            'status_display', 'payment_reference', 'transaction_id',
            'processed_at', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'tenant_id', 'created_at', 'updated_at',
            'user_display', 'offer_title', 'status_display', 'formatted_amount',
            'processed_at'
        ]
    
    def get_formatted_amount(self, obj):
        """Get formatted amount with currency"""
        symbol = get_currency_symbol(obj.currency)
        return f"{symbol}{obj.amount}"
    
    def validate_amount(self, value):
        """Validate amount"""
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than 0")
        return value

class NetworkAPILogSerializer(BaseTenantSerializer):
    """
    SaaS-Ready Network API Log Serializer
    """
    network_name = serializers.CharField(source='network.name', read_only=True)
    duration_ms = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()
    
    class Meta:
        model = NetworkAPILog
        fields = [
            'id', 'tenant_id', 'network', 'network_name', 'method', 'endpoint',
            'request_data', 'response_data', 'status_code', 'status_display',
            'duration_ms', 'is_success', 'error_message', 'request_timestamp',
            'response_timestamp', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'tenant_id', 'created_at', 'updated_at',
            'network_name', 'duration_ms', 'status_display'
        ]
    
    def get_duration_ms(self, obj):
        """Calculate duration in milliseconds"""
        if obj.request_timestamp and obj.response_timestamp:
            duration = obj.response_timestamp - obj.request_timestamp
            return int(duration.total_seconds() * 1000)
        return None
    
    def get_status_display(self, obj):
        """Get status display"""
        if obj.is_success:
            return "Success"
        else:
            return f"Error ({obj.status_code})"

class OfferTagSerializer(BaseTenantSerializer):
    """
    SaaS-Ready Offer Tag Serializer
    """
    usage_count = serializers.IntegerField(read_only=True)
    created_by_display = serializers.CharField(source='created_by.username', read_only=True)
    
    class Meta:
        model = OfferTag
        fields = [
            'id', 'tenant_id', 'name', 'slug', 'description', 'color',
            'is_active', 'is_featured', 'usage_count', 'created_by',
            'created_by_display', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'tenant_id', 'created_at', 'updated_at',
            'usage_count', 'created_by_display'
        ]
    
    def validate_color(self, value):
        """Validate color format"""
        if not value.startswith('#') or len(value) != 7:
            raise serializers.ValidationError("Color must be in hex format (#RRGGBB)")
        return value

class OfferTaggingSerializer(BaseTenantSerializer):
    """
    SaaS-Ready Offer Tagging Serializer
    """
    offer_title = serializers.CharField(source='offer.title', read_only=True)
    tag_name = serializers.CharField(source='tag.name', read_only=True)
    added_by_display = serializers.CharField(source='added_by.username', read_only=True)
    
    class Meta:
        model = OfferTagging
        fields = [
            'id', 'tenant_id', 'offer', 'offer_title', 'tag', 'tag_name',
            'added_by', 'added_by_display', 'is_auto_tagged',
            'confidence_score', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'tenant_id', 'created_at', 'updated_at',
            'offer_title', 'tag_name', 'added_by_display'
        ]
    
    def validate_confidence_score(self, value):
        """Validate confidence score"""
        if not (0 <= value <= 100):
            raise serializers.ValidationError("Confidence score must be between 0 and 100")
        return value

class NetworkHealthCheckSerializer(BaseTenantSerializer):
    """
    SaaS-Ready Network Health Check Serializer
    """
    network_name = serializers.CharField(source='network.name', read_only=True)
    check_type_display = serializers.CharField(source='get_check_type_display', read_only=True)
    status_display = serializers.SerializerMethodField()
    response_time_display = serializers.SerializerMethodField()
    
    class Meta:
        model = NetworkHealthCheck
        fields = [
            'id', 'tenant_id', 'network', 'network_name', 'check_type',
            'check_type_display', 'is_healthy', 'status_display',
            'status_code', 'response_time_ms', 'response_time_display',
            'error', 'error_type', 'check_data', 'created_at'
        ]
        read_only_fields = [
            'id', 'tenant_id', 'created_at', 'network_name',
            'check_type_display', 'status_display', 'response_time_display'
        ]
    
    def get_status_display(self, obj):
        """Get status display"""
        if obj.is_healthy:
            return "Healthy"
        else:
            return f"Unhealthy ({obj.status_code})"
    
    def get_response_time_display(self, obj):
        """Get response time display"""
        if obj.response_time_ms < 1000:
            return f"{obj.response_time_ms}ms"
        else:
            seconds = obj.response_time_ms / 1000
            return f"{seconds:.2f}s"

class OfferPerformanceAnalyticsSerializer(BaseTenantSerializer):
    """
    SaaS-Ready Offer Performance Analytics Serializer
    """
    offer_title = serializers.CharField(source='offer.title', read_only=True)
    performance_grade = serializers.SerializerMethodField()
    trend_indicator = serializers.SerializerMethodField()
    
    class Meta:
        model = OfferPerformanceAnalytics
        fields = [
            'id', 'tenant_id', 'offer', 'offer_title', 'date',
            'clicks', 'conversions', 'revenue', 'cost', 'profit',
            'conversion_rate', 'avg_session_duration', 'bounce_rate',
            'performance_grade', 'trend_indicator', 'created_at'
        ]
        read_only_fields = [
            'id', 'tenant_id', 'created_at', 'offer_title',
            'performance_grade', 'trend_indicator'
        ]
    
    def get_performance_grade(self, obj):
        """Calculate performance grade"""
        if not obj.conversion_rate:
            return "N/A"
        
        if obj.conversion_rate >= 10:
            return "A+"
        elif obj.conversion_rate >= 7:
            return "A"
        elif obj.conversion_rate >= 5:
            return "B"
        elif obj.conversion_rate >= 3:
            return "C"
        else:
            return "D"
    
    def get_trend_indicator(self, obj):
        """Get trend indicator"""
        # This would typically compare with previous period
        # For now, return a simple indicator
        if obj.profit > 0:
            return "up"
        elif obj.profit < 0:
            return "down"
        else:
            return "stable"

class SmartOfferRecommendationSerializer(BaseTenantSerializer):
    """
    SaaS-Ready Smart Offer Recommendation Serializer
    """
    user_display = serializers.CharField(source='user.username', read_only=True)
    offer_title = serializers.CharField(source='offer.title', read_only=True)
    reward_amount = serializers.DecimalField(source='offer.reward_amount', read_only=True, max_digits=10, decimal_places=2)
    reward_currency = serializers.CharField(source='offer.reward_currency', read_only=True)
    
    class Meta:
        model = SmartOfferRecommendation
        fields = [
            'id', 'tenant_id', 'user', 'user_display', 'offer', 'offer_title',
            'reward_amount', 'reward_currency', 'score', 'is_displayed',
            'is_clicked', 'is_converted', 'clicked_at', 'converted_at',
            'recommendation_data', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'tenant_id', 'created_at', 'updated_at',
            'user_display', 'offer_title', 'reward_amount', 'reward_currency',
            'clicked_at', 'converted_at'
        ]
    
    def validate_score(self, value):
        """Validate score"""
        if not (0 <= value <= 100):
            raise serializers.ValidationError("Score must be between 0 and 100")
        return value

class NetworkStatisticSerializer(BaseTenantSerializer):
    """
    SaaS-Ready Network Statistic Serializer
    """
    network_name = serializers.CharField(source='network.name', read_only=True)
    conversion_rate = serializers.SerializerMethodField()
    avg_payout = serializers.SerializerMethodField()
    
    class Meta:
        model = NetworkStatistic
        fields = [
            'id', 'tenant_id', 'network', 'network_name', 'date',
            'clicks', 'conversions', 'payout', 'commission',
            'conversion_rate', 'avg_payout', 'revenue', 'cost',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'tenant_id', 'created_at', 'updated_at',
            'network_name', 'conversion_rate', 'avg_payout'
        ]
    
    def get_conversion_rate(self, obj):
        """Calculate conversion rate"""
        if obj.clicks == 0:
            return 0
        return round((obj.conversions / obj.clicks) * 100, 2)
    
    def get_avg_payout(self, obj):
        """Calculate average payout"""
        if obj.conversions == 0:
            return 0
        return round(obj.payout / obj.conversions, 2)

class UserOfferLimitSerializer(BaseTenantSerializer):
    """
    SaaS-Ready User Offer Limit Serializer
    """
    user_display = serializers.CharField(source='user.username', read_only=True)
    offer_title = serializers.CharField(source='offer.title', read_only=True)
    is_limit_reached = serializers.SerializerMethodField()
    
    class Meta:
        model = UserOfferLimit
        fields = [
            'id', 'tenant_id', 'user', 'user_display', 'offer', 'offer_title',
            'daily_count', 'daily_limit', 'total_count', 'is_limit_reached',
            'last_completed', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'tenant_id', 'created_at', 'updated_at',
            'user_display', 'offer_title', 'is_limit_reached'
        ]
    
    def get_is_limit_reached(self, obj):
        """Check if limit is reached"""
        return obj.daily_count >= obj.daily_limit

class OfferSyncLogSerializer(BaseTenantSerializer):
    """
    SaaS-Ready Offer Sync Log Serializer
    """
    network_name = serializers.CharField(source='ad_network.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    duration_display = serializers.SerializerMethodField()
    
    class Meta:
        model = OfferSyncLog
        fields = [
            'id', 'tenant_id', 'ad_network', 'network_name', 'sync_type',
            'status', 'status_display', 'offers_fetched', 'offers_updated',
            'offers_created', 'offers_deleted', 'sync_duration',
            'duration_display', 'error_message', 'sync_data',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'tenant_id', 'created_at', 'updated_at',
            'network_name', 'status_display', 'duration_display'
        ]
    
    def get_duration_display(self, obj):
        """Get duration display"""
        if obj.sync_duration:
            if obj.sync_duration.total_seconds() < 60:
                return f"{obj.sync_duration.total_seconds():.1f}s"
            else:
                minutes = obj.sync_duration.total_seconds() // 60
                seconds = obj.sync_duration.total_seconds() % 60
                return f"{int(minutes)}m {seconds:.0f}s"
        return "N/A"

class AdNetworkWebhookLogSerializer(BaseTenantSerializer):
    """
    SaaS-Ready Ad Network Webhook Log Serializer
    """
    network_name = serializers.CharField(source='ad_network.name', read_only=True)
    event_type_display = serializers.CharField(source='get_event_type_display', read_only=True)
    processing_time = serializers.SerializerMethodField()
    
    class Meta:
        model = AdNetworkWebhookLog
        fields = [
            'id', 'tenant_id', 'ad_network', 'network_name', 'event_type',
            'event_type_display', 'payload', 'processed', 'processing_time',
            'error_message', 'retry_count', 'webhook_id', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'tenant_id', 'created_at', 'updated_at',
            'network_name', 'event_type_display', 'processing_time'
        ]
    
    def get_processing_time(self, obj):
        """Get processing time"""
        if obj.created_at and obj.updated_at:
            duration = obj.updated_at - obj.created_at
            return f"{duration.total_seconds():.3f}s"
        return "N/A"

class OfferDailyLimitSerializer(BaseTenantSerializer):
    """
    SaaS-Ready Offer Daily Limit Serializer
    """
    user_display = serializers.CharField(source='user.username', read_only=True)
    offer_title = serializers.CharField(source='offer.title', read_only=True)
    is_limit_reached = serializers.BooleanField(read_only=True)
    remaining_count = serializers.SerializerMethodField()
    
    class Meta:
        model = OfferDailyLimit
        fields = [
            'id', 'tenant_id', 'user', 'user_display', 'offer', 'offer_title',
            'count_today', 'daily_limit', 'is_limit_reached', 'remaining_count',
            'is_active', 'last_reset_at', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'tenant_id', 'created_at', 'updated_at',
            'user_display', 'offer_title', 'is_limit_reached', 'remaining_count'
        ]
    
    def get_remaining_count(self, obj):
        """Get remaining count"""
        remaining = obj.daily_limit - obj.count_today
        return max(0, remaining)
    
    def validate_daily_limit(self, value):
        """Validate daily limit"""
        if value <= 0:
            raise serializers.ValidationError("Daily limit must be greater than 0")
        return value

# ============================================================================
# UTILITY SERIALIZERS
# ============================================================================

class BulkOperationSerializer(serializers.Serializer):
    """Serializer for bulk operations"""
    action = serializers.ChoiceField(choices=['create', 'update', 'delete'])
    items = serializers.ListField(child=serializers.DictField())
    
    def validate_items(self, value):
        """Validate items list"""
        if len(value) > 100:  # Max bulk operation size
            raise serializers.ValidationError(
                "Cannot process more than 100 items"
            )
        return value

class CacheInvalidationSerializer(serializers.Serializer):
    """Serializer for cache invalidation"""
    patterns = serializers.ListField(child=serializers.CharField())
    tenant_id = serializers.CharField(required=False)
    
    def validate_patterns(self, value):
        """Validate cache patterns"""
        if not value:
            raise serializers.ValidationError("At least one pattern is required")
        return value

# ============================================================================
# SERIALIZER FACTORY
# ============================================================================

class SerializerFactory:
    """
    Factory class for creating optimized serializers based on context
    """
    
    @staticmethod
    def get_offer_serializer(action='list', context=None):
        """Get appropriate offer serializer based on action"""
        context = context or {}
        
        serializer_map = {
            'list': OfferListSerializer,
            'retrieve': OfferDetailSerializer,
            'create': OfferSerializer,
            'update': OfferSerializer,
            'partial_update': OfferSerializer
        }
        
        serializer_class = serializer_map.get(action, OfferListSerializer)
        
        # Add context-specific optimizations
        if action == 'list':
            context['include_performance'] = False
        elif action == 'retrieve':
            context['include_performance'] = True
            context['include_history'] = True
        
        return serializer_class
    
    @staticmethod
    def get_engagement_serializer(action='list', context=None):
        """Get appropriate engagement serializer based on action"""
        context = context or {}
        
        serializer_map = {
            'list': UserOfferEngagementSerializer,
            'retrieve': UserOfferEngagementDetailSerializer,
            'create': UserOfferEngagementSerializer,
            'update': UserOfferEngagementSerializer
        }
        
        return serializer_map.get(action, UserOfferEngagementSerializer)
    
    @staticmethod
    def create_optimized_serializer(model_class, fields=None, exclude=None):
        """Create optimized serializer for given model"""
        class Meta:
            model = model_class
            fields = fields or '__all__'
            exclude = exclude or []
        
        attrs = {'Meta': Meta}
        
        # Add common optimizations
        if hasattr(model_class, 'tenant_id'):
            attrs['tenant_id'] = serializers.CharField(read_only=True)
        
        return type(
            f'{model_class.__name__}OptimizedSerializer',
            (serializers.ModelSerializer,),
            attrs
        )

# ============================================================================
# OFFER ATTACHMENT SERIALIZER
# ============================================================================

class OfferAttachmentSerializer(serializers.ModelSerializer):
    """Serializer for OfferAttachment model"""
    
    file_size_display = serializers.SerializerMethodField()
    file_type_display = serializers.SerializerMethodField()
    download_url = serializers.SerializerMethodField()
    
    class Meta:
        model = OfferAttachment
        fields = [
            'id', 'offer', 'file', 'filename', 'file_type', 'file_size',
            'description', 'is_active', 'created_at', 'updated_at',
            'file_size_display', 'file_type_display', 'download_url'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_file_size_display(self, obj):
        """Get human readable file size"""
        if obj.file_size:
            for unit in ['B', 'KB', 'MB', 'GB']:
                if obj.file_size < 1024.0:
                    return f"{obj.file_size:.2f} {unit}"
                obj.file_size /= 1024.0
            return f"{obj.file_size:.2f} TB"
        return "0 B"
    
    def get_file_type_display(self, obj):
        """Get file type display"""
        type_map = {
            'image': 'Image',
            'document': 'Document',
            'video': 'Video',
            'audio': 'Audio',
            'other': 'Other'
        }
        return type_map.get(obj.file_type, 'Unknown')
    
    def get_download_url(self, obj):
        """Get download URL"""
        if obj.file:
            return f"/api/ad_networks/attachments/{obj.id}/download/"
        return None


# ============================================================================
# USER WALLET SERIALIZER
# ============================================================================

class UserWalletSerializer(serializers.ModelSerializer):
    """Serializer for UserWallet model"""
    
    user_display = serializers.SerializerMethodField()
    balance_formatted = serializers.SerializerMethodField()
    pending_balance_formatted = serializers.SerializerMethodField()
    total_withdrawn_formatted = serializers.SerializerMethodField()
    is_active_display = serializers.SerializerMethodField()
    
    class Meta:
        model = UserWallet
        fields = [
            'id', 'user', 'user_display', 'current_balance', 'pending_balance',
            'total_earned', 'total_withdrawn', 'currency', 'is_active',
            'is_frozen', 'freeze_reason', 'frozen_at', 'created_at', 'updated_at',
            'balance_formatted', 'pending_balance_formatted', 
            'total_withdrawn_formatted', 'is_active_display'
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at', 'frozen_at']
    
    def get_user_display(self, obj):
        """Get user display name"""
        if obj.user:
            return f"{obj.user.get_full_name() or obj.user.username}"
        return "Unknown User"
    
    def get_balance_formatted(self, obj):
        """Get formatted balance"""
        return f"{obj.current_balance} {obj.currency}"
    
    def get_pending_balance_formatted(self, obj):
        """Get formatted pending balance"""
        return f"{obj.pending_balance} {obj.currency}"
    
    def get_total_withdrawn_formatted(self, obj):
        """Get formatted total withdrawn"""
        return f"{obj.total_withdrawn} {obj.currency}"
    
    def get_is_active_display(self, obj):
        """Get active status display"""
        if obj.is_frozen:
            return "Frozen"
        elif obj.is_active:
            return "Active"
        return "Inactive"


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Base serializers
    'BaseTenantSerializer',
    'BaseFraudSerializer',
    
    # Core serializers
    'AdNetworkSerializer',
    'AdNetworkDetailSerializer',
    'OfferCategorySerializer',
    'OfferSerializer',
    'OfferDetailSerializer',
    'OfferListSerializer',
    'UserOfferEngagementSerializer',
    'UserOfferEngagementDetailSerializer',
    'OfferConversionSerializer',
    'OfferWallSerializer',
    
    # Fraud detection serializers
    'FraudDetectionRuleSerializer',
    'BlacklistedIPSerializer',
    'KnownBadIPSerializer',
    
    # Network serializers
    'NetworkHealthCheckSerializer',
    'NetworkAPILogSerializer',
    
    # Analytics serializers
    'OfferPerformanceAnalyticsSerializer',
    'SmartOfferRecommendationSerializer',
    'NetworkStatisticSerializer',
    
    # User management serializers
    'UserOfferLimitSerializer',
    'OfferDailyLimitSerializer',
    
    # Offer management serializers
    'OfferClickSerializer',
    'OfferRewardSerializer',
    'OfferTagSerializer',
    'OfferTaggingSerializer',
    
    # System management serializers
    'OfferSyncLogSerializer',
    'AdNetworkWebhookLogSerializer',
    
    # Utility serializers
    'BulkOperationSerializer',
    'CacheInvalidationSerializer',
    
    # Additional serializers
    'OfferAttachmentSerializer',
    'UserWalletSerializer',
    
    # Factory
    'SerializerFactory',
    
    # Custom fields
    'DecimalField',
    'UUIDField',
    'CurrencyDecimalField',
    'JSONField',
    'IPAddressField',
    'TenantAwareField'
]
