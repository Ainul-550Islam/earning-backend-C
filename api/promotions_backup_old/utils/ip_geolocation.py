# api/promotions/utils/ip_geolocation.py
import logging, requests
from django.core.cache import cache
logger = logging.getLogger('utils.geo')

class IPGeolocation:
    """IP → Country/City/ISP. Providers: ip-api.com → ipinfo.io fallback。"""
    PROVIDERS = [
        ('ip-api',  'http://ip-api.com/json/{ip}?fields=country,countryCode,city,region,isp,proxy,hosting'),
        ('ipinfo',  'https://ipinfo.io/{ip}/json'),
    ]

    def lookup(self, ip: str) -> dict:
        if ip in ('127.0.0.1', 'localhost', '::1'): return {'country': 'LOCAL', 'country_code': 'XX', 'city': 'localhost'}
        ck = f'geo:{ip}'
        if cache.get(ck): return cache.get(ck)
        for name, url_tpl in self.PROVIDERS:
            try:
                r    = requests.get(url_tpl.format(ip=ip), timeout=5)
                data = r.json()
                if name == 'ip-api':
                    result = {'country': data.get('country',''), 'country_code': data.get('countryCode',''),
                              'city': data.get('city',''), 'region': data.get('region',''),
                              'isp': data.get('isp',''), 'is_proxy': data.get('proxy',False),
                              'is_hosting': data.get('hosting',False)}
                else:
                    result = {'country': data.get('country',''), 'country_code': data.get('country','')[:2],
                              'city': data.get('city',''), 'region': data.get('region',''), 'isp': data.get('org','')}
                cache.set(ck, result, timeout=86400)
                return result
            except Exception: continue
        return {'country': '', 'country_code': '', 'city': ''}

    def is_vpn_or_proxy(self, ip: str) -> bool:
        geo = self.lookup(ip)
        return geo.get('is_proxy', False) or geo.get('is_hosting', False)

    def bulk_lookup(self, ips: list[str]) -> dict:
        return {ip: self.lookup(ip) for ip in ips}
