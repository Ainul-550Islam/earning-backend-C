from rest_framework.exceptions import APIException
from rest_framework import status


class IPIntelligenceError(APIException):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = 'IP intelligence service error.'
    default_code = 'ip_intelligence_error'


class InvalidIPAddress(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Invalid IP address provided.'
    default_code = 'invalid_ip_address'


class IPBlacklistedException(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = 'This IP address is blacklisted.'
    default_code = 'ip_blacklisted'


class ThreatFeedUnavailable(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = 'Threat feed service is currently unavailable.'
    default_code = 'threat_feed_unavailable'


class DetectionEngineError(APIException):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = 'Detection engine encountered an error.'
    default_code = 'detection_engine_error'


class MLModelNotFound(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = 'ML model not found.'
    default_code = 'ml_model_not_found'


class RateLimitExceeded(APIException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = 'Rate limit exceeded for this IP.'
    default_code = 'rate_limit_exceeded'


class IntegrationError(Exception):
    """Raised when a third-party integration fails."""
    pass


class MaxMindError(IntegrationError):
    pass


class AbuseIPDBError(IntegrationError):
    pass


class VirusTotalError(IntegrationError):
    pass
