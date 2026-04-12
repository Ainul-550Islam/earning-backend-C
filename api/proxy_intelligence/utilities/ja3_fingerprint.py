"""
JA3 Fingerprint Parser  (PRODUCTION-READY — COMPLETE)
=======================================================
Parses and processes JA3/JA3S fingerprint data from multiple sources.

JA3 is computed from the TLS ClientHello message. There are several ways
to get JA3 data into the application:

1. nginx with nginx-ja3-fingerprint module → X-JA3-Fingerprint header
2. haproxy with lua JA3 script → custom header
3. Cloudflare passes JA3 in CF-Ja3 header (Enterprise plan)
4. Raw TLS data parsed by application (requires TLS termination in app)
5. Client-submitted (less trustworthy — client controls this value)

This module handles all these scenarios and provides utilities for:
  - Extracting JA3 from request headers
  - Validating JA3 hash format
  - Computing JA3 from raw TLS parameters
  - Comparing JA3 against the known fingerprint database
  - Caching JA3 results per IP
"""
import hashlib
import logging
import re
from typing import Optional, List, Tuple

from django.core.cache import cache

logger = logging.getLogger(__name__)

# ── JA3 Header Names (from various sources) ────────────────────────────────
JA3_HEADER_NAMES = [
    'HTTP_X_JA3_FINGERPRINT',      # nginx-ja3-fingerprint module
    'HTTP_JA3_FINGERPRINT',        # generic
    'HTTP_CF_JA3',                 # Cloudflare Enterprise
    'HTTP_X_CLIENT_JA3',           # custom/haproxy
    'HTTP_SSL_JA3',                # some WAF implementations
    'HTTP_JA3',                    # shorthand
]

# ── JA3 hash format validation ─────────────────────────────────────────────
JA3_HASH_PATTERN = re.compile(r'^[0-9a-f]{32}$', re.IGNORECASE)

# ── GREASE values to filter ────────────────────────────────────────────────
GREASE_VALUES = frozenset({
    0x0a0a, 0x1a1a, 0x2a2a, 0x3a3a, 0x4a4a,
    0x5a5a, 0x6a6a, 0x7a7a, 0x8a8a, 0x9a9a,
    0xaaaa, 0xbaba, 0xcaca, 0xdada, 0xeaea, 0xfafa,
})


