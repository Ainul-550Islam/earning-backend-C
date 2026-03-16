from rest_framework.exceptions import APIException
from rest_framework import status


class SubscriptionException(APIException):
    """Base exception for subscription module."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "A subscription error occurred."
    default_code = "subscription_error"


class AlreadySubscribedException(SubscriptionException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "User already has an active subscription."
    default_code = "already_subscribed"


class NoActiveSubscriptionException(SubscriptionException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "No active subscription found for this user."
    default_code = "no_active_subscription"


class SubscriptionExpiredException(SubscriptionException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "Your subscription has expired. Please renew to continue."
    default_code = "subscription_expired"


class SubscriptionCancelledException(SubscriptionException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "Your subscription has been cancelled."
    default_code = "subscription_cancelled"


class PlanNotFoundException(SubscriptionException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "Subscription plan not found or is no longer available."
    default_code = "plan_not_found"


class PlanInactiveException(SubscriptionException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "This subscription plan is currently inactive."
    default_code = "plan_inactive"


class PaymentFailedException(SubscriptionException):
    status_code = status.HTTP_402_PAYMENT_REQUIRED
    default_detail = "Payment processing failed. Please try again."
    default_code = "payment_failed"


class InvalidPaymentMethodException(SubscriptionException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Invalid or unsupported payment method."
    default_code = "invalid_payment_method"


class RefundNotAllowedException(SubscriptionException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Refund is not allowed for this payment."
    default_code = "refund_not_allowed"


class SubscriptionDowngradeException(SubscriptionException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Subscription cannot be downgraded to this plan."
    default_code = "downgrade_not_allowed"


class TrialAlreadyUsedException(SubscriptionException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "You have already used your free trial."
    default_code = "trial_already_used"


class SubscriptionPauseException(SubscriptionException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Subscription cannot be paused at this time."
    default_code = "pause_not_allowed"


class MaxSubscriptionsReachedException(SubscriptionException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Maximum number of active subscriptions reached."
    default_code = "max_subscriptions_reached"


class WebhookVerificationException(SubscriptionException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Webhook signature verification failed."
    default_code = "webhook_verification_failed"


class InvalidCouponException(SubscriptionException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Invalid or expired coupon code."
    default_code = "invalid_coupon"


class CouponAlreadyUsedException(SubscriptionException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "This coupon has already been used."
    default_code = "coupon_already_used"

class PlanHasActiveSubscribersException(SubscriptionException):
    status_code = 409
    default_detail = "Cannot delete a plan that has active subscribers. Archive it instead."
    default_code = "plan_has_active_subscribers"


class CouponExpiredException(SubscriptionException):
    status_code = 400
    default_detail = "This coupon has expired."
    default_code = "coupon_expired"


class CouponNotApplicableException(SubscriptionException):
    status_code = 400
    default_detail = "This coupon is not applicable to the selected plan."
    default_code = "coupon_not_applicable"


class AdminSubscriptionException(SubscriptionException):
    status_code = 400
    default_detail = "Admin subscription operation failed."
    default_code = "admin_subscription_error"
