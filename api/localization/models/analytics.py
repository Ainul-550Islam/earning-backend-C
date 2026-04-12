# models/analytics.py — LocalizationInsight, TranslationCoverage, LanguageUsageStat, GeoInsight
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


class LocalizationInsight(models.Model):
    """Daily localization usage stats — aggregated per day"""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    date = models.DateField(db_index=True, help_text=_("Stat date"))
    language = models.ForeignKey('localization.Language', on_delete=models.CASCADE, related_name='insights', null=True, blank=True)
    country = models.ForeignKey('localization.Country', on_delete=models.SET_NULL, null=True, blank=True, related_name='insights')
    total_requests = models.PositiveIntegerField(default=0)
    unique_users = models.PositiveIntegerField(default=0)
    translation_hits = models.PositiveIntegerField(default=0, help_text=_("Translation lookups"))
    translation_misses = models.PositiveIntegerField(default=0, help_text=_("Missing translations"))
    cache_hits = models.PositiveIntegerField(default=0)
    cache_misses = models.PositiveIntegerField(default=0)
    avg_response_time_ms = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    currency_conversions = models.PositiveIntegerField(default=0)
    language_switches = models.PositiveIntegerField(default=0)
    geo_lookups = models.PositiveIntegerField(default=0)
    top_missing_keys = models.JSONField(default=list, blank=True, help_text=_("Top 10 most-missing translation keys"))
    top_endpoints = models.JSONField(default=list, blank=True)
    platform_breakdown = models.JSONField(default=dict, blank=True, help_text=_("web/mobile/api breakdown"))
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = ['date', 'language', 'country']
        ordering = ['-date']
        verbose_name = _("Localization Insight")
        verbose_name_plural = _("Localization Insights")
        indexes = [
            models.Index(fields=['date']),
            models.Index(fields=['language', 'date']),
            models.Index(fields=['country', 'date']),
        ]

    def __str__(self):
        lang = getattr(self.language, 'code', 'all') if self.language else 'all'
        return f"Insight [{lang}] {self.date} — {self.total_requests} requests"

    @property
    def cache_hit_rate(self):
        total = self.cache_hits + self.cache_misses
        return round((self.cache_hits / total * 100), 2) if total > 0 else 0

    @property
    def translation_hit_rate(self):
        total = self.translation_hits + self.translation_misses
        return round((self.translation_hits / total * 100), 2) if total > 0 else 0

    @classmethod
    def get_summary(cls, days=30, language_code=None):
        from django.db.models import Sum, Avg
        cutoff = timezone.now().date() - timedelta(days=days)
        qs = cls.objects.filter(date__gte=cutoff)
        if language_code:
            qs = qs.filter(language__code=language_code)
        return qs.aggregate(
            total_requests=Sum('total_requests'),
            total_hits=Sum('translation_hits'),
            total_misses=Sum('translation_misses'),
            avg_response=Avg('avg_response_time_ms'),
        )


class TranslationCoverage(models.Model):
    """Translation coverage percentage per language — updated daily"""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    language = models.OneToOneField('localization.Language', on_delete=models.CASCADE, related_name='coverage_stat')
    total_keys = models.PositiveIntegerField(default=0)
    translated_keys = models.PositiveIntegerField(default=0)
    approved_keys = models.PositiveIntegerField(default=0)
    pending_review_keys = models.PositiveIntegerField(default=0)
    machine_translated_keys = models.PositiveIntegerField(default=0)
    coverage_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    approved_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    missing_keys = models.PositiveIntegerField(default=0)
    last_calculated_at = models.DateTimeField(null=True, blank=True)
    coverage_by_namespace = models.JSONField(default=dict, blank=True, help_text=_("Coverage per namespace/category"))
    top_missing = models.JSONField(default=list, blank=True, help_text=_("Top 20 missing keys by importance"))
    trend_7d = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, help_text=_("Coverage change % over last 7 days"))
    trend_30d = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)

    class Meta:
        verbose_name = _("Translation Coverage")
        verbose_name_plural = _("Translation Coverages")
        indexes = [models.Index(fields=['coverage_percent'])]

    def __str__(self):
        lang = getattr(self.language, 'code', '?')
        return f"Coverage [{lang}]: {self.coverage_percent}%"

    def recalculate(self):
        """Coverage stats আবার calculate করে"""
        try:
            from .core import TranslationKey, Translation
            total = TranslationKey.objects.count()
            translated = Translation.objects.filter(language=self.language).count()
            approved = Translation.objects.filter(language=self.language, is_approved=True).count()
            pending = Translation.objects.filter(language=self.language, is_approved=False).count()
            machine = Translation.objects.filter(language=self.language, source='auto').count()
            self.total_keys = total
            self.translated_keys = translated
            self.approved_keys = approved
            self.pending_review_keys = pending
            self.machine_translated_keys = machine
            self.missing_keys = total - translated
            self.coverage_percent = round((translated / total * 100), 2) if total > 0 else 0
            self.approved_percent = round((approved / total * 100), 2) if total > 0 else 0
            self.last_calculated_at = timezone.now()
            self.save()
        except Exception as e:
            logger.error(f"Coverage recalculate failed for {self.language}: {e}")


