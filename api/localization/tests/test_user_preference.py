# tests/test_user_preference.py
from django.test import TestCase
from unittest.mock import MagicMock
from .factories import make_language, make_currency


class UserPreferenceServiceTest(TestCase):
    def setUp(self):
        self.lang_en = make_language(code='up-en', name='UP English', is_default=True)
        self.lang_bn = make_language(code='up-bn', name='UP Bengali', is_default=False)
        self.currency = make_currency(code='UPT', name='UP Test', symbol='UT')

    def _mock_user(self, authenticated=False):
        user = MagicMock()
        user.is_authenticated = authenticated
        user.pk = 999
        return user

    def test_get_default_preferences_structure(self):
        from localization.services.services_loca.UserPreferenceService import UserPreferenceService
        prefs = UserPreferenceService()._get_default_preferences()
        self.assertEqual(prefs['language']['effective']['code'], 'en')
        self.assertEqual(prefs['currency']['code'], 'USD')
        self.assertEqual(prefs['timezone']['name'], 'UTC')
        self.assertTrue(prefs['auto_translate'])

    def test_get_full_preference_unauthenticated(self):
        from localization.services.services_loca.UserPreferenceService import UserPreferenceService
        prefs = UserPreferenceService().get_full_preference(self._mock_user(False))
        self.assertIsNotNone(prefs)
        self.assertIsNone(prefs['user_id'])

    def test_get_notification_language_default(self):
        from localization.services.services_loca.UserPreferenceService import UserPreferenceService
        result = UserPreferenceService().get_notification_language(self._mock_user(False))
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    def test_language_distribution_returns_list(self):
        from localization.services.services_loca.UserPreferenceService import UserPreferenceService
        result = UserPreferenceService().get_language_distribution()
        self.assertIsInstance(result, list)

    def test_lang_dict_helper_valid(self):
        from localization.services.services_loca.UserPreferenceService import UserPreferenceService
        lang = make_language(code='up-ld', name='Lang Dict Test', is_default=False)
        result = UserPreferenceService()._lang_dict(lang)
        self.assertEqual(result['code'], 'up-ld')
        self.assertIn('is_rtl', result)
        self.assertIn('text_direction', result)

    def test_lang_dict_none_returns_none(self):
        from localization.services.services_loca.UserPreferenceService import UserPreferenceService
        self.assertIsNone(UserPreferenceService()._lang_dict(None))

    def test_currency_dict_fallback_usd(self):
        from localization.services.services_loca.UserPreferenceService import UserPreferenceService
        result = UserPreferenceService()._currency_dict(None)
        self.assertEqual(result['code'], 'USD')
        self.assertEqual(result['symbol'], '$')

    def test_timezone_dict_fallback_utc(self):
        from localization.services.services_loca.UserPreferenceService import UserPreferenceService
        result = UserPreferenceService()._timezone_dict(None)
        self.assertEqual(result['name'], 'UTC')

    def test_set_date_format_invalid_rejects(self):
        from localization.services.services_loca.UserPreferenceService import UserPreferenceService
        result = UserPreferenceService().set_date_format(self._mock_user(False), 'BAD_FORMAT')
        self.assertFalse(result['success'])
        self.assertIn('error', result)

    def test_original_get_user_preference_unauthenticated(self):
        from localization.services.services_loca.UserPreferenceService import UserPreferenceService
        result = UserPreferenceService().get_user_preference(self._mock_user(False))
        self.assertIsNone(result)

    def test_original_set_user_preference_unauthenticated(self):
        from localization.services.services_loca.UserPreferenceService import UserPreferenceService
        result = UserPreferenceService().set_user_preference(self._mock_user(False), 'en')
        self.assertFalse(result)

    def test_create_preference_object_with_valid_lang(self):
        from localization.services.services_loca.UserPreferenceService import UserPreferenceService
        pref = UserPreferenceService()._create_preference_object('up-en')
        self.assertIsNotNone(pref)
        self.assertIsNotNone(pref.ui_language)

    def test_set_language_invalid_code(self):
        from localization.services.services_loca.UserPreferenceService import UserPreferenceService
        result = UserPreferenceService().set_language(self._mock_user(True), 'xx-invalid')
        self.assertFalse(result['success'])

    def test_set_currency_invalid_code(self):
        from localization.services.services_loca.UserPreferenceService import UserPreferenceService
        result = UserPreferenceService().set_currency(self._mock_user(True), 'INVALID')
        self.assertFalse(result['success'])

    def test_set_timezone_invalid(self):
        from localization.services.services_loca.UserPreferenceService import UserPreferenceService
        result = UserPreferenceService().set_timezone(self._mock_user(True), 'Not/A/Timezone')
        self.assertFalse(result['success'])

    def test_format_amount_for_user_fallback(self):
        from localization.services.services_loca.UserPreferenceService import UserPreferenceService
        result = UserPreferenceService().format_amount_for_user(self._mock_user(False), 1234.56)
        self.assertIsNotNone(result)
