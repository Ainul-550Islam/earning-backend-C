"""
Tenant Lifecycle Management
Handles onboarding, offboarding, data purge, BYOK (Bring Your Own Key),
SSO/SAML/OIDC configuration, and IP allowlisting per tenant.
"""

import logging
import secrets
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Enums ─────────────────────────────────────────────────────────────────────

class OnboardingStatus(str, Enum):
    INVITED      = "invited"
    CONFIGURING  = "configuring"
    ACTIVE       = "active"
    SUSPENDED    = "suspended"
    OFFBOARDING  = "offboarding"
    TERMINATED   = "terminated"


class SSOProtocol(str, Enum):
    SAML2    = "saml2"
    OIDC     = "oidc"
    OAUTH2   = "oauth2"
    LDAP     = "ldap"


class OffboardingReason(str, Enum):
    CHURNED         = "churned"
    NON_PAYMENT     = "non_payment"
    VIOLATION       = "violation"
    REQUESTED       = "customer_requested"
    MIGRATED        = "migrated_to_other"


# ── Onboarding ─────────────────────────────────────────────────────────────────

@dataclass
class OnboardingChecklist:
    tenant_id: str
    admin_user_created: bool = False
    storage_configured: bool = False
    first_backup_run: bool = False
    notification_configured: bool = False
    sso_configured: bool = False
    billing_configured: bool = False
    white_label_configured: bool = False
    invited_at: Optional[datetime] = None
    activated_at: Optional[datetime] = None

    @property
    def completion_pct(self) -> float:
        fields = [
            self.admin_user_created, self.storage_configured,
            self.first_backup_run, self.notification_configured,
            self.billing_configured,
        ]
        done = sum(1 for f in fields if f)
        return round(done / len(fields) * 100, 1)

    @property
    def is_complete(self) -> bool:
        return self.completion_pct >= 100.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "completion_pct": self.completion_pct,
            "steps": {
                "admin_user_created": self.admin_user_created,
                "storage_configured": self.storage_configured,
                "first_backup_run": self.first_backup_run,
                "notification_configured": self.notification_configured,
                "billing_configured": self.billing_configured,
                "sso_configured": self.sso_configured,
            },
        }


class TenantOnboardingService:
    """
    Step-by-step tenant onboarding.
    Tracks checklist completion and sends welcome communications.
    """

    def __init__(self):
        self._checklists: Dict[str, OnboardingChecklist] = {}
        self._statuses: Dict[str, OnboardingStatus] = {}

    def invite_tenant(self, tenant_id: str,
                       admin_email: str) -> OnboardingChecklist:
        checklist = OnboardingChecklist(
            tenant_id=tenant_id,
            invited_at=datetime.utcnow(),
        )
        self._checklists[tenant_id] = checklist
        self._statuses[tenant_id] = OnboardingStatus.INVITED
        logger.info("Tenant invited: %s admin=%s", tenant_id, admin_email)
        self._send_welcome_email(admin_email, tenant_id)
        return checklist

    def mark_step(self, tenant_id: str, step: str) -> OnboardingChecklist:
        checklist = self._checklists.get(tenant_id)
        if not checklist:
            raise LookupError(f"Checklist not found for tenant {tenant_id}")
        if hasattr(checklist, step):
            setattr(checklist, step, True)
        if checklist.is_complete and not checklist.activated_at:
            checklist.activated_at = datetime.utcnow()
            self._statuses[tenant_id] = OnboardingStatus.ACTIVE
            logger.info("Tenant fully onboarded: %s", tenant_id)
        return checklist

    def get_checklist(self, tenant_id: str) -> Optional[OnboardingChecklist]:
        return self._checklists.get(tenant_id)

    def get_status(self, tenant_id: str) -> Optional[OnboardingStatus]:
        return self._statuses.get(tenant_id)

    def list_incomplete(self) -> List[OnboardingChecklist]:
        return [c for c in self._checklists.values() if not c.is_complete]

    def _send_welcome_email(self, email: str, tenant_id: str) -> None:
        logger.info("Welcome email queued: %s tenant=%s", email, tenant_id)


# ── Offboarding ────────────────────────────────────────────────────────────────

@dataclass
class OffboardingRequest:
    tenant_id: str
    reason: OffboardingReason
    requested_by: str
    purge_data: bool = True
    purge_after_days: int = 30             # grace period before permanent deletion
    requested_at: datetime = field(default_factory=datetime.utcnow)
    scheduled_purge_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    data_purged: bool = False
    export_requested: bool = False

    def __post_init__(self):
        if self.purge_data and not self.scheduled_purge_at:
            self.scheduled_purge_at = (
                self.requested_at + timedelta(days=self.purge_after_days)
            )


