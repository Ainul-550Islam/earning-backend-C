# api/payment_gateways/integration_system/integ_audit_logs.py
# Audit logging for all integration events — immutable, append-only

import json
import logging
from django.utils import timezone
from django.db import models

logger = logging.getLogger(__name__)


class IntegAuditLog(models.Model):
    """
    Immutable audit log for all integration events.
    Records every cross-module interaction for compliance and debugging.
    Append-only — never update or delete records.
    """

    SEVERITY = (
        ('debug',    'Debug'),
        ('info',     'Info'),
        ('warning',  'Warning'),
        ('error',    'Error'),
        ('critical', 'Critical'),
    )

    # Event info
    event_type   = models.CharField(max_length=100, db_index=True)
    source_module= models.CharField(max_length=100)
    target_module= models.CharField(max_length=100, blank=True)
    severity     = models.CharField(max_length=10, choices=SEVERITY, default='info')

    # Payload (sanitized — no PII/secrets)
    payload      = models.JSONField(default=dict)
    result       = models.JSONField(default=dict)

    # Context
    user_id      = models.IntegerField(null=True, blank=True, db_index=True)
    reference_id = models.CharField(max_length=200, blank=True, db_index=True)
    ip_address   = models.GenericIPAddressField(null=True, blank=True)

    # Performance
    duration_ms  = models.IntegerField(default=0)
    success      = models.BooleanField(default=True)
    error_message= models.TextField(blank=True)

    # Immutable timestamp
    timestamp    = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label    = 'payment_gateways'
        verbose_name = 'Integration Audit Log'
        ordering     = ['-timestamp']
        indexes      = [
            models.Index(fields=['event_type', 'timestamp']),
            models.Index(fields=['user_id', 'timestamp']),
            models.Index(fields=['success', 'timestamp']),
        ]

    def __str__(self):
        return f'[{self.severity.upper()}] {self.event_type} | {self.source_module} → {self.target_module} | {self.timestamp}'

    def save(self, *args, **kwargs):
        """Prevent updates — only allow inserts."""
        if self.pk:
            logger.warning('Attempted to update immutable audit log — ignored')
            return
        super().save(*args, **kwargs)


class AuditLogger:
    """
    Helper class to create audit log entries.
    Handles DB writes asynchronously to not slow down request cycle.
    """

    def log(self, event_type: str, source_module: str,
             target_module: str = '', payload: dict = None,
             result: dict = None, user_id: int = None,
             reference_id: str = '', success: bool = True,
             severity: str = 'info', duration_ms: int = 0,
             error_message: str = '', ip_address: str = ''):
        """Create an audit log entry asynchronously."""
        import threading

        def _write():
            try:
                IntegAuditLog.objects.create(
                    event_type   = event_type,
                    source_module= source_module,
                    target_module= target_module,
                    severity     = severity,
                    payload      = self._sanitize(payload or {}),
                    result       = result or {},
                    user_id      = user_id,
                    reference_id = reference_id[:200] if reference_id else '',
                    ip_address   = ip_address or None,
                    duration_ms  = duration_ms,
                    success      = success,
                    error_message= error_message[:2000] if error_message else '',
                )
            except Exception as e:
                # Never let audit logging break the main flow
                logger.debug(f'Audit log write failed: {e}')

        thread = threading.Thread(target=_write, daemon=True)
        thread.start()

    def log_deposit(self, user, deposit, success: bool = True, error: str = ''):
        self.log(
            event_type    = 'deposit.completed' if success else 'deposit.failed',
            source_module = 'api.payment_gateways',
            target_module = 'api.wallet',
            payload       = {'gateway': deposit.gateway, 'amount': str(deposit.amount)},
            result        = {'net_amount': str(deposit.net_amount)},
            user_id       = user.id,
            reference_id  = deposit.reference_id,
            success       = success,
            severity      = 'info' if success else 'error',
            error_message = error,
        )

    def log_withdrawal(self, user, payout, success: bool = True, error: str = ''):
        self.log(
            event_type    = 'withdrawal.processed' if success else 'withdrawal.failed',
            source_module = 'api.payment_gateways',
            target_module = 'api.wallet',
            payload       = {'method': payout.payout_method, 'amount': str(payout.amount)},
            result        = {'net_amount': str(payout.net_amount)},
            user_id       = user.id,
            reference_id  = payout.reference_id,
            success       = success,
            severity      = 'info' if success else 'error',
            error_message = error,
        )

    def log_fraud(self, user, risk_score: int, action: str, reasons: list):
        self.log(
            event_type    = 'fraud.detected',
            source_module = 'api.payment_gateways.fraud',
            target_module = 'api.fraud_detection',
            payload       = {'risk_score': risk_score, 'reasons': reasons},
            result        = {'action': action},
            user_id       = getattr(user, 'id', None),
            success       = action != 'block',
            severity      = 'critical' if action == 'block' else 'warning',
        )

    def log_webhook(self, gateway: str, is_valid: bool, event_type: str = ''):
        self.log(
            event_type    = 'webhook.received',
            source_module = f'gateway.{gateway}',
            target_module = 'api.payment_gateways',
            payload       = {'gateway': gateway, 'event': event_type},
            result        = {'is_valid': is_valid},
            success       = is_valid,
            severity      = 'info' if is_valid else 'warning',
        )

    def _sanitize(self, payload: dict) -> dict:
        """Remove sensitive data before storing."""
        SENSITIVE = {'password', 'api_key', 'secret', 'token', 'cvv', 'pin', 'private_key'}
        return {
            k: '***' if any(s in k.lower() for s in SENSITIVE) else v
            for k, v in payload.items()
        }

    def get_recent(self, event_type: str = None, user_id: int = None,
                    hours: int = 24, limit: int = 100) -> list:
        """Get recent audit logs."""
        from datetime import timedelta
        since = timezone.now() - timedelta(hours=hours)
        qs    = IntegAuditLog.objects.filter(timestamp__gte=since)
        if event_type:
            qs = qs.filter(event_type=event_type)
        if user_id:
            qs = qs.filter(user_id=user_id)
        return list(qs.values()[:limit])


# Global audit logger instance
audit_logger = AuditLogger()
