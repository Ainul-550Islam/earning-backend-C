# api/djoyalty/integration_system/integ_audit_logs.py
"""
Integration Audit Logs -- Complete audit trail for all integrations।
Every external call, postback, webhook, payment logged here।
"""
import logging
import time
from typing import Any, Optional
from django.utils import timezone

logger = logging.getLogger(__name__)


class IntegAuditEntry:
    """Single audit log entry।"""
    def __init__(self, integration: str, action: str,
                  success: bool, duration_ms: float = 0,
                  customer_id: int = None, request_data: dict = None,
                  response_data: dict = None, error: str = '',
                  ip_address: str = ''):
        self.integration = integration
        self.action = action
        self.success = success
        self.duration_ms = duration_ms
        self.customer_id = customer_id
        self.request_data = request_data or {}
        self.response_data = response_data or {}
        self.error = error
        self.ip_address = ip_address
        self.timestamp = timezone.now()

    def to_dict(self) -> dict:
        return {
            'integration': self.integration,
            'action': self.action,
            'success': self.success,
            'duration_ms': round(self.duration_ms, 2),
            'customer_id': self.customer_id,
            'error': self.error,
            'timestamp': self.timestamp.isoformat(),
        }


class IntegAuditLogger:
    """
    Integration audit logger।
    Logs all external integration calls to DB (AdminAuditLog) + file।

    Usage:
        IntegAuditLogger.log_payment('bkash', 'create_payment',
            success=True, customer_id=1,
            request={'amount': 100}, response={'paymentID': 'xxx'})

        IntegAuditLogger.log_postback('cpalead', 'postback',
            success=True, txn_id='abc123', payout=1.5, customer_id=1)

        # Context manager
        with IntegAuditLogger.track('bkash', 'verify_payment', customer_id=1) as audit:
            result = bkash.query_payment(payment_id)
            audit.response = result
    """

    @staticmethod
    def log(integration: str, action: str, success: bool,
             customer_id: int = None, duration_ms: float = 0,
             request_data: dict = None, response_data: dict = None,
             error: str = '', ip_address: str = '',
             severity: str = 'info', tenant=None):
        """Log integration action to AdminAuditLog।"""
        try:
            from ..models.audit import AdminAuditLog
            AdminAuditLog.log(
                action=f'{integration}.{action}',
                category='api',
                customer=None,
                performed_by=f'integration:{integration}',
                old_value={'request': request_data} if request_data else None,
                new_value={'response': response_data} if response_data else None,
                description=f'{integration} {action}: {"OK" if success else f"FAILED: {error}"}',
                severity='info' if success else 'warning',
                object_type=integration,
            )
        except Exception as e:
            logger.debug('IntegAuditLogger.log error: %s', e)

        # Also log to standard logger
        level = logging.INFO if success else logging.WARNING
        logger.log(level, 'IntegAudit[%s.%s]: %s (%.1fms%s)',
                   integration, action,
                   '✓' if success else f'✗ {error}',
                   duration_ms,
                   f' customer={customer_id}' if customer_id else '')

    @staticmethod
    def log_payment(integration: str, action: str, success: bool,
                     customer_id: int = None, amount=None,
                     reference: str = '', error: str = '',
                     request_data: dict = None, response_data: dict = None):
        """Log payment integration action।"""
        IntegAuditLogger.log(
            integration=integration,
            action=action,
            success=success,
            customer_id=customer_id,
            request_data={'amount': str(amount), 'reference': reference, **(request_data or {})},
            response_data=response_data,
            error=error,
        )

    @staticmethod
    def log_postback(provider: str, action: str = 'postback',
                      success: bool = True, txn_id: str = '',
                      payout: float = 0, customer_id: int = None,
                      error: str = '', ip_address: str = ''):
        """Log incoming postback।"""
        IntegAuditLogger.log(
            integration=provider,
            action=action,
            success=success,
            customer_id=customer_id,
            request_data={'txn_id': txn_id, 'payout': payout},
            error=error,
            ip_address=ip_address,
        )

    @staticmethod
    def log_sms(provider: str, to: str, success: bool,
                 message_preview: str = '', error: str = ''):
        """Log SMS send।"""
        # Mask phone number for privacy
        masked = f'{to[:3]}****{to[-2:]}' if len(to) > 5 else '***'
        IntegAuditLogger.log(
            integration=provider,
            action='send_sms',
            success=success,
            request_data={'to': masked, 'preview': message_preview[:50]},
            error=error,
        )

    @staticmethod
    def log_webhook(url: str, event_type: str, success: bool,
                     status_code: int = None, attempt: int = 1):
        """Log outbound webhook delivery।"""
        IntegAuditLogger.log(
            integration='webhook',
            action='deliver',
            success=success,
            request_data={
                'url': url,
                'event': event_type,
                'attempt': attempt,
                'status_code': status_code,
            },
        )

    class _AuditContext:
        def __init__(self, integration: str, action: str, customer_id: int = None):
            self.integration = integration
            self.action = action
            self.customer_id = customer_id
            self.request = {}
            self.response = {}
            self._start = None
            self._success = True
            self._error = ''

        def __enter__(self):
            self._start = time.monotonic()
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            duration_ms = (time.monotonic() - self._start) * 1000
            if exc_type:
                self._success = False
                self._error = str(exc_val)
            IntegAuditLogger.log(
                integration=self.integration,
                action=self.action,
                success=self._success,
                customer_id=self.customer_id,
                duration_ms=duration_ms,
                request_data=self.request,
                response_data=self.response,
                error=self._error,
            )
            return False  # Don't suppress exceptions

    @classmethod
    def track(cls, integration: str, action: str,
               customer_id: int = None) -> '_AuditContext':
        """Context manager for automatic audit logging।"""
        return cls._AuditContext(integration, action, customer_id)
