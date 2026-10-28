# api/cms/tests/test_search.py
"""Tests for CMS full-text search."""
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


class TestSearchEngine(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()

    def test_search_empty_query(self):
        from api.cms.search import CMSSearchEngine
        result = CMSSearchEngine.search('a')  # Too short
        self.assertIn('error', result)

    def test_search_returns_structure(self):
        from api.cms.search import CMSSearchEngine
        result = CMSSearchEngine.search('test query')
        self.assertIn('results', result)
        self.assertIn('count', result)
        self.assertIn('query', result)

    def test_search_content_types_filtered(self):
        from api.cms.search import CMSSearchEngine
        result = CMSSearchEngine.search('test', content_types=['blog'])
        self.assertIn('content_types_searched', result)
        self.assertEqual(result['content_types_searched'], ['blog'])

    def test_suggest_short_query(self):
        from api.cms.search import CMSSearchEngine
        suggestions = CMSSearchEngine.suggest('a')
        self.assertEqual(suggestions, [])

    def test_suggest_returns_list(self):
        from api.cms.search import CMSSearchEngine
        suggestions = CMSSearchEngine.suggest('test')
        self.assertIsInstance(suggestions, list)

    def test_score_text(self):
        from api.cms.search import CMSSearchEngine
        score = CMSSearchEngine._score_text(
            ['python', 'django'],
            title='Python Django Tutorial',
            body='Learn Python and Django framework',
        )
        self.assertGreater(score, 0)

    def test_extract_excerpt(self):
        from api.cms.search import CMSSearchEngine
        text = 'Hello this is a test document about Python programming'
        excerpt = CMSSearchEngine._extract_excerpt(text, 'Python')
        self.assertIn('Python', excerpt)

    def test_reindex_all(self):
        from api.cms.search import CMSSearchEngine
        counts = CMSSearchEngine.reindex_all()
        self.assertIsInstance(counts, dict)

    def test_search_result_dataclass(self):
        from api.cms.search import SearchResult
        sr = SearchResult(
            id=1, title='Test', url='/test/', content_type='blog',
            excerpt='Test excerpt', score=2.5,
        )
        d = sr.to_dict()
        self.assertEqual(d['id'], 1)
        self.assertEqual(d['title'], 'Test')
        self.assertEqual(d['score'], 2.5)


class TestFeatureFlags(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()

    def test_default_flags(self):
        from api.cms.feature_flags import FeatureFlags, FLAG_OFFERWALL
        val = FeatureFlags.is_enabled(FLAG_OFFERWALL)
        self.assertIsInstance(val, bool)

    def test_enable_flag(self):
        from api.cms.feature_flags import FeatureFlags
        FeatureFlags.enable('test_custom_flag')
        val = FeatureFlags.is_enabled('test_custom_flag')
        self.assertTrue(val)

    def test_disable_flag(self):
        from api.cms.feature_flags import FeatureFlags
        FeatureFlags.disable('test_custom_flag_2')
        val = FeatureFlags.is_enabled('test_custom_flag_2')
        self.assertFalse(val)

    def test_get_all_flags(self):
        from api.cms.feature_flags import FeatureFlags
        all_flags = FeatureFlags.get_all()
        self.assertIsInstance(all_flags, dict)
        self.assertGreater(len(all_flags), 10)

    def test_require_raises_for_disabled(self):
        from api.cms.feature_flags import FeatureFlags
        from api.cms.exceptions import ServiceUnavailableError
        FeatureFlags.disable('disabled_test_feature')
        with self.assertRaises(ServiceUnavailableError):
            FeatureFlags.require('disabled_test_feature')

    def test_staff_always_has_access(self):
        from api.cms.factories import UserFactory
        from api.cms.feature_flags import FeatureFlags
        admin = UserFactory.create_admin()
        # Staff should always return True
        val = FeatureFlags._get_user_flag('any_flag', admin)
        self.assertTrue(val)
