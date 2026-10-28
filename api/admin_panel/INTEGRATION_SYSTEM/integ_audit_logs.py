# api/admin_panel/INTEGRATION_SYSTEM/integ_audit_logs.py
"""
IntegrationAuditLogger — Comprehensive audit trail for all integration operations.
Every cross-app admin action is logged: who, what, which app, result, timestamp.
Queryable, exportable, compliance-ready.
"""
import json
import logging
from typing import Any, Dict, List, Optional
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


class IntegrationAuditLogger:
    """
    Logs all cross-app integration actions to the AdminActivity model
    and to a fast in-memory ring buffer for real-time monitoring.
    """

    RING_BUFFER_SIZE = 2000

    _buffer: List[Dict] = []

    @classmethod
    def log(
        cls,
        actor,
        app: str,
        action: str,
        payload: Optional[Dict] = None,
        result: Optional[Dict] = None,
        ip: str = '',
        correlation_id: str = '',
        severity: str = 'info',
    ) -> None:
        """
        Log an integration audit entry.

        Args:
            actor:          The user performing the action
            app:            Target app (e.g. 'wallet', 'fraud_detection')
            action:         Action name (e.g. 'adjust_balance', 'block_ip')
            payload:        Action input (sensitive fields stripped)
            result:         Result data
            ip:             Caller IP address
            correlation_id: Tracing ID for distributed tracing
            severity:       info | warning | error | critical
        """
        # Sanitize payload
        safe_payload = cls._sanitize(payload or {})
        success = (result or {}).get('success', True)

        entry = {
            'timestamp': timezone.now().isoformat(),
            'actor': actor.username if actor else 'system',
            'actor_id': actor.pk if actor else None,
            'app': app,
            'action': action,
            'payload': safe_payload,
            'success': success,
            'error': (result or {}).get('error', ''),
            'ip': ip,
            'correlation_id': correlation_id,
            'severity': severity if not success else 'info',
        }

        # Ring buffer for real-time monitoring
        cls._buffer.insert(0, entry)
        if len(cls._buffer) > cls.RING_BUFFER_SIZE:
            cls._buffer = cls._buffer[:cls.RING_BUFFER_SIZE]

        # Persist to AdminActivity model
        cls._persist(actor=actor, app=app, action=action,
                     safe_payload=safe_payload, result=result or {})

        # Log to Python logger
        log_fn = logger.warning if not success else logger.info
        log_fn(f"[IntegAudit] {actor.username if actor else 'system'}.{app}.{action} success={success} ip={ip}")

        # For critical severity, also trigger alert
        if severity == 'critical':
            cls._alert_critical(entry)

    @classmethod
    def _persist(cls, actor, app: str, action: str, safe_payload: dict, result: dict):
        try:
            from api.admin_panel.models.activity import AdminActivity
            AdminActivity.log(
                actor=actor,
                action=f'integ.{app}.{action}',
                model_name=app,
                changes={
                    'payload': safe_payload,
                    'result': {
                        'success': result.get('success'),
                        'error': result.get('error', ''),
                    }
                },
                status='success' if result.get('success') else 'failed',
            )
        except Exception as e:
            logger.debug(f"[IntegAudit] AdminActivity persist failed: {e}")

    @classmethod
    def _sanitize(cls, data: dict) -> dict:
        """Remove sensitive fields from audit payload."""
        dangerous = {'password', 'token', 'secret', 'api_key', 'private_key', 'pin', 'otp'}
        return {k: '***' if k.lower() in dangerous else v for k, v in data.items()}

    @classmethod
    def _alert_critical(cls, entry: dict):
        try:
            cache_key = 'admin_panel:integ_critical_alerts'
            alerts = cache.get(cache_key) or []
            alerts.insert(0, entry)
            cache.set(cache_key, alerts[:100], 86400)
        except Exception:
            pass

    # ==================== QUERY ====================

    @classmethod
    def get_recent(cls, limit: int = 100, app: str = '', action: str = '', success: Optional[bool] = None) -> List[Dict]:
        """Get recent audit entries from ring buffer."""
        entries = cls._buffer
        if app:
            entries = [e for e in entries if e['app'] == app]
        if action:
            entries = [e for e in entries if e['action'] == action]
        if success is not None:
            entries = [e for e in entries if e['success'] == success]
        return entries[:limit]

    @classmethod
    def get_stats(cls, hours: int = 24) -> Dict:
        """Audit stats for last N hours."""
        from django.utils import timezone
        entries = cls._buffer
        return {
            'total': len(entries),
            'failed': sum(1 for e in entries if not e.get('success')),
            'by_app': cls._count_by(entries, 'app'),
            'by_action': cls._count_by(entries, 'action'),
            'by_actor': cls._count_by(entries, 'actor'),
        }

    @classmethod
    def _count_by(cls, entries: List[Dict], field: str) -> Dict:
        counts = {}
        for entry in entries:
            val = entry.get(field, 'unknown')
            counts[val] = counts.get(val, 0) + 1
        return dict(sorted(counts.items(), key=lambda x: x[1], reverse=True)[:20])

    @classmethod
    def export_csv(cls, limit: int = 10000) -> str:
        """Export audit log to CSV string."""
        import io, csv
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['timestamp', 'actor', 'app', 'action', 'success', 'error', 'ip', 'correlation_id'])
        for entry in cls._buffer[:limit]:
            writer.writerow([
                entry.get('timestamp', ''),
                entry.get('actor', ''),
                entry.get('app', ''),
                entry.get('action', ''),
                entry.get('success', ''),
                entry.get('error', ''),
                entry.get('ip', ''),
                entry.get('correlation_id', ''),
            ])
        return output.getvalue()

    @classmethod
    def clear_buffer(cls) -> int:
        count = len(cls._buffer)
        cls._buffer = []
        return count