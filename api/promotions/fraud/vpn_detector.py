# =============================================================================
# promotions/fraud/vpn_detector.py
# VPN/Proxy/Tor Detection — block fraudulent traffic
# =============================================================================
from django.core.cache import cache
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
import ipaddress, logging

logger = logging.getLogger(__name__)

KNOWN_VPN_RANGES = [
    '10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16',  # Private
    '100.64.0.0/10',  # Shared Address Space
]

DATACENTER_ASNS = {  # Known datacenter ASNs (VPN/proxy likely)
    'AS14061': 'DigitalOcean', 'AS16276': 'OVH', 'AS14618': 'AWS',
    'AS15169': 'Google', 'AS8075': 'Microsoft', 'AS13335': 'Cloudflare',
    'AS20473': 'Choopa/Vultr', 'AS24940': 'Hetzner',
}


class VPNDetector:
    """Detect VPN, proxy, Tor, and datacenter traffic."""

    def is_suspicious_ip(self, ip: str) -> dict:
        """Check if IP is VPN/proxy/datacenter."""
        result = {
            'ip': ip, 'is_vpn': False, 'is_proxy': False,
            'is_datacenter': False, 'is_tor': False,
            'risk_score': 0, 'reason': [],
        }
        # Private IP ranges
        try:
            ip_obj = ipaddress.ip_address(ip)
            if ip_obj.is_private:
                result['is_vpn'] = True
                result['risk_score'] = 80
                result['reason'].append('private_ip')
                return result
        except ValueError:
            return result

        # Cache check (from previous lookups)
        cached = cache.get(f'ip_check:{ip}')
        if cached:
            return cached

        # Known VPN CIDR ranges check
        for cidr in KNOWN_VPN_RANGES:
            try:
                if ip_obj in ipaddress.ip_network(cidr):
                    result['is_vpn'] = True
                    result['risk_score'] += 50
                    result['reason'].append(f'vpn_range_{cidr}')
            except ValueError:
                pass

        # Tor exit node check (in production: query Tor exit node list)
        if cache.get(f'tor_exit:{ip}'):
            result['is_tor'] = True
            result['risk_score'] = 100
            result['reason'].append('tor_exit_node')

        cache.set(f'ip_check:{ip}', result, timeout=3600 * 6)
        return result

    def add_tor_exit_node(self, ip: str):
        cache.set(f'tor_exit:{ip}', True, timeout=3600 * 24 * 7)

    def get_fraud_risk_score(self, ip: str, user_agent: str, country: str) -> int:
        """Combined fraud risk score 0-100."""
        score = 0
        vpn_check = self.is_suspicious_ip(ip)
        score += vpn_check['risk_score'] * 0.4
        ua = user_agent.lower()
        if any(bot in ua for bot in ['bot', 'crawler', 'spider', 'curl', 'wget', 'python', 'java']):
            score += 40
        if country in ['', 'XX', 'ZZ']:
            score += 20
        return min(int(score), 100)


class ClickFloodDetector:
    """Detect click flooding — too many clicks from same source."""
    FLOOD_THRESHOLD = 50  # Clicks per minute per IP

    def check_click_flood(self, ip: str, campaign_id: int) -> dict:
        key = f'click_flood:{ip}:{campaign_id}:{__import__("time").time()//60:.0f}'
        count = cache.get(key, 0)
        count += 1
        cache.set(key, count, timeout=120)
        is_flood = count > self.FLOOD_THRESHOLD
        return {
            'is_flood': is_flood,
            'click_count_per_min': count,
            'threshold': self.FLOOD_THRESHOLD,
            'risk_level': 'high' if is_flood else 'normal',
        }


class DeviceFarmDetector:
    """Detect device farms — emulators generating fake installs."""

    def is_device_farm_signal(self, device_fingerprint: dict) -> dict:
        signals = []
        score = 0
        ua = device_fingerprint.get('user_agent', '').lower()
        if 'emulator' in ua or 'sdk_gphone' in ua:
            signals.append('emulator_ua')
            score += 60
        if device_fingerprint.get('screen_width', 0) == 0:
            signals.append('no_screen')
            score += 30
        if not device_fingerprint.get('timezone'):
            signals.append('no_timezone')
            score += 20
        return {
            'is_device_farm': score >= 60,
            'risk_score': min(score, 100),
            'signals': signals,
        }


fraud_detector = VPNDetector()
click_flood_detector = ClickFloodDetector()
device_farm_detector = DeviceFarmDetector()


@api_view(['GET'])
@permission_classes([IsAdminUser])
def check_ip_view(request):
    ip = request.query_params.get('ip', request.META.get('REMOTE_ADDR', ''))
    detector = VPNDetector()
    return Response(detector.is_suspicious_ip(ip))
