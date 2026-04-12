"""GeoIP Database — manages local MaxMind .mmdb database files."""
import logging, os
from django.conf import settings
logger = logging.getLogger(__name__)

DB_PATHS = {
    'city':    getattr(settings, 'MAXMIND_CITY_DB',   '/var/lib/geoip/GeoLite2-City.mmdb'),
    'country': getattr(settings, 'MAXMIND_COUNTRY_DB', '/var/lib/geoip/GeoLite2-Country.mmdb'),
    'asn':     getattr(settings, 'MAXMIND_ASN_DB',     '/var/lib/geoip/GeoLite2-ASN.mmdb'),
}

class GeoIPDatabase:
    @staticmethod
    def lookup_city(ip_address: str) -> dict:
        db = DB_PATHS.get('city', '')
        if not db or not os.path.exists(db):
            return {}
        try:
            import geoip2.database
            with geoip2.database.Reader(db) as reader:
                r = reader.city(ip_address)
                return {
                    'country_code': r.country.iso_code or '',
                    'city': r.city.name or '',
                    'region': r.subdivisions.most_specific.name or '',
                    'latitude': float(r.location.latitude or 0),
                    'longitude': float(r.location.longitude or 0),
                    'timezone': r.location.time_zone or '',
                }
        except Exception as e:
            logger.debug(f"GeoIP city lookup failed: {e}")
            return {}

    @staticmethod
    def lookup_asn(ip_address: str) -> dict:
        db = DB_PATHS.get('asn', '')
        if not db or not os.path.exists(db):
            return {}
        try:
            import geoip2.database
            with geoip2.database.Reader(db) as reader:
                r = reader.asn(ip_address)
                return {
                    'asn': f"AS{r.autonomous_system_number}",
                    'asn_name': r.autonomous_system_organization or '',
                }
        except Exception as e:
            logger.debug(f"GeoIP ASN lookup failed: {e}")
            return {}

    @staticmethod
    def databases_available() -> dict:
        return {name: os.path.exists(path) for name, path in DB_PATHS.items()}
