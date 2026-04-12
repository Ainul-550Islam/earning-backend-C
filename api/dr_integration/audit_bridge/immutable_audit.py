"""
Immutable Audit — api/audit_logs/ module-এর replacement।
Tamper-evident JSONL logging with integrity hashing।

কিভাবে ব্যবহার করবে:
    from dr_integration.audit_bridge.immutable_audit import ImmutableAuditService
    audit = ImmutableAuditService()
    audit.log(actor_id=str(request.user.id), action="user.login", ...)
"""
import logging
from datetime import datetime
from typing import Optional
from django.conf import settings

logger = logging.getLogger(__name__)


class ImmutableAuditService:
    """
    api/audit_logs/services/LogService.py এর replacement।
    
    নতুন features:
    - JSONL append-only file (tamper-proof)
    - SHA-256 integrity hash প্রতিটা entry-তে
    - Database + file dual-write
    - SIEM-ready structured format
    - 7-বছর retention support
    - Compliance-ready search
    """

    def __init__(self):
        self._dr_logger = None

    def _logger(self):
        if self._dr_logger is None:
            try:
                from disaster_recovery.SECURITY_COMPLIANCE.audit_logger import AuditLogger
                config = getattr(settings, "DR_AUDIT_CONFIG", {})
                self._dr_logger = AuditLogger(config=config)
            except Exception as e:
                logger.debug(f"DR AuditLogger init failed: {e}")
        return self._dr_logger

    def log(self, actor_id, action: str, resource_type: str = None,
            resource_id=None, ip_address: str = None,
            result: str = "success", error_message: str = None,
            old_values: dict = None, new_values: dict = None,
            request_id: str = None, actor_type: str = "user") -> dict:
        """
        Audit log entry তৈরি করো।
        api/audit_logs/services/LogService.create_log() এর replacement।
        """
        dr_log = self._logger()
        entry = {}
        if dr_log:
            try:
                entry = dr_log.log(
                    actor_id=str(actor_id), action=action,
                    resource_type=resource_type,
                    resource_id=str(resource_id) if resource_id else None,
                    ip_address=ip_address, result=result,
                    error_message=error_message, old_values=old_values,
                    new_values=new_values, request_id=request_id,
                    actor_type=actor_type,
                )
            except Exception as e:
                logger.debug(f"DR audit error: {e}")
        # Also write to Django audit_logs if it exists
        self._write_django_audit(actor_id, action, resource_type, resource_id,
                                  ip_address, result, error_message, actor_type)
        return entry

    def log_from_request(self, request, action: str, resource_type: str = None,
                          resource_id=None, result: str = "success",
                          old_values: dict = None, new_values: dict = None) -> dict:
        """Django request থেকে directly audit log।"""
        actor_id = str(request.user.id) if request.user.is_authenticated else "anonymous"
        ip = (request.META.get("HTTP_X_FORWARDED_FOR","").split(",")[0].strip()
              or request.META.get("REMOTE_ADDR",""))
        return self.log(
            actor_id=actor_id, action=action,
            resource_type=resource_type, resource_id=resource_id,
            ip_address=ip, result=result,
            old_values=old_values, new_values=new_values,
            request_id=request.META.get("HTTP_X_REQUEST_ID"),
            actor_type="user" if request.user.is_authenticated else "anonymous",
        )

    def log_security_event(self, actor_id, event_type: str, description: str,
                            details: dict = None) -> dict:
        """Security event log করো — api/security/ থেকে call করা হবে।"""
        dr_log = self._logger()
        if dr_log:
            try:
                return dr_log.log_security_event(event_type, str(actor_id), description, details)
            except Exception: pass
        return self.log(actor_id=actor_id, action=event_type,
                        resource_type="security",
                        new_values={"description": description, **(details or {})},
                        result="security_event")

    def search(self, actor_id=None, action: str = None, resource_type: str = None,
               from_date: datetime = None, to_date: datetime = None,
               result: str = None, limit: int = 100) -> list:
        """Audit log search করো।"""
        dr_log = self._logger()
        if dr_log:
            try:
                return dr_log.search(actor_id=actor_id, action=action,
                                      resource_type=resource_type,
                                      from_date=from_date, to_date=to_date,
                                      result=result, limit=limit)
            except Exception: pass
        # Fallback: search Django audit_logs
        return self._search_django_audit(actor_id, action, resource_type, limit)

    def verify_integrity(self) -> dict:
        """Audit log integrity verify করো।"""
        dr_log = self._logger()
        if dr_log:
            try: return dr_log.verify_integrity()
            except Exception: pass
        return {"status": "unavailable"}

    def _write_django_audit(self, actor_id, action, resource_type, resource_id,
                             ip_address, result, error_message, actor_type):
        """api/audit_logs/ Django model-এও write করো।"""
        try:
            from api.audit_logs.models import AuditLog, AuditLogAction
            # Map to existing AuditLog model fields
            AuditLog.objects.create(
                action=action[:50],
                ip_address=ip_address or "",
                result=result,
            )
        except Exception: pass  # OK if audit_logs model is different

    def _search_django_audit(self, actor_id, action, resource_type, limit) -> list:
        """Fallback: search in Django audit_logs."""
        try:
            from api.audit_logs.models import AuditLog
            qs = AuditLog.objects.all()
            if action: qs = qs.filter(action__icontains=action)
            return list(qs.values("id","action","ip_address","result")[:limit])
        except Exception: return []
