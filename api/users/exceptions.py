"""
api/users/exceptions.py
Custom Exceptions — সব user-related error এখানে
DRF exception handler এগুলো automatically JSON response-এ convert করবে
"""
from rest_framework.exceptions import APIException
from rest_framework import status
from .constants import ErrorCode


# ─────────────────────────────────────────
# BASE
# ─────────────────────────────────────────
class UserBaseException(APIException):
    """সব user exception এই class extend করবে"""
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = 'user_error'

    def __init__(self, detail=None, code=None, error_code=None):
        self.error_code = error_code or self.default_code
        super().__init__(detail=detail, code=code)

    def to_dict(self):
        return {
            'error': True,
            'error_code': self.error_code,
            'message': str(self.detail),
        }


# ─────────────────────────────────────────
# AUTH EXCEPTIONS
# ─────────────────────────────────────────
class UserNotFoundException(UserBaseException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = 'User not found.'
    default_code = ErrorCode.USER_NOT_FOUND

    def __init__(self, identifier=None):
        detail = f'User not found: {identifier}' if identifier else self.default_detail
        super().__init__(detail=detail, error_code=ErrorCode.USER_NOT_FOUND)


class InvalidCredentialsException(UserBaseException):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = 'Invalid username or password.'
    default_code = ErrorCode.INVALID_CREDENTIALS

    def __init__(self):
        super().__init__(
            detail=self.default_detail,
            error_code=ErrorCode.INVALID_CREDENTIALS
        )


class AccountSuspendedException(UserBaseException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = 'Your account has been suspended.'
    default_code = ErrorCode.ACCOUNT_SUSPENDED

    def __init__(self, reason=None):
        detail = f'Account suspended. Reason: {reason}' if reason else self.default_detail
        super().__init__(detail=detail, error_code=ErrorCode.ACCOUNT_SUSPENDED)


class AccountBannedException(UserBaseException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = 'Your account has been permanently banned.'

    def __init__(self, reason=None):
        detail = f'Account banned. Reason: {reason}' if reason else self.default_detail
        super().__init__(detail=detail, error_code=ErrorCode.ACCOUNT_SUSPENDED)


class AccountLockedException(UserBaseException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = 'Account temporarily locked due to too many failed attempts.'

    def __init__(self, unlock_after_minutes=30):
        super().__init__(
            detail=f'Account locked. Try again after {unlock_after_minutes} minutes.',
            error_code=ErrorCode.ACCOUNT_LOCKED
        )
        self.unlock_after_minutes = unlock_after_minutes


class EmailNotVerifiedException(UserBaseException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = 'Please verify your email address first.'

    def __init__(self):
        super().__init__(
            detail=self.default_detail,
            error_code=ErrorCode.EMAIL_NOT_VERIFIED
        )


# ─────────────────────────────────────────
# OTP EXCEPTIONS
# ─────────────────────────────────────────
class OTPExpiredException(UserBaseException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'OTP has expired. Please request a new one.'

    def __init__(self):
        super().__init__(detail=self.default_detail, error_code=ErrorCode.OTP_EXPIRED)


class InvalidOTPException(UserBaseException):
    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(self, attempts_remaining=None):
        if attempts_remaining is not None:
            detail = f'Invalid OTP. {attempts_remaining} attempts remaining.'
        else:
            detail = 'Invalid OTP.'
        super().__init__(detail=detail, error_code=ErrorCode.OTP_INVALID)


class OTPMaxAttemptsException(UserBaseException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = 'Too many OTP attempts. Please request a new OTP.'

    def __init__(self):
        super().__init__(detail=self.default_detail, error_code=ErrorCode.OTP_MAX_ATTEMPTS)


class OTPCooldownException(UserBaseException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS

    def __init__(self, seconds_remaining):
        super().__init__(
            detail=f'Please wait {seconds_remaining} seconds before requesting a new OTP.',
            error_code=ErrorCode.RATE_LIMIT_EXCEEDED
        )


# ─────────────────────────────────────────
# TOKEN EXCEPTIONS
# ─────────────────────────────────────────
class InvalidTokenException(UserBaseException):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = 'Token is invalid or has been revoked.'

    def __init__(self):
        super().__init__(detail=self.default_detail, error_code=ErrorCode.INVALID_TOKEN)


class TokenExpiredException(UserBaseException):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = 'Token has expired. Please log in again.'

    def __init__(self):
        super().__init__(detail=self.default_detail, error_code=ErrorCode.TOKEN_EXPIRED)


class InvalidAPIKeyException(UserBaseException):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = 'Invalid or expired API key.'

    def __init__(self):
        super().__init__(detail=self.default_detail, error_code=ErrorCode.INVALID_API_KEY)


# ─────────────────────────────────────────
# REGISTRATION / PROFILE EXCEPTIONS
# ─────────────────────────────────────────
class DuplicateUsernameException(UserBaseException):
    status_code = status.HTTP_409_CONFLICT

    def __init__(self, username):
        super().__init__(
            detail=f'Username "{username}" is already taken.',
            error_code=ErrorCode.DUPLICATE_USERNAME
        )


class DuplicateEmailException(UserBaseException):
    status_code = status.HTTP_409_CONFLICT

    def __init__(self, email=None):
        detail = f'Email "{email}" is already registered.' if email else 'Email already registered.'
        super().__init__(detail=detail, error_code=ErrorCode.DUPLICATE_EMAIL)


class DuplicatePhoneException(UserBaseException):
    status_code = status.HTTP_409_CONFLICT

    def __init__(self):
        super().__init__(
            detail='This phone number is already registered.',
            error_code=ErrorCode.DUPLICATE_PHONE
        )


class ProfileIncompleteException(UserBaseException):
    status_code = status.HTTP_403_FORBIDDEN

    def __init__(self, missing_fields=None):
        if missing_fields:
            detail = f'Profile incomplete. Please fill in: {", ".join(missing_fields)}'
        else:
            detail = 'Profile is incomplete.'
        super().__init__(detail=detail, error_code=ErrorCode.PROFILE_INCOMPLETE)


# ─────────────────────────────────────────
# KYC / WALLET / REFERRAL (signal-based, এখানে শুধু exception class)
# ─────────────────────────────────────────
class KYCRequiredException(UserBaseException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = 'KYC verification is required for this action.'

    def __init__(self):
        super().__init__(detail=self.default_detail, error_code=ErrorCode.KYC_REQUIRED)


class InsufficientBalanceException(UserBaseException):
    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(self, required=None, available=None):
        if required and available:
            detail = f'Insufficient balance. Required: ${required}, Available: ${available}'
        else:
            detail = 'Insufficient balance.'
        super().__init__(detail=detail, error_code=ErrorCode.INSUFFICIENT_BALANCE)


class RateLimitExceededException(UserBaseException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS

    def __init__(self, action=None, retry_after=None):
        if action and retry_after:
            detail = f'Rate limit exceeded for {action}. Retry after {retry_after} seconds.'
        else:
            detail = 'Too many requests. Please slow down.'
        super().__init__(detail=detail, error_code=ErrorCode.RATE_LIMIT_EXCEEDED)


# ─────────────────────────────────────────
# DRF EXCEPTION HANDLER (config/settings-এ register করো)
# ─────────────────────────────────────────
def custom_exception_handler(exc, context):
    """
    settings.py-তে যোগ করো:
    REST_FRAMEWORK = {
        'EXCEPTION_HANDLER': 'api.users.exceptions.custom_exception_handler'
    }
    """
    from rest_framework.views import exception_handler
    response = exception_handler(exc, context)

    if response is not None and isinstance(exc, UserBaseException):
        response.data = exc.to_dict()

    return response
