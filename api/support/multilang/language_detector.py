"""
api/support/multilang/language_detector.py
FILE 55/70 — Auto Language Detection

User message-এর language auto-detect করো।
Bengali / Hindi / English / Arabic support।
"""
import re
import logging
from django.core.cache import cache

logger = logging.getLogger(__name__)


class LanguageDetector:
    """
    Unicode range-based fast language detection।
    Confidence score সহ।
    """

    SCRIPTS = {
        'bn': {'name': 'Bengali',    'range': (0x0980, 0x09FF), 'threshold': 0.05},
        'hi': {'name': 'Hindi',      'range': (0x0900, 0x097F), 'threshold': 0.05},
        'ar': {'name': 'Arabic',     'range': (0x0600, 0x06FF), 'threshold': 0.05},
        'zh': {'name': 'Chinese',    'range': (0x4E00, 0x9FFF), 'threshold': 0.05},
        'ja': {'name': 'Japanese',   'range': (0x3040, 0x30FF), 'threshold': 0.05},
        'ko': {'name': 'Korean',     'range': (0xAC00, 0xD7FF), 'threshold': 0.05},
        'ru': {'name': 'Russian',    'range': (0x0400, 0x04FF), 'threshold': 0.05},
    }

    # Common Bengali words (high confidence)
    BN_KEYWORDS = [
        'আমি','আমার','এটা','হয়নি','করেছি','টাকা','পাইনি','কেন',
        'বিকাশ','নগদ','কয়েন','একাউন্ট','পেমেন্ট','উইথড্র',
        'সাহায্য','সমস্যা','রিফান্ড','ব্যালেন্স','ভেরিফিকেশন',
    ]

    # Common Hindi words
    HI_KEYWORDS = [
        'मैं','मेरा','नहीं','है','पैसा','खाता','समस्या','मदद',
        'वापस','कृपया','धन्यवाद',
    ]

    def detect(self, text: str) -> dict:
        """
        Language detect করো।
        Returns: {language, confidence, script, name}
        """
        if not text or len(text.strip()) < 3:
            return self._result('en', 0.5)

        text_lower = text.lower()

        # Cache check
        cache_key  = f'lang_detect:{hash(text[:100])}'
        cached     = cache.get(cache_key)
        if cached:
            return cached

        # Unicode character analysis
        total_chars  = len([c for c in text if not c.isspace()])
        if total_chars == 0:
            return self._result('en', 0.5)

        scores = {}
        for lang, info in self.SCRIPTS.items():
            lo, hi = info['range']
            count  = sum(1 for c in text if lo <= ord(c) <= hi)
            ratio  = count / total_chars
            if ratio >= info['threshold']:
                scores[lang] = ratio

        # Bengali keyword boost
        bn_keywords_found = sum(1 for kw in self.BN_KEYWORDS if kw in text)
        if bn_keywords_found >= 1:
            scores['bn'] = scores.get('bn', 0) + bn_keywords_found * 0.1

        # Hindi keyword boost
        hi_keywords_found = sum(1 for kw in self.HI_KEYWORDS if kw in text)
        if hi_keywords_found >= 1:
            scores['hi'] = scores.get('hi', 0) + hi_keywords_found * 0.1

        if scores:
            best_lang  = max(scores, key=scores.get)
            confidence = min(scores[best_lang] * 2, 1.0)
            result     = self._result(best_lang, confidence)
        else:
            # Check if Latin/English
            latin_count = sum(1 for c in text if 'a' <= c.lower() <= 'z')
            confidence  = min(latin_count / max(total_chars, 1), 1.0)
            result      = self._result('en', confidence)

        cache.set(cache_key, result, timeout=3600)
        return result

    def detect_bulk(self, texts: list) -> list:
        return [self.detect(t) for t in texts]

    def is_bengali(self, text: str) -> bool:
        return self.detect(text)['language'] == 'bn'

    def is_english(self, text: str) -> bool:
        return self.detect(text)['language'] == 'en'

    def _result(self, language: str, confidence: float) -> dict:
        lang_names = {
            'en': 'English', 'bn': 'Bengali', 'hi': 'Hindi',
            'ar': 'Arabic',  'zh': 'Chinese', 'ja': 'Japanese',
            'ko': 'Korean',  'ru': 'Russian',
        }
        return {
            'language':   language,
            'name':       lang_names.get(language, language.upper()),
            'confidence': round(confidence, 3),
            'is_rtl':     language in ['ar', 'he', 'fa'],
        }


language_detector = LanguageDetector()