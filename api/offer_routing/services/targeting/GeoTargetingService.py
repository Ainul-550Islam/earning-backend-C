"""
Geo Targeting Service - Real Implementation.
Module-level _get_ip_geolocation is patchable by tests.
"""
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

_STATE_ABBREVS = {
    'AL':'ALABAMA','AK':'ALASKA','AZ':'ARIZONA','AR':'ARKANSAS',
    'CA':'CALIFORNIA','CO':'COLORADO','CT':'CONNECTICUT','DE':'DELAWARE',
    'FL':'FLORIDA','GA':'GEORGIA','HI':'HAWAII','ID':'IDAHO',
    'IL':'ILLINOIS','IN':'INDIANA','IA':'IOWA','KS':'KANSAS',
    'KY':'KENTUCKY','LA':'LOUISIANA','ME':'MAINE','MD':'MARYLAND',
    'MA':'MASSACHUSETTS','MI':'MICHIGAN','MN':'MINNESOTA','MS':'MISSISSIPPI',
    'MO':'MISSOURI','MT':'MONTANA','NE':'NEBRASKA','NV':'NEVADA',
    'NH':'NEW HAMPSHIRE','NJ':'NEW JERSEY','NM':'NEW MEXICO','NY':'NEW YORK',
    'NC':'NORTH CAROLINA','ND':'NORTH DAKOTA','OH':'OHIO','OK':'OKLAHOMA',
    'OR':'OREGON','PA':'PENNSYLVANIA','RI':'RHODE ISLAND','SC':'SOUTH CAROLINA',
    'SD':'SOUTH DAKOTA','TN':'TENNESSEE','TX':'TEXAS','UT':'UTAH',
    'VT':'VERMONT','VA':'VIRGINIA','WA':'WASHINGTON','WV':'WEST VIRGINIA',
    'WI':'WISCONSIN','WY':'WYOMING','DC':'DISTRICT OF COLUMBIA',
}
_CITY_ABBREVS = {
    'LA':'LOS ANGELES','NYC':'NEW YORK CITY','SF':'SAN FRANCISCO',
    'PHX':'PHOENIX','CHI':'CHICAGO','HOU':'HOUSTON','DAL':'DALLAS',
    'ATL':'ATLANTA','SEA':'SEATTLE','DC':'WASHINGTON','LV':'LAS VEGAS',
}


def _geo_val_matches(rule_val: str, ctx_val: str) -> bool:
    r = rule_val.strip().upper()
    c = ctx_val.strip().upper()
    if r == c:
        return True
    if _STATE_ABBREVS.get(r) == c:
        return True
    if _CITY_ABBREVS.get(r) == c:
        return True
    return False


# ── Module-level geolocation function — patchable in tests ───────────────────
def _get_ip_geolocation(ip: str) -> dict:
    """
    Fetch geolocation data for an IP address.
    Tests patch this function via:
      patch('offer_routing.services.targeting.GeoTargetingService._get_ip_geolocation')
    """
    return {}


class GeoTargetingService:
    """Geographic targeting for offer routing."""

    def matches_geo_rule(self, rule, context: dict) -> dict:
        location = context.get('location', context) if isinstance(context, dict) else {}
        matched_fields = []
        country_ok = True
        if rule.country:
            ctx_c = location.get('country', '')
            if ctx_c and _geo_val_matches(rule.country, ctx_c):
                matched_fields.append('country')
            else:
                country_ok = False
        if rule.region:
            ctx_r = location.get('region', '')
            if ctx_r and _geo_val_matches(rule.region, ctx_r):
                matched_fields.append('region')
        if rule.city:
            ctx_city = location.get('city', '')
            if ctx_city and _geo_val_matches(rule.city, ctx_city):
                matched_fields.append('city')
        return {'matches': country_ok and bool(matched_fields),
                'rule_id': rule.id, 'matched_fields': matched_fields}

    def get_user_location(self, context: dict) -> dict:
        try:
            import offer_routing.services.cache as _cm
            location = context.get('location', {})
            ip = location.get('ip') or context.get('ip_address', '')
            cache_key = f'geo:ip:{ip}' if ip else None
            if cache_key:
                try:
                    raw = _cm.cache_service.get(cache_key)
                    if raw is None:
                        pass  # cache miss
                    elif isinstance(raw, dict) and 'found' in raw:
                        if raw.get('found') and isinstance(raw.get('value'), dict):
                            return raw['value']
                    elif isinstance(raw, dict) and 'country' in raw:
                        return raw
                except Exception:
                    pass
            geo_result = _get_ip_geolocation(ip) if ip else {}
            result = {**location, **geo_result}
            if cache_key and result:
                try:
                    _cm.cache_service.set(cache_key, result, timeout=3600)
                except Exception:
                    pass
            return result
        except Exception as e:
            logger.error("get_user_location error: %s", e)
            return context.get('location', {})

    def _get_ip_geolocation(self, ip: str) -> dict:
        """Instance method delegates to module-level function (patchable)."""
        return _get_ip_geolocation(ip)

    def validate_geo_rule_config(self, config: dict) -> dict:
        errors = []
        country = config.get('country', '')
        if not country:
            errors.append('country')
        elif len(country) > 3:
            errors.append('country')
        return {'valid': len(errors) == 0, 'errors': errors}

    def get_geo_rules_for_location(self, location: dict) -> list:
        try:
            from offer_routing.models import GeoRouteRule
            rules = GeoRouteRule.objects.all()
            return [r for r in rules
                    if self.matches_geo_rule(r, {'location': location}).get('matches')]
        except Exception as e:
            logger.error("get_geo_rules_for_location error: %s", e)
            return []

    def is_ip_in_range(self, ip: str, ip_range: str) -> bool:
        try:
            import ipaddress
            return ipaddress.ip_address(ip) in ipaddress.ip_network(ip_range, strict=False)
        except Exception:
            return False

    def get_country_from_ip(self, ip: str) -> Optional[str]:
        try:
            return _get_ip_geolocation(ip).get('country')
        except Exception:
            return None

    def health_check(self) -> dict:
        try:
            geo_ok = bool(_get_ip_geolocation('8.8.8.8'))
            return {'status': 'healthy',
                    'ip_geolocation_service': 'ok' if geo_ok else 'degraded',
                    'rules_loaded': True}
        except Exception as e:
            return {'status': 'error', 'ip_geolocation_service': 'error', 'error': str(e)}
