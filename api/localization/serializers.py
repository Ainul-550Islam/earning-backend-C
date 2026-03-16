# serializers.py
from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.core.exceptions import ValidationError as DjangoValidationError
from django.conf import settings
import logging
from typing import Dict, Any, Optional, List, Union
from decimal import Decimal, InvalidOperation
from .models import (
    Language, Country, Currency, Timezone, City,
    TranslationKey, Translation, TranslationCache,
    UserLanguagePreference, MissingTranslation
)

logger = logging.getLogger(__name__)


# ======================== Base Serializer with Defensive Coding ========================

class BulletproofSerializer(serializers.Serializer):
    """Base serializer with defensive coding techniques"""
    
    def to_representation(self, instance):
        try:
            return super().to_representation(instance)
        except Exception as e:
            logger.error(f"Serialization error in {self.__class__.__name__}: {e}")
            return {}
    
    def to_internal_value(self, data):
        try:
            return super().to_internal_value(data)
        except serializers.ValidationError:
            raise
        except Exception as e:
            logger.error(f"Deserialization error in {self.__class__.__name__}: {e}")
            raise serializers.ValidationError({"non_field_errors": ["Invalid data format"]})
    
    def get_safe_attr(self, instance, attr: str, default=None):
        try:
            return getattr(instance, attr, default)
        except Exception:
            return default


# ======================== Validation Mixins ========================

class DefaultValidationMixin:
    """Mixin for validating default field logic"""
    
    def validate_is_default(self, value):
        """Ensure only one instance can be default"""
        if value:
            model_class = self.Meta.model
            existing = model_class.objects.filter(is_default=True)
            if self.instance:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise serializers.ValidationError(
                    _("Another %s is already set as default") % model_class.__name__.lower()
                )
        return value


class ActiveValidationMixin:
    """Mixin for validating active status logic"""
    
    def validate_is_active(self, value):
        """Custom active validation if needed"""
        return value
    
    def validate_active_dependency(self, attrs, dependent_fields):
        """Validate that if is_active is True, dependent fields are provided"""
        if attrs.get('is_active'):
            for field in dependent_fields:
                if not attrs.get(field):
                    raise serializers.ValidationError({
                        field: _(f"{field} is required when is_active is True")
                    })
        return attrs


# ======================== Base Model Serializer ========================

class BaseModelSerializer(BulletproofSerializer, serializers.ModelSerializer):
    """Base model serializer with common functionality"""
    
    class Meta:
        abstract = True
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


# ======================== Language Serializers ========================

class LanguageSerializer(BaseModelSerializer, DefaultValidationMixin):
    """Language model serializer"""
    
    display_name = serializers.SerializerMethodField()
    
    class Meta(BaseModelSerializer.Meta):
        model = Language
    
    def get_display_name(self, obj):
        return obj.get_safe_display() if obj else ''
    
    def validate_code(self, value):
        if value and len(value) < 2:
            raise serializers.ValidationError(
                _("Language code must be at least 2 characters")
            )
        return value.lower()
    
    def validate(self, attrs):
        if attrs.get('is_default') and not attrs.get('is_active', True):
            raise serializers.ValidationError({
                'is_default': _("Default language must be active")
            })
        return attrs


class LanguageDetailSerializer(LanguageSerializer):
    """Detailed language serializer with additional info"""
    
    translations_count = serializers.SerializerMethodField()
    translation_keys_count = serializers.SerializerMethodField()
    
    class Meta(LanguageSerializer.Meta):
        fields = '__all__'
    
    def get_translations_count(self, obj):
        try:
            return obj.translations.filter(is_approved=True).count()
        except Exception:
            return 0
    
    def get_translation_keys_count(self, obj):
        try:
            return TranslationKey.objects.filter(
                translations__language=obj,
                translations__is_approved=True
            ).distinct().count()
        except Exception:
            return 0


class LanguageMinimalSerializer(BaseModelSerializer):
    """Minimal language serializer"""
    
    class Meta(BaseModelSerializer.Meta):
        model = Language
        fields = ['code', 'name', 'flag_emoji']


# ======================== Country Serializers ========================

