# engagement/services/referral_service.py
import logging
import secrets
from django.db import transaction
from django.utils import timezone
from .coin_service import CoinService
from .xp_service import XPService
from ..models.referral import Referral, ReferralProgram
from ..exceptions import ReferralSelfError, AlreadyReferredError

logger = logging.getLogger(__name__)


class ReferralService:

    @staticmethod
    def generate_code(user) -> str:
        """Generate a unique referral code for a user (idempotent)."""
        base = f"{user.pk:06x}{secrets.token_hex(3)}".upper()
        return base[:12]

    @classmethod
    @transaction.atomic
    def register_referral(cls, referrer, referee, code: str, tenant=None) -> Referral:
        """
        Record that `referee` signed up via `referrer`'s code.
        Raises ReferralSelfError, AlreadyReferredError.
        """
        if referrer.pk == referee.pk:
            raise ReferralSelfError()

        if Referral.objects.filter(referee=referee).exists():
            raise AlreadyReferredError()

        program = ReferralProgram.objects.filter(
            is_active=True,
            tenant=tenant,
        ).filter(
            # Date range check
            starts_at__isnull=True
        ).first() or ReferralProgram.objects.filter(is_active=True, tenant=tenant).first()

        referral = Referral.objects.create(
            program  = program,
            referrer = referrer,
            referee  = referee,
            code     = code,
            status   = "confirmed",
            tenant   = tenant or getattr(referrer, "tenant", None),
        )

        if program:
            cls._distribute_rewards(referral, program)

        logger.info("Referral: %s → %s (code=%s)", referrer.pk, referee.pk, code)
        return referral

    @classmethod
    def _distribute_rewards(cls, referral: Referral, program: ReferralProgram):
        """Give coins+XP to both referrer and referee."""
        if program.referrer_reward > 0:
            CoinService.add(referral.referrer, program.referrer_reward,
                            source="referral", ref_id=str(referral.pk))
        if program.referrer_xp > 0:
            XPService.grant(referral.referrer, program.referrer_xp,
                            source="referral", ref_id=str(referral.pk))

        if program.referee_reward > 0:
            CoinService.add(referral.referee, program.referee_reward,
                            source="referral", ref_id=str(referral.pk))
        if program.referee_xp > 0:
            XPService.grant(referral.referee, program.referee_xp,
                            source="referral", ref_id=str(referral.pk))

        referral.status      = "rewarded"
        referral.rewarded_at = timezone.now()
        referral.save(update_fields=["status", "rewarded_at"])
