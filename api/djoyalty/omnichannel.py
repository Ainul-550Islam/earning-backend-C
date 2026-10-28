# api/djoyalty/omnichannel.py
"""
Djoyalty Omnichannel -- Unify online/offline/mobile loyalty touchpoints।
Single customer view across all channels।
"Do not summarize or skip any logic. Provide the full code."
"""
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)


class OmnichannelLoyalty:
    """
    Unified omnichannel loyalty manager।
    Ensures consistent experience across: web, app, POS, kiosk, WhatsApp।

    Usage:
        omni = OmnichannelLoyalty()
        profile = omni.get_unified_profile(customer)
        result = omni.process_event(channel='pos', customer=c, event='purchase', amount=1500)
    """

    CHANNELS = ['web', 'app', 'pos', 'kiosk', 'whatsapp', 'email', 'sms', 'api']

    @staticmethod
    def get_unified_profile(customer) -> dict:
        """Get complete customer profile across all channels।"""
        from .selectors import get_customer_loyalty_summary, get_referral_stats

        summary = get_customer_loyalty_summary(customer)
        referral = get_referral_stats(customer)

        # Add pending points
        try:
            from .pending_points import PendingPointsManager
            pending = PendingPointsManager.get_pending_total(customer)
        except Exception:
            pending = Decimal('0')

        # Add membership
        membership_info = {}
        try:
            from .paid_membership import MembershipBenefitsManager
            membership = MembershipBenefitsManager.get_active_membership(customer)
            if membership:
                membership_info = {
                    'plan': membership.plan.name,
                    'status': membership.status,
                    'days_remaining': membership.days_remaining,
                    'earn_multiplier': str(membership.plan.earn_multiplier),
                }
        except Exception:
            pass

        return {
            **summary,
            'pending_points': str(pending),
            'total_available': str(summary['balance']),
            'referral': referral,
            'membership': membership_info,
            'channels_active': OmnichannelLoyalty.CHANNELS,
        }

    @staticmethod
    def process_event(channel: str, customer, event: str,
                       amount: Decimal = Decimal('0'), reference: str = '',
                       metadata: dict = None) -> dict:
        """
        Process a loyalty event from any channel।
        Ensures idempotent, consistent processing regardless of channel।
        """
        from .idempotency import IdempotencyGuard

        # Idempotency: same event from same channel for same customer doesn't duplicate
        guard = IdempotencyGuard(
            'omnichannel_event',
            customer_id=customer.id,
            channel=channel,
            event=event,
            reference=reference,
        )
        if guard.already_processed():
            return guard.get_cached_result()

        meta = metadata or {}
        meta['channel'] = channel

        from .use_cases import EarnPointsUseCase, EarnPointsInput
        result_obj = EarnPointsUseCase().execute(EarnPointsInput(
            customer_id=customer.id,
            amount=amount,
            source=event,
            reference_id=reference,
            metadata=meta,
        ))

        result = {
            'success': result_obj.success,
            'channel': channel,
            'event': event,
            'points_earned': str(result_obj.points_earned),
            'new_balance': str(result_obj.new_balance),
            'tier_changed': result_obj.tier_changed,
            'error': result_obj.error,
        }

        if result_obj.success:
            guard.mark_processed(result)

        return result
