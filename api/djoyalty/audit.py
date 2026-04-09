# api/djoyalty/audit.py
"""
Audit log utilities for Djoyalty।
Compliance এবং debugging এর জন্য।
"""
import logging
import json
from django.utils import timezone
from typing import Optional, Dict, Any

logger = logging.getLogger('djoyalty.audit')
audit_logger = logging.getLogger('djoyalty.audit.structured')


class AuditAction:
    """Audit action constants।"""
    # Points
    POINTS_EARNED = 'points.earned'
    POINTS_REDEEMED = 'points.redeemed'
    POINTS_ADJUSTED = 'points.adjusted'
    POINTS_EXPIRED = 'points.expired'
    POINTS_TRANSFERRED = 'points.transferred'
    POINTS_RESERVED = 'points.reserved'
    POINTS_RESERVATION_RELEASED = 'points.reservation.released'
    POINTS_RESERVATION_CONFIRMED = 'points.reservation.confirmed'

    # Tier
    TIER_ASSIGNED = 'tier.assigned'
    TIER_UPGRADED = 'tier.upgraded'
    TIER_DOWNGRADED = 'tier.downgraded'
    TIER_FORCE_CHANGED = 'tier.force_changed'

    # Redemption
    REDEMPTION_CREATED = 'redemption.created'
    REDEMPTION_APPROVED = 'redemption.approved'
    REDEMPTION_REJECTED = 'redemption.rejected'
    REDEMPTION_CANCELLED = 'redemption.cancelled'

    # Voucher
    VOUCHER_GENERATED = 'voucher.generated'
    VOUCHER_USED = 'voucher.used'
    VOUCHER_EXPIRED = 'voucher.expired'

    # Customer
    CUSTOMER_CREATED = 'customer.created'
    CUSTOMER_UPDATED = 'customer.updated'
    CUSTOMER_DEACTIVATED = 'customer.deactivated'

    # Fraud
    FRAUD_FLAGGED = 'fraud.flagged'
    FRAUD_RESOLVED = 'fraud.resolved'
    ACCOUNT_SUSPENDED = 'account.suspended'

    # Admin
    ADMIN_ADJUSTMENT = 'admin.adjustment'
    ADMIN_TIER_OVERRIDE = 'admin.tier_override'


class AuditLog:
    """
    Structured audit logging।
    JSON format — ELK/Splunk/CloudWatch এর জন্য।
    """

    @staticmethod
    def log(
        action: str,
        actor: Optional[Any] = None,
        customer: Optional[Any] = None,
        tenant: Optional[Any] = None,
        data: Optional[Dict] = None,
        correlation_id: Optional[str] = None,
        request=None,
    ):
        """
        Structured audit log entry।
        """
        entry = {
            'timestamp': timezone.now().isoformat(),
            'action': action,
            'actor_id': getattr(actor, 'id', None) if actor else None,
            'actor_str': str(actor) if actor else 'system',
            'customer_id': getattr(customer, 'id', None) if customer else None,
            'customer_code': getattr(customer, 'code', None) if customer else None,
            'tenant_id': getattr(tenant, 'id', None) if tenant else None,
            'correlation_id': correlation_id or (
                getattr(request, 'correlation_id', None) if request else None
            ),
            'ip_address': AuditLog._get_ip(request) if request else None,
            'data': data or {},
        }

        audit_logger.info(json.dumps(entry, default=str))
        return entry

    @staticmethod
    def log_points_earned(customer, points, source, tenant=None, request=None):
        return AuditLog.log(
            action=AuditAction.POINTS_EARNED,
            customer=customer,
            tenant=tenant or getattr(customer, 'tenant', None),
            data={'points': str(points), 'source': source},
            request=request,
        )

    @staticmethod
    def log_redemption(customer, redemption_request, action: str, actor=None, request=None):
        return AuditLog.log(
            action=action,
            actor=actor,
            customer=customer,
            tenant=getattr(customer, 'tenant', None),
            data={
                'redemption_id': redemption_request.id,
                'points_used': str(redemption_request.points_used),
                'status': redemption_request.status,
            },
            request=request,
        )

    @staticmethod
    def log_tier_change(customer, from_tier, to_tier, change_type, request=None):
        return AuditLog.log(
            action=AuditAction.TIER_UPGRADED if change_type == 'upgrade' else AuditAction.TIER_DOWNGRADED,
            customer=customer,
            tenant=getattr(customer, 'tenant', None),
            data={
                'from_tier': from_tier,
                'to_tier': to_tier,
                'change_type': change_type,
            },
            request=request,
        )

    @staticmethod
    def log_fraud(customer, risk_level, action_taken, description, request=None):
        return AuditLog.log(
            action=AuditAction.FRAUD_FLAGGED,
            customer=customer,
            tenant=getattr(customer, 'tenant', None),
            data={
                'risk_level': risk_level,
                'action_taken': action_taken,
                'description': description,
            },
            request=request,
        )

    @staticmethod
    def log_admin_adjustment(customer, points, reason, admin_user, request=None):
        return AuditLog.log(
            action=AuditAction.ADMIN_ADJUSTMENT,
            actor=admin_user,
            customer=customer,
            tenant=getattr(customer, 'tenant', None),
            data={'points': str(points), 'reason': reason},
            request=request,
        )

    @staticmethod
    def _get_ip(request) -> Optional[str]:
        """Real IP behind proxy।"""
        if not request:
            return None
        forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
        if forwarded:
            return forwarded.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')
