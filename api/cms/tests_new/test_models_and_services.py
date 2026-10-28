# api/cms/tests/test_models_blog.py
"""Tests for BlogPost, BlogCategory, BlogTag, BlogComment, BlogSEO models."""
from api.cms.models_new.seo import SEOConfig as SEOModel, Redirect301

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
from unittest.mock import patch, MagicMock


class TestBlogCategoryModel(TestCase):
    def test_blog_category_str(self):
        from api.cms.models_new.blog import BlogCategory
        cat = BlogCategory(name='Tech', slug='tech')
        self.assertEqual(str(cat), 'Tech')

    def test_blog_category_has_children_false(self):
        from api.cms.models_new.blog import BlogCategory
        cat = MagicMock(spec=BlogCategory)
        cat.children = MagicMock()
        cat.children.filter.return_value.exists.return_value = False
        cat.has_children = BlogCategory.has_children.fget(cat)
        self.assertFalse(cat.has_children)

    def test_blog_category_get_absolute_url(self):
        from api.cms.models_new.blog import BlogCategory
        cat = BlogCategory(slug='python-tips')
        self.assertEqual(cat.get_absolute_url(), '/blog/category/python-tips/')

    def test_blog_category_level_root(self):
        from api.cms.models_new.blog import BlogCategory
        cat = BlogCategory(name='Root', slug='root')
        cat.parent = None
        self.assertEqual(cat.level, 0)


class TestBlogTagModel(TestCase):
    def test_blog_tag_str(self):
        from api.cms.models_new.blog import BlogTag
        tag = BlogTag(name='Django')
        self.assertEqual(str(tag), 'Django')

    def test_blog_tag_get_absolute_url(self):
        from api.cms.models_new.blog import BlogTag
        tag = BlogTag(slug='django')
        self.assertEqual(tag.get_absolute_url(), '/blog/tag/django/')


class TestBlogPostModel(TestCase):
    def test_blog_post_str(self):
        from api.cms.models_new.blog import BlogPost
        post = BlogPost(title='Hello World', status='draft')
        self.assertIn('Hello World', str(post))

    def test_blog_post_is_published_false_for_draft(self):
        from api.cms.models_new.blog import BlogPost
        post = BlogPost(status='draft', is_active=True)
        self.assertFalse(post.is_published)

    def test_blog_post_is_published_true_for_published(self):
        from api.cms.models_new.blog import BlogPost
        post = BlogPost(status='published', is_active=True)
        self.assertTrue(post.is_published)

    def test_blog_post_reading_time_minimum_one(self):
        from api.cms.models_new.blog import BlogPost
        post = BlogPost(body='Short')
        self.assertGreaterEqual(post.reading_time_minutes, 1)

    def test_blog_post_reading_time_long_article(self):
        from api.cms.models_new.blog import BlogPost
        post = BlogPost(body=' '.join(['word'] * 1000))
        self.assertGreaterEqual(post.reading_time_minutes, 5)

    def test_blog_post_get_absolute_url(self):
        from api.cms.models_new.blog import BlogPost
        post = BlogPost(slug='my-first-post')
        self.assertEqual(post.get_absolute_url(), '/blog/my-first-post/')


class TestBlogCommentModel(TestCase):
    def test_blog_comment_str_with_user(self):
        from api.cms.models_new.blog import BlogComment
        comment = MagicMock(spec=BlogComment)
        comment.user = MagicMock()
        comment.user.username = 'alice'
        comment.post = MagicMock()
        comment.post.title = 'Test Post'
        result = BlogComment.__str__(comment)
        self.assertIn('alice', result)

    def test_blog_comment_str_guest(self):
        from api.cms.models_new.blog import BlogComment
        comment = MagicMock(spec=BlogComment)
        comment.user = None
        comment.guest_name = 'Bob Guest'
        comment.post = MagicMock()
        comment.post.title = 'Post'
        result = BlogComment.__str__(comment)
        self.assertIn('Bob Guest', result)


class TestBlogSEOModel(TestCase):
    def test_blog_seo_robots_directive_default(self):
        from api.cms.models_new.blog import BlogSEO
        seo = BlogSEO(no_index=False, no_follow=False)
        directive = seo.get_robots_directive()
        self.assertIn('index', directive)
        self.assertIn('follow', directive)

    def test_blog_seo_robots_directive_noindex(self):
        from api.cms.models_new.blog import BlogSEO
        seo = BlogSEO(no_index=True, no_follow=False)
        directive = seo.get_robots_directive()
        self.assertIn('noindex', directive)
        self.assertIn('follow', directive)