class TenantOffboardingService:
    """
    Handles graceful tenant termination including data export,
    scheduled purge, and regulatory compliance.
    """

    def __init__(self):
        self._requests: Dict[str, OffboardingRequest] = {}

    def initiate(self, request: OffboardingRequest) -> OffboardingRequest:
        self._requests[request.tenant_id] = request
        logger.warning(
            "Tenant offboarding initiated: %s reason=%s purge=%s grace=%dd",
            request.tenant_id, request.reason.value,
            request.purge_data, request.purge_after_days,
        )
        return request

    def export_tenant_data(self, tenant_id: str,
                            destination: str) -> Dict[str, Any]:
        """Export all tenant data before purge"""
        logger.info("Data export initiated: tenant=%s dest=%s", tenant_id, destination)
        return {
            "status": "queued",
            "tenant_id": tenant_id,
            "destination": destination,
            "estimated_size_gb": 0,
        }

    def purge_tenant_data(self, tenant_id: str) -> Dict[str, Any]:
        """
        Permanently delete all tenant data.
        Runs after grace period — irreversible.
        """
        request = self._requests.get(tenant_id)
        if not request:
            raise LookupError(f"No offboarding request for {tenant_id}")

        if (request.scheduled_purge_at
                and datetime.utcnow() < request.scheduled_purge_at):
            raise RuntimeError(
                f"Grace period not elapsed. Purge scheduled at "
                f"{request.scheduled_purge_at.isoformat()}"
            )

        # In production: delete from S3, Azure, GCS, DB, audit logs
        purged = {
            "backup_files": True,
            "database_records": True,
            "audit_logs": True,
            "user_accounts": True,
            "api_keys": True,
            "webhooks": True,
        }
        request.data_purged = True
        request.completed_at = datetime.utcnow()
        logger.warning("TENANT DATA PURGED: %s (irreversible)", tenant_id)
        return {"tenant_id": tenant_id, "purged": purged,
                "completed_at": request.completed_at.isoformat()}

    def cancel_offboarding(self, tenant_id: str) -> bool:
        """Cancel offboarding during grace period"""
        request = self._requests.get(tenant_id)
        if not request or request.data_purged:
            return False
        del self._requests[tenant_id]
        logger.info("Offboarding cancelled: %s", tenant_id)
        return True

    def due_for_purge(self) -> List[OffboardingRequest]:
        now = datetime.utcnow()
        return [
            r for r in self._requests.values()
            if r.purge_data
            and not r.data_purged
            and r.scheduled_purge_at
            and now >= r.scheduled_purge_at
        ]

    def get_request(self, tenant_id: str) -> Optional[OffboardingRequest]:
        return self._requests.get(tenant_id)


# ── BYOK (Bring Your Own Key) ─────────────────────────────────────────────────

@dataclass
class CustomerEncryptionKey:
    tenant_id: str
    key_id: str
    key_alias: str
    provider: str        # "aws_kms" | "azure_key_vault" | "gcp_kms" | "local_hsm"
    key_arn: str         # ARN / resource URI of the external key
    created_at: datetime = field(default_factory=datetime.utcnow)
    rotated_at: Optional[datetime] = None
    is_active: bool = True
    rotation_days: int = 90

    @property
    def needs_rotation(self) -> bool:
        ref = self.rotated_at or self.created_at
        return (datetime.utcnow() - ref).days >= self.rotation_days


class BYOKManager:
    """
    Bring Your Own Key (BYOK) / Customer-Managed Encryption Keys (CMEK).
    Tenants provide keys stored in their own KMS — we never see plaintext keys.
    """

    def __init__(self):
        self._keys: Dict[str, CustomerEncryptionKey] = {}  # tenant_id → key

    def register_key(self, key: CustomerEncryptionKey) -> None:
        key.key_id = key.key_id or secrets.token_hex(16)
        self._keys[key.tenant_id] = key
        logger.info("BYOK registered: tenant=%s provider=%s alias=%s",
                    key.tenant_id, key.provider, key.key_alias)

    def get_key(self, tenant_id: str) -> Optional[CustomerEncryptionKey]:
        return self._keys.get(tenant_id)

    def rotate_key(self, tenant_id: str, new_key_arn: str) -> bool:
        key = self._keys.get(tenant_id)
        if not key:
            return False
        key.key_arn = new_key_arn
        key.rotated_at = datetime.utcnow()
        logger.info("BYOK rotated: tenant=%s new_arn=%s", tenant_id, new_key_arn)
        return True

    def revoke_key(self, tenant_id: str) -> bool:
        key = self._keys.get(tenant_id)
        if not key:
            return False
        key.is_active = False
        logger.warning("BYOK revoked: tenant=%s — data inaccessible!", tenant_id)
        return True

    def keys_needing_rotation(self) -> List[CustomerEncryptionKey]:
        return [k for k in self._keys.values() if k.is_active and k.needs_rotation]

    def encrypt_with_tenant_key(self, tenant_id: str, data: bytes) -> bytes:
        """Encrypt data using tenant's external KMS key (envelope encryption)"""
        key = self._keys.get(tenant_id)
        if not key or not key.is_active:
            raise PermissionError(f"No active BYOK key for tenant {tenant_id}")
        # In production: call AWS KMS, Azure Key Vault, or GCP KMS
        # Here we simulate envelope encryption
        dek = secrets.token_bytes(32)   # data encryption key
        import hashlib, hmac
        signature = hmac.new(dek, data, hashlib.sha256).digest()
        return signature + data         # simplified — real impl uses AES-GCM

    def decrypt_with_tenant_key(self, tenant_id: str, ciphertext: bytes) -> bytes:
        key = self._keys.get(tenant_id)
        if not key or not key.is_active:
            raise PermissionError(f"No active BYOK key for tenant {tenant_id}")
        return ciphertext[32:]          # strip mock signature


