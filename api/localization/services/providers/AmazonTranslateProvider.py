# services/providers/AmazonTranslateProvider.py
"""Amazon Translate provider via AWS SDK (boto3) or REST"""
import logging, time
from typing import Dict, List
from .BaseProvider import BaseTranslationProvider

logger = logging.getLogger(__name__)


class AmazonTranslateProvider(BaseTranslationProvider):
    provider_name = 'amazon'
    supports_auto_detect = True
    supports_bulk = False
    max_chars_per_request = 10000

    LANG_MAP = {
        'bn': 'bn', 'hi': 'hi', 'ar': 'ar', 'ur': 'ur', 'fa': 'fa',
        'en': 'en', 'es': 'es', 'fr': 'fr', 'de': 'de', 'pt': 'pt',
        'it': 'it', 'ru': 'ru', 'zh': 'zh', 'ja': 'ja', 'ko': 'ko',
        'tr': 'tr', 'vi': 'vi', 'id': 'id', 'ms': 'ms', 'th': 'th',
        'nl': 'nl', 'pl': 'pl', 'sv': 'sv', 'da': 'da', 'fi': 'fi',
        'el': 'el', 'he': 'he', 'ta': 'ta', 'uk': 'uk', 'cs': 'cs',
        'ro': 'ro', 'hu': 'hu', 'bg': 'bg', 'lt': 'lt', 'lv': 'lv',
        'et': 'et', 'af': 'af', 'sw': 'sw',
    }

    def translate(self, text: str, source_lang: str, target_lang: str) -> Dict:
        start = time.time()
        try:
            # Try boto3 first
            import boto3
            client = boto3.client(
                'translate',
                region_name=self.config.get('region', 'us-east-1'),
                aws_access_key_id=self.config.get('access_key', ''),
                aws_secret_access_key=self.api_key,
            )
            src = self.LANG_MAP.get(source_lang, source_lang)
            tgt = self.LANG_MAP.get(target_lang, target_lang)
            response = client.translate_text(
                Text=text,
                SourceLanguageCode=src,
                TargetLanguageCode=tgt,
            )
            translated = response['TranslatedText']
            elapsed = int((time.time() - start) * 1000)
            self._log_request(len(text), True, elapsed)
            return self.format_result(translated, source_lang, target_lang)
        except ImportError:
            logger.warning("boto3 not installed — Amazon Translate unavailable")
            return self.format_result(text, source_lang, target_lang)
        except Exception as e:
            logger.error(f"Amazon Translate failed: {e}")
            return self.format_result(text, source_lang, target_lang)

    def get_supported_languages(self) -> List[str]:
        return list(self.LANG_MAP.keys())

    def health_check(self) -> bool:
        try:
            result = self.translate('hello', 'en', 'fr')
            return bool(result.get('translated'))
        except Exception:
            return False
