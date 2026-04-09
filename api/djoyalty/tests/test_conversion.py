# api/djoyalty/tests/test_conversion.py
from decimal import Decimal
from django.test import TestCase


class PointsConversionServiceTest(TestCase):

    def test_points_to_currency_default_rate(self):
        from djoyalty.services.points.PointsConversionService import PointsConversionService
        value = PointsConversionService.points_to_currency(Decimal('100'))
        self.assertGreater(value, Decimal('0'))

    def test_points_to_currency_custom_rate(self):
        from djoyalty.services.points.PointsConversionService import PointsConversionService
        value = PointsConversionService.points_to_currency(Decimal('100'), point_value=Decimal('0.05'))
        self.assertEqual(value, Decimal('5.00'))

    def test_currency_to_points_default_rate(self):
        from djoyalty.services.points.PointsConversionService import PointsConversionService
        points = PointsConversionService.currency_to_points(Decimal('100'))
        self.assertGreater(points, Decimal('0'))

    def test_currency_to_points_custom_rate(self):
        from djoyalty.services.points.PointsConversionService import PointsConversionService
        points = PointsConversionService.currency_to_points(Decimal('100'), earn_rate=Decimal('2'))
        self.assertEqual(points, Decimal('200.00'))

    def test_zero_points_to_currency(self):
        from djoyalty.services.points.PointsConversionService import PointsConversionService
        value = PointsConversionService.points_to_currency(Decimal('0'))
        self.assertEqual(value, Decimal('0'))

    def test_decimal_precision(self):
        from djoyalty.services.points.PointsConversionService import PointsConversionService
        value = PointsConversionService.points_to_currency(Decimal('333'), point_value=Decimal('0.01'))
        self.assertEqual(value, Decimal('3.33'))


class UtilsConversionTest(TestCase):

    def test_calculate_points_to_earn(self):
        from djoyalty.utils import calculate_points_to_earn
        points = calculate_points_to_earn(Decimal('100'), Decimal('1'), Decimal('1'))
        self.assertEqual(points, Decimal('100.00'))

    def test_calculate_points_with_multiplier(self):
        from djoyalty.utils import calculate_points_to_earn
        points = calculate_points_to_earn(Decimal('100'), Decimal('1'), Decimal('2'))
        self.assertEqual(points, Decimal('200.00'))

    def test_calculate_points_value(self):
        from djoyalty.utils import calculate_points_value
        value = calculate_points_value(Decimal('100'), Decimal('0.01'))
        self.assertEqual(value, Decimal('1.00'))

    def test_safe_decimal_none(self):
        from djoyalty.utils import safe_decimal
        result = safe_decimal(None)
        self.assertEqual(result, Decimal('0'))

    def test_safe_decimal_invalid(self):
        from djoyalty.utils import safe_decimal
        result = safe_decimal('not_a_number')
        self.assertEqual(result, Decimal('0'))

    def test_safe_decimal_valid(self):
        from djoyalty.utils import safe_decimal
        result = safe_decimal('123.45')
        self.assertEqual(result, Decimal('123.45'))