# ── SSO / SAML / OIDC ─────────────────────────────────────────────────────────

@dataclass
class SSOConfig:
    tenant_id: str
    protocol: SSOProtocol
    provider_name: str                   # e.g. "Okta", "Azure AD", "Google"
    entity_id: Optional[str] = None      # SAML entity ID
    sso_url: Optional[str] = None        # SAML SSO URL / OIDC auth endpoint
    slo_url: Optional[str] = None        # Single logout URL
    x509_cert: Optional[str] = None      # SAML IdP certificate
    client_id: Optional[str] = None      # OIDC client ID
    client_secret: Optional[str] = None
    discovery_url: Optional[str] = None  # OIDC discovery doc URL
    attribute_mapping: Dict[str, str] = field(default_factory=lambda: {
        "email": "email", "first_name": "given_name", "last_name": "family_name",
    })
    auto_provision: bool = True          # create user on first SSO login
    default_role: str = "viewer"
    enabled: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)

    def validate(self):
        errors = {}
        if self.protocol == SSOProtocol.SAML2:
            if not self.entity_id:
                errors["entity_id"] = "Required for SAML2"
            if not self.sso_url:
                errors["sso_url"] = "Required for SAML2"
            if not self.x509_cert:
                errors["x509_cert"] = "Required for SAML2"
        elif self.protocol in (SSOProtocol.OIDC, SSOProtocol.OAUTH2):
            if not self.client_id:
                errors["client_id"] = "Required for OIDC/OAuth2"
            if not self.discovery_url and not self.sso_url:
                errors["discovery_url"] = "Required for OIDC"
        if errors:
            raise ValueError(errors)
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "protocol": self.protocol.value,
            "provider_name": self.provider_name,
            "entity_id": self.entity_id,
            "sso_url": self.sso_url,
            "auto_provision": self.auto_provision,
            "default_role": self.default_role,
            "enabled": self.enabled,
        }


class SSOManager:
    """SSO configuration management per tenant"""

    def __init__(self):
        self._configs: Dict[str, SSOConfig] = {}

    def configure(self, config: SSOConfig) -> None:
        config.validate()
        self._configs[config.tenant_id] = config
        logger.info("SSO configured: tenant=%s protocol=%s provider=%s",
                    config.tenant_id, config.protocol.value, config.provider_name)

    def get(self, tenant_id: str) -> Optional[SSOConfig]:
        return self._configs.get(tenant_id)

    def disable(self, tenant_id: str) -> bool:
        config = self._configs.get(tenant_id)
        if not config:
            return False
        config.enabled = False
        return True

    def initiate_saml_flow(self, tenant_id: str) -> Dict[str, Any]:
        config = self._configs.get(tenant_id)
        if not config or config.protocol != SSOProtocol.SAML2:
            raise ValueError("SAML2 not configured for this tenant")
        state = secrets.token_urlsafe(32)
        return {
            "redirect_url": f"{config.sso_url}?state={state}",
            "entity_id": config.entity_id,
            "state": state,
        }

    def initiate_oidc_flow(self, tenant_id: str,
                            redirect_uri: str) -> Dict[str, Any]:
        config = self._configs.get(tenant_id)
        if not config or config.protocol not in (SSOProtocol.OIDC, SSOProtocol.OAUTH2):
            raise ValueError("OIDC not configured for this tenant")
        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(16)
        auth_url = (
            f"{config.sso_url}?response_type=code"
            f"&client_id={config.client_id}"
            f"&redirect_uri={redirect_uri}"
            f"&scope=openid+email+profile"
            f"&state={state}&nonce={nonce}"
        )
        return {"redirect_url": auth_url, "state": state, "nonce": nonce}

    def process_saml_response(self, tenant_id: str,
                               saml_response: str) -> Dict[str, Any]:
        """Validate SAML assertion and return user attributes"""
        config = self._configs.get(tenant_id)
        if not config:
            raise LookupError(f"SSO not configured for {tenant_id}")
        # In production: validate XML signature using x509_cert
        logger.info("SAML response processed: tenant=%s", tenant_id)
        return {
            "email": "user@tenant.com",
            "first_name": "John",
            "last_name": "Doe",
            "auto_provision": config.auto_provision,
            "role": config.default_role,
        }

    def list_configs(self) -> List[SSOConfig]:
        return list(self._configs.values())


