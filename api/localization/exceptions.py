# exceptions.py — Custom API exceptions
from rest_framework.exceptions import APIException
from rest_framework import status


class LocalizationException(APIException):
    """Base localization exception"""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Localization error'
    default_code = 'localization_error'


class LanguageNotFoundError(LocalizationException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = 'Language not found or inactive'
    default_code = 'language_not_found'


class TranslationKeyNotFoundError(LocalizationException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = 'Translation key not found'
    default_code = 'translation_key_not_found'


class TranslationValueTooLongError(LocalizationException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Translation value exceeds maximum length'
    default_code = 'translation_too_long'


class CurrencyNotFoundError(LocalizationException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = 'Currency not found or inactive'
    default_code = 'currency_not_found'


class InvalidCurrencyAmountError(LocalizationException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Invalid currency amount'
    default_code = 'invalid_amount'


class ExchangeRateUnavailableError(LocalizationException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = 'Exchange rate not available'
    default_code = 'exchange_rate_unavailable'


class TranslationProviderError(LocalizationException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = 'Translation provider error'
    default_code = 'provider_error'


class AllProvidersFailedError(TranslationProviderError):
    default_detail = 'All translation providers failed'
    default_code = 'all_providers_failed'


class GeoIPLookupError(LocalizationException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = 'GeoIP lookup failed'
    default_code = 'geoip_error'


class InvalidLocaleError(LocalizationException):
    default_detail = 'Invalid locale code'
    default_code = 'invalid_locale'


class CountryNotFoundError(LocalizationException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = 'Country not found'
    default_code = 'country_not_found'


class ImportFormatError(LocalizationException):
    default_detail = 'Invalid import file format'
    default_code = 'invalid_import_format'


class ImportFileTooLargeError(LocalizationException):
    status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    default_detail = 'Import file too large'
    default_code = 'file_too_large'


class CoverageCalculationError(LocalizationException):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = 'Coverage calculation failed'
    default_code = 'coverage_error'


class RateLimitExceededError(LocalizationException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = 'API rate limit exceeded'
    default_code = 'rate_limit_exceeded'


class PermissionRequiredError(LocalizationException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = 'Permission required'
    default_code = 'permission_denied'


class TranslationNotApprovedError(LocalizationException):
    default_detail = 'Translation is not approved'
    default_code = 'not_approved'


class DuplicateTranslationError(LocalizationException):
    default_detail = 'Translation already exists for this key and language'
    default_code = 'duplicate_translation'


class WorkflowStateError(LocalizationException):
    default_detail = 'Invalid workflow state transition'
    default_code = 'workflow_state_error'


class GlossaryViolationError(LocalizationException):
    default_detail = 'Translation violates glossary rules'
    default_code = 'glossary_violation'
