# api/offer_inventory/targeting/isp_targeting.py
"""
ISP Targeting — Filter and route offers based on Internet Service Provider.
Supports ASN-based targeting, mobile/datacenter detection, risk scoring.
"""
import ipaddress
import logging
from django.core.cache import cache

logger = logging.getLogger(__name__)


class ISPTargetingEngine:
    """Target users by ISP, ASN, mobile carrier, or connection type."""

    @staticmethod
    def get_isp_info(ip: str) -> dict:
        """Get ISP information for an IP address."""
        cache_key = f'isp:{ip}'
        cached    = cache.get(cache_key)
        if cached:
            return cached

        # DB lookup first
        try:
            from api.offer_inventory.models import GeoData
            geo = GeoData.objects.get(ip_address=ip)
            if geo.isp:
                result = {'isp': geo.isp, 'asn': '', 'is_mobile': False, 'is_hosting': False}
                cache.set(cache_key, result, 3600)
                return result
        except Exception:
            pass

        # External API fallback
        try:
            import requests
            resp = requests.get(f'https://ipapi.co/{ip}/json/', timeout=4)
            if resp.status_code == 200:
                data = resp.json()
                result = {
                    'isp'       : data.get('org', ''),
                    'asn'       : data.get('asn', ''),
                    'is_mobile' : data.get('network', {}).get('type', '') == 'Mobile' if isinstance(data.get('network'), dict) else False,
                    'is_hosting': 'datacenter' in data.get('org', '').lower() or 'hosting' in data.get('org', '').lower(),
                }
                cache.set(cache_key, result, 3600)
                return result
        except Exception as e:
            logger.debug(f'ISP lookup error for {ip}: {e}')

        return {'isp': '', 'asn': '', 'is_mobile': False, 'is_hosting': False}

    @staticmethod
    def filter_offers_by_isp(offers: list, ip: str) -> list:
        """Remove offers not available for user's ISP."""
        isp_info = ISPTargetingEngine.get_isp_info(ip)
        if not isp_info.get('isp'):
            return offers

        result = []
        for offer in offers:
            # Check ISP targeting rules
            try:
                rules = offer.visibility_rules.filter(rule_type='isp', is_active=True)
                excluded = False
                for rule in rules:
                    isp_lower = isp_info['isp'].lower()
                    vals      = [v.lower() for v in (rule.values or [])]
                    if rule.operator == 'include' and not any(v in isp_lower for v in vals):
                        excluded = True
                        break
                    if rule.operator == 'exclude' and any(v in isp_lower for v in vals):
                        excluded = True
                        break
                if not excluded:
                    result.append(offer)
            except Exception:
                result.append(offer)
        return result

    @staticmethod
    def is_hosting_provider(ip: str) -> bool:
        """Check if IP belongs to a datacenter/hosting provider (potential fraud)."""
        info = ISPTargetingEngine.get_isp_info(ip)
        return info.get('is_hosting', False)

    @staticmethod
    def is_mobile_carrier(ip: str) -> bool:
        """Check if IP is from a mobile carrier."""
        info = ISPTargetingEngine.get_isp_info(ip)
        return info.get('is_mobile', False)

    @staticmethod
    def get_risk_score_from_isp(ip: str) -> float:
        """ISP-based fraud risk score (0-100)."""
        info = ISPTargetingEngine.get_isp_info(ip)
        score = 0.0
        if info.get('is_hosting'):
            score += 40.0   # Datacenter IPs are higher risk
        isp_lower = info.get('isp', '').lower()
        suspicious_keywords = ['vpn', 'proxy', 'anonymous', 'tor', 'hide', 'tunnel']
        for kw in suspicious_keywords:
            if kw in isp_lower:
                score += 20.0
                break
        return min(100.0, score)
