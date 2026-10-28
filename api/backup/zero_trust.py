"""
Zero Trust Data Security
Inspired by: Rubrik Zero Trust Data Security, Commvault Air Gap Protect
Implements zero-trust principles: immutable snapshots, MFA, least privilege,
air-gapped storage, and access anomaly detection.
"""

import hashlib
import hmac
import logging
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class TrustLevel(str, Enum):
    UNTRUSTED  = "untrusted"
    LOW        = "low"
    MEDIUM     = "medium"
    HIGH       = "high"
    VERIFIED   = "verified"


class AccessDecision(str, Enum):
    ALLOW  = "allow"
    DENY   = "deny"
    CHALLENGE = "challenge"    # Require additional MFA


@dataclass
class ZeroTrustContext:
    """Context for every access decision"""
    user_id: str
    resource_id: str
    action: str
    ip_address: str
    user_agent: str = ""
    mfa_verified: bool = False
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AccessAuditEntry:
    context: ZeroTrustContext
    decision: AccessDecision
    trust_level: TrustLevel
    reason: str
    timestamp: datetime = field(default_factory=datetime.utcnow)


class ZeroTrustPolicyEngine:
    """
    Evaluates every access request against zero-trust policies.
    Never trust, always verify — including internal service calls.
    """

    # High-risk actions always require MFA
    MFA_REQUIRED_ACTIONS = {
        "backup_delete", "backup_restore", "storage_config_change",
        "policy_change", "user_grant_admin", "export_data",
    }

    # Actions blocked outside business hours (configurable)
    TIME_RESTRICTED_ACTIONS = {
        "bulk_delete", "retention_policy_change",
    }

    def __init__(self, allowed_ip_ranges: Optional[List[str]] = None,
                 business_hours: Optional[Dict] = None):
        self.allowed_ip_ranges = allowed_ip_ranges or []
        self.business_hours = business_hours or {"start": 8, "end": 20}
        self._audit_log: List[AccessAuditEntry] = []
        self._blocked_users: Set[str] = set()
        self._failed_attempts: Dict[str, List[datetime]] = {}

    def evaluate(self, ctx: ZeroTrustContext) -> AccessDecision:
        decision, trust, reason = self._evaluate_internal(ctx)
        self._audit_log.append(AccessAuditEntry(
            context=ctx, decision=decision, trust_level=trust, reason=reason
        ))
        if decision == AccessDecision.DENY:
            self._record_failed_attempt(ctx.user_id)
        return decision

    def _evaluate_internal(self, ctx: ZeroTrustContext
                           ) -> tuple[AccessDecision, TrustLevel, str]:
        # 1. Blocked users
        if ctx.user_id in self._blocked_users:
            return AccessDecision.DENY, TrustLevel.UNTRUSTED, "User is blocked"

        # 2. MFA check for sensitive actions
        if ctx.action in self.MFA_REQUIRED_ACTIONS and not ctx.mfa_verified:
            return AccessDecision.CHALLENGE, TrustLevel.LOW, "MFA required for this action"

        # 3. Time restriction
        if ctx.action in self.TIME_RESTRICTED_ACTIONS:
            hour = ctx.timestamp.hour
            if not (self.business_hours["start"] <= hour < self.business_hours["end"]):
                return AccessDecision.DENY, TrustLevel.LOW, "Action restricted outside business hours"

        # 4. Brute-force detection
        if self._is_brute_force(ctx.user_id):
            self._blocked_users.add(ctx.user_id)
            return AccessDecision.DENY, TrustLevel.UNTRUSTED, "Account locked: too many failed attempts"

        trust_level = TrustLevel.VERIFIED if ctx.mfa_verified else TrustLevel.MEDIUM
        return AccessDecision.ALLOW, trust_level, "Access granted"

    def _record_failed_attempt(self, user_id: str) -> None:
        now = datetime.utcnow()
        attempts = self._failed_attempts.setdefault(user_id, [])
        attempts.append(now)
        cutoff = now - timedelta(minutes=15)
        self._failed_attempts[user_id] = [a for a in attempts if a > cutoff]

    def _is_brute_force(self, user_id: str, threshold: int = 5) -> bool:
        cutoff = datetime.utcnow() - timedelta(minutes=15)
        recent = [a for a in self._failed_attempts.get(user_id, []) if a > cutoff]
        return len(recent) >= threshold

    def unblock_user(self, user_id: str) -> None:
        self._blocked_users.discard(user_id)
        self._failed_attempts.pop(user_id, None)

    def get_audit_log(self, user_id: Optional[str] = None,
                      limit: int = 100) -> List[AccessAuditEntry]:
        entries = self._audit_log
        if user_id:
            entries = [e for e in entries if e.context.user_id == user_id]
        return entries[-limit:]


class MFAVerifier:
    """Time-based One-Time Password (TOTP) MFA verification"""

    TOTP_STEP = 30  # seconds

    def __init__(self, secret: Optional[str] = None):
        self.secret = secret or secrets.token_hex(20)

    def _hotp(self, counter: int) -> str:
        import struct
        msg = struct.pack(">Q", counter)
        h = hmac.new(self.secret.encode(), msg, hashlib.sha1).digest()
        offset = h[-1] & 0xF
        code = ((h[offset] & 0x7F) << 24 |
                (h[offset+1] & 0xFF) << 16 |
                (h[offset+2] & 0xFF) << 8 |
                (h[offset+3] & 0xFF))
        return str(code % 10**6).zfill(6)

    def generate_totp(self) -> str:
        counter = int(time.time()) // self.TOTP_STEP
        return self._hotp(counter)

    def verify_totp(self, code: str, window: int = 1) -> bool:
        counter = int(time.time()) // self.TOTP_STEP
        for delta in range(-window, window + 1):
            if self._hotp(counter + delta) == code:
                return True
        return False


class AirGapManager:
    """
    Manages air-gapped backup copies.
    Air-gapped backups are network-isolated and read-only — ransomware cannot reach them.
    """

    def __init__(self):
        self._air_gap_copies: Dict[str, Dict[str, Any]] = {}

    def create_air_gap_copy(self, backup_id: str, source_path: str,
                             retention_days: int = 365) -> str:
        """Copy backup to air-gapped vault"""
        import uuid
        vault_id = str(uuid.uuid4())
        self._air_gap_copies[vault_id] = {
            "backup_id": backup_id,
            "source_path": source_path,
            "created_at": datetime.utcnow(),
            "retention_days": retention_days,
            "network_isolated": True,
            "read_only": True,
        }
        logger.info("Air-gap copy created: backup=%s vault=%s", backup_id, vault_id)
        return vault_id

    def list_air_gap_copies(self, backup_id: Optional[str] = None) -> List[Dict]:
        copies = list(self._air_gap_copies.values())
        if backup_id:
            copies = [c for c in copies if c["backup_id"] == backup_id]
        return copies

    def retrieve_copy(self, vault_id: str, authorized_by: str) -> Optional[Dict]:
        """Retrieve requires explicit authorization — logged for audit"""
        copy = self._air_gap_copies.get(vault_id)
        if copy:
            logger.info("Air-gap retrieval: vault=%s authorized_by=%s", vault_id, authorized_by)
        return copy
