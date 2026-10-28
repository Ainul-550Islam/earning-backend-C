# api/cms/tests/test_versioning.py
"""
Tests for VersioningService: snapshot, diff, restore.
"""
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
from django.utils import timezone


class TestVersioningSnapshot(TestCase):
    """Test VersioningService.take_snapshot"""

    def test_snapshot_returns_dict(self):
        from api.cms.services_new.VersioningService import VersioningService
        obj = MagicMock()
        obj.id = 1
        obj.version = 2
        obj.title = 'Test Page'
        obj.slug = 'test-page'
        obj.content = '<p>Hello</p>'
        obj.excerpt = 'Excerpt'
        obj.status = 'published'
        obj.meta_title = 'SEO Title'
        obj.meta_description = 'SEO Desc'
        obj.meta_keywords = 'key1,key2'
        obj.tags = ['tag1']
        obj.page_type = 'static'
        obj.visibility = 'public'
        obj.is_featured = False
        obj.subtitle = ''

        snapshot = VersioningService.take_snapshot(obj, 'page')
        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot['id'], 1)
        self.assertEqual(snapshot['version'], 2)
        self.assertIn('data', snapshot)

    def test_snapshot_includes_versioned_fields(self):
        from api.cms.services_new.VersioningService import VersioningService
        obj = MagicMock(spec=[
            'id', 'version', 'title', 'slug', 'content', 'excerpt',
            'status', 'meta_title', 'meta_description', 'meta_keywords',
            'tags', 'page_type', 'visibility', 'is_featured', 'subtitle'
        ])
        obj.id = 1
        obj.version = 1
        snapshot = VersioningService.take_snapshot(obj, 'page')
        self.assertIn('data', snapshot)

    def test_snapshot_handles_exception(self):
        from api.cms.services_new.VersioningService import VersioningService
        result = VersioningService.take_snapshot(None, 'page')
        self.assertIsNone(result)


class TestVersioningDiff(TestCase):
    """Test VersioningService.diff_versions"""

    def test_diff_detects_changes(self):
        from api.cms.services_new.VersioningService import VersioningService
        snap_a = {'version': 1, 'data': {'title': 'Old Title', 'status': 'draft'}}
        snap_b = {'version': 2, 'data': {'title': 'New Title', 'status': 'published'}}
        diff = VersioningService.diff_versions(snap_a, snap_b)
        self.assertEqual(diff['total_changes'], 2)
        self.assertIn('title', diff['changes'])
        self.assertIn('status', diff['changes'])
        self.assertEqual(diff['changes']['title']['old'], 'Old Title')
        self.assertEqual(diff['changes']['title']['new'], 'New Title')

    def test_diff_no_changes(self):
        from api.cms.services_new.VersioningService import VersioningService
        snap_a = {'version': 1, 'data': {'title': 'Same', 'status': 'draft'}}
        snap_b = {'version': 2, 'data': {'title': 'Same', 'status': 'draft'}}
        diff = VersioningService.diff_versions(snap_a, snap_b)
        self.assertEqual(diff['total_changes'], 0)

    def test_diff_new_field_added(self):
        from api.cms.services_new.VersioningService import VersioningService
        snap_a = {'version': 1, 'data': {'title': 'T'}}
        snap_b = {'version': 2, 'data': {'title': 'T', 'new_field': 'value'}}
        diff = VersioningService.diff_versions(snap_a, snap_b)
        self.assertIn('new_field', diff['changes'])


class TestVersioningRestore(TestCase):
    """Test VersioningService.restore_blog_version"""

    def test_restore_from_snapshot(self):
        from api.cms.services_new.VersioningService import VersioningService
        post = MagicMock()
        post.id = 1
        post.version = 3
        post.title = 'Current Title'
        post.save = MagicMock()

        snapshot = {
            'version': 1,
            'data': {'title': 'Old Title', 'excerpt': 'Old excerpt', 'status': 'draft'}
        }
        result = VersioningService.restore_blog_version(post, snapshot)
        self.assertTrue(result)
        self.assertEqual(post.title, 'Old Title')
        self.assertEqual(post.excerpt, 'Old excerpt')

    def test_restore_increments_version(self):
        from api.cms.services_new.VersioningService import VersioningService
        post = MagicMock()
        post.id = 1
        post.version = 2
        post.save = MagicMock()
        snapshot = {'version': 1, 'data': {'title': 'T'}}
        VersioningService.restore_blog_version(post, snapshot)
        self.assertEqual(post.version, 3)


# api/cms/tests/test_search.py
"""
Tests for ContentSearchService: search, scoring, suggestions.
"""
from django.test import TestCase


