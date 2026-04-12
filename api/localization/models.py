# models.py
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.core.validators import MinLengthValidator, MinValueValidator, MaxValueValidator, RegexValidator
from django.conf import settings
import logging
from datetime import timedelta
from django.utils import timezone
import pytz
from decimal import Decimal
from typing import Optional, Dict

logger = logging.getLogger(__name__)


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True


class Language(TimeStampedModel):
    code = models.CharField(
        max_length=10, 
        unique=True,
        help_text=_("Language code (e.g., en, bn, null=True, blank=True)")
    )
    name = models.CharField(
        max_length=50,
        help_text=_("Language name in English")
    )
    name_native = models.CharField(
        max_length=50, 
        blank=True,
        help_text=_("Language name in native script")
    )
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(
        default=False,
        help_text=_("Only one language can be default")
    )
    is_rtl = models.BooleanField(
        default=False,
        help_text=_("Right-to-left language?")
    )
    flag_emoji = models.CharField(
        max_length=5, 
        blank=True,
        help_text=_("Flag emoji (e.g., 🇧🇩, null=True, blank=True)")
    )
    locale_code = models.CharField(
        max_length=10, 
        blank=True,
        help_text=_("Locale code (e.g., bn_BD, en_US, null=True, blank=True)")
    )
    
    class Meta:
        ordering = ['name']
        verbose_name = _("Language")
        verbose_name_plural = _("Languages")
        indexes = [
            models.Index(fields=['is_active']),
            models.Index(fields=['is_default', 'is_active']),
        ]
    
    def __str__(self):
        return self.get_safe_display()
    
    def get_safe_display(self):
        name = getattr(self, 'name', None) or ''
        code = getattr(self, 'code', None) or 'unknown'
        return f"{name} ({code})" if name else code
    
    def save(self, *args, **kwargs):
        from django.db import transaction
        try:
            with transaction.atomic():
                if self.is_default:
                    Language.objects.filter(is_default=True).exclude(pk=self.pk).update(is_default=False)
                super().save(*args, **kwargs)
        except Exception as e:
            logger.error(f"Language save failed: {e}")
            raise
    
    @property
    def safe_name(self):
        return getattr(self, 'name_native', None) or getattr(self, 'name', '') or _('Unknown')


class Country(TimeStampedModel):
    code = models.CharField(
        max_length=2, 
        unique=True, 
        validators=[MinLengthValidator(2)],
        help_text=_("ISO 3166-1 alpha-2 country code")
    )
    code_alpha3 = models.CharField(
        max_length=3, 
        blank=True,
        help_text=_("ISO 3166-1 alpha-3 country code")
    )
    name = models.CharField(
        max_length=100,
        help_text=_("Country name in English")
    )
    native_name = models.CharField(
        max_length=100, 
        blank=True,
        help_text=_("Country name in native language")
    )
    phone_code = models.CharField(
        max_length=10,
        help_text=_("Phone code (e.g., +880, null=True, blank=True)")
    )
    phone_digits = models.PositiveSmallIntegerField(
        default=10,
        help_text=_("Number of digits in phone number")
    )
    flag_emoji = models.CharField(
        max_length=10, 
        blank=True,
        help_text=_("Flag emoji")
    )
    flag_svg_url = models.URLField(
        blank=True,
        help_text=_("Flag SVG URL")
    )
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = _("Country")
        verbose_name_plural = _("Countries")
        indexes = [
            models.Index(fields=['is_active']),
            models.Index(fields=['code']),
        ]
    
    def __str__(self):
        return f"{getattr(self, 'name', _('Unknown'))} ({getattr(self, 'code', '')})"
    
    @classmethod
    def get_active_countries(cls):
        try:
            return cls.objects.filter(is_active=True)
        except Exception as e:
            logger.error(f"Failed to get active countries: {e}")
            return cls.objects.none()
    
    def get_safe_phone_code(self):
        return getattr(self, 'phone_code', '') or ''


