# api/cms/tests/test_analytics.py
"""Tests for Analytics system."""
from django.test import TestCase
from decimal import Decimal
from datetime import datetime, timedelta, date
from typing import Dict, List, Any, Optional, Tuple
from unittest.mock import patch, MagicMock, call
try:
    from api.cms.models_new.profile_surveys import (
        SurveyTemplate as Survey, SurveyCompletion, SurveyCategory, SurveyQuestion
    )
    from api.cms.models_new.survey_rewards import (
        SurveyReward, RewardTransaction as Transaction, RewardPool
    )
    from api.cms.models_new.seo import SEOConfig as SEOModel, Redirect301
    from api.cms.models_new.user_profile import UserProfile, UserSegment
    from api.cms.models_new.task_management import TaskSchedule, TaskExecution
    from api.cms.models_new.cpalead import (
        VirtualCurrency, UserVirtualBalance, ConversionLog, ClickLog, ContentLocker
    )
except Exception:
    pass


class TestRevenueAnalytics(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()

    def test_get_summary_empty(self):
        from api.cms.analytics import RevenueAnalytics
        summary = RevenueAnalytics.get_summary(days=30)
        self.assertIn('total_conversions', summary)
        self.assertIn('total_revenue_usd', summary)
        self.assertEqual(summary['total_conversions'], 0)

    def test_get_daily_revenue_empty(self):
        from api.cms.analytics import RevenueAnalytics
        daily = RevenueAnalytics.get_daily_revenue(days=7)
        self.assertIsInstance(daily, list)

    def test_full_dashboard(self):
        from api.cms.analytics import CMSAnalyticsDashboard
        dashboard = CMSAnalyticsDashboard.get_full_dashboard(days=7)
        self.assertIn('revenue', dashboard)
        self.assertIn('users', dashboard)
        self.assertIn('content', dashboard)

    def test_user_analytics_summary(self):
        from api.cms.analytics import UserAnalytics
        summary = UserAnalytics.get_summary(days=30)
        self.assertIn('total_users', summary)
        self.assertIn('active_users_period', summary)

    def test_content_analytics(self):
        from api.cms.analytics import ContentAnalytics
        quiz_stats = ContentAnalytics.get_quiz_stats(30)
        self.assertIn('total_quizzes', quiz_stats)

    def test_withdrawal_analytics(self):
        from api.cms.analytics import WithdrawalAnalytics
        summary = WithdrawalAnalytics.get_summary(days=30)
        self.assertIn('total_requests', summary)


class TestMonitoring(TestCase):
    def test_increment_metric(self):
        from api.cms.monitoring import CMSMetrics
        CMSMetrics.increment('test_metric', 5)
        val = CMSMetrics.get('test_metric')
        self.assertGreaterEqual(val, 5)

    def test_record_postback_metrics(self):
        from api.cms.monitoring import CMSMetrics
        CMSMetrics.record_postback(success=True, payout_usd=0.50)
        total = CMSMetrics.get('postback_total')
        self.assertGreaterEqual(total, 1)

    def test_sla_within_limit(self):
        from api.cms.monitoring import SLAMonitor
        within = SLAMonitor.check_sla('cpalead_postback', 150)
        self.assertTrue(within)

    def test_sla_breach(self):
        from api.cms.monitoring import SLAMonitor
        within = SLAMonitor.check_sla('cpalead_postback', 500)
        self.assertFalse(within)

    def test_performance_tracker(self):
        from api.cms.monitoring import PerformanceTracker
        import time
        with PerformanceTracker('test_operation') as tracker:
            time.sleep(0.01)
        self.assertGreater(tracker.elapsed_ms, 0)


class TestCaching(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()

    def test_cache_set_get(self):
        from api.cms.caching import CMSCache, NS_BLOG
        CMSCache.set(NS_BLOG, 'post', '1', {'title': 'Test'}, ttl=60)
        val = CMSCache.get(NS_BLOG, 'post', '1')
        self.assertEqual(val, {'title': 'Test'})

    def test_cache_delete(self):
        from api.cms.caching import CMSCache, NS_BLOG
        CMSCache.set(NS_BLOG, 'post', '99', 'value', ttl=60)
        CMSCache.delete(NS_BLOG, 'post', '99')
        val = CMSCache.get(NS_BLOG, 'post', '99')
        self.assertIsNone(val)

    def test_cache_key_namespaced(self):
        from api.cms.caching import CMSCache, NS_USER_BALANCE
        key1 = CMSCache.key(NS_USER_BALANCE, 1)
        key2 = CMSCache.key(NS_USER_BALANCE, 2)
        self.assertNotEqual(key1, key2)
        self.assertIn(NS_USER_BALANCE, key1)

    def test_cache_get_stats(self):
        from api.cms.caching import CMSCache
        stats = CMSCache.get_stats()
        self.assertIn('status', stats)
        self.assertEqual(stats['status'], 'healthy')
