# api/tests/test_localization.py
from django.test import TestCase
from django.contrib.auth import get_user_model
import uuid

User = get_user_model()
def uid(): return uuid.uuid4().hex[:8]


class LocalizationTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username=f'u_{uid()}',
            email=f'{uid()}@test.com',
            password='testpass123'
        )

    def test_language_creation(self):
        from api.localization.models import Language
        lang = Language.objects.create(
            code=f'ts{uid()[:2]}',   # unique code
            name='Test Language',
            name_native='Test',
            is_active=True,
            is_default=False,
        )
        self.assertTrue(lang.is_active)
        self.assertFalse(lang.is_default)

    def test_country_creation(self):
        from api.localization.models import Country
        country = Country.objects.create(
            code=f'T{uid()[:1]}'.upper()[:2],  # 2-char unique code
            name=f'TestCountry_{uid()}',
            phone_code='+880',
            is_active=True,
        )
        self.assertTrue(country.is_active)

    def test_currency_creation(self):
        from api.localization.models import Currency
        code = f'T{uid()[:2]}'.upper()[:3]
        currency = Currency.objects.create(
            code=code,
            name=f'TestCurrency_{uid()}',
            symbol='T$',
            is_active=True,
            is_default=False,
            exchange_rate='1.000000',
        )
        self.assertTrue(currency.is_active)

    def test_timezone_creation(self):
        from api.localization.models import Timezone
        tz = Timezone.objects.create(
            name=f'Asia/Test_{uid()}',
            code=f'TST{uid()[:3]}',
            offset='+06:00',
            offset_seconds=21600,
            is_active=True,
        )
        self.assertTrue(tz.is_active)
        self.assertIn('+06:00', str(tz))

    def test_translation_key_creation(self):
        """Test TranslationKey model creation"""
        from api.localization.models import TranslationKey
        # ✅ Real fields: key, description, category, context, is_plural, is_html
        key = TranslationKey.objects.create(
            key=f'test.key.{uid()}',         # unique key
            description='Test description',
            category='general',
            context='Test context',
            is_plural=False,
            is_html=False,
        )
        self.assertEqual(key.category, 'general')
        self.assertFalse(key.is_plural)

    def test_translation_creation(self):
        """Test Translation model with FK to TranslationKey and Language"""
        from api.localization.models import TranslationKey, Language, Translation
        lang = Language.objects.create(
            code=f'tr{uid()[:2]}',
            name='TransLang',
            is_active=True,
            is_default=False,
        )
        key = TranslationKey.objects.create(
            key=f'trans.key.{uid()}',
            category='ui',
        )
        translation = Translation.objects.create(
            key=key,
            language=lang,
            value='Translated text here',
            is_approved=True,
        )
        self.assertEqual(translation.value, 'Translated text here')
        self.assertTrue(translation.is_approved)

    def test_user_language_preference(self):
        """Test UserLanguagePreference model creation"""
        from api.localization.models import Language, UserLanguagePreference
        # ✅ Real fields: user, primary_language, ui_language, auto_translate
        lang = Language.objects.create(
            code=f'ul{uid()[:2]}',
            name='UserLang',
            is_active=True,
            is_default=False,
        )
        pref = UserLanguagePreference.objects.create(
            user=self.user,
            primary_language=lang,     # ✅ FK not secondary_languages
            ui_language=lang,
            auto_translate=True,
        )
        self.assertEqual(pref.primary_language, lang)
        self.assertTrue(pref.auto_translate)

    def test_translation_cache(self):
        from api.localization.models import TranslationCache
        from django.utils import timezone
        from datetime import timedelta
        tc = TranslationCache.objects.create(
            language_code='en',
            cache_key=f'test_cache_{uid()}',
            cache_data={'hello': 'world'},
            expires_at=timezone.now() + timedelta(hours=1),
        )
        self.assertEqual(tc.language_code, 'en')
        self.assertEqual(tc.cache_data['hello'], 'world')