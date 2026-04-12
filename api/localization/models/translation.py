# models/translation.py
# TranslationCache, MissingTranslation (keep) + TranslationMemory, TranslationGlossary, TranslationVersion (new)
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.conf import settings
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


# ============================================================
# KEPT FROM ORIGINAL — TranslationCache
# ============================================================
class TranslationCache(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    language_code = models.CharField(max_length=10, db_index=True, help_text=_("Language code"))
    cache_key = models.CharField(max_length=255, db_index=True, help_text=_("Cache key"))
    cache_data = models.JSONField(default=dict, help_text=_("Cached translation data"))
    expires_at = models.DateTimeField(db_index=True, help_text=_("Cache expiration time"))
    hits = models.PositiveIntegerField(default=0, help_text=_("Number of cache hits"))

    class Meta:
        unique_together = ['language_code', 'cache_key']
        indexes = [models.Index(fields=['expires_at'])]
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
        try:
            return cls.objects.filter(expires_at__lte=timezone.now()).delete()
        except Exception as e:
            logger.error(f"Failed to clean expired cache: {e}")
            return 0, {}

    @classmethod
    def bulk_clean_expired(cls, days=7):
        try:
            cutoff = timezone.now() - timedelta(days=days)
            return cls.objects.filter(expires_at__lte=cutoff).delete()
        except Exception as e:
            logger.error(f"Bulk clean failed: {e}")
            return 0, {}


# ============================================================
# KEPT FROM ORIGINAL — MissingTranslation
# ============================================================
class MissingTranslation(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    key = models.CharField(max_length=255, db_index=True, help_text=_("Missing translation key"))
    language = models.ForeignKey('localization.Language', on_delete=models.CASCADE, help_text=_("Language where translation is missing"))
    context = models.TextField(blank=True, default='')
    request_path = models.CharField(max_length=500, blank=True, default='')
    user_agent = models.TextField(blank=True, default='')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='resolved_missing_translations'
    )
    occurrence_count = models.PositiveIntegerField(default=1)
    last_seen_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _("Missing Translation")
        verbose_name_plural = _("Missing Translations")
        indexes = [
            models.Index(fields=['key']),
            models.Index(fields=['language', 'resolved']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        key = getattr(self, 'key', 'Unknown') or 'Unknown'
        lang_code = getattr(self.language, 'code', 'unknown') if self.language else 'unknown'
        return f"Missing: {key} in {lang_code}"

    @classmethod
    def log_missing(cls, key, language_code, request=None, user=None):
        try:
            from .core import Language
            language = Language.objects.filter(code=language_code).first()
            if not language:
                return
            existing = cls.objects.filter(
                key=key, language=language,
                created_at__gte=timezone.now() - timedelta(hours=24)
            ).first()
            if existing:
                existing.occurrence_count += 1
                existing.last_seen_at = timezone.now()
                existing.save(update_fields=['occurrence_count', 'last_seen_at'])
                return
            data = {'key': key, 'language': language, 'user': user}
            if request:
                data.update({
                    'request_path': getattr(request, 'path', '')[:500],
                    'user_agent': request.META.get('HTTP_USER_AGENT', '')[:500] if hasattr(request, 'META') else '',
                    'ip_address': cls._get_client_ip(request),
                })
            cls.objects.create(**data)
        except Exception as e:
            logger.error(f"Failed to log missing translation: {e}")

    @staticmethod
    def _get_client_ip(request):
        try:
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                return x_forwarded_for.split(',')[0]
            return request.META.get('REMOTE_ADDR')
        except Exception:
            return None


# ============================================================
# NEW — TranslationMemory
# ============================================================
class TranslationMemory(models.Model):
    """Reuse past translated segments — Translation Memory (TM) system"""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    source_language = models.ForeignKey('localization.Language', on_delete=models.CASCADE, related_name='tm_source')
    target_language = models.ForeignKey('localization.Language', on_delete=models.CASCADE, related_name='tm_target')
    source_text = models.TextField(help_text=_("Original source text"))
    target_text = models.TextField(help_text=_("Translated text"))
    source_hash = models.CharField(max_length=64, db_index=True, help_text=_("SHA256 hash of normalized source"))
    domain = models.CharField(max_length=100, blank=True, db_index=True, help_text=_("Subject domain (finance, legal, marketing)"))
    context = models.TextField(blank=True)
    usage_count = models.PositiveIntegerField(default=0)
    is_approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_tm')
    quality_rating = models.PositiveSmallIntegerField(null=True, blank=True, help_text=_("Quality rating 1-5"))
    source_word_count = models.PositiveIntegerField(null=True, blank=True)
    target_word_count = models.PositiveIntegerField(null=True, blank=True)
    client = models.CharField(max_length=100, blank=True)
    project = models.CharField(max_length=100, blank=True)
    tags = models.JSONField(default=list, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-usage_count', '-created_at']
        verbose_name = _("Translation Memory")
        verbose_name_plural = _("Translation Memories")
        indexes = [
            models.Index(fields=['source_hash', 'source_language', 'target_language']),
            models.Index(fields=['domain']),
            models.Index(fields=['is_approved']),
        ]

    def __str__(self):
        src = getattr(self.source_language, 'code', '?') if self.source_language else '?'
        tgt = getattr(self.target_language, 'code', '?') if self.target_language else '?'
        return f"TM [{src}→{tgt}]: {self.source_text[:40]}..."

    def save(self, *args, **kwargs):
        import hashlib
        if self.source_text:
            normalized = ' '.join(self.source_text.lower().split())
            self.source_hash = hashlib.sha256(normalized.encode()).hexdigest()
            self.source_word_count = len(self.source_text.split())
        if self.target_text:
            self.target_word_count = len(self.target_text.split())
        super().save(*args, **kwargs)

    @classmethod
    def find_exact_match(cls, source_text, source_lang_code, target_lang_code, domain=''):
        import hashlib
        try:
            normalized = ' '.join(source_text.lower().split())
            source_hash = hashlib.sha256(normalized.encode()).hexdigest()
            qs = cls.objects.filter(
                source_hash=source_hash,
                source_language__code=source_lang_code,
                target_language__code=target_lang_code,
            )
            if domain:
                qs = qs.filter(domain=domain)
            result = qs.order_by('-is_approved', '-usage_count').first()
            if result:
                result.usage_count += 1
                result.last_used_at = timezone.now()
                result.save(update_fields=['usage_count', 'last_used_at'])
            return result
        except Exception as e:
            logger.error(f"TM lookup failed: {e}")
            return None


# ============================================================
# NEW — TranslationGlossary
# ============================================================
class TranslationGlossary(models.Model):
    """Brand terms, do-not-translate list, preferred translations per language"""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    source_language = models.ForeignKey('localization.Language', on_delete=models.CASCADE, related_name='glossary_source')
    source_term = models.CharField(max_length=500, help_text=_("Original term"))
    definition = models.TextField(blank=True)
    domain = models.CharField(max_length=100, blank=True, db_index=True)
    part_of_speech = models.CharField(
        max_length=20, blank=True,
        choices=[('noun','Noun'),('verb','Verb'),('adj','Adjective'),('phrase','Phrase'),('acronym','Acronym'),('proper','Proper Noun')]
    )
    is_do_not_translate = models.BooleanField(default=False, help_text=_("Leave this term untranslated"))
    is_brand_term = models.BooleanField(default=False, help_text=_("Brand/product name"))
    is_forbidden = models.BooleanField(default=False, help_text=_("Forbidden/blacklisted term"))
    forbidden_reason = models.TextField(blank=True)
    notes = models.TextField(blank=True, help_text=_("Notes for translators"))
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_glossary')
    tags = models.JSONField(default=list, blank=True)
    usage_count = models.PositiveIntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['source_term']
        verbose_name = _("Translation Glossary")
        verbose_name_plural = _("Translation Glossaries")
        indexes = [
            models.Index(fields=['source_term', 'source_language']),
            models.Index(fields=['domain']),
            models.Index(fields=['is_do_not_translate']),
            models.Index(fields=['is_brand_term']),
        ]

    def __str__(self):
        lang = getattr(self.source_language, 'code', '?') if self.source_language else '?'
        dnt = " [DNT]" if self.is_do_not_translate else ""
        return f"[{lang}] {self.source_term}{dnt}"


class TranslationGlossaryEntry(models.Model):
    """Per-language translation of a glossary term"""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    glossary = models.ForeignKey(TranslationGlossary, on_delete=models.CASCADE, related_name='entries')
    language = models.ForeignKey('localization.Language', on_delete=models.CASCADE, related_name='glossary_entries')
    translated_term = models.CharField(max_length=500)
    alternative_terms = models.JSONField(default=list, blank=True)
    forbidden_terms = models.JSONField(default=list, blank=True, help_text=_("Terms NOT to use"))
    notes = models.TextField(blank=True)
    is_approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_glossary_entries')

    class Meta:
        unique_together = ['glossary', 'language']
        verbose_name = _("Glossary Entry")
        verbose_name_plural = _("Glossary Entries")

    def __str__(self):
        lang = getattr(self.language, 'code', '?') if self.language else '?'
        return f"[{lang}] {self.translated_term}"


# ============================================================
# NEW — TranslationVersion
# ============================================================
class TranslationVersion(models.Model):
    """Version history for every translation change"""
    created_at = models.DateTimeField(auto_now_add=True)
    translation = models.ForeignKey('localization.Translation', on_delete=models.CASCADE, related_name='versions')
    version_number = models.PositiveIntegerField(default=1)
    value = models.TextField(help_text=_("Value at this version"))
    value_plural = models.TextField(blank=True, default='')
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='translation_versions')
    change_reason = models.TextField(blank=True, help_text=_("Why was this changed?"))
    source = models.CharField(max_length=20, default='manual', choices=[('manual','Manual'),('auto','Auto'),('import','Import'),('api','API')])
    is_approved = models.BooleanField(default=False)
    word_count = models.PositiveIntegerField(null=True, blank=True)
    char_count = models.PositiveIntegerField(null=True, blank=True)
    diff_from_previous = models.TextField(blank=True, help_text=_("Diff from previous version"))

    class Meta:
        ordering = ['-version_number']
        unique_together = ['translation', 'version_number']
        verbose_name = _("Translation Version")
        verbose_name_plural = _("Translation Versions")
        indexes = [
            models.Index(fields=['translation', 'version_number']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"Version {self.version_number} of {self.translation}"

    def save(self, *args, **kwargs):
        if self.value:
            self.word_count = len(self.value.split())
            self.char_count = len(self.value)
        super().save(*args, **kwargs)
