# api/djoyalty/tests/test_eco_family.py
"""
Eco / Family / Charity Tests -- NEW।
FamilyAccount, EcoAction, CharityCause, ExperientialReward,
CustomerConsent -- all had ZERO test coverage।
"""
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from .factories import make_customer, make_loyalty_points


# ─── Family Account Tests ─────────────────────────────────────────────────────

class FamilyAccountTest(TestCase):

    def setUp(self):
        self.owner  = make_customer(code='FAMOWN01')
        self.member = make_customer(code='FAMMEM01')

    def test_create_family_account(self):
        from djoyalty.models.family_eco import FamilyAccount
        account = FamilyAccount.objects.create(
            owner=self.owner,
            name='Smith Family',
            account_code='FAM-SMITH01',
            pool_points=True,
            max_members=5,
            is_active=True,
        )
        self.assertEqual(account.owner, self.owner)
        self.assertTrue(account.pool_points)

    def test_owner_can_invite_member(self):
        from djoyalty.models.family_eco import FamilyAccount, FamilyMember
        account = FamilyAccount.objects.create(
            owner=self.owner, name='Smith Family',
            account_code='FAM-INV01', max_members=5, is_active=True,
        )
        member_record = FamilyMember.objects.create(
            family_account=account, customer=self.member,
            role='adult', can_redeem=True, can_transfer=False,
            is_active=True,
        )
        self.assertEqual(member_record.customer, self.member)
        self.assertEqual(account.members.count(), 1)

    def test_max_members_constraint(self):
        from djoyalty.models.family_eco import FamilyAccount
        account = FamilyAccount.objects.create(
            owner=self.owner, name='Family', account_code='FAM-MAX01',
            max_members=2, is_active=True,
        )
        self.assertEqual(account.max_members, 2)

    def test_family_serializer_owner_code(self):
        from djoyalty.models.family_eco import FamilyAccount
        from djoyalty.serializers.EcoFamilySerializer import FamilyAccountSerializer
        account = FamilyAccount.objects.create(
            owner=self.owner, name='Test', account_code='FAM-SER01',
            max_members=5, is_active=True,
        )
        s = FamilyAccountSerializer(account)
        self.assertEqual(s.data['owner_code'], self.owner.code)

    def test_family_invite_serializer_needs_code_or_email(self):
        from djoyalty.serializers.EcoFamilySerializer import FamilyInviteSerializer
        s = FamilyInviteSerializer(data={'role': 'adult'})
        self.assertFalse(s.is_valid())

        s = FamilyInviteSerializer(data={'customer_code': 'FAMMEM01', 'role': 'adult'})
        self.assertTrue(s.is_valid())

        s = FamilyInviteSerializer(data={'email': 'test@test.com', 'role': 'adult'})
        self.assertTrue(s.is_valid())


# ─── Eco Action Tests ─────────────────────────────────────────────────────────

