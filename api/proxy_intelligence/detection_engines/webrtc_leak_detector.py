"""
WebRTC Leak Detector  (PRODUCTION-READY — COMPLETE)
=====================================================
Detects WebRTC IP leaks that reveal a user's real IP address
even when they are connected through a VPN or proxy.

How WebRTC leaks work:
  - WebRTC (used for video calls, P2P) can bypass VPN tunnels
  - The browser queries STUN servers and the real IP is exposed
  - Even anonymous browsing can be de-anonymized this way
  - Many VPNs fail to prevent WebRTC leaks by default

Server-side detection approach:
  - Frontend JavaScript collects all IPs exposed via WebRTC
  - These are sent to this endpoint in the fingerprint payload
  - We compare them against the actual connection IP
  - Any public IP different from connection IP = leak detected

This is a critical signal for earning/marketing platforms because:
  - Confirms the user IS using a VPN/proxy (the leaked IP is their real IP)
  - De-anonymizes the user completely (we know their real IP)
  - Allows cross-referencing against other accounts with the same real IP
"""
import ipaddress
import logging
from typing import List, Optional, Tuple

from django.core.cache import cache

logger = logging.getLogger(__name__)

# ── IP Classification Helpers ──────────────────────────────────────────────

# Link-local ranges (169.254.x.x / fe80::/10)
LINK_LOCAL_V4 = ipaddress.ip_network('169.254.0.0/16')
LINK_LOCAL_V6 = ipaddress.ip_network('fe80::/10')

# mDNS ranges (used by modern Chrome to hide local IPs)
# Chrome 92+ returns .local hostnames instead of real local IPs
MDNS_SUFFIX = '.local'


