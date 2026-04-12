# api/promotions/connectors/data_partners.py
# Data Partners — Third-party data enrichment (demographics, interests, device data)
import logging, requests
from django.conf import settings
from django.core.cache import cache
logger = logging.getLogger('connectors.data_partners')

class DataPartnerConnector:
    """
    Third-party data enrichment for targeting.
    Partners: Acxiom, Oracle Data Cloud, Nielsen, Lotame DMP.
    """
    def enrich_user(self, user_id: int, ip: str, user_agent: str) -> dict:
        """User profile 3rd party data দিয়ে enrich করে।"""
        cache_key = f'dmp:user:{user_id}'
        cached    = cache.get(cache_key)
        if cached: return cached

        enriched = {
            'age_group':     self._estimate_age_group(user_agent),
            'interests':     [],
            'income_bracket': 'unknown',
            'purchase_intent': [],
        }
        # Add IP geolocation
        geo = self._ip_lookup(ip)
        enriched.update(geo)
        cache.set(cache_key, enriched, timeout=86400)
        return enriched

    def get_audience_segments(self, segment_ids: list[str]) -> dict:
        """DMP audience segment details।"""
        return {sid: {'name': f'Segment_{sid}', 'size': 10000} for sid in segment_ids}

    def _estimate_age_group(self, ua: str) -> str:
        ua = ua.lower()
        if 'android 1' in ua or 'ios 1' in ua: return '18-25'
        return 'unknown'

    def _ip_lookup(self, ip: str) -> dict:
        try:
            from api.promotions.utils.ip_geolocation import IPGeolocation
            return IPGeolocation().lookup(ip)
        except Exception:
            return {'country': '', 'city': '', 'region': ''}
