# api/djoyalty/services/redemption/GiftCardService.py
import logging
from decimal import Decimal
from django.utils import timezone
from ...models.redemption import GiftCard
from ...utils import generate_gift_card_code
from ...exceptions import GiftCardNotFoundError, GiftCardExpiredError, GiftCardAlreadyUsedError, GiftCardInsufficientBalanceError

logger = logging.getLogger(__name__)

class GiftCardService:
    @staticmethod
    def issue(value: Decimal, issued_to=None, tenant=None, validity_days: int = 365) -> GiftCard:
        code = generate_gift_card_code()
        while GiftCard.objects.filter(code=code).exists():
            code = generate_gift_card_code()
        from ...utils import get_expiry_date
        expires_at = get_expiry_date(validity_days)
        return GiftCard.objects.create(
            tenant=tenant, code=code, initial_value=value,
            remaining_value=value, status='active',
            issued_to=issued_to, expires_at=expires_at,
        )

    @staticmethod
    def redeem(code: str, amount: Decimal) -> GiftCard:
        gc = GiftCard.objects.filter(code=code.upper()).first()
        if not gc:
            raise GiftCardNotFoundError()
        if gc.status == 'used':
            raise GiftCardAlreadyUsedError()
        if gc.expires_at and gc.expires_at < timezone.now():
            raise GiftCardExpiredError()
        if gc.remaining_value < amount:
            raise GiftCardInsufficientBalanceError()
        gc.remaining_value -= amount
        if gc.remaining_value == 0:
            gc.status = 'used'
            gc.used_at = timezone.now()
        gc.save(update_fields=['remaining_value', 'status', 'used_at'])
        return gc
