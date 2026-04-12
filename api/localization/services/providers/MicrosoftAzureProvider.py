# services/providers/MicrosoftAzureProvider.py
"""Microsoft Azure Cognitive Services Translator provider"""
import logging, time, uuid
from typing import Dict, List
from .BaseProvider import BaseTranslationProvider

logger = logging.getLogger(__name__)


class MicrosoftAzureProvider(BaseTranslationProvider):
    provider_name = 'azure'
    supports_auto_detect = True
    supports_bulk = True
    max_chars_per_request = 50000
    BASE_URL = 'https://api.cognitive.microsofttranslator.com/translate'

    LANG_MAP = {
        'bn': 'bn', 'hi': 'hi', 'ar': 'ar', 'ur': 'ur', 'fa': 'fa',
        'en': 'en', 'es': 'es', 'fr': 'fr', 'de': 'de', 'pt': 'pt',
        'it': 'it', 'ru': 'ru', 'zh': 'zh-Hans', 'ja': 'ja', 'ko': 'ko',
        'tr': 'tr', 'vi': 'vi', 'id': 'id', 'ms': 'ms', 'th': 'th',
        'nl': 'nl', 'pl': 'pl', 'sv': 'sv', 'da': 'da', 'no': 'no',
        'fi': 'fi', 'el': 'el', 'he': 'he', 'ta': 'ta', 'te': 'te',
        'ml': 'ml', 'ne': 'ne', 'si': 'si', 'my': 'my', 'km': 'km',
        'uk': 'uk', 'cs': 'cs', 'sk': 'sk', 'ro': 'ro', 'hu': 'hu',
        'bg': 'bg', 'hr': 'hr', 'sr': 'sr-Cyrl', 'lt': 'lt', 'lv': 'lv',
        'et': 'et', 'af': 'af', 'sw': 'sw', 'am': 'am',
    }

    def translate(self, text: str, source_lang: str, target_lang: str) -> Dict:
        start = time.time()
        try:
            import urllib.request, json
            if not self.api_key:
                return self.format_result(text, source_lang, target_lang)
            region = self.config.get('region', 'eastus')
            tgt = self.LANG_MAP.get(target_lang, target_lang)
            src = self.LANG_MAP.get(source_lang, source_lang)
            url = f"{self.BASE_URL}?api-version=3.0&from={src}&to={tgt}"
            payload = json.dumps([{"Text": text}]).encode('utf-8')
            req = urllib.request.Request(url, data=payload, headers={
                'Ocp-Apim-Subscription-Key': self.api_key,
                'Ocp-Apim-Subscription-Region': region,
                'Content-Type': 'application/json',
                'X-ClientTraceId': str(uuid.uuid4()),
            }, method='POST')
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read().decode())
            translated = result[0]['translations'][0]['text']
            elapsed = int((time.time() - start) * 1000)
            self._log_request(len(text), True, elapsed)
            return self.format_result(translated, source_lang, target_lang)
        except Exception as e:
            logger.error(f"Azure Translate failed: {e}")
            return self.format_result(text, source_lang, target_lang)

    def bulk_translate(self, texts: List[str], source_lang: str, target_lang: str) -> List[Dict]:
        """Azure supports bulk in single request"""
        try:
            import urllib.request, json, uuid
            if not self.api_key:
                return [self.format_result(t, source_lang, target_lang) for t in texts]
            region = self.config.get('region', 'eastus')
            tgt = self.LANG_MAP.get(target_lang, target_lang)
            src = self.LANG_MAP.get(source_lang, source_lang)
            url = f"{self.BASE_URL}?api-version=3.0&from={src}&to={tgt}"
            payload = json.dumps([{"Text": t} for t in texts]).encode('utf-8')
            req = urllib.request.Request(url, data=payload, headers={
                'Ocp-Apim-Subscription-Key': self.api_key,
                'Ocp-Apim-Subscription-Region': region,
                'Content-Type': 'application/json',
                'X-ClientTraceId': str(uuid.uuid4()),
            }, method='POST')
            with urllib.request.urlopen(req, timeout=15) as resp:
                results = json.loads(resp.read().decode())
            return [
                self.format_result(r['translations'][0]['text'], source_lang, target_lang)
                for r in results
            ]
        except Exception as e:
            logger.error(f"Azure bulk translate failed: {e}")
            return [self.format_result(t, source_lang, target_lang) for t in texts]

    def get_supported_languages(self) -> List[str]:
        return list(self.LANG_MAP.keys())

    def health_check(self) -> bool:
        try:
            result = self.translate('hello', 'en', 'fr')
            return bool(result.get('translated'))
        except Exception:
            return False
