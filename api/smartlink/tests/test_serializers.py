"""
Full serializer test suite.
Covers all 8 previously-missing serializers + existing ones.
"""
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from .factories import (
    SmartLinkFactory, UserFactory, ClickFactory, SmartLinkDailyStatFactory,
)
from ..models.click import BotClick, ClickSession
from ..models.offer_pool import OfferRotationLog, OfferScoreCache
from ..models.redirect import RedirectChain
from ..models.publisher import PublisherAllowList, PublisherBlockList
from ..models.postback_log import PostbackLog


# ─── Existing Serializers ─────────────────────────────────────────────────────

class ClickSerializerTest(TestCase):
    def test_click_serializer_fields(self):
        from ..serializers.ClickSerializer import ClickSerializer
        click = ClickFactory()
        data = ClickSerializer(click).data
        for field in ('country', 'device_type', 'is_unique', 'fraud_score'):
            self.assertIn(field, data)

    def test_stat_serializer_values(self):
        from ..serializers.SmartLinkStatSerializer import SmartLinkStatSerializer
        sl = SmartLinkFactory()
        stat = SmartLinkDailyStatFactory(
            smartlink=sl, clicks=500, unique_clicks=400,
            conversions=25, revenue=125.50,
        )
        data = SmartLinkStatSerializer(stat).data
        self.assertEqual(data['clicks'], 500)
        self.assertEqual(data['conversions'], 25)

    def test_insight_serializer_valid(self):
        from ..serializers.InsightSerializer import InsightSerializer
        s = InsightSerializer(data={
            'smartlink_id': 1, 'period_days': 30,
            'clicks': 1000, 'unique_clicks': 800,
            'conversions': 50, 'revenue': '250.0000',
            'epc': 0.25, 'conversion_rate': 5.0,
            'quality_rate': 95.0, 'bot_clicks': 10,
            'fraud_clicks': 5,
        })
        self.assertTrue(s.is_valid(), s.errors)


# ─── PostbackLogSerializer ────────────────────────────────────────────────────

class PostbackLogSerializerTest(TestCase):
    def setUp(self):
        self.log = PostbackLog.objects.create(
            click_id='click_abc',
            offer_id='offer_999',
            event='lead',
            payout='2.5000',
            currency='USD',
            transaction_id='txn_001',
        )

    def test_read_serializer_contains_all_fields(self):
        from ..serializers.PostbackLogSerializer import PostbackLogSerializer
        data = PostbackLogSerializer(self.log).data
        for field in (
            'id', 'click_id', 'offer_id', 'event',
            'payout', 'currency', 'transaction_id',
            'is_duplicate', 'is_attributed', 'created_at',
        ):
            self.assertIn(field, data)

    def test_create_serializer_valid_lead(self):
        from ..serializers.PostbackLogSerializer import PostbackLogCreateSerializer
        s = PostbackLogCreateSerializer(data={
            'click_id': 'click_xyz',
            'offer_id': 'offer_100',
            'event': 'lead',
            'payout': '3.0000',
            'currency': 'USD',
        })
        self.assertTrue(s.is_valid(), s.errors)

    def test_create_serializer_negative_payout_invalid(self):
        from ..serializers.PostbackLogSerializer import PostbackLogCreateSerializer
        s = PostbackLogCreateSerializer(data={
            'click_id': 'click_xyz',
            'event': 'lead',
            'payout': '-1.00',
            'currency': 'USD',
        })
        self.assertFalse(s.is_valid())
        self.assertIn('payout', s.errors)

    def test_create_serializer_unknown_event_invalid(self):
        from ..serializers.PostbackLogSerializer import PostbackLogCreateSerializer
        s = PostbackLogCreateSerializer(data={
            'event': 'refund',
            'payout': '2.00',
            'currency': 'USD',
        })
        self.assertFalse(s.is_valid())
        self.assertIn('event', s.errors)

    def test_create_serializer_bad_currency_invalid(self):
        from ..serializers.PostbackLogSerializer import PostbackLogCreateSerializer
        s = PostbackLogCreateSerializer(data={
            'event': 'lead',
            'payout': '2.00',
            'currency': 'US',  # wrong length
        })
        self.assertFalse(s.is_valid())
        self.assertIn('currency', s.errors)

    def test_create_serializer_normalises_currency_to_uppercase(self):
        from ..serializers.PostbackLogSerializer import PostbackLogCreateSerializer
        s = PostbackLogCreateSerializer(data={
            'click_id': 'c1',
            'offer_id': 'o1',
            'event': 'sale',
            'payout': '10.00',
            'currency': 'eur',
        })
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(s.validated_data['currency'], 'EUR')

    def test_read_serializer_is_fully_read_only(self):
        from ..serializers.PostbackLogSerializer import PostbackLogSerializer
        s = PostbackLogSerializer(self.log, data={'payout': '99.00'}, partial=True)
        # All fields are read-only; validated_data should be empty
        self.assertTrue(s.is_valid())
        self.assertEqual(s.validated_data, {})


