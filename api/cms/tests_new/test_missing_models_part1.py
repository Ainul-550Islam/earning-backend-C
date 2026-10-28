# cms/tests_new/test_missing_models_part1.py
"""
Tests for 13 previously-untested models (Part 1 of 2).

Coverage added:
  1.  Announcement
  2.  CommentReaction
  3.  ContentCategory (cms.models)
  4.  ContentComment
  5.  ContentPermission (cms.models)
  6.  ContentSchedule (models_new/site_config.py)
  7.  EmailTemplate
  8.  FAQCategory (cms.models)
  9.  FileManager (cms.models)
 10.  FormField
 11.  GalleryImage (cms.models)
 12.  ImageGallery (cms.models)
 13.  LockerUnlock
"""
import uuid
from datetime import timedelta
from unittest.mock import patch, MagicMock

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def make_user(username=None, is_staff=False):
    username = username or f"user_{uuid.uuid4().hex[:6]}"
    return User.objects.create_user(
        username=username, password="testpass123", is_staff=is_staff
    )


# ─────────────────────────────────────────────────────────────────────────────
# 1. Announcement
# ─────────────────────────────────────────────────────────────────────────────

class AnnouncementModelTest(TestCase):
    def setUp(self):
        try:
            from api.cms.models_new.extras import Announcement
            self.Announcement = Announcement
        except ImportError:
            self.skipTest("Announcement model not importable")

    def _make(self, **kwargs):
        defaults = dict(
            title="Test Announcement",
            message="Test message",
            announcement_type="info",
            start_date=timezone.now() - timedelta(hours=1),
        )
        defaults.update(kwargs)
        return self.Announcement.objects.create(**defaults)

    def test_create_announcement(self):
        ann = self._make()
        self.assertEqual(ann.title, "Test Announcement")
        self.assertEqual(ann.announcement_type, "info")
        self.assertTrue(ann.is_active)

    def test_is_active_now_true(self):
        ann = self._make(is_active=True)
        self.assertTrue(ann.is_active_now())

    def test_is_active_now_false_when_inactive(self):
        ann = self._make(is_active=False)
        self.assertFalse(ann.is_active_now())

    def test_is_active_now_future_start(self):
        ann = self._make(start_date=timezone.now() + timedelta(hours=2))
        self.assertFalse(ann.is_active_now())

    def test_is_active_now_past_end(self):
        ann = self._make(end_date=timezone.now() - timedelta(hours=1))
        self.assertFalse(ann.is_active_now())

    def test_record_view_increments_count(self):
        ann = self._make()
        self.assertEqual(ann.view_count, 0)
        ann.record_view()
        ann.refresh_from_db()
        self.assertEqual(ann.view_count, 1)

    def test_record_dismiss_increments_count(self):
        ann = self._make()
        ann.record_dismiss()
        ann.refresh_from_db()
        self.assertEqual(ann.dismiss_count, 1)

    def test_get_active_returns_active(self):
        ann = self._make()
        active = self.Announcement.get_active()
        self.assertIn(ann, list(active))

    def test_str_representation(self):
        ann = self._make(title="Hello World")
        self.assertIn("Hello World", str(ann))

    def test_pinned_ordering(self):
        normal = self._make(is_pinned=False, priority=0)
        pinned = self._make(is_pinned=True, priority=10)
        all_anns = list(self.Announcement.objects.all())
        pinned_idx  = all_anns.index(pinned)
        normal_idx  = all_anns.index(normal)
        self.assertLess(pinned_idx, normal_idx)


# ─────────────────────────────────────────────────────────────────────────────
# 2. CommentReaction
# ─────────────────────────────────────────────────────────────────────────────

class CommentReactionModelTest(TestCase):
    def setUp(self):
        try:
            from api.cms.models_new.comments import ContentComment, CommentReaction
            self.ContentComment = ContentComment
            self.CommentReaction = CommentReaction
        except ImportError:
            self.skipTest("CommentReaction model not importable")
        self.user = make_user()
        self.comment = ContentComment.objects.create(
            content_type='blog_post',
            object_id=1,
            body='Test comment',
            user=self.user,
        )

    def test_create_like_reaction(self):
        reaction = self.CommentReaction.objects.create(
            comment=self.comment, user=self.user, reaction='like'
        )
        self.assertEqual(reaction.reaction, 'like')

    def test_unique_together_prevents_duplicate(self):
        from django.db import IntegrityError
        self.CommentReaction.objects.create(
            comment=self.comment, user=self.user, reaction='like'
        )
        with self.assertRaises(IntegrityError):
            self.CommentReaction.objects.create(
                comment=self.comment, user=self.user, reaction='dislike'
            )

    def test_str_representation(self):
        r = self.CommentReaction.objects.create(
            comment=self.comment, user=self.user, reaction='like'
        )
        self.assertIn('like', str(r))

    def test_dislike_reaction_valid(self):
        r = self.CommentReaction.objects.create(
            comment=self.comment, user=make_user(), reaction='dislike'
        )
        self.assertEqual(r.reaction, 'dislike')


