# tests/test_providers.py — Translation provider mock tests
from django.test import TestCase


class GoogleTranslateProviderTest(TestCase):
    def test_provider_init(self):
        from localization.services.providers.GoogleTranslateProvider import GoogleTranslateProvider
        provider = GoogleTranslateProvider(api_key='test_key')
        self.assertEqual(provider.provider_name, 'google')
        self.assertTrue(provider.supports_auto_detect)

    def test_translate_no_key(self):
        from localization.services.providers.GoogleTranslateProvider import GoogleTranslateProvider
        provider = GoogleTranslateProvider(api_key='')
        result = provider.translate('Hello', 'en', 'fr')
        self.assertEqual(result['translated'], 'Hello')

    def test_get_supported_languages(self):
        from localization.services.providers.GoogleTranslateProvider import GoogleTranslateProvider
        langs = GoogleTranslateProvider().get_supported_languages()
        self.assertIn('en', langs)
        self.assertIn('bn', langs)
        self.assertIn('ar', langs)

    def test_format_result(self):
        from localization.services.providers.GoogleTranslateProvider import GoogleTranslateProvider
        result = GoogleTranslateProvider().format_result('Bonjour', 'en', 'fr', confidence=0.99)
        self.assertEqual(result['translated'], 'Bonjour')
        self.assertEqual(result['provider'], 'google')
        self.assertEqual(result['confidence'], 0.99)


class DeepLProviderTest(TestCase):
    def test_provider_init(self):
        from localization.services.providers.DeepLProvider import DeepLProvider
        self.assertEqual(DeepLProvider().provider_name, 'deepl')

    def test_lang_mapping(self):
        from localization.services.providers.DeepLProvider import DeepLProvider
        p = DeepLProvider()
        self.assertEqual(p.LANG_MAP.get('en'), 'EN')
        self.assertEqual(p.LANG_MAP.get('de'), 'DE')

    def test_translate_no_key(self):
        from localization.services.providers.DeepLProvider import DeepLProvider
        result = DeepLProvider(api_key='').translate('Test', 'en', 'de')
        self.assertEqual(result['translated'], 'Test')


class AzureProviderTest(TestCase):
    def test_provider_init(self):
        from localization.services.providers.MicrosoftAzureProvider import MicrosoftAzureProvider
        p = MicrosoftAzureProvider(api_key='key', config={'region': 'eastus'})
        self.assertEqual(p.provider_name, 'azure')

    def test_lang_mapping(self):
        from localization.services.providers.MicrosoftAzureProvider import MicrosoftAzureProvider
        p = MicrosoftAzureProvider()
        self.assertEqual(p.LANG_MAP.get('zh'), 'zh-Hans')
        self.assertIn('bn', p.LANG_MAP)
        self.assertIn('ur', p.LANG_MAP)

    def test_translate_no_key(self):
        from localization.services.providers.MicrosoftAzureProvider import MicrosoftAzureProvider
        result = MicrosoftAzureProvider(api_key='').translate('Hello', 'en', 'fr')
        self.assertEqual(result['translated'], 'Hello')

    def test_supported_languages_count(self):
        from localization.services.providers.MicrosoftAzureProvider import MicrosoftAzureProvider
        langs = MicrosoftAzureProvider().get_supported_languages()
        self.assertGreater(len(langs), 30)


class AmazonProviderTest(TestCase):
    def test_provider_init(self):
        from localization.services.providers.AmazonTranslateProvider import AmazonTranslateProvider
        self.assertEqual(AmazonTranslateProvider().provider_name, 'amazon')

    def test_translate_no_boto3(self):
        from localization.services.providers.AmazonTranslateProvider import AmazonTranslateProvider
        result = AmazonTranslateProvider(api_key='').translate('Hello', 'en', 'fr')
        self.assertEqual(result['translated'], 'Hello')

    def test_supported_languages(self):
        from localization.services.providers.AmazonTranslateProvider import AmazonTranslateProvider
        langs = AmazonTranslateProvider().get_supported_languages()
        self.assertIn('en', langs)
        self.assertIn('bn', langs)


class OpenAIProviderTest(TestCase):
    def test_provider_init(self):
        from localization.services.providers.OpenAIProvider import OpenAIProvider
        self.assertEqual(OpenAIProvider().provider_name, 'openai')

    def test_translate_no_key(self):
        from localization.services.providers.OpenAIProvider import OpenAIProvider
        result = OpenAIProvider(api_key='').translate('Hello', 'en', 'bn')
        self.assertEqual(result['translated'], 'Hello')

    def test_supports_rare_languages(self):
        from localization.services.providers.OpenAIProvider import OpenAIProvider
        langs = OpenAIProvider().get_supported_languages()
        self.assertIn('si', langs)
        self.assertIn('ne', langs)


class ProviderRouterTest(TestCase):
    def test_router_init_no_crash(self):
        from localization.services.providers.ProviderRouter import ProviderRouter
        router = ProviderRouter()
        self.assertIsNotNone(router)

    def test_router_translate_fallback(self):
        from localization.services.providers.ProviderRouter import ProviderRouter
        result = ProviderRouter().translate('Hello', 'en', 'fr')
        self.assertIn('translated', result)

    def test_health_checker_structure(self):
        from localization.services.providers.ProviderHealthChecker import ProviderHealthChecker
        results = ProviderHealthChecker().check_all()
        self.assertIn('providers', results)
        self.assertIn('all_healthy', results)
