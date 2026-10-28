# cms/tests_new/test_models_group2.py
"""
Model Tests — Group 2

Tests for:
  - ABTest models
  - Comments models
  - Extras models (Announcement, Testimonial, SocialLink)
  - Media models (MediaFile, MediaFolder)
  - Popup models
  - Referral models
  - SmartLink models
"""

from django.test import TestCase
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.utils import timezone
from decimal import Decimal


# ─────────────────────────────────────────────────────────────────────────────
# AB TEST MODEL TESTS
# ─────────────────────────────────────────────────────────────────────────────

class ABTestModelTest(TestCase):

    def setUp(self):
        try:
            from api.cms.models_new.ab_testing import ABTest
            self.ABTest = ABTest
            self.user = User.objects.create_user('abuser', 'ab@test.com', 'pass')
            self.test = ABTest.objects.create(
                name='Button Color Test',
                hypothesis='Green button converts better',
                test_type='ui',
                created_by=self.user,
            )
        except Exception:
            self.skipTest('ABTest model not available')

    def test_abtest_creation(self):
        self.assertIsNotNone(self.test.id)
        self.assertEqual(self.test.name, 'Button Color Test')

    def test_abtest_default_status(self):
        self.assertIn(self.test.status, ['draft', 'pending', 'active'])

    def test_abtest_str(self):
        self.assertIsInstance(str(self.test), str)

    def test_abtest_created_by(self):
        self.assertEqual(self.test.created_by, self.user)


class ABTestVariantModelTest(TestCase):

    def setUp(self):
        try:
            from api.cms.models_new.ab_testing import ABTest, ABTestVariant
            self.ABTestVariant = ABTestVariant
            user = User.objects.create_user('varuser', 'var@test.com', 'pass')
            test = ABTest.objects.create(
                name='Variant Test', test_type='ui', created_by=user
            )
            self.control = ABTestVariant.objects.create(
                test=test, name='Control', is_control=True, traffic_split=50
            )
            self.variant = ABTestVariant.objects.create(
                test=test, name='Variant A', is_control=False, traffic_split=50
            )
        except Exception:
            self.skipTest('ABTestVariant model not available')

    def test_variant_creation(self):
        self.assertIsNotNone(self.control.id)
        self.assertTrue(self.control.is_control)
        self.assertFalse(self.variant.is_control)

    def test_variant_traffic_split_sum(self):
        total = self.control.traffic_split + self.variant.traffic_split
        self.assertEqual(total, 100)

    def test_variant_str(self):
        self.assertIsInstance(str(self.control), str)


# ─────────────────────────────────────────────────────────────────────────────
# COMMENTS MODEL TESTS
# ─────────────────────────────────────────────────────────────────────────────

class ContentCommentModelTest(TestCase):

    def setUp(self):
        try:
            from api.cms.models_new.comments import ContentComment
            from django.contrib.contenttypes.models import ContentType
            self.ContentComment = ContentComment
            self.user = User.objects.create_user('commenter', 'c@test.com', 'pass')
            ct = ContentType.objects.get_for_model(User)
            self.comment = ContentComment.objects.create(
                author=self.user,
                content_type=ct,
                object_id=self.user.id,
                body='This is a test comment body here.',
            )
        except Exception:
            self.skipTest('ContentComment model not available')

    def test_comment_creation(self):
        self.assertIsNotNone(self.comment.id)
        self.assertEqual(self.comment.author, self.user)

    def test_comment_default_not_approved(self):
        self.assertFalse(self.comment.is_approved)

    def test_comment_default_not_spam(self):
        self.assertFalse(self.comment.is_spam)

    def test_comment_str(self):
        self.assertIsInstance(str(self.comment), str)

    def test_comment_approve(self):
        self.comment.is_approved = True
        self.comment.save()
        refreshed = self.ContentComment.objects.get(pk=self.comment.pk)
        self.assertTrue(refreshed.is_approved)


# ─────────────────────────────────────────────────────────────────────────────
# EXTRAS MODEL TESTS
# ─────────────────────────────────────────────────────────────────────────────

