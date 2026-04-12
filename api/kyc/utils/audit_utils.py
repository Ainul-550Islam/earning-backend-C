# kyc/utils/audit_utils.py  ── WORLD #1
"""Audit trail helper utilities"""
import logging

logger = logging.getLogger(__name__)


def model_to_dict_safe(instance, fields: list = None) -> dict:
    """Safely serialize a model instance to dict for audit before/after states."""
    if instance is None:
        return {}
    try:
        from django.forms.models import model_to_dict as _mtd
        data = _mtd(instance, fields=fields) if fields else _mtd(instance)
        # Convert non-serializable types
        result = {}
        for k, v in data.items():
            if hasattr(v, 'isoformat'):
                result[k] = v.isoformat()
            elif hasattr(v, 'name'):   # FileField
                result[k] = str(v)
            elif hasattr(v, '__iter__') and not isinstance(v, (str, list, dict)):
                result[k] = list(v)
            else:
                result[k] = v
        return result
    except Exception as e:
        logger.warning(f"model_to_dict_safe failed: {e}")
        return {'id': getattr(instance, 'pk', None)}


def get_client_ip(request) -> str:
    """Extract real client IP from request."""
    if not request:
        return ''
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if x_forwarded:
        return x_forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


def get_user_agent(request) -> str:
    return request.META.get('HTTP_USER_AGENT', '') if request else ''


def log_kyc_audit(entity_type, entity_id, action, actor=None, tenant=None,
                  before=None, after=None, description='', severity='low', request=None):
    """Shortcut to KYCAuditTrail.log() with request context."""
    try:
        from ..models import KYCAuditTrail
        KYCAuditTrail.log(
            entity_type=entity_type, entity_id=entity_id, action=action,
            actor=actor, tenant=tenant, before=before, after=after,
            description=description, severity=severity,
            actor_ip=get_client_ip(request), actor_agent=get_user_agent(request),
        )
    except Exception as e:
        logger.error(f"log_kyc_audit failed: {e}")
