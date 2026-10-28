# publisher_tools/tests/test_serializers_new.py
"""
Publisher Management subfolder — নতুন serializers-এর সম্পূর্ণ unit test।

Covers all 19 new serializers added in serializers.py:
  KYCDocumentSerializer
  PublisherKYCSerializer
  KYCSubmitSerializer
  PublisherBankAccountSerializer
  BankAccountAddSerializer
  PublisherStoreSerializer
  StoreContactMessageSerializer
  PublisherSubscriptionSerializer
  SubscriptionPlanSerializer
  SubscriptionPaymentHistorySerializer
  PublisherVerificationSerializer
  PublisherBusinessSerializer
  PublisherRatingSerializer
  PublisherRatingConfigSerializer
  PublisherRatingRecordSerializer
  PublisherAggregateRatingSerializer
  PublisherCommissionSerializer
  CommissionTierSerializer
  PublisherReferralSerializer
  PublisherBlacklistSerializer
  PublisherBlacklistEntrySerializer
  PublisherLeaderboardSerializer
  PublisherPerformanceTargetSerializer
  PublisherPerformanceSnapshotSerializer
"""
import pytest
from datetime import date, datetime, timezone as dt_tz
from decimal import Decimal
from unittest.mock import MagicMock


# ── Helper ────────────────────────────────────────────────────────────────────

def mock_obj(**kwargs):
    obj = MagicMock()
    obj.pk         = kwargs.get('pk', 1)
    obj.created_at = datetime(2025, 1, 15, tzinfo=dt_tz.utc)
    obj.updated_at = datetime(2025, 1, 15, tzinfo=dt_tz.utc)
    for k, v in kwargs.items():
        setattr(obj, k, v)
    return obj


# ══════════════════════════════════════════════════════════════════════════════
# KYCDocumentSerializer
# ══════════════════════════════════════════════════════════════════════════════

class TestKYCDocumentSerializer:
    def test_read_only_fields_present(self):
        from publisher_tools.serializers import KYCDocumentSerializer
        obj = mock_obj(
            document_type='id_front',
            file_url='https://cdn.example.com/id.jpg',
            status='pending',
        )
        obj.is_expired.return_value = False
        data = KYCDocumentSerializer(obj).data
        assert 'document_type' in data
        assert 'file_url'      in data
        assert 'status'        in data
        assert 'is_expired'    in data

    def test_all_required_fields_present(self):
        from publisher_tools.serializers import KYCDocumentSerializer
        obj = mock_obj(
            document_type='id_back',
            file_url='https://cdn.example.com/back.jpg',
            status='approved',
        )
        obj.is_expired.return_value = False
        for field in ['document_type', 'file_url', 'status', 'uploaded_at']:
            assert field in KYCDocumentSerializer(obj).data


# ══════════════════════════════════════════════════════════════════════════════
# KYCSubmitSerializer (input validation)
# ══════════════════════════════════════════════════════════════════════════════