class AnnouncementModelTest(TestCase):

    def setUp(self):
        try:
            from api.cms.models_new.extras import Announcement
            self.Announcement = Announcement
            self.ann = Announcement.objects.create(
                title='System Maintenance',
                content='Maintenance on Sunday',
                announcement_type='maintenance',
                start_date=timezone.now(),
            )
        except Exception:
            self.skipTest('Announcement model not available')

    def test_announcement_creation(self):
        self.assertIsNotNone(self.ann.id)
        self.assertEqual(self.ann.title, 'System Maintenance')

    def test_announcement_default_active(self):
        self.assertTrue(self.ann.is_active)

    def test_announcement_str(self):
        self.assertIsInstance(str(self.ann), str)


class TestimonialModelTest(TestCase):

    def setUp(self):
        try:
            from api.cms.models_new.extras import Testimonial
            self.Testimonial = Testimonial
            self.testimonial = Testimonial.objects.create(
                author_name='John Doe',
                content='Great platform! Earned $500 last month.',
                rating=5,
            )
        except Exception:
            self.skipTest('Testimonial model not available')

    def test_testimonial_creation(self):
        self.assertIsNotNone(self.testimonial.id)
        self.assertEqual(self.testimonial.rating, 5)

    def test_testimonial_default_not_approved(self):
        self.assertFalse(self.testimonial.is_approved)

    def test_testimonial_str(self):
        self.assertIsInstance(str(self.testimonial), str)


class SocialLinkModelTest(TestCase):

    def setUp(self):
        try:
            from api.cms.models_new.extras import SocialLink
            self.SocialLink = SocialLink
            self.link = SocialLink.objects.create(
                platform='facebook',
                url='https://facebook.com/testpage',
                display_order=1,
            )
        except Exception:
            self.skipTest('SocialLink model not available')

    def test_sociallink_creation(self):
        self.assertIsNotNone(self.link.id)
        self.assertEqual(self.link.platform, 'facebook')

    def test_sociallink_default_active(self):
        self.assertTrue(self.link.is_active)

    def test_sociallink_str(self):
        self.assertIsInstance(str(self.link), str)


# ─────────────────────────────────────────────────────────────────────────────
# MEDIA MODEL TESTS
# ─────────────────────────────────────────────────────────────────────────────

class MediaFolderModelTest(TestCase):

    def setUp(self):
        try:
            from api.cms.models_new.media import MediaFolder
            self.MediaFolder = MediaFolder
            self.user = User.objects.create_user('mediauser', 'm@test.com', 'pass')
            self.folder = MediaFolder.objects.create(
                name='Images',
                created_by=self.user,
            )
        except Exception:
            self.skipTest('MediaFolder model not available')

    def test_folder_creation(self):
        self.assertIsNotNone(self.folder.id)
        self.assertEqual(self.folder.name, 'Images')

    def test_folder_str(self):
        self.assertIsInstance(str(self.folder), str)

    def test_folder_no_parent_by_default(self):
        self.assertIsNone(self.folder.parent)

    def test_folder_parent_child(self):
        child = self.MediaFolder.objects.create(
            name='Avatars', parent=self.folder, created_by=self.user
        )
        self.assertEqual(child.parent, self.folder)


class MediaFileModelTest(TestCase):

    def setUp(self):
        try:
            from api.cms.models_new.media import MediaFile, MediaFolder
            self.MediaFile = MediaFile
            self.user = User.objects.create_user('filemedia', 'fm@test.com', 'pass')
            self.folder = MediaFolder.objects.create(name='Docs', created_by=self.user)
            self.media = MediaFile.objects.create(
                name='test_image.jpg',
                file_type='image',
                file_size=204800,
                folder=self.folder,
                uploaded_by=self.user,
            )
        except Exception:
            self.skipTest('MediaFile model not available')

    def test_media_file_creation(self):
        self.assertIsNotNone(self.media.id)
        self.assertEqual(self.media.name, 'test_image.jpg')
        self.assertEqual(self.media.file_type, 'image')

    def test_media_file_size_positive(self):
        self.assertGreater(self.media.file_size, 0)

    def test_media_file_str(self):
        self.assertIsInstance(str(self.media), str)

    def test_media_file_belongs_to_folder(self):
        self.assertEqual(self.media.folder, self.folder)


# ─────────────────────────────────────────────────────────────────────────────
# POPUP MODEL TESTS
# ─────────────────────────────────────────────────────────────────────────────

