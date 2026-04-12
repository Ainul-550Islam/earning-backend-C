# services/translation/LanguageVariantService.py
"""
Language variant support — en-US vs en-GB, pt-BR vs pt-PT, zh-Hans vs zh-Hant.
Falls back to base language if variant not found.
"""
import logging
from typing import Optional, Dict, List
from django.core.cache import cache
logger = logging.getLogger(__name__)

VARIANT_FALLBACK = {
    'en-us': 'en', 'en-gb': 'en', 'en-au': 'en', 'en-ca': 'en', 'en-in': 'en',
    'pt-br': 'pt', 'pt-pt': 'pt',
    'zh-hans': 'zh', 'zh-hant': 'zh', 'zh-tw': 'zh', 'zh-hk': 'zh',
    'es-419': 'es', 'es-mx': 'es', 'es-ar': 'es', 'es-co': 'es',
    'fr-ca': 'fr', 'fr-be': 'fr', 'fr-ch': 'fr',
    'de-at': 'de', 'de-ch': 'de',
    'ar-sa': 'ar', 'ar-eg': 'ar', 'ar-ae': 'ar', 'ar-ma': 'ar',
    'bn-bd': 'bn', 'bn-in': 'bn',
}

VARIANT_DIFFERENCES = {
    # en-US vs en-GB key differences
    'en-us:en-gb': {
        'color': 'colour', 'analyze': 'analyse', 'organize': 'organise',
        'license': 'licence', 'center': 'centre', 'fiber': 'fibre',
    },
    # pt-BR vs pt-PT
    'pt-br:pt-pt': {
        'você': 'tu', 'celular': 'telemóvel', 'ônibus': 'autocarro',
        'apartamento': 'apartamento',
    },
}


class LanguageVariantService:
    """Handle language variants with intelligent fallback."""

    def get_translation(self, key: str, language_code: str, fallback_chain: bool = True) -> Optional[str]:
        """
        Translation পাওয়া — variant → base → default language fallback।
        'en-US' → check en-US → check en → return None
        """
        try:
            from ..models.core import Translation, TranslationKey, Language
            lang_code_norm = language_code.lower()

            # Try exact variant first
            lang = Language.objects.filter(code__iexact=language_code, is_active=True).first()
            if lang:
                trans = Translation.objects.filter(
                    key__key=key, language=lang, is_approved=True
                ).first()
                if trans:
                    return trans.value

            # Try base language fallback
            if fallback_chain:
                base_code = VARIANT_FALLBACK.get(lang_code_norm, lang_code_norm.split('-')[0])
                if base_code != language_code.lower():
                    base_lang = Language.objects.filter(code=base_code, is_active=True).first()
                    if base_lang:
                        trans = Translation.objects.filter(
                            key__key=key, language=base_lang, is_approved=True
                        ).first()
                        if trans:
                            return self._apply_variant_rules(trans.value, base_code, lang_code_norm)

            return None
        except Exception as e:
            logger.error(f"LanguageVariantService.get_translation failed: {e}")
            return None

    def _apply_variant_rules(self, text: str, base_lang: str, variant_lang: str) -> str:
        """Apply variant-specific word substitutions."""
        variant_key = f"{base_lang}:{variant_lang}"
        rules = VARIANT_DIFFERENCES.get(variant_key, {})
        result = text
        for base_word, variant_word in rules.items():
            result = result.replace(base_word, variant_word)
        return result

    def get_supported_variants(self) -> Dict[str, List[str]]:
        """All supported language variants"""
        variants: Dict[str, List[str]] = {}
        for variant, base in VARIANT_FALLBACK.items():
            variants.setdefault(base, []).append(variant)
        return variants

    def get_fallback_chain(self, language_code: str) -> List[str]:
        """Language-এর full fallback chain"""
        chain = [language_code]
        lang_lower = language_code.lower()
        base = VARIANT_FALLBACK.get(lang_lower, lang_lower.split('-')[0])
        if base != lang_lower:
            chain.append(base)
        chain.append('en')  # Ultimate fallback
        return list(dict.fromkeys(chain))  # Remove duplicates
