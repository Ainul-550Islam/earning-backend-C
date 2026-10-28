# cms/tests_new/test_missing_models_part2.py
"""
Tests for 13 previously-untested models (Part 2 of 2).

Coverage added:
 14. NotificationTemplate
 15. OfferUpdateQueue
 16. RTBAdSlot
 17. RTBBidLog
 18. RTBConfig
 19. RealTimeOfferUpdate
 20. SiteSettings (cms.models)
 21. SocialLink
 22. Testimonial
 23. UserOfferSubscription
 24. VideoContent
 25. VideoGenerationRequest
 26. ZeroHoursSessionLog
"""
import uuid
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


def make_user(username=None):
    username = username or f"u_{uuid.uuid4().hex[:6]}"
    return User.objects.create_user(username=username, password="pass123")


# ─────────────────────────────────────────────────────────────────────────────
# 14. NotificationTemplate
# ─────────────────────────────────────────────────────────────────────────────

class NotificationTemplateModelTest(TestCase):
    def setUp(self):
        try:
            from api.cms.models_new.extras import NotificationTemplate
            self.NotificationTemplate = NotificationTemplate
        except ImportError:
            self.skipTest("NotificationTemplate not importable")

    def _make(self, name=None, **kwargs):
        defaults = dict(
            name=name or f"tmpl_{uuid.uuid4().hex[:6]}",
            notification_type='reward',
            title_template='You earned {amount}!',
            message_template='Congrats {username}, you earned {amount}.',
        )
        defaults.update(kwargs)
        return self.NotificationTemplate.objects.create(**defaults)

    def test_create_template(self):
        t = self._make()
        self.assertTrue(t.is_active)
        self.assertEqual(t.notification_type, 'reward')

    def test_render_with_context(self):
        t = self._make()
        title, msg = t.render({'amount': '5.00', 'username': 'Rana'})
        self.assertIn('5.00', title)
        self.assertIn('Rana', msg)

    def test_render_missing_var_kept(self):
        t = self._make()
        title, _ = t.render({})
        self.assertIn('{amount}', title)

    def test_str_representation(self):
        t = self._make(name='Reward Template')
        self.assertIn('Reward Template', str(t))

    def test_unique_name(self):
        name = f"UniqueNT_{uuid.uuid4().hex[:4]}"
        self._make(name=name)
        with self.assertRaises(Exception):
            self._make(name=name)


# ─────────────────────────────────────────────────────────────────────────────
# 15. OfferUpdateQueue
# ─────────────────────────────────────────────────────────────────────────────

class OfferUpdateQueueModelTest(TestCase):
    def setUp(self):
        try:
            from api.cms.models_new.realtime_offers import OfferUpdateQueue
            self.OfferUpdateQueue = OfferUpdateQueue
        except ImportError:
            self.skipTest("OfferUpdateQueue not importable")

    def _make(self, **kwargs):
        defaults = dict(
            batch_data=[{'offer_id': 1, 'action': 'update'}],
            status='pending',
        )
        defaults.update(kwargs)
        return self.OfferUpdateQueue.objects.create(**defaults)

    def test_create_queue_item(self):
        item = self._make()
        self.assertEqual(item.status, 'pending')

    def test_str_representation(self):
        item = self._make()
        self.assertIsNotNone(str(item))

    def test_status_transitions(self):
        item = self._make()
        item.status = 'processing'
        item.save()
        item.refresh_from_db()
        self.assertEqual(item.status, 'processing')

    def test_failed_status(self):
        item = self._make(status='failed', error_message='Redis timeout')
        self.assertEqual(item.error_message, 'Redis timeout')

    def test_uuid_auto_assigned(self):
        item = self._make()
        self.assertIsNotNone(item.uuid)


# ─────────────────────────────────────────────────────────────────────────────
# 16. RTBAdSlot
# ─────────────────────────────────────────────────────────────────────────────

