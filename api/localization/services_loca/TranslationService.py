import requests
import json
from django.conf import settings
from django.core.cache import cache
from django.utils.translation import gettext_lazy as _
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from .LanguageDetector import LanguageDetector
from ..models import Language, Translation

logger = logging.getLogger(__name__)


class TranslationService:
    """
    Service for translating text using various providers
    Supports: Google Translate, DeepL, Microsoft Azure, Amazon Translate
    """
    
    def __init__(self):
        self.providers = self._initialize_providers()
        self.detector = LanguageDetector()
        self.cache_timeout = 3600 * 24 * 7  # 7 days cache
        
    def _initialize_providers(self) -> Dict:
        """Initialize available translation providers"""
        providers = {}
        
        # Google Cloud Translate
        if hasattr(settings, 'GOOGLE_TRANSLATE_API_KEY'):
            providers['google'] = GoogleTranslateProvider()
        
        # DeepL
        if hasattr(settings, 'DEEPL_API_KEY'):
            providers['deepl'] = DeepLProvider()
        
        # Microsoft Azure
        if (hasattr(settings, 'AZURE_TRANSLATE_KEY') and 
            hasattr(settings, 'AZURE_TRANSLATE_ENDPOINT')):
            providers['azure'] = AzureTranslateProvider()
        
        # Amazon Translate
        if (hasattr(settings, 'AWS_ACCESS_KEY_ID') and 
            hasattr(settings, 'AWS_SECRET_ACCESS_KEY') and
            hasattr(settings, 'AWS_TRANSLATE_REGION')):
            providers['amazon'] = AmazonTranslateProvider()
        
        # Fallback: MyMemory Translate (free)
        providers['mymemory'] = MyMemoryTranslateProvider()
        
        return providers
    
    def translate(
        self,
        text: str,
        target_language: str,
        source_language: Optional[str] = None,
        context: Optional[str] = None,
        provider: str = 'auto',
        formality: Optional[str] = None
    ) -> Dict:
        """
        Translate text to target language
        
        Args:
            text: Text to translate
            target_language: Target language code (e.g., 'bn', 'es')
            source_language: Source language code (optional, auto-detected)
            context: Context for translation (helps with accuracy)
            provider: Translation provider ('auto', 'google', 'deepl', etc.)
            formality: Formality level ('formal', 'informal') for some providers
        
        Returns:
            Dictionary with translation results
        """
        # Check cache first
        cache_key = self._get_cache_key(
            text, target_language, source_language, context, provider
        )
        cached_result = cache.get(cache_key)
        
        if cached_result:
            logger.debug(f"Cache hit for translation: {cache_key}")
            cached_result['from_cache'] = True
            return cached_result
        
        # Validate target language
        if not Language.objects.filter(code=target_language, is_active=True).exists():
            raise ValueError(f"Target language not supported: {target_language}")
        
        # Detect source language if not provided
        if not source_language:
            detection_result = self.detector.detect_language(text)
            source_language = detection_result['language']
            detection_confidence = detection_result['confidence']
        else:
            detection_confidence = 1.0
        
        # Don't translate if source and target are same
        if source_language == target_language:
            return {
                'translated_text': text,
                'source_language': source_language,
                'target_language': target_language,
                'confidence': 1.0,
                'provider': 'none',
                'from_cache': False
            }
        
        # Select provider
        translation_provider = self._select_provider(provider)
        
        try:
            # Perform translation
            result = translation_provider.translate(
                text=text,
                source_language=source_language,
                target_language=target_language,
                context=context,
                formality=formality
            )
            
            # Add metadata
            result.update({
                'from_cache': False,
                'detection_confidence': detection_confidence,
                'text_length': len(text),
                'character_count': len(text),
                'word_count': len(text.split()),
                'timestamp': datetime.now().isoformat(),
            })
            
            # Cache the result
            cache.set(cache_key, result, self.cache_timeout)
            
            # Log successful translation
            self._log_translation(
                text, result['translated_text'], 
                source_language, target_language,
                translation_provider.name, result.get('confidence', 0)
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Translation failed: {str(e)}")
            
            # Try fallback provider
            if translation_provider.name != 'mymemory':
                logger.info(f"Trying fallback provider for translation")
                try:
                    fallback_result = self.providers['mymemory'].translate(
                        text=text,
                        source_language=source_language,
                        target_language=target_language,
                        context=context
                    )
                    
                    fallback_result.update({
                        'from_cache': False,
                        'provider': 'mymemory_fallback',
                        'original_provider_failed': translation_provider.name
                    })
                    
                    # Cache fallback result with shorter timeout
                    cache.set(cache_key, fallback_result, 3600)
                    
                    return fallback_result
                    
                except Exception as fallback_error:
                    logger.error(f"Fallback translation also failed: {str(fallback_error)}")
            
            raise Exception(f"Translation failed: {str(e)}")
    
    def translate_batch(
        self,
        texts: List[str],
        target_language: str,
        source_language: Optional[str] = None,
        provider: str = 'auto'
    ) -> List[Dict]:
        """
        Translate multiple texts at once
        """
        results = []
        
        for text in texts:
            try:
                result = self.translate(
                    text=text,
                    target_language=target_language,
                    source_language=source_language,
                    provider=provider
                )
                results.append(result)
            except Exception as e:
                results.append({
                    'text': text,
                    'error': str(e),
                    'translated_text': '',
                    'success': False
                })
        
        return results
    
    def get_supported_languages(self, provider: str = None) -> Dict:
        """
        Get supported languages by provider
        """
        if provider and provider in self.providers:
            return self.providers[provider].get_supported_languages()
        
        # Merge all providers' supported languages
        all_languages = {}
        for prov_name, provider_instance in self.providers.items():
            try:
                provider_langs = provider_instance.get_supported_languages()
                for lang_code, lang_name in provider_langs.items():
                    if lang_code not in all_languages:
                        all_languages[lang_code] = {
                            'name': lang_name,
                            'providers': [prov_name]
                        }
                    else:
                        all_languages[lang_code]['providers'].append(prov_name)
            except Exception as e:
                logger.error(f"Error getting languages from {prov_name}: {e}")
        
        return all_languages
    
    def get_usage_statistics(self) -> Dict:
        """
        Get translation service usage statistics
        """
        # Get from cache or database
        cache_key = 'translation_service_stats'
        stats = cache.get(cache_key)
        
        if not stats:
            stats = {
                'total_translations': 0,
                'by_provider': {},
                'by_language_pair': {},
                'success_rate': 100,
                'average_response_time': 0,
                'today_count': 0
            }
            
            # TODO: Implement actual statistics collection
            # This could be stored in a database table
            
            cache.set(cache_key, stats, 300)  # Cache for 5 minutes
        
        return stats
    
    def _select_provider(self, provider_name: str):
        """
        Select translation provider based on preference and availability
        """
        if provider_name == 'auto':
            # Auto-select based on language pair and performance
            # For now, return the first available premium provider
            for name in ['deepl', 'google', 'azure', 'amazon']:
                if name in self.providers:
                    return self.providers[name]
            return self.providers['mymemory']
        
        elif provider_name in self.providers:
            return self.providers[provider_name]
        
        else:
            raise ValueError(f"Unknown provider: {provider_name}")
    
    def _get_cache_key(
        self,
        text: str,
        target_language: str,
        source_language: Optional[str],
        context: Optional[str],
        provider: str
    ) -> str:
        """Generate cache key for translation"""
        import hashlib
        
        key_parts = [
            text,
            target_language,
            source_language or 'auto',
            context or '',
            provider
        ]
        
        key_string = '|'.join(key_parts)
        return f"translation:{hashlib.md5(key_string.encode()).hexdigest()}"
    
    def _log_translation(
        self,
        original_text: str,
        translated_text: str,
        source_lang: str,
        target_lang: str,
        provider: str,
        confidence: float
    ):
        """
        Log translation for analytics and monitoring
        """
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'source_language': source_lang,
            'target_language': target_lang,
            'provider': provider,
            'confidence': confidence,
            'original_length': len(original_text),
            'translated_length': len(translated_text),
            'character_reduction': len(original_text) - len(translated_text),
        }
        
        logger.info(f"Translation completed: {log_entry}")
        
        # Store in database for analytics if enabled
        if hasattr(settings, 'LOG_TRANSLATIONS') and settings.LOG_TRANSLATIONS:
            try:
                from ..models import TranslationLog
                
                TranslationLog.objects.create(
                    source_language=source_lang,
                    target_language=target_lang,
                    provider=provider,
                    confidence=confidence,
                    original_text_length=len(original_text),
                    translated_text_length=len(translated_text),
                    metadata=log_entry
                )
            except Exception as e:
                logger.error(f"Error logging translation: {e}")


