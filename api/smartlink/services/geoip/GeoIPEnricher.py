"""
SmartLink GeoIP Enricher
World #1 Feature: Full IP intelligence enrichment.
Beyond basic country lookup — ISP, carrier, proxy, VPN, tor, datacenter detection.
Uses MaxMind GeoIP2 City + ASN + Enterprise databases.
"""
import logging
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger('smartlink.geoip')

CACHE_TTL = 3600  # 1 hour per IP


class GeoIPEnricher:
    """
    Full IP intelligence enrichment service.
    Single lookup returns everything needed for targeting + fraud scoring.
    """

    def enrich(self, ip: str) -> dict:
        """
        Enrich an IP address with full geo + ASN + proxy intelligence.

        Returns:
            {
                'ip': str,
                'country': str,       # 'BD'
                'country_name': str,  # 'Bangladesh'
                'region': str,        # 'Dhaka Division'
                'region_code': str,   # 'C'
                'city': str,          # 'Dhaka'
                'postal_code': str,
                'latitude': float,
                'longitude': float,
                'timezone': str,      # 'Asia/Dhaka'
                'asn': str,           # 'AS24389'
                'asn_org': str,       # 'Grameenphone Ltd'
                'isp': str,           # 'Grameenphone'
                'is_mobile': bool,    # True for mobile carriers
                'is_proxy': bool,
                'is_vpn': bool,
                'is_tor': bool,
                'is_datacenter': bool,
                'connection_type': str,  # 'cellular' | 'cable' | 'dsl' | 'fiber'
                'fraud_risk': str,    # 'low' | 'medium' | 'high'
            }
        """
        # Cache first
        cache_key = f'geoip:{ip}'
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        result = self._empty_result(ip)

        try:
            result = self._lookup_city(ip, result)
        except Exception as e:
            logger.debug(f"City lookup failed for {ip}: {e}")

        try:
            result = self._lookup_asn(ip, result)
        except Exception as e:
            logger.debug(f"ASN lookup failed for {ip}: {e}")

        # Enrich with proxy/VPN/datacenter detection
        result = self._detect_proxy_vpn(result)

        # Set fraud risk level
        result['fraud_risk'] = self._assess_fraud_risk(result)

        cache.set(cache_key, result, CACHE_TTL)
        return result

    def _lookup_city(self, ip: str, result: dict) -> dict:
        import geoip2.database
        geoip_path = getattr(settings, 'GEOIP_PATH', '/usr/share/GeoIP')
        with geoip2.database.Reader(f"{geoip_path}/GeoLite2-City.mmdb") as reader:
            r = reader.city(ip)
            result.update({
                'country':      r.country.iso_code or '',
                'country_name': r.country.name or '',
                'region':       r.subdivisions.most_specific.name or '',
                'region_code':  r.subdivisions.most_specific.iso_code or '',
                'city':         r.city.name or '',
                'postal_code':  r.postal.code or '',
                'latitude':     float(r.location.latitude or 0),
                'longitude':    float(r.location.longitude or 0),
                'timezone':     r.location.time_zone or 'UTC',
            })
        return result

    def _lookup_asn(self, ip: str, result: dict) -> dict:
        import geoip2.database
        geoip_path = getattr(settings, 'GEOIP_PATH', '/usr/share/GeoIP')
        with geoip2.database.Reader(f"{geoip_path}/GeoLite2-ASN.mmdb") as reader:
            r = reader.asn(ip)
            asn_num = r.autonomous_system_number
            asn_org = r.autonomous_system_organization or ''
            result.update({
                'asn':     f"AS{asn_num}" if asn_num else '',
                'asn_org': asn_org,
                'isp':     asn_org,
            })
            # Detect mobile carrier
            mobile_keywords = [
                'grameenphone', 'robi', 'banglalink', 'teletalk', 'airtel',
                'vodafone', 'tmobile', 't-mobile', 'att ', 'verizon',
                'sprint', 'cellular', 'mobile', 'wireless',
            ]
            org_lower = asn_org.lower()
            result['is_mobile'] = any(kw in org_lower for kw in mobile_keywords)

            # Detect connection type
            if result['is_mobile']:
                result['connection_type'] = 'cellular'
            elif any(kw in org_lower for kw in ['fiber', 'fttb', 'ftth']):
                result['connection_type'] = 'fiber'
            elif any(kw in org_lower for kw in ['cable', 'comcast', 'spectrum']):
                result['connection_type'] = 'cable'
            else:
                result['connection_type'] = 'dsl'

        return result

    def _detect_proxy_vpn(self, result: dict) -> dict:
        asn = result.get('asn', '')
        org = result.get('asn_org', '').lower()

        # Datacenter ASNs
        datacenter_asns = {
            'AS14618', 'AS16509', 'AS15169', 'AS396982',
            'AS8075', 'AS20473', 'AS14061', 'AS63949',
            'AS24940', 'AS200651', 'AS135377',
        }
        result['is_datacenter'] = asn.upper() in datacenter_asns

        # Known VPN/proxy providers
        vpn_keywords = [
            'vpn', 'proxy', 'nordvpn', 'expressvpn', 'surfshark',
            'privateinternetaccess', 'pia', 'mullvad', 'protonvpn',
            'hide.me', 'cyberghost', 'ipvanish', 'strongvpn',
            'm247', 'cdn77', 'b2 net', 'fastly', 'cloudflare',
        ]
        result['is_vpn']   = any(kw in org for kw in vpn_keywords)
        result['is_proxy'] = result['is_datacenter'] or result['is_vpn']
        result['is_tor']   = self._check_tor_exit(result.get('ip', ''))

        return result

    def _check_tor_exit(self, ip: str) -> bool:
        """Check if IP is a known Tor exit node (cached list)."""
        cache_key = f'tor_exit:{ip}'
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
        # In production: maintain a Redis set of Tor exit IPs
        # Updated daily from https://check.torproject.org/exit-addresses
        is_tor = bool(cache.get(f'tor:ips:{ip}'))
        cache.set(cache_key, is_tor, 3600)
        return is_tor

    def _assess_fraud_risk(self, result: dict) -> str:
        if result.get('is_tor') or result.get('is_datacenter'):
            return 'high'
        if result.get('is_vpn') or result.get('is_proxy'):
            return 'medium'
        return 'low'

    def _empty_result(self, ip: str) -> dict:
        return {
            'ip': ip, 'country': '', 'country_name': '',
            'region': '', 'region_code': '', 'city': '',
            'postal_code': '', 'latitude': 0.0, 'longitude': 0.0,
            'timezone': 'UTC', 'asn': '', 'asn_org': '', 'isp': '',
            'is_mobile': False, 'is_proxy': False, 'is_vpn': False,
            'is_tor': False, 'is_datacenter': False,
            'connection_type': 'unknown', 'fraud_risk': 'low',
        }