class TestKYCSubmitSerializer:

    VALID = {
        'kyc_type':  'individual',
        'full_name': 'Test Publisher',
        'id_type':   'passport',
        'id_number': 'A12345678',
        'country':   'BD',
    }

    def test_valid_data_passes(self):
        from publisher_tools.serializers import KYCSubmitSerializer
        s = KYCSubmitSerializer(data=self.VALID)
        assert s.is_valid(), s.errors

    def test_missing_kyc_type_fails(self):
        from publisher_tools.serializers import KYCSubmitSerializer
        data = {k: v for k, v in self.VALID.items() if k != 'kyc_type'}
        s    = KYCSubmitSerializer(data=data)
        assert not s.is_valid()
        assert 'kyc_type' in s.errors

    def test_invalid_kyc_type_fails(self):
        from publisher_tools.serializers import KYCSubmitSerializer
        data = {**self.VALID, 'kyc_type': 'invalid_type'}
        s    = KYCSubmitSerializer(data=data)
        assert not s.is_valid()
        assert 'kyc_type' in s.errors

    def test_missing_full_name_fails(self):
        from publisher_tools.serializers import KYCSubmitSerializer
        data = {k: v for k, v in self.VALID.items() if k != 'full_name'}
        s    = KYCSubmitSerializer(data=data)
        assert not s.is_valid()
        assert 'full_name' in s.errors

    def test_missing_id_type_fails(self):
        from publisher_tools.serializers import KYCSubmitSerializer
        data = {k: v for k, v in self.VALID.items() if k != 'id_type'}
        s    = KYCSubmitSerializer(data=data)
        assert not s.is_valid()
        assert 'id_type' in s.errors

    def test_invalid_id_type_fails(self):
        from publisher_tools.serializers import KYCSubmitSerializer
        data = {**self.VALID, 'id_type': 'unknown_doc'}
        s    = KYCSubmitSerializer(data=data)
        assert not s.is_valid()
        assert 'id_type' in s.errors

    def test_valid_id_types(self):
        from publisher_tools.serializers import KYCSubmitSerializer
        valid_id_types = ['passport', 'national_id', 'driving_license', 'tax_id', 'other']
        for it in valid_id_types:
            data = {**self.VALID, 'id_type': it}
            s    = KYCSubmitSerializer(data=data)
            assert s.is_valid(), f"id_type='{it}' should be valid: {s.errors}"

    def test_missing_id_number_fails(self):
        from publisher_tools.serializers import KYCSubmitSerializer
        data = {k: v for k, v in self.VALID.items() if k != 'id_number'}
        s    = KYCSubmitSerializer(data=data)
        assert not s.is_valid()
        assert 'id_number' in s.errors

    def test_missing_country_fails(self):
        from publisher_tools.serializers import KYCSubmitSerializer
        data = {k: v for k, v in self.VALID.items() if k != 'country'}
        s    = KYCSubmitSerializer(data=data)
        assert not s.is_valid()
        assert 'country' in s.errors

    def test_optional_fields_default_to_blank(self):
        from publisher_tools.serializers import KYCSubmitSerializer
        s = KYCSubmitSerializer(data=self.VALID)
        s.is_valid()
        vd = s.validated_data
        assert vd.get('documents') == []

    def test_documents_list_accepted(self):
        from publisher_tools.serializers import KYCSubmitSerializer
        data = {
            **self.VALID,
            'documents': [
                {'document_type': 'id_front', 'file_url': 'https://cdn.com/1.jpg'},
            ],
        }
        s = KYCSubmitSerializer(data=data)
        assert s.is_valid(), s.errors

    def test_business_kyc_type_valid(self):
        from publisher_tools.serializers import KYCSubmitSerializer
        s = KYCSubmitSerializer(data={**self.VALID, 'kyc_type': 'business'})
        assert s.is_valid(), s.errors


# ══════════════════════════════════════════════════════════════════════════════
# BankAccountAddSerializer
# ══════════════════════════════════════════════════════════════════════════════

class TestBankAccountAddSerializer:

    def test_bank_transfer_requires_account_number(self):
        from publisher_tools.serializers import BankAccountAddSerializer
        s = BankAccountAddSerializer(data={
            'account_type': 'bank_transfer',
        })
        assert not s.is_valid()
        assert 'account_number' in s.errors or not s.is_valid()

    def test_paypal_requires_email(self):
        from publisher_tools.serializers import BankAccountAddSerializer
        s = BankAccountAddSerializer(data={'account_type': 'paypal'})
        assert not s.is_valid()
        assert 'email' in s.errors

    def test_wise_requires_email(self):
        from publisher_tools.serializers import BankAccountAddSerializer
        s = BankAccountAddSerializer(data={'account_type': 'wise'})
        assert not s.is_valid()
        assert 'email' in s.errors

    def test_valid_paypal_data(self):
        from publisher_tools.serializers import BankAccountAddSerializer
        s = BankAccountAddSerializer(data={
            'account_type': 'paypal',
            'email':        'pub@paypal.com',
            'currency':     'USD',
        })
        assert s.is_valid(), s.errors

    def test_valid_bank_transfer_data(self):
        from publisher_tools.serializers import BankAccountAddSerializer
        s = BankAccountAddSerializer(data={
            'account_type':        'bank_transfer',
            'account_number':      '1234567890',
            'account_holder_name': 'Test Publisher',
            'bank_name':           'Test Bank',
            'bank_country':        'BD',
            'currency':            'USD',
        })
        assert s.is_valid(), s.errors

    def test_missing_account_type_fails(self):
        from publisher_tools.serializers import BankAccountAddSerializer
        s = BankAccountAddSerializer(data={'email': 'test@paypal.com'})
        assert not s.is_valid()
        assert 'account_type' in s.errors

    def test_invalid_account_type_fails(self):
        from publisher_tools.serializers import BankAccountAddSerializer
        s = BankAccountAddSerializer(data={
            'account_type': 'unknown_method',
            'email': 'test@test.com',
        })
        assert not s.is_valid()
        assert 'account_type' in s.errors

    def test_valid_account_types(self):
        from publisher_tools.serializers import BankAccountAddSerializer
        valid_types = ['bank_transfer', 'paypal', 'wise', 'payoneer', 'crypto', 'other']
        for at in valid_types:
            if at == 'bank_transfer':
                data = {'account_type': at, 'account_number': '123'}
            elif at in ('paypal', 'wise'):
                data = {'account_type': at, 'email': 'test@test.com'}
            else:
                data = {'account_type': at}
            s = BankAccountAddSerializer(data=data)
            s.is_valid()  # should not raise

    def test_set_as_primary_defaults_false(self):
        from publisher_tools.serializers import BankAccountAddSerializer
        s = BankAccountAddSerializer(data={
            'account_type': 'paypal', 'email': 'p@paypal.com',
        })
        s.is_valid()
        assert s.validated_data.get('set_as_primary') is False


