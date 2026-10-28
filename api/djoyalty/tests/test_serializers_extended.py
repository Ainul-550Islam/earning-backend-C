# api/djoyalty/tests/test_serializers_extended.py
"""
Serializer Extended Tests -- NEW।
Original test_serializers.py covered only Customer + basic fields।
This file covers:
  - All new serializers (Cashout, Gamification, AI, Eco, Social)
  - Legacy alias name resolution (PointsSerializer, TierSerializer)
  - Validation edge cases across all new serializers
  - Read-only field enforcement
  - Nested serializer output shape
"""
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from .factories import make_customer, make_loyalty_points


# ─── Legacy Name Aliases ──────────────────────────────────────────────────────

class LegacyAliasTest(TestCase):
    """Verify that legacy serializer name aliases still resolve after the flat
    serializers.py fix."""

    def test_points_serializer_alias_resolves(self):
        from djoyalty.serializers import PointsSerializer, LoyaltyPointsSerializer
        self.assertIs(PointsSerializer, LoyaltyPointsSerializer)

    def test_tier_serializer_alias_resolves(self):
        from djoyalty.serializers import TierSerializer, LoyaltyTierSerializer
        self.assertIs(TierSerializer, LoyaltyTierSerializer)

    def test_redemption_serializer_alias_resolves(self):
        from djoyalty.serializers import RedemptionSerializer, RedemptionRequestSerializer
        self.assertIs(RedemptionSerializer, RedemptionRequestSerializer)

    def test_campaign_serializer_alias_resolves(self):
        from djoyalty.serializers import CampaignSerializer, LoyaltyCampaignSerializer
        self.assertIs(CampaignSerializer, LoyaltyCampaignSerializer)

    def test_partner_serializer_alias_resolves(self):
        from djoyalty.serializers import PartnerSerializer, PartnerMerchantSerializer
        self.assertIs(PartnerSerializer, PartnerMerchantSerializer)

    def test_insight_serializer_alias_resolves(self):
        from djoyalty.serializers import InsightSerializer, LoyaltyInsightSerializer
        self.assertIs(InsightSerializer, LoyaltyInsightSerializer)


# ─── Tenant Serializer Tests ──────────────────────────────────────────────────

class TenantSerializerTest(TestCase):

    def test_tenant_create_serializer_valid(self):
        from djoyalty.serializers.TenantSerializer import TenantCreateSerializer
        s = TenantCreateSerializer(data={
            'name': 'Acme Corp',
            'slug': 'acme-corp',
            'plan': 'enterprise',
        })
        self.assertTrue(s.is_valid(), s.errors)

    def test_tenant_create_serializer_missing_name(self):
        from djoyalty.serializers.TenantSerializer import TenantCreateSerializer
        s = TenantCreateSerializer(data={'slug': 'acme', 'plan': 'starter'})
        self.assertFalse(s.is_valid())
        self.assertIn('name', s.errors)

    def test_tenant_admin_serializer_has_api_key(self):
        from djoyalty.serializers.TenantSerializer import TenantAdminSerializer
        meta_fields = TenantAdminSerializer.Meta.fields
        self.assertIn('api_key', meta_fields)

    def test_tenant_public_serializer_no_api_key(self):
        from djoyalty.serializers.TenantSerializer import TenantSerializer
        meta_fields = TenantSerializer.Meta.fields
        self.assertNotIn('api_key', meta_fields)


# ─── Audit Serializer Tests ───────────────────────────────────────────────────

class AuditSerializerTest(TestCase):

    def setUp(self):
        self.customer = make_customer(code='AUDSER01')

    def test_audit_log_all_fields_read_only(self):
        from djoyalty.serializers.AuditSerializer import AdminAuditLogSerializer
        ro = AdminAuditLogSerializer.Meta.read_only_fields
        fields = AdminAuditLogSerializer.Meta.fields
        self.assertEqual(set(ro), set(fields),
                         'All audit log fields must be read-only')

    def test_system_config_serializer_valid(self):
        from djoyalty.serializers.AuditSerializer import SystemConfigSerializer
        from djoyalty.models.audit import SystemConfig
        cfg = SystemConfig(
            key='max_earn_per_day',
            value='5000',
            value_type='integer',
            is_sensitive=False,
        )
        s = SystemConfigSerializer(cfg)
        self.assertIn('key', s.data)
        self.assertIn('typed_value', s.data)

    def test_system_config_masks_sensitive(self):
        from djoyalty.serializers.AuditSerializer import SystemConfigSerializer
        from djoyalty.models.audit import SystemConfig
        cfg = SystemConfig(
            key='stripe_secret_key',
            value='sk_live_supersecret',
            value_type='string',
            is_sensitive=True,
        )
        s = SystemConfigSerializer(cfg)
        self.assertEqual(s.data['value'], '***')
        self.assertEqual(s.data['typed_value'], '***')

    def test_product_catalog_rule_is_valid_active(self):
        from djoyalty.serializers.AuditSerializer import ProductCatalogRuleSerializer
        from djoyalty.models.audit import ProductCatalogRule
        rule = ProductCatalogRule(
            name='Double Points on Electronics',
            rule_type='category',
            target_value='electronics',
            earn_type='multiplier',
            value=Decimal('2'),
            is_active=True,
            valid_from=None,
            valid_until=None,
        )
        s = ProductCatalogRuleSerializer(rule)
        self.assertTrue(s.data['is_currently_valid'])