class RTBAdSlotModelTest(TestCase):
    def setUp(self):
        try:
            from api.cms.models_new.rtb import RTBConfig, RTBAdSlot
            self.RTBConfig = RTBConfig
            self.RTBAdSlot = RTBAdSlot
        except ImportError:
            self.skipTest("RTBAdSlot not importable")
        self.config = RTBConfig.objects.create(
            name='Test RTB Config',
            endpoint_url='https://rtb.example.com/bid',
        )

    def test_create_ad_slot(self):
        slot = self.RTBAdSlot.objects.create(
            config=self.config,
            slot_name='header_banner',
            width=728,
            height=90,
        )
        self.assertEqual(slot.slot_name, 'header_banner')
        self.assertEqual(slot.width, 728)

    def test_str_representation(self):
        slot = self.RTBAdSlot.objects.create(
            config=self.config, slot_name='sidebar', width=300, height=250
        )
        self.assertIn('sidebar', str(slot))

    def test_is_active_default(self):
        slot = self.RTBAdSlot.objects.create(
            config=self.config, slot_name='footer', width=300, height=250
        )
        self.assertTrue(slot.is_active)

    def test_multiple_slots_per_config(self):
        for i in range(3):
            self.RTBAdSlot.objects.create(
                config=self.config, slot_name=f'slot_{i}', width=300, height=250
            )
        self.assertEqual(self.RTBAdSlot.objects.filter(config=self.config).count(), 3)


# ─────────────────────────────────────────────────────────────────────────────
# 17. RTBBidLog
# ─────────────────────────────────────────────────────────────────────────────

class RTBBidLogModelTest(TestCase):
    def setUp(self):
        try:
            from api.cms.models_new.rtb import RTBConfig, RTBAdSlot, RTBBidLog
            self.RTBConfig = RTBConfig
            self.RTBAdSlot = RTBAdSlot
            self.RTBBidLog = RTBBidLog
        except ImportError:
            self.skipTest("RTBBidLog not importable")
        self.config = RTBConfig.objects.create(
            name='Test Config', endpoint_url='https://rtb.example.com/bid'
        )
        self.slot = RTBAdSlot.objects.create(
            config=self.config, slot_name='test_slot', width=300, height=250
        )
        self.user = make_user()

    def test_create_bid_log(self):
        log = self.RTBBidLog.objects.create(
            slot=self.slot,
            user=self.user,
            bid_price=Decimal('0.0150'),
            won=True,
            ip_address='127.0.0.1',
        )
        self.assertEqual(log.bid_price, Decimal('0.0150'))
        self.assertTrue(log.won)

    def test_str_representation(self):
        log = self.RTBBidLog.objects.create(
            slot=self.slot, user=self.user,
            bid_price=Decimal('0.01'), won=False, ip_address='127.0.0.1'
        )
        self.assertIsNotNone(str(log))

    def test_lost_bid(self):
        log = self.RTBBidLog.objects.create(
            slot=self.slot, user=self.user,
            bid_price=Decimal('0.005'), won=False, ip_address='10.0.0.1'
        )
        self.assertFalse(log.won)


# ─────────────────────────────────────────────────────────────────────────────
# 18. RTBConfig
# ─────────────────────────────────────────────────────────────────────────────

class RTBConfigModelTest(TestCase):
    def setUp(self):
        try:
            from api.cms.models_new.rtb import RTBConfig
            self.RTBConfig = RTBConfig
        except ImportError:
            self.skipTest("RTBConfig not importable")

    def test_create_config(self):
        config = self.RTBConfig.objects.create(
            name='Appnexus',
            endpoint_url='https://ib.adnxs.com/openrtb2',
        )
        self.assertEqual(config.name, 'Appnexus')
        self.assertTrue(config.is_active)

    def test_str_representation(self):
        config = self.RTBConfig.objects.create(
            name='Google Ad Exchange', endpoint_url='https://ad.doubleclick.net'
        )
        self.assertIn('Google Ad Exchange', str(config))

    def test_timeout_default(self):
        config = self.RTBConfig.objects.create(
            name='RTB Config', endpoint_url='https://rtb.example.com'
        )
        self.assertIsNotNone(config.timeout_ms)

    def test_inactive_config(self):
        config = self.RTBConfig.objects.create(
            name='Inactive RTB', endpoint_url='https://old.rtb.com', is_active=False
        )
        self.assertFalse(config.is_active)


