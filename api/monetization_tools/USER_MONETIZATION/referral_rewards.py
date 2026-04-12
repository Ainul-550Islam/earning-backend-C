"""USER_MONETIZATION/referral_rewards.py — Referral reward management."""
from ..services import ReferralService, ReferralProgramService


class ReferralRewards:
    @classmethod
    def get_link(cls, user, tenant=None):
        program = ReferralProgramService.get_active(tenant)
        if not program:
            return None
        return ReferralService.get_or_create_link(user, program)

    @classmethod
    def award_signup(cls, referrer, referee, tenant=None):
        program = ReferralProgramService.get_active(tenant)
        if program:
            return ReferralProgramService.award_signup_bonus(program, referrer, referee)
        return {}

    @classmethod
    def commission_summary(cls, user) -> dict:
        return ReferralService.get_summary(user)
