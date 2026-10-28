"""
Tests for core services:
  SlugGeneratorService, MultiCurrencyService,
  DeviceFingerprintService, TimeTargetingService,
  ISPTargetingService, OSTargetingService, LanguageTargetingService.
"""
from unittest.mock import patch, MagicMock
from django.test import TestCase
from .factories import SmartLinkFactory, UserFactory


# ─── SlugGeneratorService ─────────────────────────────────────────────────────

class SlugGeneratorServiceTest(TestCase):
    def setUp(self):
        from ..services.core.SlugGeneratorService import SlugGeneratorService
        self.svc = SlugGeneratorService()

    def test_generate_unique_returns_string(self):
        with patch('django.core.cache.cache.add', return_value=True):
            slug = self.svc.generate_unique(length=8)
        self.assertIsInstance(slug, str)
        self.assertEqual(len(slug), 8)

    def test_generate_unique_avoids_existing_slugs(self):
        existing = SmartLinkFactory(slug='abcdefgh')
        call_count = {'n': 0}
        original_random = self.svc._random_slug

        def fake_random(length):
            call_count['n'] += 1
            if call_count['n'] == 1:
                return 'abcdefgh'  # collide first
            return 'newslugx'      # succeed second

        with patch.object(self.svc, '_random_slug', side_effect=fake_random):
            with patch('django.core.cache.cache.add', return_value=True):
                slug = self.svc.generate_unique(length=8)

        self.assertEqual(slug, 'newslugx')
        self.assertEqual(call_count['n'], 2)

    def test_generate_unique_raises_on_max_attempts(self):
        from ..exceptions import SlugConflict
        with patch('django.core.cache.cache.add', return_value=False):
            with self.assertRaises(SlugConflict):
                self.svc.generate_unique(max_attempts=3)

    def test_generate_custom_returns_lowercase_slug(self):
        with patch('django.core.cache.cache.add', return_value=True):
            slug = self.svc.generate_custom('MyCustomSlug')
        self.assertEqual(slug, 'mycustomslug')

    def test_generate_custom_raises_when_slug_taken(self):
        from ..exceptions import SlugConflict
        SmartLinkFactory(slug='taken')
        with self.assertRaises(SlugConflict):
            self.svc.generate_custom('taken')

    def test_generate_custom_raises_on_reserved_word(self):
        from ..exceptions import SlugReserved
        from ..constants import SLUG_RESERVED_WORDS
        reserved = next(iter(SLUG_RESERVED_WORDS))
        with self.assertRaises(SlugReserved):
            self.svc.generate_custom(reserved)

    def test_generate_from_name_derives_slug(self):
        with patch('django.core.cache.cache.add', return_value=True):
            slug = self.svc.generate_from_name('My Campaign 2024')
        self.assertIn('my', slug)

    def test_generate_from_name_falls_back_to_random_when_taken(self):
        SmartLinkFactory(slug='my-camp')
        with patch('django.core.cache.cache.add', return_value=True):
            with patch.object(self.svc, '_random_slug', return_value='rand1234'):
                slug = self.svc.generate_from_name('my camp')
        self.assertEqual(slug, 'rand1234')

    def test_is_available_true_for_new_slug(self):
        result = self.svc.is_available('brandnewslug999')
        self.assertTrue(result)

    def test_is_available_false_for_existing_slug(self):
        SmartLinkFactory(slug='existingslug')
        result = self.svc.is_available('existingslug')
        self.assertFalse(result)

    def test_is_available_false_for_reserved_word(self):
        from ..constants import SLUG_RESERVED_WORDS
        reserved = next(iter(SLUG_RESERVED_WORDS))
        result = self.svc.is_available(reserved)
        self.assertFalse(result)

    def test_generate_batch_returns_correct_count(self):
        with patch('django.core.cache.cache.add', return_value=True):
            slugs = self.svc.generate_batch(5)
        self.assertEqual(len(slugs), 5)
        self.assertEqual(len(set(slugs)), 5)  # all unique

    def test_random_slug_correct_length_and_chars(self):
        from ..constants import SLUG_ALLOWED_CHARS
        slug = self.svc._random_slug(10)
        self.assertEqual(len(slug), 10)
        for ch in slug:
            self.assertIn(ch, SLUG_ALLOWED_CHARS)