class Currency(TimeStampedModel):
    code = models.CharField(
        max_length=3, 
        unique=True, 
        validators=[MinLengthValidator(3)],
        help_text=_("Currency code (e.g., USD, BDT)")
    )
    name = models.CharField(
        max_length=50,
        help_text=_("Currency name")
    )
    symbol = models.CharField(
        max_length=10,
        help_text=_("Currency symbol (e.g., $, ৳, null=True, blank=True)")
    )
    symbol_native = models.CharField(
        max_length=10, 
        blank=True,
        help_text=_("Native currency symbol")
    )
    decimal_digits = models.PositiveSmallIntegerField(
        default=2,
        help_text=_("Number of decimal digits")
    )
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(
        default=False,
        help_text=_("Only one currency can be default")
    )
    exchange_rate = models.DecimalField(
        max_digits=12, 
        decimal_places=6, 
        default=1.000000,
        help_text=_("Exchange rate to default currency")
    )
    exchange_rate_updated_at = models.DateTimeField(
        null=True, 
        blank=True,
        help_text=_("Last time exchange rate was updated")
    )
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        ordering = ['code']
        verbose_name = _("Currency")
        verbose_name_plural = _("Currencies")
        indexes = [
            models.Index(fields=['is_active']),
            models.Index(fields=['is_default', 'is_active']),
        ]
    
    def __str__(self):
        return f"{getattr(self, 'code', '')} ({getattr(self, 'symbol', '')})"
    
    def save(self, *args, **kwargs):
        from django.db import transaction
        try:
            with transaction.atomic():
                if self.is_default:
                    Currency.objects.filter(is_default=True).exclude(pk=self.pk).update(is_default=False)
                super().save(*args, **kwargs)
        except Exception as e:
            logger.error(f"Currency save failed: {e}")
            raise
    
    def format_amount(self, amount):
        try:
            if amount is None:
                return f"{self.get_safe_symbol()}0.00"
            digits = getattr(self, 'decimal_digits', 2) or 2
            # Use Decimal instead of float for precision
            formatted = f"{Decimal(str(amount)):.{digits}f}"
            return f"{self.get_safe_symbol()}{formatted}"
        except (TypeError, ValueError, AttributeError) as e:
            logger.error(f"Amount formatting error: {e}")
            return f"{self.get_safe_symbol()}0.00"
    
    def get_safe_symbol(self):
        """Return symbol with fallback"""
        return getattr(self, 'symbol', '$') or '$'
    
    @property
    def needs_exchange_update(self):
        try:
            if not self.exchange_rate_updated_at:
                return True
            age = timezone.now() - self.exchange_rate_updated_at
            return age > timedelta(hours=24)
        except Exception as e:
            logger.error(f"Exchange rate check failed: {e}")
            return False


class Timezone(TimeStampedModel):
    name = models.CharField(
        max_length=100, 
        unique=True,
        help_text=_("Timezone name (e.g., Asia/Dhaka, null=True, blank=True)")
    )
    code = models.CharField(
        max_length=50, 
        unique=True,
        help_text=_("Timezone code (e.g., BDT, null=True, blank=True)")
    )
    offset = models.CharField(
        max_length=6, 
        blank=True,
        validators=[RegexValidator(
            regex=r'^[+-]\d{2}:\d{2}$',
            message=_('Offset must be in +HH:MM or -HH:MM format')
        )],
        help_text=_("UTC offset (e.g., +06:00)")
    )
    offset_seconds = models.IntegerField(
        default=0,
        help_text=_("Offset in seconds")
    )
    is_dst = models.BooleanField(
        default=False,
        help_text=_("Daylight Saving Time?")
    )
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        ordering = ['offset_seconds', 'name']
        verbose_name = _("Timezone")
        verbose_name_plural = _("Timezones")
        indexes = [
            models.Index(fields=['is_active']),
            models.Index(fields=['name']),
        ]
    
    def __str__(self):
        return f"{getattr(self, 'name', _('Unknown'))} (UTC{getattr(self, 'offset', '+00:00')})"
    
    @classmethod
    def get_current_time(cls, timezone_name=None):
        try:
            if timezone_name:
                tz = pytz.timezone(timezone_name)
                return timezone.now().astimezone(tz)
            # Default timezone from settings
            return timezone.localtime(timezone.now())
        except Exception as e:
            logger.error(f"Timezone conversion error: {e}")
            return timezone.now()


