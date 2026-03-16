from rest_framework.exceptions import APIException
from rest_framework import status


class PostbackException(APIException):
    """Base exception for the postback module."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "A postback processing error occurred."
    default_code = "postback_error"


class InvalidSignatureException(PostbackException):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = "Postback signature verification failed."
    default_code = "invalid_signature"


class SignatureExpiredException(PostbackException):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = "Postback timestamp is outside the allowed tolerance window."
    default_code = "signature_expired"


class NonceReusedException(PostbackException):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = "Postback nonce has already been used (replay attack detected)."
    default_code = "nonce_reused"


class IPNotWhitelistedException(PostbackException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "Request IP is not in the network's whitelist."
    default_code = "ip_not_whitelisted"


class DuplicateLeadException(PostbackException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Lead has already been processed for this network."
    default_code = "duplicate_lead"


class NetworkNotFoundException(PostbackException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "Postback network configuration not found or inactive."
    default_code = "network_not_found"


class NetworkInactiveException(PostbackException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "This postback network is currently inactive."
    default_code = "network_inactive"


class MissingRequiredFieldsException(PostbackException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "missing_fields"

    def __init__(self, missing_fields=None):
        self.missing_fields = missing_fields or []
        detail = (
            f"Missing required fields: {', '.join(self.missing_fields)}."
            if self.missing_fields
            else "Missing required fields."
        )
        super().__init__(detail=detail)


class SchemaValidationException(PostbackException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "Postback payload failed schema validation."
    default_code = "schema_validation"

    def __init__(self, errors=None):
        self.validation_errors = errors or {}
        detail = self.default_detail
        if errors:
            detail = f"{detail} Errors: {errors}"
        super().__init__(detail=detail)


class FraudDetectedException(PostbackException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "Postback flagged as potentially fraudulent."
    default_code = "fraud_detected"


class RateLimitExceededException(PostbackException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = "Postback rate limit exceeded for this network."
    default_code = "rate_limited"


class PayoutLimitExceededException(PostbackException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Postback payout exceeds the configured maximum."
    default_code = "payout_limit_exceeded"


class UserResolutionException(PostbackException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Could not resolve a user from the postback parameters."
    default_code = "user_not_found"


class PostbackAlreadyProcessedException(PostbackException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "This postback has already been processed."
    default_code = "already_processed"


class BlacklistedSourceException(PostbackException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "Postback source is blacklisted."
    default_code = "blacklisted"