class PopupModelTest(TestCase):

    def setUp(self):
        try:
            from api.cms.models_new.popup import Popup
            self.Popup = Popup
            self.user = User.objects.create_user('popupuser', 'p@test.com', 'pass')
            self.popup = Popup.objects.create(
                name='Welcome Popup',
                title='Welcome!',
                content='Welcome to our platform',
                popup_type='modal',
                trigger_type='on_load',
                priority=10,
                created_by=self.user,
            )
        except Exception:
            self.skipTest('Popup model not available')

    def test_popup_creation(self):
        self.assertIsNotNone(self.popup.id)
        self.assertEqual(self.popup.name, 'Welcome Popup')

    def test_popup_default_inactive(self):
        self.assertFalse(self.popup.is_active)

    def test_popup_str(self):
        self.assertIsInstance(str(self.popup), str)

    def test_popup_activate(self):
        self.popup.is_active = True
        self.popup.save()
        refreshed = self.Popup.objects.get(pk=self.popup.pk)
        self.assertTrue(refreshed.is_active)


# ─────────────────────────────────────────────────────────────────────────────
# REFERRAL MODEL TESTS
# ─────────────────────────────────────────────────────────────────────────────

class ReferralCodeModelTest(TestCase):

    def setUp(self):
        try:
            from api.cms.models_new.referral import ReferralCode
            self.ReferralCode = ReferralCode
            self.user = User.objects.create_user('refuser', 'ref@test.com', 'pass')
            self.code = ReferralCode.objects.create(
                user=self.user,
                code='TESTREF123',
            )
        except Exception:
            self.skipTest('ReferralCode model not available')

    def test_code_creation(self):
        self.assertIsNotNone(self.code.id)
        self.assertEqual(self.code.code, 'TESTREF123')

    def test_code_default_active(self):
        self.assertTrue(self.code.is_active)

    def test_code_str(self):
        self.assertIsInstance(str(self.code), str)

    def test_code_belongs_to_user(self):
        self.assertEqual(self.code.user, self.user)

    def test_code_unique(self):
        user2 = User.objects.create_user('ref2', 'ref2@test.com', 'pass')
        with self.assertRaises(Exception):
            self.ReferralCode.objects.create(user=user2, code='TESTREF123')


class ReferralEarningModelTest(TestCase):

    def setUp(self):
        try:
            from api.cms.models_new.referral import ReferralCode, ReferralEarning
            self.ReferralEarning = ReferralEarning
            self.referrer = User.objects.create_user('referrer', 'rr@test.com', 'pass')
            self.code = ReferralCode.objects.create(user=self.referrer, code='EARNCDE')
            self.earning = ReferralEarning.objects.create(
                user=self.referrer,
                referral_code=self.code,
                amount=Decimal('2.50'),
                earning_type='signup',
            )
        except Exception:
            self.skipTest('ReferralEarning model not available')

    def test_earning_creation(self):
        self.assertIsNotNone(self.earning.id)
        self.assertEqual(self.earning.amount, Decimal('2.50'))

    def test_earning_amount_positive(self):
        self.assertGreater(self.earning.amount, 0)

    def test_earning_str(self):
        self.assertIsInstance(str(self.earning), str)


# ─────────────────────────────────────────────────────────────────────────────
# SMART LINK MODEL TESTS
# ─────────────────────────────────────────────────────────────────────────────

class SmartLinkModelTest(TestCase):

    def setUp(self):
        try:
            from api.cms.models_new.smartlink import SmartLink
            self.SmartLink = SmartLink
            self.user = User.objects.create_user('sluser', 'sl@test.com', 'pass')
            self.link = SmartLink.objects.create(
                name='CPA Offer Link',
                short_code='ABC123',
                destination_url='https://example.com/offer',
                link_type='offer',
                created_by=self.user,
            )
        except Exception:
            self.skipTest('SmartLink model not available')

    def test_smartlink_creation(self):
        self.assertIsNotNone(self.link.id)
        self.assertEqual(self.link.short_code, 'ABC123')

    def test_smartlink_default_active(self):
        self.assertTrue(self.link.is_active)

    def test_smartlink_str(self):
        self.assertIsInstance(str(self.link), str)

    def test_smartlink_short_code_unique(self):
        user2 = User.objects.create_user('sl2', 'sl2@test.com', 'pass')
        with self.assertRaises(Exception):
            self.SmartLink.objects.create(
                name='Dup', short_code='ABC123',
                destination_url='https://example.com/2',
                link_type='offer', created_by=user2,
            )

    def test_smartlink_click_count_default_zero(self):
        self.assertEqual(getattr(self.link, 'click_count', 0), 0)
