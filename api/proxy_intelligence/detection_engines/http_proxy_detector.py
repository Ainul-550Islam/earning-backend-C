"""HTTP/HTTPS Proxy Detector — header analysis + port scan."""
import socket, logging
from django.core.cache import cache
logger = logging.getLogger(__name__)

HTTP_PROXY_PORTS = {8080:'HTTP',3128:'Squid',8888:'HTTP',8118:'Privoxy',
                    8081:'HTTP',8000:'HTTP',80:'HTTP',8443:'HTTPS',443:'HTTPS'}

PROXY_REQUEST_HEADERS = [
    'HTTP_VIA','HTTP_X_FORWARDED_FOR','HTTP_FORWARDED','HTTP_PROXY_CONNECTION',
    'HTTP_X_PROXY_ID','HTTP_PROXY_AUTHENTICATE','HTTP_X_REAL_IP',
]

class HTTPProxyDetector:
    def __init__(self, ip_address: str, request_headers: dict = None):
        self.ip_address = ip_address
        self.headers = request_headers or {}

    def detect(self) -> dict:
        cache_key = f"pi:http_proxy:{self.ip_address}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        # Header signals
        found_headers = [h.replace('HTTP_','') for h in PROXY_REQUEST_HEADERS
                         if h in self.headers and self.headers[h]]
        header_score = 0.5 if found_headers else 0.0

        # Port scan (fast — top 3 only)
        open_ports = []
        for port in [8080, 3128, 8118]:
            try:
                s = socket.socket(); s.settimeout(0.4)
                if s.connect_ex((self.ip_address, port)) == 0:
                    open_ports.append({'port': port, 'service': HTTP_PROXY_PORTS[port]})
                s.close()
            except Exception:
                pass
        port_score = 0.4 if open_ports else 0.0

        confidence = min(header_score + port_score, 1.0)
        result = {
            'ip_address': self.ip_address,
            'is_http_proxy': confidence >= 0.4,
            'confidence': round(confidence, 3),
            'proxy_headers': found_headers,
            'open_ports': open_ports,
            'is_transparent': len(found_headers) > 0 and 'X_FORWARDED_FOR' in str(found_headers),
        }
        cache.set(cache_key, result, 1800)
        return result
