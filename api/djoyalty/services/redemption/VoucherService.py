# api/djoyalty/services/redemption/VoucherService.py
import logging
from decimal import Decimal
from django.utils import timezone
from ...models.redemption import Voucher, VoucherRedemption
from ...utils import generate_voucher_code, get_expiry_date
from ...exceptions import VoucherNotFoundError, VoucherExpiredError, VoucherAlreadyUsedError
from ...constants import VOUCHER_DEFAULT_VALIDITY_DAYS

logger = logging.getLogger(__name__)

class VoucherService:
    @staticmethod
    def generate_voucher(customer, voucher_type: str, discount_value: Decimal, tenant=None, validity_days: int = None) -> Voucher:
        code = generate_voucher_code()
        while Voucher.objects.filter(code=code).exists():
            code = generate_voucher_code()
        expires_at = get_expiry_date(validity_days or VOUCHER_DEFAULT_VALIDITY_DAYS)
        return Voucher.objects.create(
            tenant=tenant or customer.tenant,
            customer=customer, code=code,
            voucher_type=voucher_type, discount_value=discount_value,
            status='active', expires_at=expires_at,
        )

    @staticmethod
    def use_voucher(code: str, customer, order_reference: str = None) -> VoucherRedemption:
        voucher = Voucher.objects.filter(code=code.upper()).first()
        if not voucher:
            raise VoucherNotFoundError()
        if voucher.status == 'used':
            raise VoucherAlreadyUsedError()
        if voucher.expires_at and voucher.expires_at < timezone.now():
            raise VoucherExpiredError()
        voucher.status = 'used'
        voucher.used_at = timezone.now()
        voucher.save(update_fields=['status', 'used_at'])
        return VoucherRedemption.objects.create(
            voucher=voucher, customer=customer,
            order_reference=order_reference, discount_applied=voucher.discount_value,
        )
