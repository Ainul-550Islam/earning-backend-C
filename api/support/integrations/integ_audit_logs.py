# api/support/integrations/integ_audit_logs.py  — WORLD #1
"""
Integration Audit Logs — সব integration events log করে।
Support system-এর সব cross-app calls এখানে record হয়।
"""
import logging
from typing import Any, Optional
from django.utils import timezone

from .integ_constants import AUDIT_RETENTION_DAYS, AUDIT_SENSITIVE_FIELDS

logger = logging.getLogger(__name__)


class IntegrationAuditLogger:
    """
    Comprehensive audit logging for support integration events.
    
    Logs:
    - Wallet credits/freezes from dispute approvals
    - Fraud flags triggered by support
    - Cross-app data access
    - Webhook receipts
    """

    def log_wallet_credit(self, user, amount, reason: str, ticket_id: str = '', agent=None) -> None:
        """Log when support credits user wallet."""
        self._log('wallet_credit', user, {
            'amount':    str(amount),
            'reason':    reason,
            'ticket_id': ticket_id,
            'agent':     str(agent.id) if agent else 'auto',
        })

    def log_wallet_freeze(self, user, amount, reason: str, agent=None) -> None:
        """Log wallet freeze operation."""
        self._log('wallet_freeze', user, {'amount': str(amount), 'reason': reason})

    def log_dispute_auto_approved(self, dispute, confidence: float) -> None:
        """Log auto-approved offer dispute."""
        self._log('dispute_auto_approved', dispute.user, {
            'dispute_id':    dispute.id,
            'offer_id':      dispute.offer_id,
            'amount':        str(dispute.expected_amount),
            'confidence':    f'{confidence:.0%}',
        })

    def log_dispute_rejected(self, dispute, reason: str) -> None:
        """Log rejected dispute."""
        self._log('dispute_rejected', dispute.user, {
            'dispute_id': dispute.id,
            'offer_id':   dispute.offer_id,
            'reason':     reason,
        })

    def log_fraud_flag(self, user, reason: str, flagged_by=None) -> None:
        """Log when support flags a user for fraud."""
        self._log('user_fraud_flagged', user, {
            'reason':     reason,
            'flagged_by': str(flagged_by.id) if flagged_by else 'auto',
        })

    def log_webhook_received(self, event_type: str, payload: dict, result: dict) -> None:
        """Log incoming webhook."""
        # Mask sensitive fields
        safe_payload = {k: '***' if k in AUDIT_SENSITIVE_FIELDS else v for k, v in payload.items()}
        self._log('webhook_received', None, {
            'event_type': event_type,
            'payload':    safe_payload,
            'result':     result.get('status', ''),
        })

    def log_agent_user_context_access(self, agent, target_user, ticket_id: str = '') -> None:
        """Log when agent accesses user cross-app context."""
        self._log('agent_user_context_access', target_user, {
            'agent_id':  str(agent.id),
            'ticket_id': ticket_id,
        })

    def log_integration_error(self, adapter: str, method: str, error: str, user=None) -> None:
        """Log integration call errors."""
        self._log('integration_error', user, {
            'adapter': adapter,
            'method':  method,
            'error':   error[:500],
        })

    def _log(self, event_type: str, user, data: dict) -> None:
        """Write to support audit log + django audit_logs app if available."""
        # Always write to Python logger
        logger.info(f'AUDIT [{event_type}] user={user.id if user else "system"} data={data}')

        # Try to write to support notification log
        try:
            from api.support.models import SupportNotificationLog
            SupportNotificationLog.objects.create(
                user      = user,
                channel   = 'api',
                event     = event_type,
                recipient = str(user.id) if user else 'system',
                status    = 'sent',
            )
        except Exception:
            pass

        # Try main audit_logs app
        try:
            from django.apps import apps
            for audit_model in [('audit_logs','AuditLog'),('audit_logs','AuditEntry')]:
                try:
                    M = apps.get_model(*audit_model)
                    M.objects.create(
                        user       = user,
                        action     = event_type,
                        extra_data = data,
                    )
                    return
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f'Audit log write to audit_logs app failed: {e}')

    def get_user_audit_history(self, user, limit: int = 20) -> list:
        """Get audit history for a user."""
        try:
            from api.support.models import SupportNotificationLog
            logs = SupportNotificationLog.objects.filter(user=user).order_by('-created_at')[:limit]
            return [{'event': l.event, 'created_at': l.created_at.isoformat()} for l in logs]
        except Exception:
            return []

    def cleanup_old_logs(self, days: int = AUDIT_RETENTION_DAYS) -> int:
        """Remove old audit logs beyond retention period."""
        try:
            from django.utils import timezone
            from datetime import timedelta
            from api.support.models import SupportNotificationLog
            cutoff  = timezone.now() - timedelta(days=days)
            deleted, _ = SupportNotificationLog.objects.filter(created_at__lte=cutoff).delete()
            logger.info(f'Audit log cleanup: {deleted} records deleted (older than {days} days)')
            return deleted
        except Exception as e:
            logger.error(f'Audit log cleanup failed: {e}')
            return 0


audit_logger = IntegrationAuditLogger()