class City(TimeStampedModel):
    name = models.CharField(
        max_length=100,
        help_text=_("City name")
    )
    native_name = models.CharField(
        max_length=100, 
        blank=True,
        help_text=_("City name in native language")
    )
    country = models.ForeignKey(
        Country, 
        on_delete=models.CASCADE, 
        related_name='cities',
        help_text=_("Country of the city")
    )
    timezone = models.ForeignKey(
        Timezone, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        help_text=_("Timezone of the city")
    )
    latitude = models.DecimalField(
        max_digits=9, 
        decimal_places=6, 
        null=True, 
        blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
        help_text=_("Latitude (-90 to 90)")
    )
    longitude = models.DecimalField(
        max_digits=9, 
        decimal_places=6, 
        null=True, 
        blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
        help_text=_("Longitude (-180 to 180)")
    )
    is_active = models.BooleanField(default=True)
    is_capital = models.BooleanField(
        default=False,
        help_text=_("Is this the capital city?")
    )
    population = models.PositiveIntegerField(
        null=True, 
        blank=True,
        help_text=_("City population")
    )
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        unique_together = ['name', 'country']
        ordering = ['country__name', 'name']
        verbose_name = _("City")
        verbose_name_plural = _("Cities")
        indexes = [
            models.Index(fields=['is_active']),
            models.Index(fields=['country', 'is_active']),
        ]
    
    def __str__(self):
        country_code = getattr(self.country, 'code', _('Unknown')) if self.country else _('Unknown')
        return f"{getattr(self, 'name', _('Unknown'))}, {country_code}"
    
    @classmethod
    def get_active_cities_for_country(cls, country_code):
        try:
            return cls.objects.filter(
                country__code=country_code,
                is_active=True
            ).select_related('country', 'timezone')
        except Exception as e:
            logger.error(f"Failed to get cities for country {country_code}: {e}")
            return cls.objects.none()
    
    def clean(self):
        """Validate latitude and longitude together"""
        if (self.latitude is not None and self.longitude is None) or \
           (self.latitude is None and self.longitude is not None):
            raise ValidationError(_("Both latitude and longitude must be provided together"))


class TranslationKey(TimeStampedModel):
    key = models.CharField(
        max_length=255, 
        unique=True, 
        db_index=True,
        help_text=_("Unique translation key")
    )
    description = models.TextField(
        blank=True, 
        default='',
        help_text=_("Description for translators")
    )
    category = models.CharField(
        max_length=100, 
        blank=True, 
        default='', 
        db_index=True,
        help_text=_("Category for grouping translations")
    )
    context = models.TextField(
        blank=True, 
        default='',
        help_text=_("Additional context for translation")
    )
    is_plural = models.BooleanField(
        default=False,
        help_text=_("Has plural forms?")
    )
    plural_forms = models.JSONField(
        default=list, 
        blank=True,
        help_text=_("List of required plural forms")
    )
    is_html = models.BooleanField(
        default=False,
        help_text=_("Contains HTML tags?")
    )
    max_length = models.IntegerField(
        null=True, 
        blank=True,
        help_text=_("Maximum allowed length for translation")
    )
    
    class Meta:
        ordering = ['key']
        verbose_name = _("Translation Key")
        verbose_name_plural = _("Translation Keys")
        indexes = [
            models.Index(fields=['category']),
        ]
    
    def __str__(self):
        return getattr(self, 'key', '') or _('Unknown Key')
    
    @classmethod
    def get_or_create_key(cls, key, **kwargs):
        try:
            defaults = {
                'description': kwargs.get('description', ''),
                'category': kwargs.get('category', ''),
                'context': kwargs.get('context', '')
            }
            obj, created = cls.objects.get_or_create(key=key, defaults=defaults)
            return obj, created
        except Exception as e:
            logger.error(f"Failed to get/create translation key '{key}': {e}")
            return None, False


