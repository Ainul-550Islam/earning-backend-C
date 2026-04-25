# models/settings.py — LocalizationConfig, DateTimeFormat, NumberFormat, AddressFormat
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
import logging

logger = logging.getLogger(__name__)


class LocalizationConfig(models.Model):
    """Tenant-level localization settings"""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    tenant_id = models.CharField(max_length=100, unique=True, db_index=True, help_text=_("Tenant identifier"))
    default_language = models.ForeignKey('localization.Language', on_delete=models.SET_NULL, null=True, blank=True, related_name='config_default')
    fallback_language = models.ForeignKey('localization.Language', on_delete=models.SET_NULL, null=True, blank=True, related_name='config_fallback')
    default_currency = models.ForeignKey('localization.Currency', on_delete=models.SET_NULL, null=True, blank=True, related_name='config_default')
    default_timezone = models.ForeignKey('localization.Timezone', on_delete=models.SET_NULL, null=True, blank=True, related_name='config_default')
    supported_languages = models.ManyToManyField('localization.Language', blank=True, related_name='tenant_configs')
    supported_currencies = models.ManyToManyField('localization.Currency', blank=True, related_name='tenant_configs')
    detect_language_from_browser = models.BooleanField(default=True)
    detect_language_from_ip = models.BooleanField(default=True)
    auto_translate_missing = models.BooleanField(default=False)
    auto_translate_provider = models.CharField(max_length=50, blank=True, choices=[
        ('google','Google Translate'),('deepl','DeepL'),('azure','Azure'),
        ('openai','OpenAI'),('amazon','Amazon Translate'),
    ])
    require_translation_approval = models.BooleanField(default=True)
    show_untranslated_keys = models.BooleanField(default=True, help_text=_("Show key name if translation missing?"))
    translation_cache_ttl = models.PositiveIntegerField(default=3600, help_text=_("Cache TTL in seconds"))
    log_missing_translations = models.BooleanField(default=True)
    update_exchange_rates_interval = models.PositiveIntegerField(default=60, help_text=_("Minutes between rate updates"))
    exchange_rate_provider = models.CharField(max_length=50, blank=True)
    enable_rtl_support = models.BooleanField(default=True)
    enable_translation_memory = models.BooleanField(default=True)
    enable_glossary = models.BooleanField(default=True)
    enable_content_localization = models.BooleanField(default=True)
    custom_settings = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = _("Localization Config")
        verbose_name_plural = _("Localization Configs")

    def __str__(self):
        default_lang = getattr(self.default_language, 'code', 'none') if self.default_language else 'none'
        return f"Config [{self.tenant_id}] default={default_lang}"


class DateTimeFormat(models.Model):
    """Date/time format patterns per locale"""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    language = models.ForeignKey('localization.Language', on_delete=models.CASCADE, related_name='datetime_formats')
    country = models.ForeignKey('localization.Country', on_delete=models.SET_NULL, null=True, blank=True, related_name='datetime_formats')
    calendar_system = models.CharField(max_length=30, default='gregorian', choices=[
        ('gregorian','Gregorian'),('islamic','Islamic/Hijri'),
        ('islamic_civil','Islamic Civil'),('persian','Persian/Solar Hijri'),
        ('hebrew','Hebrew'),('buddhist','Buddhist'),('japanese','Japanese'),
    ])
    date_short = models.CharField(max_length=30, default='MM/dd/yyyy')
    date_medium = models.CharField(max_length=40, default='MMM d, yyyy')
    date_long = models.CharField(max_length=50, default='MMMM d, yyyy')
    date_full = models.CharField(max_length=60, default='EEEE, MMMM d, yyyy')
    time_short = models.CharField(max_length=20, default='h:mm a')
    time_medium = models.CharField(max_length=30, default='h:mm:ss a')
    time_long = models.CharField(max_length=40, default='h:mm:ss a z')
    datetime_short = models.CharField(max_length=60, blank=True)
    first_day_of_week = models.PositiveSmallIntegerField(default=1, help_text=_("1=Monday, 7=Sunday"))
    am_symbol = models.CharField(max_length=10, default='AM')
    pm_symbol = models.CharField(max_length=10, default='PM')
    month_names = models.JSONField(default=list, blank=True, help_text=_("Full month names Jan-Dec"))
    month_names_short = models.JSONField(default=list, blank=True)
    day_names = models.JSONField(default=list, blank=True)
    day_names_short = models.JSONField(default=list, blank=True)
    day_names_min = models.JSONField(default=list, blank=True)
    use_native_numerals = models.BooleanField(default=False)
    native_digits = models.CharField(max_length=20, blank=True, help_text=_("e.g. ০১২৩৪৫৬৭৮৯"))
    relative_time_examples = models.JSONField(default=dict, blank=True)
    era_names = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = ['language', 'country', 'calendar_system']
        verbose_name = _("Date/Time Format")
        verbose_name_plural = _("Date/Time Formats")

    def __str__(self):
        lang = getattr(self.language, 'code', '?')
        return f"[{lang}] {self.calendar_system} date format"


