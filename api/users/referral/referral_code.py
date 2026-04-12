"""
api/users/referral/referral_code.py
Referral code generation — users app-এর part।
Full referral logic api.referral-এ আছে।
এখানে শুধু code generate + basic lookup।
"""
import uuid
import secrets
import logging
from ..constants import ReferralConstants

logger = logging.getLogger(__name__)


class ReferralCodeManager:
    """
    users app-এ referral code দরকার:
    - Registration-এ code generate করা
    - Code দিয়ে referrer খোঁজা
    - Deep link তৈরি করা

    Commission, reward, multi-level — api.referral-এর কাজ।
    """

    PREFIX = ReferralConstants.CODE_PREFIX    # 'EARN'
    LENGTH = ReferralConstants.CODE_LENGTH    # 8

    # ─────────────────────────────────────
    # GENERATE
    # ─────────────────────────────────────
    def generate(self, user=None) -> str:
        """
        Unique referral code তৈরি করো।
        Format: EARN + 8 random chars = EARNAB12CD34
        """
        while True:
            random_part = secrets.token_hex(self.LENGTH // 2).upper()[:self.LENGTH]
            code        = f"{self.PREFIX}{random_part}"

            if not self._code_exists(code):
                return code

    def generate_and_assign(self, user) -> str:
        """
        Code তৈরি করো এবং user-এ save করো।
        Registration-এ call করো।
        """
        if getattr(user, 'referral_code', None):
            return user.referral_code

        code = self.generate(user)
        user.referral_code = code
        user.save(update_fields=['referral_code'])
        logger.info(f'Referral code assigned: {code} to user {user.id}')
        return code

    # ─────────────────────────────────────
    # LOOKUP
    # ─────────────────────────────────────
    def get_referrer(self, code: str):
        """
        Code দিয়ে referrer user খোঁজো।
        Registration-এ আসা referral code validate করতে।
        Returns: User instance or None
        """
        if not code:
            return None
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            return User.objects.filter(
                referral_code = code.upper(),
                is_active     = True,
            ).first()
        except Exception as e:
            logger.warning(f'Referrer lookup failed for code {code}: {e}')
            return None

    def is_valid_code(self, code: str) -> bool:
        """Code valid এবং active user-এর কিনা"""
        return self.get_referrer(code) is not None

    # ─────────────────────────────────────
    # LINKS
    # ─────────────────────────────────────
    def get_referral_link(self, user) -> str:
        """
        User-এর referral link দাও।
        """
        from django.conf import settings
        base_url = getattr(settings, 'FRONTEND_URL', 'https://example.com')
        code     = getattr(user, 'referral_code', '') or self.generate_and_assign(user)
        return f"{base_url}/register?ref={code}"

    def get_share_links(self, user) -> dict:
        """Social share links"""
        link    = self.get_referral_link(user)
        message = f"Join me on EarningApp and earn money! Use my referral link: {link}"
        encoded = message.replace(' ', '%20').replace('!', '%21')

        return {
            'referral_link': link,
            'whatsapp':      f"https://wa.me/?text={encoded}",
            'telegram':      f"https://t.me/share/url?url={link}&text=Join+EarningApp+and+earn!",
            'twitter':       f"https://twitter.com/intent/tweet?text={encoded}",
            'facebook':      f"https://www.facebook.com/sharer/sharer.php?u={link}",
            'copy':          link,
        }

    # ─────────────────────────────────────
    # NOTIFY api.referral
    # ─────────────────────────────────────
    def notify_referral_used(self, referrer, new_user) -> None:
        """
        New user register হলে api.referral-কে signal দাও।
        Reward, commission — api.referral calculate করবে।
        """
        try:
            logger.info(
                f'Referral used: referrer={referrer.id}, new_user={new_user.id}'
            )
            # api.referral.signals.referral_registered.send(
            #     sender=self.__class__,
            #     referrer=referrer,
            #     referred=new_user,
            # )
        except Exception as e:
            logger.warning(f'Referral signal failed: {e}')

    # ─────────────────────────────────────
    # PRIVATE
    # ─────────────────────────────────────
    def _code_exists(self, code: str) -> bool:
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            return User.objects.filter(referral_code=code).exists()
        except Exception:
            return False


# Singleton
referral_code_manager = ReferralCodeManager()
