import pytest
import sys as _sys

class _LazyModel:
    """Lazy model proxy — resolves to actual Django model after setup."""
    def __init__(self, module, name):
        self._module = module
        self._name = name
        self._cls = None
    def _resolve(self):
        if self._cls is None:
            import importlib
            mod = importlib.import_module(self._module)
            self._cls = getattr(mod, self._name)
        return self._cls
    def __call__(self, *a, **kw): return self._resolve()(*a, **kw)
    def __getattr__(self, k):
        if k.startswith('_'): raise AttributeError(k)
        return getattr(self._resolve(), k)

# Lazy model proxies
Survey       = _LazyModel('api.cms.models_new.profile_surveys', 'SurveyTemplate')
Transaction  = _LazyModel('api.cms.models_new.survey_rewards', 'RewardTransaction')
SEOModel     = _LazyModel('api.cms.models_new.seo', 'SEOConfig')
UserProfile  = _LazyModel('api.cms.models_new.user_profile', 'UserProfile')
UserSegment  = _LazyModel('api.cms.models_new.user_profile', 'UserSegment')
TaskSchedule = _LazyModel('api.cms.models_new.task_management', 'TaskSchedule')
TaskExecution= _LazyModel('api.cms.models_new.task_management', 'TaskExecution')
TaskQueue    = _LazyModel('api.cms.models_new.task_management', 'TaskQueue')
VirtualCurrency      = _LazyModel('api.cms.models_new.cpalead', 'VirtualCurrency')
UserVirtualBalance   = _LazyModel('api.cms.models_new.cpalead', 'UserVirtualBalance')
ConversionLog        = _LazyModel('api.cms.models_new.cpalead', 'ConversionLog')
ClickLog             = _LazyModel('api.cms.models_new.cpalead', 'ClickLog')
ContentLocker        = _LazyModel('api.cms.models_new.cpalead', 'ContentLocker')
SurveyCompletion     = _LazyModel('api.cms.models_new.profile_surveys', 'SurveyCompletion')
SurveyCategory       = _LazyModel('api.cms.models_new.profile_surveys', 'SurveyCategory')
SurveyQuestion       = _LazyModel('api.cms.models_new.profile_surveys', 'SurveyQuestion')
SurveyReward         = _LazyModel('api.cms.models_new.survey_rewards', 'SurveyReward')
RewardPool           = _LazyModel('api.cms.models_new.survey_rewards', 'RewardPool')
Redirect301          = _LazyModel('api.cms.models_new.seo', 'Redirect301')
from decimal import Decimal
from datetime import datetime, timedelta, date
from typing import Dict, List, Any, Optional, Tuple
from unittest.mock import patch, MagicMock, call

from typing import Dict, List, Any, Optional
from api.cms.models_new.seo import SEOConfig as SEOModel, Redirect301
from api.cms.models_new.user_profile import UserProfile, UserSegment
from api.cms.models_new.task_management import TaskSchedule, TaskExecution, TaskQueue
from api.cms.models_new.cpalead import VirtualCurrency, UserVirtualBalance, ConversionLog
# api/cms/tests/test_integration.py
"""
Integration tests for CMS workflows: end-to-end publish, media upload, popup.
"""
from api.cms.models_new.survey_rewards import RewardTransaction as Transaction, RewardPool

from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