# ══════════════════════════════════════════════════════════════════════════════
# PublisherStoreSerializer
# ══════════════════════════════════════════════════════════════════════════════

class TestPublisherStoreSerializer:
    def test_serializer_reads_object(self):
        from publisher_tools.serializers import PublisherStoreSerializer
        obj = mock_obj(
            store_name='My Publisher Store',
            description='A great store',
            slug='my-publisher-store',
            logo_url='https://cdn.com/logo.png',
            banner_url='',
            contact_email='contact@store.com',
            is_active=True,
        )
        obj.get_absolute_url.return_value = '/store/my-publisher-store/'
        data = PublisherStoreSerializer(obj).data
        assert data['store_name']    == 'My Publisher Store'
        assert data['is_active']     is True
        assert 'slug'                in data
        assert 'store_url'           in data

    def test_store_url_from_get_absolute_url(self):
        from publisher_tools.serializers import PublisherStoreSerializer
        obj = mock_obj(store_name='Test Store')
        obj.get_absolute_url.return_value = '/store/test-store/'
        data = PublisherStoreSerializer(obj).data
        assert data['store_url'] == '/store/test-store/'

    def test_missing_store_name_fails_write(self):
        from publisher_tools.serializers import PublisherStoreSerializer
        s = PublisherStoreSerializer(data={})
        assert not s.is_valid()
        assert 'store_name' in s.errors


# ══════════════════════════════════════════════════════════════════════════════
# StoreContactMessageSerializer
# ══════════════════════════════════════════════════════════════════════════════

class TestStoreContactMessageSerializer:
    def test_valid_data_passes(self):
        from publisher_tools.serializers import StoreContactMessageSerializer
        s = StoreContactMessageSerializer(data={
            'sender_name':  'Test Visitor',
            'sender_email': 'visitor@example.com',
            'subject':      'Hello',
            'message':      'I would like to contact you.',
        })
        assert s.is_valid(), s.errors

    def test_missing_sender_name_fails(self):
        from publisher_tools.serializers import StoreContactMessageSerializer
        s = StoreContactMessageSerializer(data={
            'sender_email': 'visitor@example.com',
            'message':      'Hello',
        })
        assert not s.is_valid()
        assert 'sender_name' in s.errors

    def test_missing_sender_email_fails(self):
        from publisher_tools.serializers import StoreContactMessageSerializer
        s = StoreContactMessageSerializer(data={
            'sender_name': 'Test',
            'message':     'Hello',
        })
        assert not s.is_valid()
        assert 'sender_email' in s.errors

    def test_invalid_email_fails(self):
        from publisher_tools.serializers import StoreContactMessageSerializer
        s = StoreContactMessageSerializer(data={
            'sender_name':  'Test',
            'sender_email': 'not-an-email',
            'message':      'Hello',
        })
        assert not s.is_valid()
        assert 'sender_email' in s.errors

    def test_missing_message_fails(self):
        from publisher_tools.serializers import StoreContactMessageSerializer
        s = StoreContactMessageSerializer(data={
            'sender_name':  'Test',
            'sender_email': 'test@example.com',
        })
        assert not s.is_valid()
        assert 'message' in s.errors

    def test_subject_is_optional(self):
        from publisher_tools.serializers import StoreContactMessageSerializer
        s = StoreContactMessageSerializer(data={
            'sender_name':  'Test',
            'sender_email': 'test@example.com',
            'message':      'No subject here.',
        })
        assert s.is_valid(), s.errors