# ─── Points Extended Serializer Tests ────────────────────────────────────────

class PointsExtendedSerializerTest(TestCase):

    def setUp(self):
        self.customer = make_customer(code='PTEXTSER01')
        make_loyalty_points(self.customer, balance=Decimal('500'))

    def test_points_expiry_serializer_days_until_expiry(self):
        from djoyalty.serializers.PointsExtendedSerializer import PointsExpirySerializer
        from djoyalty.models.points import PointsExpiry
        expiry = PointsExpiry.objects.create(
            customer=self.customer,
            points=Decimal('100'),
            expires_at=timezone.now() + timedelta(days=7),
            is_processed=False,
        )
        s = PointsExpirySerializer(expiry)
        self.assertGreaterEqual(s.data['days_until_expiry'], 6)

    def test_points_expiry_serializer_is_expired_false(self):
        from djoyalty.serializers.PointsExtendedSerializer import PointsExpirySerializer
        from djoyalty.models.points import PointsExpiry
        expiry = PointsExpiry.objects.create(
            customer=self.customer,
            points=Decimal('100'),
            expires_at=timezone.now() + timedelta(days=30),
            is_processed=False,
        )
        s = PointsExpirySerializer(expiry)
        self.assertFalse(s.data['is_expired'])

    def test_points_expiry_serializer_is_expired_true_past_date(self):
        from djoyalty.serializers.PointsExtendedSerializer import PointsExpirySerializer
        from djoyalty.models.points import PointsExpiry
        expiry = PointsExpiry.objects.create(
            customer=self.customer,
            points=Decimal('100'),
            expires_at=timezone.now() - timedelta(days=1),
            is_processed=False,
        )
        s = PointsExpirySerializer(expiry)
        self.assertTrue(s.data['is_expired'])

    def test_points_adjustment_create_zero_invalid(self):
        from djoyalty.serializers.PointsExtendedSerializer import PointsAdjustmentCreateSerializer
        s = PointsAdjustmentCreateSerializer(data={
            'points': '0',
            'reason': 'correction',
        })
        self.assertFalse(s.is_valid())

    def test_points_adjustment_create_valid(self):
        from djoyalty.serializers.PointsExtendedSerializer import PointsAdjustmentCreateSerializer
        s = PointsAdjustmentCreateSerializer(data={
            'points': '100',
            'reason': 'goodwill',
            'note': 'Customer complaint resolution',
        })
        self.assertTrue(s.is_valid(), s.errors)

    def test_points_adjustment_create_negative_valid(self):
        """Negative adjustments are valid (deductions)."""
        from djoyalty.serializers.PointsExtendedSerializer import PointsAdjustmentCreateSerializer
        s = PointsAdjustmentCreateSerializer(data={
            'points': '-50',
            'reason': 'fraud_reversal',
        })
        self.assertTrue(s.is_valid(), s.errors)


# ─── Notification Extended Serializer Tests ───────────────────────────────────

class NotificationExtendedSerializerTest(TestCase):

    def setUp(self):
        self.customer = make_customer(code='NOTEXTSER01')

    def test_bulk_read_serializer_requires_ids_or_mark_all(self):
        from djoyalty.serializers.NotificationExtendedSerializer import NotificationBulkReadSerializer
        s = NotificationBulkReadSerializer(data={
            'notification_ids': [], 'mark_all': False
        })
        self.assertFalse(s.is_valid())

    def test_bulk_read_serializer_mark_all_no_ids_needed(self):
        from djoyalty.serializers.NotificationExtendedSerializer import NotificationBulkReadSerializer
        s = NotificationBulkReadSerializer(data={
            'notification_ids': [1, 2, 3], 'mark_all': True
        })
        self.assertTrue(s.is_valid(), s.errors)

    def test_bulk_read_serializer_max_100_ids(self):
        from djoyalty.serializers.NotificationExtendedSerializer import NotificationBulkReadSerializer
        ids = list(range(1, 102))  # 101 ids -- exceeds max
        s = NotificationBulkReadSerializer(data={
            'notification_ids': ids, 'mark_all': False
        })
        self.assertFalse(s.is_valid())

    def test_points_alert_serializer_fields(self):
        from djoyalty.serializers.NotificationExtendedSerializer import PointsAlertSerializer
        from djoyalty.models.advanced import PointsAlert
        alert = PointsAlert.objects.create(
            customer=self.customer,
            alert_type='expiry_warning',
            threshold=Decimal('50'),
            is_active=True,
        )
        s = PointsAlertSerializer(alert)
        self.assertIn('alert_type', s.data)
        self.assertIn('threshold', s.data)
        self.assertIn('is_active', s.data)


