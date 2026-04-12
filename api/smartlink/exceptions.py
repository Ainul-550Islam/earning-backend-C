from rest_framework.exceptions import APIException
from rest_framework import status


class SmartLinkNotFound(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = 'SmartLink not found or inactive.'
    default_code = 'smartlink_not_found'


class SmartLinkInactive(APIException):
    status_code = status.HTTP_410_GONE
    default_detail = 'This SmartLink is no longer active.'
    default_code = 'smartlink_inactive'


class NoOfferAvailable(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = 'No offer available for your traffic profile.'
    default_code = 'no_offer_available'


class ClickBlocked(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = 'Click blocked due to fraud detection.'
    default_code = 'click_blocked'


class DuplicateClick(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = 'Duplicate click detected.'
    default_code = 'duplicate_click'


class DomainVerificationFailed(APIException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = 'Domain verification failed. Please check DNS settings.'
    default_code = 'domain_verification_failed'


class OfferCapReached(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = 'Offer daily cap has been reached.'
    default_code = 'offer_cap_reached'


class SlugConflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = 'This slug is already taken.'
    default_code = 'slug_conflict'


class SlugReserved(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'This slug is reserved and cannot be used.'
    default_code = 'slug_reserved'


class TargetingConfigError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Invalid targeting configuration.'
    default_code = 'targeting_config_error'


class RedirectChainTooLong(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Redirect chain exceeds maximum allowed hops.'
    default_code = 'redirect_chain_too_long'


class ABTestConfigError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Invalid A/B test configuration. Variant weights must sum to 100.'
    default_code = 'ab_test_config_error'


class PublisherLimitExceeded(APIException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = 'Publisher SmartLink limit exceeded.'
    default_code = 'publisher_limit_exceeded'


class InvalidSubIDFormat(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Invalid sub-ID format. Only alphanumeric, hyphen, and underscore allowed.'
    default_code = 'invalid_sub_id_format'
