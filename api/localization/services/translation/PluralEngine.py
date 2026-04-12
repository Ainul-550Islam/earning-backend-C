# services/translation/PluralEngine.py
"""
PluralEngine — Service for plural form management.
Links CLDR plural rules to TranslationKey plural forms.
"""
import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class PluralEngine:
    """Plural form detection, generation, and validation service"""

    def get_plural_form(self, count: float, language_code: str) -> str:
        """CLDR plural category for count in language"""
        try:
            from ...utils.plural import get_plural_form
            return get_plural_form(count, language_code)
        except Exception as e:
            logger.error(f"get_plural_form failed: {e}")
            return 'other'

    def get_forms_for_language(self, language_code: str) -> List[str]:
        """Language-এর সব plural forms"""
        try:
            from ...utils.plural import get_plural_forms_for_locale
            return get_plural_forms_for_locale(language_code)
        except Exception:
            return ['one', 'other']

    def get_cldr_examples(self, language_code: str) -> Dict:
        """Plural forms with example numbers"""
        try:
            from ...utils.plural import get_cldr_info
            return get_cldr_info(language_code)
        except Exception:
            return {'forms': ['one', 'other'], 'examples': {'one': [1], 'other': [2, 5]}}

    def generate_plural_templates(
        self, key_text: str, language_code: str
    ) -> Dict[str, str]:
        """
        Translation key-এর জন্য plural form templates generate করে।
        Translator-কে কোন forms fill করতে হবে সেটা দেখায়।
        """
        forms = self.get_forms_for_language(language_code)
        templates = {}
        for form in forms:
            templates[form] = f"[{form}] {key_text}"  # Empty template for translator
        return templates

    def validate_plural_completeness(
        self, translations: Dict[str, str], language_code: str
    ) -> Dict:
        """Translation-এ সব required plural forms আছে কিনা check করে"""
        required_forms = set(self.get_forms_for_language(language_code))
        provided_forms = set(k for k, v in translations.items() if v and v.strip())
        missing = required_forms - provided_forms
        extra = provided_forms - required_forms
        return {
            'valid': len(missing) == 0,
            'missing_forms': list(missing),
            'extra_forms': list(extra),
            'required_forms': list(required_forms),
            'provided_forms': list(provided_forms),
        }

    def update_language_plural_rules(self, language_code: str) -> bool:
        """Language model-এ plural rule save করে CLDR data থেকে"""
        try:
            from ..models.core import Language
            from ...utils.plural import get_plural_forms_for_locale, get_cldr_info
            lang = Language.objects.filter(code=language_code).first()
            if not lang:
                return False
            forms = get_plural_forms_for_locale(language_code)
            lang.plural_forms = len(forms)
            lang.save(update_fields=['plural_forms'])
            return True
        except Exception as e:
            logger.error(f"Update plural rules failed: {e}")
            return False

    def format_count(self, count: int, translations: Dict[str, str], language_code: str) -> str:
        """
        Count-এর জন্য correct plural form return করে।
        translations = {"one": "1 আইটেম", "other": "{count} আইটেম"}
        """
        try:
            form = self.get_plural_form(count, language_code)
            template = translations.get(form) or translations.get('other', str(count))
            return template.replace('{count}', str(count)).replace('#', str(count))
        except Exception:
            return str(count)
