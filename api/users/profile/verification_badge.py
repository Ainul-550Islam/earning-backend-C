"""
api/users/profile/verification_badge.py
Verified badge logic — KYC/email/phone verify হলে badge দাও।
api.kyc থেকে signal আসলে এখানে update হবে।
"""
import logging
from ..enums import VerificationBadgeEnum

logger = logging.getLogger(__name__)


class VerificationBadgeManager:

    def get_badges(self, user) -> list[str]:
        """User-এর সব active badge দাও"""
        badges = []

        if user.is_email_verified if hasattr(user, 'is_email_verified') else getattr(user, 'is_verified', False):
            badges.append(VerificationBadgeEnum.EMAIL)

        if getattr(user, 'is_phone_verified', False):
            badges.append(VerificationBadgeEnum.PHONE)

        # api.kyc থেকে আসে — foreign key বা signal
        if self._is_kyc_verified(user):
            badges.append(VerificationBadgeEnum.KYC)

        if getattr(user, 'tier', 'FREE') in ['GOLD', 'PLATINUM', 'DIAMOND']:
            badges.append(VerificationBadgeEnum.PREMIUM)

        return [b.value for b in badges]

    def get_primary_badge(self, user) -> str:
        """সবচেয়ে উচ্চ badge দাও"""
        badges = self.get_badges(user)
        priority = [
            VerificationBadgeEnum.KYC.value,
            VerificationBadgeEnum.PREMIUM.value,
            VerificationBadgeEnum.PHONE.value,
            VerificationBadgeEnum.EMAIL.value,
        ]
        for badge in priority:
            if badge in badges:
                return badge
        return VerificationBadgeEnum.NONE.value

    def award_email_badge(self, user) -> None:
        """Email verify হলে call করো"""
        if hasattr(user, 'is_email_verified'):
            user.is_email_verified = True
            user.save(update_fields=['is_email_verified'])
        self._invalidate_cache(user)
        logger.info(f'Email badge awarded to user: {user.id}')

    def award_phone_badge(self, user) -> None:
        """Phone verify হলে call করো"""
        if hasattr(user, 'is_phone_verified'):
            user.is_phone_verified = True
            user.save(update_fields=['is_phone_verified'])
        self._invalidate_cache(user)

    def award_kyc_badge(self, user) -> None:
        """
        api.kyc approve signal এলে call করো।
        users app নিজে KYC logic করে না।
        """
        if hasattr(user, 'is_verified'):
            user.is_verified = True
            user.save(update_fields=['is_verified'])
        self._invalidate_cache(user)
        logger.info(f'KYC badge awarded to user: {user.id}')

    def _is_kyc_verified(self, user) -> bool:
        """api.kyc app-এর model check করো"""
        try:
            from django.apps import apps
            KYCVerification = apps.get_model('kyc', 'KYCVerification')
            return KYCVerification.objects.filter(
                user   = user,
                status = 'approved',
            ).exists()
        except Exception:
            # kyc app না থাকলে user.is_verified দেখো
            return getattr(user, 'is_verified', False)

    def _invalidate_cache(self, user) -> None:
        from ..cache import user_cache
        user_cache.invalidate_profile(str(user.id))


# Singleton
badge_manager = VerificationBadgeManager()
