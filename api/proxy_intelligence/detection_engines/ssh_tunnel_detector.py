"""
SSH Tunnel Detector  (PRODUCTION-READY — COMPLETE)
====================================================
Detects SSH-based tunneling and reverse proxy configurations.

SSH tunnels are used to bypass network restrictions by forwarding
traffic through an encrypted SSH connection. Common attack patterns:
  - Dynamic port forwarding (ssh -D): SOCKS5 over SSH
  - Local port forwarding: forward specific ports through SSH
  - Remote port forwarding: expose internal services via SSH
  - SSH jump hosts: multi-hop SSH chains

Detection signals:
  1. Port scan on common SSH ports (22, 2222, 2200, 22222)
  2. SSH banner grab and version extraction
  3. Non-standard SSH port usage (security-through-obscurity)
  4. OpenSSH version fingerprinting (old versions = higher risk)
  5. ISP/org keyword analysis for VPS/hosting providers
  6. Threat database cross-check
  7. SSH combined with other proxy signals
"""
import logging
import re
import socket
from typing import Optional, Tuple

from django.core.cache import cache

logger = logging.getLogger(__name__)

# ── SSH Port Registry ──────────────────────────────────────────────────────
SSH_PORTS = {
    22:    {'standard': True,  'risk': 'low',    'label': 'SSH-standard'},
    222:   {'standard': False, 'risk': 'medium', 'label': 'SSH-alt'},
    2222:  {'standard': False, 'risk': 'medium', 'label': 'SSH-alt'},
    2200:  {'standard': False, 'risk': 'medium', 'label': 'SSH-alt'},
    22222: {'standard': False, 'risk': 'medium', 'label': 'SSH-alt'},
    8022:  {'standard': False, 'risk': 'medium', 'label': 'SSH-alt'},
    10022: {'standard': False, 'risk': 'medium', 'label': 'SSH-alt'},
    22000: {'standard': False, 'risk': 'medium', 'label': 'SSH-alt'},
}

# ── Minimum SSH version risk thresholds ───────────────────────────────────
# Versions below these are EOL and may be running on attacker-controlled servers.
OUTDATED_OPENSSH_VERSION = 7.0  # Versions < 7.0 are very old

# ── ISP keywords indicating VPS/hosting (SSH tunnels are common on these) ──
SSH_HOSTING_KEYWORDS = [
    'hetzner', 'ovh', 'digitalocean', 'vultr', 'linode', 'amazon aws',
    'google cloud', 'azure', 'server', 'hosting', 'vps', 'dedicated',
    'colocation', 'data center', 'cloud',
]


