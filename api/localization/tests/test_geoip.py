# tests/test_geoip.py
from django.test import TestCase


class GeoIPServiceTest(TestCase):
    def test_service_import(self):
        from localization.services.geo.GeoIPService import GeoIPService
        service = GeoIPService()
        self.assertIsNotNone(service)

    def test_empty_result_structure(self):
        from localization.services.geo.GeoIPService import GeoIPService
        result = GeoIPService()._empty_result('1.2.3.4')
        self.assertEqual(result['ip'], '1.2.3.4')
        self.assertEqual(result['country_code'], '')
        self.assertFalse(result['is_vpn'])
        self.assertFalse(result['is_proxy'])
        self.assertIsNone(result['latitude'])

    def test_lookup_local_ip_graceful(self):
        from localization.services.geo.GeoIPService import GeoIPService
        result = GeoIPService().lookup('127.0.0.1')
        self.assertIsInstance(result, dict)
        self.assertIn('ip', result)

    def test_lookup_invalid_ip_graceful(self):
        from localization.services.geo.GeoIPService import GeoIPService
        result = GeoIPService().lookup('not.an.ip')
        self.assertIsInstance(result, dict)

    def test_get_language_for_ip_unknown(self):
        from localization.services.geo.GeoIPService import GeoIPService
        result = GeoIPService().get_language_for_ip('192.168.1.1')
        self.assertIsNone(result)
