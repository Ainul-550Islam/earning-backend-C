# api/offer_inventory/exceptions.py
from rest_framework.exceptions import APIException
from rest_framework import status


class OfferInventoryBaseException(APIException):
    """সব custom exception-এর base।"""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'একটি ত্রুটি ঘটেছে।'
    default_code = 'offer_inventory_error'


# ── Offer Exceptions ─────────────────────────────────────────────
class OfferNotFoundException(OfferInventoryBaseException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = 'অফারটি পাওয়া যায়নি।'
    default_code = 'offer_not_found'


class OfferExpiredException(OfferInventoryBaseException):
    status_code = status.HTTP_410_GONE
    default_detail = 'অফারটির মেয়াদ শেষ হয়ে গেছে।'
    default_code = 'offer_expired'


class OfferCapReachedException(OfferInventoryBaseException):
    default_detail = 'এই অফারটির conversion সীমা পূরণ হয়ে গেছে।'
    default_code = 'offer_cap_reached'


class OfferNotAvailableException(OfferInventoryBaseException):
    default_detail = 'অফারটি এই মুহূর্তে উপলব্ধ নয়।'
    default_code = 'offer_not_available'


class AlreadyCompletedException(OfferInventoryBaseException):
    default_detail = 'আপনি ইতিমধ্যে এই অফারটি সম্পন্ন করেছেন।'
    default_code = 'already_completed'


class DailyLimitReachedException(OfferInventoryBaseException):
    default_detail = 'আজকের অফার সীমা পূরণ হয়ে গেছে।'
    default_code = 'daily_limit_reached'


# ── Conversion & Tracking ────────────────────────────────────────
class InvalidClickTokenException(OfferInventoryBaseException):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = 'Click token অবৈধ বা মেয়াদোত্তীর্ণ।'
    default_code = 'invalid_click_token'


class DuplicateConversionException(OfferInventoryBaseException):
    default_detail = 'Duplicate conversion detected।'
    default_code = 'duplicate_conversion'


class InvalidPostbackException(OfferInventoryBaseException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = 'Postback signature যাচাই ব্যর্থ।'
    default_code = 'invalid_postback'


class ConversionAlreadyReversedException(OfferInventoryBaseException):
    default_detail = 'এই conversion ইতিমধ্যে বাতিল করা হয়েছে।'
    default_code = 'already_reversed'


# ── Fraud & Security ─────────────────────────────────────────────
class FraudDetectedException(OfferInventoryBaseException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = 'সন্দেহজনক কার্যকলাপ সনাক্ত হয়েছে।'
    default_code = 'fraud_detected'


class IPBlockedException(OfferInventoryBaseException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = 'আপনার IP address block করা হয়েছে।'
    default_code = 'ip_blocked'


class VPNDetectedException(OfferInventoryBaseException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = 'VPN/Proxy ব্যবহার করা যাবে না।'
    default_code = 'vpn_detected'


class UserSuspendedException(OfferInventoryBaseException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = 'আপনার অ্যাকাউন্ট সাসপেন্ড করা হয়েছে।'
    default_code = 'user_suspended'


class RateLimitExceededException(OfferInventoryBaseException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = 'অনুরোধ সীমা অতিক্রম করেছেন।'
    default_code = 'rate_limit_exceeded'


class HoneypotTriggeredException(OfferInventoryBaseException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = 'Access denied।'
    default_code = 'honeypot_triggered'


# ── Finance ──────────────────────────────────────────────────────
class InsufficientBalanceException(OfferInventoryBaseException):
    default_detail = 'পর্যাপ্ত ব্যালেন্স নেই।'
    default_code = 'insufficient_balance'


class WalletLockedException(OfferInventoryBaseException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = 'আপনার ওয়ালেট লক করা আছে।'
    default_code = 'wallet_locked'


class MinWithdrawalException(OfferInventoryBaseException):
    default_detail = 'সর্বনিম্ন উইথড্রয়াল পরিমাণ পূরণ হয়নি।'
    default_code = 'min_withdrawal'


class MaxWithdrawalException(OfferInventoryBaseException):
    default_detail = 'সর্বোচ্চ উইথড্রয়াল সীমা অতিক্রম করেছেন।'
    default_code = 'max_withdrawal'


class KYCRequiredException(OfferInventoryBaseException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = 'উইথড্রয়ালের জন্য KYC যাচাই প্রয়োজন।'
    default_code = 'kyc_required'


class PaymentMethodNotFoundException(OfferInventoryBaseException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = 'Payment method পাওয়া যায়নি।'
    default_code = 'payment_method_not_found'


# ── Network & External ───────────────────────────────────────────
class NetworkUnavailableException(OfferInventoryBaseException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = 'Ad Network বর্তমানে অনুপলব্ধ।'
    default_code = 'network_unavailable'


class PostbackDeliveryFailedException(OfferInventoryBaseException):
    default_detail = 'Postback delivery ব্যর্থ হয়েছে।'
    default_code = 'postback_failed'


# ── System ────────────────────────────────────────────────────────
class MaintenanceModeException(OfferInventoryBaseException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = 'সিস্টেম রক্ষণাবেক্ষণে আছে।'
    default_code = 'maintenance_mode'


class FeatureDisabledException(OfferInventoryBaseException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = 'এই ফিচারটি বর্তমানে নিষ্ক্রিয়।'
    default_code = 'feature_disabled'
