# services/translation/NamespaceLazyLoader.py
"""Namespace-based lazy loading — frontend fetches only needed namespace."""
import logging
from typing import Dict, List
from django.core.cache import cache
logger = logging.getLogger(__name__)


class NamespaceLazyLoader:
    """
    Namespace lazy loading — instead of one big pack, fetch by namespace.
    Frontend: fetch /api/localization/public/pack/bn/offer/ → only offer keys
    """

    NAMESPACES = [
        "common", "auth", "nav", "offer", "earning", "withdraw",
        "referral", "currency", "error", "pagination", "form",
        "table", "format", "status", "notification", "user",
        "language", "country",
    ]

    def get_namespace_pack(self, language_code: str, namespace: str, version: str = "v1") -> Dict:
        """Single namespace pack return করে — cached।"""
        cache_key = f"ns_pack_{language_code}_{namespace}_{version}"
        cached = cache.get(cache_key)
        if cached:
            cached["_cache_hit"] = True
            return cached

        try:
            from ..models.core import Translation, Language, TranslationKey
            lang = Language.objects.filter(code=language_code, is_active=True).first()
            if not lang:
                return {"error": f"Language {language_code} not found"}

            qs = Translation.objects.filter(
                language=lang,
                is_approved=True,
                key__category=namespace,
            ).select_related("key").only("key__key", "value")

            translations = {t.key.key: t.value for t in qs}

            # Fallback to English for missing keys
            default_lang = Language.objects.filter(is_default=True).first()
            if default_lang and default_lang != lang:
                missing_keys = set(
                    TranslationKey.objects.filter(category=namespace).values_list("key", flat=True)
                ) - set(translations.keys())
                if missing_keys:
                    for t in Translation.objects.filter(
                        language=default_lang,
                        key__key__in=missing_keys,
                        is_approved=True,
                    ).select_related("key"):
                        translations[t.key.key] = t.value  # Fallback value

            result = {
                "language": language_code,
                "namespace": namespace,
                "version": version,
                "count": len(translations),
                "translations": translations,
                "_cache_hit": False,
            }
            cache.set(cache_key, result, 3600)
            return result
        except Exception as e:
            logger.error(f"get_namespace_pack failed: {e}")
            return {"error": str(e)}

    def get_all_namespaces(self, language_code: str) -> Dict[str, int]:
        """All namespaces-এর key count।"""
        try:
            from ..models.core import Translation, Language
            lang = Language.objects.filter(code=language_code, is_active=True).first()
            if not lang:
                return {}
            from django.db.models import Count
            ns_counts = Translation.objects.filter(
                language=lang, is_approved=True
            ).values("key__category").annotate(count=Count("id")).order_by("key__category")
            return {row["key__category"] or "uncategorized": row["count"] for row in ns_counts}
        except Exception as e:
            return {}

    def invalidate_namespace(self, language_code: str, namespace: str):
        """Namespace cache invalidate করে।"""
        try:
            pattern = f"ns_pack_{language_code}_{namespace}_*"
            cache.delete_pattern(pattern)
        except Exception:
            cache.delete(f"ns_pack_{language_code}_{namespace}_v1")