class Translation(TimeStampedModel):
    
    class Source(models.TextChoices):
        MANUAL = 'manual', _('Manual')
        AUTO = 'auto', _('Auto-translated')
        IMPORT = 'import', _('Imported')
        API = 'api', _('API')
    
    key = models.ForeignKey(
        TranslationKey, 
        on_delete=models.CASCADE, 
        related_name='translations',
        help_text=_("Translation key")
    )
    language = models.ForeignKey(
        Language, 
        on_delete=models.CASCADE, 
        related_name='translations',
        help_text=_("Target language")
    )
    value = models.TextField(
        help_text=_("Translated text")
    )
    value_plural = models.TextField(
        blank=True, 
        default='',
        help_text=_("Plural form if applicable")
    )
    is_approved = models.BooleanField(
        default=True,
        help_text=_("Is this translation approved?")
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        help_text=_("User who approved this translation")
    )
    approved_at = models.DateTimeField(
        null=True, 
        blank=True,
        help_text=_("When was this translation approved?")
    )
    source = models.CharField(
        max_length=20, 
        choices=Source.choices, 
        default=Source.MANUAL,
        help_text=_("Source of translation")
    )
    metadata = models.JSONField(
        default=dict, 
        blank=True,
        help_text=_("Additional metadata")
    )
    
    class Meta:
        unique_together = ['key', 'language']
        ordering = ['language', 'key__key']
        verbose_name = _("Translation")
        verbose_name_plural = _("Translations")
        indexes = [
            models.Index(fields=['language', 'is_approved']),
            models.Index(fields=['key', 'language', 'is_approved']),
        ]
    
    def __str__(self):
        return self.get_safe_display()
    
    def get_safe_display(self):
        key_str = getattr(self.key, 'key', '') if self.key else ''
        lang_code = getattr(self.language, 'code', '') if self.language else ''
        value = getattr(self, 'value', '')[:30] if self.value else ''
        return f"{key_str} - {lang_code}: {value}"
    
    def save(self, *args, **kwargs):
        try:
            if self.language and getattr(self.language, 'is_default', False):
                self.is_approved = True
            super().save(*args, **kwargs)
        except Exception as e:
            logger.error(f"Translation save failed: {e}")
            raise
    
    def clean(self):
        if self.key and self.key.max_length:
            if len(self.value) > self.key.max_length:
                raise ValidationError({
                    'value': _(f'Value exceeds maximum length of {self.key.max_length}')
                })


class TranslationCache(TimeStampedModel):
    language_code = models.CharField(
        max_length=10, 
        db_index=True,
        help_text=_("Language code")
    )
    cache_key = models.CharField(
        max_length=255, 
        db_index=True,
        help_text=_("Cache key")
    )
    cache_data = models.JSONField(
        default=dict,
        help_text=_("Cached translation data")
    )
    expires_at = models.DateTimeField(
        db_index=True,
        help_text=_("Cache expiration time")
    )
    hits = models.PositiveIntegerField(
        default=0,
        help_text=_("Number of cache hits")
    )
    
    class Meta:
        unique_together = ['language_code', 'cache_key']
        indexes = [
            models.Index(fields=['expires_at']),
        ]
        verbose_name = _("Translation Cache")
        verbose_name_plural = _("Translation Caches")
    
    def __str__(self):
        return f"{self.language_code}:{self.cache_key}"
    
    @classmethod
    def get_cache_key(cls, language_code, namespace='default'):
        try:
            return f"translations:{namespace}:{language_code or 'unknown'}"
        except Exception as e:
            logger.error(f"Cache key generation failed: {e}")
            return "translations:default:unknown"
    
    @classmethod
    def get_cached_translation(cls, language_code, cache_key):
        try:
            cache = cls.objects.filter(
                language_code=language_code,
                cache_key=cache_key,
                expires_at__gt=timezone.now()
            ).first()
            
            if cache:
                cache.hits += 1
                cache.save(update_fields=['hits'])
                return cache.cache_data or {}
            
            return None
        except Exception as e:
            logger.error(f"Cache retrieval failed: {e}")
            return None
    
    @classmethod
    def clean_expired(cls):
        """Delete expired cache entries"""
        try:
            return cls.objects.filter(expires_at__lte=timezone.now()).delete()
        except Exception as e:
            logger.error(f"Failed to clean expired cache: {e}")
            return 0, {}
    
    @classmethod
    def bulk_clean_expired(cls, days=7):
        """Delete old expired cache entries"""
        try:
            cutoff = timezone.now() - timedelta(days=days)
            return cls.objects.filter(
                expires_at__lte=cutoff
            ).delete()
        except Exception as e:
            logger.error(f"Bulk clean failed: {e}")
            return 0, {}


