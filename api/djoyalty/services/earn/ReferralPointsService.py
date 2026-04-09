# api/djoyalty/services/earn/ReferralPointsService.py
import logging
from decimal import Decimal
from .BonusEventService import BonusEventService
from ...constants import REFERRAL_BONUS_REFERRER, REFERRAL_BONUS_REFEREE

logger = logging.getLogger(__name__)

class ReferralPointsService:
    @staticmethod
    def process_referral(referrer, referee, tenant=None):
        try:
            BonusEventService.award_bonus(
                referrer, REFERRAL_BONUS_REFERRER,
                reason=f'Referral bonus for {referee.code}',
                triggered_by='referral', tenant=tenant,
            )
            BonusEventService.award_bonus(
                referee, REFERRAL_BONUS_REFEREE,
                reason=f'Welcome bonus (referred by {referrer.code})',
                triggered_by='referral', tenant=tenant,
            )
            logger.info('Referral processed: %s → %s', referrer, referee)
            return True
        except Exception as e:
            logger.error('Referral error: %s', e)
            return False
