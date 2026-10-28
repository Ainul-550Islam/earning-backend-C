"""
api/support/multilang/auto_translator.py
FILE 56/70 — Auto Translation System

Bengali/Hindi ticket → English-এ translate করো।
Agent সহজে বুঝতে পারবে।
English reply → User-এর language-এ translate করো।

Providers:
1. Google Translate API (recommended)
2. DeepL API (high quality)
3. LibreTranslate (self-hosted, free)
4. Claude API (best quality, contextual)

Settings:
    TRANSLATOR_PROVIDER  = 'google'  # or 'deepl', 'libretranslate', 'claude'
    GOOGLE_TRANSLATE_KEY = 'your_key'
    DEEPL_API_KEY        = 'your_key'
    LIBRETRANSLATE_URL   = 'http://localhost:5000'
"""
import logging
import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

PROVIDER   = getattr(settings, 'TRANSLATOR_PROVIDER',  'claude')
GOOGLE_KEY = getattr(settings, 'GOOGLE_TRANSLATE_KEY', '')
DEEPL_KEY  = getattr(settings, 'DEEPL_API_KEY',        '')
LIBRE_URL  = getattr(settings, 'LIBRETRANSLATE_URL',   '')
CLAUDE_KEY = getattr(settings, 'ANTHROPIC_API_KEY',    '')