# ─── Social Serializer Tests ──────────────────────────────────────────────────

class SocialSerializerTest(TestCase):

    def test_review_create_body_min_length(self):
        from djoyalty.serializers.SocialSerializer import CustomerReviewCreateSerializer
        s = CustomerReviewCreateSerializer(data={
            'review_reward_id': 1,
            'product_id': 'SKU001',
            'product_name': 'Test Product',
            'rating': 4,
            'body': 'Too short',  # < 20 chars
        })
        self.assertFalse(s.is_valid())
        self.assertIn('body', s.errors)

    def test_review_create_valid(self):
        from djoyalty.serializers.SocialSerializer import CustomerReviewCreateSerializer
        s = CustomerReviewCreateSerializer(data={
            'review_reward_id': 1,
            'product_id': 'SKU001',
            'product_name': 'Awesome Product',
            'rating': 5,
            'body': 'This product is absolutely amazing and I love it so much!',
        })
        self.assertTrue(s.is_valid(), s.errors)

    def test_review_create_rating_range(self):
        from djoyalty.serializers.SocialSerializer import CustomerReviewCreateSerializer
        for invalid_rating in [0, 6, -1]:
            s = CustomerReviewCreateSerializer(data={
                'review_reward_id': 1, 'product_id': 'X', 'product_name': 'X',
                'rating': invalid_rating,
                'body': 'A' * 25,
            })
            self.assertFalse(s.is_valid(), f'Rating {invalid_rating} should be invalid')

    def test_qr_scan_submit_serializer_valid(self):
        from djoyalty.serializers.SocialSerializer import QRCodeScanSubmitSerializer
        s = QRCodeScanSubmitSerializer(data={'code': 'QR-ABC123'})
        self.assertTrue(s.is_valid(), s.errors)

    def test_qr_scan_submit_serializer_missing_code(self):
        from djoyalty.serializers.SocialSerializer import QRCodeScanSubmitSerializer
        s = QRCodeScanSubmitSerializer(data={})
        self.assertFalse(s.is_valid())
        self.assertIn('code', s.errors)


# ─── Serializers __init__ Completeness Test ───────────────────────────────────

class SerializersInitCompletenessTest(TestCase):
    """Verify all new serializers are accessible from the package root."""

    EXPECTED = [
        # New: Tenant
        'TenantSerializer', 'TenantAdminSerializer', 'TenantCreateSerializer',
        # New: Audit
        'AdminAuditLogSerializer', 'CustomerDeviceSerializer', 'SystemConfigSerializer',
        'MultiCurrencyRateSerializer', 'ProductCatalogRuleSerializer',
        # New: Cashout
        'CashoutRequestSerializer', 'CashoutRateSerializer',
        'CustomerBankAccountSerializer', 'CustomerMobileWalletSerializer',
        'WalletTransactionSerializer',
        # New: Points Extended
        'PointsExpirySerializer', 'PointsAdjustmentDetailSerializer',
        # New: Notification Extended
        'LoyaltyNotificationSerializer', 'PointsAlertSerializer',
        'NotificationBulkReadSerializer', 'NotificationInboxSummarySerializer',
        # New: Gamification
        'SpinWheelConfigSerializer', 'ScratchCardSerializer',
        'LotteryDrawSerializer', 'LeaderboardSeasonSerializer', 'QuizRewardSerializer',
        # New: AI
        'CustomerAIProfileSerializer', 'PersonalizedOfferSerializer',
        'ChurnAlertSerializer', 'AIRecommendationSerializer',
        # New: Eco/Family
        'FamilyAccountSerializer', 'EcoActionSerializer',
        'CharityCauseSerializer', 'ExperientialRewardSerializer',
        'CustomerConsentSerializer', 'ReceiptScanSerializer',
        # New: Social
        'ReviewRewardSerializer', 'QRCodeEarnSerializer',
        'SocialShareRewardSerializer',
    ]

    def test_all_new_serializers_in_package(self):
        import djoyalty.serializers as ser_module
        missing = []
        for name in self.EXPECTED:
            if not hasattr(ser_module, name):
                missing.append(name)
        self.assertEqual(missing, [],
                         f'These serializers are missing from djoyalty.serializers: {missing}')
