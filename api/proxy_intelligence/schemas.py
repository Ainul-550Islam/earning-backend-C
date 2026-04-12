"""
Proxy Intelligence Schemas  (PRODUCTION-READY - COMPLETE)
==========================================================
Typed dataclass schemas for strict input validation and structured
API responses. Used by views.py and services.py.

These are NOT Django models. They are pure Python dataclasses used as
Data Transfer Objects (DTOs) between layers.
"""
from __future__ import annotations
import ipaddress
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from datetime import datetime


# ═══════════════════════════════════════════════════════
# INPUT SCHEMAS  (request → service)
# ═══════════════════════════════════════════════════════

@dataclass
class IPCheckRequest:
    """Input for a single IP check."""
    ip_address: str
    include_geo: bool = True
    include_threat_feeds: bool = False
    include_vpn_check: bool = True
    include_proxy_check: bool = True
    include_tor_check: bool = True
    strict_mode: bool = False
    user_id: Optional[int] = None
    tenant_id: Optional[int] = None
    request_headers: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        try:
            self.ip_address = str(ipaddress.ip_address(self.ip_address))
        except ValueError:
            raise ValueError(f"Invalid IP address: '{self.ip_address}'")

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BulkIPCheckRequest:
    """Input for bulk IP check (max 100 IPs)."""
    ip_addresses: List[str]
    include_geo: bool = False
    include_threat_feeds: bool = False
    tenant_id: Optional[int] = None

    def __post_init__(self):
        if len(self.ip_addresses) > 100:
            raise ValueError("Maximum 100 IP addresses per bulk request.")
        validated = []
        for ip in self.ip_addresses:
            try:
                validated.append(str(ipaddress.ip_address(ip)))
            except ValueError:
                pass  # Skip invalid IPs silently in bulk mode
        self.ip_addresses = validated


@dataclass
class FingerprintSubmitRequest:
    """Input for a device fingerprint submission."""
    canvas_hash: str
    webgl_hash: str
    audio_hash: str
    user_agent: str
    screen: str
    timezone: str
    language: str
    platform: str
    plugins: List[str] = field(default_factory=list)
    fonts: List[str] = field(default_factory=list)
    hardware_concurrency: int = 0
    device_memory: int = 0
    touch_points: int = 0
    webgl_renderer: str = ''
    cookie_enabled: bool = True
    do_not_track: str = ''
    ip_address: str = ''
    user_id: Optional[int] = None
    tenant_id: Optional[int] = None


@dataclass
class BlacklistAddRequest:
    """Input for adding an IP to the blacklist."""
    ip_address: str
    reason: str                       # See BlacklistReason enum
    description: str = ''
    is_permanent: bool = False
    expires_hours: Optional[int] = None   # If not permanent
    tenant_id: Optional[int] = None

    def __post_init__(self):
        try:
            self.ip_address = str(ipaddress.ip_address(self.ip_address))
        except ValueError:
            raise ValueError(f"Invalid IP address: '{self.ip_address}'")


@dataclass
class VelocityCheckRequest:
    """Input for a velocity / rate-limit check."""
    ip_address: str
    action_type: str          # e.g. 'login', 'click', 'api_call'
    threshold: int = 60       # Max requests per window
    window_seconds: int = 60
    user_id: Optional[int] = None
    tenant_id: Optional[int] = None


# ═══════════════════════════════════════════════════════
# OUTPUT SCHEMAS  (service → view → response)
# ═══════════════════════════════════════════════════════

@dataclass
class IPDetectionResult:
    """Structured result from a full IP check."""
    ip_address: str
    risk_score: int                # 0–100
    risk_level: str                # very_low | low | medium | high | critical
    recommended_action: str        # allow | flag | challenge | block
    is_vpn: bool = False
    is_proxy: bool = False
    is_tor: bool = False
    is_datacenter: bool = False
    is_residential: bool = False
    is_mobile: bool = False
    is_blacklisted: bool = False
    is_whitelisted: bool = False
    vpn_provider: str = ''
    proxy_type: str = ''
    country_code: str = ''
    country_name: str = ''
    city: str = ''
    region: str = ''
    isp: str = ''
    asn: str = ''
    latitude: float = 0.0
    longitude: float = 0.0
    timezone: str = ''
    fraud_score: int = 0
    abuse_confidence_score: int = 0
    detection_methods: List[str] = field(default_factory=list)
    flags: List[str] = field(default_factory=list)
    raw_signals: Dict[str, Any] = field(default_factory=dict)
    response_time_ms: float = 0.0
    checked_at: Optional[str] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        if self.checked_at is None:
            from django.utils import timezone
            d['checked_at'] = timezone.now().isoformat()
        return d

    @property
    def should_block(self) -> bool:
        return self.recommended_action == 'block' or self.is_blacklisted

    @property
    def should_challenge(self) -> bool:
        return self.recommended_action == 'challenge'

    @property
    def is_clean(self) -> bool:
        return (
            not self.is_vpn and not self.is_proxy and
            not self.is_tor and self.risk_score < 41 and
            not self.is_blacklisted
        )


@dataclass
class BulkIPCheckResult:
    """Result of a bulk IP check."""
    total: int
    results: List[IPDetectionResult]
    clean_count: int = 0
    flagged_count: int = 0
    blocked_count: int = 0
    response_time_ms: float = 0.0

    def __post_init__(self):
        self.clean_count   = sum(1 for r in self.results if r.is_clean)
        self.flagged_count = sum(1 for r in self.results if r.recommended_action == 'flag')
        self.blocked_count = sum(1 for r in self.results if r.should_block)

    def to_dict(self) -> dict:
        return {
            'total':           self.total,
            'clean_count':     self.clean_count,
            'flagged_count':   self.flagged_count,
            'blocked_count':   self.blocked_count,
            'response_time_ms': self.response_time_ms,
            'results':         [r.to_dict() for r in self.results],
        }


@dataclass
class FingerprintResult:
    """Result of processing a device fingerprint."""
    fingerprint_hash: str
    is_new: bool
    is_suspicious: bool
    spoofing_detected: bool
    risk_score: int
    flags: List[str]
    device_type: str
    browser_name: str
    os_name: str
    db_id: str
    shared_users: int = 1
    seen_on_ips: int = 1

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DashboardStats:
    """Stats for the proxy intelligence dashboard."""
    total_ips_checked: int = 0
    high_risk_ips: int = 0
    vpn_detected: int = 0
    proxy_detected: int = 0
    tor_detected: int = 0
    blacklisted_ips: int = 0
    fraud_attempts_today: int = 0
    anomalies_today: int = 0
    high_risk_users: int = 0
    avg_risk_score: float = 0.0
    tor_exit_nodes_tracked: int = 0
    malicious_ips_in_db: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class VelocityResult:
    """Result of a velocity check."""
    ip_address: str
    action_type: str
    request_count: int
    threshold: int
    window_seconds: int
    exceeded: bool
    recommended_action: str  # allow | rate_limit

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ThreatFeedResult:
    """Result from a single threat feed query."""
    feed_name: str
    ip_address: str
    is_malicious: bool
    confidence: float
    threat_types: List[str]
    raw: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AnomalyResult:
    """Result of running anomaly detection."""
    user_id: Optional[int]
    ip_address: str
    anomaly_detected: bool
    anomaly_types: List[str]
    anomaly_scores: Dict[str, float]
    recommended_action: str  # allow | flag | block

    def to_dict(self) -> dict:
        return asdict(self)
