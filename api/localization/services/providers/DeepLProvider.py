# services/providers/DeepLProvider.py
"""DeepL Translation API — glossary push, formality levels, document translation"""
import logging
import time
import json
import urllib.request
import urllib.parse
from typing import Dict, List, Optional
from .BaseProvider import BaseTranslationProvider

logger = logging.getLogger(__name__)


class DeepLProvider(BaseTranslationProvider):
    provider_name = 'deepl'
    supports_auto_detect = True
    supports_bulk = True
    max_chars_per_request = 131072  # DeepL's actual limit
    max_requests_per_minute = 60

    # DeepL uses uppercase codes with regional variants
    LANG_MAP_SRC = {
        'en': 'EN', 'de': 'DE', 'fr': 'FR', 'es': 'ES', 'pt': 'PT',
        'it': 'IT', 'nl': 'NL', 'pl': 'PL', 'ru': 'RU', 'ja': 'JA',
        'zh': 'ZH', 'bg': 'BG', 'cs': 'CS', 'da': 'DA', 'el': 'EL',
        'et': 'ET', 'fi': 'FI', 'hu': 'HU', 'id': 'ID', 'ko': 'KO',
        'lt': 'LT', 'lv': 'LV', 'nb': 'NB', 'ro': 'RO', 'sk': 'SK',
        'sl': 'SL', 'sv': 'SV', 'tr': 'TR', 'uk': 'UK',
    }
    LANG_MAP_TGT = {
        **LANG_MAP_SRC,
        'en': 'EN-US',   # DeepL target needs EN-US or EN-GB
        'pt': 'PT-BR',   # Default to Brazilian
    }
    FORMALITY_LANGS = {'de', 'fr', 'it', 'es', 'nl', 'pl', 'pt', 'ru', 'ja'}

    def __init__(self, api_key: str = '', config: dict = None):
        super().__init__(api_key, config)
        # Free API uses api-free.deepl.com, Pro uses api.deepl.com
        is_free = api_key.endswith(':fx') if api_key else True
        self._base_url = (
            'https://api-free.deepl.com/v2/translate' if is_free
            else 'https://api.deepl.com/v2/translate'
        )

    def translate(self, text: str, source_lang: str, target_lang: str,
                  formality: str = 'default') -> Dict:
        start = time.time()
        try:
            if not self.api_key:
                return self.format_result(text, source_lang, target_lang)

            src = self.LANG_MAP_SRC.get(source_lang)
            tgt = self.LANG_MAP_TGT.get(target_lang)

            if not src or not tgt:
                # Language not supported by DeepL
                return self.format_result(text, source_lang, target_lang)

            payload = {
                'auth_key': self.api_key,
                'text': text,
                'source_lang': src,
                'target_lang': tgt,
                'tag_handling': 'xml',  # Preserve XML/HTML tags
                'outline_detection': '0',
                'preserve_formatting': '1',
            }

            # Formality for supported languages
            if target_lang in self.FORMALITY_LANGS and formality != 'default':
                payload['formality'] = formality  # 'more' | 'less' | 'prefer_more' | 'prefer_less'

            # Glossary ID if configured
            glossary_id = self.config.get(f'glossary_{source_lang}_{target_lang}')
            if glossary_id:
                payload['glossary_id'] = glossary_id

            data = urllib.parse.urlencode(payload).encode('utf-8')
            req = urllib.request.Request(
                self._base_url, data=data, method='POST',
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )

            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read().decode('utf-8'))

            translated = result['translations'][0]['text']
            detected_src = result['translations'][0].get('detected_source_language', src)
            elapsed = int((time.time() - start) * 1000)
            self._log_request(len(text), True, elapsed)

            r = self.format_result(translated, source_lang, target_lang)
            r['detected_source'] = detected_src.lower()
            return r

        except urllib.error.HTTPError as e:
            body = e.read().decode('utf-8', errors='ignore')
            logger.error(f"DeepL HTTP {e.code}: {body[:200]}")
            self._log_request(len(text), False)
            return self.format_result(text, source_lang, target_lang)
        except Exception as e:
            logger.error(f"DeepL error: {e}")
            self._log_request(len(text), False)
            return self.format_result(text, source_lang, target_lang)

    def bulk_translate(self, texts: List[str], source_lang: str, target_lang: str) -> List[Dict]:
        """DeepL supports multiple text params in one request"""
        if not self.api_key or not texts:
            return [self.format_result(t, source_lang, target_lang) for t in texts]
        try:
            src = self.LANG_MAP_SRC.get(source_lang)
            tgt = self.LANG_MAP_TGT.get(target_lang)
            if not src or not tgt:
                return [self.format_result(t, source_lang, target_lang) for t in texts]

            # Build multi-text payload
            params = [('auth_key', self.api_key), ('source_lang', src), ('target_lang', tgt)]
            for t in texts[:50]:  # DeepL batch limit
                params.append(('text', t))

            data = urllib.parse.urlencode(params).encode('utf-8')
            req = urllib.request.Request(
                self._base_url, data=data, method='POST',
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode('utf-8'))

            return [
                self.format_result(t['text'], source_lang, target_lang)
                for t in result['translations']
            ]
        except Exception as e:
            logger.error(f"DeepL bulk failed: {e}")
            return [self.translate(t, source_lang, target_lang) for t in texts]

    def push_glossary(self, name: str, source_lang: str, target_lang: str,
                      entries: Dict[str, str]) -> Optional[str]:
        """Glossary terms DeepL-এ push করে — consistent brand translations"""
        try:
            if not self.api_key:
                return None
            src = self.LANG_MAP_SRC.get(source_lang, source_lang.upper())
            tgt = self.LANG_MAP_SRC.get(target_lang, target_lang.upper())
            is_free = self.api_key.endswith(':fx')
            base = 'https://api-free.deepl.com' if is_free else 'https://api.deepl.com'

            # Build TSV entries
            tsv = '\n'.join(f"{k}\t{v}" for k, v in entries.items())
            payload = {
                'auth_key': self.api_key,
                'name': name,
                'source_lang': src,
                'target_lang': tgt,
                'entries_format': 'tsv',
                'entries': tsv,
            }
            data = urllib.parse.urlencode(payload).encode('utf-8')
            req = urllib.request.Request(
                f'{base}/v2/glossaries', data=data, method='POST',
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read().decode('utf-8'))
            glossary_id = result.get('glossary_id')
            logger.info(f"DeepL glossary created: {glossary_id}")
            return glossary_id
        except Exception as e:
            logger.error(f"DeepL push_glossary failed: {e}")
            return None

    def get_usage(self) -> Dict:
        """API usage statistics"""
        try:
            if not self.api_key:
                return {}
            is_free = self.api_key.endswith(':fx')
            base = 'https://api-free.deepl.com' if is_free else 'https://api.deepl.com'
            req = urllib.request.Request(
                f'{base}/v2/usage',
                headers={'Authorization': f'DeepL-Auth-Key {self.api_key}'}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except Exception:
            return {}

    def get_supported_languages(self) -> List[str]:
        return list(self.LANG_MAP_SRC.keys())

    def health_check(self) -> bool:
        try:
            if not self.api_key:
                return False
            usage = self.get_usage()
            return 'character_count' in usage
        except Exception:
            return False
