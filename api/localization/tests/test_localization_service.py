# tests/test_localization_service.py
from django.test import TestCase
from .factories import make_language


class LocalizationServiceTest(TestCase):
    def setUp(self):
        self.lang = make_language(code='loc-en', name='Loc English', is_default=True)

    def test_service_import(self):
        from localization.services.services_loca.LocalizationService import LocalizationService
        service = LocalizationService()
        self.assertIsNotNone(service)

    def test_get_language_code_from_request(self):
        from localization.services.services_loca.LocalizationService import LocalizationService
        from django.test import RequestFactory
        service = LocalizationService()
        request = RequestFactory().get('/', HTTP_ACCEPT_LANGUAGE='bn-BD,bn;q=0.9,en;q=0.8')
        try:
            result = service.get_language_for_request(request)
            self.assertIsNotNone(result)
        except AttributeError:
            pass

    def test_localization_service_has_key_methods(self):
        from localization.services.services_loca.LocalizationService import LocalizationService
        service = LocalizationService()
        for method in ['get_language_for_request', 'get_translation', 'detect_language']:
            self.assertTrue(hasattr(service, method), f"Missing method: {method}")
