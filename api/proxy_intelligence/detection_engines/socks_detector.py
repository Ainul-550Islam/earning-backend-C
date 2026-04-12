"""
SOCKS Proxy Detector  (PRODUCTION-READY — COMPLETE)
=====================================================
Detects SOCKS4/SOCKS5 proxy servers by:
  1. Port scan on well-known SOCKS ports (1080, 1081, 9050, 9150)
  2. SOCKS4/SOCKS5 protocol handshake (connect + read response)
  3. Tor SOCKS port detection (9050, 9150)
  4. Threat database cross-check
  5. ISP/org keyword matching against known SOCKS providers

SOCKS proxies are dangerous because they forward all traffic types
(HTTP, HTTPS, FTP, etc.) and many support UDP, making them harder
to detect than HTTP proxies.
"""
import logging
import socket
import struct
from typing import Optional

from django.core.cache import cache

logger = logging.getLogger(__name__)

# ── SOCKS Port Registry ────────────────────────────────────────────────────
SOCKS_PORTS = {
    1080:  {'type': 'SOCKS4/5',      'risk': 'high'},
    1081:  {'type': 'SOCKS5-alt',    'risk': 'high'},
    1082:  {'type': 'SOCKS5-alt',    'risk': 'medium'},
    1083:  {'type': 'SOCKS5-alt',    'risk': 'medium'},
    9050:  {'type': 'Tor-SOCKS5',    'risk': 'critical'},
    9150:  {'type': 'Tor-Browser',   'risk': 'critical'},
    4145:  {'type': 'SOCKS5-common', 'risk': 'high'},
    1085:  {'type': 'SOCKS5-alt',    'risk': 'medium'},
    10800: {'type': 'SOCKS5-alt',    'risk': 'medium'},
    10801: {'type': 'SOCKS5-alt',    'risk': 'medium'},
}

# SOCKS5 greeting — version 5, 1 auth method, no auth required
SOCKS5_GREETING     = b'\x05\x01\x00'
# SOCKS4 connect request to 0.0.0.0:80 (minimal probe)
SOCKS4_PROBE        = b'\x04\x01\x00\x50\x00\x00\x00\x01\x00'
# Expected SOCKS5 response prefix (version=5, no-auth accepted)
SOCKS5_EXPECTED_PREFIX = b'\x05\x00'
# Expected SOCKS4 response prefix (version=0, request granted=0x5a)
SOCKS4_EXPECTED_PREFIX = b'\x00\x5a'

# ISP keywords that indicate SOCKS proxy providers
SOCKS_ISP_KEYWORDS = [
    'socks', 'proxy', 'proxies', 'anon', 'anonymous',
    'tunnel', 'vpn', 'hosting', 'server', 'vps',
]


