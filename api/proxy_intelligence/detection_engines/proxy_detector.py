"""
Proxy Detector Engine
=====================
Detects HTTP/HTTPS/SOCKS proxies via header analysis and port scanning.
"""
import logging
import socket
from django.core.cache import cache
from ..constants import PROXY_CONFIDENCE_THRESHOLD

logger = logging.getLogger(__name__)

# Headers that reveal proxy usage
PROXY_HEADERS = [
    'HTTP_X_FORWARDED_FOR',
    'HTTP_X_REAL_IP',
    'HTTP_VIA',
    'HTTP_X_PROXY_ID',
    'HTTP_FORWARDED',
    'HTTP_CLIENT_IP',
    'HTTP_X_CLUSTER_CLIENT_IP',
    'HTTP_FORWARDED_FOR',
    'HTTP_PROXY_CONNECTION',
]

PROXY_PORTS = {
    8080: 'HTTP Proxy',
    3128: 'Squid Proxy',
    8888: 'HTTP Proxy',
    8118: 'Privoxy',
    1080: 'SOCKS',
    1081: 'SOCKS5',
    3129: 'HTTP Proxy',
    4444: 'Proxy',
    9050: 'Tor SOCKS',
    9051: 'Tor Control',
}


class ProxyDetector:
    """
    Detects proxy usage through multiple signals.
    """

    def __init__(self, ip_address: str, request_headers: dict = None):
        self.ip_address = ip_address
        self.request_headers = request_headers or {}
        self.signals = {}

    def detect(self) -> dict:
        cache_key = f"pi:proxy_detect:{self.ip_address}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        self._check_headers()
        self._check_ports()

        confidence = self._calculate_confidence()
        is_proxy = confidence >= PROXY_CONFIDENCE_THRESHOLD
        proxy_type = self._determine_proxy_type()

        result = {
            'ip_address': self.ip_address,
            'is_proxy': is_proxy,
            'confidence': round(confidence, 3),
            'proxy_type': proxy_type,
            'is_anonymous': not self.signals.get('real_ip_leaked', False),
            'detected_headers': self.signals.get('proxy_headers_found', []),
            'open_proxy_ports': self.signals.get('open_ports', []),
            'signals': self.signals,
        }
        cache.set(cache_key, result, 1800)
        return result

    def _check_headers(self):
        """Analyze request headers for proxy indicators."""
        found_headers = []
        real_ip_leaked = False

        for header in PROXY_HEADERS:
            if header in self.request_headers:
                found_headers.append(header)
                if header == 'HTTP_X_FORWARDED_FOR':
                    real_ip_leaked = True

        self.signals['proxy_headers_found'] = found_headers
        self.signals['has_proxy_headers'] = len(found_headers) > 0
        self.signals['real_ip_leaked'] = real_ip_leaked

    def _check_ports(self):
        """Scan common proxy ports."""
        open_ports = []
        for port in [8080, 3128, 1080, 8118]:  # Top 4 only for speed
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(0.5)
                if sock.connect_ex((self.ip_address, port)) == 0:
                    open_ports.append({'port': port, 'type': PROXY_PORTS.get(port, 'Unknown')})
                sock.close()
            except Exception:
                pass
        self.signals['open_ports'] = open_ports
        self.signals['has_open_proxy_ports'] = len(open_ports) > 0

    def _calculate_confidence(self) -> float:
        score = 0.0
        if self.signals.get('has_proxy_headers'):
            score += 0.5
        if self.signals.get('has_open_proxy_ports'):
            score += 0.4
        if self.signals.get('real_ip_leaked'):
            score += 0.1
        return min(score, 1.0)

    def _determine_proxy_type(self) -> str:
        if not self.signals.get('open_ports'):
            if self.signals.get('has_proxy_headers'):
                return 'http'
            return 'unknown'
        port = self.signals['open_ports'][0]['port']
        if port in [1080, 1081]:
            return 'socks5'
        if port == 9050:
            return 'tor'
        return 'http'

    @classmethod
    def quick_check(cls, ip_address: str, headers: dict = None) -> bool:
        return cls(ip_address, headers).detect()['is_proxy']


class DatacenterDetector:
    """Detects if an IP belongs to a known datacenter/hosting provider."""

    @classmethod
    def is_datacenter(cls, ip_address: str, asn: str = '') -> bool:
        cache_key = f"pi:dc_detect:{ip_address}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        result = False
        # Check known datacenter ASNs
        if any(asn.startswith(dc) for dc in DATACENTER_ASN_PREFIXES if asn):
            result = True

        if not result:
            # Check IP against datacenter ranges in DB
            try:
                from ..models import DatacenterIPRange
                import ipaddress
                ip_obj = ipaddress.ip_address(ip_address)
                for range_entry in DatacenterIPRange.objects.filter(is_active=True).values_list('cidr', flat=True):
                    try:
                        if ip_obj in ipaddress.ip_network(range_entry, strict=False):
                            result = True
                            break
                    except ValueError:
                        continue
            except Exception as e:
                logger.debug(f"Datacenter DB check failed: {e}")

        cache.set(cache_key, result, 3600)
        return result


try:
    from ..constants import DATACENTER_ASN_PREFIXES
except ImportError:
    DATACENTER_ASN_PREFIXES = []
