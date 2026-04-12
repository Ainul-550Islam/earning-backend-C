from django.test import TestCase
from unittest.mock import patch, MagicMock
from .factories import SmartLinkFactory, UserFactory


class SmartLinkSignalsTest(TestCase):
    @patch('smartlink.tasks.cache_warmup_tasks.invalidate_smartlink_cache')
    def test_save_triggers_cache_invalidation(self, mock_task):
        mock_task.delay = MagicMock()
        sl = SmartLinkFactory()
        sl.name = 'Updated'
        sl.save()
        mock_task.delay.assert_called()

    def test_delete_invalidates_cache(self):
        sl = SmartLinkFactory()
        slug = sl.slug
        with patch('smartlink.services.core.SmartLinkCacheService.SmartLinkCacheService.invalidate_smartlink') as mock_inv:
            sl.delete()
            mock_inv.assert_called_with(slug)


class SerializerTest(TestCase):
    def test_smartlink_serializer_valid(self):
        from ..serializers.SmartLinkSerializer import SmartLinkSerializer
        sl = SmartLinkFactory()
        s = SmartLinkSerializer(sl)
        data = s.data
        self.assertEqual(data['slug'], sl.slug)
        self.assertIn('total_clicks', data)
        self.assertIn('epc', data)
        self.assertIn('full_url', data)

    def test_smartlink_serializer_invalid_slug(self):
        from ..serializers.SmartLinkSerializer import SmartLinkSerializer
        s = SmartLinkSerializer(data={'name': 'Test', 'slug': 'INVALID SLUG WITH SPACES'})
        self.assertFalse(s.is_valid())
        self.assertIn('slug', s.errors)

    def test_geo_targeting_serializer_validates_country_codes(self):
        from ..serializers.GeoTargetingSerializer import GeoTargetingSerializer
        from ..models import TargetingRule
        sl = SmartLinkFactory()
        rule = TargetingRule.objects.create(smartlink=sl)
        s = GeoTargetingSerializer(data={
            'mode': 'whitelist',
            'countries': ['US', 'GB', 'BD'],
            'regions': [], 'cities': [],
        })
        self.assertTrue(s.is_valid(), s.errors)

    def test_geo_targeting_rejects_invalid_country_code(self):
        from ..serializers.GeoTargetingSerializer import GeoTargetingSerializer
        s = GeoTargetingSerializer(data={
            'mode': 'whitelist',
            'countries': ['INVALID'],
            'regions': [], 'cities': [],
        })
        self.assertFalse(s.is_valid())

    def test_offer_pool_entry_validates_weight(self):
        from ..serializers.OfferPoolEntrySerializer import OfferPoolEntrySerializer
        s = OfferPoolEntrySerializer(data={'offer': 1, 'weight': 0})
        self.assertFalse(s.is_valid())
        self.assertIn('weight', s.errors)

    def test_time_targeting_validates_start_before_end(self):
        from ..serializers.TimeTargetingSerializer import TimeTargetingSerializer
        s = TimeTargetingSerializer(data={
            'days_of_week': [0, 1, 2],
            'start_hour': 18,
            'end_hour': 9,
            'timezone_name': 'UTC',
        })
        self.assertFalse(s.is_valid())
