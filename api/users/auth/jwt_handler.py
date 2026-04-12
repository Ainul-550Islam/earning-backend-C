"""
api/users/auth/jwt_handler.py
JWT token management — login_view.py থেকে extract করা হয়েছে
"""
import logging
from datetime import timedelta
from django.utils import timezone
from django.conf import settings
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
from rest_framework_simplejwt.exceptions import TokenError
from ..constants import AuthConstants
from ..exceptions import InvalidTokenException, TokenExpiredException
from ..cache import user_cache

logger = logging.getLogger(__name__)


class JWTHandler:

    @staticmethod
    def generate_tokens(user) -> dict:
        """
        User-এর জন্য access + refresh token তৈরি করো।
        Login success-এর পরে call করো।
        """
        refresh = RefreshToken.for_user(user)

        # Custom claims যোগ করো
        refresh['username'] = user.username
        refresh['tier']     = getattr(user, 'tier', 'FREE')
        refresh['role']     = getattr(user, 'role', 'user')

        access = refresh.access_token

        return {
            'access':         str(access),
            'refresh':        str(refresh),
            'access_expires': (
                timezone.now() +
                timedelta(minutes=AuthConstants.ACCESS_TOKEN_LIFETIME_MINUTES)
            ).isoformat(),
            'refresh_expires': (
                timezone.now() +
                timedelta(days=AuthConstants.REFRESH_TOKEN_LIFETIME_DAYS)
            ).isoformat(),
            'token_type': 'Bearer',
        }

    @staticmethod
    def refresh_access_token(refresh_token_str: str) -> dict:
        """Refresh token দিয়ে নতুন access token নাও"""
        try:
            refresh = RefreshToken(refresh_token_str)
            return {
                'access':         str(refresh.access_token),
                'access_expires': (
                    timezone.now() +
                    timedelta(minutes=AuthConstants.ACCESS_TOKEN_LIFETIME_MINUTES)
                ).isoformat(),
            }
        except TokenError:
            raise InvalidTokenException()

    @staticmethod
    def blacklist_token(refresh_token_str: str) -> bool:
        """Logout — refresh token blacklist করো"""
        try:
            token = RefreshToken(refresh_token_str)
            token.blacklist()
            return True
        except Exception as e:
            logger.warning(f'Token blacklist failed: {e}')
            return False

    @staticmethod
    def decode_token(access_token_str: str) -> dict:
        """Token decode করে payload দাও"""
        try:
            token = AccessToken(access_token_str)
            return dict(token.payload)
        except TokenError:
            raise InvalidTokenException()

    @staticmethod
    def get_user_from_token(access_token_str: str):
        """Token থেকে user নিয়ে আসো"""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            payload = JWTHandler.decode_token(access_token_str)
            user_id = payload.get('user_id')
            return User.objects.get(id=user_id)
        except Exception:
            raise InvalidTokenException()

    @staticmethod
    def blacklist_all_user_tokens(user_id: str) -> None:
        """
        User ban/suspend হলে সব token invalidate করো।
        Cache-ও clear করো।
        """
        user_cache.invalidate_all(str(user_id))
        # simplejwt outstanding tokens
        try:
            from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken
            tokens = OutstandingToken.objects.filter(user_id=user_id)
            for token in tokens:
                BlacklistedToken.objects.get_or_create(token=token)
        except Exception as e:
            logger.warning(f'Bulk token blacklist failed: {e}')


# Singleton
jwt_handler = JWTHandler()