# ─── ClickSessionSerializer ───────────────────────────────────────────────────

class ClickSessionSerializerTest(TestCase):
    def setUp(self):
        self.sl = SmartLinkFactory()
        self.session = ClickSession.objects.create(
            smartlink=self.sl,
            ip='1.2.3.4',
            country='US',
            device_type='mobile',
            click_count=3,
        )

    def test_session_serializer_contains_expected_fields(self):
        from ..serializers.ClickSessionSerializer import ClickSessionSerializer
        data = ClickSessionSerializer(self.session).data
        for field in (
            'id', 'session_id', 'smartlink', 'smartlink_slug',
            'ip', 'country', 'device_type', 'click_count',
            'first_seen', 'last_seen', 'duration_seconds',
        ):
            self.assertIn(field, data)

    def test_session_serializer_slug_matches(self):
        from ..serializers.ClickSessionSerializer import ClickSessionSerializer
        data = ClickSessionSerializer(self.session).data
        self.assertEqual(data['smartlink_slug'], self.sl.slug)

    def test_duration_seconds_zero_when_no_timestamps(self):
        from ..serializers.ClickSessionSerializer import ClickSessionSerializer
        data = ClickSessionSerializer(self.session).data
        self.assertGreaterEqual(data['duration_seconds'], 0)

    def test_list_serializer_omits_user_agent(self):
        from ..serializers.ClickSessionSerializer import ClickSessionListSerializer
        data = ClickSessionListSerializer(self.session).data
        self.assertNotIn('user_agent', data)
        self.assertIn('click_count', data)


# ─── BotClickSerializer ───────────────────────────────────────────────────────

class BotClickSerializerTest(TestCase):
    def setUp(self):
        self.sl = SmartLinkFactory()
        self.bot_click = BotClick.objects.create(
            smartlink=self.sl,
            ip='10.0.0.1',
            user_agent='Googlebot/2.1',
            bot_type='Googlebot',
            detection_method='ua_pattern',
            country='US',
        )

    def test_bot_click_serializer_fields(self):
        from ..serializers.BotClickSerializer import BotClickSerializer
        data = BotClickSerializer(self.bot_click).data
        for field in (
            'id', 'smartlink', 'smartlink_slug',
            'ip', 'bot_type', 'detection_method', 'country', 'created_at',
        ):
            self.assertIn(field, data)

    def test_bot_click_slug_matches(self):
        from ..serializers.BotClickSerializer import BotClickSerializer
        data = BotClickSerializer(self.bot_click).data
        self.assertEqual(data['smartlink_slug'], self.sl.slug)

    def test_summary_serializer_valid_data(self):
        from ..serializers.BotClickSerializer import BotClickSummarySerializer
        s = BotClickSummarySerializer(data={
            'total_bot_clicks': 150,
            'bot_types': {'Googlebot': 80, 'SEMrush': 40, 'Other': 30},
            'detection_methods': {'ua_pattern': 120, 'ip_list': 30},
            'top_countries': [{'country': 'US', 'count': 50}],
            'period_days': 30,
        })
        self.assertTrue(s.is_valid(), s.errors)


# ─── OfferRotationLogSerializer ───────────────────────────────────────────────