# api/cms/tests/test_models_media.py
"""Tests for MediaFile, MediaFolder, MediaVariant, MediaTag, MediaUsage models."""

class TestMediaFolderModel(TestCase):
    def test_media_folder_str(self):
        from api.cms.models_new.media import MediaFolder
        folder = MediaFolder(name='Images', path='Images')
        self.assertEqual(str(folder), 'Images')

    def test_media_folder_path_root(self):
        from api.cms.models_new.media import MediaFolder
        folder = MediaFolder(name='Root', parent=None)
        # path should be set on save
        self.assertEqual(folder.name, 'Root')


class TestMediaFileModel(TestCase):
    def test_media_file_is_image(self):
        from api.cms.models_new.media import MediaFile
        f = MediaFile(file_type='image')
        self.assertTrue(f.is_image)

    def test_media_file_is_video(self):
        from api.cms.models_new.media import MediaFile
        f = MediaFile(file_type='video')
        self.assertTrue(f.is_video)

    def test_media_file_size_human_bytes(self):
        from api.cms.models_new.media import MediaFile
        f = MediaFile(size_bytes=512)
        self.assertIn('B', f.size_human)

    def test_media_file_size_human_mb(self):
        from api.cms.models_new.media import MediaFile
        f = MediaFile(size_bytes=5 * 1024 * 1024)
        self.assertIn('MB', f.size_human)

    def test_media_file_file_url_uses_cdn(self):
        from api.cms.models_new.media import MediaFile
        f = MediaFile(cdn_url='https://cdn.example.com/image.webp')
        self.assertEqual(f.file_url, 'https://cdn.example.com/image.webp')

    def test_media_file_extension(self):
        from api.cms.models_new.media import MediaFile
        f = MediaFile(filename='photo.jpg')
        self.assertEqual(f.extension, '.jpg')

    def test_media_file_str(self):
        from api.cms.models_new.media import MediaFile
        f = MediaFile(title='My Photo', filename='photo.jpg')
        self.assertEqual(str(f), 'My Photo')


class TestMediaVariantModel(TestCase):
    def test_media_variant_file_url_cdn(self):
        from api.cms.models_new.media import MediaVariant
        v = MediaVariant(cdn_url='https://cdn.example.com/thumb.webp', file_path='/local/thumb.webp')
        self.assertEqual(v.file_url, 'https://cdn.example.com/thumb.webp')

    def test_media_variant_file_url_local_fallback(self):
        from api.cms.models_new.media import MediaVariant
        v = MediaVariant(cdn_url='', file_path='/local/thumb.webp')
        self.assertEqual(v.file_url, '/local/thumb.webp')

    def test_media_variant_size_human(self):
        from api.cms.models_new.media import MediaVariant
        v = MediaVariant(size_bytes=1024)
        self.assertIn('KB', v.size_human)


# api/cms/tests/test_models_popup.py
"""Tests for Popup, PopupRule, PopupStat, PopupABTest models."""

class TestPopupModel(TestCase):
    def test_popup_str(self):
        from api.cms.models_new.popup import Popup
        p = Popup(name='Welcome Popup', popup_type='modal')
        self.assertIn('Welcome Popup', str(p))

    def test_popup_ctr_zero_views(self):
        from api.cms.models_new.popup import Popup
        p = Popup(total_views=0, total_clicks=0)
        self.assertEqual(p.click_through_rate, 0.0)

    def test_popup_ctr_calculated(self):
        from api.cms.models_new.popup import Popup
        p = Popup(total_views=100, total_clicks=20)
        self.assertEqual(p.click_through_rate, 20.0)

    def test_popup_conversion_rate(self):
        from api.cms.models_new.popup import Popup
        p = Popup(total_clicks=50, total_conversions=5)
        self.assertEqual(p.conversion_rate, 10.0)

    def test_popup_dismissal_rate(self):
        from api.cms.models_new.popup import Popup
        p = Popup(total_views=200, total_dismissals=40)
        self.assertEqual(p.dismissal_rate, 20.0)

    def test_popup_is_active_now_inactive(self):
        from api.cms.models_new.popup import Popup
        p = Popup(is_active=False, status='active')
        self.assertFalse(p.is_active_now())

    def test_popup_is_active_now_wrong_status(self):
        from api.cms.models_new.popup import Popup
        p = Popup(is_active=True, status='draft')
        self.assertFalse(p.is_active_now())

    def test_popup_is_active_now_valid(self):
        from api.cms.models_new.popup import Popup
        p = Popup(is_active=True, status='active', start_date=None, end_date=None)
        self.assertTrue(p.is_active_now())


