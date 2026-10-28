# api/referral/INTEGRATION_SYSTEM/integ_handler.py
# Core event handlers — referral reacts to events from other modules
# task_completed → commission | offer_approved → commission
# user_registered → referral signup | fraud_confirmed → clawback
# ============================================================

import logging
from decimal import Decimal
from django.db import transaction
from .integ_constants import (
    SOURCE_TASK, SOURCE_OFFER, SOURCE_WITHDRAWAL,
    AUDIT_COMMISSION_PAID, AUDIT_REFERRAL_CREATED,
    AUDIT_FRAUD_CONFIRMED, AUDIT_CLAWBACK_INITIATED,
    QUEUE_REFERRAL_HIGH, QUEUE_REFERRAL_NORMAL,
)
from .integ_exceptions import (
    IntegrationError, ModuleUnavailableError, HandlerError
)

logger = logging.getLogger(__name__)


# ── INBOUND HANDLERS ──────────────────────────────────────────────────────────

@transaction.atomic
def handle_task_completed(
    user,
    task,
    earned_amount: Decimal,
    completion=None,
    **kwargs
) -> dict:
    """
    api/tasks → referral commission.

    Called when a user completes a task (MasterTask/UserTaskCompletion).
    Processes L1/L2/L3 commission for all ancestors.

    Integration point:
        api/tasks/services.py → TaskRevenueService.process_task_revenue()
        → fires EVENT_TASK_COMPLETED via event_bus.publish()
    """
    try:
        from api.referral.services.ReferralService import ReferralService
        results = ReferralService.process_multilevel_commission(
            earner=user,
            earned_amount=Decimal(str(earned_amount)),
            source_type=SOURCE_TASK,
            source_id=str(task.id) if task else '',
        )

        if results:
            _audit_commission_paid(
                user=user,
                results=results,
                source=f'task:{task.id}' if task else 'task',
            )
            logger.info(
                f'[IntegHandler] Task commission: user={user.id} '
                f'amount={earned_amount} → {len(results)} ancestors paid'
            )

        return {'success': True, 'commissions': results}

    except Exception as e:
        logger.error(f'[IntegHandler] handle_task_completed error: {e}')
        raise HandlerError(f'Task commission failed: {e}') from e


@transaction.atomic
def handle_offer_completed(
    user,
    conversion,
    user_net_reward: Decimal,
    offer_id: str = '',
    **kwargs
) -> dict:
    """
    api/offer_inventory → referral commission.

    Called when conversion is approved (on_conversion_approved signal).
    Integration point:
        api/offer_inventory/signals.py → on_conversion_approved
        → fires EVENT_OFFER_COMPLETED via event_bus.publish()
    """
    try:
        from api.referral.services.ReferralService import ReferralService
        results = ReferralService.process_multilevel_commission(
            earner=user,
            earned_amount=Decimal(str(user_net_reward)),
            source_type=SOURCE_OFFER,
            source_id=str(offer_id or (conversion.id if conversion else '')),
        )

        if results:
            logger.info(
                f'[IntegHandler] Offer commission: user={user.id} '
                f'offer={offer_id} reward={user_net_reward} → {len(results)} paid'
            )

        return {'success': True, 'commissions': results}

    except Exception as e:
        logger.error(f'[IntegHandler] handle_offer_completed error: {e}')
        raise HandlerError(f'Offer commission failed: {e}') from e