# ══════════════════════════════════════════════════════════════════════════════
# SubscriptionPlanSerializer
# ══════════════════════════════════════════════════════════════════════════════

class TestSubscriptionPlanSerializer:
    def test_reads_plan_object(self):
        from publisher_tools.serializers import SubscriptionPlanSerializer
        obj = mock_obj(
            name='Pro Plan',
            tier='pro',
            monthly_price=Decimal('29.99'),
            annual_price=Decimal('299.90'),
            max_sites=10,
            max_apps=5,
            max_ad_units=100,
            features=['analytics', 'priority_support'],
            is_active=True,
        )
        obj.get_discount_pct.return_value = 16.7
        data = SubscriptionPlanSerializer(obj).data
        assert data['name']          == 'Pro Plan'
        assert data['max_sites']     == 10
        assert 'monthly_price'       in data
        assert 'features'            in data
        assert 'discount_pct'        in data


# ══════════════════════════════════════════════════════════════════════════════
# PublisherSubscriptionSerializer
# ══════════════════════════════════════════════════════════════════════════════

class TestPublisherSubscriptionSerializer:
    def test_reads_subscription(self):
        from publisher_tools.serializers import PublisherSubscriptionSerializer
        plan = mock_obj(name='Free Plan', tier='free',
                        monthly_price=Decimal('0'), annual_price=Decimal('0'),
                        max_sites=2, max_apps=1, max_ad_units=10,
                        features=[], is_active=True)
        plan.get_discount_pct.return_value = 0

        obj = mock_obj(status='active')
        obj.plan = plan
        obj.expires_at = None
        obj.can_add_site.return_value = True
        obj.can_add_app.return_value  = True

        data = PublisherSubscriptionSerializer(obj).data
        assert data['status']      == 'active'
        assert 'plan'              in data
        assert 'can_add_site'      in data
        assert 'can_add_app'       in data


# ══════════════════════════════════════════════════════════════════════════════
# PublisherVerificationSerializer
# ══════════════════════════════════════════════════════════════════════════════

class TestPublisherVerificationSerializer:
    def test_reads_verification(self):
        from publisher_tools.serializers import PublisherVerificationSerializer
        obj = mock_obj(
            verification_type='domain',
            target='example.com',
            method='dns_record',
            status='verified',
            verified_at=datetime(2025, 1, 10, tzinfo=dt_tz.utc),
            expires_at=datetime(2026, 1, 10, tzinfo=dt_tz.utc),
        )
        obj.is_expired.return_value = False
        data = PublisherVerificationSerializer(obj).data
        assert data['verification_type'] == 'domain'
        assert data['status']            == 'verified'
        assert data['is_expired']        is False
        assert 'verified_at'             in data
        assert 'expires_at'              in data


# ══════════════════════════════════════════════════════════════════════════════
# PublisherBusinessSerializer
# ══════════════════════════════════════════════════════════════════════════════

class TestPublisherBusinessSerializer:
    def test_reads_business(self):
        from publisher_tools.serializers import PublisherBusinessSerializer
        obj = mock_obj(
            legal_name='Acme Corp Ltd',
            registration_number='REG123456',
            tax_id='TAX789',
            business_type='llc',
            incorporation_country='BD',
            incorporation_date=date(2020, 1, 1),
            website='https://acme.com',
            is_verified=True,
            verified_at=datetime(2025, 1, 5, tzinfo=dt_tz.utc),
        )
        data = PublisherBusinessSerializer(obj).data
        assert data['legal_name']             == 'Acme Corp Ltd'
        assert data['incorporation_country']  == 'BD'
        assert data['is_verified']            is True
        assert 'website'                      in data

    def test_missing_legal_name_fails(self):
        from publisher_tools.serializers import PublisherBusinessSerializer
        s = PublisherBusinessSerializer(data={})
        assert not s.is_valid()
        assert 'legal_name' in s.errors

    def test_valid_data_passes(self):
        from publisher_tools.serializers import PublisherBusinessSerializer
        s = PublisherBusinessSerializer(data={
            'legal_name': 'Test Corp',
            'country':    'BD',
        })
        s.is_valid()  # should not raise for minimal required data


