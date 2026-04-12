from django.test import TestCase
from .factories import SmartLinkFactory, ClickFactory, SmartLinkDailyStatFactory


class ClickSerializerTest(TestCase):
    def test_click_serializer_read_only(self):
        from ..serializers.ClickSerializer import ClickSerializer
        click = ClickFactory()
        s = ClickSerializer(click)
        data = s.data
        self.assertIn('country', data)
        self.assertIn('device_type', data)
        self.assertIn('is_unique', data)
        self.assertIn('fraud_score', data)

    def test_stat_serializer(self):
        from ..serializers.SmartLinkStatSerializer import SmartLinkStatSerializer
        sl = SmartLinkFactory()
        stat = SmartLinkDailyStatFactory(
            smartlink=sl, clicks=500, unique_clicks=400,
            conversions=25, revenue=125.50
        )
        s = SmartLinkStatSerializer(stat)
        data = s.data
        self.assertEqual(data['clicks'], 500)
        self.assertEqual(data['conversions'], 25)

    def test_insight_serializer_fields(self):
        from ..serializers.InsightSerializer import InsightSerializer
        s = InsightSerializer(data={
            'smartlink_id': 1, 'period_days': 30,
            'clicks': 1000, 'unique_clicks': 800,
            'conversions': 50, 'revenue': '250.0000',
            'epc': 0.25, 'conversion_rate': 5.0,
            'quality_rate': 95.0, 'bot_clicks': 10,
            'fraud_clicks': 5,
        })
        self.assertTrue(s.is_valid(), s.errors)