@transaction.atomic
def handle_withdrawal_approved(
    user,
    amount: Decimal,
    transaction_id: str = '',
    **kwargs
) -> dict:
    """
    api/wallet → referral commission on withdrawal.

    Integration point:
        api/wallet/services.py → WalletService.approve_withdrawal()
        → fires EVENT_WITHDRAWAL_APPROVED via event_bus.publish()
    """
    try:
        from api.referral.services.CommissionService import CommissionService
        from api.referral.models import ReferralSettings

        settings = ReferralSettings.objects.first()
        if not settings or not settings.is_active:
            return {'success': True, 'commissions': [], 'reason': 'inactive'}

        # Only process if withdrawal commission is configured
        rule = CommissionService.get_applicable_rule(1, 'withdrawal')
        if not rule:
            return {'success': True, 'commissions': [], 'reason': 'no_rule'}

        from api.referral.services.ReferralService import ReferralService
        results = ReferralService.process_multilevel_commission(
            earner=user,
            earned_amount=Decimal(str(amount)),
            source_type=SOURCE_WITHDRAWAL,
            source_id=str(transaction_id),
        )

        return {'success': True, 'commissions': results}

    except Exception as e:
        logger.error(f'[IntegHandler] handle_withdrawal_approved error: {e}')
        raise HandlerError(f'Withdrawal commission failed: {e}') from e


@transaction.atomic
def handle_user_registered(
    new_user,
    referral_code: str = '',
    new_user_ip: str = '',
    referrer_ip: str = '',
    device_fingerprint: str = '',
    **kwargs
) -> dict:
    """
    api/users → referral signup processing.

    Integration point:
        api/users/views.py → registration view
        → fires EVENT_USER_REGISTERED via event_bus.publish()
        OR called directly from api/users/signals.py

    Also compatible with:
        user.referred_by field (set before signal fires)
    """
    try:
        # Method 1: referral_code passed directly
        referrer = None
        if referral_code:
            from api.referral.services.ReferralCodeService import ReferralCodeService
            result = ReferralCodeService.validate_code(referral_code)
            if result['valid']:
                referrer = result['user']
                # Record code conversion
                result['code'].record_conversion()

        # Method 2: user.referred_by already set
        if not referrer:
            referrer = getattr(new_user, 'referred_by', None)

        if not referrer:
            return {'success': True, 'reason': 'no_referrer'}

        from api.referral.services.ReferralService import ReferralService
        signup_result = ReferralService.process_signup_with_fraud_check(
            new_user=new_user,
            referrer=referrer,
            new_user_ip=new_user_ip,
            referrer_ip=referrer_ip,
            device_fingerprint=device_fingerprint,
        )

        if signup_result.get('success'):
            _audit_log(
                action=AUDIT_REFERRAL_CREATED,
                user=new_user,
                data={
                    'referrer_id': referrer.id,
                    'bonus_given': signup_result.get('bonus_given'),
                    'referral_id': signup_result.get('referral_id'),
                }
            )

        return signup_result

    except Exception as e:
        logger.error(f'[IntegHandler] handle_user_registered error: {e}')
        raise HandlerError(f'User registration referral failed: {e}') from e


@transaction.atomic
def handle_fraud_confirmed(
    referral_id: int = None,
    user=None,
    fraud_score: int = 0,
    confirmed_by=None,
    **kwargs
) -> dict:
    """
    api/fraud_detection → referral clawback.

    Integration point:
        api/fraud_detection/services/ → when fraud score confirms
        → fires EVENT_FRAUD_CONFIRMED via event_bus.publish()
    """
    try:
        from api.referral.services.CommissionClawbackService import (
            CommissionClawbackService
        )
        from api.referral.models import Referral, SuspiciousReferral

        if referral_id:
            result = CommissionClawbackService.bulk_initiate_for_fraud(
                referral_id=referral_id,
                reason_detail=f'fraud_detection confirmed, score={fraud_score}',
            )
            _audit_log(
                action=AUDIT_CLAWBACK_INITIATED,
                user=user,
                data={'referral_id': referral_id, 'fraud_score': fraud_score},
            )
            return result

        if user:
            # Find all referrals for this user as referred_user
            referrals = Referral.objects.filter(referred_user=user)
            total_initiated = 0
            for referral in referrals:
                r = CommissionClawbackService.bulk_initiate_for_fraud(
                    referral_id=referral.id,
                    reason_detail=f'user fraud confirmed, score={fraud_score}',
                )
                total_initiated += r.get('initiated', 0)
            return {'success': True, 'initiated': total_initiated}

        return {'success': False, 'reason': 'no referral_id or user provided'}

    except Exception as e:
        logger.error(f'[IntegHandler] handle_fraud_confirmed error: {e}')
        raise HandlerError(f'Fraud clawback failed: {e}') from e


