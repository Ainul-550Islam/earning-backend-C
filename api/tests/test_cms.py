# api/tests/test_cms.py
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
import uuid

User = get_user_model()
def uid(): return uuid.uuid4().hex[:8]


class CMSTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username=f'u_{uid()}', email=f'{uid()}@test.com', password='x'
        )

    def test_content_category_creation(self):
        from api.cms.models import ContentCategory
        cat = ContentCategory.objects.create(
            name=f'Category_{uid()}',
            slug=f'cat-{uid()}',          # ✅ unique SlugField
            category_type='page',
        )
        self.assertEqual(cat.category_type, 'page')
        self.assertTrue(cat.is_active)

    def test_content_page_creation(self):
        from api.cms.models import ContentPage
        page = ContentPage.objects.create(
            title=f'Page_{uid()}',
            slug=f'page-{uid()}',         # ✅ unique SlugField
            content='Test content body',  # ✅ RichTextField required
            status='draft',
            page_type='static',
        )
        self.assertEqual(page.status, 'draft')
        self.assertFalse(page.is_published)

    def test_faq_category(self):
        from api.cms.models import FAQCategory
        cat = FAQCategory.objects.create(
            name=f'FAQ Cat_{uid()}',
            slug=f'faq-{uid()}',          # ✅ unique SlugField
            faq_type='general',
        )
        self.assertTrue(cat.is_active)

    def test_faq_creation(self):
        from api.cms.models import FAQ
        faq = FAQ.objects.create(
            question='How to withdraw coins?',
            slug=f'how-to-withdraw-{uid()}',      # ✅ unique SlugField
            detailed_answer='Go to wallet page.',  # ✅ RichTextField required
            short_answer='Visit wallet.',
            priority=2,
        )
        self.assertEqual(faq.priority, 2)
        self.assertTrue(faq.is_active)

    def test_banner_creation(self):
        from api.cms.models import Banner
        banner = Banner.objects.create(
            name=f'Banner_{uid()}',
            title=f'Test Banner_{uid()}',  # ✅ title required
            banner_type='hero',
            position='top',
            start_date=timezone.now(),     # ✅ NOT NULL
            is_active=True,
        )
        self.assertTrue(banner.is_active)
        self.assertEqual(banner.banner_type, 'hero')

    def test_banner_impression(self):
        from api.cms.models import Banner, BannerImpression
        banner = Banner.objects.create(
            name=f'Banner_{uid()}',
            title=f'Test Banner_{uid()}',
            start_date=timezone.now(),
        )
        impression = BannerImpression.objects.create(
            banner=banner,
            user=self.user,
            impression_type='view',
        )
        self.assertEqual(impression.impression_type, 'view')

    def test_banner_click(self):
        from api.cms.models import Banner, BannerClick
        banner = Banner.objects.create(
            name=f'Banner_{uid()}',
            title=f'Test Banner_{uid()}',
            start_date=timezone.now(),
        )
        click = BannerClick.objects.create(
            banner=banner,
            user=self.user,
            click_type='user',
        )
        self.assertEqual(click.click_type, 'user')

    def test_faq_feedback(self):
        from api.cms.models import FAQ, FAQFeedback
        faq = FAQ.objects.create(
            question='Test question?',
            slug=f'test-question-{uid()}',
            detailed_answer='Test answer.',
        )
        feedback = FAQFeedback.objects.create(
            faq=faq,
            user=self.user,
            is_helpful=True,
        )
        self.assertTrue(feedback.is_helpful)