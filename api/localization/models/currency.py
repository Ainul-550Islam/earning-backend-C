# models/currency.py — ExchangeRate, ExchangeRateProvider, CurrencyFormat, CurrencyConversionLog
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class ExchangeRate(models.Model):
    """Historical and real-time currency exchange rates"""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    from_currency = models.ForeignKey('localization.Currency', on_delete=models.CASCADE, related_name='rates_from')
    to_currency = models.ForeignKey('localization.Currency', on_delete=models.CASCADE, related_name='rates_to')
    rate = models.DecimalField(max_digits=20, decimal_places=10, help_text=_("Exchange rate"))
    bid_rate = models.DecimalField(max_digits=20, decimal_places=10, null=True, blank=True)
    ask_rate = models.DecimalField(max_digits=20, decimal_places=10, null=True, blank=True)
    mid_rate = models.DecimalField(max_digits=20, decimal_places=10, null=True, blank=True)
    date = models.DateField(db_index=True, help_text=_("Rate date"))
    fetched_at = models.DateTimeField(default=timezone.now)
    valid_until = models.DateTimeField(null=True, blank=True)
    source = models.CharField(max_length=50, default='manual', choices=[
        ('manual','Manual'), ('openexchangerates','Open Exchange Rates'),
        ('fixer','Fixer.io'), ('currencylayer','CurrencyLayer'),
        ('xe','XE.com'), ('ecb','European Central Bank'),
        ('bangladesh_bank','Bangladesh Bank'), ('fed','Federal Reserve'),
        ('coinbase','Coinbase'), ('binance','Binance'),
    ])
    is_official = models.BooleanField(default=False, help_text=_("Official central bank rate?"))
    change_percent = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)
    raw_response = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-date', '-fetched_at']
        verbose_name = _("Exchange Rate")
        verbose_name_plural = _("Exchange Rates")
        indexes = [
            models.Index(fields=['from_currency', 'to_currency', 'date'], name='idx_from_currency_to_curre_e02'),
            models.Index(fields=['date'], name='idx_date_1084'),
            models.Index(fields=['source'], name='idx_source_1085'),
        ]

    def __str__(self):
        from_code = getattr(self.from_currency, 'code', '?') if self.from_currency else '?'
        to_code = getattr(self.to_currency, 'code', '?') if self.to_currency else '?'
        return f"{from_code}→{to_code}: {self.rate} ({self.date})"

    @classmethod
    def get_latest(cls, from_code, to_code):
        try:
            return cls.objects.filter(
                from_currency__code=from_code,
                to_currency__code=to_code
            ).order_by('-date', '-fetched_at').first()
        except Exception as e:
            logger.error(f"Rate lookup failed: {e}")
            return None

    @classmethod
    def get_historical(cls, from_code, to_code, days=30):
        cutoff = timezone.now().date() - __import__('datetime').timedelta(days=days)
        return cls.objects.filter(
            from_currency__code=from_code,
            to_currency__code=to_code,
            date__gte=cutoff
        ).order_by('date')


class ExchangeRateProvider(models.Model):
    """Configuration for exchange rate API providers"""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    name = models.CharField(max_length=100, unique=True)
    provider_type = models.CharField(max_length=50, choices=[
        ('openexchangerates','Open Exchange Rates'), ('fixer','Fixer.io'),
        ('currencylayer','CurrencyLayer'), ('xe','XE.com'), ('ecb','ECB'),
        ('bangladesh_bank','Bangladesh Bank'), ('coinbase','Coinbase'),
        ('custom','Custom'),
    ])
    api_key = models.CharField(max_length=500, blank=True, help_text=_("API key (stored encrypted)"))
    base_url = models.URLField(blank=True)
    base_currency = models.ForeignKey('localization.Currency', on_delete=models.SET_NULL, null=True, blank=True, related_name='provider_base')
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    fetch_interval_minutes = models.PositiveIntegerField(default=60, help_text=_("How often to fetch rates (minutes)"))
    supported_currencies = models.ManyToManyField('localization.Currency', blank=True, related_name='supported_by_providers')
    last_fetch_at = models.DateTimeField(null=True, blank=True)
    last_success_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    total_requests = models.PositiveIntegerField(default=0)
    failed_requests = models.PositiveIntegerField(default=0)
    rate_limit_per_month = models.PositiveIntegerField(null=True, blank=True)
    requests_this_month = models.PositiveIntegerField(default=0)
    config = models.JSONField(default=dict, blank=True, help_text=_("Provider-specific configuration"))
    priority = models.PositiveSmallIntegerField(default=1, help_text=_("Lower = higher priority in fallback chain"))

    class Meta:
        ordering = ['priority', 'name']
        verbose_name = _("Exchange Rate Provider")
        verbose_name_plural = _("Exchange Rate Providers")

    def __str__(self):
        status = "✓" if self.is_active else "✗"
        return f"{status} {self.name} (Priority {self.priority})"

    def save(self, *args, **kwargs):
        from django.db import transaction
        with transaction.atomic():
            if self.is_default:
                ExchangeRateProvider.objects.filter(is_default=True).exclude(pk=self.pk).update(is_default=False)
            super().save(*args, **kwargs)


