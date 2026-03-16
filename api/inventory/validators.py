from decimal import Decimal
from django.core.exceptions import ValidationError
from django.utils import timezone

from .constants import (
    MAX_QUANTITY_PER_USER_PER_ITEM,
    REDEMPTION_CODE_LENGTH,
    REDEMPTION_CODE_CHARSET,
    MAX_CODES_PER_BATCH_IMPORT,
    UNLIMITED_STOCK,
)


def validate_non_negative_stock(value: int) -> None:
    """Stock quantity must be ≥ 0 or the sentinel UNLIMITED_STOCK (-1)."""
    if value != UNLIMITED_STOCK and value < 0:
        raise ValidationError(
            f"Stock quantity must be 0 or greater (or {UNLIMITED_STOCK} for unlimited). Got {value}."
        )


def validate_positive_points_cost(value: int) -> None:
    if value < 0:
        raise ValidationError(f"Points cost cannot be negative. Got {value}.")


def validate_low_stock_threshold(value: int) -> None:
    if value < 0:
        raise ValidationError(f"Low-stock threshold cannot be negative. Got {value}.")


def validate_redemption_code_format(code: str) -> None:
    """Validate that a redemption code matches expected length and charset."""
    if not code:
        raise ValidationError("Redemption code cannot be empty.")
    code = code.upper().replace("-", "").replace(" ", "")
    if len(code) != REDEMPTION_CODE_LENGTH:
        raise ValidationError(
            f"Redemption code must be exactly {REDEMPTION_CODE_LENGTH} characters "
            f"(after stripping dashes/spaces). Got {len(code)}."
        )
    invalid_chars = set(code) - set(REDEMPTION_CODE_CHARSET)
    if invalid_chars:
        raise ValidationError(
            f"Redemption code contains invalid characters: {', '.join(sorted(invalid_chars))}."
        )


def validate_code_not_expired(code_expiry) -> None:
    if code_expiry and code_expiry < timezone.now():
        raise ValidationError("Redemption code has expired.")


def validate_user_item_quantity_limit(user, item, requested_qty: int = 1) -> None:
    """
    Guard against a single user hoarding more than the per-item cap.
    Import lazily to avoid circular imports.
    """
    from .models import UserInventory
    from .choices import InventoryStatus

    active_qty = (
        UserInventory.objects.filter(
            user=user,
            item=item,
            status__in=[
                InventoryStatus.PENDING,
                InventoryStatus.DELIVERED,
                InventoryStatus.CLAIMED,
            ],
        )
        .count()
    )
    if active_qty + requested_qty > MAX_QUANTITY_PER_USER_PER_ITEM:
        raise ValidationError(
            f"You already own {active_qty} of '{item.name}'. "
            f"Maximum allowed per user is {MAX_QUANTITY_PER_USER_PER_ITEM}."
        )


def validate_stock_adjustment_will_not_go_negative(item, delta: int) -> None:
    """Raise if applying delta would make stock negative."""
    if item.current_stock == UNLIMITED_STOCK:
        return
    projected = item.current_stock + delta
    if projected < 0:
        raise ValidationError(
            f"Adjustment of {delta} would result in negative stock "
            f"({item.current_stock} + {delta} = {projected})."
        )


def validate_bulk_code_count(count: int) -> None:
    if count <= 0:
        raise ValidationError("Bulk import must contain at least 1 code.")
    if count > MAX_CODES_PER_BATCH_IMPORT:
        raise ValidationError(
            f"Bulk import cannot exceed {MAX_CODES_PER_BATCH_IMPORT} codes at once. Got {count}."
        )


def validate_future_expiry_date(value) -> None:
    if value and value <= timezone.now():
        raise ValidationError("Expiry date must be in the future.")