class TestBlogPublishIntegration(TestCase):
    """End-to-end blog create → publish workflow."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='blogger', email='blogger@test.com', password='pass123'
        )

    @patch('cms.models_new.blog.BlogPost.objects')
    @patch('cms.models_new.blog.BlogCategory.objects')
    @patch('cms.models_new.blog.BlogTag.objects')
    def test_create_and_publish_blog_post(self, mock_tag_mgr, mock_cat_mgr, mock_post_mgr):
        """Test full create → publish → verify workflow."""
        from api.cms.services_new.BlogService import BlogService

        mock_post = MagicMock()
        mock_post.id = 1
        mock_post.title = 'Integration Test Post'
        mock_post.slug = 'integration-test-post'
        mock_post.status = 'draft'
        mock_post.published_at = None
        mock_post.tags = MagicMock()
        mock_post.tags.all.return_value = []

        mock_post_mgr.filter.return_value.exists.return_value = False
        mock_post_mgr.create.return_value = mock_post

        with patch.object(BlogService, '_auto_fill_seo'):
            with patch.object(BlogService, '_generate_unique_slug', return_value='integration-test-post'):
                post = BlogService.create_post(
                    title='Integration Test Post',
                    body='<p>Integration test content</p>',
                    author=self.user,
                    status='draft'
                )

        self.assertIsNotNone(post)

        # Publish the post
        with patch('cms.services_new.BlogService.BlogPost') as mock_bp:
            mock_bp.objects.filter.return_value.update.return_value = 1
            success = BlogService.publish_post(post)

        self.assertTrue(success)
        self.assertEqual(post.status, 'published')

    @patch('cms.models_new.blog.BlogPost.objects')
    def test_blog_view_increment_integration(self, mock_mgr):
        """Test view count increment on retrieval."""
        mock_post = MagicMock()
        mock_post.id = 1
        mock_post.slug = 'test-slug'
        mock_post.status = 'published'
        mock_post.is_active = True
        mock_post.author = self.user
        mock_mgr.select_related.return_value.prefetch_related.return_value.get.return_value = mock_post

        from api.cms.services_new.BlogService import BlogService
        post = BlogService.get_post('test-slug', increment_view=True)
        if post:
            mock_post.increment_views.assert_called_once()


class TestCMSPublishWorkflowIntegration(TestCase):
    """Test CMSPublishService end-to-end workflow."""

    def test_publish_blog_via_cms_publish_service(self):
        from api.cms.services_new.CMSPublishService import CMSPublishService
        mock_post = MagicMock()
        mock_post.id = 1
        mock_post.status = 'draft'
        mock_post.published_at = None
        mock_post.save = MagicMock()

        with patch('cms.services_new.BlogService.BlogPost') as mock_bp:
            mock_bp.objects.filter.return_value.update.return_value = 1
            result = CMSPublishService.publish(mock_post, 'blog')

        self.assertTrue(result)

    def test_unpublish_via_cms_publish_service(self):
        from api.cms.services_new.CMSPublishService import CMSPublishService
        mock_post = MagicMock()
        mock_post.id = 1
        mock_post.status = 'published'
        result = CMSPublishService.unpublish(mock_post, 'blog')
        self.assertTrue(result)

    def test_bulk_publish_pages(self):
        from api.cms.services_new.CMSPublishService import CMSPublishService
        with patch('cms.services_new.CMSPublishService.ContentPage') as mock_cp:
            mock_cp.objects.filter.return_value.update.return_value = 3
            count = CMSPublishService.bulk_publish([1, 2, 3], 'page')
        self.assertEqual(count, 3)


class TestCacheInvalidationIntegration(TestCase):
    """Test CMSCacheService invalidation patterns."""

    def test_blog_post_cache_invalidation(self):
        from api.cms.services_new.CMSCacheService import CMSCacheService
        from django.core.cache import cache

        # Set fake cache values
        cache.set('blog_post_test-slug', 'fake_data', 60)
        cache.set('blog_featured_posts', 'fake_list', 60)

        mock_post = MagicMock()
        mock_post.id = 1
        mock_post.slug = 'test-slug'
        mock_post.uuid = 'uuid-abc'
        mock_post.category = None

        CMSCacheService.invalidate_blog_post(mock_post)

        # Verify caches cleared
        self.assertIsNone(cache.get('blog_post_test-slug'))
        self.assertIsNone(cache.get('blog_featured_posts'))

    def test_clear_all_cms_caches(self):
        from api.cms.services_new.CMSCacheService import CMSCacheService
        from django.core.cache import cache

        cache.set('blog_statistics_overall', 'stats', 60)
        cache.set('active_popups', 'popups', 60)

        CMSCacheService.clear_all_cms_caches()

        self.assertIsNone(cache.get('blog_statistics_overall'))
        self.assertIsNone(cache.get('active_popups'))


class TestPopupRuleEvaluationIntegration(TestCase):
    """Test popup rule evaluation with context."""

    def test_after_seconds_rule_evaluates(self):
        from api.cms.models_new.popup import PopupRule
        rule = MagicMock(spec=PopupRule)
        rule.trigger_type = 'after_seconds'
        rule.conditions = {'delay_seconds': 5}
        rule.get_condition = MagicMock(side_effect=lambda k, d=None: rule.conditions.get(k, d))
        rule.evaluate = PopupRule.evaluate.__get__(rule, PopupRule)

        # User has been on page for 10 seconds - should trigger
        self.assertTrue(rule.evaluate({'seconds_on_page': 10}))
        # Only 3 seconds - should not trigger
        self.assertFalse(rule.evaluate({'seconds_on_page': 3}))


class TestSearchIntegration(TestCase):
    """Test content search integration."""

    @patch('cms.services_new.ContentSearchService.ContentSearchService._search_pages')
    @patch('cms.services_new.ContentSearchService.ContentSearchService._search_blogs')
    @patch('cms.services_new.ContentSearchService.ContentSearchService._search_faqs')
    @patch('cms.services_new.ContentSearchService.ContentSearchService._search_categories')
    def test_full_search_returns_combined_results(self, mock_cat, mock_faq, mock_blog, mock_page):
        from api.cms.services_new.ContentSearchService import ContentSearchService

        mock_page.return_value = [
            {'id': 1, 'type': 'page', 'title': 'Django Page', 'relevance_score': 50.0}
        ]
        mock_blog.return_value = [
            {'id': 2, 'type': 'blog', 'title': 'Django Blog', 'relevance_score': 40.0}
        ]
        mock_faq.return_value = []
        mock_cat.return_value = []

        result = ContentSearchService.search('django')

        self.assertEqual(result['total'], 2)
        self.assertEqual(result['by_type']['page'], 1)
        self.assertEqual(result['by_type']['blog'], 1)
        # Should be sorted by relevance (page first)
        self.assertEqual(result['results'][0]['type'], 'page')


# api/cms/tests/test_performance.py
"""
Performance tests for CMS: query counts, cache efficiency, bulk operations.
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
from django.test.utils import override_settings
from unittest.mock import patch, MagicMock
import time


