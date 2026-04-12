"""
api/ai_engine/NLP_ENGINES/translation_engine.py
================================================
Translation Engine — multi-language translation।
English ↔ Bengali, + 100+ languages।
Offer descriptions, UI, support — সব translate।
"""
import logging
from typing import List, Dict, Optional
logger = logging.getLogger(__name__)

class TranslationEngine:
    """Multi-language translation engine।"""

    SUPPORTED_LANGUAGES = {
        'en': 'English', 'bn': 'Bengali', 'hi': 'Hindi', 'ar': 'Arabic',
        'fr': 'French',  'de': 'German',  'es': 'Spanish', 'zh': 'Chinese',
        'ja': 'Japanese','ko': 'Korean',  'pt': 'Portuguese', 'ru': 'Russian',
        'tr': 'Turkish', 'id': 'Indonesian', 'ur': 'Urdu',
    }

    def __init__(self, provider: str = 'auto'):
        self.provider = provider

    def translate(self, text: str, target_lang: str,
                  source_lang: str = 'auto') -> dict:
        """Text translate করো।"""
        if not text or not text.strip():
            return {'translated': '', 'source_lang': source_lang, 'target_lang': target_lang}

        # Try providers in order
        for method in [self._openai_translate, self._google_translate, self._fallback]:
            try:
                result = method(text, target_lang, source_lang)
                if result.get('translated'):
                    return result
            except Exception as e:
                logger.debug(f"Translation provider failed: {e}")
                continue

        return {'translated': text, 'source_lang': source_lang,
                'target_lang': target_lang, 'error': 'All providers failed'}

    def _openai_translate(self, text: str, target: str, source: str) -> dict:
        """OpenAI GPT-4 translation।"""
        from ..INTEGRATIONS.openai_integration import OpenAIIntegration
        client  = OpenAIIntegration()
        lang_name = self.SUPPORTED_LANGUAGES.get(target, target)
        prompt  = f"Translate the following text to {lang_name}. Return only the translation, nothing else:\n\n{text}"
        result  = client.complete(prompt, max_tokens=500)
        translated = result.get('content', '').strip()
        return {'translated': translated, 'source_lang': source,
                'target_lang': target, 'provider': 'openai'}

    def _google_translate(self, text: str, target: str, source: str) -> dict:
        """Google Cloud Translation API।"""
        try:
            from google.cloud import translate_v2 as translate
            client = translate.Client()
            result = client.translate(text, target_language=target,
                                       source_language=None if source == 'auto' else source)
            return {
                'translated':   result['translatedText'],
                'source_lang':  result.get('detectedSourceLanguage', source),
                'target_lang':  target,
                'provider':     'google',
            }
        except ImportError:
            raise Exception("google-cloud-translate not installed")

    def _fallback(self, text: str, target: str, source: str) -> dict:
        """LibreTranslate fallback।"""
        import requests
        resp = requests.post(
            'https://libretranslate.de/translate',
            json={'q': text, 'source': source if source != 'auto' else 'en',
                  'target': target, 'format': 'text'},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            'translated':  data.get('translatedText', text),
            'source_lang': source,
            'target_lang': target,
            'provider':    'libretranslate',
        }

    def batch_translate(self, texts: List[str], target_lang: str,
                         source_lang: str = 'auto') -> List[Dict]:
        """Multiple texts translate করো।"""
        return [self.translate(t, target_lang, source_lang) for t in texts]

    def detect_language(self, text: str) -> dict:
        """Language detect করো।"""
        from ..NLP_ENGINES.language_detector import LanguageDetector
        return LanguageDetector().detect(text)

    def translate_offer(self, offer_data: dict, target_lang: str) -> dict:
        """Offer data সম্পূর্ণ translate করো।"""
        fields = ['title', 'description', 'instructions']
        translated = dict(offer_data)
        for field in fields:
            val = offer_data.get(field, '')
            if val:
                result = self.translate(val, target_lang)
                translated[f"{field}_{target_lang}"] = result.get('translated', val)
        return translated

    def get_supported_languages(self) -> Dict[str, str]:
        """Supported languages list।"""
        return self.SUPPORTED_LANGUAGES
