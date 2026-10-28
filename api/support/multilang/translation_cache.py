"""
api/support/multilang/translation_cache.py
FILE 57/70 — Redis Translation Cache

Translation results cache করো।
API calls কমাও, performance বাড়াও।
"""
import logging
import json
import hashlib
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

CACHE_TTL      = 86400 * 7   # 7 days
MAX_TEXT_LENGTH= 2000


class TranslationCache:
    """Translation cache manager"""

    def get(self, text: str, target_lang: str, source_lang: str = 'auto') -> dict | None:
        key    = self._make_key(text, target_lang, source_lang)
        cached = cache.get(key)
        if cached:
            logger.debug(f'Translation cache HIT: {target_lang}')
            return json.loads(cached)
        return None

    def set(self, text: str, target_lang: str, result: dict, source_lang: str = 'auto') -> None:
        key = self._make_key(text, target_lang, source_lang)
        cache.set(key, json.dumps(result, ensure_ascii=False), timeout=CACHE_TTL)

    def invalidate(self, text: str, target_lang: str, source_lang: str = 'auto') -> None:
        key = self._make_key(text, target_lang, source_lang)
        cache.delete(key)

    def get_or_translate(self, text: str, target_lang: str, source_lang: str = 'auto') -> dict:
        cached = self.get(text, target_lang, source_lang)
        if cached:
            return cached
        from api.support.multilang.auto_translator import auto_translator
        result = auto_translator.translate(text, target_lang, source_lang)
        if result.get('provider') != 'none':
            self.set(text, target_lang, result, source_lang)
        return result

    def get_stats(self) -> dict:
        return {
            'ttl_days':        CACHE_TTL // 86400,
            'max_text_length': MAX_TEXT_LENGTH,
        }

    def _make_key(self, text: str, target_lang: str, source_lang: str) -> str:
        text_hash = hashlib.md5(text[:MAX_TEXT_LENGTH].encode('utf-8')).hexdigest()
        return f'translation:{text_hash}:{source_lang}:{target_lang}'


translation_cache = TranslationCache()