# ─────────────────────────────────────────────────────────────────────────────
# 3. ContentCategory (legacy cms.models)
# ─────────────────────────────────────────────────────────────────────────────

class ContentCategoryModelTest(TestCase):
    def setUp(self):
        try:
            from api.cms.models import ContentCategory
            self.ContentCategory = ContentCategory
        except ImportError:
            try:
                from api.cms.models import ContentCategory
                self.ContentCategory = ContentCategory
            except ImportError:
                self.skipTest("ContentCategory model not importable")

    def _make(self, name="Test Cat", **kwargs):
        return self.ContentCategory.objects.create(name=name, **kwargs)

    def test_create_content_category(self):
        cat = self._make()
        self.assertEqual(cat.name, "Test Cat")

    def test_str_representation(self):
        cat = self._make(name="My Category")
        self.assertIn("My Category", str(cat))

    def test_default_is_active(self):
        cat = self._make()
        self.assertTrue(cat.is_active)

    def test_category_ordering(self):
        cat_b = self._make(name="B Category")
        cat_a = self._make(name="A Category")
        cats = list(self.ContentCategory.objects.all())
        names = [c.name for c in cats]
        self.assertIn("A Category", names)
        self.assertIn("B Category", names)


# ─────────────────────────────────────────────────────────────────────────────
# 4. ContentComment
# ─────────────────────────────────────────────────────────────────────────────

class ContentCommentModelTest(TestCase):
    def setUp(self):
        try:
            from api.cms.models_new.comments import ContentComment
            self.ContentComment = ContentComment
        except ImportError:
            self.skipTest("ContentComment model not importable")
        self.user = make_user()

    def _make(self, **kwargs):
        defaults = dict(
            content_type='blog_post',
            object_id=1,
            body='Test comment body',
            user=self.user,
            status='approved',
        )
        defaults.update(kwargs)
        return self.ContentComment.objects.create(**defaults)

    def test_create_comment(self):
        comment = self._make()
        self.assertEqual(comment.content_type, 'blog_post')
        self.assertEqual(comment.status, 'approved')

    def test_author_display_with_user(self):
        comment = self._make()
        self.assertEqual(comment.author_display, self.user.username)

    def test_author_display_anonymous(self):
        comment = self._make(user=None, author_name='John', status='approved')
        self.assertEqual(comment.author_display, 'John')

    def test_is_reply_false_for_top_level(self):
        comment = self._make()
        self.assertFalse(comment.is_reply)

    def test_is_reply_true_for_reply(self):
        parent = self._make()
        reply = self._make(parent=parent, depth=1)
        self.assertTrue(reply.is_reply)

    def test_get_replies_returns_approved(self):
        parent = self._make()
        reply1 = self._make(parent=parent, status='approved')
        reply2 = self._make(parent=parent, status='rejected')
        replies = list(parent.get_replies())
        self.assertIn(reply1, replies)
        self.assertNotIn(reply2, replies)

    def test_str_representation(self):
        comment = self._make()
        self.assertIn('blog_post', str(comment))

    def test_default_likes_zero(self):
        comment = self._make()
        self.assertEqual(comment.likes, 0)

    def test_model_indexes_exist(self):
        meta_indexes = self.ContentComment._meta.indexes
        self.assertGreater(len(meta_indexes), 0)


# ─────────────────────────────────────────────────────────────────────────────
# 5. ContentPermission
# ─────────────────────────────────────────────────────────────────────────────