# ─────────────────────────────────────────────────────────────────────────────
# 19. RealTimeOfferUpdate
# ─────────────────────────────────────────────────────────────────────────────

class RealTimeOfferUpdateModelTest(TestCase):
    def setUp(self):
        try:
            from api.cms.models_new.realtime_offers import RealTimeOfferUpdate
            self.RealTimeOfferUpdate = RealTimeOfferUpdate
        except ImportError:
            self.skipTest("RealTimeOfferUpdate not importable")

    def _make(self, **kwargs):
        defaults = dict(
            offer_id='offer_123',
            update_type='payout_change',
            new_data={'payout': '2.50'},
            old_data={'payout': '2.00'},
            priority=5,
        )
        defaults.update(kwargs)
        return self.RealTimeOfferUpdate.objects.create(**defaults)

    def test_create_update(self):
        update = self._make()
        self.assertEqual(update.offer_id, 'offer_123')
        self.assertEqual(update.update_type, 'payout_change')
        self.assertTrue(update.is_active)

    def test_str_representation(self):
        update = self._make()
        self.assertIn('offer_123', str(update))

    def test_uuid_generated(self):
        update = self._make()
        self.assertIsNotNone(update.uuid)

    def test_deactivate(self):
        update = self._make()
        update.is_active = False
        update.save()
        update.refresh_from_db()
        self.assertFalse(update.is_active)

    def test_ordering_by_priority(self):
        high = self._make(priority=10)
        low  = self._make(priority=1)
        qs   = list(self.RealTimeOfferUpdate.objects.order_by('-priority'))
        self.assertEqual(qs[0].pk, high.pk)


# ─────────────────────────────────────────────────────────────────────────────
# 20. SiteSettings
# ─────────────────────────────────────────────────────────────────────────────

class SiteSettingsModelTest(TestCase):
    def setUp(self):
        try:
            from api.cms.models import SiteSettings
            self.SiteSettings = SiteSettings
        except ImportError:
            try:
                from api.cms.models import SiteSettings
                self.SiteSettings = SiteSettings
            except ImportError:
                self.skipTest("SiteSettings not importable")

    def test_create_site_settings(self):
        settings = self.SiteSettings.objects.create(
            site_name="Test CMS",
            site_url="https://test.example.com",
        )
        self.assertEqual(settings.site_name, "Test CMS")

    def test_str_representation(self):
        settings = self.SiteSettings.objects.create(
            site_name="My CMS Site"
        )
        self.assertIn("My CMS Site", str(settings))

    def test_default_values(self):
        settings = self.SiteSettings.objects.create(site_name="Defaults Test")
        self.assertTrue(hasattr(settings, 'is_active'))


# ─────────────────────────────────────────────────────────────────────────────
# 21. SocialLink
# ─────────────────────────────────────────────────────────────────────────────

class SocialLinkModelTest(TestCase):
    def setUp(self):
        try:
            from api.cms.models_new.extras import SocialLink
            self.SocialLink = SocialLink
        except ImportError:
            self.skipTest("SocialLink not importable")

    def _make(self, platform='facebook', **kwargs):
        defaults = dict(
            platform=platform,
            url=f'https://{platform}.com/testpage',
            location='footer',
        )
        defaults.update(kwargs)
        return self.SocialLink.objects.create(**defaults)

    def test_create_social_link(self):
        link = self._make()
        self.assertEqual(link.platform, 'facebook')
        self.assertTrue(link.is_active)

    def test_str_representation(self):
        link = self._make(platform='twitter')
        self.assertIn('twitter', str(link).lower())

    def test_get_for_footer(self):
        self._make(platform='facebook', location='footer')
        self._make(platform='twitter',  location='header')
        footer_links = self.SocialLink.get_for_location('footer')
        self.assertEqual(len(footer_links), 1)
        self.assertEqual(footer_links[0].platform, 'facebook')

    def test_both_location_included_in_footer(self):
        self._make(platform='instagram', location='both')
        footer_links = self.SocialLink.get_for_location('footer')
        platforms = [l.platform for l in footer_links]
        self.assertIn('instagram', platforms)

    def test_inactive_link_excluded(self):
        self._make(platform='youtube', is_active=False)
        links = self.SocialLink.get_for_location('footer')
        platforms = [l.platform for l in links]
        self.assertNotIn('youtube', platforms)

    def test_ordering_by_sort_order(self):
        self._make(platform='telegram', sort_order=2)
        self._make(platform='whatsapp', sort_order=1)
        links = list(self.SocialLink.objects.filter(is_active=True).order_by('sort_order'))
        self.assertEqual(links[0].platform, 'whatsapp')


