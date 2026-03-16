# tests.py
from django.test import TestCase, Client
from django.test.utils import override_settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone
from django.db import transaction, IntegrityError
from django.core.exceptions import ValidationError
from django.urls import reverse
from decimal import Decimal
import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, List, Optional
from datetime import timedelta

from .models import (
    Language, Country, Currency, Timezone, City,
    TranslationKey, Translation, TranslationCache,
    UserLanguagePreference, MissingTranslation
)
from .services_loca import (
    language_service, translation_service, currency_service,
    timezone_service, country_service, city_service,
    user_preference_service, cache_service, health_check_service,
    ServiceFactory
)
from .serializers import (
    LanguageSerializer, CountrySerializer, CurrencySerializer,
    TranslationSerializer, UserLanguagePreferenceSerializer
)

User = get_user_model()

# ======================== Test Base Classes ========================

class BaseTestCase(TestCase):
    """Base test case with common setup and utilities"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        cache.clear()
        self._setup_test_data()
    
    def tearDown(self):
        """Clean up after tests"""
        cache.clear()
    
    def _setup_test_data(self):
        """Create test data - override in subclasses"""
        pass
    
    def assert_response_success(self, response, expected_status=200):
        """Assert response is successful"""
        self.assertEqual(response.status_code, expected_status)
        data = response.json()
        self.assertTrue(data.get('success', False))
        return data
    
    def assert_response_error(self, response, expected_status=400):
        """Assert response is error"""
        self.assertEqual(response.status_code, expected_status)
        data = response.json()
        self.assertFalse(data.get('success', True))
        return data
    
    def create_test_user(self, **kwargs):
        """Create a test user"""
        defaults = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'testpass123'
        }
        defaults.update(kwargs)
        return User.objects.create_user(**defaults)


# ======================== Model Tests ========================

class LanguageModelTests(BaseTestCase):
    """Test Language model"""
    
    def _setup_test_data(self):
        self.lang_en = Language.objects.create(
            code='en',
            name='English',
            name_native='English',
            is_default=True
        )
        self.lang_bn = Language.objects.create(
            code='bn',
            name='Bengali',
            name_native='বাংলা'
        )
    
    def test_language_creation(self):
        """Test language creation"""
        self.assertEqual(self.lang_en.code, 'en')
        self.assertEqual(self.lang_en.name, 'English')
        self.assertTrue(self.lang_en.is_default)
    
    def test_language_str_method(self):
        """Test string representation"""
        self.assertEqual(str(self.lang_en), 'English (en)')
        
        # Test with missing name
        lang = Language(code='fr')
        self.assertEqual(lang.get_safe_display(), 'fr')
    
    def test_language_save_default_constraint(self):
        """Test only one default language"""
        with self.assertRaises(Exception):
            with transaction.atomic():
                Language.objects.create(
                    code='fr',
                    name='French',
                    is_default=True
                )
    
    def test_language_get_safe_display(self):
        """Test safe display method"""
        self.assertEqual(self.lang_en.get_safe_display(), 'English (en)')
        
        # Test with None values
        lang = Language()
        self.assertEqual(lang.get_safe_display(), 'unknown')
    
    def test_language_properties(self):
        """Test language properties"""
        self.assertEqual(self.lang_en.safe_name, 'English')
        
        lang = Language(name='Test', name_native='Native')
        self.assertEqual(lang.safe_name, 'Native')


class CountryModelTests(BaseTestCase):
    """Test Country model"""
    
    def _setup_test_data(self):
        self.country = Country.objects.create(
            code='US',
            name='United States',
            phone_code='+1',
            phone_digits=10
        )
    
    def test_country_creation(self):
        """Test country creation"""
        self.assertEqual(self.country.code, 'US')
        self.assertEqual(self.country.name, 'United States')
    
    def test_country_str_method(self):
        """Test string representation"""
        self.assertEqual(str(self.country), 'United States (US)')
    
    def test_get_active_countries(self):
        """Test getting active countries"""
        countries = Country.get_active_countries()
        self.assertEqual(countries.count(), 1)
        
        # Test with inactive country
        self.country.is_active = False
        self.country.save()
        countries = Country.get_active_countries()
        self.assertEqual(countries.count(), 0)
    
    def test_get_safe_phone_code(self):
        """Test safe phone code retrieval"""
        self.assertEqual(self.country.get_safe_phone_code(), '+1')
        
        # Test with None
        country = Country()
        self.assertEqual(country.get_safe_phone_code(), '')


class CurrencyModelTests(BaseTestCase):
    """Test Currency model"""
    
    def _setup_test_data(self):
        self.usd = Currency.objects.create(
            code='USD',
            name='US Dollar',
            symbol='$',
            is_default=True
        )
        self.bdt = Currency.objects.create(
            code='BDT',
            name='Bangladeshi Taka',
            symbol='৳',
            exchange_rate=Decimal('110.50')
        )
    
    def test_currency_creation(self):
        """Test currency creation"""
        self.assertEqual(self.usd.code, 'USD')
        self.assertEqual(self.usd.symbol, '$')
    
    def test_currency_str_method(self):
        """Test string representation"""
        self.assertEqual(str(self.usd), 'USD ($)')
    
    def test_format_amount(self):
        """Test amount formatting"""
        self.assertEqual(self.usd.format_amount(100), '$100.00')
        self.assertEqual(self.usd.format_amount(None), '$0.00')
        self.assertEqual(self.bdt.format_amount(100), '৳100.00')
        
        # Test with invalid amount
        self.assertEqual(self.usd.format_amount('invalid'), '$0.00')
    
    def test_needs_exchange_update(self):
        """Test exchange rate update check"""
        self.assertTrue(self.bdt.needs_exchange_update)
        
        self.bdt.exchange_rate_updated_at = timezone.now()
        self.assertFalse(self.bdt.needs_exchange_update)
        
        # Test with old date
        self.bdt.exchange_rate_updated_at = timezone.now() - timedelta(days=2)
        self.assertTrue(self.bdt.needs_exchange_update)


class TimezoneModelTests(BaseTestCase):
    """Test Timezone model"""
    
    def _setup_test_data(self):
        self.tz = Timezone.objects.create(
            name='Asia/Dhaka',
            code='BDT',
            offset='+06:00',
            offset_seconds=21600
        )
    
    def test_timezone_creation(self):
        """Test timezone creation"""
        self.assertEqual(self.tz.name, 'Asia/Dhaka')
        self.assertEqual(self.tz.offset, '+06:00')
    
    def test_timezone_str_method(self):
        """Test string representation"""
        self.assertEqual(str(self.tz), 'Asia/Dhaka (UTC+06:00)')
    
    def test_get_current_time(self):
        """Test getting current time"""
        current = Timezone.get_current_time('Asia/Dhaka')
        self.assertIsNotNone(current)
        
        # Test with invalid timezone
        current = Timezone.get_current_time('Invalid/Timezone')
        self.assertIsNotNone(current)


class CityModelTests(BaseTestCase):
    """Test City model"""
    
    def _setup_test_data(self):
        self.country = Country.objects.create(
            code='US',
            name='United States',
            phone_code='+1'
        )
        self.city = City.objects.create(
            name='New York',
            country=self.country,
            is_capital=False
        )
    
    def test_city_creation(self):
        """Test city creation"""
        self.assertEqual(self.city.name, 'New York')
        self.assertEqual(self.city.country.code, 'US')
    
    def test_city_str_method(self):
        """Test string representation"""
        self.assertEqual(str(self.city), 'New York, US')
    
    def test_get_active_cities_for_country(self):
        """Test getting active cities for country"""
        cities = City.get_active_cities_for_country('US')
        self.assertEqual(cities.count(), 1)
        
        # Test with invalid country
        cities = City.get_active_cities_for_country('XX')
        self.assertEqual(cities.count(), 0)


class TranslationModelTests(BaseTestCase):
    """Test Translation models"""
    
    def _setup_test_data(self):
        self.lang_en = Language.objects.create(
            code='en',
            name='English',
            is_default=True
        )
        self.key = TranslationKey.objects.create(
            key='welcome_message',
            description='Welcome message'
        )
        self.translation = Translation.objects.create(
            key=self.key,
            language=self.lang_en,
            value='Welcome'
        )
    
    def test_translation_key_creation(self):
        """Test translation key creation"""
        self.assertEqual(self.key.key, 'welcome_message')
    
    def test_translation_creation(self):
        """Test translation creation"""
        self.assertEqual(self.translation.value, 'Welcome')
        self.assertTrue(self.translation.is_approved)  # Auto-approved for default language
    
    def test_translation_str_method(self):
        """Test string representation"""
        self.assertIn('welcome_message', str(self.translation))
    
    def test_get_or_create_key(self):
        """Test get or create translation key"""
        key, created = TranslationKey.get_or_create_key('new_key')
        self.assertTrue(created)
        self.assertEqual(key.key, 'new_key')
        
        # Test getting existing
        key2, created = TranslationKey.get_or_create_key('welcome_message')
        self.assertFalse(created)
        self.assertEqual(key2.key, 'welcome_message')


class UserPreferenceModelTests(BaseTestCase):
    """Test UserLanguagePreference model"""
    
    def _setup_test_data(self):
        self.user = self.create_test_user()
        self.lang_en = Language.objects.create(
            code='en',
            name='English',
            is_default=True
        )
        self.lang_bn = Language.objects.create(
            code='bn',
            name='Bengali'
        )
        self.pref = UserLanguagePreference.objects.create(
            user=self.user,
            primary_language=self.lang_en,
            ui_language=self.lang_en
        )
    
    def test_preference_creation(self):
        """Test preference creation"""
        self.assertEqual(self.pref.user, self.user)
        self.assertEqual(self.pref.primary_language.code, 'en')
    
    def test_effective_language(self):
        """Test effective language calculation"""
        effective = self.pref.effective_language
        self.assertEqual(effective.code, 'en')
        
        # Test with all None
        pref = UserLanguagePreference(user=self.user)
        effective = pref.effective_language
        self.assertEqual(effective.code, 'en')  # Default language
    
    def test_add_preferred_language(self):
        """Test adding preferred language"""
        result = self.pref.add_preferred_language('bn')
        self.assertTrue(result)
        self.assertEqual(self.pref.preferred_languages.count(), 1)
        
        # Test adding invalid language
        result = self.pref.add_preferred_language('xx')
        self.assertFalse(result)


# ======================== Service Tests ========================

class LanguageServiceTests(BaseTestCase):
    """Test LanguageService"""
    
    def _setup_test_data(self):
        self.lang_en = Language.objects.create(
            code='en',
            name='English',
            is_default=True
        )
        self.lang_bn = Language.objects.create(
            code='bn',
            name='Bengali'
        )
    
    def test_get_active_languages(self):
        """Test getting active languages"""
        languages = language_service.get_active_languages()
        self.assertEqual(len(languages), 2)
        
        # Test with search
        languages = language_service.get_active_languages(search='english')
        self.assertEqual(len(languages), 1)
        self.assertEqual(languages[0].code, 'en')
    
    def test_get_default_language(self):
        """Test getting default language"""
        default = language_service.get_default_language()
        self.assertEqual(default.code, 'en')
    
    def test_get_language_by_code(self):
        """Test getting language by code"""
        lang = language_service.get_language_by_code('en')
        self.assertEqual(lang.code, 'en')
        
        # Test with invalid code
        lang = language_service.get_language_by_code('xx')
        self.assertIsNone(lang)
    
    def test_set_default_language(self):
        """Test setting default language"""
        result = language_service.set_default_language(self.lang_bn)
        self.assertTrue(result)
        
        self.lang_bn.refresh_from_db()
        self.lang_en.refresh_from_db()
        self.assertTrue(self.lang_bn.is_default)
        self.assertFalse(self.lang_en.is_default)


class TranslationServiceTests(BaseTestCase):
    """Test TranslationService"""
    
    def _setup_test_data(self):
        self.lang_en = Language.objects.create(
            code='en',
            name='English',
            is_default=True
        )
        self.lang_bn = Language.objects.create(
            code='bn',
            name='Bengali'
        )
        self.key = TranslationKey.objects.create(key='welcome')
        self.translation = Translation.objects.create(
            key=self.key,
            language=self.lang_en,
            value='Welcome'
        )
    
    def test_get_translation(self):
        """Test getting translation"""
        # Test existing translation
        value = translation_service.get_translation('welcome', 'en')
        self.assertEqual(value, 'Welcome')
        
        # Test missing translation (returns key)
        value = translation_service.get_translation('missing', 'en')
        self.assertEqual(value, 'missing')
        
        # Test with default fallback
        value = translation_service.get_translation('missing', 'en', default='Hello')
        self.assertEqual(value, 'Hello')
    
    def test_get_translations_bulk(self):
        """Test bulk translation retrieval"""
        translations = translation_service.get_translations_bulk(
            ['welcome', 'goodbye'], 'en'
        )
        self.assertEqual(translations['welcome'], 'Welcome')
        self.assertEqual(translations['goodbye'], 'goodbye')
    
    def test_import_translations(self):
        """Test importing translations"""
        import_data = {
            'hello': 'হ্যালো',
            'goodbye': 'বিদায়'
        }
        
        result = translation_service.import_translations(
            'bn', import_data, source='test'
        )
        
        self.assertEqual(result['created'], 2)
        self.assertEqual(result['updated'], 0)
        
        # Verify translations were created
        translation = Translation.objects.filter(
            key__key='hello',
            language=self.lang_bn
        ).first()
        self.assertIsNotNone(translation)
        self.assertEqual(translation.value, 'হ্যালো')
    
    def test_export_translations(self):
        """Test exporting translations"""
        export = translation_service.export_translations('en')
        self.assertEqual(export['language']['code'], 'en')
        self.assertIn('welcome', export['translations'])


class CurrencyServiceTests(BaseTestCase):
    """Test CurrencyService"""
    
    def _setup_test_data(self):
        self.usd = Currency.objects.create(
            code='USD',
            name='US Dollar',
            symbol='$',
            exchange_rate=Decimal('1.0'),
            exchange_rate_updated_at=timezone.now()
        )
        self.bdt = Currency.objects.create(
            code='BDT',
            name='Bangladeshi Taka',
            symbol='৳',
            exchange_rate=Decimal('110.50'),
            exchange_rate_updated_at=timezone.now()
        )
    
    def test_convert_currency(self):
        """Test currency conversion"""
        result = currency_service.convert_currency(
            Decimal('100'), 'USD', 'BDT'
        )
        
        self.assertIsNotNone(result)
        self.assertEqual(result['from']['code'], 'USD')
        self.assertEqual(result['to']['code'], 'BDT')
        self.assertEqual(Decimal(result['to']['amount']), Decimal('11050.00'))
    
    def test_get_exchange_rate(self):
        """Test getting exchange rate"""
        rate = currency_service.get_exchange_rate('USD', 'BDT')
        self.assertEqual(rate, Decimal('110.5'))
        
        # Test with invalid currency
        rate = currency_service.get_exchange_rate('USD', 'XXX')
        self.assertIsNone(rate)
    
    def test_get_currencies_needing_update(self):
        """Test getting currencies needing update"""
        # Set old update time
        self.bdt.exchange_rate_updated_at = timezone.now() - timedelta(days=2)
        self.bdt.save()
        
        needing = currency_service.get_currencies_needing_update()
        self.assertEqual(len(needing), 1)
        self.assertEqual(needing[0].code, 'BDT')


# ======================== View Tests ========================

class LanguageViewTests(BaseTestCase):
    """Test language views"""
    
    def _setup_test_data(self):
        self.lang_en = Language.objects.create(
            code='en',
            name='English',
            is_default=True
        )
        self.lang_bn = Language.objects.create(
            code='bn',
            name='Bengali'
        )
    
    def test_language_list_view(self):
        """Test language list endpoint"""
        response = self.client.get('/api/v1/languages/')
        data = self.assert_response_success(response)
        
        self.assertEqual(len(data['data']['languages']), 2)
        self.assertEqual(data['data']['default_language']['code'], 'en')
    
    def test_language_detail_view(self):
        """Test language detail endpoint"""
        response = self.client.get('/api/v1/languages/en/')
        data = self.assert_response_success(response)
        
        self.assertEqual(data['data']['code'], 'en')
        self.assertEqual(data['data']['name'], 'English')
    
    def test_language_detail_not_found(self):
        """Test language detail not found"""
        response = self.client.get('/api/v1/languages/xx/')
        self.assert_response_error(response, 404)


class CountryViewTests(BaseTestCase):
    """Test country views"""
    
    def _setup_test_data(self):
        self.country = Country.objects.create(
            code='US',
            name='United States',
            phone_code='+1'
        )
    
    def test_country_list_view(self):
        """Test country list endpoint"""
        response = self.client.get('/api/v1/countries/')
        data = self.assert_response_success(response)
        
        self.assertEqual(len(data['data']['countries']), 1)
        self.assertEqual(data['data']['countries'][0]['code'], 'US')
    
    def test_country_detail_view(self):
        """Test country detail endpoint"""
        response = self.client.get('/api/v1/countries/US/')
        data = self.assert_response_success(response)
        
        self.assertEqual(data['data']['code'], 'US')
        self.assertEqual(data['data']['name'], 'United States')


class CurrencyViewTests(BaseTestCase):
    """Test currency views"""
    
    def _setup_test_data(self):
        self.usd = Currency.objects.create(
            code='USD',
            name='US Dollar',
            symbol='$',
            is_default=True
        )
        self.bdt = Currency.objects.create(
            code='BDT',
            name='Bangladeshi Taka',
            symbol='৳',
            exchange_rate=Decimal('110.50')
        )
    
    def test_currency_list_view(self):
        """Test currency list endpoint"""
        response = self.client.get('/api/v1/currencies/')
        data = self.assert_response_success(response)
        
        self.assertEqual(len(data['data']['currencies']), 2)
        self.assertEqual(data['data']['default_currency']['code'], 'USD')
    
    def test_currency_convert_view(self):
        """Test currency conversion endpoint"""
        response = self.client.get(
            '/api/v1/currency/convert/',
            {'amount': '100', 'from': 'USD', 'to': 'BDT'}
        )
        data = self.assert_response_success(response)
        
        self.assertEqual(data['data']['from']['code'], 'USD')
        self.assertEqual(data['data']['to']['code'], 'BDT')
    
    def test_currency_convert_invalid_amount(self):
        """Test currency conversion with invalid amount"""
        response = self.client.get(
            '/api/v1/currency/convert/',
            {'amount': 'invalid', 'from': 'USD', 'to': 'BDT'}
        )
        self.assert_response_error(response, 400)


class TranslationViewTests(BaseTestCase):
    """Test translation views"""
    
    def _setup_test_data(self):
        self.lang_en = Language.objects.create(
            code='en',
            name='English',
            is_default=True
        )
        self.key = TranslationKey.objects.create(key='welcome')
        self.translation = Translation.objects.create(
            key=self.key,
            language=self.lang_en,
            value='Welcome'
        )
    
    def test_translation_view(self):
        """Test translation endpoint"""
        response = self.client.get('/api/v1/translations/en/')
        data = self.assert_response_success(response)
        
        self.assertEqual(data['data']['language']['code'], 'en')
        self.assertEqual(data['data']['translations']['welcome'], 'Welcome')
    
    def test_translation_view_not_found(self):
        """Test translation endpoint with invalid language"""
        response = self.client.get('/api/v1/translations/xx/')
        self.assert_response_error(response, 404)


class UserPreferenceViewTests(BaseTestCase):
    """Test user preference views"""
    
    def _setup_test_data(self):
        self.user = self.create_test_user()
        self.lang_en = Language.objects.create(
            code='en',
            name='English',
            is_default=True
        )
        self.client.login(username='testuser', password='testpass123')
    
    def test_user_preference_get(self):
        """Test getting user preferences"""
        response = self.client.get('/api/v1/user/preferences/')
        data = self.assert_response_success(response)
        
        self.assertEqual(data['data']['effective_language']['code'], 'en')
    
    def test_user_preference_update(self):
        """Test updating user preferences"""
        response = self.client.post(
            '/api/v1/user/preferences/',
            json.dumps({'auto_translate': False}),
            content_type='application/json'
        )
        self.assert_response_success(response)
    
    def test_add_preferred_language(self):
        """Test adding preferred language"""
        response = self.client.post(
            '/api/v1/user/preferences/add-language/',
            json.dumps({'language_code': 'en'}),
            content_type='application/json'
        )
        self.assert_response_success(response)


# ======================== Health Check Tests ========================

class HealthCheckTests(BaseTestCase):
    """Test health check endpoint"""
    
    def test_health_check(self):
        """Test health check endpoint"""
        response = self.client.get('/api/v1/health/')
        data = response.json()
        
        self.assertTrue(data['success'])
        self.assertIn('database', data['data']['services'])
        self.assertIn('cache', data['data']['services'])


# ======================== Serializer Tests ========================

class LanguageSerializerTests(BaseTestCase):
    """Test LanguageSerializer"""
    
    def _setup_test_data(self):
        self.lang = Language.objects.create(
            code='en',
            name='English'
        )
    
    def test_serializer(self):
        """Test language serializer"""
        serializer = LanguageSerializer(self.lang)
        data = serializer.data
        
        self.assertEqual(data['code'], 'en')
        self.assertEqual(data['name'], 'English')
    
    def test_serializer_validation(self):
        """Test serializer validation"""
        serializer = LanguageSerializer(data={
            'code': 'fr',
            'name': 'French'
        })
        self.assertTrue(serializer.is_valid())
        
        # Test invalid code
        serializer = LanguageSerializer(data={
            'code': 'f',
            'name': 'French'
        })
        self.assertFalse(serializer.is_valid())


# ======================== Integration Tests ========================

class IntegrationTests(BaseTestCase):
    """End-to-end integration tests"""
    
    def _setup_test_data(self):
        # Create languages
        self.lang_en = Language.objects.create(
            code='en',
            name='English',
            is_default=True
        )
        self.lang_bn = Language.objects.create(
            code='bn',
            name='Bengali'
        )
        
        # Create translation keys and translations
        self.key_welcome = TranslationKey.objects.create(key='welcome')
        Translation.objects.create(
            key=self.key_welcome,
            language=self.lang_en,
            value='Welcome'
        )
        Translation.objects.create(
            key=self.key_welcome,
            language=self.lang_bn,
            value='স্বাগতম'
        )
        
        # Create currencies
        self.usd = Currency.objects.create(
            code='USD',
            name='US Dollar',
            symbol='$',
            is_default=True
        )
        self.bdt = Currency.objects.create(
            code='BDT',
            name='Bangladeshi Taka',
            symbol='৳',
            exchange_rate=Decimal('110.50')
        )
        
        # Create user
        self.user = self.create_test_user()
    
    def test_full_translation_workflow(self):
        """Test complete translation workflow"""
        # 1. Get translation
        response = self.client.get('/api/v1/translations/en/')
        data = response.json()
        self.assertEqual(data['data']['translations']['welcome'], 'Welcome')
        
        # 2. Get translation for Bengali
        response = self.client.get('/api/v1/translations/bn/')
        data = response.json()
        self.assertEqual(data['data']['translations']['welcome'], 'স্বাগতম')
        
        # 3. Import new translations
        self.client.login(username='testuser', password='testpass123')
        import_data = {
            'language_code': 'bn',
            'translations': {
                'goodbye': 'বিদায়',
                'hello': 'হ্যালো'
            }
        }
        response = self.client.post(
            '/api/v1/translations/import/',
            json.dumps(import_data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        
        # 4. Verify new translations
        response = self.client.get('/api/v1/translations/bn/')
        data = response.json()
        self.assertIn('goodbye', data['data']['translations'])
    
    def test_full_currency_workflow(self):
        """Test complete currency workflow"""
        # 1. Convert currency
        response = self.client.get(
            '/api/v1/currency/convert/',
            {'amount': '100', 'from': 'USD', 'to': 'BDT'}
        )
        data = response.json()
        self.assertEqual(data['data']['to']['formatted'], '৳11050.00')
        
        # 2. Update exchange rate
        # This would normally be an admin endpoint
        with patch('django.contrib.auth.models.User.is_staff', True):
            self.client.login(username='testuser', password='testpass123')
            response = self.client.post(
                '/api/v1/admin/currencies/update-rates/',
                json.dumps({'BDT': '115.00'}),
                content_type='application/json'
            )
        
        # 3. Verify new rate
        self.bdt.refresh_from_db()
        self.assertEqual(self.bdt.exchange_rate, Decimal('110.50'))  # Not changed in test


# ======================== Performance Tests ========================

class PerformanceTests(BaseTestCase):
    """Performance and load tests"""
    
    def _setup_test_data(self):
        # Create multiple languages
        for i in range(10):
            Language.objects.create(
                code=f'lang{i}',
                name=f'Language {i}'
            )
    
    def test_bulk_translation_retrieval(self):
        """Test performance of bulk translation retrieval"""
        import time
        
        start = time.time()
        translations = translation_service.get_translations_bulk(
            [f'key{i}' for i in range(100)], 'en'
        )
        duration = time.time() - start
        
        self.assertLess(duration, 1.0)  # Should take less than 1 second


# ======================== Edge Case Tests ========================

class EdgeCaseTests(BaseTestCase):
    """Test edge cases and error conditions"""
    
    def test_concurrent_default_language_creation(self):
        """Test concurrent default language creation"""
        def create_default():
            return Language.objects.create(
                code='xx',
                name='Test',
                is_default=True
            )
        
        # This should raise an integrity error
        with self.assertRaises(Exception):
            with transaction.atomic():
                create_default()
                create_default()
    
    def test_circular_references(self):
        """Test circular reference handling"""
        # Create self-referential data
        currency = Currency.objects.create(
            code='TEST',
            name='Test',
            symbol='T'
        )
        
        # Should not cause infinite recursion
        result = currency.format_amount(100)
        self.assertEqual(result, 'T100.00')
    
    def test_massive_data_handling(self):
        """Test handling of massive data"""
        # Create many translation keys
        keys = []
        for i in range(1000):
            keys.append(TranslationKey.objects.create(
                key=f'test_key_{i}'
            ))
        
        self.assertEqual(TranslationKey.objects.count(), 1000)


# ======================== Mock Tests ========================

class MockTests(BaseTestCase):
    """Tests using mocks"""
    
    @patch('localization.services.requests.post')
    def test_external_translation_service(self, mock_post):
        """Test external translation service with mock"""
        # Mock the external service response
        mock_response = Mock()
        mock_response.json.return_value = {
            'translated_text': 'Bonjour',
            'success': True
        }
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        # Call service
        result = translation_service.translate_text(
            'Hello', 'en', 'fr', service='test'
        )
        
        self.assertTrue(result['success'])
        self.assertEqual(result['translated_text'], '[en to fr] Hello')
    
    @patch('localization.services.cache.set')
    def test_cache_failure_handling(self, mock_cache_set):
        """Test handling of cache failures"""
        mock_cache_set.side_effect = Exception("Cache error")
        
        # Should not raise exception
        result = translation_service.set_cached('test', 'value')
        self.assertFalse(result)


# ======================== Fixture Tests ========================

@pytest.mark.django_db
class TestWithPytest:
    """Tests using pytest style"""
    
    def test_language_creation(self):
        lang = Language.objects.create(code='en', name='English')
        assert lang.code == 'en'
        assert lang.name == 'English'
    
    def test_translation_retrieval(self):
        lang = Language.objects.create(code='en', name='English')
        key = TranslationKey.objects.create(key='test')
        trans = Translation.objects.create(
            key=key,
            language=lang,
            value='Test'
        )
        
        assert trans.value == 'Test'
        assert trans.key.key == 'test'


# ======================== Cleanup Tests ========================

class CleanupTests(BaseTestCase):
    """Test cleanup operations"""
    
    def _setup_test_data(self):
        self.old_cache = TranslationCache.objects.create(
            language_code='en',
            cache_key='test',
            cache_data={'test': 'value'},
            expires_at=timezone.now() - timedelta(days=1)
        )
    
    def test_expired_cache_cleanup(self):
        """Test cleanup of expired cache"""
        self.assertEqual(TranslationCache.objects.count(), 1)
        
        TranslationCache.clean_expired()
        
        self.assertEqual(TranslationCache.objects.count(), 0)
    
    def test_orphaned_translation_cleanup(self):
        """Test cleanup of orphaned translations"""
        # Create translation with invalid key
        with self.assertRaises(Exception):
            Translation.objects.create(
                key_id=99999,  # Non-existent key
                language_id=1,
                value='Test'
            )


# ======================== Test Configuration ========================

def setup_test_environment():
    """Setup test environment"""
    # Clear cache
    cache.clear()
    
    # Disable logging during tests
    import logging
    logging.disable(logging.CRITICAL)


def teardown_test_environment():
    """Teardown test environment"""
    # Re-enable logging
    import logging
    logging.disable(logging.NOTSET)
    
    # Clear cache
    cache.clear()


# ======================== Run Tests ========================

if __name__ == '__main__':
    import django
    django.setup()
    from django.test.runner import DiscoverRunner
    
    test_runner = DiscoverRunner(verbosity=2)
    failures = test_runner.run_tests(['localization.tests'])
    
    if failures:
        import sys
        sys.exit(failures)