class TranslationProvider:
    """Base class for translation providers"""
    
    def __init__(self):
        self.name = "base"
        self.supports_formality = False
        self.supports_context = False
        self.max_text_length = 5000
        self.rate_limit = 1000  # requests per hour
    
    def translate(self, **kwargs):
        raise NotImplementedError
    
    def get_supported_languages(self):
        raise NotImplementedError
    
    def validate_text(self, text: str) -> bool:
        """Validate text before translation"""
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")
        
        if len(text) > self.max_text_length:
            raise ValueError(f"Text too long. Maximum {self.max_text_length} characters.")
        
        return True


class GoogleTranslateProvider(TranslationProvider):
    """Google Cloud Translate provider"""
    
    def __init__(self):
        super().__init__()
        self.name = "google"
        self.api_key = settings.GOOGLE_TRANSLATE_API_KEY
        self.endpoint = "https://translation.googleapis.com/language/translate/v2"
        self.max_text_length = 30000
        self.supports_context = True
        
        # Google supported languages (partial list)
        self._supported_languages = {
            'en': 'English',
            'bn': 'Bengali',
            'hi': 'Hindi',
            'es': 'Spanish',
            'fr': 'French',
            'de': 'German',
            'pt': 'Portuguese',
            'ru': 'Russian',
            'ar': 'Arabic',
            'ja': 'Japanese',
            'zh': 'Chinese',
            'ko': 'Korean',
            # Add more as needed
        }
    
    def translate(
        self,
        text: str,
        source_language: str,
        target_language: str,
        context: Optional[str] = None,
        **kwargs
    ) -> Dict:
        self.validate_text(text)
        
        params = {
            'q': text,
            'target': target_language,
            'key': self.api_key,
            'format': 'text'
        }
        
        if source_language != 'auto':
            params['source'] = source_language
        
        if context and self.supports_context:
            params['context'] = context
        
        try:
            response = requests.post(self.endpoint, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if 'data' in data and 'translations' in data['data']:
                translation = data['data']['translations'][0]
                
                return {
                    'translated_text': translation['translatedText'],
                    'source_language': translation.get('detectedSourceLanguage', source_language),
                    'target_language': target_language,
                    'confidence': float(translation.get('confidence', 0.8)),
                    'provider': self.name
                }
            
            raise Exception("Invalid response from Google Translate")
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Google Translate API error: {e}")
            raise Exception(f"Google Translate API error: {str(e)}")
    
    def get_supported_languages(self):
        try:
            # Get from Google API
            params = {'key': self.api_key, 'target': 'en'}
            response = requests.get(
                'https://translation.googleapis.com/language/translate/v2/languages',
                params=params,
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                languages = {
                    lang['language']: lang['name']
                    for lang in data.get('data', {}).get('languages', [])
                }
                return languages
        except:
            pass
        
        # Return cached list if API fails
        return self._supported_languages


class DeepLProvider(TranslationProvider):
    """DeepL Translate provider"""
    
    def __init__(self):
        super().__init__()
        self.name = "deepl"
        self.api_key = settings.DEEPL_API_KEY
        self.endpoint = "https://api.deepl.com/v2/translate"
        self.max_text_length = 50000
        self.supports_formality = True
        self.supports_context = True
        
        # DeepL specific features
        self._formality_options = ['default', 'more', 'less']
    
    def translate(
        self,
        text: str,
        source_language: str,
        target_language: str,
        context: Optional[str] = None,
        formality: Optional[str] = None,
        **kwargs
    ) -> Dict:
        self.validate_text(text)
        
        # DeepL uses different language codes
        target_language = self._normalize_language_code(target_language, 'target')
        if source_language != 'auto':
            source_language = self._normalize_language_code(source_language, 'source')
        
        data = {
            'text': text,
            'target_lang': target_language,
            'auth_key': self.api_key
        }
        
        if source_language != 'auto':
            data['source_lang'] = source_language
        
        if formality and formality in self._formality_options:
            data['formality'] = formality
        
        if context and self.supports_context:
            data['context'] = context
        
        try:
            response = requests.post(self.endpoint, data=data, timeout=15)
            response.raise_for_status()
            
            result = response.json()
            
            if 'translations' in result:
                translation = result['translations'][0]
                
                return {
                    'translated_text': translation['text'],
                    'source_language': translation.get('detected_source_language', source_language),
                    'target_language': target_language,
                    'confidence': 0.9,  # DeepL doesn't provide confidence
                    'provider': self.name,
                    'formality_used': formality or 'default'
                }
            
            raise Exception("Invalid response from DeepL")
            
        except requests.exceptions.RequestException as e:
            logger.error(f"DeepL API error: {e}")
            
            # Check if it's a quota error
            if response.status_code == 456:
                raise Exception("DeepL API quota exceeded")
            
            raise Exception(f"DeepL API error: {str(e)}")
    
    def _normalize_language_code(self, code: str, direction: str = 'target') -> str:
        """
        Normalize language code for DeepL
        DeepL uses different codes (e.g., EN-US, EN-GB)
        """
        code = code.upper()
        
        # Mapping for common languages
        mapping = {
            'EN': 'EN-US' if direction == 'target' else 'EN',
            'PT': 'PT-PT',  # European Portuguese
            'ZH': 'ZH' if direction == 'target' else 'ZH',  # Chinese
        }
        
        return mapping.get(code, code)
    
    def get_supported_languages(self):
        try:
            # DeepL API endpoint for supported languages
            params = {'auth_key': self.api_key}
            response = requests.get(
                'https://api.deepl.com/v2/languages',
                params=params,
                timeout=5
            )
            
            if response.status_code == 200:
                languages = response.json()
                lang_dict = {}
                
                for lang in languages:
                    if lang['type'] == 'target':  # We want target languages
                        lang_dict[lang['language']] = lang['name']
                
                return lang_dict
        except:
            pass
        
        # Return default list if API fails
        return {
            'BG': 'Bulgarian', 'CS': 'Czech', 'DA': 'Danish', 'DE': 'German',
            'EL': 'Greek', 'EN-US': 'English (American)', 'EN-GB': 'English (British)',
            'ES': 'Spanish', 'ET': 'Estonian', 'FI': 'Finnish', 'FR': 'French',
            'HU': 'Hungarian', 'ID': 'Indonesian', 'IT': 'Italian', 'JA': 'Japanese',
            'KO': 'Korean', 'LT': 'Lithuanian', 'LV': 'Latvian', 'NB': 'Norwegian',
            'NL': 'Dutch', 'PL': 'Polish', 'PT-PT': 'Portuguese', 'PT-BR': 'Portuguese (Brazilian)',
            'RO': 'Romanian', 'RU': 'Russian', 'SK': 'Slovak', 'SL': 'Slovenian',
            'SV': 'Swedish', 'TR': 'Turkish', 'UK': 'Ukrainian', 'ZH': 'Chinese'
        }


class AzureTranslateProvider(TranslationProvider):
    """Microsoft Azure Translate provider"""
    
    def __init__(self):
        super().__init__()
        self.name = "azure"
        self.api_key = settings.AZURE_TRANSLATE_KEY
        self.endpoint = settings.AZURE_TRANSLATE_ENDPOINT
        self.location = getattr(settings, 'AZURE_TRANSLATE_LOCATION', 'global')
        self.max_text_length = 10000
    
    def translate(
        self,
        text: str,
        source_language: str,
        target_language: str,
        **kwargs
    ) -> Dict:
        self.validate_text(text)
        
        # Azure Translate endpoint
        url = f"{self.endpoint}/translate"
        
        params = {
            'api-version': '3.0',
            'to': target_language
        }
        
        if source_language != 'auto':
            params['from'] = source_language
        
        headers = {
            'Ocp-Apim-Subscription-Key': self.api_key,
            'Ocp-Apim-Subscription-Region': self.location,
            'Content-Type': 'application/json'
        }
        
        body = [{'text': text}]
        
        try:
            response = requests.post(url, params=params, headers=headers, json=body, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            
            if result and len(result) > 0:
                translation_data = result[0]
                translations = translation_data.get('translations', [])
                
                if translations:
                    translation = translations[0]
                    
                    return {
                        'translated_text': translation['text'],
                        'source_language': translation_data.get('detectedLanguage', {}).get('language', source_language),
                        'target_language': target_language,
                        'confidence': translation_data.get('detectedLanguage', {}).get('confidence', 0.8),
                        'provider': self.name
                    }
            
            raise Exception("Invalid response from Azure Translate")
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Azure Translate API error: {e}")
            raise Exception(f"Azure Translate API error: {str(e)}")
    
    def get_supported_languages(self):
        try:
            url = f"{self.endpoint}/languages"
            params = {'api-version': '3.0', 'scope': 'translation'}
            
            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()
            
            data = response.json()
            if 'translation' in data:
                return {
                    code: info['name']
                    for code, info in data['translation'].items()
                }
        except:
            pass
        
        # Return default list
        return {
            'af': 'Afrikaans', 'ar': 'Arabic', 'bn': 'Bangla', 'bs': 'Bosnian',
            'bg': 'Bulgarian', 'yue': 'Cantonese', 'ca': 'Catalan', 'zh-Hans': 'Chinese Simplified',
            'zh-Hant': 'Chinese Traditional', 'hr': 'Croatian', 'cs': 'Czech', 'da': 'Danish',
            'nl': 'Dutch', 'en': 'English', 'et': 'Estonian', 'fj': 'Fijian',
            'fil': 'Filipino', 'fi': 'Finnish', 'fr': 'French', 'de': 'German',
            'el': 'Greek', 'ht': 'Haitian Creole', 'he': 'Hebrew', 'hi': 'Hindi',
            'mww': 'Hmong Daw', 'hu': 'Hungarian', 'is': 'Icelandic', 'id': 'Indonesian',
            'it': 'Italian', 'ja': 'Japanese', 'sw': 'Kiswahili', 'tlh': 'Klingon',
            'ko': 'Korean', 'lv': 'Latvian', 'lt': 'Lithuanian', 'mg': 'Malagasy',
            'ms': 'Malay', 'mt': 'Maltese', 'nb': 'Norwegian', 'fa': 'Persian',
            'pl': 'Polish', 'pt': 'Portuguese', 'otq': 'Querétaro Otomi', 'ro': 'Romanian',
            'ru': 'Russian', 'sm': 'Samoan', 'sr-Cyrl': 'Serbian (Cyrillic)', 'sr-Latn': 'Serbian (Latin)',
            'sk': 'Slovak', 'sl': 'Slovenian', 'es': 'Spanish', 'sv': 'Swedish',
            'ty': 'Tahitian', 'ta': 'Tamil', 'te': 'Telugu', 'th': 'Thai',
            'to': 'Tongan', 'tr': 'Turkish', 'uk': 'Ukrainian', 'ur': 'Urdu',
            'vi': 'Vietnamese', 'cy': 'Welsh', 'yua': 'Yucatec Maya'
        }


class AmazonTranslateProvider(TranslationProvider):
    """Amazon Translate provider"""
    
    def __init__(self):
        super().__init__()
        self.name = "amazon"
        self.region = settings.AWS_TRANSLATE_REGION
        self.max_text_length = 5000
        
        # Import boto3 only when needed
        try:
            import boto3
            self.client = boto3.client(
                'translate',
                region_name=self.region,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
            )
        except ImportError:
            logger.error("boto3 not installed")
            self.client = None
        except Exception as e:
            logger.error(f"Failed to initialize AWS Translate: {e}")
            self.client = None
    
    def translate(
        self,
        text: str,
        source_language: str,
        target_language: str,
        **kwargs
    ) -> Dict:
        if not self.client:
            raise Exception("AWS Translate client not initialized")
        
        self.validate_text(text)
        
        try:
            response = self.client.translate_text(
                Text=text,
                SourceLanguageCode=source_language if source_language != 'auto' else 'auto',
                TargetLanguageCode=target_language
            )
            
            return {
                'translated_text': response['TranslatedText'],
                'source_language': response.get('SourceLanguageCode', source_language),
                'target_language': target_language,
                'confidence': 0.85,  # AWS doesn't provide confidence
                'provider': self.name,
                'applied_terminology': response.get('AppliedTerminologies', [])
            }
            
        except Exception as e:
            logger.error(f"AWS Translate error: {e}")
            raise Exception(f"AWS Translate error: {str(e)}")
    
    def get_supported_languages(self):
        if not self.client:
            return {}
        
        try:
            response = self.client.list_languages()
            languages = {
                lang['LanguageCode']: lang['LanguageName']
                for lang in response['Languages']
            }
            return languages
        except:
            pass
        
        # Return default list
        return {
            'af': 'Afrikaans', 'sq': 'Albanian', 'am': 'Amharic', 'ar': 'Arabic',
            'hy': 'Armenian', 'az': 'Azerbaijani', 'bn': 'Bengali', 'bs': 'Bosnian',
            'bg': 'Bulgarian', 'ca': 'Catalan', 'zh': 'Chinese', 'zh-TW': 'Chinese (Taiwan)',
            'hr': 'Croatian', 'cs': 'Czech', 'da': 'Danish', 'fa-AF': 'Dari',
            'nl': 'Dutch', 'en': 'English', 'et': 'Estonian', 'fa': 'Farsi (Persian)',
            'tl': 'Filipino', 'fi': 'Finnish', 'fr': 'French', 'fr-CA': 'French (Canada)',
            'ka': 'Georgian', 'de': 'German', 'el': 'Greek', 'gu': 'Gujarati',
            'ht': 'Haitian Creole', 'ha': 'Hausa', 'he': 'Hebrew', 'hi': 'Hindi',
            'hu': 'Hungarian', 'is': 'Icelandic', 'id': 'Indonesian', 'ga': 'Irish',
            'it': 'Italian', 'ja': 'Japanese', 'kn': 'Kannada', 'kk': 'Kazakh',
            'ko': 'Korean', 'lv': 'Latvian', 'lt': 'Lithuanian', 'mk': 'Macedonian',
            'ms': 'Malay', 'ml': 'Malayalam', 'mt': 'Maltese', 'mr': 'Marathi',
            'mn': 'Mongolian', 'no': 'Norwegian', 'ps': 'Pashto', 'pl': 'Polish',
            'pt': 'Portuguese', 'ro': 'Romanian', 'ru': 'Russian', 'sr': 'Serbian',
            'si': 'Sinhala', 'sk': 'Slovak', 'sl': 'Slovenian', 'so': 'Somali',
            'es': 'Spanish', 'sw': 'Swahili', 'sv': 'Swedish', 'ta': 'Tamil',
            'te': 'Telugu', 'th': 'Thai', 'tr': 'Turkish', 'uk': 'Ukrainian',
            'ur': 'Urdu', 'uz': 'Uzbek', 'vi': 'Vietnamese', 'cy': 'Welsh'
        }


class MyMemoryTranslateProvider(TranslationProvider):
    """
    MyMemory Translate provider (free, fallback)
    Limited to 1000 chars per request
    """
    
    def __init__(self):
        super().__init__()
        self.name = "mymemory"
        self.endpoint = "https://api.mymemory.translated.net/get"
        self.max_text_length = 500
        self.rate_limit = 100  # Very limited for free tier
    
    def translate(
        self,
        text: str,
        source_language: str,
        target_language: str,
        **kwargs
    ) -> Dict:
        self.validate_text(text)
        
        params = {
            'q': text,
            'langpair': f"{source_language}|{target_language}",
            'de': 'your-email@example.com'  # Required for higher limits
        }
        
        try:
            response = requests.get(self.endpoint, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            if data['responseStatus'] == 200:
                translated_text = data['responseData']['translatedText']
                
                # Clean up common issues
                translated_text = self._clean_translation(translated_text)
                
                return {
                    'translated_text': translated_text,
                    'source_language': source_language,
                    'target_language': target_language,
                    'confidence': data['responseData'].get('match', 0.5),
                    'provider': self.name,
                    'quota_used': data.get('quotaFinished', False)
                }
            
            raise Exception(f"MyMemory API error: {data.get('responseDetails', 'Unknown error')}")
            
        except requests.exceptions.RequestException as e:
            logger.error(f"MyMemory API error: {e}")
            raise Exception(f"MyMemory API error: {str(e)}")
    
    def _clean_translation(self, text: str) -> str:
        """Clean common issues in MyMemory translations"""
        # Remove leading/trailing quotes
        text = text.strip('"\'')
        
        # Fix common HTML entity issues
        replacements = {
            '&quot;': '"',
            '&#39;': "'",
            '&amp;': '&',
            '&lt;': '<',
            '&gt;': '>',
            '&nbsp;': ' '
        }
        
        for old, new in replacements.items():
            text = text.replace(old, new)
        
        return text
    
    def get_supported_languages(self):
        # MyMemory supports many languages
        return {
            'en': 'English', 'es': 'Spanish', 'fr': 'French', 'de': 'German',
            'it': 'Italian', 'pt': 'Portuguese', 'ru': 'Russian', 'zh': 'Chinese',
            'ja': 'Japanese', 'ko': 'Korean', 'ar': 'Arabic', 'hi': 'Hindi',
            'bn': 'Bengali', 'pa': 'Punjabi', 'gu': 'Gujarati', 'or': 'Odia',
            'ta': 'Tamil', 'te': 'Telugu', 'kn': 'Kannada', 'ml': 'Malayalam',
            'mr': 'Marathi', 'sa': 'Sanskrit', 'sd': 'Sindhi', 'ur': 'Urdu',
            'ne': 'Nepali', 'si': 'Sinhala', 'my': 'Burmese', 'km': 'Khmer',
            'th': 'Thai', 'lo': 'Lao', 'vi': 'Vietnamese', 'id': 'Indonesian',
            'tl': 'Tagalog', 'ms': 'Malay', 'jw': 'Javanese', 'su': 'Sundanese'
        }