class TestContentSearchServiceSearch(TestCase):
    """Test ContentSearchService.search"""

    def test_empty_query_returns_empty(self):
        from api.cms.services_new.ContentSearchService import ContentSearchService
        result = ContentSearchService.search('')
        self.assertEqual(result['results'], [])
        self.assertEqual(result['total'], 0)

    def test_short_query_returns_empty(self):
        from api.cms.services_new.ContentSearchService import ContentSearchService
        result = ContentSearchService.search('a')
        self.assertEqual(result['results'], [])

    @patch('cms.services_new.ContentSearchService.ContentSearchService._search_pages')
    @patch('cms.services_new.ContentSearchService.ContentSearchService._search_blogs')
    @patch('cms.services_new.ContentSearchService.ContentSearchService._search_faqs')
    @patch('cms.services_new.ContentSearchService.ContentSearchService._search_categories')
    def test_search_calls_all_types(self, mock_cat, mock_faq, mock_blog, mock_page):
        from api.cms.services_new.ContentSearchService import ContentSearchService
        mock_page.return_value = []
        mock_blog.return_value = []
        mock_faq.return_value = []
        mock_cat.return_value = []

        result = ContentSearchService.search('django', content_types=None)
        mock_page.assert_called_once()
        mock_blog.assert_called_once()
        mock_faq.assert_called_once()
        mock_cat.assert_called_once()

    @patch('cms.services_new.ContentSearchService.ContentSearchService._search_pages')
    def test_search_type_filter(self, mock_page):
        from api.cms.services_new.ContentSearchService import ContentSearchService
        mock_page.return_value = [{'type': 'page', 'title': 'T', 'relevance_score': 50.0}]
        result = ContentSearchService.search('django', content_types=['page'])
        self.assertEqual(result['by_type']['page'], 1)
        mock_page.assert_called_once()


class TestContentSearchServiceScoring(TestCase):
    """Test ContentSearchService._score"""

    def test_exact_title_match_high_score(self):
        from api.cms.services_new.ContentSearchService import ContentSearchService
        score = ContentSearchService._score('Django Tutorial', '', 'django')
        self.assertGreater(score, 40)

    def test_partial_title_match_lower_score(self):
        from api.cms.services_new.ContentSearchService import ContentSearchService
        score = ContentSearchService._score('Python Guide', '', 'django')
        self.assertEqual(score, 0)

    def test_excerpt_match_adds_score(self):
        from api.cms.services_new.ContentSearchService import ContentSearchService
        score = ContentSearchService._score('Title', 'This is about django', 'django')
        self.assertGreater(score, 0)


class TestContentSearchSuggest(TestCase):
    """Test ContentSearchService.suggest"""

    def test_short_query_returns_empty(self):
        from api.cms.services_new.ContentSearchService import ContentSearchService
        result = ContentSearchService.suggest('a')
        self.assertEqual(result, [])

    def test_empty_query_returns_empty(self):
        from api.cms.services_new.ContentSearchService import ContentSearchService
        result = ContentSearchService.suggest('')
        self.assertEqual(result, [])


# api/cms/tests/test_redirect.py
"""
Tests for RedirectService: create, find, cleanup.
"""
from django.test import TestCase
from unittest.mock import patch, MagicMock


class TestRedirectServiceCreate(TestCase):
    """Test RedirectService.create"""

    @patch('cms.services_new.RedirectService.Redirect301')
    def test_create_redirect(self, mock_model):
        from api.cms.services_new.RedirectService import RedirectService
        mock_redirect = MagicMock()
        mock_model.objects.update_or_create.return_value = (mock_redirect, True)

        result = RedirectService.create('/old/', '/new/', redirect_type=301)
        self.assertIsNotNone(result)
        mock_model.objects.update_or_create.assert_called_once()

    @patch('cms.services_new.RedirectService.Redirect301')
    def test_create_handles_exception(self, mock_model):
        from api.cms.services_new.RedirectService import RedirectService
        mock_model.objects.update_or_create.side_effect = Exception('DB error')
        result = RedirectService.create('/old/', '/new/')
        self.assertIsNone(result)


class TestRedirectServiceFind(TestCase):
    """Test RedirectService.find"""

    @patch('cms.services_new.RedirectService.Redirect301')
    def test_find_existing_redirect(self, mock_model):
        from api.cms.services_new.RedirectService import RedirectService
        mock_redirect = MagicMock()
        mock_model.find_redirect.return_value = mock_redirect

        result = RedirectService.find('/old-page/')
        self.assertEqual(result, mock_redirect)

    @patch('cms.services_new.RedirectService.Redirect301')
    def test_find_returns_none_for_missing(self, mock_model):
        from api.cms.services_new.RedirectService import RedirectService
        mock_model.find_redirect.return_value = None
        result = RedirectService.find('/nonexistent/')
        self.assertIsNone(result)


class TestRedirectServiceCleanup(TestCase):
    """Test RedirectService.cleanup_unused and cleanup_expired"""

    @patch('cms.services_new.RedirectService.Redirect301')
    def test_cleanup_unused(self, mock_model):
        from api.cms.services_new.RedirectService import RedirectService
        mock_model.objects.filter.return_value.delete.return_value = (5, {})
        count = RedirectService.cleanup_unused(days=90)
        self.assertEqual(count, 5)

    @patch('cms.services_new.RedirectService.Redirect301')
    def test_cleanup_expired(self, mock_model):
        from api.cms.services_new.RedirectService import RedirectService
        mock_model.objects.filter.return_value.update.return_value = 3
        count = RedirectService.cleanup_expired()
        self.assertEqual(count, 3)


class TestRedirectServiceStats(TestCase):
    """Test RedirectService.get_statistics"""

    @patch('cms.services_new.RedirectService.Redirect301')
    def test_statistics_returns_dict(self, mock_model):
        from api.cms.services_new.RedirectService import RedirectService
        mock_model.objects.filter.return_value.aggregate.return_value = {
            'total': 10, 'total_hits': 500, 'avg_hits': 50.0
        }
        mock_model.objects.filter.return_value.order_by.return_value.__getitem__ = MagicMock(return_value=[])
        mock_model.objects.filter.return_value.order_by.return_value.values.return_value = []
        result = RedirectService.get_statistics()
        self.assertIsInstance(result, dict)