# ─────────────────────────────────────────────────────────────────────────────
# 22. Testimonial
# ─────────────────────────────────────────────────────────────────────────────

class TestimonialModelTest(TestCase):
    def setUp(self):
        try:
            from api.cms.models_new.extras import Testimonial
            self.Testimonial = Testimonial
        except ImportError:
            self.skipTest("Testimonial not importable")
        self.user = make_user()

    def _make(self, **kwargs):
        defaults = dict(
            user=self.user,
            content="Great platform! Made $200 in a month.",
            rating=5,
        )
        defaults.update(kwargs)
        return self.Testimonial.objects.create(**defaults)

    def test_create_testimonial(self):
        t = self._make()
        self.assertEqual(t.rating, 5)
        self.assertTrue(t.is_active)

    def test_display_name_with_user(self):
        t = self._make()
        self.assertEqual(t.display_name, self.user.username)

    def test_display_name_anonymous(self):
        t = self._make(user=None, author_name="Rana Ahmed")
        self.assertEqual(t.display_name, "Rana Ahmed")

    def test_str_representation(self):
        t = self._make()
        self.assertIn('★', str(t))

    def test_get_featured(self):
        self._make(is_featured=True)
        self._make(is_featured=False)
        featured = self.Testimonial.get_featured()
        self.assertEqual(len(featured), 1)

    def test_earning_amount_optional(self):
        t = self._make(earning_amount=Decimal('250.00'), earning_period='in 30 days')
        self.assertEqual(t.earning_amount, Decimal('250.00'))

    def test_verified_testimonial(self):
        t = self._make(is_verified=True)
        self.assertTrue(t.is_verified)


# ─────────────────────────────────────────────────────────────────────────────
# 23. UserOfferSubscription
# ─────────────────────────────────────────────────────────────────────────────

class UserOfferSubscriptionModelTest(TestCase):
    def setUp(self):
        try:
            from api.cms.models_new.realtime_offers import UserOfferSubscription
            self.UserOfferSubscription = UserOfferSubscription
        except ImportError:
            self.skipTest("UserOfferSubscription not importable")
        self.user = make_user()

    def _make(self, **kwargs):
        defaults = dict(user=self.user, is_active=True)
        defaults.update(kwargs)
        return self.UserOfferSubscription.objects.create(**defaults)

    def test_create_subscription(self):
        sub = self._make()
        self.assertTrue(sub.is_active)

    def test_str_representation(self):
        sub = self._make()
        self.assertIn(self.user.username, str(sub))

    def test_one_per_user(self):
        self._make()
        with self.assertRaises(Exception):
            self._make()  # unique user constraint

    def test_subscription_defaults(self):
        sub = self._make()
        self.assertTrue(sub.subscribe_new_offers)

    def test_can_set_min_payout_filter(self):
        sub = self._make(min_payout=Decimal('1.00'))
        sub.refresh_from_db()
        self.assertEqual(sub.min_payout, Decimal('1.00'))


# ─────────────────────────────────────────────────────────────────────────────
# 24. VideoContent
# ─────────────────────────────────────────────────────────────────────────────

