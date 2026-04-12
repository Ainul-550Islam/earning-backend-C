# services/providers/ProviderRouter.py
"""
ProviderRouter — Translation provider fallback chain.
Priority: DeepL (1) → Google (2) → Azure (3) → Amazon (4) → OpenAI (5)
Cost optimization + health checking included.
"""
import logging
import time
from typing import Dict, List, Optional, Tuple
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


class ProviderRouter:
    """
    Routes translation requests through available providers.
    Fallback chain: tries providers in priority order until one succeeds.
    Caches provider health status for 5 minutes.
    """

    PROVIDER_CLASSES = {
        'google': ('GoogleTranslateProvider', 'GoogleTranslateProvider'),
        'deepl':  ('DeepLProvider', 'DeepLProvider'),
        'openai': ('OpenAIProvider', 'OpenAIProvider'),
        'azure':  ('MicrosoftAzureProvider', 'MicrosoftAzureProvider'),
        'amazon': ('AmazonTranslateProvider', 'AmazonTranslateProvider'),
    }

    def __init__(self):
        self._providers: Dict = {}
        self._fallback_order: List[Tuple[int, str]] = []
        self._load_providers()

    def _load_providers(self):
        """Settings থেকে available providers load করে"""
        try:
            provider_config = getattr(settings, 'TRANSLATION_PROVIDERS', {})

            if not provider_config:
                # Default config — all disabled (no API keys)
                logger.debug("No TRANSLATION_PROVIDERS in settings — all providers disabled")
                return

            for name, config in provider_config.items():
                if not config.get('enabled', True):
                    continue
                provider = self._create_provider(name, config)
                if provider:
                    self._providers[name] = provider
                    priority = config.get('priority', 99)
                    self._fallback_order.append((priority, name))

            self._fallback_order.sort(key=lambda x: x[0])
            logger.info(f"Loaded providers: {[n for _, n in self._fallback_order]}")

        except Exception as e:
            logger.error(f"Provider load failed: {e}")

    def _create_provider(self, name: str, config: dict):
        """Provider instance তৈরি করে — dynamic import with proper error handling"""
        try:
            module_name, class_name = self.PROVIDER_CLASSES.get(name, (None, None))
            if not module_name:
                logger.warning(f"Unknown provider: {name}")
                return None

            # Direct import — no relative import issues
            import importlib
            module_path = f'api.localization.services.providers.{module_name}'
            try:
                module = importlib.import_module(module_path)
            except ImportError:
                # Try alternative path
                module_path = f'localization.services.providers.{module_name}'
                module = importlib.import_module(module_path)

            provider_class = getattr(module, class_name)
            return provider_class(
                api_key=config.get('api_key', ''),
                config=config
            )

        except ImportError as e:
            logger.warning(f"Provider {name} import failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Provider {name} creation failed: {e}")
            return None

    def translate(self, text: str, source_lang: str, target_lang: str) -> Dict:
        """
        Fallback chain দিয়ে translate করে।
        সফল হলে result return করে, সব fail হলে source text return করে।
        """
        if not text or not text.strip():
            return self._format_result(text, source_lang, target_lang, 'empty_input')

        errors = []
        for priority, provider_name in self._fallback_order:
            # Skip unhealthy providers
            if self._is_provider_unhealthy(provider_name):
                logger.debug(f"Skipping unhealthy provider: {provider_name}")
                continue

            provider = self._providers.get(provider_name)
            if not provider:
                continue

            try:
                start_time = time.time()
                result = provider.translate(text, source_lang, target_lang)
                elapsed_ms = int((time.time() - start_time) * 1000)

                translated = result.get('translated', '')
                if translated and translated != text:
                    result['provider'] = provider_name
                    result['response_time_ms'] = elapsed_ms
                    logger.debug(f"Translation by {provider_name} in {elapsed_ms}ms")
                    # Log successful provider
                    self._log_provider_success(provider_name)
                    return result

            except Exception as e:
                error_msg = f"{provider_name}: {str(e)}"
                errors.append(error_msg)
                logger.warning(f"Provider {provider_name} failed: {e} — trying next...")
                self._mark_provider_unhealthy(provider_name, str(e))

        # All providers failed
        if errors:
            logger.error(f"All providers failed for '{text[:30]}...': {errors}")

        return self._format_result(text, source_lang, target_lang, 'all_failed')

    def bulk_translate(self, texts: List[str], source_lang: str, target_lang: str) -> List[Dict]:
        """Multiple texts translate করে — providers that support bulk use it"""
        results = []
        for text in texts:
            results.append(self.translate(text, source_lang, target_lang))
        return results

    def health_check_all(self) -> Dict:
        """সব providers-এর health check করে"""
        results = {'providers': {}, 'all_healthy': True, 'total': len(self._providers)}
        for name, provider in self._providers.items():
            try:
                cache_key = f"provider_health_{name}"
                cached = cache.get(cache_key)
                if cached is not None:
                    results['providers'][name] = cached
                    if not cached.get('healthy', False):
                        results['all_healthy'] = False
                    continue

                healthy = provider.health_check()
                status = {'healthy': healthy, 'provider': name}
                cache.set(cache_key, status, 300)  # 5 min cache
                results['providers'][name] = status
                if not healthy:
                    results['all_healthy'] = False

            except Exception as e:
                results['providers'][name] = {'healthy': False, 'error': str(e)}
                results['all_healthy'] = False

        return results

    def get_best_provider_for_pair(self, source_lang: str, target_lang: str) -> Optional[str]:
        """Language pair-এর জন্য best provider বেছে নেয়"""
        # DeepL is best for European languages
        deepl_langs = {'en', 'de', 'fr', 'es', 'pt', 'it', 'nl', 'pl', 'ru', 'ja', 'zh'}
        if (source_lang in deepl_langs and target_lang in deepl_langs
                and 'deepl' in self._providers):
            if not self._is_provider_unhealthy('deepl'):
                return 'deepl'

        # OpenAI is best for rare/complex languages
        rare_langs = {'si', 'ne', 'am', 'sw', 'my', 'km'}
        if (source_lang in rare_langs or target_lang in rare_langs):
            if 'openai' in self._providers and not self._is_provider_unhealthy('openai'):
                return 'openai'

        # Default: first healthy provider
        for _, name in self._fallback_order:
            if not self._is_provider_unhealthy(name):
                return name

        return None

    def get_supported_languages(self) -> List[str]:
        """All providers মিলিয়ে supported languages"""
        all_langs = set()
        for provider in self._providers.values():
            try:
                all_langs.update(provider.get_supported_languages())
            except Exception:
                pass
        return sorted(all_langs)

    def get_status(self) -> Dict:
        """Router status — কোন providers loaded আছে"""
        return {
            'loaded_providers': [n for _, n in self._fallback_order],
            'total_providers': len(self._providers),
            'fallback_order': self._fallback_order,
        }

    # ── Private helpers ──────────────────────────────────────────

    def _format_result(self, text: str, source_lang: str, target_lang: str, reason: str) -> Dict:
        return {
            'translated': text,
            'source_lang': source_lang,
            'target_lang': target_lang,
            'provider': 'fallback',
            'reason': reason,
        }

    def _is_provider_unhealthy(self, name: str) -> bool:
        cache_key = f"provider_unhealthy_{name}"
        return bool(cache.get(cache_key))

    def _mark_provider_unhealthy(self, name: str, error: str):
        """Provider 5 min-এর জন্য unhealthy mark করে"""
        cache_key = f"provider_unhealthy_{name}"
        cache.set(cache_key, {'error': error}, 300)
        logger.warning(f"Provider {name} marked unhealthy for 5 minutes")

    def _log_provider_success(self, name: str):
        """Successful provider থেকে unhealthy mark সরায়"""
        cache_key = f"provider_unhealthy_{name}"
        cache.delete(cache_key)