# ─── MultiCurrencyService ─────────────────────────────────────────────────────

class MultiCurrencyServiceTest(TestCase):
    def setUp(self):
        from ..services.currency.MultiCurrencyService import MultiCurrencyService
        self.svc = MultiCurrencyService()

    def test_to_usd_usd_passthrough(self):
        result = self.svc.to_usd(10.0, 'USD')
        self.assertAlmostEqual(result, 10.0, places=4)

    def test_to_usd_eur_converts_correctly(self):
        # EUR → USD: rate = 1.08
        result = self.svc.to_usd(100.0, 'EUR')
        self.assertAlmostEqual(result, 108.0, places=1)

    def test_to_usd_bdt_converts_correctly(self):
        result = self.svc.to_usd(1000.0, 'BDT')
        self.assertAlmostEqual(result, 9.1, places=0)

    def test_from_usd_usd_passthrough(self):
        result = self.svc.from_usd(50.0, 'USD')
        self.assertAlmostEqual(result, 50.0, places=4)

    def test_from_usd_eur_converts_correctly(self):
        result = self.svc.from_usd(108.0, 'EUR')
        self.assertAlmostEqual(result, 100.0, places=0)

    def test_from_usd_zero_rate_returns_zero(self):
        with patch.object(self.svc, '_get_rates', return_value={'TEST': 0}):
            result = self.svc.from_usd(100.0, 'TEST')
        self.assertEqual(result, 0.0)

    def test_convert_between_currencies(self):
        # EUR → GBP via USD
        result = self.svc.convert(100.0, 'EUR', 'GBP')
        self.assertGreater(result, 0)

    def test_convert_same_currency_round_trip(self):
        usd_to_eur = self.svc.convert(100.0, 'USD', 'EUR')
        back_to_usd = self.svc.convert(usd_to_eur, 'EUR', 'USD')
        self.assertAlmostEqual(back_to_usd, 100.0, places=1)

    def test_format_currency_usd(self):
        result = self.svc.format_currency(10.5, 'USD')
        self.assertIn('$', result)
        self.assertIn('10.5', result)

    def test_format_currency_bdt(self):
        result = self.svc.format_currency(500.0, 'BDT')
        self.assertIn('৳', result)

    def test_format_currency_unknown_currency_uses_code(self):
        result = self.svc.format_currency(10.0, 'XYZ')
        self.assertIn('XYZ', result)

    def test_get_supported_currencies_is_sorted_list(self):
        currencies = self.svc.get_supported_currencies()
        self.assertIsInstance(currencies, list)
        self.assertIn('USD', currencies)
        self.assertIn('EUR', currencies)
        self.assertIn('BDT', currencies)
        self.assertEqual(currencies, sorted(currencies))

    def test_uses_fallback_rates_when_cache_empty(self):
        with patch('django.core.cache.cache.get', return_value=None):
            result = self.svc.to_usd(1.0, 'EUR')
        self.assertAlmostEqual(result, 1.08, places=2)

    def test_uses_cached_rates_when_available(self):
        custom_rates = {'EUR': 2.0}
        with patch('django.core.cache.cache.get', return_value=custom_rates):
            result = self.svc.to_usd(1.0, 'EUR')
        self.assertAlmostEqual(result, 2.0, places=4)

    def test_unknown_currency_defaults_to_rate_1(self):
        result = self.svc.to_usd(50.0, 'ZZZ')
        self.assertAlmostEqual(result, 50.0, places=4)


# ─── DeviceFingerprintService ─────────────────────────────────────────────────