class CountrySerializer(BaseModelSerializer):
    """Country model serializer"""
    
    phone_code_display = serializers.SerializerMethodField()
    
    class Meta(BaseModelSerializer.Meta):
        model = Country
    
    def get_phone_code_display(self, obj):
        return obj.get_safe_phone_code() if obj else ''
    
    def validate_code(self, value):
        if value and len(value) != 2:
            raise serializers.ValidationError(
                _("Country code must be exactly 2 characters (ISO 3166-1 alpha-2)")
            )
        return value.upper()
    
    def validate_code_alpha3(self, value):
        if value and len(value) != 3:
            raise serializers.ValidationError(
                _("Alpha-3 code must be exactly 3 characters (ISO 3166-1 alpha-3)")
            )
        return value.upper() if value else value
    
    def validate_phone_code(self, value):
        if value and not value.startswith('+'):
            value = f"+{value}"
        return value
    
    def validate_phone_digits(self, value):
        if value and (value < 5 or value > 15):
            raise serializers.ValidationError(
                _("Phone digits must be between 5 and 15")
            )
        return value


class CountryDetailSerializer(CountrySerializer):
    """Detailed country serializer with cities"""
    
    cities = serializers.SerializerMethodField()
    timezones = serializers.SerializerMethodField()
    cities_count = serializers.SerializerMethodField()
    
    class Meta(CountrySerializer.Meta):
        fields = '__all__'
    
    def get_cities(self, obj):
        try:
            # Local import to avoid circular import
            from .serializers import CityMinimalSerializer
            cities = City.get_active_cities_for_country(obj.code)
            return CityMinimalSerializer(cities, many=True).data
        except Exception as e:
            logger.error(f"Failed to get cities for {obj.code}: {e}")
            return []
    
    def get_timezones(self, obj):
        try:
            from .serializers import TimezoneMinimalSerializer
            timezones = obj.timezones.filter(is_active=True)
            return TimezoneMinimalSerializer(timezones, many=True).data
        except Exception:
            return []
    
    def get_cities_count(self, obj):
        try:
            return City.get_active_cities_for_country(obj.code).count()
        except Exception:
            return 0


class CountryMinimalSerializer(BaseModelSerializer):
    """Minimal country serializer"""
    
    class Meta(BaseModelSerializer.Meta):
        model = Country
        fields = ['code', 'name', 'flag_emoji', 'phone_code']


# ======================== Currency Serializers ========================

class CurrencySerializer(BaseModelSerializer, DefaultValidationMixin):
    """Currency model serializer"""
    
    formatted_examples = serializers.SerializerMethodField()
    
    class Meta(BaseModelSerializer.Meta):
        model = Currency
    
    def get_formatted_examples(self, obj):
        examples = {}
        try:
            test_amounts = [1, 100, 1000, 10000]
            for amount in test_amounts:
                examples[str(amount)] = obj.format_amount(amount)
        except Exception:
            examples = {'1': obj.symbol + '1', '100': obj.symbol + '100'}
        return examples
    
    def validate_code(self, value):
        if value and len(value) != 3:
            raise serializers.ValidationError(
                _("Currency code must be exactly 3 characters (ISO 4217)")
            )
        return value.upper()
    
    def validate_exchange_rate(self, value):
        if value is not None and value <= 0:
            raise serializers.ValidationError(
                _("Exchange rate must be positive")
            )
        return value
    
    def validate_decimal_digits(self, value):
        if value is not None and (value < 0 or value > 6):
            raise serializers.ValidationError(
                _("Decimal digits must be between 0 and 6")
            )
        return value
    
    def validate(self, attrs):
        if attrs.get('is_default') and not attrs.get('is_active', True):
            raise serializers.ValidationError({
                'is_default': _("Default currency must be active")
            })
        
        if attrs.get('exchange_rate') and not attrs.get('exchange_rate_updated_at'):
            attrs['exchange_rate_updated_at'] = timezone.now()
        
        return attrs
    
    def create(self, validated_data):
        if 'exchange_rate' in validated_data and 'exchange_rate_updated_at' not in validated_data:
            validated_data['exchange_rate_updated_at'] = timezone.now()
        return super().create(validated_data)


