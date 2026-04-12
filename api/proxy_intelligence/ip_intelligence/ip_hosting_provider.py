"""Hosting Provider Detection — identifies cloud/hosting providers from IP."""
from django.core.cache import cache

KNOWN_PROVIDERS = {
    'amazon': {'name': 'AWS', 'asns': ['AS16509']},
    'google': {'name': 'Google Cloud', 'asns': ['AS15169']},
    'microsoft': {'name': 'Azure', 'asns': ['AS8075']},
    'digitalocean': {'name': 'DigitalOcean', 'asns': ['AS14061']},
    'linode': {'name': 'Linode/Akamai', 'asns': ['AS63949']},
    'vultr': {'name': 'Vultr', 'asns': ['AS20473']},
    'hetzner': {'name': 'Hetzner', 'asns': ['AS24940']},
    'ovh': {'name': 'OVH', 'asns': ['AS16276']},
    'cloudflare': {'name': 'Cloudflare', 'asns': ['AS13335']},
    'fastly': {'name': 'Fastly', 'asns': ['AS54113']},
    'akamai': {'name': 'Akamai', 'asns': ['AS20940']},
    'leaseweb': {'name': 'LeaseWeb', 'asns': ['AS28753']},
    'psychz': {'name': 'Psychz Networks', 'asns': ['AS40676']},
    'choopa': {'name': 'Vultr/Choopa', 'asns': ['AS20473']},
}
ASN_TO_PROVIDER = {asn: info['name']
                   for info in KNOWN_PROVIDERS.values()
                   for asn in info['asns']}


class HostingProviderDetector:
    @classmethod
    def identify(cls, isp: str = '', org: str = '', asn: str = '') -> dict:
        cache_key = f"pi:hosting:{asn}:{isp[:20]}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        combined = (isp + ' ' + org).lower()
        result = {'provider_name': '', 'is_known_hosting': False, 'matched_by': ''}

        if asn and asn.upper() in ASN_TO_PROVIDER:
            result['provider_name'] = ASN_TO_PROVIDER[asn.upper()]
            result['is_known_hosting'] = True
            result['matched_by'] = 'asn'
        else:
            for keyword, info in KNOWN_PROVIDERS.items():
                if keyword in combined:
                    result['provider_name'] = info['name']
                    result['is_known_hosting'] = True
                    result['matched_by'] = 'isp_keyword'
                    break

        cache.set(cache_key, result, 3600)
        return result

    @classmethod
    def is_hosting(cls, isp: str = '', org: str = '', asn: str = '') -> bool:
        return cls.identify(isp, org, asn)['is_known_hosting']

    @classmethod
    def get_provider_name(cls, isp: str = '', org: str = '', asn: str = '') -> str:
        return cls.identify(isp, org, asn)['provider_name']

    @staticmethod
    def get_all_providers() -> dict:
        return KNOWN_PROVIDERS