class LanguageUsageStat(models.Model):
    """Daily Active Users (DAU) per language"""
    created_at = models.DateTimeField(auto_now_add=True)
    date = models.DateField(db_index=True)
    language = models.ForeignKey('localization.Language', on_delete=models.CASCADE, related_name='usage_stats')
    dau = models.PositiveIntegerField(default=0, help_text=_("Daily Active Users"))
    mau = models.PositiveIntegerField(default=0, help_text=_("Monthly Active Users (rolling 30d)"))
    new_users = models.PositiveIntegerField(default=0)
    returning_users = models.PositiveIntegerField(default=0)
    session_count = models.PositiveIntegerField(default=0)
    avg_session_duration_seconds = models.PositiveIntegerField(default=0)
    page_views = models.PositiveIntegerField(default=0)
    api_calls = models.PositiveIntegerField(default=0)
    translation_requests = models.PositiveIntegerField(default=0)
    top_countries = models.JSONField(default=list, blank=True, help_text=_("Top 5 countries using this language"))
    top_pages = models.JSONField(default=list, blank=True)
    device_breakdown = models.JSONField(default=dict, blank=True, help_text=_("mobile/desktop/tablet"))
    source_breakdown = models.JSONField(default=dict, blank=True, help_text=_("organic/direct/referral"))

    class Meta:
        unique_together = ['date', 'language']
        ordering = ['-date']
        verbose_name = _("Language Usage Stat")
        verbose_name_plural = _("Language Usage Stats")
        indexes = [
            models.Index(fields=['date', 'language']),
            models.Index(fields=['language', 'dau']),
        ]

    def __str__(self):
        lang = getattr(self.language, 'code', '?')
        return f"[{lang}] {self.date}: DAU={self.dau}"


class GeoInsight(models.Model):
    """Users per country/region — geographic usage analytics"""
    created_at = models.DateTimeField(auto_now_add=True)
    date = models.DateField(db_index=True)
    country = models.ForeignKey('localization.Country', on_delete=models.CASCADE, related_name='geo_insights', null=True, blank=True)
    country_code = models.CharField(max_length=2, blank=True, db_index=True)
    region_name = models.CharField(max_length=100, blank=True)
    city_name = models.CharField(max_length=100, blank=True)
    total_users = models.PositiveIntegerField(default=0)
    total_requests = models.PositiveIntegerField(default=0)
    top_language = models.ForeignKey('localization.Language', on_delete=models.SET_NULL, null=True, blank=True, related_name='geo_insights_top')
    language_distribution = models.JSONField(default=dict, blank=True, help_text=_("Language code → user count"))
    currency_distribution = models.JSONField(default=dict, blank=True)
    vpn_users = models.PositiveIntegerField(default=0)
    mobile_users = models.PositiveIntegerField(default=0)
    desktop_users = models.PositiveIntegerField(default=0)
    avg_response_time_ms = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)

    class Meta:
        unique_together = ['date', 'country', 'region_name', 'city_name']
        ordering = ['-date', '-total_users']
        verbose_name = _("Geo Insight")
        verbose_name_plural = _("Geo Insights")
        indexes = [
            models.Index(fields=['date']),
            models.Index(fields=['country', 'date']),
            models.Index(fields=['country_code']),
        ]

    def __str__(self):
        location = self.country_code or 'Global'
        if self.city_name:
            location = f"{self.city_name}, {location}"
        return f"Geo [{location}] {self.date}: {self.total_users} users"
