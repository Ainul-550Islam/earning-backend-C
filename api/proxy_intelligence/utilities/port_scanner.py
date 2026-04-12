"""
Port Scanner Utility  (PRODUCTION-READY — COMPLETE)
=====================================================
Lightweight, non-aggressive TCP port scanner for proxy and
VPN detection. Used by detection engines to identify open
proxy/VPN/SOCKS ports on suspicious IPs.

Design principles:
  - Low-impact: short timeouts, limited port range
  - Result caching to avoid repeated scans
  - Thread-safe for concurrent use
  - Never performs UDP scans (avoid IDS triggers)
  - Respects timeout limits for use in request middleware
"""
import logging
import socket
import concurrent.futures
from typing import List, Dict, Optional

from django.core.cache import cache

logger = logging.getLogger(__name__)

# ── Port Registry ──────────────────────────────────────────────────────────
# All ports relevant to proxy/VPN detection
KNOWN_PROXY_PORTS = {
    # HTTP Proxies
    80:    {'service': 'HTTP',         'type': 'http',        'risk': 'low'},
    443:   {'service': 'HTTPS',        'type': 'http',        'risk': 'low'},
    8080:  {'service': 'HTTP-Proxy',   'type': 'http',        'risk': 'high'},
    8081:  {'service': 'HTTP-alt',     'type': 'http',        'risk': 'high'},
    8888:  {'service': 'HTTP-Proxy',   'type': 'http',        'risk': 'high'},
    3128:  {'service': 'Squid',        'type': 'http',        'risk': 'high'},
    8118:  {'service': 'Privoxy',      'type': 'http',        'risk': 'high'},
    8123:  {'service': 'Polipo',       'type': 'http',        'risk': 'medium'},
    # SOCKS Proxies
    1080:  {'service': 'SOCKS4/5',     'type': 'socks',       'risk': 'high'},
    1081:  {'service': 'SOCKS5-alt',   'type': 'socks',       'risk': 'high'},
    4145:  {'service': 'SOCKS5',       'type': 'socks',       'risk': 'high'},
    # VPN Protocols
    1194:  {'service': 'OpenVPN UDP',  'type': 'vpn',         'risk': 'high'},
    1195:  {'service': 'OpenVPN-alt',  'type': 'vpn',         'risk': 'high'},
    500:   {'service': 'IPSec/IKEv2',  'type': 'vpn',         'risk': 'high'},
    4500:  {'service': 'IPSec-NAT',    'type': 'vpn',         'risk': 'high'},
    1701:  {'service': 'L2TP',         'type': 'vpn',         'risk': 'medium'},
    1723:  {'service': 'PPTP',         'type': 'vpn',         'risk': 'medium'},
    51820: {'service': 'WireGuard',    'type': 'vpn',         'risk': 'high'},
    8388:  {'service': 'Shadowsocks',  'type': 'vpn',         'risk': 'high'},
    # Tor
    9050:  {'service': 'Tor-SOCKS5',   'type': 'tor',         'risk': 'critical'},
    9150:  {'service': 'Tor-Browser',  'type': 'tor',         'risk': 'critical'},
    # SSH Tunnels
    22:    {'service': 'SSH',          'type': 'ssh',         'risk': 'low'},
    2222:  {'service': 'SSH-alt',      'type': 'ssh',         'risk': 'medium'},
}

# ── Port Groups for Focused Scanning ──────────────────────────────────────
PORT_GROUP_VPN    = [1194, 1195, 500, 4500, 51820, 1723, 8388]
PORT_GROUP_SOCKS  = [1080, 1081, 4145, 9050, 9150]
PORT_GROUP_HTTP   = [8080, 8081, 8888, 3128, 8118]
PORT_GROUP_SSH    = [22, 222, 2222, 2200]
PORT_GROUP_ALL    = list(KNOWN_PROXY_PORTS.keys())
PORT_GROUP_FAST   = [1080, 1194, 3128, 8080, 9050, 51820]  # Top 6 — fastest check