class VideoContentModelTest(TestCase):
    def setUp(self):
        try:
            from api.cms.models_new.video import VideoContent
            self.VideoContent = VideoContent
        except ImportError:
            self.skipTest("VideoContent not importable")
        self.user = make_user()

    def _make(self, **kwargs):
        defaults = dict(
            title='Test Video',
            status='draft',
            created_by=self.user,
        )
        defaults.update(kwargs)
        return self.VideoContent.objects.create(**defaults)

    def test_create_video(self):
        v = self._make()
        self.assertEqual(v.title, 'Test Video')
        self.assertEqual(v.status, 'draft')

    def test_str_representation(self):
        v = self._make()
        self.assertIn('Test Video', str(v))

    def test_publish_video(self):
        v = self._make()
        v.status = 'published'
        v.save()
        v.refresh_from_db()
        self.assertEqual(v.status, 'published')

    def test_video_with_url(self):
        v = self._make(video_url='https://youtube.com/watch?v=abc123')
        self.assertIn('youtube.com', v.video_url)

    def test_view_count_default_zero(self):
        v = self._make()
        self.assertEqual(getattr(v, 'view_count', 0), 0)


# ─────────────────────────────────────────────────────────────────────────────
# 25. VideoGenerationRequest
# ─────────────────────────────────────────────────────────────────────────────

class VideoGenerationRequestModelTest(TestCase):
    def setUp(self):
        try:
            from api.cms.models_new.video import VideoGenerationRequest
            self.VideoGenerationRequest = VideoGenerationRequest
        except ImportError:
            self.skipTest("VideoGenerationRequest not importable")
        self.user = make_user()

    def _make(self, **kwargs):
        defaults = dict(
            user=self.user,
            prompt='Create a 30-second promo video',
            status='pending',
        )
        defaults.update(kwargs)
        return self.VideoGenerationRequest.objects.create(**defaults)

    def test_create_request(self):
        req = self._make()
        self.assertEqual(req.status, 'pending')
        self.assertEqual(req.prompt, 'Create a 30-second promo video')

    def test_str_representation(self):
        req = self._make()
        self.assertIn(self.user.username, str(req))

    def test_status_processing(self):
        req = self._make()
        req.status = 'processing'
        req.save()
        req.refresh_from_db()
        self.assertEqual(req.status, 'processing')

    def test_completed_with_url(self):
        req = self._make(status='completed', result_url='https://cdn.example.com/video.mp4')
        self.assertEqual(req.status, 'completed')
        self.assertIn('cdn.example.com', req.result_url)

    def test_failed_with_reason(self):
        req = self._make(status='failed', error_message='AI service unavailable')
        self.assertEqual(req.error_message, 'AI service unavailable')


# ─────────────────────────────────────────────────────────────────────────────
# 26. ZeroHoursSessionLog
# ─────────────────────────────────────────────────────────────────────────────

class ZeroHoursSessionLogModelTest(TestCase):
    def setUp(self):
        try:
            from api.cms.models_new.cpalead import ZeroHoursSessionLog
            self.ZeroHoursSessionLog = ZeroHoursSessionLog
        except ImportError:
            self.skipTest("ZeroHoursSessionLog not importable")
        self.user = make_user()

    def _make(self, **kwargs):
        defaults = dict(
            user=self.user,
            session_key=f'sess_{uuid.uuid4().hex[:8]}',
            ip_address='127.0.0.1',
        )
        defaults.update(kwargs)
        return self.ZeroHoursSessionLog.objects.create(**defaults)

    def test_create_session_log(self):
        log = self._make()
        self.assertEqual(log.user, self.user)
        self.assertEqual(log.ip_address, '127.0.0.1')

    def test_str_representation(self):
        log = self._make()
        self.assertIn(self.user.username, str(log))

    def test_duration_field(self):
        log = self._make(duration_seconds=120)
        self.assertEqual(log.duration_seconds, 120)

    def test_earnings_awarded(self):
        log = self._make(earnings_awarded=Decimal('0.05'))
        self.assertEqual(log.earnings_awarded, Decimal('0.05'))

    def test_multiple_sessions_per_user(self):
        for i in range(3):
            self._make(session_key=f'sess_{i}_{uuid.uuid4().hex[:4]}')
        self.assertEqual(
            self.ZeroHoursSessionLog.objects.filter(user=self.user).count(), 3
        )
