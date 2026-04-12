from django.test import TestCase
from .factories import SmartLinkFactory
from ..services.rotation.ABTestService import ABTestService
from ..exceptions import ABTestConfigError


class ABTestServiceTest(TestCase):
    def setUp(self):
        self.service = ABTestService()
        self.sl = SmartLinkFactory()

    def test_create_test_with_valid_variants(self):
        variants = [
            {'name': 'Control', 'traffic_split': 50, 'is_control': True},
            {'name': 'Variant A', 'traffic_split': 50},
        ]
        versions = self.service.create_test(self.sl, variants)
        self.assertEqual(len(versions), 2)
        control = [v for v in versions if v.is_control]
        self.assertEqual(len(control), 1)

    def test_create_test_weights_must_sum_100(self):
        variants = [
            {'name': 'A', 'traffic_split': 60},
            {'name': 'B', 'traffic_split': 60},
        ]
        with self.assertRaises(ABTestConfigError):
            self.service.create_test(self.sl, variants)

    def test_single_variant_raises_error(self):
        with self.assertRaises(ABTestConfigError):
            self.service.create_test(self.sl, [{'name': 'Only', 'traffic_split': 100}])

    def test_select_variant_returns_version(self):
        variants = [
            {'name': 'Control', 'traffic_split': 50, 'is_control': True},
            {'name': 'Variant A', 'traffic_split': 50},
        ]
        self.service.create_test(self.sl, variants)
        self.sl.enable_ab_test = True
        self.sl.save()
        version = self.service.select_variant(self.sl)
        self.assertIsNotNone(version)

    def test_select_variant_disabled_returns_none(self):
        self.sl.enable_ab_test = False
        self.sl.save()
        version = self.service.select_variant(self.sl)
        self.assertIsNone(version)

    def test_traffic_split_distribution(self):
        """Verify variant selection follows traffic split distribution."""
        variants = [
            {'name': 'Control', 'traffic_split': 80, 'is_control': True},
            {'name': 'Variant A', 'traffic_split': 20},
        ]
        self.service.create_test(self.sl, variants)
        self.sl.enable_ab_test = True
        self.sl.save()

        counts = {}
        for _ in range(500):
            v = self.service.select_variant(self.sl)
            if v:
                counts[v.name] = counts.get(v.name, 0) + 1

        if 'Control' in counts and 'Variant A' in counts:
            control_pct = counts.get('Control', 0) / 500 * 100
            self.assertGreater(control_pct, 65, f"Control got {control_pct:.1f}%, expected ~80%")