class NumberFormat(models.Model):
    """Number format patterns per locale"""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    language = models.ForeignKey('localization.Language', on_delete=models.CASCADE, related_name='number_formats')
    country = models.ForeignKey('localization.Country', on_delete=models.SET_NULL, null=True, blank=True, related_name='number_formats')
    decimal_symbol = models.CharField(max_length=3, default='.')
    grouping_symbol = models.CharField(max_length=3, default=',')
    grouping_size = models.PositiveSmallIntegerField(default=3)
    secondary_grouping = models.PositiveSmallIntegerField(null=True, blank=True, help_text=_("For South Asian: 2 (gives 1,00,000)"))
    negative_sign = models.CharField(max_length=5, default='-')
    positive_sign = models.CharField(max_length=5, blank=True)
    percent_symbol = models.CharField(max_length=5, default='%')
    infinity_symbol = models.CharField(max_length=10, default='∞')
    nan_symbol = models.CharField(max_length=10, default='NaN')
    native_digits = models.CharField(max_length=20, blank=True)
    min_fraction_digits = models.PositiveSmallIntegerField(default=0)
    max_fraction_digits = models.PositiveSmallIntegerField(default=3)
    use_grouping = models.BooleanField(default=True)
    number_system = models.CharField(max_length=20, default='latn', help_text=_("CLDR number system (latn, arab, beng, etc.)"))

    class Meta:
        unique_together = ['language', 'country']
        verbose_name = _("Number Format")
        verbose_name_plural = _("Number Formats")

    def __str__(self):
        lang = getattr(self.language, 'code', '?')
        return f"[{lang}] number format (sep: {self.decimal_symbol})"


class AddressFormat(models.Model):
    """Postal address format per country"""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    country = models.OneToOneField('localization.Country', on_delete=models.CASCADE, related_name='address_format')
    format_template = models.TextField(help_text=_("Template with {name}, {street}, {city}, {postal_code}, {country} placeholders"))
    required_fields = models.JSONField(default=list, blank=True)
    optional_fields = models.JSONField(default=list, blank=True)
    postal_code_label = models.CharField(max_length=50, default='Postal Code')
    postal_code_regex = models.CharField(max_length=100, blank=True)
    postal_code_example = models.CharField(max_length=20, blank=True)
    state_label = models.CharField(max_length=50, blank=True, default='State')
    district_label = models.CharField(max_length=50, blank=True, default='District')
    city_label = models.CharField(max_length=50, blank=True, default='City')
    uses_state = models.BooleanField(default=True)
    uses_district = models.BooleanField(default=False)
    uses_postal_code = models.BooleanField(default=True)
    uses_upazila = models.BooleanField(default=False, help_text=_("Bangladesh upazila"))
    uses_thana = models.BooleanField(default=False, help_text=_("Bangladesh thana/police station"))
    has_apartment_field = models.BooleanField(default=True)
    address_line_count = models.PositiveSmallIntegerField(default=2)
    example_address = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = _("Address Format")
        verbose_name_plural = _("Address Formats")

    def __str__(self):
        country_code = getattr(self.country, 'code', '?')
        return f"Address format for {country_code}"


# ── Webhook Management ────────────────────────────────────────────
class WebhookRegistration(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    """Registered webhook endpoints — DB-তে manage করা হয়"""
    name         = models.CharField(max_length=200)
    url          = models.URLField(help_text=_('Webhook endpoint URL'))
    secret       = models.CharField(max_length=500, blank=True, help_text=_('HMAC signing secret'))
    events       = models.JSONField(default=list, help_text=_('Events to subscribe: ["translation.updated", "*"]'))
    is_active    = models.BooleanField(default=True)
    retry_count  = models.PositiveSmallIntegerField(default=3)
    timeout_secs = models.PositiveSmallIntegerField(default=10)
    last_called  = models.DateTimeField(null=True, blank=True)
    last_status  = models.PositiveSmallIntegerField(null=True, blank=True)
    total_calls  = models.PositiveIntegerField(default=0)
    failed_calls = models.PositiveIntegerField(default=0)
    headers      = models.JSONField(default=dict, blank=True, help_text=_('Extra HTTP headers'))
    created_by   = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='webhooks'
    )

    class Meta:
        verbose_name = _('Webhook Registration')
        ordering = ['name']

    def __str__(self):
        return f"{self.name} → {self.url[:50]}"


class WebhookDeliveryLog(models.Model):
    """Webhook delivery attempts log"""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    webhook    = models.ForeignKey(WebhookRegistration, on_delete=models.CASCADE, related_name='deliveries')
    event      = models.CharField(max_length=100)
    payload    = models.JSONField(default=dict)
    response_status = models.PositiveSmallIntegerField(null=True, blank=True)
    response_body   = models.TextField(blank=True)
    attempt    = models.PositiveSmallIntegerField(default=1)
    delivered  = models.BooleanField(default=False)
    error      = models.TextField(blank=True)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        verbose_name = _('Webhook Delivery Log')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['webhook', 'delivered', 'created_at'], name='idx_webhook_delivered_crea_2f2'),
        ]