class UserLanguagePreference(TimeStampedModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='language_preference',
        help_text=_("User")
    )
    primary_language = models.ForeignKey(
        Language, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='primary_users',
        help_text=_("Primary language")
    )
    ui_language = models.ForeignKey(
        Language, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='ui_users',
        help_text=_("UI language")
    )
    content_language = models.ForeignKey(
        Language, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='content_users',
        help_text=_("Content language")
    )
    auto_translate = models.BooleanField(
        default=True,
        help_text=_("Auto-translate non-preferred content?")
    )
    preferred_languages = models.ManyToManyField(
        Language, 
        blank=True, 
        related_name='preferred_users',
        help_text=_("Preferred languages")
    )
    last_used_languages = models.JSONField(
        default=list, 
        blank=True,
        help_text=_("Recently used languages")
    )
    
    class Meta:
        verbose_name = _("User Language Preference")
        verbose_name_plural = _("User Language Preferences")
    
    def __str__(self):
        return self.get_safe_display()
    
    def get_safe_display(self):
        user_email = getattr(self.user, 'email', _('Unknown User')) if self.user else _('Unknown User')
        return f"Language pref for {user_email}"
    
    @property
    def effective_language(self):
        # Try to use prefetched data if available
        if self.ui_language and self.ui_language.is_active:
            return self.ui_language
        if self.primary_language and self.primary_language.is_active:
            return self.primary_language
        if self.content_language and self.content_language.is_active:
            return self.content_language
        try:
            return Language.objects.filter(is_default=True, is_active=True).first()
        except Exception as e:
            logger.error(f"Failed to get default language: {e}")
            return None
    
    def add_preferred_language(self, language_code):
        try:
            language = Language.objects.filter(code=language_code, is_active=True).first()
            if language and language not in self.preferred_languages.all():
                self.preferred_languages.add(language)
                return True
        except Exception as e:
            logger.error(f"Failed to add preferred language {language_code}: {e}")
        return False


class MissingTranslation(TimeStampedModel):
    key = models.CharField(
        max_length=255, 
        db_index=True,
        help_text=_("Missing translation key")
    )
    language = models.ForeignKey(
        Language, 
        on_delete=models.CASCADE,
        help_text=_("Language where translation is missing")
    )
    context = models.TextField(
        blank=True, 
        default='',
        help_text=_("Context where missing translation was requested")
    )
    request_path = models.CharField(
        max_length=500, 
        blank=True, 
        default='',
        help_text=_("URL path where missing translation occurred")
    )
    user_agent = models.TextField(
        blank=True, 
        default='',
        help_text=_("User agent of the request")
    )
    ip_address = models.GenericIPAddressField(
        null=True, 
        blank=True,
        help_text=_("IP address of the requester")
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        help_text=_("User who encountered missing translation")
    )
    resolved = models.BooleanField(
        default=False,
        help_text=_("Has this missing translation been resolved?")
    )
    resolved_at = models.DateTimeField(
        null=True, 
        blank=True,
        help_text=_("When was this resolved?")
    )
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='resolved_missing_translations',
        help_text=_("User who resolved this missing translation")
    )
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = _("Missing Translation")
        verbose_name_plural = _("Missing Translations")
        indexes = [
            models.Index(fields=['key']),
            models.Index(fields=['language', 'resolved']),
            models.Index(fields=['created_at']),
        ]
        unique_together = ['key', 'language', 'created_at']  # Prevent duplicate entries
    
    def __str__(self):
        return self.get_safe_display()
    
    def get_safe_display(self):
        key = getattr(self, 'key', 'Unknown') or 'Unknown'
        lang_code = getattr(self.language, 'code', 'unknown') if self.language else 'unknown'
        return f"Missing: {key} in {lang_code}"
    
    @classmethod
    def log_missing(cls, key, language_code, request=None, user=None):
        try:
            language = Language.objects.filter(code=language_code).first()
            if not language:
                logger.warning(f"Language not found for missing translation: {language_code}")
                return
            
            # Check for recent duplicate (last 24 hours)
            recent = cls.objects.filter(
                key=key,
                language=language,
                created_at__gte=timezone.now() - timedelta(hours=24)
            ).exists()
            
            if recent:
                logger.debug(f"Skipping duplicate missing translation: {key} in {language_code}")
                return
            
            data = {
                'key': key,
                'language': language,
                'user': user,
            }
            
            if request:
                data.update({
                    'request_path': getattr(request, 'path', '')[:500],
                    'user_agent': request.META.get('HTTP_USER_AGENT', '')[:500] if hasattr(request, 'META') else '',
                    'ip_address': cls.get_client_ip(request),
                })
            
            cls.objects.create(**data)
        except Exception as e:
            logger.error(f"Failed to log missing translation: {e}")
    
    @staticmethod
    def get_client_ip(request):
        try:
            if request:
                x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
                if x_forwarded_for:
                    return x_forwarded_for.split(',')[0]
                return request.META.get('REMOTE_ADDR')
        except Exception:
            pass
        return None