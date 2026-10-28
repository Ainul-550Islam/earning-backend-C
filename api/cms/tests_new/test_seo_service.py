# api/cms/tests_new/test_seo_service.py
"""Tests for SEOService, Sitemap, Redirect301, RobotsConfig."""

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

User = get_user_model()


class TestSEOService(TestCase):

    def test_get_seo_config_returns_none_when_none(self):
        from api.cms.services_new.SEOService import SEOService
        config = SEOService.get_seo_config()
        self.assertIsNone(config)

    def test_update_creates_config(self):
        from api.cms.services_new.SEOService import SEOService
        success = SEOService.update_seo_config({
            'site_name': 'Test Site',
            'default_title': 'Default Title',
            'google_analytics_id': 'G-12345',
        })
        self.assertTrue(success)
        config = SEOService.get_seo_config()
        self.assertIsNotNone(config)
        self.assertEqual(config.site_name, 'Test Site')

    def test_get_robots_txt_default(self):
        from api.cms.services_new.SEOService import SEOService
        robots = SEOService.get_robots_txt()
        self.assertIn('User-agent', robots)

    def test_update_robots_config(self):
        from api.cms.services_new.SEOService import SEOService
        success = SEOService.update_robots_config({
            'name': 'Test Robots',
            'disallow_rules': ['/admin/', '/private/'],
            'allow_rules': ['/public/'],
        })
        self.assertTrue(success)
        robots = SEOService.get_robots_txt()
        self.assertIn('/admin/', robots)
        self.assertIn('/public/', robots)

    def test_add_url_to_sitemap(self):
        from api.cms.services_new.SEOService import SEOService
        from api.cms.models_new.seo import Sitemap
        entry = SEOService.add_url_to_sitemap(
            url='https://example.com/test/',
            changefreq='daily',
            priority=0.8
        )
        self.assertIsNotNone(entry)
        self.assertTrue(Sitemap.objects.filter(url='https://example.com/test/').exists())

    def test_remove_url_from_sitemap(self):
        from api.cms.services_new.SEOService import SEOService
        from api.cms.models_new.seo import Sitemap
        SEOService.add_url_to_sitemap(url='https://example.com/remove/')
        SEOService.remove_url_from_sitemap('https://example.com/remove/')
        entry = Sitemap.objects.get(url='https://example.com/remove/')
        self.assertFalse(entry.is_active)

    def test_get_sitemap_xml(self):
        from api.cms.services_new.SEOService import SEOService
        SEOService.add_url_to_sitemap('https://example.com/xml-test/', priority=0.9)
        xml = SEOService.get_sitemap_xml()
        self.assertIn('<?xml', xml)
        self.assertIn('<urlset', xml)
        self.assertIn('https://example.com/xml-test/', xml)

    def test_get_seo_statistics(self):
        from api.cms.services_new.SEOService import SEOService
        stats = SEOService.get_seo_statistics()
        self.assertIn('sitemap_entries', stats)
        self.assertIn('active_redirects', stats)


class TestRedirectService(TestCase):

    def test_create_redirect(self):
        from api.cms.services_new.RedirectService import RedirectService
        redirect = RedirectService.create('/old-url/', '/new-url/', redirect_type=301)
        self.assertIsNotNone(redirect)
        self.assertEqual(redirect.from_url, '/old-url/')
        self.assertEqual(redirect.to_url, '/new-url/')
        self.assertEqual(redirect.redirect_type, 301)

    def test_find_redirect(self):
        from api.cms.services_new.RedirectService import RedirectService
        RedirectService.create('/find-me/', '/found-here/')
        found = RedirectService.find('/find-me/')
        self.assertIsNotNone(found)
        self.assertEqual(found.to_url, '/found-here/')

    def test_find_nonexistent_redirect(self):
        from api.cms.services_new.RedirectService import RedirectService
        result = RedirectService.find('/not-exists/')
        self.assertIsNone(result)

    def test_delete_redirect(self):
        from api.cms.services_new.RedirectService import RedirectService
        from api.cms.models_new.seo import Redirect301
        redirect = RedirectService.create('/delete-me/', '/somewhere/')
        rid = redirect.id
        success = RedirectService.delete_redirect(redirect)
        self.assertTrue(success)
        self.assertFalse(Redirect301.objects.filter(id=rid).exists())

    def test_record_hit(self):
        from api.cms.services_new.RedirectService import RedirectService
        redirect = RedirectService.create('/hit-me/', '/hit-target/')
        RedirectService.record_hit(redirect)
        redirect.refresh_from_db()
        self.assertEqual(redirect.hit_count, 1)

    def test_bulk_import_csv(self):
        from api.cms.services_new.RedirectService import RedirectService
        csv_content = "/old1/,/new1/,301\n/old2/,/new2/,302\n"
        created, errors = RedirectService.bulk_import_csv(csv_content)
        self.assertEqual(created, 2)
        self.assertEqual(len(errors), 0)

    def test_cleanup_unused(self):
        from api.cms.services_new.RedirectService import RedirectService
        from django.utils import timezone
        import datetime
        redirect = RedirectService.create('/cleanup-me/', '/target/')
        # Manually set old created_at
        from api.cms.models_new.seo import Redirect301
        Redirect301.objects.filter(id=redirect.id).update(
            created_at=timezone.now() - datetime.timedelta(days=100)
        )
        deleted = RedirectService.cleanup_unused(days=90)
        self.assertGreaterEqual(deleted, 1)

    def test_get_statistics(self):
        from api.cms.services_new.RedirectService import RedirectService
        stats = RedirectService.get_statistics()
        self.assertIn('total_redirects', stats)
        self.assertIn('total_hits', stats)
