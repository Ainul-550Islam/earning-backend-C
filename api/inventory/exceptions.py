from rest_framework.exceptions import APIException
from rest_framework import status


class InventoryException(APIException):
    """Base exception for the inventory module."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "An inventory error occurred."
    default_code = "inventory_error"


class ItemNotFoundException(InventoryException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "Reward item not found."
    default_code = "item_not_found"


class ItemNotActiveException(InventoryException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "This reward item is not currently available."
    default_code = "item_not_active"


class InsufficientStockException(InventoryException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Insufficient stock available to fulfil this request."
    default_code = "insufficient_stock"


class StockReservationExpiredException(InventoryException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Stock reservation has expired. Please try again."
    default_code = "reservation_expired"


class StockReservationNotFoundException(InventoryException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "Stock reservation not found."
    default_code = "reservation_not_found"


class NoCodesAvailableException(InventoryException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "No redemption codes are available for this item."
    default_code = "no_codes_available"


class CodeAlreadyRedeemedException(InventoryException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "This redemption code has already been used."
    default_code = "code_already_redeemed"


class CodeExpiredException(InventoryException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "This redemption code has expired."
    default_code = "code_expired"


class CodeVoidedException(InventoryException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "This redemption code has been voided."
    default_code = "code_voided"


class InvalidCodeException(InventoryException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Invalid redemption code."
    default_code = "invalid_code"


class UserInventoryNotFoundException(InventoryException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "Inventory entry not found."
    default_code = "inventory_not_found"


class DeliveryFailedException(InventoryException):
    status_code = status.HTTP_502_BAD_GATEWAY
    default_detail = "Item delivery failed. It will be retried automatically."
    default_code = "delivery_failed"


class ItemQuantityLimitExceededException(InventoryException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "You have reached the maximum quantity allowed for this item."
    default_code = "quantity_limit_exceeded"


class StockAdjustmentException(InventoryException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Stock adjustment would result in negative stock."
    default_code = "invalid_stock_adjustment"


class BulkImportException(InventoryException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Bulk code import failed validation."
    default_code = "bulk_import_error"

    def __init__(self, errors=None):
        self.errors = errors or []
        detail = self.default_detail
        if errors:
            detail = f"{detail} Errors: {'; '.join(str(e) for e in errors[:5])}"
        super().__init__(detail=detail)


class InventoryRevokedException(InventoryException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "This inventory item has been revoked."
    default_code = "inventory_revoked"
