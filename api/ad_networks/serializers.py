# api/ad_networks/serializers.py
from django.core.cache import cache
from rest_framework import serializers
from django.db import transaction
from django.contrib.auth import get_user_model
from decimal import Decimal, InvalidOperation
import uuid
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import Throttled
import hashlib
import hmac
from django.utils import timezone
from .models import (
    AdNetwork, OfferCategory, Offer, UserOfferEngagement,
    OfferConversion, OfferWall, AdNetworkWebhookLog,
    NetworkStatistic, UserOfferLimit, OfferSyncLog,
    SmartOfferRecommendation, OfferPerformanceAnalytics,
    FraudDetectionRule
)

User = get_user_model()


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_currency_symbol(currency_code):
    """Get currency symbol for display"""
    currency_map = {
        'BDT': '৳',
        'USD': '$',
        'EUR': '€',
        'GBP': '£',
        'INR': '₹',
        'PKR': '₨',
    }
    return currency_map.get(currency_code.upper() if currency_code else 'USD', '$')


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
        return str(value)


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
        
        if self.currency and self.show_currency_symbol:
            currency_symbols = {
                'USD': '$',
                'EUR': '€',
                'GBP': '£',
                'BDT': '৳',
                'INR': '₹',
                'JPY': '¥',
            }
            symbol = currency_symbols.get(self.currency, '')
            return f"{symbol}{value}"
        
        return super().to_representation(value)
    
    def to_internal_value(self, data):
        if isinstance(data, str):
            currency_symbols = ['$', '€', '£', '৳', '₹', '¥']
            for symbol in currency_symbols:
                data = data.replace(symbol, '')
        
        return super().to_internal_value(data)


class SmartChoiceField(serializers.ChoiceField):
    """Choice field that returns display value in representation"""
    
    def __init__(self, *args, **kwargs):
        self.display_values = kwargs.pop('display_values', {})
        super().__init__(*args, **kwargs)
    
    def to_representation(self, value):
        if value in self.display_values:
            return self.display_values[value]
        return super().to_representation(value)
    
    def to_internal_value(self, data):
        for key, display in self.display_values.items():
            if data == display:
                return key
        return super().to_internal_value(data)


class OptimizedRelatedField(serializers.PrimaryKeyRelatedField):
    """Optimized related field that caches related objects"""
    
    def __init__(self, **kwargs):
        self.serializer_class = kwargs.pop('serializer_class', None)
        super().__init__(**kwargs)
    
    def to_representation(self, value):
        if self.serializer_class:
            if isinstance(self.serializer_class, str):
                # Dynamically import serializer class if string reference
                from . import serializers as module_serializers
                serializer_class = getattr(module_serializers, self.serializer_class)
                return serializer_class(value, context=self.context).data
            return self.serializer_class(value, context=self.context).data
        return super().to_representation(value)
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        if hasattr(queryset.model, 'ad_network'):
            queryset = queryset.select_related('ad_network')
        if hasattr(queryset.model, 'category'):
            queryset = queryset.select_related('category')
        
        return queryset


# ============================================================================
# SERIALIZER MIXINS
# ============================================================================

class CachedSerializerMixin:
    """Mixin for caching serialized data"""
    
    CACHE_TIMEOUT = 300
    CACHE_PREFIX = 'serializer_'
    
    def to_representation(self, instance):
        cache_key = f"{self.CACHE_PREFIX}{instance.__class__.__name__}_{instance.id}"
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return cached_data
        
        data = super().to_representation(instance)
        cache.set(cache_key, data, timeout=self.CACHE_TIMEOUT)
        return data
    
    @classmethod
    def invalidate_cache(cls, instance):
        cache_key = f"{cls.CACHE_PREFIX}{instance.__class__.__name__}_{instance.id}"
        cache.delete(cache_key)


class DynamicFieldsMixin:
    """A mixin that allows dynamic field selection"""
    
    def __init__(self, *args, **kwargs):
        fields = kwargs.pop('fields', None)
        exclude = kwargs.pop('exclude', None)
        
        super().__init__(*args, **kwargs)
        
        if fields is not None:
            allowed = set(fields)
            existing = set(self.fields)
            for field_name in existing - allowed:
                self.fields.pop(field_name)
        
        if exclude is not None:
            for field_name in exclude:
                if field_name in self.fields:
                    self.fields.pop(field_name)