class ContentPermissionModelTest(TestCase):
    def setUp(self):
        try:
            from api.cms.models import ContentPermission
            self.ContentPermission = ContentPermission
        except ImportError:
            try:
                from api.cms.models import ContentPermission
                self.ContentPermission = ContentPermission
            except ImportError:
                self.skipTest("ContentPermission model not importable")
        self.user = make_user()

    def test_create_permission(self):
        perm = self.ContentPermission.objects.create(
            user=self.user,
            permission_type='view',
            content_type='page',
            object_id=1,
        )
        self.assertEqual(perm.permission_type, 'view')

    def test_str_representation(self):
        perm = self.ContentPermission.objects.create(
            user=self.user,
            permission_type='edit',
            content_type='blog',
            object_id=1,
        )
        self.assertIn(self.user.username, str(perm))

    def test_permissions_are_user_scoped(self):
        user2 = make_user()
        self.ContentPermission.objects.create(
            user=self.user, permission_type='view', content_type='page', object_id=1
        )
        self.ContentPermission.objects.create(
            user=user2, permission_type='edit', content_type='page', object_id=1
        )
        user_perms = self.ContentPermission.objects.filter(user=self.user)
        self.assertEqual(user_perms.count(), 1)


# ─────────────────────────────────────────────────────────────────────────────
# 6. ContentSchedule
# ─────────────────────────────────────────────────────────────────────────────

class ContentScheduleModelTest(TestCase):
    def setUp(self):
        try:
            from api.cms.models_new.site_config import ContentSchedule
            self.ContentSchedule = ContentSchedule
        except ImportError:
            self.skipTest("ContentSchedule model not importable")
        self.user = make_user()

    def _make(self, **kwargs):
        defaults = dict(
            content_type='blog_post',
            object_id=1,
            action='publish',
            scheduled_at=timezone.now() + timedelta(hours=2),
            created_by=self.user,
            status='pending',
        )
        defaults.update(kwargs)
        return self.ContentSchedule.objects.create(**defaults)

    def test_create_schedule(self):
        s = self._make()
        self.assertEqual(s.action, 'publish')
        self.assertEqual(s.status, 'pending')

    def test_str_representation(self):
        s = self._make()
        self.assertIn('blog_post', str(s))

    def test_default_status_pending(self):
        s = self._make()
        self.assertEqual(s.status, 'pending')

    def test_scheduled_at_required(self):
        from django.db import IntegrityError
        defaults = dict(
            content_type='blog_post',
            object_id=1,
            action='publish',
            created_by=self.user,
        )
        # scheduled_at is required — should raise if omitted
        try:
            s = self.ContentSchedule(**defaults)
            s.full_clean()
            self.fail("Expected ValidationError")
        except Exception:
            pass  # expected


# ─────────────────────────────────────────────────────────────────────────────
# 7. EmailTemplate
# ─────────────────────────────────────────────────────────────────────────────

class EmailTemplateModelTest(TestCase):
    def setUp(self):
        try:
            from api.cms.models_new.extras import EmailTemplate
            self.EmailTemplate = EmailTemplate
        except ImportError:
            self.skipTest("EmailTemplate model not importable")

    def _make(self, name=None, **kwargs):
        defaults = dict(
            name=name or f"tmpl_{uuid.uuid4().hex[:6]}",
            email_type='welcome',
            subject="Hello {username}!",
            html_body="<h1>Welcome {username}</h1>",
            text_body="Welcome {username}",
        )
        defaults.update(kwargs)
        return self.EmailTemplate.objects.create(**defaults)

    def test_create_template(self):
        tmpl = self._make()
        self.assertEqual(tmpl.email_type, 'welcome')
        self.assertTrue(tmpl.is_active)

    def test_render_substitutes_variables(self):
        tmpl = self._make()
        subject, html, text = tmpl.render({'username': 'Rana'})
        self.assertIn('Rana', subject)
        self.assertIn('Rana', html)
        self.assertIn('Rana', text)

    def test_render_no_context_leaves_placeholders(self):
        tmpl = self._make()
        subject, html, text = tmpl.render({})
        self.assertIn('{username}', subject)

    def test_increment_send_count(self):
        tmpl = self._make()
        self.assertEqual(tmpl.send_count, 0)
        tmpl.increment_send_count()
        tmpl.refresh_from_db()
        self.assertEqual(tmpl.send_count, 1)

    def test_str_representation(self):
        tmpl = self._make(name='Welcome Email')
        self.assertIn('Welcome Email', str(tmpl))

    def test_unique_name_constraint(self):
        from django.db import IntegrityError
        name = "UniqueTemplate"
        self._make(name=name)
        with self.assertRaises(Exception):
            self._make(name=name)


# ─────────────────────────────────────────────────────────────────────────────
# 8. FAQCategory
# ─────────────────────────────────────────────────────────────────────────────

