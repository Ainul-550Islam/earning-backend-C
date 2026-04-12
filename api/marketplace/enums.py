"""
marketplace/enums.py — All Enum / TextChoices for Marketplace
"""

from django.db import models


# ──────────────────────────────────────────────
# Product
# ──────────────────────────────────────────────
class ProductStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    ACTIVE = "active", "Active"
    INACTIVE = "inactive", "Inactive"
    BANNED = "banned", "Banned"
    OUT_OF_STOCK = "out_of_stock", "Out of Stock"


class ProductCondition(models.TextChoices):
    NEW = "new", "New"
    USED = "used", "Used"
    REFURBISHED = "refurbished", "Refurbished"


# ──────────────────────────────────────────────
# Seller
# ──────────────────────────────────────────────
class SellerStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    ACTIVE = "active", "Active"
    SUSPENDED = "suspended", "Suspended"
    BANNED = "banned", "Banned"


class VerificationStatus(models.TextChoices):
    UNVERIFIED = "unverified", "Unverified"
    PENDING = "pending", "Pending Review"
    VERIFIED = "verified", "Verified"
    REJECTED = "rejected", "Rejected"


class PayoutStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    PROCESSING = "processing", "Processing"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"
    REVERSED = "reversed", "Reversed"


# ──────────────────────────────────────────────
# Order
# ──────────────────────────────────────────────
class OrderStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    CONFIRMED = "confirmed", "Confirmed"
    PROCESSING = "processing", "Processing"
    SHIPPED = "shipped", "Shipped"
    OUT_FOR_DELIVERY = "out_for_delivery", "Out for Delivery"
    DELIVERED = "delivered", "Delivered"
    CANCELLED = "cancelled", "Cancelled"
    RETURNED = "returned", "Returned"
    REFUNDED = "refunded", "Refunded"


class TrackingEvent(models.TextChoices):
    ORDER_PLACED = "order_placed", "Order Placed"
    PAYMENT_CONFIRMED = "payment_confirmed", "Payment Confirmed"
    SELLER_CONFIRMED = "seller_confirmed", "Seller Confirmed"
    PACKED = "packed", "Packed"
    PICKED_UP = "picked_up", "Picked Up by Courier"
    IN_TRANSIT = "in_transit", "In Transit"
    OUT_FOR_DELIVERY = "out_for_delivery", "Out for Delivery"
    DELIVERED = "delivered", "Delivered"
    DELIVERY_FAILED = "delivery_failed", "Delivery Failed"
    RETURN_INITIATED = "return_initiated", "Return Initiated"
    RETURNED = "returned", "Returned to Seller"


# ──────────────────────────────────────────────
# Payment
# ──────────────────────────────────────────────
class PaymentMethod(models.TextChoices):
    BKASH = "bkash", "bKash"
    NAGAD = "nagad", "Nagad"
    ROCKET = "rocket", "Rocket"
    CARD = "card", "Credit/Debit Card"
    BANK = "bank", "Bank Transfer"
    COD = "cod", "Cash on Delivery"
    WALLET = "wallet", "Wallet Balance"
    UPAY = "upay", "Upay"


class PaymentStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    INITIATED = "initiated", "Initiated"
    SUCCESS = "success", "Success"
    FAILED = "failed", "Failed"
    CANCELLED = "cancelled", "Cancelled"
    REFUNDED = "refunded", "Refunded"
    PARTIALLY_REFUNDED = "partially_refunded", "Partially Refunded"


class EscrowStatus(models.TextChoices):
    HOLDING = "holding", "Holding"
    RELEASED = "released", "Released to Seller"
    REFUNDED = "refunded", "Refunded to Buyer"
    DISPUTED = "disputed", "Under Dispute"


# ──────────────────────────────────────────────
# Refund / Return
# ──────────────────────────────────────────────
class RefundStatus(models.TextChoices):
    REQUESTED = "requested", "Requested"
    UNDER_REVIEW = "under_review", "Under Review"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    PROCESSED = "processed", "Processed"


class RefundReason(models.TextChoices):
    DAMAGED = "damaged", "Product Damaged"
    WRONG_ITEM = "wrong_item", "Wrong Item Delivered"
    NOT_AS_DESCRIBED = "not_as_described", "Not as Described"
    NEVER_ARRIVED = "never_arrived", "Never Arrived"
    DEFECTIVE = "defective", "Defective Product"
    OTHER = "other", "Other"


# ──────────────────────────────────────────────
# Shipping
# ──────────────────────────────────────────────
class ShippingStatus(models.TextChoices):
    PENDING = "pending", "Pending Pickup"
    PICKED_UP = "picked_up", "Picked Up"
    IN_TRANSIT = "in_transit", "In Transit"
    DELIVERED = "delivered", "Delivered"
    FAILED = "failed", "Delivery Failed"
    RETURNED = "returned", "Returned"


# ──────────────────────────────────────────────
# Coupon / Promotion
# ──────────────────────────────────────────────
class CouponType(models.TextChoices):
    PERCENTAGE = "percentage", "Percentage Discount"
    FIXED = "fixed", "Fixed Amount Discount"
    FREE_SHIPPING = "free_shipping", "Free Shipping"
    BUY_X_GET_Y = "buy_x_get_y", "Buy X Get Y"


class PromotionType(models.TextChoices):
    FLASH_SALE = "flash_sale", "Flash Sale"
    DEAL_OF_DAY = "deal_of_day", "Deal of the Day"
    SEASONAL = "seasonal", "Seasonal Sale"
    CLEARANCE = "clearance", "Clearance"
    BUNDLE = "bundle", "Bundle Deal"


# ──────────────────────────────────────────────
# Dispute
# ──────────────────────────────────────────────
class DisputeStatus(models.TextChoices):
    OPEN = "open", "Open"
    UNDER_REVIEW = "under_review", "Under Review"
    RESOLVED_BUYER = "resolved_buyer", "Resolved (Buyer Won)"
    RESOLVED_SELLER = "resolved_seller", "Resolved (Seller Won)"
    ESCALATED = "escalated", "Escalated to Admin"
    CLOSED = "closed", "Closed"


class DisputeType(models.TextChoices):
    NOT_RECEIVED = "not_received", "Item Not Received"
    NOT_AS_DESCRIBED = "not_as_described", "Not as Described"
    COUNTERFEIT = "counterfeit", "Counterfeit Item"
    DAMAGED = "damaged", "Damaged Item"
    WRONG_ITEM = "wrong_item", "Wrong Item"
    OTHER = "other", "Other"
