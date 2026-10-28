"""
tests/test_throttling.py

Tests for offerwall throttle classes:
  - OfferListThrottle      (100/hour)
  - OfferDetailThrottle    (200/hour)
  - OfferClickThrottle     (30/hour)
  - ConversionThrottle     (10/hour)
  - WebhookThrottle        (1000/hour)
  - AnalyticsThrottle      (50/hour)
  - AdminThrottle          (500/hour)
  - PublicThrottle         (50/hour  anon)

Run: python manage.py test api.offerwall.tests.test_throttling
"""
from django.test import TestCase
from rest_framework.throttling import ScopedRateThrottle, AnonRateThrottle


class ThrottleClassAttributeTest(TestCase):
    """Verify scope names and base class for every throttle."""

    def _check(self, cls_path, scope, base):
        module_path, cls_name = cls_path.rsplit('.', 1)
        import importlib
        mod = importlib.import_module(module_path)
        cls = getattr(mod, cls_name)
        self.assertEqual(cls.scope, scope, f'{cls_name}.scope should be {scope!r}')
        self.assertTrue(issubclass(cls, base),
                        f'{cls_name} should subclass {base.__name__}')

    def test_offer_list_throttle(self):
        from api.offerwall.throttling import OfferListThrottle
        self.assertEqual(OfferListThrottle.scope, 'offer_list')
        self.assertTrue(issubclass(OfferListThrottle, ScopedRateThrottle))

    def test_offer_detail_throttle(self):
        from api.offerwall.throttling import OfferDetailThrottle
        self.assertEqual(OfferDetailThrottle.scope, 'offer_detail')
        self.assertTrue(issubclass(OfferDetailThrottle, ScopedRateThrottle))

    def test_offer_click_throttle(self):
        from api.offerwall.throttling import OfferClickThrottle
        self.assertEqual(OfferClickThrottle.scope, 'offer_click')
        self.assertTrue(issubclass(OfferClickThrottle, ScopedRateThrottle))

    def test_conversion_throttle(self):
        from api.offerwall.throttling import ConversionThrottle
        self.assertEqual(ConversionThrottle.scope, 'conversion')
        self.assertTrue(issubclass(ConversionThrottle, ScopedRateThrottle))

    def test_webhook_throttle(self):
        from api.offerwall.throttling import WebhookThrottle
        self.assertEqual(WebhookThrottle.scope, 'webhook')
        self.assertTrue(issubclass(WebhookThrottle, ScopedRateThrottle))

    def test_analytics_throttle(self):
        from api.offerwall.throttling import AnalyticsThrottle
        self.assertEqual(AnalyticsThrottle.scope, 'analytics')
        self.assertTrue(issubclass(AnalyticsThrottle, ScopedRateThrottle))

    def test_admin_throttle(self):
        from api.offerwall.throttling import AdminThrottle
        self.assertEqual(AdminThrottle.scope, 'admin')
        self.assertTrue(issubclass(AdminThrottle, ScopedRateThrottle))

    def test_public_throttle(self):
        from api.offerwall.throttling import PublicThrottle
        self.assertEqual(PublicThrottle.scope, 'public')
        self.assertTrue(issubclass(PublicThrottle, AnonRateThrottle))


class ThrottleWiredToViewSetsTest(TestCase):
    """Verify ViewSets have throttle_classes set."""

    def test_offer_viewset_has_throttles(self):
        from api.offerwall.views import OfferViewSet
        self.assertTrue(len(OfferViewSet.throttle_classes) > 0)

    def test_conversion_viewset_has_throttles(self):
        from api.offerwall.views import OfferConversionViewSet
        self.assertTrue(len(OfferConversionViewSet.throttle_classes) > 0)

    def test_category_viewset_has_throttles(self):
        from api.offerwall.views import OfferCategoryViewSet
        self.assertTrue(len(OfferCategoryViewSet.throttle_classes) > 0)

    def test_provider_viewset_has_throttles(self):
        from api.offerwall.views import OfferProviderViewSet
        self.assertTrue(len(OfferProviderViewSet.throttle_classes) > 0)

    def test_click_viewset_has_throttles(self):
        from api.offerwall.views import OfferClickViewSet
        self.assertTrue(len(OfferClickViewSet.throttle_classes) > 0)

    def test_wall_viewset_has_throttles(self):
        from api.offerwall.views import OfferWallViewSet
        self.assertTrue(len(OfferWallViewSet.throttle_classes) > 0)


class ThrottleSettingsConfigTest(TestCase):
    """Verify THROTTLE_RATES are defined in settings_offerwall."""

    def test_offer_list_rate_defined(self):
        from api.offerwall.settings_offerwall import THROTTLE_RATES
        self.assertIn('offer_list', THROTTLE_RATES)

    def test_offer_click_rate_defined(self):
        from api.offerwall.settings_offerwall import THROTTLE_RATES
        self.assertIn('offer_click', THROTTLE_RATES)

    def test_conversion_rate_defined(self):
        from api.offerwall.settings_offerwall import THROTTLE_RATES
        self.assertIn('conversion', THROTTLE_RATES)

    def test_webhook_rate_defined(self):
        from api.offerwall.settings_offerwall import THROTTLE_RATES
        self.assertIn('webhook', THROTTLE_RATES)

    def test_admin_rate_defined(self):
        from api.offerwall.settings_offerwall import THROTTLE_RATES
        self.assertIn('admin', THROTTLE_RATES)

    def test_public_rate_defined(self):
        from api.offerwall.settings_offerwall import THROTTLE_RATES
        self.assertIn('public', THROTTLE_RATES)

    def test_all_8_rates_present(self):
        from api.offerwall.settings_offerwall import THROTTLE_RATES
        expected = {'offer_list', 'offer_detail', 'offer_click',
                    'conversion', 'webhook', 'analytics', 'admin', 'public'}
        self.assertEqual(set(THROTTLE_RATES.keys()), expected)

    def test_rates_use_per_hour(self):
        from api.offerwall.settings_offerwall import THROTTLE_RATES
        for scope, rate in THROTTLE_RATES.items():
            self.assertIn('/hour', rate,
                          f'Scope {scope!r} rate {rate!r} should be per hour')