class OfferRotationLogSerializerTest(TestCase):
    def setUp(self):
        self.sl = SmartLinkFactory()
        self.log = OfferRotationLog.objects.create(
            smartlink=self.sl,
            offer=None,
            selected_reason='weighted_random',
            offer_weight=60,
            offer_epc=Decimal('0.2500'),
            country='BD',
            device_type='mobile',
        )

    def test_rotation_log_serializer_fields(self):
        from ..serializers.OfferRotationLogSerializer import OfferRotationLogSerializer
        data = OfferRotationLogSerializer(self.log).data
        for field in (
            'id', 'smartlink', 'smartlink_slug', 'offer',
            'selected_reason', 'offer_weight', 'offer_epc',
            'country', 'device_type', 'created_at',
        ):
            self.assertIn(field, data)

    def test_rotation_log_slug_correct(self):
        from ..serializers.OfferRotationLogSerializer import OfferRotationLogSerializer
        data = OfferRotationLogSerializer(self.log).data
        self.assertEqual(data['smartlink_slug'], self.sl.slug)

    def test_offer_name_null_when_offer_deleted(self):
        from ..serializers.OfferRotationLogSerializer import OfferRotationLogSerializer
        data = OfferRotationLogSerializer(self.log).data
        self.assertIsNone(data['offer_name'])

    def test_list_serializer_excludes_heavy_fields(self):
        from ..serializers.OfferRotationLogSerializer import OfferRotationLogListSerializer
        data = OfferRotationLogListSerializer(self.log).data
        self.assertNotIn('offer_weight', data)
        self.assertIn('selected_reason', data)

    def test_summary_serializer_valid(self):
        from ..serializers.OfferRotationLogSerializer import OfferRotationSummarySerializer
        s = OfferRotationSummarySerializer(data={
            'offer_id': 1,
            'offer_name': 'Test Offer',
            'total_selections': 500,
            'percentage': 62.5,
            'avg_epc': '0.2500',
            'top_reason': 'weighted_random',
        })
        self.assertTrue(s.is_valid(), s.errors)


# ─── OfferScoreCacheSerializer ────────────────────────────────────────────────

class OfferScoreCacheSerializerTest(TestCase):
    def setUp(self):
        from offer_inventory.models import Offer
        offer = Offer.objects.create(name='Test Offer', payout='1.00')
        self.score_cache = OfferScoreCache.objects.create(
            offer=offer,
            country='US',
            device_type='mobile',
            epc=Decimal('0.3500'),
            conversion_rate=Decimal('0.0500'),
            total_clicks=1000,
            total_conversions=50,
            score=11.07,
        )

    def test_score_cache_serializer_fields(self):
        from ..serializers.OfferScoreCacheSerializer import OfferScoreCacheSerializer
        data = OfferScoreCacheSerializer(self.score_cache).data
        for field in (
            'id', 'offer', 'country', 'device_type',
            'epc', 'conversion_rate', 'total_clicks',
            'total_conversions', 'score', 'calculated_at',
        ):
            self.assertIn(field, data)

    def test_score_cache_epc_value(self):
        from ..serializers.OfferScoreCacheSerializer import OfferScoreCacheSerializer
        data = OfferScoreCacheSerializer(self.score_cache).data
        self.assertEqual(Decimal(data['epc']), Decimal('0.3500'))

    def test_rank_serializer_valid(self):
        from ..serializers.OfferScoreCacheSerializer import OfferScoreRankSerializer
        s = OfferScoreRankSerializer(data={
            'rank': 1,
            'offer_id': 1,
            'offer_name': 'Top Offer',
            'country': 'US',
            'device_type': 'mobile',
            'epc': '0.3500',
            'conversion_rate': '0.0500',
            'score': 11.07,
            'total_clicks': 1000,
            'calculated_at': timezone.now().isoformat(),
        })
        self.assertTrue(s.is_valid(), s.errors)

    def test_rank_serializer_rank_must_be_integer(self):
        from ..serializers.OfferScoreCacheSerializer import OfferScoreRankSerializer
        s = OfferScoreRankSerializer(data={
            'rank': 'first',
            'offer_id': 1,
            'offer_name': 'Offer',
            'country': 'US',
            'device_type': 'mobile',
            'epc': '0.10',
            'conversion_rate': '0.01',
            'score': 1.0,
            'total_clicks': 100,
            'calculated_at': timezone.now().isoformat(),
        })
        self.assertFalse(s.is_valid())
        self.assertIn('rank', s.errors)