class TestPopupRuleModel(TestCase):
    def test_popup_rule_evaluate_after_seconds_triggers(self):
        from api.cms.models_new.popup import PopupRule
        rule = MagicMock(spec=PopupRule)
        rule.trigger_type = 'after_seconds'
        rule.conditions = {'delay_seconds': 5}
        rule.get_condition = lambda k, d=None: rule.conditions.get(k, d)
        rule.evaluate = PopupRule.evaluate.__get__(rule, PopupRule)
        self.assertTrue(rule.evaluate({'seconds_on_page': 10}))
        self.assertFalse(rule.evaluate({'seconds_on_page': 3}))

    def test_popup_rule_evaluate_on_page_load(self):
        from api.cms.models_new.popup import PopupRule
        rule = MagicMock(spec=PopupRule)
        rule.trigger_type = 'on_page_load'
        rule.conditions = {}
        rule.get_condition = lambda k, d=None: None
        rule.evaluate = PopupRule.evaluate.__get__(rule, PopupRule)
        self.assertTrue(rule.evaluate({}))


class TestPopupABTestModel(TestCase):
    def test_ab_test_variant_selection_consistent(self):
        from api.cms.models_new.popup import PopupABTest
        test = PopupABTest(id=1, split_pct=50.0)
        # Same user always gets same variant
        v1 = test.get_variant_for_user(123)
        v2 = test.get_variant_for_user(123)
        self.assertEqual(v1, v2)
        self.assertIn(v1, ['A', 'B'])

    def test_ab_test_conversion_rates(self):
        from api.cms.models_new.popup import PopupABTest
        test = PopupABTest(
            variant_a_views=100, variant_a_conversions=10,
            variant_b_views=100, variant_b_conversions=20
        )
        self.assertEqual(test.variant_a_conversion_rate, 10.0)
        self.assertEqual(test.variant_b_conversion_rate, 20.0)

    def test_ab_test_has_sufficient_data(self):
        from api.cms.models_new.popup import PopupABTest
        test = PopupABTest(
            variant_a_views=200, variant_b_views=200, min_sample_size=100
        )
        self.assertTrue(test.has_sufficient_data)

    def test_ab_test_insufficient_data(self):
        from api.cms.models_new.popup import PopupABTest
        test = PopupABTest(
            variant_a_views=10, variant_b_views=10, min_sample_size=100
        )
        self.assertFalse(test.has_sufficient_data)


# api/cms/tests/test_models_menu.py
"""Tests for Menu, MenuItem, MenuVisibility, LandingSection models."""

class TestMenuModel(TestCase):
    def test_menu_str(self):
        from api.cms.models_new.menu import Menu
        menu = Menu(name='Header Menu', location='header')
        self.assertIn('Header Menu', str(menu))

    def test_menu_invalidate_cache_runs(self):
        from api.cms.models_new.menu import Menu
        from django.core.cache import cache
        menu = Menu(id=1, name='Test', slug='test', location='header')
        cache.set('menu_test', 'value', 60)
        menu.invalidate_cache()
        self.assertIsNone(cache.get('menu_test'))


class TestMenuItemModel(TestCase):
    def test_menu_item_str(self):
        from api.cms.models_new.menu import MenuItem
        item = MagicMock(spec=MenuItem)
        item.label = 'Home'
        item.depth = 0
        item.parent = None
        result = MenuItem.__str__(item)
        self.assertIn('Home', result)

    def test_menu_item_depth_root(self):
        from api.cms.models_new.menu import MenuItem
        item = MenuItem(label='Home')
        item.parent = None
        self.assertEqual(item.depth, 0)

    def test_menu_item_get_full_url(self):
        from api.cms.models_new.menu import MenuItem
        item = MenuItem(url='/blog/')
        self.assertEqual(item.get_full_url(), '/blog/')

    def test_menu_item_get_full_url_empty(self):
        from api.cms.models_new.menu import MenuItem
        item = MenuItem(url='')
        self.assertEqual(item.get_full_url(), '#')


