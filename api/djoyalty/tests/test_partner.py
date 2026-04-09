# api/djoyalty/tests/test_partner.py
from decimal import Decimal
from django.test import TestCase
from .factories import make_customer, make_loyalty_points


class PartnerMerchantTest(TestCase):

    def setUp(self):
        from djoyalty.models.campaigns import PartnerMerchant
        self.partner = PartnerMerchant.objects.create(
            name='Test Partner',
            api_key='TESTPARTNERKEY001',
            earn_rate=Decimal('1.5'),
            burn_rate=Decimal('1.0'),
            is_active=True,
        )
        self.customer = make_customer(code='PRTCUST01')

    def test_partner_str(self):
        self.assertIn('Test Partner', str(self.partner))

    def test_partner_is_active(self):
        self.assertTrue(self.partner.is_active)

    def test_coalition_earn_creation(self):
        from djoyalty.models.advanced import CoalitionEarn
        earn = CoalitionEarn.objects.create(
            customer=self.customer,
            partner=self.partner,
            spend_amount=Decimal('200'),
            points_earned=Decimal('300'),
            reference='PARTNER-TXN-001',
        )
        self.assertIsNotNone(earn.id)
        self.assertEqual(earn.points_earned, Decimal('300'))

    def test_partner_api_key_unique(self):
        from djoyalty.models.campaigns import PartnerMerchant
        from django.db import IntegrityError
        with self.assertRaises(Exception):
            PartnerMerchant.objects.create(
                name='Duplicate Partner',
                api_key='TESTPARTNERKEY001',
                earn_rate=Decimal('1'),
                burn_rate=Decimal('1'),
            )

    def test_partner_sync_update(self):
        from django.utils import timezone
        self.partner.last_sync_at = timezone.now()
        self.partner.save()
        self.partner.refresh_from_db()
        self.assertIsNotNone(self.partner.last_sync_at)