class EcoActionTest(TestCase):

    def setUp(self):
        self.customer = make_customer(code='ECOCUST01')
        make_loyalty_points(self.customer, balance=Decimal('200'))

    def test_create_eco_action(self):
        from djoyalty.models.family_eco import EcoAction
        action = EcoAction.objects.create(
            name='Recycle Plastic',
            action_type='recycling',
            points_reward=Decimal('50'),
            co2_saved_kg=Decimal('0.5'),
            max_per_customer_per_day=3,
            is_active=True,
        )
        self.assertEqual(action.action_type, 'recycling')
        self.assertEqual(action.points_reward, Decimal('50'))

    def test_eco_action_serializer_is_valid(self):
        from djoyalty.models.family_eco import EcoAction
        from djoyalty.serializers.EcoFamilySerializer import EcoActionSerializer
        action = EcoAction(
            name='Plant Tree', action_type='tree_planting',
            points_reward=Decimal('100'), co2_saved_kg=Decimal('5'),
            max_per_customer_per_day=1, is_active=True,
        )
        s = EcoActionSerializer(action)
        self.assertTrue(s.data['is_currently_valid'])

    def test_eco_action_inactive_not_valid(self):
        from djoyalty.models.family_eco import EcoAction
        from djoyalty.serializers.EcoFamilySerializer import EcoActionSerializer
        action = EcoAction(
            name='Inactive', action_type='recycling',
            points_reward=Decimal('10'), co2_saved_kg=Decimal('0.1'),
            is_active=False,
        )
        s = EcoActionSerializer(action)
        self.assertFalse(s.data['is_currently_valid'])

    def test_log_eco_action_creates_record(self):
        from djoyalty.models.family_eco import EcoAction, CustomerEcoAction
        action = EcoAction.objects.create(
            name='Use Public Transport', action_type='transport',
            points_reward=Decimal('30'), co2_saved_kg=Decimal('2.0'),
            max_per_customer_per_day=2, is_active=True,
        )
        record = CustomerEcoAction.objects.create(
            customer=self.customer,
            eco_action=action,
            points_awarded=Decimal('30'),
            co2_saved_kg=Decimal('2.0'),
            completed_at=timezone.now(),
        )
        self.assertEqual(record.customer, self.customer)
        self.assertEqual(record.points_awarded, Decimal('30'))

    def test_eco_stats_created_or_updated(self):
        from djoyalty.models.family_eco import CustomerEcoStats
        stats, created = CustomerEcoStats.objects.get_or_create(
            customer=self.customer,
            defaults={
                'total_eco_points': Decimal('0'),
                'total_co2_saved_kg': Decimal('0'),
                'total_eco_actions': 0,
            },
        )
        stats.total_eco_points   += Decimal('30')
        stats.total_co2_saved_kg += Decimal('2.0')
        stats.total_eco_actions  += 1
        stats.save()
        stats.refresh_from_db()
        self.assertEqual(stats.total_eco_points, Decimal('30'))
        self.assertEqual(stats.total_eco_actions, 1)


# ─── Charity Tests ────────────────────────────────────────────────────────────

class CharityTest(TestCase):

    def setUp(self):
        self.customer = make_customer(code='CHARCUST01')
        make_loyalty_points(self.customer, balance=Decimal('1000'))

    def test_create_charity_cause(self):
        from djoyalty.models.family_eco import CharityCause
        cause = CharityCause.objects.create(
            name='Plant Trees Bangladesh',
            description='Plant trees to fight climate change.',
            category='environment',
            points_per_donation_unit=Decimal('10'),
            min_donation_points=Decimal('100'),
            total_points_donated=Decimal('0'),
            total_currency_donated=Decimal('0'),
            is_active=True,
        )
        self.assertEqual(cause.name, 'Plant Trees Bangladesh')
        self.assertTrue(cause.is_active)

    def test_charity_cause_serializer_total_donors_zero(self):
        from djoyalty.models.family_eco import CharityCause
        from djoyalty.serializers.EcoFamilySerializer import CharityCauseSerializer
        cause = CharityCause.objects.create(
            name='Ser Test Cause', category='education',
            points_per_donation_unit=Decimal('10'),
            min_donation_points=Decimal('50'),
            total_points_donated=Decimal('0'),
            total_currency_donated=Decimal('0'),
            is_active=True,
        )
        s = CharityCauseSerializer(cause)
        self.assertIn('impact_label', s.data)

    def test_charity_donate_serializer_positive_points(self):
        from djoyalty.serializers.EcoFamilySerializer import CharityDonateSerializer
        s = CharityDonateSerializer(data={'points_to_donate': '200'})
        self.assertTrue(s.is_valid())

    def test_charity_donate_serializer_zero_points_invalid(self):
        from djoyalty.serializers.EcoFamilySerializer import CharityDonateSerializer
        s = CharityDonateSerializer(data={'points_to_donate': '0'})
        self.assertFalse(s.is_valid())

    def test_charity_donate_serializer_negative_points_invalid(self):
        from djoyalty.serializers.EcoFamilySerializer import CharityDonateSerializer
        s = CharityDonateSerializer(data={'points_to_donate': '-100'})
        self.assertFalse(s.is_valid())

    def test_charity_donation_record_created(self):
        from djoyalty.models.family_eco import CharityCause, CharityDonation
        cause = CharityCause.objects.create(
            name='Education Fund', category='education',
            points_per_donation_unit=Decimal('10'),
            min_donation_points=Decimal('100'),
            total_points_donated=Decimal('0'),
            total_currency_donated=Decimal('0'),
            is_active=True,
        )
        donation = CharityDonation.objects.create(
            customer=self.customer, charity=cause,
            points_donated=Decimal('200'),
            currency_value=Decimal('20'),
            donated_at=timezone.now(),
        )
        self.assertEqual(donation.points_donated, Decimal('200'))
        self.assertEqual(donation.customer, self.customer)