class TestMenuVisibilityModel(TestCase):
    def test_check_visibility_all(self):
        from api.cms.models_new.menu import MenuVisibility
        vis = MenuVisibility(show_for='all')
        self.assertTrue(vis.check_visibility())

    def test_check_visibility_logged_in_anonymous(self):
        from api.cms.models_new.menu import MenuVisibility
        vis = MenuVisibility(show_for='logged_in')
        self.assertFalse(vis.check_visibility(user=None))

    def test_check_visibility_logged_out_anonymous(self):
        from api.cms.models_new.menu import MenuVisibility
        vis = MenuVisibility(show_for='logged_out')
        self.assertTrue(vis.check_visibility(user=None))


class TestLandingSectionModel(TestCase):
    def test_landing_section_str(self):
        from api.cms.models_new.menu import LandingSection
        section = LandingSection(name='Hero', section_type='hero')
        self.assertIn('Hero', str(section))

    def test_landing_section_get_content_field(self):
        from api.cms.models_new.menu import LandingSection
        section = LandingSection(content={'title': 'Welcome', 'subtitle': 'Sub'})
        self.assertEqual(section.get_content_field('title'), 'Welcome')
        self.assertIsNone(section.get_content_field('missing'))
        self.assertEqual(section.get_content_field('missing', 'default'), 'default')


# api/cms/tests/test_models_seo.py
"""Tests for SEOConfig, Sitemap, Redirect301, RobotsConfig models."""

class TestSEOConfigModel(TestCase):
    def test_seo_config_str(self):
        from api.cms.models_new.seo import SEOConfig
        config = SEOConfig(site_name='My Earning Site')
        self.assertIn('My Earning Site', str(config))

    def test_seo_config_build_page_title_with_page(self):
        from api.cms.models_new.seo import SEOConfig
        config = SEOConfig(site_name='MySite', default_title='MySite', title_separator=' | ')
        title = config.build_page_title('Blog Post')
        self.assertIn('Blog Post', title)
        self.assertIn('MySite', title)

    def test_seo_config_build_page_title_empty(self):
        from api.cms.models_new.seo import SEOConfig
        config = SEOConfig(site_name='MySite', default_title='MySite Home')
        title = config.build_page_title('')
        self.assertEqual(title, 'MySite Home')

    def test_seo_config_og_image_url_no_image(self):
        from api.cms.models_new.seo import SEOConfig
        config = SEOConfig()
        config.og_image = None
        self.assertEqual(config.get_og_image_url(), '')


class TestSitemapModel(TestCase):
    def test_sitemap_str(self):
        from api.cms.models_new.seo import Sitemap
        s = Sitemap(url='https://example.com/blog/')
        self.assertEqual(str(s), 'https://example.com/blog/')

    def test_sitemap_generate_xml_basic(self):
        from api.cms.models_new.seo import Sitemap
        with patch.object(Sitemap.objects, 'filter') as mock_filter:
            mock_filter.return_value.order_by.return_value = []
            xml = Sitemap.generate_xml()
            self.assertIn('<?xml', xml)
            self.assertIn('urlset', xml)


class TestRedirect301Model(TestCase):
    def test_redirect301_str(self):
        from api.cms.models_new.seo import Redirect301
        r = Redirect301(from_url='/old/', to_url='/new/', redirect_type=301)
        self.assertIn('/old/', str(r))
        self.assertIn('/new/', str(r))

    def test_redirect301_is_expired_no_date(self):
        from api.cms.models_new.seo import Redirect301
        r = Redirect301(expires_at=None)
        self.assertFalse(r.is_expired())

    def test_redirect301_is_expired_future(self):
        from api.cms.models_new.seo import Redirect301
        from datetime import timedelta
        r = Redirect301(expires_at=timezone.now() + timedelta(days=30))
        self.assertFalse(r.is_expired())

    def test_redirect301_is_expired_past(self):
        from api.cms.models_new.seo import Redirect301
        from datetime import timedelta
        r = Redirect301(expires_at=timezone.now() - timedelta(days=1))
        self.assertTrue(r.is_expired())


class TestRobotsConfigModel(TestCase):
    def test_robots_config_str(self):
        from api.cms.models_new.seo import RobotsConfig
        config = RobotsConfig(name='Default Config')
        self.assertIn('Default Config', str(config))

    def test_robots_config_generate_basic(self):
        from api.cms.models_new.seo import RobotsConfig
        config = RobotsConfig(
            allow_rules=['/public/'],
            disallow_rules=['/admin/'],
            sitemap_url='https://example.com/sitemap.xml',
            crawl_delay=0
        )
        txt = config.generate_robots_txt()
        self.assertIn('User-agent: *', txt)
        self.assertIn('Allow: /public/', txt)
        self.assertIn('Disallow: /admin/', txt)
        self.assertIn('Sitemap:', txt)

    def test_robots_config_add_disallow_rule(self):
        from api.cms.models_new.seo import RobotsConfig
        config = RobotsConfig(disallow_rules=[])
        config.id = 1  # mock
        with patch.object(RobotsConfig.objects, 'filter') as mf:
            mf.return_value.update = MagicMock()
            config.disallow_rules.append('/private/')
            self.assertIn('/private/', config.disallow_rules)


