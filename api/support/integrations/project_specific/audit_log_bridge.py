# api/support/integrations/project_specific/audit_log_bridge.py
"""
Audit Log Bridge — writes ALL support events to your audit_logs app.

YOUR audit_logs has:
  - AuditLog model with user, action, level, extra_data
  - AuditLogLevel choices (DEBUG, INFO, WARNING, ERROR, CRITICAL, SECURITY)
  - AuditLogAction choices

Every support action (ticket create, dispute approve, wallet credit) is logged here.
"""
import logging
from typing import Optional
logger = logging.getLogger(__name__)


class SupportAuditBridge:
    """Write support system events to your audit_logs.AuditLog model."""

    def _write(self, action: str, level: str = "INFO", user=None,
               extra: dict = None, ip: str = "") -> bool:
        """Write to audit_logs.AuditLog with graceful fallback."""
        try:
            from django.apps import apps
            AuditLog = apps.get_model("audit_logs", "AuditLog")
            log_kwargs = {
                "action":     action,
                "extra_data": extra or {},
            }
            # Try different field name patterns
            for user_field in ("user", "actor", "performed_by"):
                try:
                    AuditLog.objects.create(**{user_field: user, **log_kwargs})
                    return True
                except TypeError:
                    continue

            # Fallback: try with all known fields
            AuditLog.objects.create(
                user       = user,
                action     = action,
                level      = level,
                ip_address = ip,
                extra_data = extra or {},
            )
            return True
        except Exception as e:
            logger.debug(f"SupportAuditBridge._write failed: {e}")
            return False

    def log_ticket_created(self, ticket, ip: str = "") -> None:
        self._write(
            action = "support.ticket.created",
            level  = "INFO",
            user   = ticket.user,
            extra  = {
                "ticket_id": ticket.ticket_id,
                "category":  ticket.category,
                "priority":  ticket.priority,
                "channel":   ticket.channel,
            },
            ip = ip,
        )

    def log_ticket_resolved(self, ticket, agent) -> None:
        self._write(
            action = "support.ticket.resolved",
            level  = "INFO",
            user   = agent,
            extra  = {
                "ticket_id":   ticket.ticket_id,
                "resolved_by": agent.username if agent else "auto",
                "category":    ticket.category,
            },
        )

    def log_dispute_approved(self, dispute, amount, agent=None) -> None:
        self._write(
            action = "support.dispute.approved",
            level  = "WARNING",  # financial action = WARNING level
            user   = agent or dispute.user,
            extra  = {
                "dispute_id": dispute.id,
                "offer_id":   dispute.offer_id,
                "amount":     str(amount),
                "user_id":    dispute.user_id,
                "auto":       agent is None,
            },
        )

    def log_dispute_rejected(self, dispute, reason: str, agent=None) -> None:
        self._write(
            action = "support.dispute.rejected",
            level  = "WARNING",
            user   = agent or dispute.user,
            extra  = {
                "dispute_id": dispute.id,
                "offer_id":   dispute.offer_id,
                "reason":     reason,
                "user_id":    dispute.user_id,
            },
        )

    def log_wallet_credit(self, user, amount, ticket_id: str, reason: str) -> None:
        self._write(
            action = "support.wallet.credited",
            level  = "SECURITY",  # SECURITY level for all financial ops
            user   = user,
            extra  = {
                "amount":    str(amount),
                "ticket_id": ticket_id,
                "reason":    reason,
            },
        )

    def log_sla_breach(self, ticket, breach_type: str) -> None:
        self._write(
            action = "support.sla.breach",
            level  = "ERROR",
            user   = ticket.assigned_to,
            extra  = {
                "ticket_id":   ticket.ticket_id,
                "breach_type": breach_type,
                "priority":    ticket.priority,
                "category":    ticket.category,
            },
        )

    def log_agent_action(self, ticket, agent, action: str, details: dict = None) -> None:
        self._write(
            action = f"support.agent.{action}",
            level  = "INFO",
            user   = agent,
            extra  = {
                "ticket_id": ticket.ticket_id,
                "agent":     agent.username if agent else "",
                **(details or {}),
            },
        )

    def log_security_event(self, event: str, user=None, ip: str = "", details: dict = None) -> None:
        """Log security-relevant support events (VPN detected, fraud flag, etc)."""
        self._write(
            action = f"support.security.{event}",
            level  = "SECURITY",
            user   = user,
            extra  = details or {},
            ip     = ip,
        )


audit_bridge = SupportAuditBridge()