# ─── RedirectChainSerializer ──────────────────────────────────────────────────

class RedirectChainSerializerTest(TestCase):
    def setUp(self):
        self.sl = SmartLinkFactory()
        self.click = ClickFactory(smartlink=self.sl)
        self.chain = RedirectChain.objects.create(
            smartlink=self.sl,
            click=self.click,
            chain=[
                {'step': 1, 'type': 'smartlink', 'url': 'https://go.example.com/abc', 'ts': '2024-01-01T00:00:00Z'},
                {'step': 2, 'type': 'offer', 'url': 'https://offer.example.com/', 'ts': '2024-01-01T00:00:00.010Z'},
            ],
            hop_count=2,
            total_time_ms=10.5,
            completed=True,
            final_url='https://offer.example.com/',
        )

    def test_chain_serializer_fields(self):
        from ..serializers.RedirectChainSerializer import RedirectChainSerializer
        data = RedirectChainSerializer(self.chain).data
        for field in (
            'id', 'smartlink', 'smartlink_slug', 'click',
            'hops', 'hop_count', 'total_time_ms',
            'completed', 'final_url', 'created_at', 'updated_at',
        ):
            self.assertIn(field, data)

    def test_chain_hops_list_has_correct_length(self):
        from ..serializers.RedirectChainSerializer import RedirectChainSerializer
        data = RedirectChainSerializer(self.chain).data
        self.assertEqual(len(data['hops']), 2)

    def test_chain_hops_contain_expected_keys(self):
        from ..serializers.RedirectChainSerializer import RedirectChainSerializer
        data = RedirectChainSerializer(self.chain).data
        hop = data['hops'][0]
        for key in ('step', 'type', 'url', 'ts'):
            self.assertIn(key, hop)

    def test_chain_slug_matches_smartlink(self):
        from ..serializers.RedirectChainSerializer import RedirectChainSerializer
        data = RedirectChainSerializer(self.chain).data
        self.assertEqual(data['smartlink_slug'], self.sl.slug)

    def test_list_serializer_omits_hops_detail(self):
        from ..serializers.RedirectChainSerializer import RedirectChainListSerializer
        data = RedirectChainListSerializer(self.chain).data
        self.assertNotIn('hops', data)
        self.assertIn('hop_count', data)
        self.assertIn('completed', data)


# ─── PublisherAllowListSerializer ────────────────────────────────────────────

