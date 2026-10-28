"""
test_selectors.py – Tests for selectors.py query layer.
Covers BaseSelector, PostbackLogSelector, PostbackInsightSelector,
NetworkPostbackConfigSelector, and the standalone helper functions.
"""
import datetime
from django.test import TestCase
from django.utils import timezone


class BaseSelectorTests(TestCase):

    def test_base_selector_instantiable(self):
        from api.postback.selectors import BaseSelector
        from api.postback.models import PostbackLog
        sel = BaseSelector(PostbackLog)
        self.assertIsNotNone(sel)

    def test_base_selector_all_returns_queryset(self):
        from api.postback.selectors import BaseSelector
        from api.postback.models import PostbackLog
        sel = BaseSelector(PostbackLog)
        qs = sel.all()
        self.assertIsNotNone(qs)

    def test_base_selector_count_returns_int(self):
        from api.postback.selectors import BaseSelector
        from api.postback.models import PostbackLog
        sel = BaseSelector(PostbackLog)
        self.assertIsInstance(sel.count(), int)

    def test_base_selector_filter_returns_queryset(self):
        from api.postback.selectors import BaseSelector
        from api.postback.models import PostbackLog
        sel = BaseSelector(PostbackLog)
        result = sel.filter(status="received")
        self.assertIsNotNone(result)

    def test_base_selector_exists_returns_bool(self):
        from api.postback.selectors import BaseSelector
        from api.postback.models import PostbackLog
        sel = BaseSelector(PostbackLog)
        result = sel.exists()
        self.assertIsInstance(result, bool)


class PostbackLogSelectorTests(TestCase):

    def setUp(self):
        from api.postback.tests.factories import (
            NetworkPostbackConfigFactory, PostbackLogFactory,
            RewardedPostbackLogFactory, FailedPostbackLogFactory,
        )
        self.network = NetworkPostbackConfigFactory()
        self.log1 = RewardedPostbackLogFactory(network=self.network)
        self.log2 = FailedPostbackLogFactory(network=self.network)
        self.log3 = PostbackLogFactory(network=self.network)

    def test_postback_log_selector_instantiable(self):
        from api.postback.selectors import PostbackLogSelector
        sel = PostbackLogSelector()
        self.assertIsNotNone(sel)

    def test_select_by_status(self):
        from api.postback.selectors import PostbackLogSelector
        sel = PostbackLogSelector()
        result = sel.by_status("rewarded")
        self.assertIsNotNone(result)

    def test_select_by_network(self):
        from api.postback.selectors import PostbackLogSelector
        sel = PostbackLogSelector()
        result = sel.by_network(self.network.network_key)
        self.assertIsNotNone(result)

    def test_select_recent(self):
        from api.postback.selectors import PostbackLogSelector
        sel = PostbackLogSelector()
        result = sel.recent(days=7)
        self.assertIsNotNone(result)

    def test_select_failed(self):
        from api.postback.selectors import PostbackLogSelector
        sel = PostbackLogSelector()
        result = sel.failed()
        self.assertIsNotNone(result)

    def test_select_for_retry(self):
        from api.postback.selectors import PostbackLogSelector
        sel = PostbackLogSelector()
        result = sel.for_retry()
        self.assertIsNotNone(result)

    def test_count_by_status(self):
        from api.postback.selectors import PostbackLogSelector
        sel = PostbackLogSelector()
        result = sel.count_by_status()
        self.assertIsInstance(result, (dict, list))

    def test_select_by_lead_id(self):
        from api.postback.selectors import PostbackLogSelector
        sel = PostbackLogSelector()
        result = sel.by_lead_id(self.log1.lead_id or "test-lead-1")
        self.assertIsNotNone(result)


class PostbackInsightSelectorTests(TestCase):

    def test_insight_selector_instantiable(self):
        from api.postback.selectors import PostbackInsightSelector
        sel = PostbackInsightSelector()
        self.assertIsNotNone(sel)

    def test_select_with_anomalies(self):
        from api.postback.selectors import PostbackInsightSelector
        sel = PostbackInsightSelector()
        result = sel.with_anomalies()
        self.assertIsNotNone(result)

    def test_select_date_range(self):
        from api.postback.selectors import PostbackInsightSelector
        sel = PostbackInsightSelector()
        today = datetime.date.today()
        result = sel.date_range(today - datetime.timedelta(days=7), today)
        self.assertIsNotNone(result)

    def test_select_low_health(self):
        from api.postback.selectors import PostbackInsightSelector
        sel = PostbackInsightSelector()
        result = sel.low_health(threshold=50)
        self.assertIsNotNone(result)


class NetworkPostbackConfigSelectorTests(TestCase):

    def setUp(self):
        from api.postback.tests.factories import NetworkPostbackConfigFactory
        self.network = NetworkPostbackConfigFactory()

    def test_network_selector_instantiable(self):
        from api.postback.selectors import NetworkPostbackConfigSelector
        sel = NetworkPostbackConfigSelector()
        self.assertIsNotNone(sel)

    def test_select_active_networks(self):
        from api.postback.selectors import NetworkPostbackConfigSelector
        sel = NetworkPostbackConfigSelector()
        result = sel.active()
        self.assertIsNotNone(result)

    def test_select_by_network_key(self):
        from api.postback.selectors import NetworkPostbackConfigSelector
        sel = NetworkPostbackConfigSelector()
        result = sel.by_key(self.network.network_key)
        self.assertIsNotNone(result)

    def test_select_with_rate_limits(self):
        from api.postback.selectors import NetworkPostbackConfigSelector
        sel = NetworkPostbackConfigSelector()
        result = sel.with_rate_limits()
        self.assertIsNotNone(result)


class SelectorHelperFunctionTests(TestCase):

    def setUp(self):
        from api.postback.tests.factories import (
            NetworkPostbackConfigFactory, RewardedPostbackLogFactory,
        )
        self.network = NetworkPostbackConfigFactory()
        self.log = RewardedPostbackLogFactory(network=self.network)

    def test_select_postback_logs_factory(self):
        from api.postback.selectors import select_postback_logs
        sel = select_postback_logs()
        self.assertIsNotNone(sel)

    def test_select_postback_insights_factory(self):
        from api.postback.selectors import select_postback_insights
        sel = select_postback_insights()
        self.assertIsNotNone(sel)

    def test_select_network_configs_factory(self):
        from api.postback.selectors import select_network_configs
        sel = select_network_configs()
        self.assertIsNotNone(sel)

    def test_select_recent_postbacks(self):
        from api.postback.selectors import select_recent_postbacks
        result = select_recent_postbacks(days=7)
        self.assertIsInstance(result, list)

    def test_select_recent_postbacks_with_status(self):
        from api.postback.selectors import select_recent_postbacks
        result = select_recent_postbacks(days=30, status="rewarded")
        self.assertIsInstance(result, list)

    def test_select_network_performance(self):
        from api.postback.selectors import select_network_performance
        result = select_network_performance(self.network.network_key, days=7)
        self.assertIsInstance(result, dict)

    def test_select_anomaly_insights(self):
        from api.postback.selectors import select_anomaly_insights
        result = select_anomaly_insights(days=7)
        self.assertIsInstance(result, list)

    def test_select_top_networks_by_health(self):
        from api.postback.selectors import select_top_networks_by_health
        result = select_top_networks_by_health(limit=5, days=7)
        self.assertIsInstance(result, list)

    def test_selector_health_check(self):
        from api.postback.selectors import check_selector_health
        result = check_selector_health()
        self.assertIsInstance(result, dict)
        self.assertIn("status", result)
