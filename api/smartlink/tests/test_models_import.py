"""
Smoke tests for models/__init__.py.
Verifies that every model can be imported cleanly, including the
previously-broken PostbackLog import.
"""
from django.test import TestCase


class ModelsInitImportTest(TestCase):
    """Ensure models/__init__.py exports every declared model without errors."""

    def test_smartlink_models_import(self):
        from ..models import (
            SmartLink, SmartLinkDomain, SmartLinkGroup,
            SmartLinkRotation, SmartLinkFallback,
            SmartLinkTag, SmartLinkTagging, SmartLinkVersion,
        )
        for model in (
            SmartLink, SmartLinkDomain, SmartLinkGroup,
            SmartLinkRotation, SmartLinkFallback,
            SmartLinkTag, SmartLinkTagging, SmartLinkVersion,
        ):
            self.assertTrue(hasattr(model, '_meta'), f"{model} is not a Django model")

    def test_targeting_models_import(self):
        from ..models import (
            TargetingRule, GeoTargeting, DeviceTargeting,
            OSTargeting, BrowserTargeting, TimeTargeting,
            ISPTargeting, LanguageTargeting,
        )
        for model in (
            TargetingRule, GeoTargeting, DeviceTargeting,
            OSTargeting, BrowserTargeting, TimeTargeting,
            ISPTargeting, LanguageTargeting,
        ):
            self.assertTrue(hasattr(model, '_meta'), f"{model} is not a Django model")

    def test_offer_pool_models_import(self):
        from ..models import (
            OfferPool, OfferPoolEntry, OfferCapTracker,
            OfferBlacklist, OfferRotationLog, OfferScoreCache,
        )
        for model in (
            OfferPool, OfferPoolEntry, OfferCapTracker,
            OfferBlacklist, OfferRotationLog, OfferScoreCache,
        ):
            self.assertTrue(hasattr(model, '_meta'), f"{model} is not a Django model")

    def test_click_models_import(self):
        from ..models import (
            Click, ClickMetadata, UniqueClick,
            ClickFraudFlag, ClickHeatmap, BotClick, ClickSession,
        )
        for model in (
            Click, ClickMetadata, UniqueClick,
            ClickFraudFlag, ClickHeatmap, BotClick, ClickSession,
        ):
            self.assertTrue(hasattr(model, '_meta'), f"{model} is not a Django model")

    def test_redirect_models_import(self):
        from ..models import (
            RedirectLog, RedirectRule, LandingPage,
            PreLander, RedirectChain,
        )
        for model in (
            RedirectLog, RedirectRule, LandingPage,
            PreLander, RedirectChain,
        ):
            self.assertTrue(hasattr(model, '_meta'), f"{model} is not a Django model")

    def test_publisher_models_import(self):
        from ..models import (
            PublisherSmartLink, PublisherSubID, PublisherDomain,
            PublisherAllowList, PublisherBlockList,
        )
        for model in (
            PublisherSmartLink, PublisherSubID, PublisherDomain,
            PublisherAllowList, PublisherBlockList,
        ):
            self.assertTrue(hasattr(model, '_meta'), f"{model} is not a Django model")

    def test_analytics_models_import(self):
        from ..models import (
            SmartLinkStat, SmartLinkDailyStat, OfferPerformanceStat,
            GeoPerformanceStat, DevicePerformanceStat, ABTestResult,
        )
        for model in (
            SmartLinkStat, SmartLinkDailyStat, OfferPerformanceStat,
            GeoPerformanceStat, DevicePerformanceStat, ABTestResult,
        ):
            self.assertTrue(hasattr(model, '_meta'), f"{model} is not a Django model")

    def test_postback_log_import_fixed(self):
        """This import was previously broken — the line had no trailing newline."""
        from ..models import PostbackLog
        self.assertTrue(hasattr(PostbackLog, '_meta'))

    def test_postback_log_in_all(self):
        from .. import models
        self.assertIn('PostbackLog', models.__all__)

    def test_all_exports_are_importable(self):
        from .. import models
        for name in models.__all__:
            obj = getattr(models, name, None)
            self.assertIsNotNone(obj, f"__all__ entry '{name}' is not exported from models")


