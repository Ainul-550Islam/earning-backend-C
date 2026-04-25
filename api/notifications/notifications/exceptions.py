# earning_backend/api/notifications/exceptions.py
"""
Custom exceptions for the notification system.
"""
from rest_framework.exceptions import APIException
from rest_framework import status


class NotificationException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'A notification error occurred.'
    default_code = 'notification_error'


class NotificationNotFound(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = 'Notification not found.'
    default_code = 'not_found'


class NotificationPermissionDenied(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = 'You do not have permission to access this notification.'
    default_code = 'permission_denied'


class UserFatigued(APIException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = 'Too many notifications sent today. Please try again tomorrow.'
    default_code = 'user_fatigued'


class UserOptedOut(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'User has opted out of this notification channel.'
    default_code = 'user_opted_out'


class ProviderUnavailable(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = 'Notification provider is currently unavailable.'
    default_code = 'provider_unavailable'


class InvalidToken(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Invalid or expired device token.'
    default_code = 'invalid_token'


class CampaignError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Campaign operation failed.'
    default_code = 'campaign_error'


class TemplateRenderError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Failed to render notification template.'
    default_code = 'template_render_error'


class RateLimitExceeded(APIException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = 'Notification rate limit exceeded.'
    default_code = 'rate_limit_exceeded'


class InvalidSchedule(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Invalid notification schedule configuration.'
    default_code = 'invalid_schedule'


class WebhookVerificationFailed(APIException):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = 'Webhook signature verification failed.'
    default_code = 'webhook_verification_failed'