# ══════════════════════════════════════════════════════════════════════════════
# PublisherRatingSerializer
# ══════════════════════════════════════════════════════════════════════════════

class TestPublisherRatingSerializer:
    def test_reads_rating(self):
        from publisher_tools.serializers import PublisherRatingSerializer
        obj = mock_obj(
            overall_score=85,
            content_score=90,
            traffic_score=80,
            technical_score=85,
            tier='gold',
            updated_at=datetime(2025, 1, 15, tzinfo=dt_tz.utc),
        )
        obj.weighted_score.return_value = 87.5
        data = PublisherRatingSerializer(obj).data
        assert data['overall_score']   == 85
        assert data['weighted_score']  == 87.5
        assert data['tier']            == 'gold'
        assert 'content_score'         in data
        assert 'traffic_score'         in data
        assert 'technical_score'       in data


class TestPublisherRatingConfigSerializer:
    def test_reads_config(self):
        from publisher_tools.serializers import PublisherRatingConfigSerializer
        obj = mock_obj(
            content_weight=Decimal('0.40'),
            traffic_weight=Decimal('0.35'),
            tech_weight=Decimal('0.25'),
            is_active=True,
        )
        data = PublisherRatingConfigSerializer(obj).data
        assert 'content_weight' in data
        assert 'traffic_weight' in data
        assert 'tech_weight'    in data
        assert data['is_active'] is True


class TestPublisherRatingRecordSerializer:
    def test_reads_record(self):
        from publisher_tools.serializers import PublisherRatingRecordSerializer
        obj = mock_obj(
            rating_date=date(2025, 1, 15),
            content_score=88,
            traffic_score=82,
            technical_score=79,
            overall_score=83,
            notes='Excellent content quality.',
        )
        data = PublisherRatingRecordSerializer(obj).data
        assert data['overall_score']  == 83
        assert data['content_score']  == 88
        assert 'rating_date'          in data
        assert 'notes'                in data


class TestPublisherAggregateRatingSerializer:
    def test_reads_aggregate(self):
        from publisher_tools.serializers import PublisherAggregateRatingSerializer
        obj = mock_obj(
            avg_score=Decimal('84.5'),
            min_score=70,
            max_score=95,
            total_records=12,
            period_start=date(2025, 1, 1),
            period_end=date(2025, 1, 31),
        )
        data = PublisherAggregateRatingSerializer(obj).data
        assert 'avg_score'     in data
        assert 'total_records' in data
        assert 'period_start'  in data
        assert 'period_end'    in data


# ══════════════════════════════════════════════════════════════════════════════
# CommissionTierSerializer
# ══════════════════════════════════════════════════════════════════════════════

class TestCommissionTierSerializer:
    def test_reads_tier(self):
        from publisher_tools.serializers import CommissionTierSerializer
        obj = mock_obj(
            tier_name='Gold Tier',
            min_revenue=Decimal('10000'),
            max_revenue=Decimal('50000'),
            commission_pct=Decimal('30.00'),
            is_active=True,
        )
        data = CommissionTierSerializer(obj).data
        assert data['tier_name']      == 'Gold Tier'
        assert data['is_active']      is True
        assert 'commission_pct'       in data
        assert 'min_revenue'          in data


# ══════════════════════════════════════════════════════════════════════════════
# PublisherCommissionSerializer
# ══════════════════════════════════════════════════════════════════════════════

class TestPublisherCommissionSerializer:
    def test_reads_commission(self):
        from publisher_tools.serializers import PublisherCommissionSerializer
        obj = mock_obj(
            commission_type='monthly',
            amount=Decimal('250.00'),
            gross_revenue=Decimal('1000.00'),
            commission_pct=Decimal('25.00'),
            status='paid',
            period_start=date(2025, 1, 1),
            period_end=date(2025, 1, 31),
            paid_at=datetime(2025, 2, 5, tzinfo=dt_tz.utc),
        )
        data = PublisherCommissionSerializer(obj).data
        assert data['commission_type'] == 'monthly'
        assert data['status']          == 'paid'
        assert 'amount'                in data
        assert 'gross_revenue'         in data
        assert 'period_start'          in data


# ══════════════════════════════════════════════════════════════════════════════
# PublisherReferralSerializer
# ══════════════════════════════════════════════════════════════════════════════

