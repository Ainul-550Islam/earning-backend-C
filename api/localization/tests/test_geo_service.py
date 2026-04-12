# tests/test_geo_service.py
from django.test import TestCase


class GeoServiceTest(TestCase):
    def test_geoip_service_empty_result(self):
        from localization.services.geo.GeoIPService import GeoIPService
        service = GeoIPService()
        # Using a local/private IP
        result = service._empty_result('127.0.0.1')
        self.assertEqual(result['ip'], '127.0.0.1')
        self.assertEqual(result['country_code'], '')

    def test_city_service_autocomplete_empty(self):
        from localization.services.geo.CityService import CityService
        service = CityService()
        results = service.autocomplete('XYZ_NONEXISTENT_CITY_12345')
        self.assertIsInstance(results, list)

    def test_timezone_service_utc_offset(self):
        from localization.services.geo.TimezoneService import TimezoneService
        service = TimezoneService()
        offset = service.get_utc_offset('Asia/Dhaka')
        self.assertIsNotNone(offset)
        self.assertIn('UTC', offset)
        self.assertIn('+06', offset)
