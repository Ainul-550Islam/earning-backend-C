# api/payment_gateways/ip_intelligence.py
# IP intelligence — VPN/proxy/Tor detection, GEO lookup
import logging
from django.core.cache import cache
logger = logging.getLogger(__name__)

KNOWN_VPN_PROVIDERS = {'nordvpn','expressvpn','surfshark','cyberghost','ipvanish','purevpn','windscribe'}
TOR_EXIT_NODES_CACHE_KEY = 'ip:tor_nodes'

class IPIntelligence:
    def analyze(self, ip):
        if not ip or ip in ('127.0.0.1','::1','localhost'): return {'ip':ip,'is_local':True,'risk':'low'}
        cache_key = f'ip:intel:{ip}'
        cached = cache.get(cache_key)
        if cached: return cached
        result = {'ip':ip,'is_local':False,'country':'','is_vpn':False,'is_proxy':False,'is_tor':False,'is_datacenter':False,'risk':'low','isp':'','city':'','asn':''}
        result.update(self._geoip_lookup(ip))
        result.update(self._risk_assessment(result))
        cache.set(cache_key, result, 3600)
        return result
    def _geoip_lookup(self, ip):
        try:
            import geoip2.database
            from django.conf import settings
            db_path = getattr(settings,'GEOIP2_DATABASE_PATH','/usr/share/GeoIP/GeoLite2-City.mmdb')
            with geoip2.database.Reader(db_path) as reader:
                r = reader.city(ip)
                return {'country':r.country.iso_code or '','city':r.city.name or '','asn':str(r.traits.autonomous_system_number or '')}
        except:
            try:
                import requests
                r = requests.get(f'http://ip-api.com/json/{ip}?fields=status,country,isp,org,as,proxy,hosting', timeout=3)
                d = r.json()
                if d.get('status')=='success':
                    return {'country':d.get('countryCode',''),'city':d.get('city',''),'isp':d.get('isp',''),'is_proxy':bool(d.get('proxy')),'is_datacenter':bool(d.get('hosting')),'asn':d.get('as','')}
            except: pass
        return {}
    def _risk_assessment(self, data):
        risk = 'low'
        if data.get('is_tor') or data.get('is_vpn'): risk = 'high'
        elif data.get('is_proxy') or data.get('is_datacenter'): risk = 'medium'
        return {'risk': risk}
    def get_country(self, ip):
        return self.analyze(ip).get('country','')
    def is_suspicious(self, ip):
        data = self.analyze(ip)
        return data.get('risk') in ('high','critical') or data.get('is_tor') or data.get('is_vpn')
ip_intelligence = IPIntelligence()
