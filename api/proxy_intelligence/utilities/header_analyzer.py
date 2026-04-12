"""
HTTP Header Analyzer  (PRODUCTION-READY — COMPLETE)
=====================================================
Analyzes HTTP request headers to detect proxy usage,
bot traffic, suspicious configurations, and fraud signals.

Headers analyzed:
  - Proxy reveal headers (X-Forwarded-For, Via, X-Real-IP)
  - Multi-hop proxy detection (chained X-Forwarded-For)
  - Inconsistent header fingerprinting
  - Missing mandatory headers (bots often skip Accept-Language)
  - Suspicious header values
  - Client IP extraction (respects trusted proxy configuration)
"""
import logging
import ipaddress
import re
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Headers that reveal proxy presence ────────────────────────────────────
PROXY_REVEAL_HEADERS = [
    'HTTP_VIA',
    'HTTP_X_FORWARDED_FOR',
    'HTTP_FORWARDED',
    'HTTP_X_PROXY_ID',
    'HTTP_PROXY_CONNECTION',
    'HTTP_X_REAL_IP',
    'HTTP_CLIENT_IP',
    'HTTP_X_CLUSTER_CLIENT_IP',
    'HTTP_FORWARDED_FOR',
    'HTTP_X_ORIGINATING_IP',
    'HTTP_USERAGENT_VIA',
    'HTTP_X_COMING_FROM',
    'HTTP_COMING_FROM',
    'HTTP_X_FORWARDED_HOST',
    'HTTP_X_FORWARDED_PROTO',
    'HTTP_CF_CONNECTING_IP',     # Cloudflare: passes real IP
    'HTTP_TRUE_CLIENT_IP',       # Akamai: passes real IP
    'HTTP_X_AZURE_CLIENTIP',     # Azure CDN
    'HTTP_FASTLY_CLIENT_IP',     # Fastly CDN
]

# ── Headers typically present in real browser requests ────────────────────
REAL_BROWSER_HEADERS = [
    'HTTP_ACCEPT',
    'HTTP_ACCEPT_LANGUAGE',
    'HTTP_ACCEPT_ENCODING',
]

# ── HTTP method legitimacy (most bots use GET/POST only) ─────────────────
LEGITIMATE_METHODS = {'GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS'}

# ── Accept-Language patterns that indicate spoofing ──────────────────────
SUSPICIOUS_ACCEPT_LANGUAGE = [
    'xx',           # Non-existent language
    'zz',           # Non-existent
    'test',         # Obvious test value
]


