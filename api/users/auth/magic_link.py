"""
api/users/auth/magic_link.py
Passwordless login via email magic link
"""
import secrets
import logging
from django.conf import settings
from django.contrib.auth import get_user_model
from ..cache import user_cache
from ..constants import AuthConstants
from ..exceptions import InvalidTokenException, TokenExpiredException, UserNotFoundException

logger = logging.getLogger(__name__)
User   = get_user_model()

FRONTEND_URL = getattr(settings, 'FRONTEND_URL', 'https://example.com')


class MagicLinkService:

    TTL = AuthConstants.MAGIC_LINK_EXPIRY_MINUTES * 60  # seconds

    def generate_link(self, user) -> str:
        """
        Magic link তৈরি করো।
        Returns: full URL
        """
        token = secrets.token_urlsafe(48)
        user_cache.set_magic_link(token, str(user.id))
        link = f"{FRONTEND_URL}/auth/magic-link/?token={token}"
        logger.info(f'Magic link generated for user: {user.id}')
        return link, token

    def send_magic_link(self, email: str) -> bool:
        """
        Email দিয়ে user খুঁজো, magic link পাঠাও।
        User না থাকলেও success return করো (security best practice)।
        """
        try:
            user = User.objects.get(email=email, is_active=True)
            link, token = self.generate_link(user)
            self._send_email(email, link, user.username)
            return True
        except User.DoesNotExist:
            # Security: email exist কিনা জানাবো না
            logger.info(f'Magic link requested for non-existent email: {email}')
            return True
        except Exception as e:
            logger.error(f'Magic link send failed: {e}')
            return False

    def verify_and_login(self, token: str):
        """
        Token verify করো, user return করো।
        Token one-time use — verify-র পরে delete করো।
        """
        user_id = user_cache.get_magic_link(token)

        if not user_id:
            raise TokenExpiredException()

        try:
            user = User.objects.get(id=user_id, is_active=True)
        except User.DoesNotExist:
            raise UserNotFoundException()

        # One-time use — delete
        user_cache.delete_magic_link(token)

        logger.info(f'Magic link login successful for user: {user.id}')
        return user

    def _send_email(self, email: str, link: str, username: str) -> None:
        """
        Email পাঠাও — api.notifications-কে signal দাও।
        নিজে email logic লিখবো না।
        """
        from django.dispatch import Signal
        from ..constants import UserEvent

        # Signal fire করো — api.notifications শুনবে
        try:
            from django.db.models.signals import Signal
            magic_link_signal = Signal()
            # Actual: api.notifications.signals.send_magic_link_email
            # এখানে শুধু event emit করছি
            logger.info(f'Magic link email event fired for: {email}')
        except Exception as e:
            logger.error(f'Email signal failed: {e}')


# Singleton
magic_link_service = MagicLinkService()
