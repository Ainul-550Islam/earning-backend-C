from django.test import TestCase
from .factories import (
    SmartLinkFactory, SmartLinkGroupFactory, SmartLinkFallbackFactory,
    TargetingRuleFactory, GeoTargetingFactory, DeviceTargetingFactory,
    OfferPoolFactory, ClickFactory, UserFactory,
)


class SmartLinkModelTest(TestCase):
    def test_smartlink_str(self):
        sl = SmartLinkFactory(slug='testslug', name='Test Link')
        self.assertIn('testslug', str(sl))

    def test_full_url_property(self):
        sl = SmartLinkFactory(slug='mylink')
        self.assertIn('mylink', sl.full_url)
        self.assertTrue(sl.full_url.startswith('http'))

    def test_epc_zero_clicks(self):
        sl = SmartLinkFactory(total_clicks=0, total_revenue=0)
        self.assertEqual(sl.total_clicks, 0)

    def test_increment_clicks_unique(self):
        sl = SmartLinkFactory()
        original_clicks = sl.total_clicks
        sl.increment_clicks(unique=True)
        sl.refresh_from_db()
        self.assertEqual(sl.total_clicks, original_clicks + 1)
        self.assertEqual(sl.total_unique_clicks, 1)

    def test_increment_clicks_not_unique(self):
        sl = SmartLinkFactory()
        sl.increment_clicks(unique=False)
        sl.refresh_from_db()
        self.assertEqual(sl.total_clicks, 1)
        self.assertEqual(sl.total_unique_clicks, 0)

    def test_smartlink_is_active_by_default(self):
        sl = SmartLinkFactory()
        self.assertTrue(sl.is_active)
        self.assertFalse(sl.is_archived)

    def test_smartlink_uuid_unique(self):
        sl1 = SmartLinkFactory()
        sl2 = SmartLinkFactory()
        self.assertNotEqual(sl1.uuid, sl2.uuid)

    def test_smartlink_group_str(self):
        group = SmartLinkGroupFactory(name='My Campaign')
        self.assertIn('My Campaign', str(group))

    def test_smartlink_fallback_str(self):
        fallback = SmartLinkFallbackFactory()
        self.assertIn('Fallback', str(fallback))


class GeoTargetingModelTest(TestCase):
    def test_whitelist_match(self):
        rule = TargetingRuleFactory()
        geo = GeoTargetingFactory(rule=rule, mode='whitelist', countries=['US', 'GB'])
        self.assertTrue(geo.matches(country='US'))
        self.assertFalse(geo.matches(country='DE'))

    def test_blacklist_match(self):
        rule = TargetingRuleFactory()
        geo = GeoTargetingFactory(rule=rule, mode='blacklist', countries=['CN', 'RU'])
        self.assertFalse(geo.matches(country='CN'))
        self.assertTrue(geo.matches(country='US'))

    def test_empty_countries_allows_all(self):
        rule = TargetingRuleFactory()
        geo = GeoTargetingFactory(rule=rule, countries=[])
        self.assertTrue(geo.matches(country='BD'))
        self.assertTrue(geo.matches(country='US'))


class DeviceTargetingModelTest(TestCase):
    def test_mobile_whitelist(self):
        rule = TargetingRuleFactory()
        dev = DeviceTargetingFactory(rule=rule, mode='whitelist', device_types=['mobile'])
        self.assertTrue(dev.matches('mobile'))
        self.assertFalse(dev.matches('desktop'))

    def test_empty_device_types_allows_all(self):
        rule = TargetingRuleFactory()
        dev = DeviceTargetingFactory(rule=rule, device_types=[])
        self.assertTrue(dev.matches('mobile'))
        self.assertTrue(dev.matches('desktop'))


class ClickModelTest(TestCase):
    def test_click_str(self):
        click = ClickFactory()
        self.assertIn(click.smartlink.slug, str(click))

    def test_click_default_flags(self):
        click = ClickFactory()
        self.assertFalse(click.is_fraud)
        self.assertFalse(click.is_bot)
        self.assertFalse(click.is_converted)
        self.assertEqual(click.fraud_score, 0)