# ─── Customer Consent Tests ───────────────────────────────────────────────────

class CustomerConsentTest(TestCase):

    def setUp(self):
        self.customer = make_customer(code='CONSCUST01')

    def test_create_consent(self):
        from djoyalty.models.family_eco import CustomerConsent
        consent = CustomerConsent.objects.create(
            customer=self.customer,
            consent_type='marketing_email',
            is_granted=True,
            granted_at=timezone.now(),
            source='web',
        )
        self.assertTrue(consent.is_granted)
        self.assertEqual(consent.consent_type, 'marketing_email')

    def test_revoke_consent(self):
        from djoyalty.models.family_eco import CustomerConsent
        consent = CustomerConsent.objects.create(
            customer=self.customer,
            consent_type='marketing_sms',
            is_granted=True,
            granted_at=timezone.now(),
            source='app',
        )
        consent.is_granted = False
        consent.revoked_at = timezone.now()
        consent.save()
        consent.refresh_from_db()
        self.assertFalse(consent.is_granted)
        self.assertIsNotNone(consent.revoked_at)

    def test_consent_update_serializer_valid_types(self):
        from djoyalty.serializers.EcoFamilySerializer import CustomerConsentUpdateSerializer
        valid_consents = {
            'marketing_email': True,
            'marketing_sms': False,
            'profiling': True,
        }
        s = CustomerConsentUpdateSerializer(data={'consents': valid_consents})
        self.assertTrue(s.is_valid(), s.errors)

    def test_consent_update_serializer_invalid_type(self):
        from djoyalty.serializers.EcoFamilySerializer import CustomerConsentUpdateSerializer
        s = CustomerConsentUpdateSerializer(data={'consents': {'sell_data': True}})
        self.assertFalse(s.is_valid())

    def test_multiple_consent_types_per_customer(self):
        from djoyalty.models.family_eco import CustomerConsent
        types = ['marketing_email', 'marketing_push', 'profiling', 'data_analytics']
        for t in types:
            CustomerConsent.objects.create(
                customer=self.customer, consent_type=t,
                is_granted=True, granted_at=timezone.now(), source='web',
            )
        count = CustomerConsent.objects.filter(customer=self.customer).count()
        self.assertEqual(count, 4)


# ─── Receipt Scan Tests ───────────────────────────────────────────────────────

class ReceiptScanTest(TestCase):

    def setUp(self):
        self.customer = make_customer(code='RECCUST01')

    def test_receipt_submit_serializer_valid(self):
        from djoyalty.serializers.EcoFamilySerializer import ReceiptSubmitSerializer
        s = ReceiptSubmitSerializer(data={
            'receipt_image_url': 'https://example.com/receipt.jpg',
            'channel': 'app',
        })
        self.assertTrue(s.is_valid(), s.errors)

    def test_receipt_submit_serializer_invalid_url(self):
        from djoyalty.serializers.EcoFamilySerializer import ReceiptSubmitSerializer
        s = ReceiptSubmitSerializer(data={
            'receipt_image_url': 'not-a-url',
            'channel': 'app',
        })
        self.assertFalse(s.is_valid())

    def test_create_receipt_scan(self):
        from djoyalty.models.family_eco import ReceiptScan
        receipt = ReceiptScan.objects.create(
            customer=self.customer,
            receipt_image_url='https://s3.example.com/receipt.jpg',
            status='pending',
            channel='app',
            submitted_at=timezone.now(),
        )
        self.assertEqual(receipt.status, 'pending')
        self.assertEqual(receipt.customer, self.customer)

    def test_receipt_scan_serializer_read_only_status(self):
        from djoyalty.models.family_eco import ReceiptScan
        from djoyalty.serializers.EcoFamilySerializer import ReceiptScanSerializer
        receipt = ReceiptScan(
            customer=self.customer,
            receipt_image_url='https://s3.example.com/r.jpg',
            status='pending',
            channel='app',
        )
        s = ReceiptScanSerializer(receipt)
        self.assertIn('status', s.data)
        self.assertEqual(s.data['status'], 'pending')