class SSHTunnelDetector:
    """
    Detects SSH servers and evaluates tunnel risk.

    Note: Finding an SSH port open is NOT necessarily malicious —
    many legitimate servers run SSH. The risk comes from combining
    SSH with other proxy signals or from non-standard configurations.

    Usage:
        detector = SSHTunnelDetector('1.2.3.4', isp='Hetzner Online')
        result = detector.detect()
    """

    CONNECT_TIMEOUT  = 0.5   # seconds for port scan
    BANNER_TIMEOUT   = 1.5   # seconds to read SSH banner
    SCAN_PORTS       = [22, 2222, 2200, 22222, 8022]  # Top 5 ports

    def __init__(self, ip_address: str,
                 isp: str = '',
                 org: str = '',
                 has_other_proxy_signals: bool = False):
        """
        Args:
            ip_address:              IP to check
            isp:                     ISP name for hosting keyword check
            org:                     Organization name
            has_other_proxy_signals: Set True if VPN/proxy was already detected
                                     — SSH + proxy = very high risk
        """
        self.ip_address             = ip_address
        self.isp                    = (isp + ' ' + org).lower()
        self.has_other_proxy_signals = has_other_proxy_signals
        self.signals: dict          = {}

    # ── Public API ─────────────────────────────────────────────────────────

    def detect(self) -> dict:
        """
        Run all SSH tunnel detection signals.

        Returns:
            {
                'ip_address':      str,
                'is_ssh_server':   bool,  # SSH port found open
                'is_ssh_tunnel':   bool,  # High risk of being used as tunnel
                'ssh_version':     str,   # e.g. 'OpenSSH_8.9p1'
                'open_ssh_ports':  list,
                'confidence':      float,
                'signals':         dict,
                'detection_methods': list,
            }
        """
        cache_key = f"pi:ssh:{self.ip_address}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        self._scan_ports()
        self._grab_banners()
        self._check_isp_keywords()
        self._check_threat_db()
        self._check_combined_signals()

        confidence = self._calculate_confidence()

        result = {
            'ip_address':        self.ip_address,
            'is_ssh_server':     self.signals.get('has_open_ssh_ports', False),
            'is_ssh_tunnel':     confidence >= 0.55,
            'confidence':        round(confidence, 4),
            'ssh_version':       self.signals.get('ssh_version', ''),
            'ssh_vendor':        self.signals.get('ssh_vendor', ''),
            'is_outdated_ssh':   self.signals.get('is_outdated_ssh', False),
            'open_ssh_ports':    self.signals.get('open_ports', []),
            'has_non_standard_port': self.signals.get('has_non_standard_port', False),
            'signals':           self.signals,
            'detection_methods': self._triggered_methods(),
        }

        cache.set(cache_key, result, 3600)
        return result

    @classmethod
    def quick_check(cls, ip_address: str, isp: str = '') -> bool:
        """Fast boolean SSH tunnel risk check."""
        return cls(ip_address, isp=isp).detect()['is_ssh_tunnel']

    # ── Signal Checks ──────────────────────────────────────────────────────

    def _scan_ports(self):
        """Signal 1: TCP connect scan on SSH ports."""
        open_ports         = []
        has_non_standard   = False

        for port in self.SCAN_PORTS:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(self.CONNECT_TIMEOUT)
                    if s.connect_ex((self.ip_address, port)) == 0:
                        port_info = SSH_PORTS.get(port, {})
                        open_ports.append({
                            'port':     port,
                            'standard': port_info.get('standard', port == 22),
                            'risk':     port_info.get('risk', 'medium'),
                            'label':    port_info.get('label', 'SSH-alt'),
                        })
                        if port != 22:
                            has_non_standard = True
            except Exception:
                pass

        self.signals['open_ports']             = open_ports
        self.signals['has_open_ssh_ports']     = len(open_ports) > 0
        self.signals['has_non_standard_port']  = has_non_standard
        self.signals['open_port_count']        = len(open_ports)

    def _grab_banners(self):
        """Signal 2: Read SSH version banner from open ports."""
        self.signals['ssh_version']       = ''
        self.signals['ssh_vendor']        = ''
        self.signals['is_outdated_ssh']   = False
        self.signals['banner_raw']        = ''

        for port_info in self.signals.get('open_ports', []):
            port   = port_info['port']
            banner = self._read_banner(port)
            if banner:
                self.signals['banner_raw'] = banner[:200]
                version, vendor, is_old = self._parse_banner(banner)
                self.signals['ssh_version']     = version
                self.signals['ssh_vendor']      = vendor
                self.signals['is_outdated_ssh'] = is_old
                return  # Use first successful banner

    def _check_isp_keywords(self):
        """Signal 3: ISP/org hosting keyword match."""
        matched = [kw for kw in SSH_HOSTING_KEYWORDS if kw in self.isp]
        self.signals['isp_hosting_keyword'] = len(matched) > 0
        self.signals['isp_keywords_matched'] = matched

    def _check_threat_db(self):
        """Signal 4: Threat database lookup for known SSH tunnel IPs."""
        try:
            from ..models import MaliciousIPDatabase
            from ..enums import ThreatType
            entry = MaliciousIPDatabase.objects.filter(
                ip_address=self.ip_address,
                threat_type__in=[ThreatType.PROXY, ThreatType.MALWARE],
                is_active=True,
            ).first()
            self.signals['db_threat_match'] = entry is not None
            self.signals['db_confidence']   = (
                float(entry.confidence_score) if entry else 0.0
            )
        except Exception as e:
            logger.debug(f"Threat DB check failed: {e}")
            self.signals['db_threat_match'] = False
            self.signals['db_confidence']   = 0.0

    def _check_combined_signals(self):
        """Signal 5: SSH + other proxy signals = very high risk."""
        ssh_open = self.signals.get('has_open_ssh_ports', False)
        self.signals['ssh_plus_proxy'] = (
            ssh_open and self.has_other_proxy_signals
        )

    # ── Banner Parsing ─────────────────────────────────────────────────────

    def _read_banner(self, port: int) -> str:
        """Read the SSH version banner from the server."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(self.BANNER_TIMEOUT)
                s.connect((self.ip_address, port))
                banner = s.recv(256).decode('utf-8', errors='ignore').strip()
                return banner
        except Exception:
            return ''

    def _parse_banner(self, banner: str) -> Tuple[str, str, bool]:
        """
        Parse SSH banner string like 'SSH-2.0-OpenSSH_8.9p1 Ubuntu-3ubuntu0.1'.

        Returns:
            (version_string, vendor_name, is_outdated)
        """
        version    = ''
        vendor     = ''
        is_outdated = False

        if not banner.startswith('SSH-'):
            return version, vendor, is_outdated

        # Extract version info
        match = re.search(
            r'SSH-\d+\.\d+-(\S+)',
            banner,
        )
        if match:
            version = match.group(1)

        # Identify vendor
        banner_lower = banner.lower()
        if 'openssh' in banner_lower:
            vendor = 'OpenSSH'
            # Check version number
            ver_match = re.search(r'openssh[_\-](\d+\.\d+)', banner_lower)
            if ver_match:
                try:
                    ver_num = float(ver_match.group(1))
                    is_outdated = ver_num < OUTDATED_OPENSSH_VERSION
                except ValueError:
                    pass
        elif 'dropbear' in banner_lower:
            vendor = 'Dropbear'  # Lightweight SSH server, common on embedded
        elif 'bitvise' in banner_lower:
            vendor = 'Bitvise'
        elif 'libssh' in banner_lower:
            vendor = 'libssh'
        elif 'cisco' in banner_lower:
            vendor = 'Cisco'
        else:
            vendor = 'Unknown'

        return version, vendor, is_outdated

    # ── Confidence & Classification ────────────────────────────────────────

    def _calculate_confidence(self) -> float:
        score = 0.0

        # SSH + proxy signals together = very strong indicator
        if self.signals.get('ssh_plus_proxy'):
            score += 0.70

        # Non-standard SSH port on hosting ISP
        if (self.signals.get('has_non_standard_port') and
                self.signals.get('isp_hosting_keyword')):
            score += 0.40

        # Outdated SSH version (attacker-controlled servers)
        if self.signals.get('is_outdated_ssh'):
            score += 0.25

        # Multiple SSH ports open
        if self.signals.get('open_port_count', 0) >= 2:
            score += 0.20

        # Single standard SSH port on hosting ISP (mild signal)
        if (self.signals.get('has_open_ssh_ports') and
                self.signals.get('isp_hosting_keyword') and
                not self.signals.get('has_non_standard_port')):
            score += 0.15

        # Threat DB hit
        if self.signals.get('db_threat_match'):
            db_conf = self.signals.get('db_confidence', 0)
            score = max(score, db_conf * 0.85)

        return min(score, 1.0)

    def _triggered_methods(self) -> list:
        methods = []
        if self.signals.get('has_open_ssh_ports'):
            methods.append('ssh_port_scan')
        if self.signals.get('ssh_version'):
            methods.append('ssh_banner_grab')
        if self.signals.get('is_outdated_ssh'):
            methods.append('ssh_version_analysis')
        if self.signals.get('has_non_standard_port'):
            methods.append('non_standard_port')
        if self.signals.get('isp_hosting_keyword'):
            methods.append('hosting_isp_match')
        if self.signals.get('db_threat_match'):
            methods.append('threat_db_lookup')
        if self.signals.get('ssh_plus_proxy'):
            methods.append('ssh_proxy_combination')
        return methods