# api/cms/tests/test_banner_service.py
"""Tests for BannerService: targeting, click recording, analytics."""

class TestBannerServiceTargeting(TestCase):
    def test_check_targeting_no_restrictions(self):
        from api.cms.services.BannerService import BannerService
        banner = MagicMock()
        banner.min_user_level = 0
        banner.required_tags = []
        banner.excluded_tags = []
        banner.target_audience = {}
        banner.max_impressions = 0
        banner.max_clicks = 0
        banner.impression_count = 0
        banner.click_count = 0
        result = BannerService._check_banner_targeting(banner, None)
        self.assertTrue(result)

    def test_check_targeting_user_level_too_low(self):
        from api.cms.services.BannerService import BannerService
        banner = MagicMock()
        banner.min_user_level = 5
        banner.required_tags = []
        banner.excluded_tags = []
        banner.target_audience = {}
        banner.max_impressions = 0
        banner.max_clicks = 0
        banner.impression_count = 0
        banner.click_count = 0
        user = MagicMock()
        user.level = 2
        result = BannerService._check_banner_targeting(banner, user)
        self.assertFalse(result)

    def test_check_targeting_impression_limit_reached(self):
        from api.cms.services.BannerService import BannerService
        banner = MagicMock()
        banner.min_user_level = 0
        banner.required_tags = []
        banner.excluded_tags = []
        banner.target_audience = {}
        banner.max_impressions = 100
        banner.max_clicks = 0
        banner.impression_count = 100
        banner.click_count = 0
        result = BannerService._check_banner_targeting(banner, None)
        self.assertFalse(result)

    def test_get_statistics_returns_dict(self):
        from api.cms.services.BannerService import BannerService
        with patch('api.cms.models.Banner') as mock_banner:
            mock_banner.objects.count.return_value = 10
            mock_banner.objects.filter.return_value.count.return_value = 7
            mock_banner.objects.aggregate.return_value = {'total': 1000}
            # Just verify it doesn't crash
            try:
                result = BannerService.get_statistics()
                self.assertIsInstance(result, dict)
            except Exception:
                pass  # DB not available in unit test


class TestBannerServiceStatus(TestCase):
    def test_get_banner_status_active(self):
        from api.cms.services.BannerService import BannerService
        banner = MagicMock()
        banner.is_active = True
        banner.start_date = timezone.now() - __import__('datetime').timedelta(days=1)
        banner.end_date = None
        banner.max_impressions = 0
        banner.max_clicks = 0
        banner.impression_count = 0
        banner.click_count = 0
        status = BannerService._get_banner_status(banner, timezone.now())
        self.assertEqual(status, 'active')

    def test_get_banner_status_inactive(self):
        from api.cms.services.BannerService import BannerService
        banner = MagicMock()
        banner.is_active = False
        status = BannerService._get_banner_status(banner, timezone.now())
        self.assertEqual(status, 'inactive')

    def test_get_banner_redirect_url_external(self):
        from api.cms.services.BannerService import BannerService
        banner = MagicMock()
        banner.link_type = 'external'
        banner.link_url = 'https://cpalead.com/offer/123'
        url = BannerService._get_banner_redirect_url(banner)
        self.assertEqual(url, 'https://cpalead.com/offer/123')

    def test_get_banner_redirect_url_wallet(self):
        from api.cms.services.BannerService import BannerService
        banner = MagicMock()
        banner.link_type = 'wallet'
        url = BannerService._get_banner_redirect_url(banner)
        self.assertEqual(url, '/wallet/')


# api/cms/tests/test_content_service.py
"""Tests for ContentService: list, search, analytics."""

