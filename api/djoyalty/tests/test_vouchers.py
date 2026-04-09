# api/djoyalty/tests/test_vouchers.py
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from .factories import make_customer, make_voucher


class VoucherServiceTest(TestCase):

    def setUp(self):
        self.customer = make_customer(code='VOUCUST01')

    def test_generate_voucher_creates_record(self):
        from djoyalty.services.redemption.VoucherService import VoucherService
        from djoyalty.models.redemption import Voucher
        voucher = VoucherService.generate_voucher(self.customer, 'percent', Decimal('10'))
        self.assertIsNotNone(voucher)
        self.assertEqual(voucher.status, 'active')
        self.assertEqual(voucher.discount_value, Decimal('10'))

    def test_generate_voucher_unique_code(self):
        from djoyalty.services.redemption.VoucherService import VoucherService
        v1 = VoucherService.generate_voucher(self.customer, 'percent', Decimal('10'))
        v2 = VoucherService.generate_voucher(self.customer, 'fixed', Decimal('20'))
        self.assertNotEqual(v1.code, v2.code)

    def test_use_voucher_marks_used(self):
        from djoyalty.services.redemption.VoucherService import VoucherService
        voucher = VoucherService.generate_voucher(self.customer, 'percent', Decimal('15'))
        VoucherService.use_voucher(voucher.code, self.customer)
        voucher.refresh_from_db()
        self.assertEqual(voucher.status, 'used')

    def test_use_voucher_creates_redemption(self):
        from djoyalty.services.redemption.VoucherService import VoucherService
        from djoyalty.models.redemption import VoucherRedemption
        voucher = VoucherService.generate_voucher(self.customer, 'fixed', Decimal('50'))
        VoucherService.use_voucher(voucher.code, self.customer, order_reference='ORD001')
        self.assertTrue(VoucherRedemption.objects.filter(voucher=voucher).exists())

    def test_use_already_used_voucher_raises_error(self):
        from djoyalty.services.redemption.VoucherService import VoucherService
        from djoyalty.exceptions import VoucherAlreadyUsedError
        voucher = VoucherService.generate_voucher(self.customer, 'percent', Decimal('10'))
        VoucherService.use_voucher(voucher.code, self.customer)
        with self.assertRaises(VoucherAlreadyUsedError):
            VoucherService.use_voucher(voucher.code, self.customer)

    def test_use_nonexistent_voucher_raises_error(self):
        from djoyalty.services.redemption.VoucherService import VoucherService
        from djoyalty.exceptions import VoucherNotFoundError
        with self.assertRaises(VoucherNotFoundError):
            VoucherService.use_voucher('INVALID000', self.customer)

    def test_expired_voucher_raises_error(self):
        from djoyalty.services.redemption.VoucherService import VoucherService
        from djoyalty.exceptions import VoucherExpiredError
        from datetime import timedelta
        voucher = make_voucher(
            self.customer,
            status='active',
            expires_at=timezone.now() - timedelta(days=1),
        )
        with self.assertRaises(VoucherExpiredError):
            VoucherService.use_voucher(voucher.code, self.customer)