class SOCKSDetector:
    """
    Detects SOCKS4/SOCKS5 proxies via port scanning and protocol handshake.

    Usage:
        detector = SOCKSDetector('1.2.3.4')
        result = detector.detect()
        if result['is_socks']:
            print(result['socks_type'])  # e.g. 'SOCKS5'
    """

    # Ports to scan in fast mode (top 4 most common)
    FAST_SCAN_PORTS = [1080, 9050, 9150, 4145]
    # Ports to scan in full mode (all known SOCKS ports)
    FULL_SCAN_PORTS = list(SOCKS_PORTS.keys())

    CONNECT_TIMEOUT = 0.5   # seconds per port scan attempt
    HANDSHAKE_TIMEOUT = 1.0  # seconds for protocol handshake

    def __init__(self, ip_address: str,
                 isp: str = '',
                 org: str = '',
                 fast_mode: bool = True):
        """
        Args:
            ip_address: IP to check
            isp:        ISP name (from geo lookup) for keyword matching
            org:        Organization name
            fast_mode:  If True, only scan top 4 ports (faster, less thorough)
        """
        self.ip_address = ip_address
        self.isp        = (isp + ' ' + org).lower()
        self.fast_mode  = fast_mode
        self.signals: dict = {}

    # ── Public API ─────────────────────────────────────────────────────────

    def detect(self) -> dict:
        """
        Run all SOCKS detection signals.

        Returns:
            {
                'ip_address':    str,
                'is_socks':      bool,
                'is_tor_socks':  bool,
                'socks_type':    str,   # 'SOCKS4', 'SOCKS5', 'Tor-SOCKS5', etc.
                'open_ports':    list,
                'handshake_confirmed': bool,
                'confidence':    float,
                'detection_methods': list,
            }
        """
        cache_key = f"pi:socks:{self.ip_address}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        self._scan_ports()
        self._perform_handshakes()
        self._check_threat_db()
        self._check_isp_keywords()

        confidence = self._calculate_confidence()

        socks_type  = self._determine_socks_type()
        is_tor      = self.signals.get('has_tor_ports', False)

        result = {
            'ip_address':          self.ip_address,
            'is_socks':            confidence >= 0.60,
            'is_tor_socks':        is_tor,
            'socks_type':          socks_type,
            'open_socks_ports':    self.signals.get('open_ports', []),
            'handshake_confirmed': self.signals.get('handshake_socks5', False) or
                                   self.signals.get('handshake_socks4', False),
            'confidence':          round(confidence, 4),
            'signals':             self.signals,
            'detection_methods':   self._triggered_methods(),
            'proxy_type_detail':   'tor' if is_tor else 'socks',
        }

        if result['is_socks']:
            self._persist_log(result)

        cache.set(cache_key, result, 1800)
        return result

    @classmethod
    def quick_check(cls, ip_address: str) -> bool:
        """Fast boolean SOCKS check."""
        return cls(ip_address, fast_mode=True).detect()['is_socks']

    # ── Signal Checks ──────────────────────────────────────────────────────

    def _scan_ports(self):
        """Signal 1: TCP connect scan on SOCKS ports."""
        ports_to_scan = self.FAST_SCAN_PORTS if self.fast_mode else self.FULL_SCAN_PORTS
        open_ports    = []
        tor_ports     = []

        for port in ports_to_scan:
            if self._is_port_open(port):
                port_info = SOCKS_PORTS.get(port, {})
                entry = {
                    'port':    port,
                    'type':    port_info.get('type', 'SOCKS'),
                    'risk':    port_info.get('risk', 'medium'),
                }
                open_ports.append(entry)
                if port in (9050, 9150):
                    tor_ports.append(port)

        self.signals['open_ports']     = open_ports
        self.signals['has_open_ports'] = len(open_ports) > 0
        self.signals['has_tor_ports']  = len(tor_ports) > 0
        self.signals['tor_ports']      = tor_ports

    def _perform_handshakes(self):
        """Signal 2: Attempt SOCKS4/SOCKS5 protocol handshake on open ports."""
        self.signals['handshake_socks5'] = False
        self.signals['handshake_socks4'] = False
        self.signals['handshake_port']   = None

        if not self.signals.get('has_open_ports'):
            return

        # Try SOCKS5 first (more common)
        for port_info in self.signals.get('open_ports', []):
            port = port_info['port']
            if self._verify_socks5(port):
                self.signals['handshake_socks5'] = True
                self.signals['handshake_port']   = port
                self.signals['confirmed_type']   = 'SOCKS5'
                return

        # Try SOCKS4 as fallback
        for port_info in self.signals.get('open_ports', []):
            port = port_info['port']
            if self._verify_socks4(port):
                self.signals['handshake_socks4'] = True
                self.signals['handshake_port']   = port
                self.signals['confirmed_type']   = 'SOCKS4'
                return

    def _check_threat_db(self):
        """Signal 3: MaliciousIPDatabase cross-check for SOCKS proxies."""
        try:
            from ..models import MaliciousIPDatabase
            from ..enums import ThreatType
            entry = MaliciousIPDatabase.objects.filter(
                ip_address=self.ip_address,
                threat_type=ThreatType.PROXY,
                is_active=True,
            ).first()
            self.signals['db_threat_match'] = entry is not None
            self.signals['db_confidence']   = (
                float(entry.confidence_score) if entry else 0.0
            )
        except Exception as e:
            logger.debug(f"Threat DB check failed for {self.ip_address}: {e}")
            self.signals['db_threat_match'] = False
            self.signals['db_confidence']   = 0.0

    def _check_isp_keywords(self):
        """Signal 4: ISP/org name keyword matching."""
        matched = [kw for kw in SOCKS_ISP_KEYWORDS if kw in self.isp]
        self.signals['isp_keyword_match'] = len(matched) > 0
        self.signals['isp_keywords']      = matched

    # ── Protocol Handshake Verification ───────────────────────────────────

    def _verify_socks5(self, port: int) -> bool:
        """
        Verify SOCKS5 by sending the client greeting and
        checking the server responds with version=5.
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(self.HANDSHAKE_TIMEOUT)
                sock.connect((self.ip_address, port))
                sock.sendall(SOCKS5_GREETING)
                response = sock.recv(2)
                # SOCKS5 server must reply with \x05\x00 (version=5, no-auth)
                return response[:2] == SOCKS5_EXPECTED_PREFIX
        except Exception:
            return False

    def _verify_socks4(self, port: int) -> bool:
        """
        Verify SOCKS4 by sending a minimal CONNECT request
        and checking for an 8-byte response starting with \x00\x5a.
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(self.HANDSHAKE_TIMEOUT)
                sock.connect((self.ip_address, port))
                sock.sendall(SOCKS4_PROBE)
                response = sock.recv(8)
                return len(response) >= 2 and response[:2] == SOCKS4_EXPECTED_PREFIX
        except Exception:
            return False

    # ── Port Scan Helper ───────────────────────────────────────────────────

    def _is_port_open(self, port: int) -> bool:
        """Fast TCP connect check."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(self.CONNECT_TIMEOUT)
                return sock.connect_ex((self.ip_address, port)) == 0
        except Exception:
            return False

    # ── Confidence & Classification ────────────────────────────────────────

    def _calculate_confidence(self) -> float:
        score = 0.0

        # Handshake confirmed — highest confidence
        if self.signals.get('handshake_socks5') or self.signals.get('handshake_socks4'):
            score += 0.85

        # Open Tor ports — very high confidence
        if self.signals.get('has_tor_ports'):
            score += 0.80

        # Open non-Tor SOCKS ports without handshake confirmation
        elif self.signals.get('has_open_ports'):
            score += 0.50

        # Threat DB
        if self.signals.get('db_threat_match'):
            db_conf = self.signals.get('db_confidence', 0)
            score = max(score, db_conf * 0.90)

        # ISP keywords (weak signal alone)
        if self.signals.get('isp_keyword_match'):
            score += 0.10

        return min(score, 1.0)

    def _determine_socks_type(self) -> str:
        if self.signals.get('has_tor_ports'):
            return 'Tor-SOCKS5'
        if self.signals.get('handshake_socks5'):
            return 'SOCKS5'
        if self.signals.get('handshake_socks4'):
            return 'SOCKS4'
        if self.signals.get('has_open_ports'):
            # Guess from port
            for p_info in self.signals.get('open_ports', []):
                return p_info.get('type', 'SOCKS4/5')
        return ''

    def _triggered_methods(self) -> list:
        methods = []
        if self.signals.get('has_open_ports'):
            methods.append('port_scan')
        if self.signals.get('handshake_socks5'):
            methods.append('socks5_handshake')
        if self.signals.get('handshake_socks4'):
            methods.append('socks4_handshake')
        if self.signals.get('has_tor_ports'):
            methods.append('tor_port_detection')
        if self.signals.get('db_threat_match'):
            methods.append('threat_db_lookup')
        if self.signals.get('isp_keyword_match'):
            methods.append('isp_keyword_match')
        return methods

    def _persist_log(self, result: dict):
        """Save detection to ProxyDetectionLog."""
        try:
            from ..models import ProxyDetectionLog
            proxy_type = 'tor' if result.get('is_tor_socks') else 'socks5'
            ProxyDetectionLog.objects.create(
                ip_address       = self.ip_address,
                proxy_type       = proxy_type,
                proxy_port       = (
                    result['open_socks_ports'][0]['port']
                    if result['open_socks_ports'] else None
                ),
                confidence_score = result['confidence'],
                is_anonymous     = True,
                is_elite         = result.get('handshake_confirmed', False),
                headers_detected = [],
            )
        except Exception as e:
            logger.debug(f"SOCKSDetector log save failed: {e}")