class PortScanner:
    """
    Non-aggressive TCP port scanner for proxy/VPN detection.

    Usage:
        scanner = PortScanner('1.2.3.4', timeout=0.5)
        results = scanner.scan(PORT_GROUP_FAST)
        open_ports = [r for r in results if r['is_open']]
    """

    def __init__(self, ip_address: str,
                 timeout: float     = 0.5,
                 max_workers: int   = 5,
                 cache_results: bool = True):
        """
        Args:
            ip_address:    Target IP address
            timeout:       Socket connect timeout per port (seconds)
            max_workers:   Max concurrent scan threads
            cache_results: Cache scan results in Redis
        """
        self.ip_address    = ip_address
        self.timeout       = timeout
        self.max_workers   = max_workers
        self.cache_results = cache_results

    # ── Main Scan Methods ──────────────────────────────────────────────────

    def scan(self, ports: List[int]) -> List[Dict]:
        """
        Scan a list of ports concurrently.

        Args:
            ports: List of port numbers to scan

        Returns:
            List of {port, is_open, service, type, risk} dicts
        """
        if not ports:
            return []

        cache_key = f"pi:portscan:{self.ip_address}:{'-'.join(map(str, sorted(ports)))}"
        if self.cache_results:
            cached = cache.get(cache_key)
            if cached is not None:
                return cached

        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_port = {
                executor.submit(self._check_port, port): port
                for port in ports
            }
            for future in concurrent.futures.as_completed(future_to_port):
                port   = future_to_port[future]
                try:
                    is_open = future.result()
                except Exception:
                    is_open = False

                port_info = KNOWN_PROXY_PORTS.get(port, {})
                results.append({
                    'port':    port,
                    'is_open': is_open,
                    'service': port_info.get('service', 'unknown'),
                    'type':    port_info.get('type', 'unknown'),
                    'risk':    port_info.get('risk', 'medium'),
                })

        # Sort by port number for consistent output
        results.sort(key=lambda x: x['port'])

        if self.cache_results:
            cache.set(cache_key, results, 1800)

        return results

    def scan_vpn(self) -> List[Dict]:
        """Scan VPN-specific ports (OpenVPN, WireGuard, IPSec, etc.)."""
        return self.scan(PORT_GROUP_VPN)

    def scan_socks(self) -> List[Dict]:
        """Scan SOCKS proxy ports."""
        return self.scan(PORT_GROUP_SOCKS)

    def scan_http_proxy(self) -> List[Dict]:
        """Scan HTTP/HTTPS proxy ports."""
        return self.scan(PORT_GROUP_HTTP)

    def scan_fast(self) -> List[Dict]:
        """Quick scan of top 6 most common proxy/VPN ports."""
        return self.scan(PORT_GROUP_FAST)

    def scan_all(self) -> List[Dict]:
        """Full scan of all known proxy/VPN ports."""
        return self.scan(PORT_GROUP_ALL)

    # ── Analysis Helpers ───────────────────────────────────────────────────

    def get_open_ports(self, ports: List[int] = None) -> List[Dict]:
        """Return only open ports from a scan."""
        results = self.scan(ports or PORT_GROUP_FAST)
        return [r for r in results if r['is_open']]

    def get_risk_summary(self, ports: List[int] = None) -> dict:
        """
        Scan ports and return a risk-level summary.

        Returns:
            {
                'has_open_ports':   bool,
                'open_port_count':  int,
                'highest_risk':     str ('critical'|'high'|'medium'|'low'|'none')
                'detected_types':   list of proxy types detected,
                'open_ports':       list of open port dicts,
                'vpn_ports':        list of open VPN port numbers,
                'proxy_ports':      list of open proxy port numbers,
                'tor_ports':        list of open Tor port numbers,
                'ssh_ports':        list of open SSH port numbers,
            }
        """
        results    = self.scan(ports or PORT_GROUP_FAST)
        open_ports = [r for r in results if r['is_open']]

        if not open_ports:
            return {
                'has_open_ports': False, 'open_port_count': 0,
                'highest_risk': 'none', 'detected_types': [],
                'open_ports': [], 'vpn_ports': [], 'proxy_ports': [],
                'tor_ports': [], 'ssh_ports': [],
            }

        risk_order   = {'critical': 4, 'high': 3, 'medium': 2, 'low': 1}
        highest_risk = max(open_ports, key=lambda x: risk_order.get(x['risk'], 0))['risk']
        types        = list(set(p['type'] for p in open_ports))

        return {
            'has_open_ports': True,
            'open_port_count': len(open_ports),
            'highest_risk':    highest_risk,
            'detected_types':  types,
            'open_ports':      open_ports,
            'vpn_ports':       [p['port'] for p in open_ports if p['type'] == 'vpn'],
            'proxy_ports':     [p['port'] for p in open_ports if p['type'] in ('http', 'socks')],
            'tor_ports':       [p['port'] for p in open_ports if p['type'] == 'tor'],
            'ssh_ports':       [p['port'] for p in open_ports if p['type'] == 'ssh'],
        }

    # ── Single Port Checks ─────────────────────────────────────────────────

    @staticmethod
    def is_port_open(ip_address: str, port: int,
                      timeout: float = 0.5) -> bool:
        """
        Check if a single port is open on a remote host.
        This is the static convenience version.
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(timeout)
                return sock.connect_ex((ip_address, port)) == 0
        except Exception:
            return False

    @staticmethod
    def grab_banner(ip_address: str, port: int,
                     timeout: float = 1.5,
                     send_bytes: bytes = b'') -> str:
        """
        Grab a service banner from an open port.

        Args:
            ip_address:  Target IP
            port:        Target port
            timeout:     Read timeout
            send_bytes:  Optional bytes to send before reading (e.g. HTTP request)

        Returns:
            Banner string (up to 512 bytes), or '' on failure
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(timeout)
                sock.connect((ip_address, port))
                if send_bytes:
                    sock.sendall(send_bytes)
                banner = sock.recv(512).decode('utf-8', errors='ignore').strip()
                return banner[:300]
        except Exception:
            return ''

    # ── Private Helpers ────────────────────────────────────────────────────

    def _check_port(self, port: int) -> bool:
        """Thread-safe single port check."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(self.timeout)
                return sock.connect_ex((self.ip_address, port)) == 0
        except Exception:
            return False


# ── Module-level convenience functions ────────────────────────────────────

def quick_proxy_scan(ip_address: str, timeout: float = 0.4) -> dict:
    """
    One-liner: fast proxy scan with risk summary.
    Scans top 6 ports in parallel, returns risk summary.
    """
    scanner = PortScanner(ip_address, timeout=timeout, max_workers=6)
    return scanner.get_risk_summary(PORT_GROUP_FAST)


def check_tor_ports(ip_address: str) -> bool:
    """Return True if Tor SOCKS ports (9050, 9150) are open."""
    return any(
        PortScanner.is_port_open(ip_address, port)
        for port in [9050, 9150]
    )


def check_vpn_ports(ip_address: str) -> list:
    """Return list of open VPN port numbers."""
    scanner = PortScanner(ip_address, timeout=0.4)
    open_ports = scanner.get_open_ports(PORT_GROUP_VPN)
    return [p['port'] for p in open_ports]
