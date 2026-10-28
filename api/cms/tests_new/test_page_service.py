# api/cms/tests/test_page_service.py
"""
Tests for PageService: CRUD, slug generation, publishing, versioning.
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
from django.contrib.auth import get_user_model
from django.utils import timezone
from unittest.mock import patch, MagicMock

User = get_user_model()


class TestPageServiceCreate(TestCase):
    """Test PageService.create_page"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='author', email='author@test.com', password='pass123'
        )

    @patch('cms.services_new.PageService.ContentPage')
    def test_create_page_returns_page(self, mock_model):
        from api.cms.services_new.PageService import PageService
        mock_page = MagicMock()
        mock_page.id = 1
        mock_page.title = 'Test Page'
        mock_model.objects.filter.return_value.exists.return_value = False
        mock_model.objects.create.return_value = mock_page

        with patch.object(PageService, '_generate_unique_slug', return_value='test-page'):
            result = PageService.create_page(
                title='Test Page',
                content='<p>Hello World</p>',
                author=self.user,
                status='draft'
            )
        self.assertIsNotNone(result)

    @patch('cms.services_new.PageService.ContentPage')
    def test_create_page_handles_exception(self, mock_model):
        from api.cms.services_new.PageService import PageService
        mock_model.objects.create.side_effect = Exception('DB error')
        with patch.object(PageService, '_generate_unique_slug', return_value='slug'):
            result = PageService.create_page(title='X', content='Y', author=self.user)
        self.assertIsNone(result)


class TestPageServiceSlug(TestCase):
    """Test PageService._generate_unique_slug"""

    @patch('cms.services_new.PageService.ContentPage')
    def test_slug_uniqueness(self, mock_model):
        from api.cms.services_new.PageService import PageService
        mock_model.objects.filter.return_value.exists.side_effect = [True, True, False]
        slug = PageService._generate_unique_slug('My Page')
        self.assertIn('my-page', slug)

    @patch('cms.services_new.PageService.ContentPage')
    def test_slug_from_title(self, mock_model):
        from api.cms.services_new.PageService import PageService
        mock_model.objects.filter.return_value.exists.return_value = False
        slug = PageService._generate_unique_slug('Hello World Page')
        self.assertEqual(slug, 'hello-world-page')

    @patch('cms.services_new.PageService.ContentPage')
    def test_empty_title_gets_default(self, mock_model):
        from api.cms.services_new.PageService import PageService
        mock_model.objects.filter.return_value.exists.return_value = False
        slug = PageService._generate_unique_slug('')
        self.assertTrue(len(slug) > 0)


class TestPageServicePublish(TestCase):
    """Test PageService publish/unpublish"""

    def test_publish_sets_status(self):
        from api.cms.services_new.PageService import PageService
        mock_page = MagicMock()
        mock_page.id = 1
        mock_page.title = 'My Page'
        mock_page.slug = 'my-page'
        mock_page.uuid = 'uuid-1234'

        with patch('cms.services_new.PageService.ContentPage') as mock_model:
            mock_model.objects.filter.return_value.update.return_value = 1
            result = PageService.publish_page(mock_page)

        self.assertTrue(result)
        self.assertEqual(mock_page.status, 'published')

    def test_unpublish_sets_draft(self):
        from api.cms.services_new.PageService import PageService
        mock_page = MagicMock()
        mock_page.id = 1
        mock_page.slug = 'my-page'
        result = PageService.unpublish_page(mock_page)
        self.assertTrue(result)
        self.assertEqual(mock_page.status, 'draft')

    def test_schedule_sets_scheduled_status(self):
        from api.cms.services_new.PageService import PageService
        mock_page = MagicMock()
        future = timezone.now() + timezone.timedelta(days=1)
        result = PageService.schedule_page(mock_page, scheduled_date=future)
        self.assertTrue(result)
        self.assertEqual(mock_page.status, 'scheduled')

    def test_schedule_past_date_fails(self):
        from api.cms.services_new.PageService import PageService
        mock_page = MagicMock()
        past = timezone.now() - timezone.timedelta(days=1)
        result = PageService.schedule_page(mock_page, scheduled_date=past)
        self.assertFalse(result)


class TestPageServiceVisibility(TestCase):
    """Test PageService._can_view"""

    def setUp(self):
        self.user = MagicMock()
        self.user.is_authenticated = True
        self.user.is_staff = False

    def test_public_published_page_visible(self):
        from api.cms.services_new.PageService import PageService
        page = MagicMock()
        page.is_active = True
        page.status = 'published'
        page.visibility = 'public'
        self.assertTrue(PageService._can_view(page, None))

    def test_authenticated_page_requires_login(self):
        from api.cms.services_new.PageService import PageService
        page = MagicMock()
        page.is_active = True
        page.status = 'published'
        page.visibility = 'authenticated'
        self.assertFalse(PageService._can_view(page, None))
        self.assertTrue(PageService._can_view(page, self.user))

    def test_inactive_page_not_visible(self):
        from api.cms.services_new.PageService import PageService
        page = MagicMock()
        page.is_active = False
        page.status = 'published'
        page.visibility = 'public'
        self.assertFalse(PageService._can_view(page, None))

    def test_staff_can_view_any(self):
        from api.cms.services_new.PageService import PageService
        page = MagicMock()
        page.is_active = True
        page.status = 'draft'
        page.visibility = 'admin'
        staff_user = MagicMock()
        staff_user.is_staff = True
        staff_user.is_authenticated = True
        self.assertTrue(PageService._can_view(page, staff_user))
