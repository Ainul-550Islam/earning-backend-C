# api/djoyalty/sanctions.py
"""
Djoyalty Sanctions -- Fraud detection, account suspension, sanctions management।
Flag suspicious accounts, block cashouts, freeze points।
"Do not summarize or skip any logic. Provide the full code."
"""
import logging
from decimal import Decimal
from django.utils import timezone

logger = logging.getLogger(__name__)


class SanctionLevel:
    WARNING  = 'warning'
    FREEZE   = 'freeze'    # Points frozen -- can't earn or redeem
    SUSPEND  = 'suspend'   # Account suspended
    BAN      = 'ban'       # Permanent ban


class SanctionManager:
    """
    Manage customer account sanctions for fraud prevention।

    Usage:
        SanctionManager.flag_warning(customer, reason='Duplicate receipt')
        SanctionManager.freeze_account(customer, reason='Suspicious activity')
        SanctionManager.check_can_earn(customer)  # Returns (True/False, reason)
    """

    @staticmethod
    def flag_warning(customer, reason: str, details: dict = None) -> bool:
        """Add a warning flag to customer account।"""
        try:
            from .models.advanced import PointsAbuseLog
            from .models.audit import AdminAuditLog

            PointsAbuseLog.objects.create(
                customer=customer,
                tenant=customer.tenant,
                abuse_type='fraud_attempt',
                risk_level='medium',
                description=reason,
                details=details or {},
            )

            AdminAuditLog.log(
                action='sanction_warning',
                category='fraud',
                customer=customer,
                description=reason,
                severity='warning',
                new_value=details,
            )
            logger.warning('SanctionManager: WARNING for %s -- %s', customer.code, reason)
            return True
        except Exception as e:
            logger.error('SanctionManager.flag_warning error: %s', e)
            return False

    @staticmethod
    def freeze_account(customer, reason: str) -> bool:
        """Freeze customer account -- blocks earn/redeem but not login।"""
        try:
            from .models.audit import AdminAuditLog

            # Set is_verified=False to block operations
            if hasattr(customer, 'is_verified'):
                customer.is_verified = False
                customer.save(update_fields=['is_verified'])

            AdminAuditLog.log(
                action='account_frozen',
                category='fraud',
                customer=customer,
                description=reason,
                severity='critical',
            )
            logger.critical('SanctionManager: FROZEN %s -- %s', customer.code, reason)
            return True
        except Exception as e:
            logger.error('SanctionManager.freeze_account error: %s', e)
            return False

    @staticmethod
    def suspend_account(customer, reason: str) -> bool:
        """Suspend customer account -- blocks all operations।"""
        try:
            from .models.audit import AdminAuditLog

            customer.is_active = False
            customer.save(update_fields=['is_active'])

            AdminAuditLog.log(
                action='account_suspended',
                category='fraud',
                customer=customer,
                description=reason,
                severity='critical',
            )
            logger.critical('SanctionManager: SUSPENDED %s -- %s', customer.code, reason)

            # Notify customer
            try:
                from .services.NotificationService import NotificationService
                NotificationService.send(
                    customer, 'system',
                    title='⚠️ Account Suspended',
                    body='Your account has been suspended. Please contact support.',
                    priority='critical',
                )
            except Exception:
                pass

            return True
        except Exception as e:
            logger.error('SanctionManager.suspend_account error: %s', e)
            return False

    @staticmethod
    def unfreeze_account(customer, reason: str = 'Manually cleared') -> bool:
        """Remove freeze from customer account।"""
        try:
            from .models.audit import AdminAuditLog

            if hasattr(customer, 'is_verified'):
                customer.is_verified = True
                customer.save(update_fields=['is_verified'])

            AdminAuditLog.log(
                action='account_unfrozen',
                category='fraud',
                customer=customer,
                description=reason,
                severity='info',
            )
            return True
        except Exception as e:
            logger.error('SanctionManager.unfreeze_account error: %s', e)
            return False

    @staticmethod
    def check_can_earn(customer) -> tuple:
        """
        Check if customer is allowed to earn points।
        Returns: (can_earn: bool, reason: str)
        """
        if not customer.is_active:
            return False, 'Account is not active.'

        if hasattr(customer, 'is_verified') and not customer.is_verified:
            return False, 'Account is frozen pending verification.'

        # Check recent fraud flags
        try:
            from .models.advanced import PointsAbuseLog
            high_risk = PointsAbuseLog.objects.filter(
                customer=customer,
                is_resolved=False,
                risk_level__in=['high', 'critical'],
                created_at__gte=timezone.now() - __import__('datetime').timedelta(days=30),
            ).exists()
            if high_risk:
                return False, 'Account has unresolved high-risk fraud flags.'
        except Exception:
            pass

        return True, ''

    @staticmethod
    def check_can_cashout(customer) -> tuple:
        """Check if customer can cashout।"""
        can_earn, reason = SanctionManager.check_can_earn(customer)
        if not can_earn:
            return False, reason

        try:
            from .models.advanced import PointsAbuseLog
            any_flag = PointsAbuseLog.objects.filter(
                customer=customer,
                is_resolved=False,
            ).exists()
            if any_flag:
                return False, 'Cashout blocked: pending fraud review.'
        except Exception:
            pass

        return True, ''

    @staticmethod
    def get_sanction_history(customer) -> list:
        """Get sanction history for a customer।"""
        from .models.audit import AdminAuditLog
        return list(
            AdminAuditLog.objects.filter(
                customer=customer,
                action_category='fraud',
            ).order_by('-timestamp')[:20]
        )

    @staticmethod
    def auto_sanction_check(customer) -> dict:
        """
        Automated fraud check -- runs rules and auto-sanctions if needed।
        Called periodically by fraud_check_tasks।
        """
        result = {'customer': customer.code, 'actions': []}

        try:
            from .models.advanced import PointsAbuseLog, LoyaltyFraudRule
            from .models.points import PointsLedger
            from django.db.models import Sum, Count
            from datetime import timedelta

            now = timezone.now()
            last_24h = now - timedelta(hours=24)

            # Rule 1: Too many credits in 24h
            credits_24h = PointsLedger.objects.filter(
                customer=customer,
                txn_type='credit',
                created_at__gte=last_24h,
            ).aggregate(total=Sum('points'))['total'] or Decimal('0')

            if credits_24h > Decimal('50000'):
                SanctionManager.flag_warning(
                    customer,
                    reason=f'Suspicious: {credits_24h} points credited in 24h',
                    details={'credits_24h': str(credits_24h)},
                )
                result['actions'].append('warning: excessive_credits_24h')

            # Rule 2: Multiple receipt scans in 1 hour
            try:
                from .models.family_eco import ReceiptScan
                receipts_1h = ReceiptScan.objects.filter(
                    customer=customer,
                    submitted_at__gte=now - timedelta(hours=1),
                ).count()
                if receipts_1h > 10:
                    SanctionManager.flag_warning(
                        customer,
                        reason=f'Suspicious: {receipts_1h} receipt scans in 1 hour',
                    )
                    result['actions'].append('warning: excessive_receipt_scans')
            except Exception:
                pass

        except Exception as e:
            logger.error('SanctionManager.auto_sanction_check error: %s', e)

        return result
