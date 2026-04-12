"""
api/ai_engine/NLP_ENGINES/language_detector.py
===============================================
Language Detector — text এর ভাষা identify করো।
Bengali, English, Hindi, Arabic, Urdu support।
Auto-routing for localized responses।
"""
import re, logging
from typing import Dict
logger = logging.getLogger(__name__)

LANGUAGE_RANGES: Dict[str, tuple] = {
    'bn': ('ঀ', '৿'),
    'hi': ('ऀ', 'ॿ'),
    'ar': ('؀', 'ۿ'),
    'ur': ('؀', 'ۿ'),
}

class LanguageDetector:
    def detect(self, text: str) -> dict:
        if not text or len(text.strip()) < 3:
            return {'language': 'en', 'confidence': 0.50, 'script': 'latin'}
        total = max(len(text), 1)
        char_counts: Dict[str, int] = {}
        for char in text:
            for lang, (lo, hi) in LANGUAGE_RANGES.items():
                if lo <= char <= hi:
                    char_counts[lang] = char_counts.get(lang, 0) + 1
        ascii_count = sum(1 for c in text if c.isalpha() and ord(c) < 128)
        ratios = {lang: count/total for lang, count in char_counts.items()}
        ratios['en'] = ascii_count / total
        if not ratios:
            return {'language': 'en', 'confidence': 0.60, 'script': 'latin'}
        best_lang = max(ratios, key=ratios.get)
        confidence = min(0.99, ratios[best_lang] * 3)
        script_map = {'bn':'bengali','hi':'devanagari','ar':'arabic','ur':'arabic','en':'latin'}
        return {
            'language':   best_lang,
            'confidence': round(confidence, 4),
            'script':     script_map.get(best_lang, 'unknown'),
            'all_ratios': {k: round(v, 4) for k, v in ratios.items() if v > 0.01},
            'is_mixed':   sum(1 for v in ratios.values() if v > 0.10) > 1,
        }

    def detect_bulk(self, texts: list) -> list:
        return [self.detect(t) for t in texts]

    def get_response_language(self, user_language: str, supported: list = None) -> str:
        supported = supported or ['en', 'bn']
        return user_language if user_language in supported else 'en'

    def localize_message(self, message_key: str, language: str) -> str:
        messages = {
            'welcome': {'en': 'Welcome!', 'bn': 'স্বাগতম!'},
            'error':   {'en': 'An error occurred.', 'bn': 'একটি ত্রুটি হয়েছে।'},
            'success': {'en': 'Success!', 'bn': 'সফল!'},
        }
        return messages.get(message_key, {}).get(language, messages.get(message_key, {}).get('en', message_key))