class ModelDbTableNamesTest(TestCase):
    """Verify Meta.db_table values don't collide and follow naming convention."""

    def test_all_model_db_tables_start_with_sl_prefix(self):
        """
        Verify db_table names for click/session/postback/redirect/publisher models.
        The main SmartLink model uses 'smartlink' (no prefix) by design.
        """
        from ..models import (
            Click, ClickSession, BotClick,
            PostbackLog, OfferRotationLog, RedirectLog, RedirectChain,
            PublisherAllowList, PublisherBlockList,
        )
        sl_prefixed_models = [
            Click, ClickSession, BotClick,
            PostbackLog, OfferRotationLog, RedirectLog, RedirectChain,
            PublisherAllowList, PublisherBlockList,
        ]
        for model in sl_prefixed_models:
            self.assertTrue(
                model._meta.db_table.startswith('sl_'),
                f"{model.__name__}.db_table '{model._meta.db_table}' does not start with 'sl_'"
            )

    def test_postback_log_db_table(self):
        from ..models import PostbackLog
        self.assertEqual(PostbackLog._meta.db_table, 'sl_postback_log')

    def test_redirect_chain_db_table(self):
        from ..models import RedirectChain
        self.assertEqual(RedirectChain._meta.db_table, 'sl_redirect_chain')


class PostbackLogModelTest(TestCase):
    """Direct model-level tests for PostbackLog."""

    def test_create_postback_log(self):
        from ..models import PostbackLog
        log = PostbackLog.objects.create(
            click_id='click_test_001',
            offer_id='offer_100',
            event='lead',
            payout='2.5000',
            currency='USD',
            transaction_id='txn_abc',
        )
        self.assertIsNotNone(log.pk)
        self.assertIsNotNone(log.created_at)

    def test_postback_log_str(self):
        from ..models import PostbackLog
        log = PostbackLog.objects.create(
            click_id='click_str_test',
            offer_id='offer_200',
            event='sale',
            payout='10.0000',
            currency='USD',
        )
        s = str(log)
        self.assertIn('click_str_test', s)
        self.assertIn('offer_200', s)

    def test_postback_log_ordering_newest_first(self):
        from ..models import PostbackLog
        PostbackLog.objects.create(click_id='first', offer_id='o1', payout=0)
        PostbackLog.objects.create(click_id='second', offer_id='o1', payout=0)
        logs = list(PostbackLog.objects.all())
        self.assertEqual(logs[0].click_id, 'second')

    def test_postback_log_default_flags(self):
        from ..models import PostbackLog
        log = PostbackLog.objects.create(
            click_id='click_flags', offer_id='o1', payout=0,
        )
        self.assertFalse(log.is_duplicate)
        self.assertFalse(log.is_attributed)

    def test_postback_log_raw_params_stored(self):
        from ..models import PostbackLog
        raw = {'source': 'facebook', 'campaign': 'summer24'}
        log = PostbackLog.objects.create(
            click_id='click_params', offer_id='o1',
            payout=1.0, raw_params=raw,
        )
        log.refresh_from_db()
        self.assertEqual(log.raw_params['source'], 'facebook')


class RedirectChainModelTest(TestCase):
    """Tests for RedirectChain.add_hop() method."""

    def setUp(self):
        from .factories import SmartLinkFactory, ClickFactory
        self.sl = SmartLinkFactory()
        self.click = ClickFactory(smartlink=self.sl)

    def test_add_hop_increments_hop_count(self):
        from ..models import RedirectChain
        chain = RedirectChain.objects.create(
            smartlink=self.sl,
            click=self.click,
            hop_count=0,
        )
        chain.add_hop('smartlink', 'https://go.example.com/abc')
        self.assertEqual(chain.hop_count, 1)
        self.assertEqual(len(chain.chain), 1)

    def test_add_hop_records_step_type_and_url(self):
        from ..models import RedirectChain
        chain = RedirectChain.objects.create(
            smartlink=self.sl,
            click=self.click,
            hop_count=0,
        )
        chain.add_hop('pre_lander', 'https://survey.example.com/')
        hop = chain.chain[0]
        self.assertEqual(hop['type'], 'pre_lander')
        self.assertEqual(hop['url'], 'https://survey.example.com/')
        self.assertEqual(hop['step'], 1)
        self.assertIn('ts', hop)

    def test_add_multiple_hops_sequential_steps(self):
        from ..models import RedirectChain
        chain = RedirectChain.objects.create(
            smartlink=self.sl,
            click=self.click,
            hop_count=0,
        )
        chain.add_hop('smartlink', 'https://go.example.com/x')
        chain.add_hop('offer', 'https://offer.example.com/')
        chain.refresh_from_db()
        self.assertEqual(chain.hop_count, 2)
        self.assertEqual(chain.chain[0]['step'], 1)
        self.assertEqual(chain.chain[1]['step'], 2)
