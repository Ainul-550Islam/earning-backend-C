# api/referral/INTEGRATION_SYSTEM/integ_audit_logs.py
# Referral-specific audit logging — integrates with api/audit_logs
# ============================================================

import logging
from typing import Any, Dict, Optional
from .integ_constants import (
    AUDIT_COMMISSION_PAID, AUDIT_REFERRAL_CREATED,
    AUDIT_FRAUD_FLAGGED, AUDIT_FRAUD_CLEARED,
    AUDIT_FRAUD_CONFIRMED, AUDIT_CLAWBACK_INITIATED,
    AUDIT_CLAWBACK_APPROVED, AUDIT_SETTINGS_UPDATED,
    AUDIT_BLACKLIST_ADDED, AUDIT_MILESTONE_AWARDED,
    AUDIT_CONTEST_PRIZE_PAID, AUDIT_CAMPAIGN_CREATED,
)

logger = logging.getLogger(__name__)


class ReferralAuditLogger:
    """
    Structured audit logging for referral module.
    Integrates with api/audit_logs/models.py → AuditLog model.
    Falls back to Python logging if audit_logs module unavailable.
    """

    @staticmethod
    def log(
        action: str,
        user=None,
        data: Dict = None,
        level: str = 'INFO',
        ip_address: str = '',
    ) -> None:
        """Generic audit log entry."""
        try:
            from api.audit_logs.models import AuditLog, AuditLogLevel, AuditLogAction
            AuditLog.objects.create(
                user=user,
                action=action,
                level=level,
                metadata=data or {},
                ip_address=ip_address or '',
            )
        except ImportError:
            logger.info(f'[AuditLog] {action} | user={getattr(user, "id", "?")} | {data}')
        except Exception as e:
            logger.warning(f'[AuditLog] Failed to write audit log: {e}')
            logger.info(f'[AuditLog] {action} | user={getattr(user, "id", "?")} | {data}')

    @staticmethod
    def log_commission_paid(
        referrer_username: str, earner, amount: float,
        level: int, source: str,
    ) -> None:
        ReferralAuditLogger.log(
            action=AUDIT_COMMISSION_PAID,
            user=earner,
            data={
                'referrer': referrer_username,
                'earner_id': getattr(earner, 'id', '?'),
                'amount': str(amount),
                'level': level,
                'source': source,
            },
        )

    @staticmethod
    def log_referral_created(referrer, referred_user, referral_id: int) -> None:
        ReferralAuditLogger.log(
            action=AUDIT_REFERRAL_CREATED,
            user=referred_user,
            data={
                'referrer_id': getattr(referrer, 'id', '?'),
                'referrer_username': getattr(referrer, 'username', '?'),
                'referred_user_id': getattr(referred_user, 'id', '?'),
                'referral_id': referral_id,
            },
        )

    @staticmethod
    def log_fraud_flagged(referral_id: int, fraud_score: int, flags: list) -> None:
        ReferralAuditLogger.log(
            action=AUDIT_FRAUD_FLAGGED,
            level='WARNING',
            data={
                'referral_id': referral_id,
                'fraud_score': fraud_score,
                'flags': flags,
            },
        )

    @staticmethod
    def log_fraud_cleared(referral_id: int, admin_user, notes: str = '') -> None:
        ReferralAuditLogger.log(
            action=AUDIT_FRAUD_CLEARED,
            user=admin_user,
            data={'referral_id': referral_id, 'notes': notes},
        )

    @staticmethod
    def log_fraud_confirmed(referral_id: int, admin_user, notes: str = '') -> None:
        ReferralAuditLogger.log(
            action=AUDIT_FRAUD_CONFIRMED,
            user=admin_user,
            level='WARNING',
            data={'referral_id': referral_id, 'notes': notes},
        )

    @staticmethod
    def log_clawback_initiated(commission_id: int, amount: float, reason: str) -> None:
        ReferralAuditLogger.log(
            action=AUDIT_CLAWBACK_INITIATED,
            level='WARNING',
            data={
                'commission_id': commission_id,
                'amount': str(amount),
                'reason': reason,
            },
        )

    @staticmethod
    def log_clawback_approved(clawback_id: int, admin_user, amount: float) -> None:
        ReferralAuditLogger.log(
            action=AUDIT_CLAWBACK_APPROVED,
            user=admin_user,
            level='WARNING',
            data={'clawback_id': clawback_id, 'amount': str(amount)},
        )

    @staticmethod
    def log_settings_updated(admin_user, changes: Dict) -> None:
        ReferralAuditLogger.log(
            action=AUDIT_SETTINGS_UPDATED,
            user=admin_user,
            data={'changes': {k: str(v) for k, v in changes.items()}},
        )

    @staticmethod
    def log_blacklist_added(admin_user, pattern_type: str, pattern_value: str) -> None:
        ReferralAuditLogger.log(
            action=AUDIT_BLACKLIST_ADDED,
            user=admin_user,
            level='WARNING',
            data={'pattern_type': pattern_type, 'pattern_value': pattern_value},
        )

    @staticmethod
    def log_milestone_awarded(user, milestone_value: float, bonus_amount: float) -> None:
        ReferralAuditLogger.log(
            action=AUDIT_MILESTONE_AWARDED,
            user=user,
            data={
                'milestone_value': str(milestone_value),
                'bonus_amount': str(bonus_amount),
            },
        )

    @staticmethod
    def log_campaign_created(admin_user, campaign_id: int, campaign_name: str) -> None:
        ReferralAuditLogger.log(
            action=AUDIT_CAMPAIGN_CREATED,
            user=admin_user,
            data={'campaign_id': campaign_id, 'campaign_name': campaign_name},
        )