def handle_user_tier_upgraded(
    user,
    old_tier: str,
    new_tier: str,
    **kwargs
) -> dict:
    """
    api/users tier upgrade → referral bonus multiplier check.

    When user upgrades tier, check if their referral rates should change.
    Integration point:
        api/users/services/UserEnhancedService.py → check_and_upgrade_tier()
    """
    try:
        # Tier upgrade can trigger milestone bonus
        from api.referral.services.ReferralBonusService import ReferralBonusService
        awarded = ReferralBonusService.check_and_award_milestones(user)

        if awarded:
            logger.info(
                f'[IntegHandler] Tier upgrade milestones: '
                f'{user.id} {old_tier}→{new_tier} awards={len(awarded)}'
            )

        return {'success': True, 'milestones_awarded': len(awarded)}

    except Exception as e:
        logger.warning(f'[IntegHandler] handle_user_tier_upgraded warning: {e}')
        return {'success': False, 'error': str(e)}


# ── OUTBOUND HANDLERS ─────────────────────────────────────────────────────────

def notify_commission_paid(user, amount: Decimal, level: int, from_user) -> None:
    """Referral module → notification service."""
    try:
        from api.notifications.services import NotificationService
        ns = NotificationService()
        ns.create_notification(
            user=user,
            title='Referral Commission Earned! 💰',
            message=f'৳{float(amount):.2f} Level {level} commission from {from_user.username}',
            notification_type='referral_commission',
            priority='medium',
            channel='in_app',
        )
    except Exception as e:
        logger.warning(f'[IntegHandler] notify_commission_paid failed: {e}')


def update_analytics_on_referral(referrer, referred_user) -> None:
    """Referral module → analytics tracking."""
    try:
        from api.analytics.models import AnalyticsEvent
        AnalyticsEvent.objects.create(
            event_type='referral_created',
            user=referrer,
            metadata={
                'referred_user_id': referred_user.id,
                'referred_username': referred_user.username,
            }
        )
    except Exception as e:
        logger.debug(f'[IntegHandler] analytics update skipped: {e}')


def trigger_djoyalty_referral_points(referrer, referee) -> None:
    """
    Referral module → djoyalty points system.
    Awards loyalty points for referral actions.
    """
    try:
        from api.djoyalty.services.earn.ReferralPointsService import (
            ReferralPointsService
        )
        tenant = getattr(referrer, 'tenant', None)
        ReferralPointsService.process_referral(
            referrer=referrer,
            referee=referee,
            tenant=tenant,
        )
    except Exception as e:
        logger.debug(f'[IntegHandler] djoyalty points skipped: {e}')


# ── PRIVATE HELPERS ───────────────────────────────────────────────────────────

def _audit_commission_paid(user, results: list, source: str) -> None:
    try:
        from api.referral.INTEGRATION_SYSTEM.integ_audit_logs import (
            ReferralAuditLogger
        )
        for r in results:
            ReferralAuditLogger.log_commission_paid(
                referrer_username=r.get('beneficiary', ''),
                earner=user,
                amount=r.get('commission', 0),
                level=r.get('level', 1),
                source=source,
            )
    except Exception as e:
        logger.debug(f'[IntegHandler] _audit_commission_paid skipped: {e}')


def _audit_log(action: str, user, data: dict) -> None:
    try:
        from api.referral.INTEGRATION_SYSTEM.integ_audit_logs import (
            ReferralAuditLogger
        )
        ReferralAuditLogger.log(action=action, user=user, data=data)
    except Exception as e:
        logger.debug(f'[IntegHandler] _audit_log skipped: {e}')