class AutoTranslator:
    """
    Multi-provider auto translation।
    Cache-based to minimize API calls।
    """

    CACHE_TTL = 86400  # 24 hours

    # ──────────────────────────────────────────
    # MAIN TRANSLATE
    # ──────────────────────────────────────────
    def translate(self, text: str, target_lang: str = 'en', source_lang: str = 'auto') -> dict:
        """
        Text translate করো।
        Returns: {translated, source_lang, target_lang, provider}
        """
        if not text or len(text.strip()) < 2:
            return {'translated': text, 'source_lang': source_lang, 'target_lang': target_lang}

        # Same language → skip
        if source_lang == target_lang and source_lang != 'auto':
            return {'translated': text, 'source_lang': source_lang, 'target_lang': target_lang}

        # Cache check
        cache_key = f'translate:{hash(text[:100])}:{target_lang}'
        cached    = cache.get(cache_key)
        if cached:
            return cached

        # Auto detect source
        if source_lang == 'auto':
            from api.support.multilang.language_detector import language_detector
            detected  = language_detector.detect(text)
            source_lang = detected['language']

        # Same as target → skip
        if source_lang == target_lang:
            result = {'translated': text, 'source_lang': source_lang, 'target_lang': target_lang, 'provider': 'none'}
            return result

        # Translate
        result = None
        if PROVIDER == 'google' and GOOGLE_KEY:
            result = self._google_translate(text, target_lang, source_lang)
        elif PROVIDER == 'deepl' and DEEPL_KEY:
            result = self._deepl_translate(text, target_lang, source_lang)
        elif PROVIDER == 'libretranslate' and LIBRE_URL:
            result = self._libre_translate(text, target_lang, source_lang)
        elif PROVIDER == 'claude' and CLAUDE_KEY:
            result = self._claude_translate(text, target_lang, source_lang)

        if not result:
            logger.warning(f'Translation skipped: no provider configured or translation failed.')
            result = {'translated': text, 'source_lang': source_lang, 'target_lang': target_lang, 'provider': 'none'}

        cache.set(cache_key, result, timeout=self.CACHE_TTL)
        return result

    def translate_to_english(self, text: str) -> str:
        """Quick helper: any language → English"""
        result = self.translate(text, 'en')
        return result.get('translated', text)

    def translate_from_english(self, text: str, target_lang: str) -> str:
        """Quick helper: English → target language"""
        if target_lang == 'en':
            return text
        result = self.translate(text, target_lang, 'en')
        return result.get('translated', text)

    def translate_ticket(self, ticket) -> dict:
        """Ticket subject + description translate করো"""
        from api.support.multilang.language_detector import language_detector
        text    = f"{ticket.subject} {ticket.description}"
        lang    = language_detector.detect(text)['language']

        if lang == 'en':
            return {'language': 'en', 'translated': False}

        translated_subject = self.translate(ticket.subject, 'en', lang).get('translated', ticket.subject)
        translated_desc    = self.translate(ticket.description, 'en', lang).get('translated', ticket.description)

        # Save to ticket
        try:
            ticket.ai_category = ticket.ai_category  # Keep existing
            ticket.save()

            # Save translation as internal note
            from api.support.models import TicketMessage
            from django.contrib.auth import get_user_model
            User   = get_user_model()
            system = User.objects.filter(is_superuser=True).first()
            if system and translated_desc != ticket.description:
                TicketMessage.objects.create(
                    ticket      = ticket,
                    sender      = system,
                    content     = f'🌐 [Auto Translation — {lang.upper()} → EN]\n\nSubject: {translated_subject}\n\n{translated_desc}',
                    is_agent    = True,
                    is_internal = True,
                )
        except Exception as e:
            logger.warning(f'Save translation failed: {e}')

        return {
            'language':            lang,
            'translated_subject':  translated_subject,
            'translated_desc':     translated_desc[:500],
            'translated':          True,
        }

    # ──────────────────────────────────────────
    # PROVIDERS
    # ──────────────────────────────────────────
    def _google_translate(self, text: str, target: str, source: str) -> dict | None:
        try:
            url  = 'https://translation.googleapis.com/language/translate/v2'
            resp = requests.post(url, params={
                'key': GOOGLE_KEY,
            }, json={
                'q':      text[:5000],
                'target': target,
                'source': source if source != 'auto' else None,
                'format': 'text',
            }, timeout=10)

            if resp.status_code == 200:
                data = resp.json()
                translated = data['data']['translations'][0]['translatedText']
                detected   = data['data']['translations'][0].get('detectedSourceLanguage', source)
                return {'translated': translated, 'source_lang': detected, 'target_lang': target, 'provider': 'google'}
        except Exception as e:
            logger.error(f'Google Translate failed: {e}')
        return None

    def _deepl_translate(self, text: str, target: str, source: str) -> dict | None:
        try:
            lang_map = {'en': 'EN', 'bn': 'BN', 'hi': 'HI', 'ar': 'AR', 'de': 'DE', 'fr': 'FR', 'es': 'ES'}
            resp     = requests.post(
                'https://api-free.deepl.com/v2/translate',
                headers = {'Authorization': f'DeepL-Auth-Key {DEEPL_KEY}'},
                data    = {
                    'text':        text[:5000],
                    'target_lang': lang_map.get(target, target.upper()),
                    'source_lang': lang_map.get(source, source.upper()) if source != 'auto' else None,
                },
                timeout=10,
            )
            if resp.status_code == 200:
                translation = resp.json()['translations'][0]
                return {'translated': translation['text'], 'source_lang': source, 'target_lang': target, 'provider': 'deepl'}
        except Exception as e:
            logger.error(f'DeepL failed: {e}')
        return None

    def _libre_translate(self, text: str, target: str, source: str) -> dict | None:
        try:
            resp = requests.post(f'{LIBRE_URL}/translate', json={
                'q': text[:5000], 'source': source if source != 'auto' else 'auto', 'target': target
            }, timeout=10)
            if resp.status_code == 200:
                translated = resp.json().get('translatedText', text)
                return {'translated': translated, 'source_lang': source, 'target_lang': target, 'provider': 'libretranslate'}
        except Exception as e:
            logger.error(f'LibreTranslate failed: {e}')
        return None

    def _claude_translate(self, text: str, target: str, source: str) -> dict | None:
        """Claude API দিয়ে high-quality contextual translation"""
        try:
            lang_names = {'en': 'English', 'bn': 'Bengali', 'hi': 'Hindi', 'ar': 'Arabic', 'fr': 'French', 'de': 'German', 'es': 'Spanish'}
            target_name= lang_names.get(target, target)

            resp = requests.post(
                'https://api.anthropic.com/v1/messages',
                headers = {
                    'x-api-key':         CLAUDE_KEY,
                    'anthropic-version': '2023-06-01',
                    'content-type':      'application/json',
                },
                json = {
                    'model':      'claude-haiku-4-5-20251001',
                    'max_tokens': 500,
                    'system':     f'You are a translator. Translate to {target_name}. Return ONLY the translation, nothing else. Keep technical terms, ticket IDs, and proper nouns unchanged.',
                    'messages':   [{'role': 'user', 'content': text[:2000]}],
                },
                timeout=15,
            )

            if resp.status_code == 200:
                translated = resp.json()['content'][0]['text'].strip()
                return {'translated': translated, 'source_lang': source, 'target_lang': target, 'provider': 'claude'}
        except Exception as e:
            logger.error(f'Claude translate failed: {e}')
        return None


auto_translator = AutoTranslator()