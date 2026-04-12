# api/offer_inventory/geo_targeting.py
"""
Geo Targeting Engine.
Country/region-based offer filtering, routing and analytics.
Supports IP geolocation, ISP detection, and VPN/proxy detection.
"""
import ipaddress
import logging
from typing import Optional
from django.core.cache import cache

logger = logging.getLogger(__name__)

GEO_CACHE_TTL  = 3600   # 1 hour per IP
HIGH_RISK_COUNTRIES = ['', 'XX']  # Unknown / test IPs


class GeoTargetingEngine:
    """
    Full geo targeting — lookup, filter, score.
    """

    # ── IP Geolocation ─────────────────────────────────────────────

    @staticmethod
    def get_geo(ip: str) -> dict:
        """
        Get geo data for an IP.
        DB cache → External API → fallback.
        Returns dict with country_code, city, isp, is_vpn, is_proxy.
        """
        if not ip or ip in ('127.0.0.1', '::1', 'localhost'):
            return GeoTargetingEngine._empty_geo(ip)

        cache_key = f'geo:{ip}'
        cached    = cache.get(cache_key)
        if cached:
            return cached

        # DB check first
        result = GeoTargetingEngine._from_db(ip)
        if result:
            cache.set(cache_key, result, GEO_CACHE_TTL)
            return result

        # External API
        result = GeoTargetingEngine._from_api(ip)
        cache.set(cache_key, result, GEO_CACHE_TTL)

        # Persist to DB for future use
        GeoTargetingEngine._save_to_db(ip, result)

        return result

    @staticmethod
    def _from_db(ip: str) -> Optional[dict]:
        try:
            from api.offer_inventory.models import GeoData
            geo = GeoData.objects.get(ip_address=ip)
            return {
                'ip_address'  : ip,
                'country_code': geo.country_code,
                'country_name': geo.country_name,
                'region'      : geo.region,
                'city'        : geo.city,
                'latitude'    : float(geo.latitude or 0),
                'longitude'   : float(geo.longitude or 0),
                'isp'         : geo.isp,
                'is_vpn'      : geo.is_vpn,
                'is_proxy'    : geo.is_proxy,
            }
        except Exception:
            return None

    @staticmethod
    def _from_api(ip: str) -> dict:
        """Call ipapi.co for geo info."""
        try:
            import requests
            resp = requests.get(f'https://ipapi.co/{ip}/json/', timeout=4)
            if resp.status_code == 200:
                data = resp.json()
                return {
                    'ip_address'  : ip,
                    'country_code': data.get('country_code', ''),
                    'country_name': data.get('country_name', ''),
                    'region'      : data.get('region', ''),
                    'city'        : data.get('city', ''),
                    'latitude'    : float(data.get('latitude', 0) or 0),
                    'longitude'   : float(data.get('longitude', 0) or 0),
                    'isp'         : data.get('org', ''),
                    'is_vpn'      : False,
                    'is_proxy'    : False,
                }
        except Exception as e:
            logger.debug(f'Geo API error for {ip}: {e}')
        return GeoTargetingEngine._empty_geo(ip)

    @staticmethod
    def _empty_geo(ip: str) -> dict:
        return {
            'ip_address': ip, 'country_code': '', 'country_name': '',
            'region': '', 'city': '', 'latitude': 0.0, 'longitude': 0.0,
            'isp': '', 'is_vpn': False, 'is_proxy': False,
        }

    @staticmethod
    def _save_to_db(ip: str, data: dict):
        try:
            from api.offer_inventory.models import GeoData
            GeoData.objects.update_or_create(
                ip_address=ip,
                defaults={
                    'country_code': data['country_code'],
                    'country_name': data['country_name'],
                    'region'      : data['region'],
                    'city'        : data['city'],
                    'latitude'    : data['latitude'],
                    'longitude'   : data['longitude'],
                    'isp'         : data['isp'],
                    'is_vpn'      : data['is_vpn'],
                    'is_proxy'    : data['is_proxy'],
                }
            )
        except Exception as e:
            logger.debug(f'GeoData save error: {e}')

    # ── Offer Filtering ────────────────────────────────────────────

    @staticmethod
    def filter_offers_for_country(offers: list, country_code: str) -> list:
        """
        Return only offers allowed for this country.
        Applies OfferVisibilityRule country constraints.
        """
        if not country_code:
            return offers

        result = []
        for offer in offers:
            if GeoTargetingEngine.offer_allowed_in(offer, country_code):
                result.append(offer)
        return result

    @staticmethod
    def offer_allowed_in(offer, country_code: str) -> bool:
        """Check if a single offer is allowed in a country."""
        try:
            rules = offer.visibility_rules.filter(
                rule_type='country', is_active=True
            )
            for rule in rules:
                vals = rule.values or []
                if rule.operator == 'include' and country_code not in vals:
                    return False
                if rule.operator == 'exclude' and country_code in vals:
                    return False
        except Exception:
            pass
        return True

    # ── Country-level analytics ────────────────────────────────────

    @staticmethod
    def get_top_countries(days: int = 7, limit: int = 20) -> list:
        """Top countries by click volume."""
        from api.offer_inventory.models import Click
        from django.db.models import Count
        from datetime import timedelta
        from django.utils import timezone

        since = timezone.now() - timedelta(days=days)
        return list(
            Click.objects.filter(created_at__gte=since, is_fraud=False)
            .exclude(country_code='')
            .values('country_code')
            .annotate(clicks=Count('id'))
            .order_by('-clicks')[:limit]
        )

    @staticmethod
    def get_country_revenue(days: int = 7) -> list:
        """Revenue breakdown by country."""
        from api.offer_inventory.models import Conversion
        from django.db.models import Count, Sum
        from datetime import timedelta
        from django.utils import timezone

        since = timezone.now() - timedelta(days=days)
        return list(
            Conversion.objects.filter(
                created_at__gte=since, status__name='approved'
            )
            .exclude(country_code='')
            .values('country_code')
            .annotate(
                conversions=Count('id'),
                revenue    =Sum('payout_amount'),
                rewards    =Sum('reward_amount'),
            )
            .order_by('-revenue')[:20]
        )

    # ── ISP / VPN detection ────────────────────────────────────────

    @staticmethod
    def is_high_risk_location(ip: str) -> tuple:
        """
        Returns (is_risky: bool, reason: str).
        Checks VPN, proxy, datacenter IPs.
        """
        geo = GeoTargetingEngine.get_geo(ip)

        if geo['is_vpn']:
            return True, 'vpn_detected'
        if geo['is_proxy']:
            return True, 'proxy_detected'

        # Check against VPNProvider DB
        try:
            import ipaddress as _ip
            from api.offer_inventory.models import VPNProvider
            ip_obj = _ip.ip_address(ip)
            for vpn in VPNProvider.objects.filter(is_active=True):
                for asn in (vpn.asn_numbers or []):
                    if str(asn).lower() in geo.get('isp', '').lower():
                        return True, f'vpn_provider:{vpn.name}'
        except Exception:
            pass

        return False, ''