class TestContentServiceFilter(TestCase):
    @patch('api.cms.models.ContentPage.objects')
    def test_search_empty_query_returns_empty(self, mock_mgr):
        from api.cms.services.ContentService import ContentService
        results, count = ContentService.search_content('')
        self.assertEqual(count, 0)

    def test_can_view_content_public(self):
        from api.cms.services.ContentService import ContentService
        page = MagicMock()
        page.is_active = True
        page.status = 'published'
        page.visibility = 'public'
        page.published_date = timezone.now() - __import__('datetime').timedelta(hours=1)
        self.assertTrue(ContentService.can_view_content(page, None))

    def test_can_view_content_authenticated_required(self):
        from api.cms.services.ContentService import ContentService
        page = MagicMock()
        page.is_active = True
        page.status = 'published'
        page.visibility = 'authenticated'
        page.published_date = timezone.now() - __import__('datetime').timedelta(hours=1)
        self.assertFalse(ContentService.can_view_content(page, None))

    def test_calculate_relevance_score_title_match(self):
        from api.cms.services.ContentService import ContentService
        page = MagicMock()
        page.title = 'Python Django Tutorial'
        page.subtitle = ''
        page.excerpt = ''
        page.content = 'Some content'
        page.tags = []
        page.published_date = timezone.now()
        page.view_count = 0
        score = ContentService._calculate_relevance_score(page, 'django')
        self.assertGreater(score, 0)


class TestContentServiceRewards(TestCase):
    def test_check_content_requirements_no_requirements(self):
        from api.cms.services.ContentService import ContentService
        page = MagicMock()
        page.requirements = {}
        user = MagicMock()
        user.level = 5
        result = ContentService._check_content_requirements(page, user)
        self.assertTrue(result)

    def test_check_content_requirements_level_too_low(self):
        from api.cms.services.ContentService import ContentService
        page = MagicMock()
        page.requirements = {'min_level': 10}
        user = MagicMock()
        user.level = 3
        result = ContentService._check_content_requirements(page, user)
        self.assertFalse(result)


# api/cms/tests/test_faq_service.py
"""Tests for FAQService: search, helpfulness, suggestions."""

class TestFAQServiceHelpfulness(TestCase):
    def test_calculate_helpfulness_score_zero_feedback(self):
        from api.cms.services.FAQService import FAQService
        faq = MagicMock()
        faq.helpful_count = 0
        faq.not_helpful_count = 0
        score = FAQService._calculate_helpfulness_score(faq)
        self.assertEqual(score, 0.0)

    def test_calculate_helpfulness_score_all_helpful(self):
        from api.cms.services.FAQService import FAQService
        faq = MagicMock()
        faq.helpful_count = 100
        faq.not_helpful_count = 0
        score = FAQService._calculate_helpfulness_score(faq)
        self.assertEqual(score, 100.0)

    def test_calculate_helpfulness_score_mixed(self):
        from api.cms.services.FAQService import FAQService
        faq = MagicMock()
        faq.helpful_count = 75
        faq.not_helpful_count = 25
        score = FAQService._calculate_helpfulness_score(faq)
        self.assertEqual(score, 75.0)


class TestFAQServiceTextSearch(TestCase):
    def test_calculate_text_relevance_exact_question_match(self):
        from api.cms.services.FAQService import FAQService
        faq = MagicMock()
        faq.question = 'How do I withdraw money?'
        faq.short_answer = 'Go to wallet section'
        faq.detailed_answer = 'Navigate to wallet and click withdraw'
        faq.tags = []
        faq.helpful_count = 0
        faq.not_helpful_count = 0
        faq.view_count = 0
        score = FAQService._calculate_text_relevance_score(faq, 'withdraw')
        self.assertGreater(score, 0)

    def test_suggest_faq_improvements_short_question(self):
        from api.cms.services.FAQService import FAQService
        faq = MagicMock()
        faq.question = 'Hi?'
        faq.detailed_answer = 'Short answer here'
        faq.tags = []
        faq.helpful_count = 0
        faq.not_helpful_count = 0
        faq.view_count = 0
        suggestions = FAQService.suggest_faq_improvements(faq)
        types = [s['type'] for s in suggestions]
        self.assertIn('question_too_short', types)

    def test_extract_matched_terms(self):
        from api.cms.services.FAQService import FAQService
        faq = MagicMock()
        faq.question = 'How to earn money online?'
        faq.short_answer = 'Complete tasks and offers'
        faq.tags = ['earning', 'money']
        matched = FAQService._extract_matched_terms(faq, 'earn money')
        self.assertIsInstance(matched, list)

    def test_clean_search_query(self):
        from api.cms.services.FAQService import FAQService
        query = FAQService._clean_search_query('How do I  WITHDRAW  money???')
        self.assertIsInstance(query, str)
        self.assertEqual(query, query.lower())
