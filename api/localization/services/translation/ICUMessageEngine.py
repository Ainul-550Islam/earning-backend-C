# services/translation/ICUMessageEngine.py
"""
ICUMessageEngine — Service wrapper around ICU utilities.
Used by translation endpoints and middleware.
"""
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ICUMessageEngine:
    """
    ICU Message Format engine — format, validate, detect, translate.
    """

    def __init__(self):
        from ...utils.icu import ICUMessageFormatter
        self._formatter = ICUMessageFormatter()

    def format(self, template: str, values: Dict[str, Any], locale: str = 'en') -> str:
        """
        ICU template format করে।
        Example:
          template = "You have {count, plural, one {# message} other {# messages}}"
          values   = {"count": 5}
          locale   = "bn"
          → "You have 5 messages"  (or "আপনার ৫টি বার্তা আছে" if translated)
        """
        try:
            return self._formatter.format(template, values, locale)
        except Exception as e:
            logger.error(f"ICU format failed: {e}")
            # Graceful degradation
            result = template
            for k, v in values.items():
                result = result.replace('{' + k + '}', str(v))
            return result

    def validate(self, template: str) -> Dict:
        """Template validate করে — syntax errors, missing 'other' form, etc."""
        try:
            from ...utils.icu import validate_icu_template
            return validate_icu_template(template)
        except Exception as e:
            logger.error(f"ICU validate failed: {e}")
            return {'valid': False, 'errors': [str(e)], 'warnings': []}

    def is_icu(self, text: str) -> bool:
        """Text ICU format কিনা detect করে"""
        try:
            from ...utils.icu import is_icu_format
            return is_icu_format(text)
        except Exception:
            return False

    def extract_variables(self, template: str) -> List[str]:
        """Template থেকে variable names extract করে"""
        try:
            from ...utils.icu import extract_icu_variables
            return extract_icu_variables(template)
        except Exception:
            return []

    def translate_icu_template(
        self,
        source_template: str,
        source_lang: str,
        target_lang: str,
        domain: str = '',
    ) -> str:
        """
        ICU template-এর text parts translate করে, structure অক্ষুণ্ণ রাখে।
        Example:
          "You have {count, plural, one {# item} other {# items}}"
          → (Bengali) "আপনার {count, plural, one {# টি আইটেম} other {# টি আইটেম}} আছে"
        """
        try:
            from ...utils.icu import ICUMessageFormatter, is_icu_format
            from .TranslationEngine import TranslationEngine

            if not is_icu_format(source_template):
                # Not ICU — translate directly
                engine = TranslationEngine()
                result = engine.translate(source_template, source_lang, target_lang, domain)
                return result.get('translated', source_template)

            engine = TranslationEngine()

            # Extract and translate text segments while preserving ICU structure
            translated = self._translate_icu_parts(source_template, source_lang, target_lang, engine, domain)
            return translated

        except Exception as e:
            logger.error(f"ICU template translation failed: {e}")
            return source_template

    def _translate_icu_parts(
        self, template: str, source_lang: str, target_lang: str,
        engine, domain: str
    ) -> str:
        """ICU template-এর text parts translate করে, placeholders রাখে intact"""
        import re

        # Strategy: translate the whole template as-is,
        # but protect ICU syntax patterns as placeholders
        # Pattern: {varname, type, ...} → protect the ICU syntax, translate text content

        # Find all top-level ICU blocks
        result = template
        # For now, translate literal text parts between ICU blocks
        # Split on top-level ICU blocks
        parts = re.split(r'(\{[^{}]*(?:\{[^{}]*\}[^{}]*)?\})', template)

        translated_parts = []
        for part in parts:
            if part.startswith('{') and ',' in part:
                # ICU block — translate inner text but keep structure
                translated_parts.append(self._translate_icu_block(part, source_lang, target_lang, engine, domain))
            elif part.strip():
                # Plain text — translate it
                if len(part.strip()) > 2:
                    result = engine.translate(part, source_lang, target_lang, domain)
                    translated_parts.append(result.get('translated', part))
                else:
                    translated_parts.append(part)
            else:
                translated_parts.append(part)

        return ''.join(translated_parts)

    def _translate_icu_block(
        self, block: str, source_lang: str, target_lang: str, engine, domain: str
    ) -> str:
        """Single ICU block translate করে"""
        try:
            # Extract option values and translate them
            import re
            # Find option templates: one {# item} → translate "item"
            def translate_match(m):
                text = m.group(1)
                if text.strip() and len(text.strip()) > 1:
                    result = engine.translate(text.strip(), source_lang, target_lang, domain)
                    translated = result.get('translated', text)
                    return f'{{{translated}}}'
                return m.group(0)

            # Replace option values
            translated_block = re.sub(r'\{([^{}]+)\}', translate_match, block)
            return translated_block
        except Exception:
            return block

    def get_plural_forms(self, locale: str) -> Dict:
        """Locale-র plural forms info"""
        try:
            from ...utils.plural import get_cldr_info
            return get_cldr_info(locale)
        except Exception as e:
            logger.error(f"Get plural forms failed: {e}")
            return {'locale': locale, 'forms': ['one', 'other'], 'form_count': 2}

    def format_plural(self, count: int, singular: str, plural: str, locale: str = 'en') -> str:
        """
        Simple plural helper — no ICU template needed.
        format_plural(1, "item", "items", "en") → "1 item"
        format_plural(5, "item", "items", "en") → "5 items"
        """
        try:
            from ...utils.plural import get_plural_form
            form = get_plural_form(count, locale)
            text = singular if form == 'one' else plural
            return f"{count} {text}"
        except Exception:
            return f"{count} {singular if count == 1 else plural}"