class DeviceFingerprintServiceTest(TestCase):
    def setUp(self):
        from ..services.fingerprint.DeviceFingerprintService import DeviceFingerprintService
        self.svc = DeviceFingerprintService()
        self.base_context = {
            'ip': '192.168.1.100',
            'user_agent': 'Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36',
            'accept_language': 'en-US,en;q=0.9',
            'accept': 'text/html,application/xhtml+xml',
        }

    def test_generate_returns_64_char_hex(self):
        fp = self.svc.generate(self.base_context)
        self.assertIsInstance(fp, str)
        self.assertEqual(len(fp), 64)
        int(fp, 16)  # should not raise — valid hex

    def test_same_context_produces_same_fingerprint(self):
        fp1 = self.svc.generate(self.base_context)
        fp2 = self.svc.generate(self.base_context)
        self.assertEqual(fp1, fp2)

    def test_different_user_agents_produce_different_fingerprints(self):
        ctx1 = {**self.base_context, 'user_agent': 'Chrome/120'}
        ctx2 = {**self.base_context, 'user_agent': 'Safari/17'}
        self.assertNotEqual(self.svc.generate(ctx1), self.svc.generate(ctx2))

    def test_different_ips_produce_different_fingerprints(self):
        ctx1 = {**self.base_context, 'ip': '10.0.0.1'}
        ctx2 = {**self.base_context, 'ip': '10.1.0.1'}
        self.assertNotEqual(self.svc.generate(ctx1), self.svc.generate(ctx2))

    def test_same_subnet_same_fingerprint(self):
        """Last octet changes should NOT affect the fingerprint (DHCP resilience)."""
        ctx1 = {**self.base_context, 'ip': '192.168.1.50'}
        ctx2 = {**self.base_context, 'ip': '192.168.1.200'}
        self.assertEqual(self.svc.generate(ctx1), self.svc.generate(ctx2))

    def test_optional_screen_resolution_included(self):
        ctx = {**self.base_context, 'screen_resolution': '1920x1080'}
        fp_with = self.svc.generate(ctx)
        fp_without = self.svc.generate(self.base_context)
        self.assertNotEqual(fp_with, fp_without)

    def test_is_seen_returns_false_when_not_cached(self):
        with patch('django.core.cache.cache.get', return_value=None):
            result = self.svc.is_seen('abc123fingerprint', offer_id=1)
        self.assertFalse(result)

    def test_is_seen_returns_true_when_cached(self):
        with patch('django.core.cache.cache.get', return_value={'click_id': 99}):
            result = self.svc.is_seen('abc123fingerprint', offer_id=1)
        self.assertTrue(result)

    def test_mark_seen_sets_cache(self):
        with patch('django.core.cache.cache.set') as mock_set:
            self.svc.mark_seen('fp_abc123', offer_id=1, click_id=999, window_hours=24)
        mock_set.assert_called_once()
        args = mock_set.call_args[0]
        self.assertIn('fp_seen:', args[0])
        self.assertEqual(args[2], 86400)  # 24 * 3600

    def test_detect_emulator_true_for_android_sdk(self):
        ctx = {'user_agent': 'Mozilla/5.0 (Linux; Android 13; Android SDK built for x86)'}
        self.assertTrue(self.svc.detect_emulator(ctx))

    def test_detect_emulator_true_for_genymotion(self):
        ctx = {'user_agent': 'Mozilla/5.0 Genymotion/3.0'}
        self.assertTrue(self.svc.detect_emulator(ctx))

    def test_detect_emulator_false_for_real_device(self):
        ctx = {'user_agent': 'Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36'}
        self.assertFalse(self.svc.detect_emulator(ctx))

    def test_update_device_profile_creates_profile(self):
        fp = 'testfingerprint' * 4
        profile_store = {}

        def fake_get(key, default=None):
            return profile_store.get(key, default)

        def fake_set(key, value, ttl):
            profile_store[key] = value

        with patch('django.core.cache.cache.get', side_effect=fake_get):
            with patch('django.core.cache.cache.set', side_effect=fake_set):
                profile = self.svc.update_device_profile(fp, {
                    'user_agent': 'Chrome/120',
                    'country': 'BD',
                    'device_type': 'mobile',
                })

        self.assertEqual(profile['country'], 'BD')
        self.assertEqual(profile['click_count'], 1)
        self.assertIn('first_seen', profile)


