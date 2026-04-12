# services/providers/OpenAIProvider.py
"""OpenAI GPT translation — nuanced, context-aware, rare languages"""
import logging
import time
import json
import urllib.request
from typing import Dict, List
from .BaseProvider import BaseTranslationProvider

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseTranslationProvider):
    provider_name = 'openai'
    supports_auto_detect = True
    supports_bulk = False
    max_chars_per_request = 4000
    max_requests_per_minute = 20

    BASE_URL = 'https://api.openai.com/v1/chat/completions'
    DEFAULT_MODEL = 'gpt-4o-mini'  # Fast, cheap, good quality

    # CPAlead domain-specific system prompts
    DOMAIN_PROMPTS = {
        'finance':    'You specialize in financial translation. Use precise monetary terminology.',
        'marketing':  'You specialize in marketing copy. Keep it engaging and culturally appropriate.',
        'legal':      'You specialize in legal translation. Be precise and formal.',
        'offer':      'You translate earning/reward platform content. Keep it clear and motivating.',
        'ui':         'You translate UI/UX copy. Keep strings short and action-oriented.',
        'default':    'Translate naturally, preserving tone and formatting.',
    }

    # Languages where GPT outperforms DeepL/Google
    SPECIALTY_LANGS = {
        'si', 'ne', 'am', 'my', 'km', 'lo', 'mn', 'ky', 'tk', 'uz',
        'tg', 'ka', 'hy', 'az', 'ur', 'ps', 'sd', 'ku', 'ckb',
    }

    def __init__(self, api_key: str = '', config: dict = None):
        super().__init__(api_key, config)
        self._model = (config or {}).get('model', self.DEFAULT_MODEL)
        self._temperature = (config or {}).get('temperature', 0.2)

    def translate(self, text: str, source_lang: str, target_lang: str,
                  context: str = '', domain: str = 'default',
                  formality: str = 'neutral') -> Dict:
        start = time.time()
        try:
            if not self.api_key:
                return self.format_result(text, source_lang, target_lang)

            domain_instruction = self.DOMAIN_PROMPTS.get(domain, self.DOMAIN_PROMPTS['default'])
            formality_note = {
                'formal': 'Use formal language.',
                'informal': 'Use informal, friendly language.',
                'neutral': '',
            }.get(formality, '')

            system_prompt = f"""You are an expert professional translator.
Translate from {source_lang} to {target_lang}.
{domain_instruction}
{formality_note}
Rules:
- Return ONLY the translation, nothing else
- Preserve all placeholders: {{variable}}, %s, {{{{variable}}}}
- Preserve HTML tags: <b>, <a>, etc.
- Preserve ICU message format: {{count, plural, one{{}} other{{}}}}
- Maintain the same tone and register as the source
- Do not add explanations or notes"""

            if context:
                system_prompt += f"\nContext: {context}"

            payload = {
                'model': self._model,
                'messages': [
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': text},
                ],
                'temperature': self._temperature,
                'max_tokens': min(int(len(text) * 4) + 100, 2000),
            }

            req = urllib.request.Request(
                self.BASE_URL,
                data=json.dumps(payload).encode('utf-8'),
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {self.api_key}',
                },
                method='POST'
            )

            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode('utf-8'))

            translated = result['choices'][0]['message']['content'].strip()
            # Strip quotes if GPT added them
            if translated.startswith('"') and translated.endswith('"'):
                translated = translated[1:-1]

            elapsed = int((time.time() - start) * 1000)
            self._log_request(len(text), True, elapsed)

            r = self.format_result(translated, source_lang, target_lang, confidence=0.92)
            r['model'] = self._model
            r['tokens_used'] = result.get('usage', {}).get('total_tokens', 0)
            return r

        except urllib.error.HTTPError as e:
            body = e.read().decode('utf-8', errors='ignore')
            if e.code == 429:
                logger.warning("OpenAI rate limited")
            else:
                logger.error(f"OpenAI HTTP {e.code}: {body[:200]}")
            self._log_request(len(text), False)
            return self.format_result(text, source_lang, target_lang)
        except Exception as e:
            logger.error(f"OpenAI error: {e}")
            self._log_request(len(text), False)
            return self.format_result(text, source_lang, target_lang)

    def translate_batch_with_context(self, texts: List[str], source_lang: str,
                                      target_lang: str, domain: str = 'default') -> List[Dict]:
        """
        Multiple texts একটি request-এ translate করে — GPT context window utilize করে।
        Consistent translations across related strings.
        """
        if not self.api_key or not texts:
            return [self.format_result(t, source_lang, target_lang) for t in texts]
        try:
            domain_instruction = self.DOMAIN_PROMPTS.get(domain, self.DOMAIN_PROMPTS['default'])
            numbered = '\n'.join(f'{i+1}. {t}' for i, t in enumerate(texts[:20]))

            system_prompt = f"""You are an expert translator ({source_lang} → {target_lang}).
{domain_instruction}
Translate the numbered list below. Return ONLY the translations in the same numbered format.
Maintain consistency — same term should always translate the same way.
Preserve all placeholders, HTML tags, and ICU format."""

            payload = {
                'model': self._model,
                'messages': [
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': numbered},
                ],
                'temperature': 0.1,
                'max_tokens': min(sum(len(t) for t in texts) * 4 + 200, 4000),
            }

            req = urllib.request.Request(
                self.BASE_URL,
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {self.api_key}'},
                method='POST'
            )

            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read().decode('utf-8'))

            response_text = result['choices'][0]['message']['content'].strip()

            # Parse numbered list response
            import re
            lines = response_text.split('\n')
            translations = {}
            for line in lines:
                m = re.match(r'^(\d+)\.\s*(.+)$', line.strip())
                if m:
                    idx = int(m.group(1)) - 1
                    translations[idx] = m.group(2).strip()

            results = []
            for i, text in enumerate(texts):
                translated = translations.get(i, text)
                results.append(self.format_result(translated, source_lang, target_lang))
            return results

        except Exception as e:
            logger.error(f"OpenAI batch translate failed: {e}")
            return [self.translate(t, source_lang, target_lang) for t in texts]

    def get_supported_languages(self) -> List[str]:
        """GPT supports virtually all languages"""
        return [
            'af', 'am', 'ar', 'az', 'be', 'bg', 'bn', 'bs', 'ca', 'cs', 'cy', 'da',
            'de', 'el', 'en', 'eo', 'es', 'et', 'eu', 'fa', 'fi', 'fr', 'ga', 'gl',
            'gu', 'ha', 'he', 'hi', 'hr', 'hu', 'hy', 'id', 'is', 'it', 'ja', 'ka',
            'kk', 'km', 'kn', 'ko', 'ku', 'ky', 'lo', 'lt', 'lv', 'mg', 'mi', 'mk',
            'ml', 'mn', 'mr', 'ms', 'mt', 'my', 'ne', 'nl', 'no', 'ny', 'or', 'pa',
            'pl', 'ps', 'pt', 'ro', 'ru', 'rw', 'sd', 'si', 'sk', 'sl', 'sm', 'sn',
            'so', 'sq', 'sr', 'st', 'su', 'sv', 'sw', 'ta', 'te', 'tg', 'th', 'tk',
            'tl', 'tr', 'tt', 'ug', 'uk', 'ur', 'uz', 'vi', 'xh', 'yi', 'yo', 'zh', 'zu',
        ]

    def health_check(self) -> bool:
        try:
            if not self.api_key:
                return False
            result = self.translate('Hello', 'en', 'fr')
            translated = result.get('translated', '')
            return bool(translated) and translated != 'Hello'
        except Exception:
            return False