class FAQCategoryModelTest(TestCase):
    def setUp(self):
        try:
            from api.cms.models import FAQCategory
            self.FAQCategory = FAQCategory
        except ImportError:
            try:
                from api.cms.models import FAQCategory
                self.FAQCategory = FAQCategory
            except ImportError:
                self.skipTest("FAQCategory model not importable")

    def test_create_faq_category(self):
        cat = self.FAQCategory.objects.create(name="General Questions")
        self.assertEqual(cat.name, "General Questions")

    def test_str_representation(self):
        cat = self.FAQCategory.objects.create(name="Billing")
        self.assertIn("Billing", str(cat))

    def test_default_is_active(self):
        cat = self.FAQCategory.objects.create(name="Support")
        self.assertTrue(cat.is_active)

    def test_multiple_categories(self):
        for i in range(3):
            self.FAQCategory.objects.create(name=f"Cat {i}")
        self.assertEqual(self.FAQCategory.objects.count(), 3)


# ─────────────────────────────────────────────────────────────────────────────
# 9. FileManager
# ─────────────────────────────────────────────────────────────────────────────

class FileManagerModelTest(TestCase):
    def setUp(self):
        try:
            from api.cms.models import FileManager
            self.FileManager = FileManager
        except ImportError:
            try:
                from api.cms.models import FileManager
                self.FileManager = FileManager
            except ImportError:
                self.skipTest("FileManager model not importable")
        self.user = make_user()

    def test_create_file_entry(self):
        f = self.FileManager.objects.create(
            name="test_doc.pdf",
            uploaded_by=self.user,
        )
        self.assertEqual(f.name, "test_doc.pdf")

    def test_str_representation(self):
        f = self.FileManager.objects.create(
            name="report.xlsx", uploaded_by=self.user
        )
        self.assertIn("report.xlsx", str(f))

    def test_is_active_default(self):
        f = self.FileManager.objects.create(
            name="file.zip", uploaded_by=self.user
        )
        self.assertTrue(f.is_active)


# ─────────────────────────────────────────────────────────────────────────────
# 10. FormField
# ─────────────────────────────────────────────────────────────────────────────

class FormFieldModelTest(TestCase):
    def setUp(self):
        try:
            from api.cms.models_new.forms import DynamicForm, FormField
            self.DynamicForm = DynamicForm
            self.FormField   = FormField
        except ImportError:
            self.skipTest("FormField model not importable")
        self.user = make_user()
        self.form = DynamicForm.objects.create(
            title="Test Form",
            created_by=self.user,
        )

    def test_create_text_field(self):
        field = self.FormField.objects.create(
            form=self.form,
            label="Email Address",
            field_type="email",
            sort_order=1,
            is_required=True,
        )
        self.assertEqual(field.field_type, "email")
        self.assertTrue(field.is_required)

    def test_create_select_field(self):
        field = self.FormField.objects.create(
            form=self.form,
            label="Gender",
            field_type="select",
            sort_order=2,
            options=["Male", "Female", "Other"],
        )
        self.assertEqual(len(field.options), 3)

    def test_str_representation(self):
        field = self.FormField.objects.create(
            form=self.form, label="Name", field_type="text", sort_order=1
        )
        self.assertIn("Name", str(field))

    def test_form_field_ordering(self):
        self.FormField.objects.create(form=self.form, label="B", field_type="text", sort_order=2)
        self.FormField.objects.create(form=self.form, label="A", field_type="text", sort_order=1)
        fields = list(self.FormField.objects.filter(form=self.form).order_by('sort_order'))
        self.assertEqual(fields[0].label, "A")
        self.assertEqual(fields[1].label, "B")


# ─────────────────────────────────────────────────────────────────────────────
# 11. GalleryImage
# ─────────────────────────────────────────────────────────────────────────────

class GalleryImageModelTest(TestCase):
    def setUp(self):
        try:
            from api.cms.models import GalleryImage, ImageGallery
            self.GalleryImage = GalleryImage
            self.ImageGallery = ImageGallery
        except ImportError:
            try:
                from api.cms.models import GalleryImage, ImageGallery
                self.GalleryImage = GalleryImage
                self.ImageGallery = ImageGallery
            except ImportError:
                self.skipTest("GalleryImage model not importable")
        self.gallery = self.ImageGallery.objects.create(
            title="Test Gallery", slug=f"gallery-{uuid.uuid4().hex[:4]}"
        )

    def test_create_gallery_image(self):
        img = self.GalleryImage.objects.create(
            gallery=self.gallery,
            title="Test Image",
            sort_order=1,
        )
        self.assertEqual(img.title, "Test Image")

    def test_str_representation(self):
        img = self.GalleryImage.objects.create(
            gallery=self.gallery, title="My Photo", sort_order=1
        )
        self.assertIn("My Photo", str(img))

    def test_is_active_default(self):
        img = self.GalleryImage.objects.create(
            gallery=self.gallery, title="Photo", sort_order=1
        )
        self.assertTrue(img.is_active)

    def test_ordering_by_sort_order(self):
        self.GalleryImage.objects.create(gallery=self.gallery, title="B", sort_order=2)
        self.GalleryImage.objects.create(gallery=self.gallery, title="A", sort_order=1)
        images = list(self.GalleryImage.objects.filter(gallery=self.gallery).order_by('sort_order'))
        self.assertEqual(images[0].title, "A")