# ─── TimeTargetingService ─────────────────────────────────────────────────────

class TimeTargetingServiceTest(TestCase):
    def setUp(self):
        from ..services.targeting.TimeTargetingService import TimeTargetingService
        self.svc = TimeTargetingService()

    def test_matches_returns_true_when_no_targeting(self):
        result = self.svc.matches(None, day_of_week=2, hour=14)
        self.assertTrue(result)

    def test_matches_delegates_to_model(self):
        mock_targeting = MagicMock()
        mock_targeting.matches.return_value = True
        result = self.svc.matches(mock_targeting, day_of_week=1, hour=10)
        mock_targeting.matches.assert_called_once_with(day_of_week=1, hour=10)
        self.assertTrue(result)

    def test_get_current_day_hour_returns_tuple(self):
        day, hour = self.svc.get_current_day_hour('UTC')
        self.assertIn(day, range(7))
        self.assertIn(hour, range(24))

    def test_get_current_day_hour_invalid_timezone_falls_back(self):
        day, hour = self.svc.get_current_day_hour('Invalid/Timezone')
        self.assertIn(day, range(7))
        self.assertIn(hour, range(24))


# ─── ISPTargetingService ──────────────────────────────────────────────────────

class ISPTargetingServiceTest(TestCase):
    def setUp(self):
        from ..services.targeting.ISPTargetingService import ISPTargetingService
        self.svc = ISPTargetingService()

    def test_matches_returns_true_when_no_targeting(self):
        self.assertTrue(self.svc.matches(None, isp_name='Grameenphone', asn='AS24389'))

    def test_matches_delegates_to_model(self):
        mock_targeting = MagicMock()
        mock_targeting.matches.return_value = False
        result = self.svc.matches(mock_targeting, isp_name='Robi', asn='AS24432')
        mock_targeting.matches.assert_called_once_with(isp_name='Robi', asn='AS24432')
        self.assertFalse(result)


# ─── OSTargetingService ───────────────────────────────────────────────────────

class OSTargetingServiceTest(TestCase):
    def setUp(self):
        from ..services.targeting.OSTargetingService import OSTargetingService
        self.svc = OSTargetingService()

    def test_matches_returns_true_when_no_targeting(self):
        self.assertTrue(self.svc.matches(None, os_type='android'))

    def test_matches_delegates_to_model(self):
        mock_targeting = MagicMock()
        mock_targeting.matches.return_value = True
        result = self.svc.matches(mock_targeting, os_type='ios')
        mock_targeting.matches.assert_called_once_with('ios')
        self.assertTrue(result)


# ─── LanguageTargetingService ─────────────────────────────────────────────────

class LanguageTargetingServiceTest(TestCase):
    def setUp(self):
        from ..services.targeting.LanguageTargetingService import LanguageTargetingService
        self.svc = LanguageTargetingService()

    def test_matches_returns_true_when_no_targeting(self):
        self.assertTrue(self.svc.matches(None, language='en'))

    def test_matches_delegates_to_model(self):
        mock_targeting = MagicMock()
        mock_targeting.matches.return_value = True
        result = self.svc.matches(mock_targeting, language='bn')
        mock_targeting.matches.assert_called_once_with('bn')
        self.assertTrue(result)

    def test_extract_language_returns_primary_code(self):
        with patch('smartlink.utils.parse_accept_language', return_value='en'):
            result = self.svc.extract_language('en-US,en;q=0.9,bn;q=0.8')
        self.assertEqual(result, 'en')

    def test_extract_language_empty_header_returns_empty(self):
        with patch('smartlink.utils.parse_accept_language', return_value=None):
            result = self.svc.extract_language('')
        self.assertEqual(result, '')
