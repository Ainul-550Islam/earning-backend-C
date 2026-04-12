"""
VPN Detector Engine  (PRODUCTION-READY - COMPLETE REWRITE)
===========================================================
Signals used:
  1. ASN match against known VPN provider ASN database
  2. HTTP request headers (X-Forwarded-For, Via, Proxy-*)
  3. ISP name keyword analysis
  4. Reverse DNS hostname analysis
  5. Open port scan on common VPN ports
  6. Datacenter ASN prefix match
  7. Known VPN IP database (MaliciousIPDatabase)
"""
import logging
import re
import socket
import struct
from typing import Optional
from django.core.cache import cache

logger = logging.getLogger(__name__)

# ── 1. Comprehensive VPN Provider ASN Map ──────────────────────────────────
VPN_PROVIDER_ASN_MAP = {
    # Tier-1 known VPN providers
    'AS9009':   'M247',           'AS20860': 'IOMART',
    'AS35819':  'Multa-ASN',      'AS62240': 'Clouvider',
    'AS202422': 'G-Core Labs',    'AS60068': 'CDN77',
    'AS9370':   'Sakura Internet','AS14061': 'DigitalOcean',
    'AS16276':  'OVH',            'AS24940': 'Hetzner',
    'AS16509':  'Amazon AWS',     'AS15169': 'Google Cloud',
    'AS8075':   'Microsoft Azure','AS13335': 'Cloudflare',
    'AS20473':  'Vultr',          'AS63949': 'Linode',
    'AS46484':  'PIA',            'AS209103':'Mullvad',
    'AS44814':  'NordVPN',        'AS212238':'ExpressVPN',
    'AS36352':  'ColoCrossing',   'AS40676': 'Psychz Networks',
    'AS32244':  'Liquid Web',     'AS26347': 'Namecheap',
    'AS22612':  'Namecheap',      'AS135134':'IPRoyal',
    'AS207990': 'ProtonVPN',      'AS199524':'G-Core',
    'AS48693':  'Ruvds',          'AS197540':'Hostkey',
}

# ── 2. ISP name keywords that indicate a VPN/hosting provider ────────────
VPN_ISP_KEYWORDS = [
    'vpn', 'proxy', 'hosting', 'server', 'datacenter', 'data center',
    'cloud', 'vps', 'dedicated', 'colocation', 'colo', 'cdn',
    'anonymous', 'privacy', 'anonymizer', 'nordvpn', 'expressvpn',
    'mullvad', 'proton', 'tunnelbear', 'cyberghost', 'ipvanish',
    'surfshark', 'hotspot shield', 'purevpn', 'hide.me', 'windscribe',
    'm247', 'ovh', 'hetzner', 'vultr', 'linode', 'digital ocean',
    'choopa', 'psychz', 'quadranet', 'tzulo', 'packetexchange',
]

# ── 3. Hostname keywords strongly indicating VPN ─────────────────────────
VPN_HOSTNAME_KEYWORDS = [
    'vpn', 'proxy', 'exit', 'relay', 'anon', 'tor', 'tunnel',
    'privacy', 'secure', 'hide', 'mask', 'cloak',
]

# ── 4. HTTP headers that reveal proxy/VPN usage ──────────────────────────
PROXY_REVEAL_HEADERS = [
    'HTTP_VIA',
    'HTTP_X_FORWARDED_FOR',
    'HTTP_FORWARDED',
    'HTTP_X_PROXY_ID',
    'HTTP_PROXY_CONNECTION',
    'HTTP_X_REAL_IP',
    'HTTP_FORWARDED_FOR',
    'HTTP_CLIENT_IP',
    'HTTP_X_CLUSTER_CLIENT_IP',
    'HTTP_CF_CONNECTING_IP',      # Cloudflare passes real IP
    'HTTP_X_FORWARDED_HOST',
    'HTTP_X_ORIGINATING_IP',
    'HTTP_USERAGENT_VIA',
    'HTTP_X_COMING_FROM',
    'HTTP_COMING_FROM',
]

# ── 5. Common VPN port numbers ───────────────────────────────────────────
VPN_PORTS = {
    1194: 'OpenVPN UDP/TCP',
    1195: 'OpenVPN alt',
    1196: 'OpenVPN alt',
    500:  'IPSec/IKEv2',
    4500: 'IPSec NAT-T',
    1701: 'L2TP',
    1723: 'PPTP',
    51820: 'WireGuard',
    8388: 'Shadowsocks',
    443:  'SSL VPN / OpenVPN-over-HTTPS',
    1080: 'SOCKS',
    8080: 'HTTP proxy',
    3128: 'Squid',
}

