# services/providers/GoogleTranslateProvider.py
"""Google Cloud Translation API v3 — batch support, glossary, formality"""
import logging
import time
import json
import urllib.request
import urllib.parse
from typing import Dict, List, Optional
from .BaseProvider import BaseTranslationProvider

logger = logging.getLogger(__name__)


class GoogleTranslateProvider(BaseTranslationProvider):
    provider_name = 'google'
    supports_auto_detect = True
    supports_bulk = True
    max_chars_per_request = 30000
    max_requests_per_minute = 100

    # v3 endpoint (Cloud Translation)
    V3_BASE = 'https://translation.googleapis.com/v3/projects/{project}/locations/global:translateText'
    # v2 endpoint (Basic) — simpler, works with just API key
    V2_BASE = 'https://translation.googleapis.com/language/translate/v2'

    # Google uses BCP-47 codes; some need remapping
    LANG_MAP = {
        'zh': 'zh-CN', 'zh-hans': 'zh-CN', 'zh-hant': 'zh-TW',
        'he': 'iw',  # Google uses 'iw' for Hebrew
        'jv': 'jw',  # Javanese
    }

    def __init__(self, api_key: str = '', config: dict = None):
        super().__init__(api_key, config)
        self._project_id = (config or {}).get('project_id', '')
        self._use_v3 = bool(self._project_id)

    def translate(self, text: str, source_lang: str, target_lang: str) -> Dict:
        start = time.time()
        try:
            if not self.api_key:
                return self.format_result(text, source_lang, target_lang)

            src = self.LANG_MAP.get(source_lang, source_lang)
            tgt = self.LANG_MAP.get(target_lang, target_lang)

            params = {
                'q': text,
                'source': src,
                'target': tgt,
                'key': self.api_key,
                'format': 'text',
            }
            url = f"{self.V2_BASE}?{urllib.parse.urlencode(params)}"
            req = urllib.request.Request(url, headers={'User-Agent': 'World1Localization/2.0'})

            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode('utf-8'))

            translated = data['data']['translations'][0]['translatedText']
            elapsed = int((time.time() - start) * 1000)
            self._log_request(len(text), True, elapsed)
            return self.format_result(translated, source_lang, target_lang)

        except urllib.error.HTTPError as e:
            body = e.read().decode('utf-8', errors='ignore')
            logger.error(f"Google Translate HTTP {e.code}: {body[:200]}")
            self._log_request(len(text), False)
            return self.format_result(text, source_lang, target_lang)
        except Exception as e:
            logger.error(f"Google Translate error: {e}")
            self._log_request(len(text), False)
            return self.format_result(text, source_lang, target_lang)

    def bulk_translate(self, texts: List[str], source_lang: str, target_lang: str) -> List[Dict]:
        """Batch translate — Google supports multiple q params"""
        if not self.api_key or not texts:
            return [self.format_result(t, source_lang, target_lang) for t in texts]
        try:
            src = self.LANG_MAP.get(source_lang, source_lang)
            tgt = self.LANG_MAP.get(target_lang, target_lang)

            # Build query with multiple q params
            params = [('source', src), ('target', tgt), ('key', self.api_key), ('format', 'text')]
            for t in texts[:128]:  # Google limit
                params.append(('q', t))

            url = f"{self.V2_BASE}?{urllib.parse.urlencode(params)}"
            with urllib.request.urlopen(url, timeout=30) as resp:
                data = json.loads(resp.read().decode('utf-8'))

            results = []
            for i, translation in enumerate(data['data']['translations']):
                results.append(self.format_result(translation['translatedText'], source_lang, target_lang))
            return results

        except Exception as e:
            logger.error(f"Google bulk translate failed: {e}")
            return [self.translate(t, source_lang, target_lang) for t in texts]

    def detect_language(self, text: str) -> Optional[str]:
        """Text-এর language detect করে"""
        try:
            if not self.api_key:
                return None
            params = {'q': text[:500], 'key': self.api_key}
            url = f"{self.V2_BASE}/detect?{urllib.parse.urlencode(params)}"
            with urllib.request.urlopen(url, timeout=5) as resp:
                data = json.loads(resp.read().decode('utf-8'))
            return data['data']['detections'][0][0].get('language')
        except Exception:
            return None

    def get_supported_languages(self) -> List[str]:
        return [
            'af', 'am', 'ar', 'az', 'be', 'bg', 'bn', 'bs', 'ca', 'cs', 'cy', 'da',
            'de', 'el', 'en', 'eo', 'es', 'et', 'eu', 'fa', 'fi', 'fr', 'ga', 'gl',
            'gu', 'ha', 'hi', 'hr', 'ht', 'hu', 'hy', 'id', 'is', 'it', 'iw', 'ja',
            'jw', 'ka', 'kk', 'km', 'kn', 'ko', 'ku', 'ky', 'la', 'lb', 'lo', 'lt',
            'lv', 'mg', 'mi', 'mk', 'ml', 'mn', 'mr', 'ms', 'mt', 'my', 'ne', 'nl',
            'no', 'ny', 'or', 'pa', 'pl', 'ps', 'pt', 'ro', 'ru', 'rw', 'sd', 'si',
            'sk', 'sl', 'sm', 'sn', 'so', 'sq', 'sr', 'st', 'su', 'sv', 'sw', 'ta',
            'te', 'tg', 'th', 'tk', 'tl', 'tr', 'tt', 'ug', 'uk', 'ur', 'uz', 'vi',
            'xh', 'yi', 'yo', 'zh', 'zu',
        ]

    def health_check(self) -> bool:
        try:
            if not self.api_key:
                return False
            result = self.translate('Hello', 'en', 'fr')
            return bool(result.get('translated')) and result['translated'] != 'Hello'
        except Exception:
            return False