class PublisherAllowListSerializerTest(TestCase):
    def setUp(self):
        self.publisher = UserFactory()
        self.admin = UserFactory(is_staff=True)
        self.entry = PublisherAllowList.objects.create(
            publisher=self.publisher,
            category='finance',
            is_active=True,
            granted_by=self.admin,
        )

    def test_serializer_fields(self):
        from ..serializers.PublisherAllowListSerializer import PublisherAllowListSerializer
        data = PublisherAllowListSerializer(self.entry).data
        for field in (
            'id', 'publisher', 'publisher_username', 'category',
            'is_active', 'granted_by', 'granted_by_username',
            'created_at', 'expires_at', 'is_expired',
        ):
            self.assertIn(field, data)

    def test_publisher_username_populated(self):
        from ..serializers.PublisherAllowListSerializer import PublisherAllowListSerializer
        data = PublisherAllowListSerializer(self.entry).data
        self.assertEqual(data['publisher_username'], self.publisher.username)

    def test_granted_by_username_populated(self):
        from ..serializers.PublisherAllowListSerializer import PublisherAllowListSerializer
        data = PublisherAllowListSerializer(self.entry).data
        self.assertEqual(data['granted_by_username'], self.admin.username)

    def test_is_expired_false_for_no_expiry(self):
        from ..serializers.PublisherAllowListSerializer import PublisherAllowListSerializer
        data = PublisherAllowListSerializer(self.entry).data
        self.assertFalse(data['is_expired'])

    def test_is_expired_true_for_past_expiry(self):
        from ..serializers.PublisherAllowListSerializer import PublisherAllowListSerializer
        from django.utils import timezone
        import datetime
        self.entry.expires_at = timezone.now() - datetime.timedelta(days=1)
        self.entry.save()
        data = PublisherAllowListSerializer(self.entry).data
        self.assertTrue(data['is_expired'])

    def test_create_valid_entry(self):
        from ..serializers.PublisherAllowListSerializer import PublisherAllowListSerializer
        s = PublisherAllowListSerializer(data={
            'publisher': self.publisher.pk,
            'category': 'gaming',
            'is_active': True,
            'granted_by': self.admin.pk,
        })
        self.assertTrue(s.is_valid(), s.errors)

    def test_blank_category_invalid(self):
        from ..serializers.PublisherAllowListSerializer import PublisherAllowListSerializer
        s = PublisherAllowListSerializer(data={
            'publisher': self.publisher.pk,
            'category': '   ',
            'granted_by': self.admin.pk,
        })
        self.assertFalse(s.is_valid())
        self.assertIn('category', s.errors)

    def test_duplicate_entry_invalid(self):
        from ..serializers.PublisherAllowListSerializer import PublisherAllowListSerializer
        s = PublisherAllowListSerializer(data={
            'publisher': self.publisher.pk,
            'category': 'finance',  # already exists
            'granted_by': self.admin.pk,
        })
        self.assertFalse(s.is_valid())

    def test_bulk_create_serializer_valid(self):
        from ..serializers.PublisherAllowListSerializer import PublisherAllowListBulkCreateSerializer
        s = PublisherAllowListBulkCreateSerializer(data={
            'publisher': self.publisher.pk,
            'categories': ['health', 'beauty', 'finance'],
        })
        self.assertTrue(s.is_valid(), s.errors)


# ─── PublisherBlockListSerializer ─────────────────────────────────────────────

class PublisherBlockListSerializerTest(TestCase):
    def setUp(self):
        self.publisher = UserFactory()
        self.admin = UserFactory(is_staff=True)
        self.entry = PublisherBlockList.objects.create(
            publisher=self.publisher,
            category='adult',
            reason='Compliance requirement',
            blocked_by=self.admin,
            is_active=True,
        )

    def test_serializer_fields(self):
        from ..serializers.PublisherBlockListSerializer import PublisherBlockListSerializer
        data = PublisherBlockListSerializer(self.entry).data
        for field in (
            'id', 'publisher', 'publisher_username',
            'category', 'reason', 'blocked_by',
            'blocked_by_username', 'is_active',
            'created_at', 'target_label',
        ):
            self.assertIn(field, data)

    def test_target_label_for_category(self):
        from ..serializers.PublisherBlockListSerializer import PublisherBlockListSerializer
        data = PublisherBlockListSerializer(self.entry).data
        self.assertIn('adult', data['target_label'])

    def test_publisher_username_populated(self):
        from ..serializers.PublisherBlockListSerializer import PublisherBlockListSerializer
        data = PublisherBlockListSerializer(self.entry).data
        self.assertEqual(data['publisher_username'], self.publisher.username)

    def test_validation_requires_advertiser_or_category(self):
        from ..serializers.PublisherBlockListSerializer import PublisherBlockListSerializer
        s = PublisherBlockListSerializer(data={
            'publisher': self.publisher.pk,
            'blocked_by': self.admin.pk,
            # No advertiser, no category
        })
        self.assertFalse(s.is_valid())

    def test_bulk_serializer_valid_with_categories(self):
        from ..serializers.PublisherBlockListSerializer import PublisherBlockListBulkSerializer
        s = PublisherBlockListBulkSerializer(data={
            'publisher': self.publisher.pk,
            'categories': ['adult', 'gambling'],
            'reason': 'Policy violation',
        })
        self.assertTrue(s.is_valid(), s.errors)

    def test_bulk_serializer_invalid_when_empty(self):
        from ..serializers.PublisherBlockListSerializer import PublisherBlockListBulkSerializer
        s = PublisherBlockListBulkSerializer(data={
            'publisher': self.publisher.pk,
            # No advertiser_ids, no categories
        })
        self.assertFalse(s.is_valid())