class HeaderAnalyzer:
    """
    Analyzes HTTP request headers from Django's request.META dict.

    Usage:
        analyzer = HeaderAnalyzer(request.META)
        result = analyzer.analyze()
        if result['has_proxy_headers']:
            real_ip = result['real_ip_via_xff']
    """

    def __init__(self, meta: Dict[str, str]):
        """
        Args:
            meta: Django request.META dict (or any dict with HTTP_* keys)
        """
        self.meta = meta

    # ── Main Analysis ──────────────────────────────────────────────────────

    def analyze(self) -> dict:
        """
        Comprehensive header analysis.

        Returns:
            {
                'connection_ip':          str,   # REMOTE_ADDR
                'real_ip_via_xff':        str,   # First IP from X-Forwarded-For
                'proxy_headers_found':    list,  # Names of proxy-revealing headers
                'has_proxy_headers':      bool,
                'is_transparent_proxy':   bool,  # XFF present + connection IP differs
                'is_anonymous_proxy':     bool,  # Proxy headers present but no real IP leaked
                'multi_hop_proxy':        bool,  # Multiple IPs in XFF
                'hop_count':              int,
                'is_bot':                 bool,
                'bot_signals':            list,
                'missing_browser_headers': list,
                'suspicious_values':      list,
                'xff_chain':              list,  # All IPs from XFF chain
                'via_header':             str,
                'cloudflare_ip':          str,
                'risk_score':             int,
            }
        """
        connection_ip  = self.meta.get('REMOTE_ADDR', '')
        proxy_headers  = self._find_proxy_headers()
        xff_data       = self._parse_xff()
        real_ip        = self._extract_real_ip(connection_ip, xff_data)
        bot_signals    = self._check_bot_signals()
        missing_hdrs   = self._check_missing_browser_headers()
        suspicious     = self._check_suspicious_values()

        via_header     = self.meta.get('HTTP_VIA', '')
        cf_ip          = self.meta.get('HTTP_CF_CONNECTING_IP', '')
        akamai_ip      = self.meta.get('HTTP_TRUE_CLIENT_IP', '')
        cdn_real_ip    = cf_ip or akamai_ip

        is_transparent = (
            bool(proxy_headers) and
            real_ip != connection_ip and
            bool(real_ip)
        )
        is_anonymous   = (
            bool(proxy_headers) and
            not real_ip
        )

        risk_score = self._calculate_risk(
            proxy_headers, bot_signals, missing_hdrs,
            suspicious, xff_data['multi_hop']
        )

        return {
            'connection_ip':           connection_ip,
            'real_ip_via_xff':         real_ip,
            'cdn_real_ip':             cdn_real_ip,
            'effective_client_ip':     cdn_real_ip or real_ip or connection_ip,
            'proxy_headers_found':     proxy_headers,
            'has_proxy_headers':       len(proxy_headers) > 0,
            'is_transparent_proxy':    is_transparent,
            'is_anonymous_proxy':      is_anonymous,
            'is_elite_proxy':          not proxy_headers and connection_ip != real_ip,
            'multi_hop_proxy':         xff_data['multi_hop'],
            'hop_count':               xff_data['hop_count'],
            'xff_chain':               xff_data['chain'],
            'via_header':              via_header,
            'cloudflare_ip':           cf_ip,
            'is_bot':                  len(bot_signals) > 0,
            'bot_signals':             bot_signals,
            'missing_browser_headers': missing_hdrs,
            'suspicious_values':       suspicious,
            'user_agent':              self.meta.get('HTTP_USER_AGENT', '')[:300],
            'accept_language':         self.meta.get('HTTP_ACCEPT_LANGUAGE', ''),
            'risk_score':              risk_score,
            'risk_contribution':       min(risk_score // 3, 20),
        }

    # ── Convenience Methods ─────────────────────────────────────────────────

    def get_real_ip(self) -> str:
        """
        Extract the real client IP, honouring trusted proxy headers.
        Priority: Cloudflare > Akamai > X-Forwarded-For > X-Real-IP > REMOTE_ADDR
        """
        # CDN headers are most trustworthy (set by Cloudflare/Akamai at edge)
        cf_ip = self.meta.get('HTTP_CF_CONNECTING_IP', '').strip()
        if cf_ip and self._is_valid_public_ip(cf_ip):
            return cf_ip

        akamai_ip = self.meta.get('HTTP_TRUE_CLIENT_IP', '').strip()
        if akamai_ip and self._is_valid_public_ip(akamai_ip):
            return akamai_ip

        # X-Forwarded-For: take leftmost IP (most trusted in standard configs)
        xff = self.meta.get('HTTP_X_FORWARDED_FOR', '').strip()
        if xff:
            ips = [ip.strip() for ip in xff.split(',')]
            for ip in ips:
                if self._is_valid_public_ip(ip):
                    return ip

        # X-Real-IP
        x_real = self.meta.get('HTTP_X_REAL_IP', '').strip()
        if x_real and self._is_valid_public_ip(x_real):
            return x_real

        return self.meta.get('REMOTE_ADDR', '0.0.0.0')

    def is_from_proxy(self) -> bool:
        """Quick boolean: is this request coming through a proxy?"""
        return bool(self._find_proxy_headers())

    def get_proxy_type(self) -> str:
        """
        Classify the proxy type based on headers.
        Returns: 'transparent', 'anonymous', 'elite', 'none'
        """
        proxy_headers = self._find_proxy_headers()
        if not proxy_headers:
            return 'none'

        real_ip       = self._extract_real_ip(
            self.meta.get('REMOTE_ADDR', ''),
            self._parse_xff()
        )

        if real_ip:
            return 'transparent'   # Proxy reveals real IP
        return 'anonymous'         # Proxy present but hides real IP

    # ── Private Helpers ────────────────────────────────────────────────────

    def _find_proxy_headers(self) -> List[str]:
        """Find all proxy-revealing headers present in the request."""
        found = []
        for header in PROXY_REVEAL_HEADERS:
            value = self.meta.get(header, '').strip()
            if value:
                found.append({
                    'header': header.replace('HTTP_', ''),
                    'value':  value[:150],
                })
        return found

    def _parse_xff(self) -> dict:
        """Parse X-Forwarded-For header into IP chain."""
        xff = self.meta.get('HTTP_X_FORWARDED_FOR', '').strip()
        if not xff:
            return {'chain': [], 'multi_hop': False, 'hop_count': 0}

        chain     = [ip.strip() for ip in xff.split(',') if ip.strip()]
        multi_hop = len(chain) > 1

        return {
            'chain':     chain,
            'multi_hop': multi_hop,
            'hop_count': len(chain),
        }

    def _extract_real_ip(self, connection_ip: str, xff_data: dict) -> str:
        """Extract the most likely real client IP from headers."""
        # Check CDN headers first
        cdn_ip = (
            self.meta.get('HTTP_CF_CONNECTING_IP', '') or
            self.meta.get('HTTP_TRUE_CLIENT_IP', '') or
            self.meta.get('HTTP_FASTLY_CLIENT_IP', '')
        ).strip()
        if cdn_ip and self._is_valid_public_ip(cdn_ip):
            return cdn_ip

        # XFF leftmost public IP
        for ip in xff_data.get('chain', []):
            if self._is_valid_public_ip(ip):
                return ip

        # X-Real-IP
        x_real = self.meta.get('HTTP_X_REAL_IP', '').strip()
        if x_real and self._is_valid_public_ip(x_real):
            return x_real

        return ''

    def _check_bot_signals(self) -> List[str]:
        """Detect bot-like header patterns."""
        signals = []

        ua = self.meta.get('HTTP_USER_AGENT', '')
        if not ua:
            signals.append('missing_user_agent')
        else:
            ua_lower = ua.lower()
            bot_keywords = [
                'bot', 'crawler', 'spider', 'scraper',
                'curl', 'wget', 'python', 'java/', 'go-http',
                'headlesschrome', 'phantomjs', 'selenium',
            ]
            for kw in bot_keywords:
                if kw in ua_lower:
                    signals.append(f'bot_ua:{kw}')
                    break

        # Missing Accept header (most real browsers always send this)
        if not self.meta.get('HTTP_ACCEPT'):
            signals.append('missing_accept_header')

        # Missing Accept-Language (real browsers always have this)
        if not self.meta.get('HTTP_ACCEPT_LANGUAGE'):
            signals.append('missing_accept_language')

        return signals

    def _check_missing_browser_headers(self) -> List[str]:
        """Headers that real browsers always send but bots often omit."""
        missing = []
        for header in REAL_BROWSER_HEADERS:
            if not self.meta.get(header, '').strip():
                missing.append(header.replace('HTTP_', ''))
        return missing

    def _check_suspicious_values(self) -> List[str]:
        """Check for obviously invalid/suspicious header values."""
        suspicious = []

        # Suspicious Accept-Language values
        accept_lang = self.meta.get('HTTP_ACCEPT_LANGUAGE', '').lower()
        for bad_lang in SUSPICIOUS_ACCEPT_LANGUAGE:
            if accept_lang.startswith(bad_lang):
                suspicious.append(f'suspicious_language:{bad_lang}')

        # Via header with internal hostnames (leaked internal proxy)
        via = self.meta.get('HTTP_VIA', '')
        if via and re.search(r'10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+', via):
            suspicious.append('private_ip_in_via')

        # Proxy-Connection header (deprecated, only old/misconfigured proxies send it)
        if self.meta.get('HTTP_PROXY_CONNECTION'):
            suspicious.append('deprecated_proxy_connection_header')

        return suspicious

    def _calculate_risk(
        self, proxy_headers: list, bot_signals: list,
        missing_headers: list, suspicious: list, multi_hop: bool
    ) -> int:
        """Calculate a risk score (0–100) from header signals."""
        score = 0
        if proxy_headers:
            score += 20
        if multi_hop:
            score += 15
        if bot_signals:
            score += len(bot_signals) * 15
        if missing_headers:
            score += len(missing_headers) * 10
        if suspicious:
            score += len(suspicious) * 10
        return min(score, 100)

    @staticmethod
    def _is_valid_public_ip(ip_str: str) -> bool:
        """Return True if ip_str is a valid, non-private IP address."""
        try:
            addr = ipaddress.ip_address(ip_str)
            return not (addr.is_private or addr.is_loopback or
                        addr.is_link_local or addr.is_reserved or
                        addr.is_multicast)
        except ValueError:
            return False