# Datacenter ASN prefixes (first match wins)
DATACENTER_ASN_PREFIXES = [
    'AS14061', 'AS16509', 'AS15169', 'AS8075', 'AS13335',
    'AS20940', 'AS20473', 'AS63949', 'AS16276', 'AS24940',
]


class VPNDetector:
    """
    Full production VPN detector.
    Runs 6 independent signals and combines confidence scores.
    """

    # Signal confidence weights (must sum <= 1.0; excess is capped at 1.0)
    WEIGHTS = {
        'asn_match':            0.45,  # Strongest signal
        'isp_keyword':          0.20,
        'hostname_keyword':     0.15,
        'proxy_headers':        0.10,
        'open_vpn_ports':       0.15,
        'db_malicious':         0.40,  # Known malicious DB entry
        'datacenter_asn':       0.10,
    }

    def __init__(self, ip_address: str, request_headers: Optional[dict] = None):
        self.ip_address = ip_address
        self.request_headers = request_headers or {}
        self.signals: dict = {}

    # ── Public API ────────────────────────────────────────────────────────

    def detect(self) -> dict:
        """
        Run all detection signals and return a structured result.
        Uses Redis cache (TTL=1h) to avoid repeated external calls.
        """
        cache_key = f"pi:vpn_detect:{self.ip_address}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        self._check_asn_and_isp()
        self._check_hostname()
        self._check_proxy_headers()
        self._check_open_ports()
        self._check_malicious_db()

        confidence = self._calculate_confidence()

        from ..constants import VPN_CONFIDENCE_THRESHOLD
        is_vpn = confidence >= VPN_CONFIDENCE_THRESHOLD

        result = {
            'ip_address':     self.ip_address,
            'is_vpn':         is_vpn,
            'confidence':     round(confidence, 4),
            'vpn_provider':   self.signals.get('asn_provider', ''),
            'asn':            self.signals.get('asn', ''),
            'isp':            self.signals.get('isp', ''),
            'hostname':       self.signals.get('hostname', ''),
            'proxy_headers':  self.signals.get('proxy_headers_found', []),
            'open_ports':     self.signals.get('open_ports', []),
            'signals':        self.signals,
            'detection_methods': self._triggered_methods(),
        }

        # Persist to VPNDetectionLog if detected
        if is_vpn:
            self._persist_log(result)

        cache.set(cache_key, result, 3600)
        return result

    @classmethod
    def quick_check(cls, ip_address: str, headers: dict = None) -> bool:
        """Fast boolean — uses cache first."""
        return cls(ip_address, headers).detect()['is_vpn']

    # ── Signal Checks ─────────────────────────────────────────────────────

    def _check_asn_and_isp(self):
        """
        Signal 1: ASN match against VPN provider map.
        Signal 2: ISP name keyword analysis.
        """
        try:
            from ..ip_intelligence.ip_asn_lookup import ASNLookup
            asn_info = ASNLookup.lookup(self.ip_address)
        except Exception as e:
            logger.debug(f"ASN lookup failed for {self.ip_address}: {e}")
            asn_info = {}

        asn = asn_info.get('asn', '').upper()
        isp = asn_info.get('isp', '').lower()
        org = asn_info.get('org', '').lower()
        combined_text = f"{isp} {org}"

        self.signals['asn'] = asn
        self.signals['isp'] = asn_info.get('isp', '')

        # ASN exact match
        if asn and asn in VPN_PROVIDER_ASN_MAP:
            self.signals['asn_match'] = True
            self.signals['asn_provider'] = VPN_PROVIDER_ASN_MAP[asn]
        else:
            self.signals['asn_match'] = False
            self.signals['asn_provider'] = ''

        # Datacenter ASN prefix
        self.signals['datacenter_asn'] = any(
            asn.startswith(prefix) for prefix in DATACENTER_ASN_PREFIXES
        ) if asn else False

        # ISP keyword match
        matched_isp_kw = [kw for kw in VPN_ISP_KEYWORDS if kw in combined_text]
        self.signals['isp_keyword'] = len(matched_isp_kw) > 0
        self.signals['isp_keywords_matched'] = matched_isp_kw

    def _check_hostname(self):
        """
        Signal 3: Reverse DNS hostname keyword analysis.
        """
        try:
            hostname, _, _ = socket.gethostbyaddr(self.ip_address)
            hostname_lower = hostname.lower()
            matched = [kw for kw in VPN_HOSTNAME_KEYWORDS if kw in hostname_lower]
            self.signals['hostname'] = hostname
            self.signals['hostname_keyword'] = len(matched) > 0
            self.signals['hostname_keywords_matched'] = matched
        except (socket.herror, socket.gaierror, OSError):
            self.signals['hostname'] = ''
            self.signals['hostname_keyword'] = False
            self.signals['hostname_keywords_matched'] = []

    def _check_proxy_headers(self):
        """
        Signal 4: HTTP header analysis.
        Non-empty VIA or X-Forwarded-For headers strongly suggest a proxy/VPN.
        """
        found = []
        for header in PROXY_REVEAL_HEADERS:
            value = self.request_headers.get(header, '')
            if value and value.strip():
                found.append({'header': header.replace('HTTP_', ''), 'value': value[:100]})

        self.signals['proxy_headers_found'] = found
        self.signals['proxy_headers'] = len(found) > 0

        # If X-Forwarded-For lists multiple IPs, it's definitely behind a proxy
        xff = self.request_headers.get('HTTP_X_FORWARDED_FOR', '')
        if xff and ',' in xff:
            self.signals['multi_hop_proxy'] = True
            self.signals['proxy_headers'] = True

    def _check_open_ports(self):
        """
        Signal 5: Non-blocking socket scan of critical VPN ports.
        Only checks 4 high-value ports to stay under 2s total.
        """
        SCAN_PORTS = [1194, 500, 51820, 1723]  # OpenVPN, IKE, WireGuard, PPTP
        open_ports = []

        for port in SCAN_PORTS:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.settimeout(0.4)
                result = sock.connect_ex((self.ip_address, port))
                sock.close()
                if result == 0:
                    open_ports.append({
                        'port': port,
                        'service': VPN_PORTS.get(port, 'Unknown')
                    })
            except Exception:
                pass

        self.signals['open_ports'] = open_ports
        self.signals['open_vpn_ports'] = len(open_ports) > 0

    def _check_malicious_db(self):
        """
        Signal 6: Check our local MaliciousIPDatabase for VPN/proxy entries.
        """
        try:
            from ..models import MaliciousIPDatabase
            from ..enums import ThreatType
            entry = MaliciousIPDatabase.objects.filter(
                ip_address=self.ip_address,
                threat_type__in=[ThreatType.VPN, ThreatType.PROXY],
                is_active=True
            ).first()
            if entry:
                self.signals['db_malicious'] = True
                self.signals['db_confidence'] = float(entry.confidence_score)
                self.signals['db_threat_type'] = entry.threat_type
            else:
                self.signals['db_malicious'] = False
                self.signals['db_confidence'] = 0.0
        except Exception as e:
            logger.debug(f"DB malicious check failed: {e}")
            self.signals['db_malicious'] = False
            self.signals['db_confidence'] = 0.0

    # ── Confidence Calculation ────────────────────────────────────────────

    def _calculate_confidence(self) -> float:
        score = 0.0

        if self.signals.get('asn_match'):
            score += self.WEIGHTS['asn_match']
        if self.signals.get('isp_keyword'):
            score += self.WEIGHTS['isp_keyword']
        if self.signals.get('hostname_keyword'):
            score += self.WEIGHTS['hostname_keyword']
        if self.signals.get('proxy_headers'):
            score += self.WEIGHTS['proxy_headers']
        if self.signals.get('open_vpn_ports'):
            score += self.WEIGHTS['open_vpn_ports']
        if self.signals.get('db_malicious'):
            # DB entry has its own stored confidence — use the higher value
            db_conf = self.signals.get('db_confidence', 0)
            score += max(self.WEIGHTS['db_malicious'], db_conf)
        if self.signals.get('datacenter_asn') and not self.signals.get('asn_match'):
            score += self.WEIGHTS['datacenter_asn']

        return min(score, 1.0)

    def _triggered_methods(self) -> list:
        methods = []
        if self.signals.get('asn_match'):         methods.append('asn_database')
        if self.signals.get('isp_keyword'):        methods.append('isp_keyword_analysis')
        if self.signals.get('hostname_keyword'):   methods.append('reverse_dns_analysis')
        if self.signals.get('proxy_headers'):      methods.append('http_header_analysis')
        if self.signals.get('open_vpn_ports'):     methods.append('port_scan')
        if self.signals.get('db_malicious'):       methods.append('threat_db_lookup')
        if self.signals.get('datacenter_asn'):     methods.append('datacenter_asn_match')
        return methods

    def _persist_log(self, result: dict):
        """Save VPN detection to database."""
        try:
            from ..models import VPNDetectionLog
            VPNDetectionLog.objects.create(
                ip_address=self.ip_address,
                vpn_provider=result.get('vpn_provider', ''),
                confidence_score=result['confidence'],
                detection_method=','.join(result.get('detection_methods', [])),
                is_confirmed=result['confidence'] >= 0.8,
            )
        except Exception as e:
            logger.debug(f"VPNDetectionLog save failed: {e}")