class JA3Fingerprint:
    """
    JA3 fingerprint extraction, computation, and analysis.

    Typical usage with a Django request:
        ja3 = JA3Fingerprint.from_request(request)
        if ja3.is_valid:
            result = ja3.identify()
            if result['is_bot']:
                # Block or challenge
    """

    def __init__(self, ja3_hash: str = '', source: str = 'unknown'):
        """
        Args:
            ja3_hash: 32-character MD5 hex string
            source:   Where this JA3 came from ('header', 'computed', 'client')
        """
        self.hash   = ja3_hash.strip().lower() if ja3_hash else ''
        self.source = source

    # ── Class Methods (Constructors) ───────────────────────────────────────

    @classmethod
    def from_request(cls, request) -> 'JA3Fingerprint':
        """
        Extract JA3 from a Django request object.
        Checks multiple known header names.
        """
        for header_name in JA3_HEADER_NAMES:
            value = request.META.get(header_name, '').strip()
            if value and cls._is_valid_hash(value):
                return cls(ja3_hash=value, source='header')

        return cls(ja3_hash='', source='not_found')

    @classmethod
    def from_meta(cls, meta: dict) -> 'JA3Fingerprint':
        """
        Extract JA3 from Django request.META dict.
        """
        for header_name in JA3_HEADER_NAMES:
            value = meta.get(header_name, '').strip()
            if value and cls._is_valid_hash(value):
                return cls(ja3_hash=value, source='header')
        return cls(ja3_hash='', source='not_found')

    @classmethod
    def from_header_value(cls, value: str) -> 'JA3Fingerprint':
        """Create from a raw header value string."""
        return cls(ja3_hash=value, source='header')

    @classmethod
    def compute(
        cls,
        tls_version: int,
        cipher_suites: List[int],
        extensions: List[int],
        elliptic_curves: List[int],
        ec_point_formats: List[int],
    ) -> 'JA3Fingerprint':
        """
        Compute a JA3 fingerprint from raw TLS ClientHello fields.

        Reference: https://github.com/salesforce/ja3

        Args:
            tls_version:       From ClientHello (771 = TLS 1.2, 772 = TLS 1.3)
            cipher_suites:     List of cipher suite codes (uint16)
            extensions:        List of extension type codes (uint16)
            elliptic_curves:   Supported groups / elliptic curves (uint16)
            ec_point_formats:  EC point format codes (uint8)

        Returns:
            JA3Fingerprint instance with computed hash
        """
        # Filter GREASE values (RFC 8701)
        ciphers = [c for c in cipher_suites   if c not in GREASE_VALUES]
        exts    = [e for e in extensions       if e not in GREASE_VALUES]
        curves  = [c for c in elliptic_curves  if c not in GREASE_VALUES]
        fmts    = list(ec_point_formats)

        # Build the canonical JA3 string
        ja3_string = (
            f"{tls_version},"
            f"{'-'.join(str(c) for c in ciphers)},"
            f"{'-'.join(str(e) for e in exts)},"
            f"{'-'.join(str(c) for c in curves)},"
            f"{'-'.join(str(f) for f in fmts)}"
        )

        ja3_hash = hashlib.md5(ja3_string.encode('utf-8')).hexdigest()
        instance = cls(ja3_hash=ja3_hash, source='computed')
        instance._raw_string = ja3_string
        return instance

    # ── Properties ─────────────────────────────────────────────────────────

    @property
    def is_valid(self) -> bool:
        """True if this instance has a valid 32-char MD5 JA3 hash."""
        return self._is_valid_hash(self.hash)

    @property
    def is_available(self) -> bool:
        """True if JA3 data was found (valid hash present)."""
        return bool(self.hash) and self.is_valid

    # ── Analysis ───────────────────────────────────────────────────────────

    def identify(self) -> dict:
        """
        Look up this JA3 hash in the known fingerprint database.

        Returns:
            {
                'ja3_hash':           str,
                'client':             str,
                'is_bot':             bool,
                'risk_level':         str,
                'is_known':           bool,
                'source':             str,
                'recommended_action': str,
            }
        """
        if not self.is_valid:
            return {
                'ja3_hash':           self.hash,
                'client':             'unavailable',
                'is_bot':             False,
                'risk_level':         'low',
                'is_known':           False,
                'source':             self.source,
                'recommended_action': 'allow',
            }

        # Check cache first
        cache_key = f"pi:ja3:{self.hash}"
        cached    = cache.get(cache_key)
        if cached:
            return cached

        # Look up in TLSFingerprinter database
        from .tls_fingerprint import TLSFingerprinter
        result = TLSFingerprinter.identify(self.hash)
        result['source'] = self.source

        cache.set(cache_key, result, 86400)
        return result

    def is_bot(self) -> bool:
        """Quick boolean: is this JA3 from a bot/automation tool?"""
        if not self.is_valid:
            return False
        return self.identify().get('is_bot', False)

    def get_client_name(self) -> str:
        """Return the identified client name string."""
        return self.identify().get('client', 'unknown')

    def check_consistency_with_ua(self, user_agent: str) -> dict:
        """
        Check if this JA3 is consistent with the User-Agent string.
        Inconsistency = spoofed User-Agent.
        """
        if not self.is_valid:
            return {'is_consistent': True, 'reason': 'no_ja3_available'}

        from .tls_fingerprint import TLSFingerprinter
        return TLSFingerprinter.check_ua_ja3_consistency(user_agent, self.hash)

    # ── Persistence & Caching ─────────────────────────────────────────────

    def cache_for_ip(self, ip_address: str, ttl: int = 3600):
        """Store this JA3 hash associated with an IP address."""
        if not self.is_valid or not ip_address:
            return
        cache.set(f"pi:ja3_for_ip:{ip_address}", self.hash, ttl)

    @classmethod
    def get_for_ip(cls, ip_address: str) -> 'JA3Fingerprint':
        """Retrieve the most recently seen JA3 for an IP address."""
        cached = cache.get(f"pi:ja3_for_ip:{ip_address}")
        return cls(ja3_hash=cached or '', source='cached')

    # ── Utilities ──────────────────────────────────────────────────────────

    @staticmethod
    def _is_valid_hash(value: str) -> bool:
        """Validate JA3 hash format: 32 lowercase hex chars."""
        if not value:
            return False
        return bool(JA3_HASH_PATTERN.match(value))

    @staticmethod
    def extract_from_string(text: str) -> Optional[str]:
        """
        Extract a JA3 hash from a free-form string.
        Useful for parsing log files.
        """
        match = JA3_HASH_PATTERN.search(text.lower())
        return match.group(0) if match else None

    def __str__(self) -> str:
        return self.hash or '<no JA3>'

    def __repr__(self) -> str:
        return f"JA3Fingerprint(hash={self.hash!r}, source={self.source!r})"

    def __bool__(self) -> bool:
        return self.is_valid

    def __eq__(self, other) -> bool:
        if isinstance(other, JA3Fingerprint):
            return self.hash == other.hash
        if isinstance(other, str):
            return self.hash == other.lower().strip()
        return False


# ── Module-level convenience functions ────────────────────────────────────

def get_ja3_from_request(request) -> str:
    """
    Extract JA3 hash string from a Django request.
    Returns empty string if not available.
    """
    return JA3Fingerprint.from_request(request).hash


def is_bot_ja3(ja3_hash: str) -> bool:
    """
    Quick boolean check: is this JA3 hash from a bot?
    """
    fp = JA3Fingerprint(ja3_hash)
    return fp.is_bot()


def analyze_request_ja3(request, ip_address: str = '') -> dict:
    """
    Full JA3 analysis of a Django request.
    Returns identification + UA consistency check.
    """
    fp       = JA3Fingerprint.from_request(request)
    ua       = request.META.get('HTTP_USER_AGENT', '')
    identity = fp.identify()
    consistency = fp.check_consistency_with_ua(ua)

    # Cache JA3 for this IP
    if ip_address and fp.is_valid:
        fp.cache_for_ip(ip_address)

    return {
        'ja3_hash':      fp.hash,
        'ja3_source':    fp.source,
        'ja3_available': fp.is_available,
        'identity':      identity,
        'consistency':   consistency,
        'risk_score':    (
            consistency.get('risk_score', 0) +
            (20 if identity.get('is_bot') else 0)
        ),
    }
