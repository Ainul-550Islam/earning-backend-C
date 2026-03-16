# =============================================================================
# behavior_analytics/tests/test_analytics.py
# =============================================================================
"""
Unit and integration tests for the behavior_analytics application.

Test strategy:
  - Pure-logic classes (EngagementCalculator, PathAnalyzer) are tested without
    any DB access — fast, reliable unit tests.
  - Service-layer tests use Django's TestCase (DB rolled back after each test).
  - Viewset tests use DRF's APIClient.
  - Factory Boy factories (factories.py) build fixtures declaratively.
  - Every test class has a docstring explaining what it covers.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from ..analytics.engagement_calculator import (
    EngagementCalculator,
    NormalisationCaps,
    RawEngagementMetrics,
)
from ..analytics.path_analyzer import PathAnalyzer, PathNode
from ..choices import EngagementTier, SessionStatus
from ..constants import (
    ENGAGEMENT_SCORE_MAX,
    ENGAGEMENT_SCORE_MIN,
    MAX_PATH_NODES,
    STAY_TIME_BOUNCE_THRESHOLD,
)
from ..exceptions import (
    DuplicateSessionError,
    InvalidPathDataError,
    StayTimeOutOfRangeError,
)
from ..models import ClickMetric, EngagementScore, StayTime, UserPath
from ..services import (
    ClickMetricService,
    EngagementScoreService,
    StayTimeService,
    UserPathService,
    _compute_score,
)


# =============================================================================
# EngagementCalculator tests (pure unit — no DB)
# =============================================================================

class TestEngagementCalculator(TestCase):
    """Unit tests for the pure engagement score calculator."""

    def setUp(self):
        self.calc = EngagementCalculator()

    def test_zero_metrics_gives_zero_score(self):
        result = self.calc.calculate(RawEngagementMetrics())
        self.assertEqual(result.score, Decimal("0.00"))

    def test_full_metrics_gives_maximum_score(self):
        caps = NormalisationCaps()
        result = self.calc.calculate(
            RawEngagementMetrics(
                click_count=caps.clicks_cap,
                total_stay_sec=caps.stay_sec_cap,
                path_depth=caps.depth_cap,
                return_visits=caps.return_visits_cap,
            )
        )
        self.assertEqual(result.score, Decimal("100.00"))

    def test_score_clamped_to_max(self):
        """Metrics above caps should not exceed 100."""
        result = self.calc.calculate(
            RawEngagementMetrics(
                click_count=99_999,
                total_stay_sec=99_999,
                path_depth=99_999,
                return_visits=99_999,
            )
        )
        self.assertLessEqual(result.score, Decimal("100.00"))

    def test_breakdown_keys_present(self):
        result = self.calc.calculate(RawEngagementMetrics(click_count=50))
        self.assertIn("click_contribution", result.breakdown)
        self.assertIn("stay_contribution",  result.breakdown)
        self.assertIn("depth_contribution", result.breakdown)
        self.assertIn("return_contribution", result.breakdown)

    def test_invalid_metrics_raises_value_error(self):
        with self.assertRaises(ValueError):
            RawEngagementMetrics(click_count=-1)

    def test_custom_caps(self):
        caps   = NormalisationCaps(clicks_cap=10)
        calc   = EngagementCalculator(caps=caps)
        result = calc.calculate(RawEngagementMetrics(click_count=10))
        # With full click contribution only = 25 %
        self.assertEqual(result.breakdown["click_contribution"], 25.0)

    def test_batch_returns_same_length(self):
        metrics = [RawEngagementMetrics(click_count=i * 10) for i in range(5)]
        results = self.calc.calculate_batch(metrics)
        self.assertEqual(len(results), 5)


# =============================================================================
# PathAnalyzer tests (pure unit — no DB)
# =============================================================================

class TestPathAnalyzer(TestCase):
    """Unit tests for the path analysis engine."""

    def setUp(self):
        self.analyzer = PathAnalyzer()
        self.sample_nodes = [
            {"url": "/home/",     "type": "entry",      "ts": 1000},
            {"url": "/products/", "type": "navigation", "ts": 1030},
            {"url": "/product/1/","type": "navigation", "ts": 1060},
            {"url": "/cart/",     "type": "navigation", "ts": 1090},
            {"url": "/checkout/", "type": "conversion", "ts": 1120},
        ]

    def test_correct_depth(self):
        result = self.analyzer.analyse(self.sample_nodes)
        self.assertEqual(result.depth, 5)

    def test_entry_and_exit_urls(self):
        result = self.analyzer.analyse(self.sample_nodes)
        self.assertEqual(result.entry_url, "/home/")
        self.assertEqual(result.exit_url,  "/checkout/")

    def test_single_node_is_bounce(self):
        result = self.analyzer.analyse([{"url": "/home/", "type": "entry", "ts": 0}])
        self.assertTrue(result.is_bounce)

    def test_multiple_nodes_not_bounce(self):
        result = self.analyzer.analyse(self.sample_nodes)
        self.assertFalse(result.is_bounce)

    def test_empty_nodes_returns_empty_result(self):
        result = self.analyzer.analyse([])
        self.assertEqual(result.total_nodes, 0)
        self.assertTrue(result.is_bounce)

    def test_loop_detection(self):
        nodes = [
            {"url": "/home/",     "type": "entry"},
            {"url": "/products/", "type": "navigation"},
            {"url": "/home/",     "type": "navigation"},   # loop back
        ]
        result = self.analyzer.analyse(nodes)
        self.assertIn("/home/", result.loops)

    def test_error_page_detection(self):
        nodes = [
            {"url": "/home/",  "type": "entry",      "status": 200},
            {"url": "/error/", "type": "navigation", "status": 404},
        ]
        result = self.analyzer.analyse(nodes)
        self.assertIn("/error/", result.error_pages)

    def test_funnel_completion(self):
        result = self.analyzer.analyse(
            self.sample_nodes,
            funnel_steps=["/cart/", "/checkout/", "/order-confirmed/"],
        )
        self.assertTrue(result.funnel_completion["/cart/"])
        self.assertTrue(result.funnel_completion["/checkout/"])
        self.assertFalse(result.funnel_completion["/order-confirmed/"])

    def test_non_list_input_raises(self):
        from ..analytics.path_analyzer import PathAnalysisError
        with self.assertRaises(PathAnalysisError):
            self.analyzer.analyse("not-a-list")  # type: ignore[arg-type]

    def test_merge_paths_aggregate(self):
        paths = [self.sample_nodes, [{"url": "/home/", "type": "entry"}]]
        merged = self.analyzer.merge_paths(paths)
        self.assertEqual(merged["total_paths"], 2)
        self.assertEqual(merged["bounce_count"], 1)


# =============================================================================
# Model tests (DB required)
# =============================================================================

class TestUserPathModel(TestCase):
    """Tests for UserPath model methods and constraints."""

    def _make_user(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        return User.objects.create_user(
            username="testuser", email="test@example.com", password="secret"
        )

    def test_add_node_increments_list(self):
        user = self._make_user()
        path = UserPath.objects.create(
            user=user, session_id="sess-001", device_type="desktop"
        )
        path.add_node(url="/page-1/")
        self.assertEqual(len(path.nodes), 1)
        self.assertEqual(path.nodes[0]["url"], "/page-1/")

    def test_add_node_raises_at_limit(self):
        user = self._make_user()
        path = UserPath.objects.create(
            user=user, session_id="sess-limit",
            device_type="mobile",
            nodes=[{"url": f"/p/{i}/", "type": "navigation", "ts": i} for i in range(MAX_PATH_NODES)],
        )
        with self.assertRaises(InvalidPathDataError):
            path.add_node(url="/overflow/")

    def test_depth_counts_unique_urls(self):
        user = self._make_user()
        path = UserPath(
            user=user, session_id="sess-depth", device_type="desktop",
            nodes=[
                {"url": "/a/", "type": "navigation"},
                {"url": "/b/", "type": "navigation"},
                {"url": "/a/", "type": "navigation"},  # duplicate
            ],
        )
        self.assertEqual(path.depth, 2)  # /a/ and /b/

    def test_is_bounce_single_node(self):
        user = self._make_user()
        path = UserPath(
            user=user, session_id="sess-bounce", device_type="mobile",
            nodes=[{"url": "/home/", "type": "entry"}],
        )
        self.assertTrue(path.is_bounce)


class TestEngagementScoreModel(TestCase):
    """Tests for EngagementScore model validation."""

    def _make_user(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        return User.objects.create_user(
            username="enguser", email="eng@example.com", password="secret"
        )

    def test_invalid_score_raises(self):
        from ..exceptions import InvalidEngagementScoreError
        user  = self._make_user()
        score = EngagementScore(
            user=user, date=timezone.localdate(), score=Decimal("150.00")
        )
        with self.assertRaises(InvalidEngagementScoreError):
            score.clean()

    def test_valid_score_passes_clean(self):
        user  = self._make_user()
        score = EngagementScore(
            user=user, date=timezone.localdate(), score=Decimal("75.50"),
            tier=EngagementTier.HIGH,
        )
        score.clean()   # should not raise


# =============================================================================
# Service tests (DB + atomic transactions)
# =============================================================================

class TestUserPathService(TestCase):

    def setUp(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.user = User.objects.create_user(
            username="svcuser", email="svc@example.com", password="secret"
        )

    def test_create_path_success(self):
        path = UserPathService.create_path(
            user=self.user,
            session_id="test-session-01",
            device_type="desktop",
        )
        self.assertEqual(path.user, self.user)
        self.assertEqual(path.session_id, "test-session-01")
        self.assertEqual(path.status, SessionStatus.ACTIVE)

    def test_create_path_duplicate_raises(self):
        UserPathService.create_path(
            user=self.user, session_id="dup-session", device_type="mobile"
        )
        with self.assertRaises(DuplicateSessionError):
            UserPathService.create_path(
                user=self.user, session_id="dup-session", device_type="mobile"
            )

    def test_close_path(self):
        path = UserPathService.create_path(
            user=self.user, session_id="close-session", device_type="tablet"
        )
        closed = UserPathService.close_path(
            path=path, exit_url="/goodbye/", status=SessionStatus.COMPLETED
        )
        self.assertEqual(closed.status, SessionStatus.COMPLETED)
        self.assertEqual(closed.exit_url, "/goodbye/")

    def test_get_or_404_raises_on_missing(self):
        with self.assertRaises(Exception):
            UserPathService.get_or_404(user=self.user, session_id="nonexistent")


class TestComputeScore(TestCase):
    """Unit tests for the private _compute_score function."""

    def test_zero_inputs(self):
        score, breakdown = _compute_score(
            click_count=0, total_stay_sec=0, path_depth=0, return_visits=0
        )
        self.assertEqual(score, Decimal("0.00"))

    def test_score_in_valid_range(self):
        score, _ = _compute_score(
            click_count=50, total_stay_sec=1800, path_depth=10, return_visits=5
        )
        self.assertGreaterEqual(score, Decimal(str(ENGAGEMENT_SCORE_MIN)))
        self.assertLessEqual(score, Decimal(str(ENGAGEMENT_SCORE_MAX)))

    def test_breakdown_sums_to_score(self):
        score, breakdown = _compute_score(
            click_count=100, total_stay_sec=3600, path_depth=20, return_visits=10
        )
        total = sum(breakdown.values())
        self.assertAlmostEqual(total, float(score), places=1)