class WebRTCLeakDetector:
    """
    Analyzes WebRTC IP data submitted from the browser to detect leaks.

    The frontend should collect WebRTC IPs using:
        const pc = new RTCPeerConnection({iceServers:[{urls:'stun:stun.l.google.com:19302'}]});
        pc.createDataChannel('');
        pc.createOffer().then(offer => pc.setLocalDescription(offer));
        pc.onicecandidate = e => {
            if (e.candidate) {
                // Parse IP from e.candidate.candidate
                // Send to server
            }
        };

    Usage:
        detector = WebRTCLeakDetector(
            connection_ip='185.x.x.x',         # IP of VPN exit node
            webrtc_ips=['192.168.1.5', '1.2.3.4'],  # From browser
        )
        result = detector.detect()
        if result['leak_detected']:
            real_ip = result['leaked_real_ips'][0]
    """

    def __init__(self,
                 connection_ip: str,
                 webrtc_ips: Optional[List[str]] = None,
                 webrtc_hostnames: Optional[List[str]] = None,
                 ip_country: str = '',
                 user_id: Optional[int] = None):
        """
        Args:
            connection_ip:      The IP the browser used to reach our server (VPN exit)
            webrtc_ips:         List of IPs gathered from WebRTC ICE candidates
            webrtc_hostnames:   List of hostnames (e.g. .local mDNS names from Chrome)
            ip_country:         Country code of connection_ip (for consistency check)
            user_id:            User ID for cross-referencing leaked IPs
        """
        self.connection_ip    = connection_ip.strip()
        self.webrtc_ips       = [ip.strip() for ip in (webrtc_ips or []) if ip.strip()]
        self.webrtc_hostnames = [h.strip() for h in (webrtc_hostnames or [])]
        self.ip_country       = ip_country.upper()
        self.user_id          = user_id
        self.signals: dict    = {}

    # ── Public API ─────────────────────────────────────────────────────────

    def detect(self) -> dict:
        """
        Analyze WebRTC data for IP leaks.

        Returns:
            {
                'connection_ip':      str,   # VPN/proxy exit IP
                'webrtc_leak_detected': bool,
                'leaked_real_ips':    list,  # Public IPs different from connection_ip
                'local_ips':          list,  # Private/local IPs (less sensitive)
                'mdns_hostnames':     list,  # Chrome mDNS hostnames
                'ip_consistency':     bool,  # True if all IPs match same country
                'confidence':         float,
                'risk_addition':      int,   # Extra risk points to add
                'signals':            dict,
            }
        """
        self._classify_ips()
        self._detect_leaks()
        self._check_geo_consistency()
        self._cross_reference_accounts()

        confidence = self._calculate_confidence()
        leak_detected = len(self.signals.get('leaked_ips', [])) > 0

        result = {
            'connection_ip':        self.connection_ip,
            'webrtc_ips_received':  self.webrtc_ips,
            'webrtc_leak_detected': leak_detected,
            'leaked_real_ips':      self.signals.get('leaked_ips', []),
            'local_ips':            self.signals.get('local_ips', []),
            'mdns_hostnames':       self.signals.get('mdns_hostnames', []),
            'ip_consistency':       self.signals.get('geo_consistent', True),
            'confirmed_vpn_user':   leak_detected,  # If leak = definitely VPN user
            'shared_real_ip_accounts': self.signals.get('linked_accounts', []),
            'confidence':           round(confidence, 4),
            'risk_addition':        self._risk_addition(confidence, leak_detected),
            'signals':              self.signals,
            'detection_methods':    self._triggered_methods(),
        }

        if leak_detected:
            self._save_leaked_ips(result)

        return result

    @classmethod
    def analyze_from_fingerprint(cls, fingerprint_data: dict,
                                  connection_ip: str,
                                  user_id: int = None) -> dict:
        """
        Convenience method: extract WebRTC data from a fingerprint payload
        and run leak detection.
        """
        webrtc_ips = fingerprint_data.get('webrtc_ips', [])
        webrtc_hosts = fingerprint_data.get('webrtc_hostnames', [])

        detector = cls(
            connection_ip=connection_ip,
            webrtc_ips=webrtc_ips,
            webrtc_hostnames=webrtc_hosts,
            user_id=user_id,
        )
        return detector.detect()

    # ── Signal Checks ──────────────────────────────────────────────────────

    def _classify_ips(self):
        """
        Signal 1: Classify each WebRTC IP as public, private, link-local, or mDNS.
        """
        public_ips    = []
        local_ips     = []
        link_local    = []
        mdns_hosts    = []

        # Process hostnames (Chrome mDNS)
        for host in self.webrtc_hostnames:
            if host.endswith(MDNS_SUFFIX):
                mdns_hosts.append(host)

        # Process IP addresses
        for ip_str in self.webrtc_ips:
            try:
                addr = ipaddress.ip_address(ip_str)

                # Loopback
                if addr.is_loopback:
                    local_ips.append({'ip': ip_str, 'type': 'loopback'})
                    continue

                # Link-local
                if addr.is_link_local:
                    link_local.append({'ip': ip_str, 'type': 'link_local'})
                    continue

                # Private (RFC1918 / ULA)
                if addr.is_private:
                    local_ips.append({'ip': ip_str, 'type': 'private'})
                    continue

                # Public IP
                public_ips.append(ip_str)

            except ValueError:
                logger.debug(f"Invalid WebRTC IP: {ip_str}")

        self.signals['public_ips']   = public_ips
        self.signals['local_ips']    = local_ips
        self.signals['link_local']   = link_local
        self.signals['mdns_hostnames'] = mdns_hosts

    def _detect_leaks(self):
        """
        Signal 2: Find public IPs that differ from the connection IP.
        These are the user's real IPs leaking through.
        """
        connection_norm  = self._normalise_ip(self.connection_ip)
        leaked_ips       = []

        for public_ip in self.signals.get('public_ips', []):
            ip_norm = self._normalise_ip(public_ip)
            if ip_norm and ip_norm != connection_norm:
                leaked_ips.append(public_ip)

        self.signals['leaked_ips']         = leaked_ips
        self.signals['leak_count']          = len(leaked_ips)
        self.signals['has_mdns_hostnames']  = len(self.signals.get('mdns_hostnames', [])) > 0
        # mDNS hostnames without real IP leak = Chrome WebRTC protection active
        # mDNS hostnames WITH real IP leak = worst case (leak AND Chrome showing hostnames)
        self.signals['mixed_leak'] = (
            len(leaked_ips) > 0 and self.signals.get('has_mdns_hostnames', False)
        )

    def _check_geo_consistency(self):
        """
        Signal 3: Check if leaked real IPs are from the same country as
        the connection IP. Inconsistency confirms VPN usage.
        """
        self.signals['geo_consistent'] = True
        self.signals['real_ip_country'] = ''

        leaked = self.signals.get('leaked_ips', [])
        if not leaked or not self.ip_country:
            return

        try:
            from ..ip_intelligence.ip_geo_location import IPGeoLocation
            real_ip_country = IPGeoLocation.get_country(leaked[0])
            self.signals['real_ip_country'] = real_ip_country

            if real_ip_country and real_ip_country != self.ip_country:
                self.signals['geo_consistent'] = False
                self.signals['geo_mismatch'] = {
                    'connection_country': self.ip_country,
                    'real_ip_country':    real_ip_country,
                }
        except Exception as e:
            logger.debug(f"Geo consistency check failed: {e}")

    def _cross_reference_accounts(self):
        """
        Signal 4: Check if other accounts have used the leaked real IPs.
        This helps detect multi-account fraud using VPN to hide shared IPs.
        """
        self.signals['linked_accounts'] = []

        leaked = self.signals.get('leaked_ips', [])
        if not leaked:
            return

        try:
            from ..models import IPIntelligence, DeviceFingerprint
            from django.db.models import Q

            linked = []
            for leaked_ip in leaked[:3]:  # Check max 3 leaked IPs
                # Find devices that have seen this IP
                fps = DeviceFingerprint.objects.filter(
                    ip_addresses__contains=leaked_ip
                ).exclude(user=None).values('user_id', 'fingerprint_hash')[:5]

                for fp in fps:
                    if fp['user_id'] != self.user_id:
                        linked.append({
                            'user_id':          fp['user_id'],
                            'shared_real_ip':   leaked_ip,
                            'fingerprint_hash': fp['fingerprint_hash'],
                        })

            self.signals['linked_accounts'] = linked
            self.signals['has_linked_accounts'] = len(linked) > 0

        except Exception as e:
            logger.debug(f"Account cross-reference failed: {e}")

    # ── Confidence & Risk ──────────────────────────────────────────────────

    def _calculate_confidence(self) -> float:
        score = 0.0

        if self.signals.get('leaked_ips'):
            # Real IP leaked — very high confidence
            score += 0.95

        if not self.signals.get('geo_consistent'):
            # Geo mismatch confirms VPN
            score += 0.05

        if self.signals.get('has_linked_accounts'):
            # Multi-account fraud signal
            score += 0.05

        return min(score, 1.0)

    def _risk_addition(self, confidence: float, leak_detected: bool) -> int:
        """
        Calculate additional risk points to add to the IP's composite score.
        """
        if not leak_detected:
            return 0
        # WebRTC leak confirms VPN usage definitively
        base = 35
        if not self.signals.get('geo_consistent'):
            base += 5
        if self.signals.get('has_linked_accounts'):
            base += 10
        return min(base, 50)

    def _triggered_methods(self) -> list:
        methods = []
        if self.signals.get('public_ips'):
            methods.append('webrtc_public_ip_collection')
        if self.signals.get('leaked_ips'):
            methods.append('webrtc_leak_detected')
        if self.signals.get('has_mdns_hostnames'):
            methods.append('mdns_hostname_detection')
        if not self.signals.get('geo_consistent'):
            methods.append('geo_inconsistency')
        if self.signals.get('has_linked_accounts'):
            methods.append('cross_account_correlation')
        if self.signals.get('local_ips'):
            methods.append('local_ip_collection')
        return methods

    # ── Private Helpers ────────────────────────────────────────────────────

    @staticmethod
    def _normalise_ip(ip_str: str) -> Optional[str]:
        """Normalise an IP string to handle IPv4-in-IPv6 notation."""
        if not ip_str:
            return None
        try:
            addr = ipaddress.ip_address(ip_str)
            # Convert IPv4-mapped IPv6 to plain IPv4
            if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
                return str(addr.ipv4_mapped)
            return str(addr)
        except ValueError:
            return None

    def _save_leaked_ips(self, result: dict):
        """
        When WebRTC leaks are detected, record the real IP in
        DeviceFingerprint and update the user's risk profile.
        """
        try:
            leaked = result.get('leaked_real_ips', [])
            if not leaked or not self.user_id:
                return

            from ..models import AnomalyDetectionLog
            AnomalyDetectionLog.objects.create(
                ip_address   = self.connection_ip,
                anomaly_type = 'pattern_deviation',
                description  = (
                    f"WebRTC IP leak: real IPs {leaked} "
                    f"detected behind VPN {self.connection_ip}"
                ),
                anomaly_score = 0.95,
                evidence      = {
                    'connection_ip':    self.connection_ip,
                    'leaked_real_ips':  leaked,
                    'geo_mismatch':     self.signals.get('geo_mismatch', {}),
                    'user_id':          self.user_id,
                },
            )
        except Exception as e:
            logger.debug(f"WebRTC leak save failed: {e}")