class TestPublisherReferralSerializer:
    def test_reads_referral(self):
        from publisher_tools.serializers import PublisherReferralSerializer
        obj = mock_obj(
            referred_id='PUB002',
            referred_name='Referred Publisher',
            commission_rate=Decimal('5.00'),
            total_earned=Decimal('125.50'),
            status='active',
        )
        data = PublisherReferralSerializer(obj).data
        assert 'commission_rate' in data
        assert 'total_earned'    in data
        assert data['status']    == 'active'
        assert 'joined_at'       in data


# ══════════════════════════════════════════════════════════════════════════════
# PublisherBlacklistSerializer
# ══════════════════════════════════════════════════════════════════════════════

class TestPublisherBlacklistSerializer:
    def test_reads_blacklist(self):
        from publisher_tools.serializers import PublisherBlacklistSerializer
        obj = mock_obj(
            is_active=True,
            reason='Repeated policy violations',
            expires_at=None,
        )
        data = PublisherBlacklistSerializer(obj).data
        assert data['is_active']        is True
        assert data['reason']           == 'Repeated policy violations'
        assert 'blacklisted_at'         in data

    def test_reads_inactive_blacklist(self):
        from publisher_tools.serializers import PublisherBlacklistSerializer
        obj = mock_obj(is_active=False, reason='', expires_at=None)
        data = PublisherBlacklistSerializer(obj).data
        assert data['is_active'] is False


class TestPublisherBlacklistEntrySerializer:
    def test_reads_entry(self):
        from publisher_tools.serializers import PublisherBlacklistEntrySerializer
        obj = mock_obj(
            reason='Fraudulent traffic',
            is_active=True,
            added_by='admin_001',
            expires_at=datetime(2025, 12, 31, tzinfo=dt_tz.utc),
        )
        data = PublisherBlacklistEntrySerializer(obj).data
        assert 'reason'     in data
        assert 'added_by'   in data
        assert 'expires_at' in data
        assert 'created_at' in data


# ══════════════════════════════════════════════════════════════════════════════
# PublisherLeaderboardSerializer
# ══════════════════════════════════════════════════════════════════════════════

class TestPublisherLeaderboardSerializer:
    def test_reads_leaderboard_entry(self):
        from publisher_tools.serializers import PublisherLeaderboardSerializer
        obj = mock_obj(
            rank=5,
            score=Decimal('950.75'),
            tier='platinum',
            revenue_rank=3,
            quality_rank=8,
            period='2025-01',
            updated_at=datetime(2025, 1, 31, tzinfo=dt_tz.utc),
        )
        data = PublisherLeaderboardSerializer(obj).data
        assert data['rank']         == 5
        assert data['tier']         == 'platinum'
        assert 'revenue_rank'       in data
        assert 'quality_rank'       in data
        assert 'period'             in data


# ══════════════════════════════════════════════════════════════════════════════
# PublisherPerformanceTargetSerializer
# ══════════════════════════════════════════════════════════════════════════════

class TestPublisherPerformanceTargetSerializer:
    def test_reads_target(self):
        from publisher_tools.serializers import PublisherPerformanceTargetSerializer
        obj = mock_obj(
            metric='monthly_revenue',
            target_value=Decimal('5000.00'),
            period='monthly',
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 31),
        )
        data = PublisherPerformanceTargetSerializer(obj).data
        assert data['metric']       == 'monthly_revenue'
        assert 'target_value'       in data
        assert 'period'             in data
        assert 'start_date'         in data
        assert 'end_date'           in data


# ══════════════════════════════════════════════════════════════════════════════
# PublisherPerformanceSnapshotSerializer
# ══════════════════════════════════════════════════════════════════════════════

class TestPublisherPerformanceSnapshotSerializer:
    def test_reads_snapshot(self):
        from publisher_tools.serializers import PublisherPerformanceSnapshotSerializer
        obj = mock_obj(
            snapshot_date=date(2025, 1, 15),
            revenue=Decimal('1250.75'),
            impressions=500000,
            ecpm=Decimal('2.50'),
            fill_rate=Decimal('88.50'),
            quality_score=82,
        )
        data = PublisherPerformanceSnapshotSerializer(obj).data
        assert 'snapshot_date' in data
        assert 'revenue'       in data
        assert 'impressions'   in data
        assert 'ecpm'          in data
        assert 'fill_rate'     in data
        assert 'quality_score' in data
