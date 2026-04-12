# api/publisher_tools/exceptions.py
"""
Publisher Tools — Custom Exception classes।
সব specific error handling এখানে।
"""
from rest_framework.exceptions import APIException
from rest_framework import status
from django.utils.translation import gettext_lazy as _


# ──────────────────────────────────────────────────────────────────────────────
# BASE EXCEPTION
# ──────────────────────────────────────────────────────────────────────────────

class PublisherToolsException(APIException):
    """Base exception for publisher_tools module"""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = _('Publisher Tools error occurred.')
    default_code = 'publisher_tools_error'


# ──────────────────────────────────────────────────────────────────────────────
# PUBLISHER EXCEPTIONS
# ──────────────────────────────────────────────────────────────────────────────

class PublisherNotFound(PublisherToolsException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = _('Publisher not found.')
    default_code = 'publisher_not_found'


class PublisherNotActive(PublisherToolsException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = _('Publisher account is not active.')
    default_code = 'publisher_not_active'


class PublisherSuspended(PublisherToolsException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = _('Publisher account is suspended.')
    default_code = 'publisher_suspended'


class PublisherBanned(PublisherToolsException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = _('Publisher account has been banned.')
    default_code = 'publisher_banned'


class PublisherKYCRequired(PublisherToolsException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = _('Publisher KYC verification is required.')
    default_code = 'kyc_required'


class PublisherAlreadyExists(PublisherToolsException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = _('A publisher profile already exists for this user.')
    default_code = 'publisher_already_exists'


# ──────────────────────────────────────────────────────────────────────────────
# SITE EXCEPTIONS
# ──────────────────────────────────────────────────────────────────────────────

class SiteNotFound(PublisherToolsException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = _('Site not found.')
    default_code = 'site_not_found'


class SiteNotActive(PublisherToolsException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = _('Site is not active.')
    default_code = 'site_not_active'


class SiteNotVerified(PublisherToolsException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = _('Site ownership is not verified.')
    default_code = 'site_not_verified'


class DomainAlreadyExists(PublisherToolsException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = _('This domain is already registered.')
    default_code = 'domain_already_exists'


class InvalidDomain(PublisherToolsException):
    default_detail = _('Invalid domain format.')
    default_code = 'invalid_domain'


class SiteVerificationFailed(PublisherToolsException):
    default_detail = _('Site verification failed. Please check your verification code.')
    default_code = 'verification_failed'


class AdsTxtMissing(PublisherToolsException):
    default_detail = _('ads.txt file is missing or not accessible.')
    default_code = 'ads_txt_missing'


# ──────────────────────────────────────────────────────────────────────────────
# APP EXCEPTIONS
# ──────────────────────────────────────────────────────────────────────────────

class AppNotFound(PublisherToolsException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = _('App not found.')
    default_code = 'app_not_found'


class AppNotActive(PublisherToolsException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = _('App is not active.')
    default_code = 'app_not_active'


class PackageNameAlreadyExists(PublisherToolsException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = _('This package name is already registered.')
    default_code = 'package_name_exists'


class InvalidPackageName(PublisherToolsException):
    default_detail = _('Invalid package name format. Use com.example.app format.')
    default_code = 'invalid_package_name'


class InvalidStoreUrl(PublisherToolsException):
    default_detail = _('Invalid store URL.')
    default_code = 'invalid_store_url'


# ──────────────────────────────────────────────────────────────────────────────
# AD UNIT EXCEPTIONS
# ──────────────────────────────────────────────────────────────────────────────

class AdUnitNotFound(PublisherToolsException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = _('Ad unit not found.')
    default_code = 'ad_unit_not_found'


class AdUnitNotActive(PublisherToolsException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = _('Ad unit is not active.')
    default_code = 'ad_unit_not_active'


class InvalidAdFormat(PublisherToolsException):
    default_detail = _('Invalid ad format.')
    default_code = 'invalid_ad_format'


class AdUnitLimitExceeded(PublisherToolsException):
    default_detail = _('Maximum ad units limit reached for this publisher tier.')
    default_code = 'ad_unit_limit_exceeded'


class InvalidFloorPrice(PublisherToolsException):
    default_detail = _('Invalid floor price. Must be between 0 and 100 USD CPM.')
    default_code = 'invalid_floor_price'


# ──────────────────────────────────────────────────────────────────────────────
# MEDIATION EXCEPTIONS
# ──────────────────────────────────────────────────────────────────────────────

class MediationGroupNotFound(PublisherToolsException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = _('Mediation group not found.')
    default_code = 'mediation_group_not_found'


class WaterfallItemNotFound(PublisherToolsException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = _('Waterfall item not found.')
    default_code = 'waterfall_item_not_found'


class PriorityConflict(PublisherToolsException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = _('Priority conflict. This priority level is already taken.')
    default_code = 'priority_conflict'


class WaterfallLimitExceeded(PublisherToolsException):
    default_detail = _('Maximum waterfall items limit (20) reached.')
    default_code = 'waterfall_limit_exceeded'


class NetworkAlreadyInWaterfall(PublisherToolsException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = _('This ad network is already in the waterfall.')
    default_code = 'network_already_exists'


# ──────────────────────────────────────────────────────────────────────────────
# EARNING / PAYMENT EXCEPTIONS
# ──────────────────────────────────────────────────────────────────────────────

class InsufficientBalance(PublisherToolsException):
    status_code = status.HTTP_402_PAYMENT_REQUIRED
    default_detail = _('Insufficient balance for this payout request.')
    default_code = 'insufficient_balance'


class BelowPayoutThreshold(PublisherToolsException):
    status_code = status.HTTP_402_PAYMENT_REQUIRED
    default_detail = _('Balance is below minimum payout threshold.')
    default_code = 'below_threshold'


class InvoiceNotFound(PublisherToolsException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = _('Invoice not found.')
    default_code = 'invoice_not_found'


class InvoiceAlreadyPaid(PublisherToolsException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = _('Invoice has already been paid.')
    default_code = 'invoice_already_paid'


class PaymentMethodNotVerified(PublisherToolsException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = _('Payment method is not verified.')
    default_code = 'payment_method_not_verified'


class DuplicateEarningRecord(PublisherToolsException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = _('Earning record already exists for this period.')
    default_code = 'duplicate_earning'


# ──────────────────────────────────────────────────────────────────────────────
# FRAUD EXCEPTIONS
# ──────────────────────────────────────────────────────────────────────────────

class HighFraudScore(PublisherToolsException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = _('Request blocked due to high fraud score.')
    default_code = 'high_fraud_score'


class IpBlocked(PublisherToolsException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = _('IP address is blocked.')
    default_code = 'ip_blocked'


class ExcessiveIVT(PublisherToolsException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = _('Publisher blocked due to excessive invalid traffic.')
    default_code = 'excessive_ivt'


# ──────────────────────────────────────────────────────────────────────────────
# A/B TEST EXCEPTIONS
# ──────────────────────────────────────────────────────────────────────────────

class TestNotFound(PublisherToolsException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = _('A/B test not found.')
    default_code = 'test_not_found'


class TestAlreadyRunning(PublisherToolsException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = _('An A/B test is already running for this ad unit.')
    default_code = 'test_already_running'


class InsufficientTestData(PublisherToolsException):
    default_detail = _('Insufficient data for statistical analysis. Need at least 1000 impressions per variant.')
    default_code = 'insufficient_test_data'


# ──────────────────────────────────────────────────────────────────────────────
# PERMISSION EXCEPTIONS
# ──────────────────────────────────────────────────────────────────────────────

class NotPublisherOwner(PublisherToolsException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = _('You do not have permission to access this publisher resource.')
    default_code = 'not_owner'


class TierUpgradeRequired(PublisherToolsException):
    status_code = status.HTTP_402_PAYMENT_REQUIRED
    default_detail = _('This feature requires a higher publisher tier.')
    default_code = 'tier_upgrade_required'


# ──────────────────────────────────────────────────────────────────────────────
# RATE LIMIT EXCEPTIONS
# ──────────────────────────────────────────────────────────────────────────────

class APIRateLimitExceeded(PublisherToolsException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = _('API rate limit exceeded. Please try again later.')
    default_code = 'rate_limit_exceeded'
