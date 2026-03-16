from django.db import models


class ItemType(models.TextChoices):
    PHYSICAL = "physical", "Physical Product"
    DIGITAL = "digital", "Digital Product"
    VOUCHER = "voucher", "Voucher / Gift Card"
    EXPERIENCE = "experience", "Experience / Event"
    SUBSCRIPTION = "subscription", "Subscription"
    POINTS = "points", "Points / Credits"
    NFT = "nft", "NFT / Digital Collectible"


class ItemStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    ACTIVE = "active", "Active"
    PAUSED = "paused", "Paused"
    OUT_OF_STOCK = "out_of_stock", "Out of Stock"
    DISCONTINUED = "discontinued", "Discontinued"
    ARCHIVED = "archived", "Archived"


class StockEventType(models.TextChoices):
    INITIAL = "initial", "Initial Stock"
    RESTOCK = "restock", "Restock"
    SALE = "sale", "Sale / Redemption"
    ADJUSTMENT = "adjustment", "Manual Adjustment"
    RETURN = "return", "Return"
    EXPIRED = "expired", "Expired / Written Off"
    RESERVED = "reserved", "Reserved"
    RELEASED = "released", "Reservation Released"


class CodeStatus(models.TextChoices):
    AVAILABLE = "available", "Available"
    RESERVED = "reserved", "Reserved"
    REDEEMED = "redeemed", "Redeemed"
    EXPIRED = "expired", "Expired"
    VOIDED = "voided", "Voided"
    FAILED = "failed", "Failed Delivery"


class InventoryStatus(models.TextChoices):
    PENDING = "pending", "Pending Delivery"
    DELIVERED = "delivered", "Delivered"
    CLAIMED = "claimed", "Claimed"
    EXPIRED = "expired", "Expired"
    REVOKED = "revoked", "Revoked"
    FAILED = "failed", "Delivery Failed"
    REFUNDED = "refunded", "Refunded"


class DeliveryMethod(models.TextChoices):
    EMAIL = "email", "Email"
    SMS = "sms", "SMS"
    IN_APP = "in_app", "In-App"
    MANUAL = "manual", "Manual Fulfillment"
    API = "api", "API Callback"
    PHYSICAL_SHIPMENT = "physical_shipment", "Physical Shipment"


class StockAlertLevel(models.TextChoices):
    NONE = "none", "No Alert"
    LOW = "low", "Low Stock"
    CRITICAL = "critical", "Critical Stock"
    DEPLETED = "depleted", "Depleted"