class ConditionalFieldMixin:
    """Mixin for conditionally including fields"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        request = self.context.get('request')
        if request:
            user = request.user
            
            if not user.is_staff:
                sensitive_fields = ['api_key', 'api_secret', 'publisher_id', 'sub_publisher_id', 'api_token']
                for field in sensitive_fields:
                    if field in self.fields:
                        self.fields.pop(field)
            
            include_detail = request.query_params.get('include_detail', 'false').lower() == 'true'
            if not include_detail:
                detail_fields = ['description', 'instructions', 'notes']
                for field in detail_fields:
                    if field in self.fields:
                        self.fields.pop(field)


class InternationalizedSerializerMixin:
    """Mixin for internationalized validation messages"""
    
    VALIDATION_MESSAGES = {
        'required': _('This field is required.'),
        'invalid': _('Enter a valid value.'),
        'max_length': _('Ensure this field has no more than %(max)d characters.'),
        'min_length': _('Ensure this field has at least %(min)d characters.'),
        'max_value': _('Ensure this value is less than or equal to %(max)s.'),
        'min_value': _('Ensure this value is greater than or equal to %(min)s.'),
        'max_decimal_places': _('Ensure that there are no more than %(max)d decimal places.'),
        'max_digits': _('Ensure that there are no more than %(max)d digits in total.'),
        'invalid_choice': _('Select a valid choice. %(value)s is not one of the available choices.'),
        'unique': _('This field must be unique.'),
    }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        for field_name, field in self.fields.items():
            if hasattr(field, 'error_messages'):
                for error_type, default_message in field.error_messages.items():
                    if error_type in self.VALIDATION_MESSAGES:
                        field.error_messages[error_type] = self.VALIDATION_MESSAGES[error_type]


class RateLimitedSerializerMixin:
    """Mixin for rate limiting serializers"""
    
    RATE_LIMIT_KEY = 'serializer_rate_limit'
    RATE_LIMIT = 100
    RATE_LIMIT_WINDOW = 60
    
    def validate(self, data):
        request = self.context.get('request')
        if request and request.user:
            user_id = request.user.id
            
            cache_key = f"{self.RATE_LIMIT_KEY}_{user_id}"
            operations_count = cache.get(cache_key, 0)
            
            if operations_count >= self.RATE_LIMIT:
                raise Throttled(
                    detail={
                        'message': _('Rate limit exceeded'),
                        'wait': self.RATE_LIMIT_WINDOW,
                        'limit': self.RATE_LIMIT,
                        'window': self.RATE_LIMIT_WINDOW,
                    }
                )
            
            cache.set(cache_key, operations_count + 1, self.RATE_LIMIT_WINDOW)
        
        return super().validate(data)


# ============================================================================
# BASE SERIALIZER CLASSES
# ============================================================================

class BaseSerializer(
    DynamicFieldsMixin,
    ConditionalFieldMixin,
    InternationalizedSerializerMixin,
    serializers.ModelSerializer
):
    pass


class CachedBaseSerializer(
    CachedSerializerMixin,
    BaseSerializer
):
    pass


# ============================================================================
# AD NETWORK SERIALIZERS
# ============================================================================

class AdNetworkSerializer(CachedBaseSerializer):
    
    id = UUIDField(read_only=True)
    min_payout = CurrencyDecimalField(
        max_digits=10, 
        decimal_places=2, 
        required=False,
        show_currency_symbol=True
    )
    max_payout = CurrencyDecimalField(
        max_digits=10, 
        decimal_places=2, 
        required=False,
        show_currency_symbol=True
    )
    commission_rate = DecimalField(max_digits=5, decimal_places=2, required=False)
    rating = serializers.FloatField(
        min_value=0, 
        max_value=5, 
        required=False
    )
    trust_score = serializers.IntegerField(min_value=0, max_value=100, required=False)
    total_payout = CurrencyDecimalField(
        max_digits=15, 
        decimal_places=2, 
        required=False,
        show_currency_symbol=True
    )
    epc = CurrencyDecimalField(
        max_digits=10, 
        decimal_places=4, 
        required=False,
        show_currency_symbol=True
    )
    
    category = SmartChoiceField(
        choices=[
            ('offerwall', 'Offerwall'),
            ('survey', 'Survey'),
            ('video', 'Video/Ads'),
            ('gaming', 'Gaming'),
            ('app_install', 'App Install'),
            ('cashback', 'Cashback'),
            ('cpi_cpa', 'CPI/CPA'),
            ('cpe', 'CPE (Cost Per Engagement)'),
            ('other', 'Other'),
        ],
        display_values={
            'offerwall': 'Offerwall 📱',
            'survey': 'Survey [NOTE]',
            'video': 'Video/Ads 🎬',
            'gaming': 'Gaming 🎮',
            'app_install': 'App Install 📲',
            'cashback': 'Cashback [MONEY]',
            'cpi_cpa': 'CPI/CPA [STATS]',
            'cpe': 'CPE [LOADING]',
            'other': 'Other 📦',
        }
    )
    
    country_support = SmartChoiceField(
        choices=[
            ('global', 'Global'),
            ('tier1', 'Tier 1 (US, UK, CA, AU)'),
            ('tier2', 'Tier 2 (EU, Middle East)'),
            ('tier3', 'Tier 3 (Asia, Africa, South America)'),
            ('bd_only', 'Bangladesh Only'),
            ('indian_sub', 'Indian Subcontinent'),
        ],
        display_values={
            'global': 'Global 🌍',
            'tier1': 'Tier 1 🌟',
            'tier2': 'Tier 2 ✨',
            'tier3': 'Tier 3 💫',
            'bd_only': 'Bangladesh 🇧🇩',
            'indian_sub': 'Indian Subcontinent 🇮🇳',
        },
        required=False
    )
    
    active_offers_count = serializers.SerializerMethodField()
    conversion_rate_display = serializers.SerializerMethodField()
    estimated_monthly_earnings = serializers.SerializerMethodField()
    
    class Meta:
        model = AdNetwork
        fields = [
            'id',
            'name',
            'network_type',
            'category',
            'description',
            'website',
            'logo',
            'logo_url',
            'banner_url',
            'api_key',
            'api_secret',
            'publisher_id',
            'sub_publisher_id',
            'api_token',
            'base_url',
            'webhook_url',
            'callback_url',
            'dashboard_url',
            'support_url',
            'is_active',
            'is_testing',
            'priority',
            'min_payout',
            'max_payout',
            'commission_rate',
            'rating',
            'trust_score',
            'country_support',
            'total_payout',
            'total_conversions',
            'total_clicks',
            'conversion_rate',
            'epc',
            'payment_methods',
            'payment_duration',
            'supports_postback',
            'supports_webhook',
            'supports_offers',
            'supports_surveys',
            'supports_video',
            'supports_app_install',
            'supports_gaming',
            'supports_quiz',
            'supports_tasks',
            'countries',
            'platforms',
            'device_types',
            'offer_refresh_interval',
            'last_sync',
            'next_sync',
            'config',
            'metadata',
            'notes',
            'is_verified',
            'verification_date',
            'created_at',
            'updated_at',
            'active_offers_count',
            'conversion_rate_display',
            'estimated_monthly_earnings',
        ]
        read_only_fields = [
            'id',
            'total_payout',
            'total_conversions',
            'total_clicks',
            'conversion_rate',
            'epc',
            'created_at',
            'updated_at',
            'active_offers_count',
            'conversion_rate_display',
            'estimated_monthly_earnings',
        ]
    
    def get_active_offers_count(self, obj):
        cache_key = f'ad_network_{obj.id}_active_offers'
        cached_count = cache.get(cache_key)
        
        if cached_count is not None:
            return cached_count
        
        count = obj.offers.filter(status='active').count()
        cache.set(cache_key, count, timeout=300)
        return count
    
    def get_conversion_rate_display(self, obj):
        if obj.conversion_rate is None:
            return "0.00%"
        return f"{obj.conversion_rate:.2f}%"
    
    def get_estimated_monthly_earnings(self, obj):
        if obj.epc and obj.total_clicks:
            monthly_clicks = obj.total_clicks / 30
            return obj.epc * monthly_clicks * 30
        return Decimal('0')
    
    def validate_commission_rate(self, value):
        if value < Decimal('0') or value > Decimal('100'):
            raise serializers.ValidationError(
                _("Commission rate must be between 0 and 100")
            )
        return value
    
    def validate_min_max_payout(self, data):
        min_payout = data.get('min_payout')
        max_payout = data.get('max_payout')
        
        if min_payout is not None and max_payout is not None:
            if min_payout > max_payout:
                raise serializers.ValidationError({
                    'min_payout': _('Minimum payout cannot be greater than maximum payout')
                })
        
        return data
    
    def validate(self, data):
        data = self.validate_min_max_payout(data)
        
        if data.get('is_active') and data.get('supports_offers') and not data.get('api_key'):
            raise serializers.ValidationError({
                'api_key': _('API key is required for active networks that support offers')
            })
        
        return data
    
    def create(self, validated_data):
        with transaction.atomic():
            if 'rating' not in validated_data:
                validated_data['rating'] = 4.0
            if 'trust_score' not in validated_data:
                validated_data['trust_score'] = 75
            
            instance = super().create(validated_data)
            self.invalidate_cache(instance)
            return instance
    
    def update(self, instance, validated_data):
        with transaction.atomic():
            instance = super().update(instance, validated_data)
            self.invalidate_cache(instance)
            return instance


class AdNetworkListSerializer(CachedBaseSerializer):
    
    category = SmartChoiceField(
        choices=[
            ('offerwall', 'Offerwall'),
            ('survey', 'Survey'),
            ('video', 'Video/Ads'),
            ('gaming', 'Gaming'),
            ('app_install', 'App Install'),
            ('cashback', 'Cashback'),
            ('cpi_cpa', 'CPI/CPA'),
            ('cpe', 'CPE'),
            ('other', 'Other'),
        ],
        display_values={
            'offerwall': '📱 Offerwall',
            'survey': '[NOTE] Survey',
            'video': '🎬 Video',
            'gaming': '🎮 Gaming',
            'app_install': '📲 App Install',
            'cashback': '[MONEY] Cashback',
            'cpi_cpa': '[STATS] CPI/CPA',
            'cpe': '[LOADING] CPE',
            'other': '📦 Other',
        }
    )
    
    conversion_rate_display = serializers.SerializerMethodField()
    total_payout_display = serializers.SerializerMethodField()
    
    class Meta:
        model = AdNetwork
        fields = [
            'id',
            'name',
            'network_type',
            'category',
            'is_active',
            'rating',
            'trust_score',
            'country_support',
            'total_payout_display',
            'total_conversions',
            'conversion_rate_display',
            'logo_url',
            'created_at',
        ]
    
    def get_conversion_rate_display(self, obj):
        if obj.conversion_rate is None:
            return "0.00%"
        return f"{obj.conversion_rate:.2f}%"
    
    def get_total_payout_display(self, obj):
        if obj.total_payout is None:
            return "$0.00"
        return f"${obj.total_payout:,.2f}"


class AdNetworkStatsSerializer(serializers.Serializer):
    
    network_id = UUIDField()
    network_name = serializers.CharField()
    total_clicks = serializers.IntegerField()
    total_conversions = serializers.IntegerField()
    conversion_rate = serializers.FloatField()
    total_payout = CurrencyDecimalField(max_digits=15, decimal_places=2, show_currency_symbol=True)
    total_commission = CurrencyDecimalField(max_digits=15, decimal_places=2, show_currency_symbol=True)
    avg_epc = CurrencyDecimalField(max_digits=10, decimal_places=4, show_currency_symbol=True)
    active_offers = serializers.IntegerField()
    estimated_monthly_revenue = CurrencyDecimalField(max_digits=15, decimal_places=2, show_currency_symbol=True)
    
    class Meta:
        fields = [
            'network_id',
            'network_name',
            'total_clicks',
            'total_conversions',
            'conversion_rate',
            'total_payout',
            'total_commission',
            'avg_epc',
            'active_offers',
            'estimated_monthly_revenue',
        ]


# ============================================================================
# OFFER CATEGORY SERIALIZERS
# ============================================================================

class OfferCategorySerializer(CachedBaseSerializer):
    
    id = UUIDField(read_only=True)
    
    category_type = SmartChoiceField(
        choices=[
            ('survey', 'Survey'),
            ('offer', 'Offer'),
            ('video', 'Video'),
            ('game', 'Game'),
            ('app_install', 'App Install'),
            ('quiz', 'Quiz'),
            ('task', 'Task'),
            ('signup', 'Signup'),
            ('shopping', 'Shopping'),
            ('cashback', 'Cashback'),
            ('other', 'Other'),
        ],
        display_values={
            'survey': '[NOTE] Survey',
            'offer': '[MONEY] Offer',
            'video': '🎬 Video',
            'game': '🎮 Game',
            'app_install': '📲 App Install',
            'quiz': '❓ Quiz',
            'task': '[OK] Task',
            'signup': '[NOTE] Signup',
            'shopping': '🛍️ Shopping',
            'cashback': '💸 Cashback',
            'other': '📦 Other',
        },
        required=False
    )
    
    offer_count = serializers.SerializerMethodField()
    active_offer_count = serializers.SerializerMethodField()
    
    class Meta:
        model = OfferCategory
        fields = [
            'id',
            'name',
            'slug',
            'description',
            'category_type',
            'icon',
            'image',
            'color',
            'is_active',
            'is_featured',
            'order',
            'meta_title',
            'meta_description',
            'keywords',
            'total_offers',
            'total_conversions',
            'avg_reward',
            'created_at',
            'updated_at',
            'offer_count',
            'active_offer_count',
        ]
        read_only_fields = [
            'id',
            'slug',
            'total_offers',
            'total_conversions',
            'avg_reward',
            'created_at',
            'updated_at',
            'offer_count',
            'active_offer_count',
        ]
    
    def get_offer_count(self, obj):
        return obj.total_offers
    
    def get_active_offer_count(self, obj):
        cache_key = f'category_{obj.id}_active_offers'
        cached_count = cache.get(cache_key)
        
        if cached_count is not None:
            return cached_count
        
        count = obj.offers.filter(status='active').count()
        cache.set(cache_key, count, timeout=300)
        return count
    
    def validate_slug(self, value):
        if not value and 'name' in self.initial_data:
            from django.utils.text import slugify
            name = self.initial_data['name']
            return slugify(name)
        return value
    
    def create(self, validated_data):
        if 'slug' not in validated_data and 'name' in validated_data:
            from django.utils.text import slugify
            validated_data['slug'] = slugify(validated_data['name'])
        
        instance = super().create(validated_data)
        self.invalidate_cache(instance)
        return instance
    
    def update(self, instance, validated_data):
        instance = super().update(instance, validated_data)
        self.invalidate_cache(instance)
        return instance


# ============================================================================
# OFFER LIST SERIALIZER (SHORT VERSION)
# ============================================================================

class OfferListSerializer(CachedBaseSerializer):
    
    ad_network_name = serializers.CharField(source='ad_network.name', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    
    status = SmartChoiceField(
        choices=[
            ('active', 'Active'),
            ('paused', 'Paused'),
            ('completed', 'Completed'),
            ('expired', 'Expired'),
            ('pending', 'Pending Review'),
            ('rejected', 'Rejected'),
        ],
        display_values={
            'active': '🟢 Active',
            'paused': '⏸️ Paused',
            'completed': '[OK] Completed',
            'expired': '[ERROR] Expired',
            'pending': '⏳ Pending',
            'rejected': '🚫 Rejected',
        }
    )
    
    difficulty = SmartChoiceField(
        choices=[
            ('very_easy', 'Very Easy'),
            ('easy', 'Easy'),
            ('medium', 'Medium'),
            ('hard', 'Hard'),
            ('very_hard', 'Very Hard'),
        ],
        display_values={
            'very_easy': '🟢 Very Easy',
            'easy': '🟢 Easy',
            'medium': '🟡 Medium',
            'hard': '🟠 Hard',
            'very_hard': '🔴 Very Hard',
        }
    )
    
    conversion_rate_display = serializers.SerializerMethodField()
    reward_amount_display = serializers.SerializerMethodField()
    estimated_time_display = serializers.SerializerMethodField()
    
    class Meta:
        model = Offer
        fields = [
            'id',
            'external_id',
            'title',
            'reward_amount_display',
            'reward_currency',
            'difficulty',
            'estimated_time_display',
            'status',
            'is_featured',
            'is_hot',
            'is_new',
            'is_exclusive',
            'thumbnail',
            'ad_network_name',
            'category_name',
            'conversion_rate_display',
            'countries',
            'platforms',
            'device_type',
            'created_at',
        ]
    
    def get_conversion_rate_display(self, obj):
        if obj.click_count > 0:
            return f"{(obj.total_conversions / obj.click_count) * 100:.2f}%"
        return "0.00%"
    
    def get_reward_amount_display(self, obj):
        if obj.reward_amount:
            symbol = get_currency_symbol(obj.reward_currency)
            return f"{symbol}{obj.reward_amount:.2f}"
        return "$0.00"
    
    def get_estimated_time_display(self, obj):
        if obj.estimated_time:
            if obj.estimated_time < 60:
                return f"{obj.estimated_time}m"
            else:
                return f"{obj.estimated_time // 60}h"
        return "N/A"


# ============================================================================
# OFFER SERIALIZERS
# ============================================================================

class OfferSerializer(CachedBaseSerializer, RateLimitedSerializerMixin):
    
    id = UUIDField(read_only=True)
    external_id = serializers.CharField(max_length=255, required=True)
    
    reward_amount = CurrencyDecimalField(
        max_digits=10, 
        decimal_places=2, 
        required=True,
        show_currency_symbol=True
    )
    network_payout = CurrencyDecimalField(
        max_digits=10, 
        decimal_places=2, 
        required=False,
        show_currency_symbol=True
    )
    commission = CurrencyDecimalField(
        max_digits=10, 
        decimal_places=2, 
        required=False,
        show_currency_symbol=True
    )
    
    estimated_time = serializers.IntegerField(min_value=1, max_value=1440, required=False)
    
    ad_network = OptimizedRelatedField(
        queryset=AdNetwork.objects.all(),
        required=True,
        serializer_class='AdNetworkListSerializer'
    )
    category = OptimizedRelatedField(
        queryset=OfferCategory.objects.all(),
        required=True,
        serializer_class='OfferCategorySerializer'
    )
    
    status = SmartChoiceField(
        choices=[
            ('active', 'Active'),
            ('paused', 'Paused'),
            ('completed', 'Completed'),
            ('expired', 'Expired'),
            ('pending', 'Pending Review'),
            ('rejected', 'Rejected'),
        ],
        display_values={
            'active': 'Active 🟢',
            'paused': 'Paused ⏸️',
            'completed': 'Completed [OK]',
            'expired': 'Expired [ERROR]',
            'pending': 'Pending ⏳',
            'rejected': 'Rejected 🚫',
        },
        required=False
    )
    
    difficulty = SmartChoiceField(
        choices=[
            ('very_easy', 'Very Easy'),
            ('easy', 'Easy'),
            ('medium', 'Medium'),
            ('hard', 'Hard'),
            ('very_hard', 'Very Hard'),
        ],
        display_values={
            'very_easy': 'Very Easy 🟢',
            'easy': 'Easy 🟢',
            'medium': 'Medium 🟡',
            'hard': 'Hard 🟠',
            'very_hard': 'Very Hard 🔴',
        },
        required=False
    )
    
    device_type = SmartChoiceField(
        choices=[
            ('any', 'Any Device'),
            ('mobile', 'Mobile Only'),
            ('tablet', 'Tablet Only'),
            ('desktop', 'Desktop Only'),
            ('android', 'Android Only'),
            ('ios', 'iOS Only'),
        ],
        display_values={
            'any': '📱💻 Any',
            'mobile': '📱 Mobile',
            'tablet': '📟 Tablet',
            'desktop': '💻 Desktop',
            'android': '🤖 Android',
            'ios': ' iOS',
        },
        required=False
    )
    
    ad_network_detail = AdNetworkListSerializer(source='ad_network', read_only=True)
    category_detail = OfferCategorySerializer(source='category', read_only=True)
    
    thumbnail = serializers.URLField(required=False, allow_null=True)
    
    net_profit = serializers.SerializerMethodField()
    conversion_rate_calculated = serializers.SerializerMethodField()
    estimated_earnings_per_hour = serializers.SerializerMethodField()
    is_available = serializers.SerializerMethodField()
    remaining_conversions = serializers.SerializerMethodField()
    estimated_completion_time = serializers.SerializerMethodField()
    
    class Meta:
        model = Offer
        fields = [
            'id',
            'external_id',
            'internal_id',
            'title',
            'description',
            'instructions',
            'reward_amount',
            'reward_currency',
            'network_payout',
            'commission',
            'difficulty',
            'estimated_time',
            'steps_required',
            'click_url',
            'tracking_url',
            'preview_url',
            'terms_url',
            'privacy_url',
            'thumbnail',
            'preview_images',
            'ad_network',
            'category',
            'status',
            'is_featured',
            'is_hot',
            'is_new',
            'is_exclusive',
            'requires_approval',
            'max_conversions',
            'max_daily_conversions',
            'total_conversions',
            'daily_conversions',
            'click_count',
            'user_daily_limit',
            'user_lifetime_limit',
            'countries',
            'platforms',
            'device_type',
            'min_age',
            'max_age',
            'gender_targeting',
            'age_group',
            'conversion_rate',
            'avg_completion_time',
            'quality_score',
            'metadata',
            'tags',
            'requirements',
            'fraud_score',
            'requires_screenshot',
            'requires_verification',
            'expires_at',
            'starts_at',
            'last_updated',
            'created_at',
            'updated_at',
            
            'ad_network_detail',
            'category_detail',
            
            'net_profit',
            'conversion_rate_calculated',
            'estimated_earnings_per_hour',
            'is_available',
            'remaining_conversions',
            'estimated_completion_time',
        ]
        read_only_fields = [
            'id',
            'total_conversions',
            'daily_conversions',
            'click_count',
            'conversion_rate',
            'avg_completion_time',
            'quality_score',
            'fraud_score',
            'last_updated',
            'created_at',
            'updated_at',
            'net_profit',
            'conversion_rate_calculated',
            'estimated_earnings_per_hour',
            'is_available',
            'remaining_conversions',
            'estimated_completion_time',
        ]
    
    def get_net_profit(self, obj):
        if obj.network_payout and obj.reward_amount:
            try:
                return obj.reward_amount - (obj.network_payout - obj.reward_amount)
            except:
                return obj.reward_amount
        return obj.reward_amount
    
    def get_conversion_rate_calculated(self, obj):
        if obj.click_count > 0:
            return (obj.total_conversions / obj.click_count) * 100
        return 0
    
    def get_estimated_earnings_per_hour(self, obj):
        if obj.estimated_time and obj.reward_amount:
            try:
                return (obj.reward_amount / obj.estimated_time) * 60
            except:
                return Decimal('0')
        return Decimal('0')
    
    def get_is_available(self, obj):
        return obj.is_available
    
    def get_remaining_conversions(self, obj):
        return obj.remaining_conversions
    
    def get_estimated_completion_time(self, obj):
        if obj.estimated_time:
            if obj.estimated_time < 60:
                return f"{obj.estimated_time} minutes"
            else:
                hours = obj.estimated_time // 60
                minutes = obj.estimated_time % 60
                if minutes > 0:
                    return f"{hours}h {minutes}m"
                return f"{hours} hours"
        return "N/A"
    
    def validate_external_id(self, value):
        cache_key = f'offer_external_id_{value}'
        cached_exists = cache.get(cache_key)
        
        if cached_exists is not None:
            if cached_exists:
                if self.instance and self.instance.external_id == value:
                    return value
                raise serializers.ValidationError(
                    _("An offer with this external ID already exists")
                )
        
        exists = Offer.objects.filter(external_id=value).exists()
        cache.set(cache_key, exists, timeout=300)
        
        if exists:
            if self.instance and self.instance.external_id == value:
                return value
            raise serializers.ValidationError(
                _("An offer with this external ID already exists")
            )
        
        return value
    
    def validate_reward_amount(self, value):
        if value <= Decimal('0'):
            raise serializers.ValidationError(_("Reward amount must be greater than 0"))
        return value
    
    def validate_estimated_time(self, value):
        if value <= 0:
            raise serializers.ValidationError(_("Estimated time must be greater than 0"))
        if value > 1440:
            raise serializers.ValidationError(_("Estimated time cannot exceed 24 hours (1440 minutes)"))
        return value
    
    def validate_countries(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError(_("Countries must be a list"))
        
        import re
        country_code_pattern = r'^[A-Z]{2}$'
        
        for country in value:
            if not re.match(country_code_pattern, country.upper()):
                raise serializers.ValidationError(
                    _("Invalid country code: %(country)s. Use 2-letter ISO codes.")
                    % {'country': country}
                )
        return value
    
    def validate_platforms(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError(_("Platforms must be a list"))
        
        valid_platforms = ['android', 'ios', 'web', 'windows', 'mac', 'linux']
        for platform in value:
            if platform.lower() not in valid_platforms:
                raise serializers.ValidationError(
                    _("Invalid platform: %(platform)s. Valid platforms are: %(valid)s")
                    % {'platform': platform, 'valid': ', '.join(valid_platforms)}
                )
        return value
    
    def validate(self, data):
        reward_amount = data.get('reward_amount', getattr(self.instance, 'reward_amount', None))
        network_payout = data.get('network_payout', getattr(self.instance, 'network_payout', None))
        commission = data.get('commission', getattr(self.instance, 'commission', None))
        
        if reward_amount and network_payout:
            if network_payout < reward_amount:
                raise serializers.ValidationError({
                    'network_payout': _('Network payout cannot be less than reward amount')
                })
        
        if commission and reward_amount:
            if commission > reward_amount:
                raise serializers.ValidationError({
                    'commission': _('Commission cannot be greater than reward amount')
                })
        
        min_age = data.get('min_age', getattr(self.instance, 'min_age', None))
        max_age = data.get('max_age', getattr(self.instance, 'max_age', None))
        
        if min_age and max_age:
            if min_age > max_age:
                raise serializers.ValidationError({
                    'min_age': _('Minimum age cannot be greater than maximum age')
                })
            if min_age < 13:
                raise serializers.ValidationError({
                    'min_age': _('Minimum age must be at least 13')
                })
            if max_age > 100:
                raise serializers.ValidationError({
                    'max_age': _('Maximum age cannot exceed 100')
                })
        
        return super().validate(data)
    
    def create(self, validated_data):
        with transaction.atomic():
            if 'commission' not in validated_data and 'network_payout' in validated_data and 'reward_amount' in validated_data:
                validated_data['commission'] = validated_data['network_payout'] - validated_data['reward_amount']
            
            if 'network_payout' not in validated_data and 'commission' in validated_data and 'reward_amount' in validated_data:
                validated_data['network_payout'] = validated_data['reward_amount'] + validated_data['commission']
            
            if 'difficulty' not in validated_data:
                validated_data['difficulty'] = 'medium'
            if 'estimated_time' not in validated_data:
                validated_data['estimated_time'] = 10
            if 'status' not in validated_data:
                validated_data['status'] = 'active'
            if 'countries' not in validated_data:
                validated_data['countries'] = ['US', 'UK']
            if 'platforms' not in validated_data:
                validated_data['platforms'] = ['android', 'ios']
            if 'device_type' not in validated_data:
                validated_data['device_type'] = 'mobile'
            
            instance = super().create(validated_data)
            
            self.invalidate_cache(instance)
            
            cache.delete(f'ad_network_{instance.ad_network_id}_active_offers')
            cache.delete(f'category_{instance.category_id}_active_offers')
            cache.delete(f'category_{instance.category_id}_total_offers')
            
            return instance
    
    def update(self, instance, validated_data):
        with transaction.atomic():
            instance = super().update(instance, validated_data)
            
            self.invalidate_cache(instance)
            
            cache.delete(f'offer_external_id_{instance.external_id}')
            cache.delete(f'ad_network_{instance.ad_network_id}_active_offers')
            cache.delete(f'category_{instance.category_id}_active_offers')
            
            return instance


# ============================================================================
# USER OFFER ENGAGEMENT SERIALIZERS
# ============================================================================

class UserOfferEngagementSerializer(CachedBaseSerializer, RateLimitedSerializerMixin):
    
    id = UUIDField(read_only=True)
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    offer = OptimizedRelatedField(
        queryset=Offer.objects.all(),
        serializer_class='OfferListSerializer'
    )
    
    reward_earned = CurrencyDecimalField(
        max_digits=10, 
        decimal_places=2, 
        required=False,
        show_currency_symbol=True
    )
    network_payout = CurrencyDecimalField(
        max_digits=10, 
        decimal_places=2, 
        required=False,
        show_currency_symbol=True
    )
    commission_earned = CurrencyDecimalField(
        max_digits=10, 
        decimal_places=2, 
        required=False,
        show_currency_symbol=True
    )
    
    status = SmartChoiceField(
        choices=[
            ('clicked', 'Clicked'),
            ('started', 'Started'),
            ('in_progress', 'In Progress'),
            ('completed', 'Completed'),
            ('pending', 'Pending Verification'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
            ('canceled', 'Canceled'),
            ('expired', 'Expired'),
        ],
        display_values={
            'clicked': '🖱️ Clicked',
            'started': '▶️ Started',
            'in_progress': '⏳ In Progress',
            'completed': '[OK] Completed',
            'pending': '⏸️ Pending',
            'approved': '👍 Approved',
            'rejected': '👎 Rejected',
            'canceled': '🚫 Canceled',
            'expired': '⌛ Expired',
        }
    )
    
    rejection_reason = SmartChoiceField(
        choices=[
            ('fraud', 'Fraud Detected'),
            ('incomplete', 'Incomplete Action'),
            ('quality', 'Low Quality'),
            ('duplicate', 'Duplicate'),
            ('timeout', 'Time Limit Exceeded'),
            ('invalid', 'Invalid Data'),
            ('other', 'Other'),
        ],
        display_values={
            'fraud': '🚨 Fraud',
            'incomplete': '[ERROR] Incomplete',
            'quality': '📉 Low Quality',
            'duplicate': '[DOC] Duplicate',
            'timeout': '⏰ Timeout',
            'invalid': '❓ Invalid',
            'other': '[NOTE] Other',
        },
        required=False
    )
    
    offer_title = serializers.CharField(source='offer.title', read_only=True)
    offer_reward = CurrencyDecimalField(
        source='offer.reward_amount',
        max_digits=10,
        decimal_places=2,
        read_only=True,
        show_currency_symbol=True
    )
    user_username = serializers.CharField(source='user.username', read_only=True)
    
    time_spent_display = serializers.SerializerMethodField()
    is_completed = serializers.SerializerMethodField()
    can_be_completed = serializers.SerializerMethodField()
    
    class Meta:
        model = UserOfferEngagement
        fields = [
            'id',
            'user',
            'offer',
            'status',
            'progress',
            'click_id',
            'conversion_id',
            'transaction_id',
            'campaign_id',
            'ip_address',
            'user_agent',
            'device_info',
            'location_data',
            'browser',
            'os',
            'reward_earned',
            'network_payout',
            'commission_earned',
            'clicked_at',
            'started_at',
            'completed_at',
            'verified_at',
            'rewarded_at',
            'expired_at',
            'rejection_reason',
            'rejection_details',
            'verified_by',
            'screenshot',
            'proof_data',
            'session_id',
            'referrer_url',
            'metadata',
            'notes',
            'created_at',
            'updated_at',
            
            'offer_title',
            'offer_reward',
            'user_username',
            
            'time_spent_display',
            'is_completed',
            'can_be_completed',
        ]
        read_only_fields = [
            'id',
            'clicked_at',
            'started_at',
            'completed_at',
            'verified_at',
            'rewarded_at',
            'expired_at',
            'verified_by',
            'created_at',
            'updated_at',
            'time_spent_display',
            'is_completed',
            'can_be_completed',
        ]
    
    def get_time_spent_display(self, obj):
        time_spent = obj.time_spent
        if time_spent:
            if time_spent < 60:
                return f"{time_spent:.0f}s"
            elif time_spent < 3600:
                return f"{time_spent/60:.1f}m"
            else:
                return f"{time_spent/3600:.1f}h"
        return None
    
    def get_is_completed(self, obj):
        return obj.status in ['completed', 'approved', 'rejected', 'expired']
    
    def get_can_be_completed(self, obj):
        return obj.can_be_completed
    
    def validate_click_id(self, value):
        cache_key = f'engagement_click_id_{value}'
        cached_exists = cache.get(cache_key)
        
        if cached_exists is not None:
            if cached_exists:
                if self.instance and self.instance.click_id == value:
                    return value
                raise serializers.ValidationError(
                    _("A click with this ID already exists")
                )
        
        exists = UserOfferEngagement.objects.filter(click_id=value).exists()
        cache.set(cache_key, exists, timeout=300)
        
        if exists:
            if self.instance and self.instance.click_id == value:
                return value
            raise serializers.ValidationError(
                _("A click with this ID already exists")
            )
        
        return value
    
    def validate_ip_address(self, value):
        import re
        ip_pattern = r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
        
        if value and not re.match(ip_pattern, value):
            raise serializers.ValidationError(_("Invalid IP address format"))
        
        return value
    
    def validate(self, data):
        reward_earned = data.get('reward_earned', getattr(self.instance, 'reward_earned', None))
        network_payout = data.get('network_payout', getattr(self.instance, 'network_payout', None))
        commission_earned = data.get('commission_earned', getattr(self.instance, 'commission_earned', None))
        
        if reward_earned and network_payout and not commission_earned:
            data['commission_earned'] = network_payout - reward_earned
        elif reward_earned and commission_earned and not network_payout:
            data['network_payout'] = reward_earned + commission_earned
        
        if self.instance:
            current_status = self.instance.status
            new_status = data.get('status', current_status)
            
            allowed_transitions = {
                'clicked': ['started', 'canceled', 'expired'],
                'started': ['in_progress', 'completed', 'canceled', 'expired'],
                'in_progress': ['completed', 'canceled', 'expired'],
                'completed': ['pending', 'approved', 'rejected'],
                'pending': ['approved', 'rejected'],
                'approved': ['rewarded', 'rejected'],
                'rejected': [],
                'canceled': [],
                'expired': [],
                'rewarded': [],
            }
            
            if current_status in allowed_transitions and new_status not in allowed_transitions[current_status]:
                raise serializers.ValidationError({
                    'status': _("Cannot transition from %(current)s to %(new)s")
                    % {'current': current_status, 'new': new_status}
                })
        
        return super().validate(data)
    
    def create(self, validated_data):
        with transaction.atomic():
            if 'user' not in validated_data and 'request' in self.context:
                validated_data['user'] = self.context['request'].user
            
            if 'status' not in validated_data:
                validated_data['status'] = 'clicked'
            
            if validated_data['status'] == 'clicked':
                validated_data['clicked_at'] = timezone.now()
            
            engagement = super().create(validated_data)
            
            if engagement.status == 'clicked':
                engagement.offer.click_count += 1
                engagement.offer.save()
            
            self.invalidate_cache(engagement)
            
            cache.delete(f'offer_{engagement.offer_id}_conversion_stats')
            
            return engagement
    
    def update(self, instance, validated_data):
        with transaction.atomic():
            old_status = instance.status
            new_status = validated_data.get('status', old_status)
            
            if new_status != old_status:
                if new_status == 'started' and not instance.started_at:
                    validated_data['started_at'] = timezone.now()
                elif new_status == 'completed' and not instance.completed_at:
                    validated_data['completed_at'] = timezone.now()
                elif new_status == 'approved' and not instance.verified_at:
                    validated_data['verified_at'] = timezone.now()
                elif new_status == 'rewarded' and not instance.rewarded_at:
                    validated_data['rewarded_at'] = timezone.now()
                elif new_status == 'rejected' and not instance.rejected_at:
                    validated_data['rejected_at'] = timezone.now()
            
            instance = super().update(instance, validated_data)
            
            if new_status != old_status:
                if new_status == 'completed':
                    instance.offer.total_conversions += 1
                    instance.offer.save()
            
            self.invalidate_cache(instance)
            
            cache.delete(f'engagement_click_id_{instance.click_id}')
            
            return instance


# ============================================================================
# OTHER SERIALIZERS
# ============================================================================

class NetworkStatisticSerializer(CachedBaseSerializer):
    
    id = UUIDField(read_only=True)
    ad_network = OptimizedRelatedField(
        queryset=AdNetwork.objects.all(),
        serializer_class='AdNetworkListSerializer'
    )
    clicks = serializers.IntegerField(min_value=0)
    conversions = serializers.IntegerField(min_value=0)
    payout = CurrencyDecimalField(
        max_digits=15, 
        decimal_places=2, 
        min_value=Decimal('0'),
        show_currency_symbol=True
    )
    commission = CurrencyDecimalField(
        max_digits=15, 
        decimal_places=2, 
        min_value=Decimal('0'),
        show_currency_symbol=True
    )
    
    conversion_rate_calculated = serializers.SerializerMethodField()
    epc_calculated = serializers.SerializerMethodField()
    revenue = serializers.SerializerMethodField()
    profit = serializers.SerializerMethodField()
    
    class Meta:
        model = NetworkStatistic
        fields = [
            'id',
            'ad_network',
            'date',
            'clicks',
            'conversions',
            'payout',
            'commission',
            'created_at',
            'updated_at',
            
            'conversion_rate_calculated',
            'epc_calculated',
            'revenue',
            'profit',
        ]
        read_only_fields = [
            'id',
            'conversion_rate_calculated',
            'epc_calculated',
            'revenue',
            'profit',
            'created_at',
            'updated_at',
        ]
    
    def get_conversion_rate_calculated(self, obj):
        if obj.clicks > 0:
            return (obj.conversions / obj.clicks) * 100
        return 0
    
    def get_epc_calculated(self, obj):
        if obj.clicks > 0:
            return obj.payout / obj.clicks
        return Decimal('0')
    
    def get_revenue(self, obj):
        return obj.payout + obj.commission
    
    def get_profit(self, obj):
        return obj.commission


class OfferConversionSerializer(CachedBaseSerializer):
    
    id = UUIDField(read_only=True)
    engagement = OptimizedRelatedField(
        queryset=UserOfferEngagement.objects.all(),
        serializer_class='UserOfferEngagementSerializer'
    )
    payout = CurrencyDecimalField(max_digits=10, decimal_places=2, show_currency_symbol=True)
    exchange_rate = DecimalField(max_digits=10, decimal_places=4, default=1)
    
    conversion_status = SmartChoiceField(
        choices=[
            ('pending', 'Pending Verification'),
            ('verified', 'Verified by Network'),
            ('approved', 'Approved for Payment'),
            ('rejected', 'Rejected (Fraud)'),
            ('chargeback', 'Chargeback (Payment Cancelled)'),
            ('disputed', 'Disputed'),
            ('paid', 'Paid to User'),
        ],
        display_values={
            'pending': '⏳ Pending',
            'verified': '[OK] Verified',
            'approved': '👍 Approved',
            'rejected': '👎 Rejected',
            'chargeback': '💸 Chargeback',
            'disputed': '⚖️ Disputed',
            'paid': '[MONEY] Paid',
        }
    )
    
    risk_level = SmartChoiceField(
        choices=[
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
        ],
        display_values={
            'low': '🟢 Low',
            'medium': '🟡 Medium',
            'high': '🔴 High',
        },
        required=False
    )
    
    local_payout = serializers.SerializerMethodField()
    
    class Meta:
        model = OfferConversion
        fields = [
            'id',
            'engagement',
            'postback_data',
            'payout',
            'network_currency',
            'exchange_rate',
            'is_verified',
            'verified_by',
            'verified_at',
            'conversion_status',
            'rejection_reason',
            'chargeback_at',
            'chargeback_reason',
            'chargeback_processed',
            'fraud_score',
            'fraud_reasons',
            'risk_level',
            'payment_reference',
            'payment_date',
            'payment_method',
            'processing_time',
            'retry_count',
            'metadata',
            'created_at',
            'updated_at',
            'local_payout',
        ]
        read_only_fields = [
            'id',
            'local_payout',
            'created_at',
            'updated_at',
        ]
    
    def get_local_payout(self, obj):
        return obj.payout * obj.exchange_rate


class OfferWithEngagementSerializer(serializers.Serializer):
    
    offer = OfferSerializer()
    user_engagement = UserOfferEngagementSerializer(required=False, allow_null=True)
    is_available = serializers.BooleanField()
    remaining_conversions = serializers.IntegerField()
    user_daily_clicks = serializers.IntegerField()
    can_click = serializers.BooleanField()
    estimated_earnings = CurrencyDecimalField(max_digits=10, decimal_places=2, show_currency_symbol=True)
    
    class Meta:
        fields = [
            'offer',
            'user_engagement',
            'is_available',
            'remaining_conversions',
            'user_daily_clicks',
            'can_click',
            'estimated_earnings',
        ]


# ============================================================================
# OFFER DETAIL SERIALIZER (EXTENDED VERSION)
# ============================================================================

class OfferDetailSerializer(OfferSerializer):
    """বিস্তারিত অফার তথ্যের জন্য সিরিয়ালাইজার"""
    
    ad_network_detail = AdNetworkSerializer(source='ad_network', read_only=True)
    category_detail = OfferCategorySerializer(source='category', read_only=True)
    
    # User-specific engagement data
    user_engagement = serializers.SerializerMethodField()
    user_can_click = serializers.SerializerMethodField()
    user_daily_engagement_count = serializers.SerializerMethodField()
    user_total_earnings = serializers.SerializerMethodField()
    
    # Statistics and analytics
    daily_conversion_stats = serializers.SerializerMethodField()
    hourly_conversion_rate = serializers.SerializerMethodField()
    completion_rate_by_country = serializers.SerializerMethodField()
    
    # Related offers
    similar_offers = serializers.SerializerMethodField()
    recommended_offers = serializers.SerializerMethodField()
    
    # Performance metrics
    conversion_velocity = serializers.SerializerMethodField()
    quality_metrics = serializers.SerializerMethodField()
    fraud_risk_indicators = serializers.SerializerMethodField()
    
    # User feedback and ratings
    user_ratings = serializers.SerializerMethodField()
    average_user_rating = serializers.SerializerMethodField()
    
    class Meta(OfferSerializer.Meta):
        fields = OfferSerializer.Meta.fields + [
            'user_engagement',
            'user_can_click',
            'user_daily_engagement_count',
            'user_total_earnings',
            'daily_conversion_stats',
            'hourly_conversion_rate',
            'completion_rate_by_country',
            'similar_offers',
            'recommended_offers',
            'conversion_velocity',
            'quality_metrics',
            'fraud_risk_indicators',
            'user_ratings',
            'average_user_rating',
        ]
    
    def get_user_engagement(self, obj):
        """বর্তমান ইউজারের জন্য অফার এনগেজমেন্ট ডেটা"""
        request = self.context.get('request')
        if request and request.user and request.user.is_authenticated:
            user = request.user
            engagement = UserOfferEngagement.objects.filter(
                offer=obj,
                user=user
            ).order_by('-created_at').first()
            
            if engagement:
                return {
                    'status': engagement.status,
                    'progress': engagement.progress,
                    'clicked_at': engagement.clicked_at,
                    'completed_at': engagement.completed_at,
                    'reward_earned': engagement.reward_earned,
                    'engagement_id': engagement.id
                }
        return None
    
    def get_user_can_click(self, obj):
        """ইউজার কি এই অফার ক্লিক করতে পারবে?"""
        request = self.context.get('request')
        if request and request.user and request.user.is_authenticated:
            user = request.user
            return obj.is_available_for_user(user)
        return False
    
    def get_user_daily_engagement_count(self, obj):
        """ইউজারের ডেইলি এনগেজমেন্ট সংখ্যা"""
        request = self.context.get('request')
        if request and request.user and request.user.is_authenticated:
            user = request.user
            today = timezone.now().date()
            return UserOfferEngagement.objects.filter(
                offer=obj,
                user=user,
                clicked_at__date=today
            ).count()
        return 0
    
    def get_user_total_earnings(self, obj):
        """এই অফার থেকে ইউজারের মোট আয়"""
        request = self.context.get('request')
        if request and request.user and request.user.is_authenticated:
            user = request.user
            total = UserOfferEngagement.objects.filter(
                offer=obj,
                user=user,
                status__in=['completed', 'approved', 'rewarded']
            ).aggregate(
                total=Sum('reward_earned')
            )['total'] or Decimal('0')
            return total
        return Decimal('0')
    
    def get_daily_conversion_stats(self, obj):
        """গত ৭ দিনের কনভার্সন স্ট্যাটিস্টিক্স"""
        from django.db.models import Count
        from django.utils import timezone
        from datetime import timedelta
        
        seven_days_ago = timezone.now() - timedelta(days=7)
        
        stats = UserOfferEngagement.objects.filter(
            offer=obj,
            completed_at__gte=seven_days_ago,
            status__in=['completed', 'approved', 'rewarded']
        ).extra({
            'date': "DATE(completed_at)"
        }).values('date').annotate(
            count=Count('id')
        ).order_by('date')
        
        return list(stats)
    
    def get_hourly_conversion_rate(self, obj):
        """ঘন্টাভিত্তিক কনভার্সন রেট"""
        from django.db.models import Avg
        
        hourly_stats = UserOfferEngagement.objects.filter(
            offer=obj,
            status__in=['completed', 'approved', 'rewarded']
        ).extra({
            'hour': "EXTRACT(HOUR FROM completed_at)"
        }).values('hour').annotate(
            avg_time=Avg('time_spent'),
            count=Count('id')
        ).order_by('hour')
        
        return list(hourly_stats)
    
    def get_completion_rate_by_country(self, obj):
        """দেশভিত্তিক কমপ্লিশন রেট"""
        from django.db.models import Count, Q
        
        countries = {}
        for country in obj.countries or []:
            engagements = UserOfferEngagement.objects.filter(
                offer=obj,
                location_data__contains=country
            )
            
            total = engagements.count()
            completed = engagements.filter(
                status__in=['completed', 'approved', 'rewarded']
            ).count()
            
            completion_rate = (completed / total * 100) if total > 0 else 0
            
            countries[country] = {
                'total_engagements': total,
                'completed_engagements': completed,
                'completion_rate': round(completion_rate, 2)
            }
        
        return countries
    
    def get_similar_offers(self, obj):
        """একই ক্যাটাগরির অন্যান্য অফার"""
        similar_offers = Offer.objects.filter(
            category=obj.category,
            status='active',
            is_available=True
        ).exclude(id=obj.id)[:5]
        
        return OfferListSerializer(
            similar_offers,
            many=True,
            context=self.context
        ).data
    
    def get_recommended_offers(self, obj):
        """রিকমেন্ডেড অফারগুলো"""
        from django.db.models import Q
        
        # পছন্দের উপর ভিত্তি করে রিকমেন্ডেশন
        recommended = Offer.objects.filter(
            Q(category=obj.category) | 
            Q(difficulty=obj.difficulty) |
            Q(reward_amount__gte=obj.reward_amount * Decimal('0.8')) |
            Q(reward_amount__lte=obj.reward_amount * Decimal('1.2'))
        ).filter(
            status='active',
            is_available=True
        ).exclude(id=obj.id).distinct()[:5]
        
        return OfferListSerializer(
            recommended,
            many=True,
            context=self.context
        ).data
    
    def get_conversion_velocity(self, obj):
        """কনভার্সনের গতি (ঘন্টা/দিন)"""
        from django.db.models import Count, Avg
        from django.utils import timezone
        from datetime import timedelta
        
        now = timezone.now()
        last_24h = now - timedelta(hours=24)
        last_7d = now - timedelta(days=7)
        
        conversions_24h = UserOfferEngagement.objects.filter(
            offer=obj,
            completed_at__gte=last_24h,
            status__in=['completed', 'approved', 'rewarded']
        ).count()
        
        conversions_7d = UserOfferEngagement.objects.filter(
            offer=obj,
            completed_at__gte=last_7d,
            status__in=['completed', 'approved', 'rewarded']
        ).count()
        
        avg_completion_time = UserOfferEngagement.objects.filter(
            offer=obj,
            status__in=['completed', 'approved', 'rewarded'],
            time_spent__isnull=False
        ).aggregate(
            avg_time=Avg('time_spent')
        )['avg_time'] or 0
        
        return {
            'conversions_per_hour': round(conversions_24h / 24, 2),
            'conversions_per_day': round(conversions_7d / 7, 2),
            'average_completion_time_minutes': round(avg_completion_time / 60, 2),
            'velocity_score': min(100, (conversions_24h / max(1, obj.total_conversions)) * 100)
        }
    
    def get_quality_metrics(self, obj):
        """অফারের কোয়ালিটি মেট্রিক্স"""
        engagements = UserOfferEngagement.objects.filter(offer=obj)
        
        total_engagements = engagements.count()
        completed_engagements = engagements.filter(
            status__in=['completed', 'approved', 'rewarded']
        ).count()
        
        rejected_engagements = engagements.filter(status='rejected').count()
        
        if total_engagements > 0:
            completion_rate = (completed_engagements / total_engagements) * 100
            rejection_rate = (rejected_engagements / total_engagements) * 100
        else:
            completion_rate = 0
            rejection_rate = 0
        
        # Average rating calculation
        from django.db.models import Avg
        avg_rating = engagements.filter(
            user_feedback__rating__isnull=False
        ).aggregate(
            avg_rating=Avg('user_feedback__rating')
        )['avg_rating'] or 0
        
        return {
            'completion_rate_percentage': round(completion_rate, 2),
            'rejection_rate_percentage': round(rejection_rate, 2),
            'average_user_rating': round(avg_rating, 2),
            'total_engagements': total_engagements,
            'completed_engagements': completed_engagements,
            'quality_score': round((completion_rate + (avg_rating * 20)) / 2, 2)
        }
    
    def get_fraud_risk_indicators(self, obj):
        """ফ্রড রিস্ক ইনডিকেটর"""
        engagements = UserOfferEngagement.objects.filter(offer=obj)
        
        # Calculate various fraud indicators
        high_fraud_count = engagements.filter(fraud_score__gte=80).count()
        medium_fraud_count = engagements.filter(fraud_score__gte=50, fraud_score__lt=80).count()
        
        total_engagements = engagements.count()
        
        if total_engagements > 0:
            high_fraud_percentage = (high_fraud_count / total_engagements) * 100
            medium_fraud_percentage = (medium_fraud_count / total_engagements) * 100
        else:
            high_fraud_percentage = 0
            medium_fraud_percentage = 0
        
        # Calculate overall risk score
        risk_score = min(100, (high_fraud_percentage * 0.7) + (medium_fraud_percentage * 0.3))
        
        return {
            'overall_risk_score': round(risk_score, 2),
            'high_risk_engagements': high_fraud_count,
            'medium_risk_engagements': medium_fraud_count,
            'high_risk_percentage': round(high_fraud_percentage, 2),
            'medium_risk_percentage': round(medium_fraud_percentage, 2),
            'risk_level': 'HIGH' if risk_score >= 70 else 'MEDIUM' if risk_score >= 30 else 'LOW'
        }
    
    def get_user_ratings(self, obj):
        """ইউজার রেটিংস"""
        engagements = UserOfferEngagement.objects.filter(
            offer=obj,
            user_feedback__rating__isnull=False
        ).select_related('user_feedback')[:10]
        
        ratings = []
        for engagement in engagements:
            if hasattr(engagement, 'user_feedback') and engagement.user_feedback:
                ratings.append({
                    'user': engagement.user.username if engagement.user else 'Anonymous',
                    'rating': engagement.user_feedback.rating,
                    'comment': engagement.user_feedback.comment,
                    'date': engagement.user_feedback.created_at
                })
        
        return ratings
    
    def get_average_user_rating(self, obj):
        """গড় ইউজার রেটিং"""
        from django.db.models import Avg
        
        avg_rating = UserOfferEngagement.objects.filter(
            offer=obj,
            user_feedback__rating__isnull=False
        ).aggregate(
            avg_rating=Avg('user_feedback__rating')
        )['avg_rating'] or 0
        
        return round(avg_rating, 2)
    
    
    # serializers.py ফাইলে নিচের কোড যোগ করুন (অন্যান্য serializer এর পরে)

# ============================================================================
# OFFER WALL SERIALIZERS
# ============================================================================

class OfferWallSerializer(CachedBaseSerializer):
    """অফার ওয়াল সিরিয়ালাইজার"""
    
    id = UUIDField(read_only=True)
    
    # Basic fields
    name = serializers.CharField(max_length=255, required=True)
    description = serializers.CharField(required=False, allow_blank=True)
    slug = serializers.SlugField(max_length=255, required=False, allow_blank=True)
    
    # Display settings
    icon = serializers.CharField(max_length=100, required=False, allow_blank=True)
    icon_url = serializers.SerializerMethodField()
    banner = serializers.ImageField(required=False, allow_null=True)
    banner_url = serializers.SerializerMethodField()
    color = serializers.CharField(max_length=7, required=False, default='#3B82F6')
    
    # Configuration
    ad_networks = serializers.PrimaryKeyRelatedField(
        queryset=AdNetwork.objects.filter(is_active=True),
        many=True,
        required=True
    )
    categories = serializers.PrimaryKeyRelatedField(
        queryset=OfferCategory.objects.filter(is_active=True),
        many=True,
        required=False
    )
    
    # Filter settings
    countries = serializers.ListField(
        child=serializers.CharField(max_length=2),
        required=False,
        default=list
    )
    platforms = serializers.ListField(
        child=serializers.CharField(max_length=20),
        required=False,
        default=['android', 'ios', 'web']
    )
    device_types = serializers.ListField(
        child=serializers.CharField(max_length=20),
        required=False,
        default=['mobile', 'desktop', 'tablet']
    )
    
    # Reward settings
    min_payout = CurrencyDecimalField(
        max_digits=10, 
        decimal_places=2, 
        required=False,
        min_value=Decimal('0'),
        show_currency_symbol=True
    )
    max_payout = CurrencyDecimalField(
        max_digits=10, 
        decimal_places=2, 
        required=False,
        min_value=Decimal('0'),
        show_currency_symbol=True
    )
    min_difficulty = SmartChoiceField(
        choices=[
            ('very_easy', 'Very Easy'),
            ('easy', 'Easy'),
            ('medium', 'Medium'),
            ('hard', 'Hard'),
            ('very_hard', 'Very Hard'),
        ],
        required=False
    )
    max_difficulty = SmartChoiceField(
        choices=[
            ('very_easy', 'Very Easy'),
            ('easy', 'Easy'),
            ('medium', 'Medium'),
            ('hard', 'Hard'),
            ('very_hard', 'Very Hard'),
        ],
        required=False
    )
    
    # Status and ordering
    is_active = serializers.BooleanField(default=True)
    is_featured = serializers.BooleanField(default=False)
    priority = serializers.IntegerField(default=0, min_value=0, max_value=100)
    order = serializers.IntegerField(default=0)
    
    # Statistics (read-only)
    total_offers = serializers.SerializerMethodField()
    total_conversions = serializers.SerializerMethodField()
    total_payout = CurrencyDecimalField(
        max_digits=15, 
        decimal_places=2, 
        required=False,
        read_only=True,
        show_currency_symbol=True
    )
    conversion_rate = serializers.FloatField(read_only=True, min_value=0, max_value=100)
    
    # Related data
    ad_networks_detail = serializers.SerializerMethodField()
    categories_detail = serializers.SerializerMethodField()
    
    # User-specific data
    user_available = serializers.SerializerMethodField()
    user_offers_count = serializers.SerializerMethodField()
    
    class Meta:
        model = OfferWall
        fields = [
            'id',
            'name',
            'description',
            'slug',
            'icon',
            'icon_url',
            'banner',
            'banner_url',
            'color',
            'ad_networks',
            'categories',
            'countries',
            'platforms',
            'device_types',
            'min_payout',
            'max_payout',
            'min_difficulty',
            'max_difficulty',
            'is_active',
            'is_featured',
            'priority',
            'order',
            'total_offers',
            'total_conversions',
            'total_payout',
            'conversion_rate',
            'metadata',
            'notes',
            'created_at',
            'updated_at',
            'ad_networks_detail',
            'categories_detail',
            'user_available',
            'user_offers_count',
        ]
        read_only_fields = [
            'id',
            'slug',
            'total_offers',
            'total_conversions',
            'total_payout',
            'conversion_rate',
            'created_at',
            'updated_at',
            'ad_networks_detail',
            'categories_detail',
            'user_available',
            'user_offers_count',
        ]
    
    def get_icon_url(self, obj):
        if obj.icon:
            if obj.icon.startswith(('http://', 'https://')):
                return obj.icon
            else:
                # Assuming you have MEDIA_URL configured
                request = self.context.get('request')
                if request:
                    return request.build_absolute_uri(f'/media/{obj.icon}')
        return None
    
    def get_banner_url(self, obj):
        if obj.banner:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.banner.url)
        return None
    
    def get_total_offers(self, obj):
        """ওয়ালের মোট একটিভ অফার সংখ্যা"""
        cache_key = f'offerwall_{obj.id}_total_offers'
        cached_count = cache.get(cache_key)
        
        if cached_count is not None:
            return cached_count
        
        count = Offer.objects.filter(
            ad_network__in=obj.ad_networks.all(),
            status='active',
            is_available=True
        ).count()
        
        cache.set(cache_key, count, timeout=300)
        return count
    
    def get_total_conversions(self, obj):
        """ওয়ালের মোট কনভার্সন"""
        cache_key = f'offerwall_{obj.id}_total_conversions'
        cached_count = cache.get(cache_key)
        
        if cached_count is not None:
            return cached_count
        
        # Get conversions from offers in this wall
        count = UserOfferEngagement.objects.filter(
            offer__ad_network__in=obj.ad_networks.all(),
            status__in=['completed', 'approved', 'rewarded']
        ).count()
        
        cache.set(cache_key, count, timeout=300)
        return count
    
    def get_ad_networks_detail(self, obj):
        """ওয়ালের অ্যাড নেটওয়ার্কের বিস্তারিত তথ্য"""
        if hasattr(obj, 'ad_networks_prefetched'):
            ad_networks = obj.ad_networks_prefetched
        else:
            ad_networks = obj.ad_networks.all()[:10]
        
        return AdNetworkListSerializer(
            ad_networks,
            many=True,
            context=self.context
        ).data
    
    def get_categories_detail(self, obj):
        """ওয়ালের ক্যাটাগরির বিস্তারিত তথ্য"""
        if hasattr(obj, 'categories_prefetched'):
            categories = obj.categories_prefetched
        else:
            categories = obj.categories.all()[:10]
        
        return OfferCategorySerializer(
            categories,
            many=True,
            context=self.context
        ).data
    
    def get_user_available(self, obj):
        """ইউজারের জন্য ওয়ালটি available কিনা"""
        request = self.context.get('request')
        if request and request.user and request.user.is_authenticated:
            user = request.user
            
            # Check if wall is available for user's country
            user_country = getattr(user.profile, 'country', 'US') if hasattr(user, 'profile') else 'US'
            
            if obj.countries and user_country not in obj.countries:
                return False
            
            return True
        
        return False
    
    def get_user_offers_count(self, obj):
        """ইউজারের জন্য available অফার সংখ্যা"""
        request = self.context.get('request')
        if request and request.user and request.user.is_authenticated:
            user = request.user
            
            cache_key = f'offerwall_{obj.id}_user_{user.id}_offers_count'
            cached_count = cache.get(cache_key)
            
            if cached_count is not None:
                return cached_count
            
            # Get available offers for user
            user_country = getattr(user.profile, 'country', 'US') if hasattr(user, 'profile') else 'US'
            
            available_offers = Offer.objects.filter(
                ad_network__in=obj.ad_networks.all(),
                status='active',
                is_available=True,
                countries__contains=[user_country]
            )
            
            # Exclude completed offers
            completed_offer_ids = UserOfferEngagement.objects.filter(
                user=user,
                status__in=['completed', 'approved']
            ).values_list('offer_id', flat=True)
            
            count = available_offers.exclude(id__in=completed_offer_ids).count()
            
            cache.set(cache_key, count, timeout=180)
            return count
        
        return 0
    
    def validate_slug(self, value):
        """স্লাগ validation"""
        if not value and 'name' in self.initial_data:
            from django.utils.text import slugify
            name = self.initial_data['name']
            return slugify(name)
        
        # Check uniqueness
        if value:
            qs = OfferWall.objects.filter(slug=value)
            if self.instance:
                qs = qs.exclude(id=self.instance.id)
            
            if qs.exists():
                raise serializers.ValidationError(
                    _("An offer wall with this slug already exists")
                )
        
        return value
    
    def validate_min_max_payout(self, data):
        """মিনিমাম-ম্যাক্সিমাম পে-আউট validation"""
        min_payout = data.get('min_payout')
        max_payout = data.get('max_payout')
        
        if min_payout is not None and max_payout is not None:
            if min_payout > max_payout:
                raise serializers.ValidationError({
                    'min_payout': _('Minimum payout cannot be greater than maximum payout')
                })
        
        return data
    
    def validate_min_max_difficulty(self, data):
        """মিনিমাম-ম্যাক্সিমাম difficulty validation"""
        min_difficulty = data.get('min_difficulty')
        max_difficulty = data.get('max_difficulty')
        
        if min_difficulty and max_difficulty:
            difficulty_levels = {
                'very_easy': 1,
                'easy': 2,
                'medium': 3,
                'hard': 4,
                'very_hard': 5
            }
            
            if difficulty_levels.get(min_difficulty, 0) > difficulty_levels.get(max_difficulty, 0):
                raise serializers.ValidationError({
                    'min_difficulty': _('Minimum difficulty cannot be greater than maximum difficulty')
                })
        
        return data
    
    def validate_countries(self, value):
        """দেশ validation"""
        if not isinstance(value, list):
            raise serializers.ValidationError(_("Countries must be a list"))
        
        import re
        country_code_pattern = r'^[A-Z]{2}$'
        
        for country in value:
            if country and not re.match(country_code_pattern, country.upper()):
                raise serializers.ValidationError(
                    _("Invalid country code: %(country)s. Use 2-letter ISO codes.")
                    % {'country': country}
                )
        return value
    
    def validate(self, data):
        """Overall validation"""
        data = self.validate_min_max_payout(data)
        data = self.validate_min_max_difficulty(data)
        
        # Validate ad_networks
        if 'ad_networks' in data and not data['ad_networks']:
            raise serializers.ValidationError({
                'ad_networks': _('At least one ad network is required')
            })
        
        return super().validate(data)
    
    @staticmethod
    def setup_eager_loading(queryset):
        """Optimize queries with eager loading"""
        return queryset.prefetch_related(
            Prefetch(
                'ad_networks',
                queryset=AdNetwork.objects.filter(is_active=True).only(
                    'id', 'name', 'logo_url', 'network_type', 'category'
                )
            ),
            Prefetch(
                'categories',
                queryset=OfferCategory.objects.filter(is_active=True).only(
                    'id', 'name', 'icon', 'color'
                )
            )
        )
    
    def create(self, validated_data):
        """Create offer wall with validation"""
        with transaction.atomic():
            # Handle many-to-many relationships
            ad_networks = validated_data.pop('ad_networks', [])
            categories = validated_data.pop('categories', [])
            
            # Create slug if not provided
            if 'slug' not in validated_data and 'name' in validated_data:
                from django.utils.text import slugify
                validated_data['slug'] = slugify(validated_data['name'])
            
            # Create instance
            instance = super().create(validated_data)
            
            # Set many-to-many relationships
            if ad_networks:
                instance.ad_networks.set(ad_networks)
            if categories:
                instance.categories.set(categories)
            
            self.invalidate_cache(instance)
            return instance
    
    def update(self, instance, validated_data):
        """Update offer wall with validation"""
        with transaction.atomic():
            # Handle many-to-many relationships
            ad_networks = validated_data.pop('ad_networks', None)
            categories = validated_data.pop('categories', None)
            
            # Update instance
            instance = super().update(instance, validated_data)
            
            # Update many-to-many relationships
            if ad_networks is not None:
                instance.ad_networks.set(ad_networks)
            if categories is not None:
                instance.categories.set(categories)
            
            self.invalidate_cache(instance)
            return instance


class OfferWallListSerializer(CachedBaseSerializer):
    """ওয়াল লিস্টের জন্য সংক্ষিপ্ত সিরিয়ালাইজার"""
    
    id = UUIDField(read_only=True)
    
    # Basic info
    name = serializers.CharField()
    description = serializers.CharField(required=False)
    icon_url = serializers.SerializerMethodField()
    color = serializers.CharField()
    
    # Stats
    total_offers = serializers.SerializerMethodField()
    total_networks = serializers.SerializerMethodField()
    user_available = serializers.SerializerMethodField()
    
    # Status
    is_featured = serializers.BooleanField()
    priority = serializers.IntegerField()
    
    class Meta:
        model = OfferWall
        fields = [
            'id',
            'name',
            'description',
            'icon_url',
            'color',
            'total_offers',
            'total_networks',
            'user_available',
            'is_featured',
            'priority',
            'created_at',
        ]
    
    def get_icon_url(self, obj):
        if obj.icon:
            if obj.icon.startswith(('http://', 'https://')):
                return obj.icon
            else:
                request = self.context.get('request')
                if request:
                    return request.build_absolute_uri(f'/media/{obj.icon}')
        return None
    
    def get_total_offers(self, obj):
        """ওয়ালের মোট অফার সংখ্যা"""
        cache_key = f'offerwall_{obj.id}_list_total_offers'
        cached_count = cache.get(cache_key)
        
        if cached_count is not None:
            return cached_count
        
        count = Offer.objects.filter(
            ad_network__in=obj.ad_networks.all(),
            status='active'
        ).count()
        
        cache.set(cache_key, count, timeout=300)
        return count
    
    def get_total_networks(self, obj):
        """ওয়ালের মোট নেটওয়ার্ক সংখ্যা"""
        return obj.ad_networks.count()
    
    def get_user_available(self, obj):
        """ইউজারের জন্য available কিনা"""
        request = self.context.get('request')
        if request and request.user and request.user.is_authenticated:
            user = request.user
            
            # Check if wall is available for user's country
            user_country = getattr(user.profile, 'country', 'US') if hasattr(user, 'profile') else 'US'
            
            if obj.countries and user_country not in obj.countries:
                return False
            
            return True
        
        return True  # For non-authenticated users, show all walls


class OfferWallStatsSerializer(serializers.Serializer):
    """ওয়াল স্ট্যাটিস্টিক্স সিরিয়ালাইজার"""
    
    wall_id = UUIDField()
    wall_name = serializers.CharField()
    total_offers = serializers.IntegerField()
    active_offers = serializers.IntegerField()
    total_conversions = serializers.IntegerField()
    conversion_rate = serializers.FloatField()
    total_payout = CurrencyDecimalField(max_digits=15, decimal_places=2, show_currency_symbol=True)
    avg_reward = CurrencyDecimalField(max_digits=10, decimal_places=2, show_currency_symbol=True)
    unique_users = serializers.IntegerField()
    retention_rate = serializers.FloatField()
    
    class Meta:
        fields = [
            'wall_id',
            'wall_name',
            'total_offers',
            'active_offers',
            'total_conversions',
            'conversion_rate',
            'total_payout',
            'avg_reward',
            'unique_users',
            'retention_rate',
        ]


# ============================================================================
# SERIALIZER FACTORY FOR DYNAMIC SERIALIZER SELECTION
# ============================================================================

class SerializerFactory:
    """
    Serializer Factory for dynamic serializer selection and optimization
    This helps in choosing the right serializer based on action and context
    """
    
    # Serializer mapping by model and action
    SERIALIZER_MAP = {
        'offer': {
            'list': 'OfferListSerializer',
            'retrieve': 'OfferDetailSerializer',
            'create': 'OfferSerializer',
            'update': 'OfferSerializer',
            'partial_update': 'OfferSerializer',
            'destroy': 'OfferSerializer',
            'default': 'OfferSerializer'
        },
        'offerwall': {
            'list': 'OfferWallListSerializer',
            'retrieve': 'OfferWallSerializer',
            'create': 'OfferWallSerializer',
            'update': 'OfferWallSerializer',
            'partial_update': 'OfferWallSerializer',
            'destroy': 'OfferWallSerializer',
            'default': 'OfferWallSerializer'
        },
        'offercategory': {
            'list': 'OfferCategorySerializer',
            'retrieve': 'OfferCategorySerializer',
            'create': 'OfferCategorySerializer',
            'update': 'OfferCategorySerializer',
            'partial_update': 'OfferCategorySerializer',
            'destroy': 'OfferCategorySerializer',
            'default': 'OfferCategorySerializer'
        },
        'adnetwork': {
            'list': 'AdNetworkListSerializer',
            'retrieve': 'AdNetworkSerializer',
            'create': 'AdNetworkSerializer',
            'update': 'AdNetworkSerializer',
            'partial_update': 'AdNetworkSerializer',
            'destroy': 'AdNetworkSerializer',
            'default': 'AdNetworkSerializer'
        },
        'userofferengagement': {
            'list': 'UserOfferEngagementSerializer',
            'retrieve': 'UserOfferEngagementSerializer',
            'create': 'UserOfferEngagementSerializer',
            'update': 'UserOfferEngagementSerializer',
            'partial_update': 'UserOfferEngagementSerializer',
            'destroy': 'UserOfferEngagementSerializer',
            'default': 'UserOfferEngagementSerializer'
        }
    }
    
    @classmethod
    def get_serializer(cls, model_name, action='default', context=None):
        """
        Get appropriate serializer for model and action
        
        Args:
            model_name (str): Model name (e.g., 'offer', 'offerwall')
            action (str): View action (e.g., 'list', 'retrieve')
            context (dict): Serializer context
            
        Returns:
            Serializer class
        """
        # Normalize model name
        model_name = model_name.lower()
        
        # Check if model exists in map
        if model_name not in cls.SERIALIZER_MAP:
            raise ValueError(f"No serializer mapping found for model: {model_name}")
        
        # Get serializer name
        serializer_name = cls.SERIALIZER_MAP[model_name].get(action)
        if not serializer_name:
            serializer_name = cls.SERIALIZER_MAP[model_name]['default']
        
        # Import and return serializer class
        return cls._import_serializer(serializer_name)
    
    @classmethod
    def get_offer_serializer(cls, action='list', context=None):
        """
        Convenience method for getting offer serializer
        
        Args:
            action (str): View action
            context (dict): Serializer context
            
        Returns:
            Offer serializer class
        """
        return cls.get_serializer('offer', action, context)
    
    @classmethod
    def get_offer_wall_serializer(cls, action='list', context=None):
        """
        Convenience method for getting offer wall serializer
        
        Args:
            action (str): View action
            context (dict): Serializer context
            
        Returns:
            Offer wall serializer class
        """
        return cls.get_serializer('offerwall', action, context)
    
    @classmethod
    def get_category_serializer(cls, action='list', context=None):
        """
        Convenience method for getting category serializer
        
        Args:
            action (str): View action
            context (dict): Serializer context
            
        Returns:
            Category serializer class
        """
        return cls.get_serializer('offercategory', action, context)
    
    @classmethod
    def get_ad_network_serializer(cls, action='list', context=None):
        """
        Convenience method for getting ad network serializer
        
        Args:
            action (str): View action
            context (dict): Serializer context
            
        Returns:
            Ad network serializer class
        """
        return cls.get_serializer('adnetwork', action, context)
    
    @classmethod
    def _import_serializer(cls, serializer_name):
        """
        Dynamically import serializer class
        
        Args:
            serializer_name (str): Serializer class name
            
        Returns:
            Serializer class
        """
        # Import all serializers from this module
        from . import serializers as module_serializers
        
        # Get serializer class
        serializer_class = getattr(module_serializers, serializer_name, None)
        
        if not serializer_class:
            raise ImportError(f"Serializer '{serializer_name}' not found in module")
        
        return serializer_class
    
    @classmethod
    def get_optimized_queryset(cls, queryset, serializer_class, action='list'):
        """
        Get optimized queryset for serializer
        
        Args:
            queryset: Base queryset
            serializer_class: Serializer class
            action (str): View action
            
        Returns:
            Optimized queryset
        """
        # Check if serializer has setup_eager_loading method
        if hasattr(serializer_class, 'setup_eager_loading'):
            queryset = serializer_class.setup_eager_loading(queryset)
        
        # Apply additional optimizations based on action
        if action == 'list':
            # For list views, we can limit fields
            if hasattr(queryset.model, 'ad_network'):
                queryset = queryset.select_related('ad_network')
            if hasattr(queryset.model, 'category'):
                queryset = queryset.select_related('category')
        
        elif action == 'retrieve':
            # For detail views, prefetch related data
            if hasattr(queryset.model, 'engagements'):
                from django.db.models import Prefetch
                from .models import UserOfferEngagement
                
                queryset = queryset.prefetch_related(
                    Prefetch(
                        'engagements',
                        queryset=UserOfferEngagement.objects.select_related('user').order_by('-created_at')[:10],
                        to_attr='recent_engagements'
                    )
                )
        
        return queryset
    
    @classmethod
    def get_serializer_with_context(cls, model_name, action='default', request=None, **kwargs):
        """
        Get serializer with context
        
        Args:
            model_name (str): Model name
            action (str): View action
            request: HTTP request object
            **kwargs: Additional context
            
        Returns:
            Serializer instance
        """
        # Get serializer class
        serializer_class = cls.get_serializer(model_name, action)
        
        # Prepare context
        context = {'request': request} if request else {}
        context.update(kwargs)
        
        return serializer_class(context=context)
    
    @classmethod
    def get_serializer_for_instance(cls, instance, action='retrieve', request=None):
        """
        Get serializer for a model instance
        
        Args:
            instance: Model instance
            action (str): View action
            request: HTTP request object
            
        Returns:
            Serializer instance
        """
        # Get model name from instance
        model_name = instance.__class__.__name__.lower()
        
        # Get serializer class
        serializer_class = cls.get_serializer(model_name, action)
        
        # Create serializer with instance
        context = {'request': request} if request else {}
        return serializer_class(instance, context=context)
    
    @classmethod
    def get_serializer_for_queryset(cls, queryset, model_name, action='list', request=None, many=True):
        """
        Get serializer for queryset
        
        Args:
            queryset: Model queryset
            model_name (str): Model name
            action (str): View action
            request: HTTP request object
            many (bool): Whether to serialize multiple objects
            
        Returns:
            Serializer instance
        """
        # Get serializer class
        serializer_class = cls.get_serializer(model_name, action)
        
        # Create serializer with queryset
        context = {'request': request} if request else {}
        return serializer_class(queryset, context=context, many=many)


# ============================================================================
# SERIALIZER CONTEXT MANAGER
# ============================================================================

class SerializerContextManager:
    """
    Manager for serializer context data
    """
    
    @staticmethod
    def add_user_context(context, user):
        """
        Add user-related context to serializer context
        
        Args:
            context (dict): Existing serializer context
            user: User object
            
        Returns:
            Updated context
        """
        if not context:
            context = {}
        
        if user and user.is_authenticated:
            context['user'] = user
            context['user_id'] = user.id
            context['is_staff'] = user.is_staff
            context['is_superuser'] = user.is_superuser
        
        return context
    
    @staticmethod
    def add_request_context(context, request):
        """
        Add request-related context to serializer context
        
        Args:
            context (dict): Existing serializer context
            request: HTTP request object
            
        Returns:
            Updated context
        """
        if not context:
            context = {}
        
        if request:
            context['request'] = request
            context['view'] = getattr(request, 'resolver_match', {}).get('func')
            
            # Add query parameters
            if hasattr(request, 'query_params'):
                context['query_params'] = dict(request.query_params)
        
        return context
    
    @staticmethod
    def add_cache_context(context, use_cache=True, cache_timeout=300):
        """
        Add cache-related context to serializer context
        
        Args:
            context (dict): Existing serializer context
            use_cache (bool): Whether to use caching
            cache_timeout (int): Cache timeout in seconds
            
        Returns:
            Updated context
        """
        if not context:
            context = {}
        
        context['use_cache'] = use_cache
        context['cache_timeout'] = cache_timeout
        
        return context
    
    @staticmethod
    def get_full_context(request=None, user=None, **kwargs):
        """
        Get full serializer context with all necessary data
        
        Args:
            request: HTTP request object
            user: User object
            **kwargs: Additional context
            
        Returns:
            Complete serializer context
        """
        context = {}
        
        # Add request context
        if request:
            context = SerializerContextManager.add_request_context(context, request)
        
        # Add user context (from request or explicit user)
        if user:
            context = SerializerContextManager.add_user_context(context, user)
        elif request and hasattr(request, 'user'):
            context = SerializerContextManager.add_user_context(context, request.user)
        
        # Add cache context
        context = SerializerContextManager.add_cache_context(context)
        
        # Add additional kwargs
        context.update(kwargs)
        
        return context


# ============================================================================
# MAIN SERIALIZER EXPORTS এ নতুন সিরিয়ালাইজার যোগ করুন
# ============================================================================

__all__ = [
    'DecimalField',
    'UUIDField',
    'CurrencyDecimalField',
    'SmartChoiceField',
    'OptimizedRelatedField',
    'get_currency_symbol',
    'CachedSerializerMixin',
    'DynamicFieldsMixin',
    'ConditionalFieldMixin',
    'InternationalizedSerializerMixin',
    'RateLimitedSerializerMixin',
    'BaseSerializer',
    'CachedBaseSerializer',
    'AdNetworkSerializer',
    'AdNetworkListSerializer',
    'AdNetworkStatsSerializer',
    'OfferCategorySerializer',
    'OfferSerializer',
    'OfferListSerializer',
    'UserOfferEngagementSerializer',
    'NetworkStatisticSerializer',
    'OfferConversionSerializer',
    'OfferWithEngagementSerializer',
    'OfferDetailSerializer',
    'OfferWallSerializer',
    'SerializerFactory',    
]

# ============================================================================
# earning_backend/api/models.py