class CurrencyConversionSerializer(BulletproofSerializer):
    """Serializer for currency conversion requests"""
    
    amount = serializers.DecimalField(
        max_digits=12, decimal_places=6,
        required=False, default=1.0,
        min_value=Decimal('0.01')
    )
    from_currency = serializers.CharField(max_length=3, required=True)
    to_currency = serializers.CharField(max_length=3, required=True)
    
    def validate_from_currency(self, value):
        try:
            return Currency.objects.get(code=value.upper(), is_active=True)
        except Currency.DoesNotExist:
            raise serializers.ValidationError(
                _(f"Currency '{value}' not found or inactive")
            )
    
    def validate_to_currency(self, value):
        try:
            return Currency.objects.get(code=value.upper(), is_active=True)
        except Currency.DoesNotExist:
            raise serializers.ValidationError(
                _(f"Currency '{value}' not found or inactive")
            )
    
    def validate(self, attrs):
        from_curr = attrs.get('from_currency')
        to_curr = attrs.get('to_currency')
        
        if from_curr and to_curr and from_curr.pk == to_curr.pk:
            raise serializers.ValidationError(
                _("Source and target currencies must be different")
            )
        
        if from_curr and from_curr.exchange_rate == 0:
            raise serializers.ValidationError({
                'from_currency': _("Source currency has invalid exchange rate")
            })
        
        if to_curr and to_curr.exchange_rate == 0:
            raise serializers.ValidationError({
                'to_currency': _("Target currency has invalid exchange rate")
            })
        
        return attrs


class CurrencyMinimalSerializer(BaseModelSerializer):
    """Minimal currency serializer"""
    
    class Meta(BaseModelSerializer.Meta):
        model = Currency
        fields = ['code', 'symbol', 'name']


# ======================== Timezone Serializers ========================

class TimezoneSerializer(BaseModelSerializer):
    """Timezone model serializer"""
    
    current_time = serializers.SerializerMethodField()
    offset_display = serializers.SerializerMethodField()
    
    class Meta(BaseModelSerializer.Meta):
        model = Timezone
    
    def get_current_time(self, obj):
        try:
            return Timezone.get_current_time(obj.name).isoformat()
        except Exception:
            return timezone.now().isoformat()
    
    def get_offset_display(self, obj):
        if obj.offset:
            return f"UTC{obj.offset}"
        return "UTC"
    
    def validate_name(self, value):
        import pytz
        if value and value not in pytz.all_timezones:
            raise serializers.ValidationError(
                _(f"'{value}' is not a valid timezone name")
            )
        return value
    
    def validate_offset(self, value):
        import re
        if value and not re.match(r'^[+-]\d{2}:\d{2}$', value):
            raise serializers.ValidationError(
                _("Offset must be in format +HH:MM or -HH:MM")
            )
        return value


class TimezoneMinimalSerializer(BaseModelSerializer):
    """Minimal timezone serializer"""
    
    class Meta(BaseModelSerializer.Meta):
        model = Timezone
        fields = ['name', 'code', 'offset']


# ======================== City Serializers ========================

class CitySerializer(BaseModelSerializer):
    """City model serializer"""
    
    country_code = serializers.CharField(source='country.code', read_only=True)
    country_name = serializers.CharField(source='country.name', read_only=True)
    timezone_name = serializers.CharField(source='timezone.name', read_only=True)
    
    class Meta(BaseModelSerializer.Meta):
        model = City
    
    def validate_latitude(self, value):
        if value is not None and (value < -90 or value > 90):
            raise serializers.ValidationError(
                _("Latitude must be between -90 and 90")
            )
        return value
    
    def validate_longitude(self, value):
        if value is not None and (value < -180 or value > 180):
            raise serializers.ValidationError(
                _("Longitude must be between -180 and 180")
            )
        return value
    
    def validate(self, attrs):
        lat = attrs.get('latitude')
        lon = attrs.get('longitude')
        
        if (lat is None and lon is not None) or (lat is not None and lon is None):
            raise serializers.ValidationError(
                _("Both latitude and longitude must be provided together")
            )
        
        country = attrs.get('country')
        if country and not country.is_active:
            raise serializers.ValidationError({
                'country': _("Cannot assign city to inactive country")
            })
        
        return attrs
    
    def create(self, validated_data):
        name = validated_data.get('name')
        country = validated_data.get('country')
        
        if City.objects.filter(name=name, country=country).exists():
            raise serializers.ValidationError({
                'name': _(f"City '{name}' already exists in this country")
            })
        
        return super().create(validated_data)


class CityMinimalSerializer(BaseModelSerializer):
    """Minimal city serializer"""
    
    class Meta(BaseModelSerializer.Meta):
        model = City
        fields = ['id', 'name', 'native_name', 'is_capital']


