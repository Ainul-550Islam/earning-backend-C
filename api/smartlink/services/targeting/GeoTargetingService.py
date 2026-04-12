import logging

logger = logging.getLogger('smartlink.targeting.geo')


class GeoTargetingService:
    """IP → country → match rule."""

    def matches(self, geo_targeting, country: str, region: str = '', city: str = '') -> bool:
        """Check if the given geo matches the GeoTargeting rule."""
        if geo_targeting is None:
            return True
        return geo_targeting.matches(country=country, region=region, city=city)

    def get_country_from_ip(self, ip: str) -> dict:
        """
        Resolve IP to country, region, city using GeoIP2 (MaxMind).
        Returns {'country': 'BD', 'region': 'Dhaka', 'city': 'Dhaka'}.
        Falls back to empty strings on error.
        """
        result = {'country': '', 'region': '', 'city': '', 'isp': '', 'asn': ''}
        try:
            import geoip2.database
            from django.conf import settings
            db_path = getattr(settings, 'GEOIP_PATH', '/usr/share/GeoIP')

            # City database (includes country + region + city)
            with geoip2.database.Reader(f"{db_path}/GeoLite2-City.mmdb") as reader:
                response = reader.city(ip)
                result['country'] = response.country.iso_code or ''
                result['region'] = response.subdivisions.most_specific.name or ''
                result['city'] = response.city.name or ''

            # ASN database (ISP/carrier detection)
            try:
                with geoip2.database.Reader(f"{db_path}/GeoLite2-ASN.mmdb") as asn_reader:
                    asn_response = asn_reader.asn(ip)
                    result['asn'] = f"AS{asn_response.autonomous_system_number}"
                    result['isp'] = asn_response.autonomous_system_organization or ''
            except Exception:
                pass

        except Exception as e:
            logger.debug(f"GeoIP lookup failed for {ip}: {e}")

        return result
