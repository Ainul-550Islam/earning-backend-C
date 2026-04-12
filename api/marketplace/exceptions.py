"""
marketplace/exceptions.py — Custom Exceptions
"""

from rest_framework.exceptions import APIException
from rest_framework import status


class MarketplaceException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "A marketplace error occurred."
    default_code = "marketplace_error"


class ProductNotFoundException(MarketplaceException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "Product not found."
    default_code = "product_not_found"


class OutOfStockException(MarketplaceException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Product is out of stock."
    default_code = "out_of_stock"


class InsufficientStockException(MarketplaceException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Insufficient stock available."
    default_code = "insufficient_stock"


class SellerNotFoundException(MarketplaceException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "Seller not found."
    default_code = "seller_not_found"


class SellerNotVerifiedException(MarketplaceException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "Seller is not verified."
    default_code = "seller_not_verified"


class SellerSuspendedException(MarketplaceException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "Seller account is suspended."
    default_code = "seller_suspended"


class OrderNotFoundException(MarketplaceException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "Order not found."
    default_code = "order_not_found"


class InvalidOrderStatusException(MarketplaceException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Invalid order status transition."
    default_code = "invalid_order_status"


class CartEmptyException(MarketplaceException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Cart is empty."
    default_code = "cart_empty"


class PaymentFailedException(MarketplaceException):
    status_code = status.HTTP_402_PAYMENT_REQUIRED
    default_detail = "Payment failed."
    default_code = "payment_failed"


class CouponInvalidException(MarketplaceException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Coupon is invalid or expired."
    default_code = "coupon_invalid"


class CouponExpiredException(CouponInvalidException):
    default_detail = "Coupon has expired."
    default_code = "coupon_expired"


class CouponUsageLimitException(CouponInvalidException):
    default_detail = "Coupon usage limit reached."
    default_code = "coupon_limit_reached"


class DisputeAlreadyExistsException(MarketplaceException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "A dispute already exists for this order."
    default_code = "dispute_exists"


class RefundWindowExpiredException(MarketplaceException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Refund window has expired."
    default_code = "refund_window_expired"


class InsufficientPayoutBalanceException(MarketplaceException):
    status_code = status.HTTP_402_PAYMENT_REQUIRED
    default_detail = "Insufficient balance for payout."
    default_code = "insufficient_payout_balance"
