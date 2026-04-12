# services/providers/BaseProvider.py
"""Abstract base class for all translation providers"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class BaseTranslationProvider(ABC):
    """All translation providers must extend this"""

    provider_name = 'base'
    supports_auto_detect = False
    supports_bulk = False
    max_chars_per_request = 5000
    max_requests_per_minute = 60

    def __init__(self, api_key: str = '', config: dict = None):
        self.api_key = api_key
        self.config = config or {}
        self._request_count = 0

    @abstractmethod
    def translate(self, text: str, source_lang: str, target_lang: str) -> Dict:
        """Single text translate করে — subclass implement করবে"""
        pass

    @abstractmethod
    def get_supported_languages(self) -> List[str]:
        """Supported language codes return করে"""
        pass

    @abstractmethod
    def health_check(self) -> bool:
        """Provider alive কিনা check করে"""
        pass

    def bulk_translate(self, texts: List[str], source_lang: str, target_lang: str) -> List[Dict]:
        """Default: translate one by one"""
        return [self.translate(t, source_lang, target_lang) for t in texts]

    def _log_request(self, text_len: int, success: bool, response_time_ms: int = None):
        self._request_count += 1
        status = 'OK' if success else 'FAIL'
        logger.info(f"[{self.provider_name}] {status} len={text_len} total_requests={self._request_count}")

    def format_result(self, translated_text: str, source_lang: str, target_lang: str,
                      confidence: float = None) -> Dict:
        return {
            'translated': translated_text,
            'source_lang': source_lang,
            'target_lang': target_lang,
            'provider': self.provider_name,
            'confidence': confidence,
        }
