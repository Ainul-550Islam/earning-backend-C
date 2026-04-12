"""Datacenter IP Range Detector — checks CIDR ranges and ASN prefixes."""
import ipaddress, logging
from django.core.cache import cache
logger = logging.getLogger(__name__)

DATACENTER_ASN_PREFIXES = [
    'AS14061','AS16509','AS15169','AS8075','AS13335','AS20940',
    'AS20473','AS63949','AS16276','AS24940','AS36352','AS40676',
]
DATACENTER_ISP_KEYWORDS = [
    'amazon','google','microsoft','digitalocean','linode','vultr',
    'hetzner','ovh','cloudflare','fastly','akamai','leaseweb',
    'choopa','psychz','quadranet','colocation','datacenter','hosting',
]

class DatacenterDetector:
    def __init__(self, ip_address: str, asn: str = '', isp: str = ''):
        self.ip_address = ip_address
        self.asn = asn.upper()
        self.isp = isp.lower()

    def detect(self) -> dict:
        cache_key = f"pi:dc:{self.ip_address}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        signals = {}
        signals['asn_prefix_match'] = any(
            self.asn.startswith(p) for p in DATACENTER_ASN_PREFIXES
        ) if self.asn else False
        signals['isp_keyword_match'] = any(
            kw in self.isp for kw in DATACENTER_ISP_KEYWORDS
        ) if self.isp else False
        signals['cidr_match'] = self._check_cidr()

        confidence = 0.0
        if signals['asn_prefix_match']: confidence += 0.5
        if signals['isp_keyword_match']: confidence += 0.3
        if signals['cidr_match']:        confidence += 0.4
        confidence = min(confidence, 1.0)

        result = {
            'ip_address': self.ip_address,
            'is_datacenter': confidence >= 0.4,
            'confidence': round(confidence, 3),
            'provider': self._guess_provider(),
            'signals': signals,
        }
        cache.set(cache_key, result, 3600)
        return result

    def _check_cidr(self) -> bool:
        try:
            from ..models import DatacenterIPRange
            ip_obj = ipaddress.ip_address(self.ip_address)
            for cidr in DatacenterIPRange.objects.filter(is_active=True).values_list('cidr', flat=True):
                try:
                    if ip_obj in ipaddress.ip_network(cidr, strict=False):
                        return True
                except ValueError:
                    continue
        except Exception as e:
            logger.debug(f"CIDR check error: {e}")
        return False

    def _guess_provider(self) -> str:
        providers = {
            'amazon': 'AWS', 'google': 'GCP', 'microsoft': 'Azure',
            'digitalocean': 'DigitalOcean', 'linode': 'Linode',
            'vultr': 'Vultr', 'hetzner': 'Hetzner', 'ovh': 'OVH',
            'cloudflare': 'Cloudflare',
        }
        for kw, name in providers.items():
            if kw in self.isp:
                return name
        return ''

    @classmethod
    def quick_check(cls, ip: str, asn: str = '', isp: str = '') -> bool:
        return cls(ip, asn, isp).detect()['is_datacenter']