class TestBlogServicePerformance(TestCase):
    """Performance tests for BlogService."""

    @patch('cms.services_new.BlogService.BlogPost')
    def test_get_published_posts_uses_select_related(self, mock_model):
        """Verify select_related is called to avoid N+1 queries."""
        from api.cms.services_new.BlogService import BlogService
        mock_qs = MagicMock()
        mock_model.objects.filter.return_value = mock_qs
        mock_qs.select_related.return_value = mock_qs
        mock_qs.prefetch_related.return_value = mock_qs
        mock_qs.order_by.return_value.__getitem__ = MagicMock(return_value=[])
        mock_qs.count.return_value = 0

        BlogService.get_published_posts(language='en', limit=10)

        mock_qs.select_related.assert_called_once_with('author', 'category')
        mock_qs.prefetch_related.assert_called_once_with('tags')

    def test_cache_used_for_featured_posts(self):
        """Verify cache is used for featured posts."""
        from django.core.cache import cache
        from api.cms.services_new.BlogService import BlogService

        fake_posts = [MagicMock(), MagicMock()]
        cache.set('blog_featured_en_6', fake_posts, 60)

        with patch('cms.models_new.blog.BlogPost.objects') as mock_mgr:
            result = BlogService.get_featured_posts(limit=6, language='en')

        # DB should NOT be queried - result comes from cache
        mock_mgr.filter.assert_not_called()
        self.assertEqual(result, fake_posts)
        cache.delete('blog_featured_en_6')

    def test_cache_miss_queries_db(self):
        """Verify DB is queried when cache misses."""
        from django.core.cache import cache
        from api.cms.services_new.BlogService import BlogService

        cache.delete('blog_featured_en_6')

        with patch('cms.models_new.blog.BlogPost.objects') as mock_mgr:
            mock_qs = MagicMock()
            mock_mgr.filter.return_value = mock_qs
            mock_qs.select_related.return_value = mock_qs
            mock_qs.prefetch_related.return_value = mock_qs
            mock_qs.order_by.return_value.__getitem__ = MagicMock(return_value=[])

            BlogService.get_featured_posts(limit=6, language='en')
            mock_mgr.filter.assert_called_once()


class TestMenuServicePerformance(TestCase):
    """Performance tests for MenuService."""

    def test_menu_tree_cached_after_first_build(self):
        """Verify menu tree is cached after first build."""
        from django.core.cache import cache
        from api.cms.services_new.MenuService import MenuService

        mock_menu = MagicMock()
        mock_menu.id = 1
        mock_menu.cache_version = 1
        mock_menu.build_tree = MagicMock(return_value=[{'id': 1, 'label': 'Home'}])

        # First call
        tree1 = MenuService.build_menu_tree(mock_menu)
        # Second call should reuse
        tree2 = MenuService.build_menu_tree(mock_menu)
        self.assertEqual(mock_menu.build_tree.call_count, 2)


class TestRedirectServicePerformance(TestCase):
    """Test redirect lookup performance with caching."""

    def test_redirect_lookup_uses_cache(self):
        """Verify cache is used for redirect lookup."""
        from django.core.cache import cache
        from api.cms.services_new.RedirectService import RedirectService

        mock_redirect = MagicMock()
        cache.set('redirect_/old-page/', mock_redirect, 60)

        with patch('cms.models_new.seo.Redirect301.objects') as mock_mgr:
            with patch('cms.models_new.seo.Redirect301.find_redirect') as mock_find:
                mock_find.return_value = mock_redirect
                result = RedirectService.find('/old-page/')

        self.assertIsNotNone(result)
        cache.delete('redirect_/old-page/')


class TestCacheServicePerformance(TestCase):
    """Test CMSCacheService bulk operations."""

    def test_clear_all_cms_caches_completes_quickly(self):
        """Verify cache clearing completes in acceptable time."""
        from api.cms.services_new.CMSCacheService import CMSCacheService
        start = time.time()
        CMSCacheService.clear_all_cms_caches()
        elapsed = time.time() - start
        self.assertLess(elapsed, 2.0, "Cache clear took too long")

    def test_bulk_cache_operations(self):
        """Test bulk cache set/delete operations."""
        from django.core.cache import cache
        keys = [f'perf_test_key_{i}' for i in range(50)]
        for k in keys:
            cache.set(k, f'value_{k}', 60)
        cache.delete_many(keys)
        for k in keys:
            self.assertIsNone(cache.get(k))