# ── Support Ticket Integration ────────────────────────────────────────────────

class SupportTicketPriority(str, Enum):
    LOW      = "low"
    MEDIUM   = "medium"
    HIGH     = "high"
    CRITICAL = "critical"


@dataclass
class SupportTicket:
    ticket_id: str
    tenant_id: str
    subject: str
    description: str
    priority: SupportTicketPriority
    created_by: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    status: str = "open"
    external_id: Optional[str] = None    # ID in Zendesk/Freshdesk
    resolved_at: Optional[datetime] = None
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticket_id": self.ticket_id,
            "tenant_id": self.tenant_id,
            "subject": self.subject,
            "priority": self.priority.value,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "external_id": self.external_id,
        }


class SupportTicketService:
    """
    Customer support ticket management.
    Integrates with Zendesk, Freshdesk, or internal ticketing.
    """

    def __init__(self, provider: str = "internal",
                 api_key: Optional[str] = None,
                 base_url: Optional[str] = None):
        self.provider = provider
        self.api_key = api_key
        self.base_url = base_url
        self._tickets: Dict[str, SupportTicket] = {}

    def create_ticket(self, ticket: SupportTicket) -> SupportTicket:
        self._tickets[ticket.ticket_id] = ticket
        if self.provider == "zendesk" and self.api_key:
            ticket.external_id = self._create_zendesk(ticket)
        elif self.provider == "freshdesk" and self.api_key:
            ticket.external_id = self._create_freshdesk(ticket)
        logger.info("Support ticket created: %s tenant=%s priority=%s",
                    ticket.ticket_id, ticket.tenant_id, ticket.priority.value)
        return ticket

    def get_ticket(self, ticket_id: str) -> Optional[SupportTicket]:
        return self._tickets.get(ticket_id)

    def list_tenant_tickets(self, tenant_id: str,
                             open_only: bool = True) -> List[SupportTicket]:
        tickets = [t for t in self._tickets.values() if t.tenant_id == tenant_id]
        if open_only:
            tickets = [t for t in tickets if t.status != "resolved"]
        return sorted(tickets, key=lambda t: t.created_at, reverse=True)

    def resolve_ticket(self, ticket_id: str) -> bool:
        ticket = self._tickets.get(ticket_id)
        if not ticket:
            return False
        ticket.status = "resolved"
        ticket.resolved_at = datetime.utcnow()
        return True

    def _create_zendesk(self, ticket: SupportTicket) -> Optional[str]:
        import requests
        try:
            payload = {
                "ticket": {
                    "subject": ticket.subject,
                    "comment": {"body": ticket.description},
                    "priority": ticket.priority.value,
                    "tags": ticket.tags,
                }
            }
            resp = requests.post(
                f"{self.base_url}/api/v2/tickets.json",
                json=payload,
                auth=("backup_system/token", self.api_key),
                timeout=15,
            )
            resp.raise_for_status()
            return str(resp.json()["ticket"]["id"])
        except Exception as exc:
            logger.error("Zendesk ticket creation failed: %s", exc)
            return None

    def _create_freshdesk(self, ticket: SupportTicket) -> Optional[str]:
        import requests
        priority_map = {"low": 1, "medium": 2, "high": 3, "critical": 4}
        try:
            payload = {
                "subject": ticket.subject,
                "description": ticket.description,
                "priority": priority_map.get(ticket.priority.value, 2),
                "status": 2,  # Open
                "email": ticket.created_by,
            }
            resp = requests.post(
                f"{self.base_url}/api/v2/tickets",
                json=payload,
                auth=(self.api_key, "X"),
                timeout=15,
            )
            resp.raise_for_status()
            return str(resp.json()["id"])
        except Exception as exc:
            logger.error("Freshdesk ticket creation failed: %s", exc)
            return None