class CurrencyFormat(models.Model):
    """Currency display format per locale — thousands/decimal separators, symbol position"""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    currency = models.ForeignKey('localization.Currency', on_delete=models.CASCADE, related_name='formats')
    language = models.ForeignKey('localization.Language', on_delete=models.CASCADE, related_name='currency_formats')
    country = models.ForeignKey('localization.Country', on_delete=models.SET_NULL, null=True, blank=True, related_name='currency_formats')
    symbol_position = models.CharField(max_length=6, default='before', choices=[('before','Before'),('after','After')])
    symbol_spacing = models.BooleanField(default=False, help_text=_("Space between symbol and amount?"))
    thousands_separator = models.CharField(max_length=3, default=',')
    decimal_separator = models.CharField(max_length=3, default='.')
    grouping_pattern = models.CharField(max_length=20, default='3', help_text=_("e.g. 3 for 1,000 or 3,2 for South Asian 1,00,000"))
    decimal_places = models.PositiveSmallIntegerField(default=2)
    negative_format = models.CharField(max_length=20, default='-{symbol}{amount}')
    positive_format = models.CharField(max_length=20, default='{symbol}{amount}')
    zero_format = models.CharField(max_length=20, blank=True)
    rounding_rule = models.CharField(max_length=10, default='round', choices=[('round','Round'),('floor','Floor'),('ceil','Ceiling')])
    native_digits = models.CharField(max_length=20, blank=True, help_text=_("Native digit chars e.g. ০১২৩৪৫৬৭৮৯"))

    class Meta:
        unique_together = ['currency', 'language', 'country']
        verbose_name = _("Currency Format")
        verbose_name_plural = _("Currency Formats")

    def __str__(self):
        currency_code = getattr(self.currency, 'code', '?')
        lang_code = getattr(self.language, 'code', '?')
        return f"{currency_code} format for {lang_code}"

    def format_amount(self, amount, use_symbol=True):
        """Amount format করে এই locale-এর নিয়মে"""
        try:
            from decimal import Decimal
            dec_amount = Decimal(str(amount))
            formatted = f"{dec_amount:,.{self.decimal_places}f}"
            # Apply separators
            formatted = formatted.replace(',', '|COMMA|').replace('.', self.decimal_separator)
            formatted = formatted.replace('|COMMA|', self.thousands_separator)
            if use_symbol and self.currency:
                sym = self.currency.symbol
                if self.symbol_position == 'before':
                    space = ' ' if self.symbol_spacing else ''
                    return f"{sym}{space}{formatted}"
                else:
                    space = ' ' if self.symbol_spacing else ''
                    return f"{formatted}{space}{sym}"
            return formatted
        except Exception as e:
            logger.error(f"CurrencyFormat.format_amount failed: {e}")
            return str(amount)


class CurrencyConversionLog(models.Model):
    """Audit log for every currency conversion"""
    created_at = models.DateTimeField(auto_now_add=True)
    from_currency = models.ForeignKey('localization.Currency', on_delete=models.SET_NULL, null=True, related_name='conversion_logs_from')
    to_currency = models.ForeignKey('localization.Currency', on_delete=models.SET_NULL, null=True, related_name='conversion_logs_to')
    amount = models.DecimalField(max_digits=20, decimal_places=8)
    converted_amount = models.DecimalField(max_digits=20, decimal_places=8)
    rate_used = models.DecimalField(max_digits=20, decimal_places=10)
    rate_source = models.CharField(max_length=50, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='conversion_logs')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    request_path = models.CharField(max_length=500, blank=True)
    session_key = models.CharField(max_length=64, blank=True)
    response_time_ms = models.PositiveIntegerField(null=True, blank=True)
    was_cached = models.BooleanField(default=False)
    error_occurred = models.BooleanField(default=False)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _("Currency Conversion Log")
        verbose_name_plural = _("Currency Conversion Logs")
        indexes = [
            models.Index(fields=['from_currency', 'to_currency', 'created_at'], name='idx_from_currency_to_curre_0cf'),
            models.Index(fields=['user', 'created_at'], name='idx_user_created_at_1087'),
            models.Index(fields=['created_at'], name='idx_created_at_1088'),
        ]

    def __str__(self):
        from_code = getattr(self.from_currency, 'code', '?') if self.from_currency else '?'
        to_code = getattr(self.to_currency, 'code', '?') if self.to_currency else '?'
        return f"{self.amount} {from_code} → {self.converted_amount} {to_code} @ {self.created_at.date()}"