# ======================== Translation Serializers ========================

class TranslationKeySerializer(BaseModelSerializer):
    """Translation key serializer"""
    
    class Meta(BaseModelSerializer.Meta):
        model = TranslationKey
    
    def validate_key(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError(_("Key cannot be empty"))
        
        import re
        if not re.match(r'^[a-z0-9_.-]+$', value):
            raise serializers.ValidationError(
                _("Key must contain only lowercase letters, numbers, dots, underscores, and hyphens")
            )
        
        return value
    
    def validate_plural_forms(self, value):
        if value and not isinstance(value, list):
            raise serializers.ValidationError(_("Plural forms must be a list"))
        
        valid_forms = ['zero', 'one', 'two', 'few', 'many', 'other']
        for form in value:
            if form not in valid_forms:
                raise serializers.ValidationError(
                    _(f"Invalid plural form: {form}")
                )
        
        return value


class TranslationSerializer(BaseModelSerializer):
    """Translation serializer"""
    
    key_string = serializers.CharField(source='key.key', read_only=True)
    language_code = serializers.CharField(source='language.code', read_only=True)
    language_name = serializers.CharField(source='language.name', read_only=True)
    
    class Meta(BaseModelSerializer.Meta):
        model = Translation
    
    def validate(self, attrs):
        key = attrs.get('key')
        language = attrs.get('language')
        value = attrs.get('value')
        
        if key and key.max_length and len(value) > key.max_length:
            raise serializers.ValidationError({
                'value': _(f"Value exceeds maximum length of {key.max_length}")
            })
        
        if not self.instance and key and language:
            if Translation.objects.filter(key=key, language=language).exists():
                raise serializers.ValidationError(
                    _(f"Translation already exists for key '{key.key}' in {language.code}")
                )
        
        if key and key.is_plural and not attrs.get('value_plural'):
            raise serializers.ValidationError({
                'value_plural': _("Plural value is required for this key")
            })
        
        return attrs
    
    def create(self, validated_data):
        language = validated_data.get('language')
        if language and language.is_default:
            validated_data['is_approved'] = True
            validated_data['approved_at'] = timezone.now()
        
        return super().create(validated_data)


class TranslationBulkSerializer(BulletproofSerializer):
    """Serializer for bulk translation operations"""
    
    language_code = serializers.CharField()
    translations = serializers.ListField(child=serializers.DictField())
    operation = serializers.ChoiceField(
        choices=['create', 'update', 'upsert'],
        default='upsert'
    )
    
    def validate_language_code(self, value):
        try:
            return Language.objects.get(code=value, is_active=True)
        except Language.DoesNotExist:
            raise serializers.ValidationError(_(f"Language '{value}' not found"))
    
    def validate(self, attrs):
        language = attrs['language_code']
        translations = attrs['translations']
        
        # Validate each translation has required fields
        for idx, trans in enumerate(translations):
            if 'key' not in trans:
                raise serializers.ValidationError({
                    f'translations[{idx}]': _("key is required")
                })
            if 'value' not in trans:
                raise serializers.ValidationError({
                    f'translations[{idx}]': _("value is required")
                })
        
        return attrs
    
    def save(self, **kwargs):
        """Execute bulk operation"""
        from .models import Translation, TranslationKey
        
        language = self.validated_data['language_code']
        translations_data = self.validated_data['translations']
        operation = self.validated_data.get('operation', 'upsert')
        
        results = {
            'created': 0,
            'updated': 0,
            'failed': 0,
            'errors': []
        }
        
        for trans_data in translations_data:
            try:
                key_str = trans_data['key']
                value = trans_data['value']
                
                # Get or create translation key
                key, _ = TranslationKey.objects.get_or_create(
                    key=key_str,
                    defaults={'description': f'Bulk imported for {language.code}'}
                )
                
                if operation == 'create':
                    # Check if exists
                    if Translation.objects.filter(key=key, language=language).exists():
                        results['failed'] += 1
                        results['errors'].append({
                            'key': key_str,
                            'error': 'Translation already exists'
                        })
                        continue
                    
                    # Create new
                    Translation.objects.create(
                        key=key,
                        language=language,
                        value=value,
                        value_plural=trans_data.get('value_plural', ''),
                        source='import',
                        is_approved=language.is_default
                    )
                    results['created'] += 1
                    
                elif operation == 'update':
                    # Update existing
                    updated = Translation.objects.filter(
                        key=key, language=language
                    ).update(
                        value=value,
                        value_plural=trans_data.get('value_plural', ''),
                        updated_at=timezone.now()
                    )
                    if updated:
                        results['updated'] += 1
                    else:
                        results['failed'] += 1
                        results['errors'].append({
                            'key': key_str,
                            'error': 'Translation not found'
                        })
                        
                else:  # upsert
                    obj, created = Translation.objects.update_or_create(
                        key=key,
                        language=language,
                        defaults={
                            'value': value,
                            'value_plural': trans_data.get('value_plural', ''),
                            'source': 'import',
                            'is_approved': language.is_default
                        }
                    )
                    if created:
                        results['created'] += 1
                    else:
                        results['updated'] += 1
                        
            except Exception as e:
                results['failed'] += 1
                results['errors'].append({
                    'key': trans_data.get('key', 'unknown'),
                    'error': str(e)
                })
        
        # Invalidate cache
        TranslationCache.objects.filter(language_code=language.code).delete()
        
        return results


# ======================== User Preference Serializers ========================

class UserLanguagePreferenceSerializer(BaseModelSerializer):
    """User language preference serializer"""
    
    user_email = serializers.CharField(source='user.email', read_only=True)
    effective_language = serializers.SerializerMethodField()
    preferred_languages_list = serializers.SerializerMethodField()
    
    class Meta(BaseModelSerializer.Meta):
        model = UserLanguagePreference
    
    def get_effective_language(self, obj):
        lang = obj.effective_language
        if lang:
            return {
                'code': lang.code,
                'name': lang.name,
                'flag_emoji': lang.flag_emoji
            }
        return {'code': 'en', 'name': 'English'}
    
    def get_preferred_languages_list(self, obj):
        try:
            # Local import to avoid circular import
            from .serializers import LanguageMinimalSerializer
            return LanguageMinimalSerializer(
                obj.preferred_languages.filter(is_active=True),
                many=True
            ).data
        except Exception:
            return []
    
    def validate(self, attrs):
        user = self.context.get('request').user if self.context.get('request') else None
        
        # Check if preference already exists for this user
        if not self.instance and user and UserLanguagePreference.objects.filter(user=user).exists():
            raise serializers.ValidationError(
                _("User language preference already exists")
            )
        
        return attrs


class UserLanguagePreferenceUpdateSerializer(BulletproofSerializer):
    """Serializer for updating user preferences"""
    
    primary_language = serializers.CharField(required=False, allow_null=True)
    ui_language = serializers.CharField(required=False, allow_null=True)
    content_language = serializers.CharField(required=False, allow_null=True)
    auto_translate = serializers.BooleanField(required=False)
    preferred_language = serializers.CharField(required=False)
    action = serializers.ChoiceField(
        choices=['add', 'remove', 'set'],
        default='set'
    )
    
    def _get_language(self, value, field_name):
        if value:
            try:
                return Language.objects.get(code=value, is_active=True)
            except Language.DoesNotExist:
                raise serializers.ValidationError({
                    field_name: _(f"Language '{value}' not found")
                })
        return None
    
    def validate_primary_language(self, value):
        return self._get_language(value, 'primary_language')
    
    def validate_ui_language(self, value):
        return self._get_language(value, 'ui_language')
    
    def validate_content_language(self, value):
        return self._get_language(value, 'content_language')
    
    def validate_preferred_language(self, value):
        return self._get_language(value, 'preferred_language')


# ======================== Missing Translation Serializer ========================

class MissingTranslationSerializer(BaseModelSerializer):
    """Missing translation serializer"""
    
    language_code = serializers.CharField(source='language.code', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    
    class Meta(BaseModelSerializer.Meta):
        model = MissingTranslation


class MissingTranslationReportSerializer(BulletproofSerializer):
    """Serializer for reporting missing translations"""
    
    key = serializers.CharField(required=True)
    language_code = serializers.CharField(required=True)
    context = serializers.CharField(required=False, allow_blank=True)
    
    def validate_language_code(self, value):
        try:
            return Language.objects.get(code=value)
        except Language.DoesNotExist:
            raise serializers.ValidationError(_(f"Language '{value}' not found"))
    
    def save(self, **kwargs):
        key = self.validated_data['key']
        language = self.validated_data['language_code']
        context = self.validated_data.get('context', '')
        request = self.context.get('request')
        user = request.user if request and request.user.is_authenticated else None
        
        MissingTranslation.log_missing(key, language.code, request, user)
        
        return {
            'key': key,
            'language_code': language.code,
            'status': 'logged'
        }


# ======================== Cache Serializer ========================

class TranslationCacheSerializer(BaseModelSerializer):
    """Translation cache serializer"""
    
    class Meta(BaseModelSerializer.Meta):
        model = TranslationCache
        read_only_fields = ['id', 'created_at', 'updated_at', 'hits']


# ======================== Pagination Serializer ========================

class PaginationSerializer(BulletproofSerializer):
    """Serializer for paginated responses"""
    
    count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True)
    previous = serializers.CharField(allow_null=True)
    results = serializers.ListField()
    page = serializers.IntegerField()
    pages = serializers.IntegerField()
    per_page = serializers.IntegerField()
    
    class Meta:
        fields = ['count', 'next', 'previous', 'results', 'page', 'pages', 'per_page']


# ======================== Response Serializers ========================

class ErrorResponseSerializer(BulletproofSerializer):
    """Standard error response serializer"""
    
    success = serializers.BooleanField(default=False)
    error = serializers.CharField()
    code = serializers.CharField()
    field = serializers.CharField(required=False, allow_null=True)
    timestamp = serializers.DateTimeField()
    
    class Meta:
        fields = ['success', 'error', 'code', 'field', 'timestamp']


class SuccessResponseSerializer(BulletproofSerializer):
    """Standard success response serializer"""
    
    success = serializers.BooleanField(default=True)
    data = serializers.DictField(required=False, allow_null=True)
    message = serializers.CharField(required=False, allow_blank=True)
    timestamp = serializers.DateTimeField()
    
    class Meta:
        fields = ['success', 'data', 'message', 'timestamp']


# ======================== Import/Export Serializers ========================

class TranslationExportSerializer(BulletproofSerializer):
    """Serializer for exporting translations"""
    
    language_code = serializers.CharField()
    format = serializers.ChoiceField(choices=['json', 'csv', 'po'], default='json')
    include_metadata = serializers.BooleanField(default=False)
    
    def validate_language_code(self, value):
        try:
            return Language.objects.get(code=value, is_active=True)
        except Language.DoesNotExist:
            raise serializers.ValidationError(_(f"Language '{value}' not found"))


class TranslationImportResponseSerializer(BulletproofSerializer):
    """Serializer for import response"""
    
    created = serializers.IntegerField()
    updated = serializers.IntegerField()
    failed = serializers.IntegerField()
    errors = serializers.ListField(child=serializers.DictField())
    total = serializers.IntegerField()
    
    class Meta:
        fields = ['created', 'updated', 'failed', 'errors', 'total']


# ======================== Bulk Operation Serializer ========================

class BulkOperationSerializer(BulletproofSerializer):
    """Serializer for bulk operations"""
    
    operation = serializers.ChoiceField(
        choices=['create', 'update', 'delete', 'activate', 'deactivate']
    )
    ids = serializers.ListField(child=serializers.IntegerField(), required=False)
    filters = serializers.DictField(required=False)
    data = serializers.DictField(required=False)
    
    def validate_ids(self, value):
        if value and not all(isinstance(i, int) for i in value):
            raise serializers.ValidationError(_("All IDs must be integers"))
        return value


# ======================== Helper function to get serializers dynamically ========================

def get_serializer(serializer_name: str, *args, **kwargs):
    """Dynamically get serializer class to avoid circular imports"""
    serializers_map = {
        'LanguageMinimalSerializer': LanguageMinimalSerializer,
        'CityMinimalSerializer': CityMinimalSerializer,
        'TimezoneMinimalSerializer': TimezoneMinimalSerializer,
        'CurrencyMinimalSerializer': CurrencyMinimalSerializer,
        'CountryMinimalSerializer': CountryMinimalSerializer,
        'TranslationSerializer': TranslationSerializer,
    }
    
    serializer_class = serializers_map.get(serializer_name)
    if serializer_class:
        return serializer_class(*args, **kwargs)
    raise ValueError(f"Serializer {serializer_name} not found")