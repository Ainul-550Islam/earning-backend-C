"""
api/users/auth/password_manager.py
Password hashing, validation, reset — সব password logic এখানে
"""
import re
import secrets
import logging
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from ..exceptions import InvalidTokenException, TokenExpiredException, UserNotFoundException
from ..cache import user_cache
from ..constants import AuthConstants, CacheKeys

logger = logging.getLogger(__name__)
User   = get_user_model()


class PasswordManager:

    # ─────────────────────────────────────
    # VALIDATION
    # ─────────────────────────────────────
    @staticmethod
    def validate_strength(password: str) -> tuple[bool, list[str]]:
        """
        Password strength check।
        Returns: (is_valid, list_of_errors)
        """
        errors = []

        if len(password) < 8:
            errors.append('Password must be at least 8 characters.')
        if not re.search(r'[A-Z]', password):
            errors.append('Password must contain at least one uppercase letter.')
        if not re.search(r'[a-z]', password):
            errors.append('Password must contain at least one lowercase letter.')
        if not re.search(r'\d', password):
            errors.append('Password must contain at least one digit.')
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            errors.append('Password must contain at least one special character.')

        # Django built-in validators
        try:
            validate_password(password)
        except ValidationError as e:
            errors.extend(e.messages)

        return len(errors) == 0, errors

    @staticmethod
    def check_password_history(user, new_password: str, history_count: int = 5) -> bool:
        """
        Last N password-এর সাথে match করো।
        Returns: True if new password is OK (not in history)
        """
        if not hasattr(user, 'password_history'):
            return True
        for old_hash in user.password_history[-history_count:]:
            from django.contrib.auth.hashers import check_password
            if check_password(new_password, old_hash):
                return False
        return True

    # ─────────────────────────────────────
    # RESET FLOW
    # ─────────────────────────────────────
    @staticmethod
    def generate_reset_token(user) -> str:
        """Password reset token তৈরি করো — cache-এ store করো"""
        token = secrets.token_urlsafe(48)
        cache_key = f'pwd_reset:{token}'
        from django.core.cache import cache
        cache.set(cache_key, str(user.id), timeout=AuthConstants.MAGIC_LINK_EXPIRY_MINUTES * 60)
        return token

    @staticmethod
    def verify_reset_token(token: str):
        """
        Reset token verify করো।
        Returns: user instance
        """
        from django.core.cache import cache
        cache_key = f'pwd_reset:{token}'
        user_id   = cache.get(cache_key)

        if not user_id:
            raise TokenExpiredException()

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise UserNotFoundException()

        return user

    @staticmethod
    def reset_password(token: str, new_password: str) -> bool:
        """
        Token verify করে password reset করো।
        Success হলে token delete করো।
        """
        from django.core.cache import cache

        # Validate strength
        is_valid, errors = PasswordManager.validate_strength(new_password)
        if not is_valid:
            from rest_framework.exceptions import ValidationError as DRFValidationError
            raise DRFValidationError({'password': errors})

        user = PasswordManager.verify_reset_token(token)

        # Check history
        if not PasswordManager.check_password_history(user, new_password):
            from rest_framework.exceptions import ValidationError as DRFValidationError
            raise DRFValidationError({'password': ['Cannot reuse a recent password.']})

        # Set new password
        user.set_password(new_password)
        user.save(update_fields=['password'])

        # Invalidate token
        cache.delete(f'pwd_reset:{token}')

        # Invalidate all JWT tokens (force re-login)
        from .jwt_handler import jwt_handler
        jwt_handler.blacklist_all_user_tokens(str(user.id))

        logger.info(f'Password reset successful for user: {user.id}')
        return True

    @staticmethod
    def change_password(user, old_password: str, new_password: str) -> bool:
        """Authenticated user নিজে password change করো"""

        # Old password check
        if not user.check_password(old_password):
            from ..exceptions import InvalidCredentialsException
            raise InvalidCredentialsException()

        # Strength check
        is_valid, errors = PasswordManager.validate_strength(new_password)
        if not is_valid:
            from rest_framework.exceptions import ValidationError as DRFValidationError
            raise DRFValidationError({'new_password': errors})

        # Same password check
        if user.check_password(new_password):
            from rest_framework.exceptions import ValidationError as DRFValidationError
            raise DRFValidationError({'new_password': ['New password cannot be the same as old password.']})

        user.set_password(new_password)
        user.save(update_fields=['password'])

        # Invalidate cache
        user_cache.invalidate_all(str(user.id))

        logger.info(f'Password changed for user: {user.id}')
        return True


# Singleton
password_manager = PasswordManager()
