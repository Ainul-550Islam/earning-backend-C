# kyc/mixins.py  ── WORLD #1
"""Reusable view mixins for KYC endpoints"""
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)


class KYCTenantMixin:
    """Automatically scope queries to current user's tenant."""

    def get_tenant(self):
        return getattr(self.request.user, 'tenant', None)

    def filter_by_tenant(self, queryset):
        tenant = self.get_tenant()
        if tenant:
            return queryset.filter(tenant=tenant)
        return queryset


class KYCAuditMixin:
    """Auto-log audit trail for state-changing operations."""

    def log_audit(self, entity_type, entity_id, action,
                  before=None, after=None, description='', severity='low'):
        try:
            from .utils.audit_utils import log_kyc_audit
            log_kyc_audit(
                entity_type=entity_type,
                entity_id=entity_id,
                action=action,
                actor=getattr(self, 'request', None) and self.request.user,
                tenant=self.get_tenant() if hasattr(self, 'get_tenant') else None,
                before=before,
                after=after,
                description=description,
                severity=severity,
                request=getattr(self, 'request', None),
            )
        except Exception as e:
            logger.warning(f"KYCAuditMixin.log_audit failed: {e}")


class KYCRateLimitMixin:
    """Add rate limiting to KYC views."""

    def check_rate_limit(self, action: str, limit: int, window: int) -> bool:
        user_id = self.request.user.id
        from .security.rate_limiter import KYCRateLimiter
        limiter = KYCRateLimiter(user_id=user_id)
        return limiter.allow(action, limit=limit, window=window)


class KYCBlacklistCheckMixin:
    """Check blacklist before KYC operations."""

    def is_blacklisted(self, phone=None, doc_number=None, ip=None) -> bool:
        from .services import KYCBlacklistService
        result = KYCBlacklistService.check_all(phone=phone, doc_number=doc_number, ip=ip)
        return result['is_blocked']


class KYCIPLogMixin:
    """Log IP for fraud detection."""

    def log_ip(self, kyc=None, action='kyc_access'):
        try:
            from .models import KYCIPTracker
            from .utils.audit_utils import get_client_ip, get_user_agent
            ip = get_client_ip(self.request)
            if ip:
                KYCIPTracker.objects.create(
                    user=self.request.user,
                    kyc=kyc,
                    ip_address=ip,
                    action=action,
                    user_agent=get_user_agent(self.request),
                )
        except Exception as e:
            logger.warning(f"KYCIPLogMixin.log_ip failed: {e}")