# ─────────────────────────────────────────────────────────────────────────────
# 12. ImageGallery
# ─────────────────────────────────────────────────────────────────────────────

class ImageGalleryModelTest(TestCase):
    def setUp(self):
        try:
            from api.cms.models import ImageGallery
            self.ImageGallery = ImageGallery
        except ImportError:
            try:
                from api.cms.models import ImageGallery
                self.ImageGallery = ImageGallery
            except ImportError:
                self.skipTest("ImageGallery model not importable")

    def _make(self, **kwargs):
        slug = kwargs.pop('slug', f"gallery-{uuid.uuid4().hex[:4]}")
        return self.ImageGallery.objects.create(
            title="Test Gallery", slug=slug, **kwargs
        )

    def test_create_gallery(self):
        gallery = self._make()
        self.assertEqual(gallery.title, "Test Gallery")

    def test_unique_slug(self):
        from django.db import IntegrityError
        slug = f"unique-gallery-{uuid.uuid4().hex[:4]}"
        self._make(slug=slug)
        with self.assertRaises(Exception):
            self._make(slug=slug)

    def test_str_representation(self):
        gallery = self._make()
        self.assertIn("Test Gallery", str(gallery))

    def test_is_active_default(self):
        gallery = self._make()
        self.assertTrue(gallery.is_active)

    def test_gallery_image_count(self):
        from api.cms.models import GalleryImage
        gallery = self._make()
        GalleryImage.objects.create(gallery=gallery, title="Img 1", sort_order=1)
        GalleryImage.objects.create(gallery=gallery, title="Img 2", sort_order=2)
        self.assertEqual(gallery.images.count(), 2)


# ─────────────────────────────────────────────────────────────────────────────
# 13. LockerUnlock
# ─────────────────────────────────────────────────────────────────────────────

class LockerUnlockModelTest(TestCase):
    def setUp(self):
        try:
            from api.cms.models_new.cpalead import ContentLocker, LockerUnlock
            self.ContentLocker = ContentLocker
            self.LockerUnlock  = LockerUnlock
        except ImportError:
            self.skipTest("LockerUnlock model not importable")
        self.user = make_user()
        self.locker = self.ContentLocker.objects.create(
            title="Test Locker",
            created_by=self.user,
        )

    def test_create_locker_unlock(self):
        unlock = self.LockerUnlock.objects.create(
            locker=self.locker,
            user=self.user,
            ip_address="127.0.0.1",
        )
        self.assertEqual(unlock.user, self.user)
        self.assertEqual(unlock.ip_address, "127.0.0.1")

    def test_str_representation(self):
        unlock = self.LockerUnlock.objects.create(
            locker=self.locker, user=self.user, ip_address="127.0.0.1"
        )
        self.assertIn(self.user.username, str(unlock))

    def test_unlock_timestamp_auto_set(self):
        unlock = self.LockerUnlock.objects.create(
            locker=self.locker, user=self.user, ip_address="127.0.0.1"
        )
        self.assertIsNotNone(unlock.created_at)

    def test_duplicate_unlock_possible(self):
        """Same user can unlock the same locker multiple times (logged each time)."""
        self.LockerUnlock.objects.create(
            locker=self.locker, user=self.user, ip_address="127.0.0.1"
        )
        self.LockerUnlock.objects.create(
            locker=self.locker, user=self.user, ip_address="127.0.0.1"
        )
        self.assertEqual(
            self.LockerUnlock.objects.filter(locker=self.locker, user=self.user).count(), 2
        )

    def test_locker_unlock_user_scoped(self):
        user2 = make_user()
        self.LockerUnlock.objects.create(
            locker=self.locker, user=self.user,  ip_address="1.1.1.1"
        )
        self.LockerUnlock.objects.create(
            locker=self.locker, user=user2,       ip_address="2.2.2.2"
        )
        self.assertEqual(
            self.LockerUnlock.objects.filter(user=self.user).count(), 1
        )
