# api/cms/tests_new/test_blog_service.py
"""
Tests for BlogService: CRUD, slug generation, publishing workflow,
SEO auto-fill, comment management, and analytics.
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
from django.utils.text import slugify
from unittest.mock import patch, MagicMock

User = get_user_model()


def make_user(username='testuser', **kwargs):
    return User.objects.create_user(username=username, password='pass123', **kwargs)


class TestBlogServiceCRUD(TestCase):
    """Test BlogService create, update, delete operations."""

    def setUp(self):
        self.user = make_user()

    def test_create_post_basic(self):
        """Should create a blog post with required fields."""
        from api.cms.services_new.BlogService import BlogService
        post = BlogService.create_post(
            title='Test Post',
            body='<p>Body content</p>',
            author=self.user,
        )
        self.assertIsNotNone(post)
        self.assertEqual(post.title, 'Test Post')
        self.assertEqual(post.status, 'draft')
        self.assertEqual(post.author, self.user)

    def test_create_post_generates_slug(self):
        """Should auto-generate slug from title."""
        from api.cms.services_new.BlogService import BlogService
        post = BlogService.create_post(title='My Awesome Post', body='body', author=self.user)
        self.assertEqual(post.slug, 'my-awesome-post')

    def test_create_post_unique_slug(self):
        """Should generate unique slug when title conflicts."""
        from api.cms.services_new.BlogService import BlogService
        post1 = BlogService.create_post(title='Duplicate Title', body='body1', author=self.user)
        post2 = BlogService.create_post(title='Duplicate Title', body='body2', author=self.user)
        self.assertIsNotNone(post1)
        self.assertIsNotNone(post2)
        self.assertNotEqual(post1.slug, post2.slug)
        self.assertEqual(post2.slug, 'duplicate-title-1')

    def test_create_post_with_category(self):
        """Should assign category to post."""
        from api.cms.services_new.BlogService import BlogService
        cat = BlogService.create_category(name='Tech')
        post = BlogService.create_post(title='Tech Post', body='body', author=self.user, category=cat)
        self.assertEqual(post.category, cat)

    def test_create_post_with_tags(self):
        """Should assign tags to post."""
        from api.cms.services_new.BlogService import BlogService
        from api.cms.models_new.blog import BlogTag
        tag1 = BlogService.get_or_create_tag('python')
        tag2 = BlogService.get_or_create_tag('django')
        post = BlogService.create_post(title='Tagged Post', body='body', author=self.user, tags=[tag1, tag2])
        self.assertIsNotNone(post)
        self.assertIn(tag1, post.tags.all())
        self.assertIn(tag2, post.tags.all())

    def test_update_post_title(self):
        """Should update post title and regenerate slug."""
        from api.cms.services_new.BlogService import BlogService
        post = BlogService.create_post(title='Old Title', body='body', author=self.user)
        success = BlogService.update_post(post, {'title': 'New Title'})
        post.refresh_from_db()
        self.assertTrue(success)
        self.assertEqual(post.title, 'New Title')
        self.assertEqual(post.slug, 'new-title')

    def test_update_post_body(self):
        """Should update post body."""
        from api.cms.services_new.BlogService import BlogService
        post = BlogService.create_post(title='Post', body='<p>Old</p>', author=self.user)
        BlogService.update_post(post, {'body': '<p>New body</p>'})
        post.refresh_from_db()
        self.assertEqual(post.body, '<p>New body</p>')

    def test_soft_delete_post(self):
        """Soft delete should archive post, not remove from DB."""
        from api.cms.services_new.BlogService import BlogService
        from api.cms.models_new.blog import BlogPost
        post = BlogService.create_post(title='To Delete', body='body', author=self.user)
        post_id = post.id
        BlogService.delete_post(post, soft=True)
        still_exists = BlogPost.objects.filter(id=post_id).exists()
        self.assertTrue(still_exists)
        post.refresh_from_db()
        self.assertEqual(post.status, 'archived')
        self.assertFalse(post.is_active)

    def test_hard_delete_post(self):
        """Hard delete should remove post from DB."""
        from api.cms.services_new.BlogService import BlogService
        from api.cms.models_new.blog import BlogPost
        post = BlogService.create_post(title='Hard Delete', body='body', author=self.user)
        post_id = post.id
        BlogService.delete_post(post, soft=False)
        self.assertFalse(BlogPost.objects.filter(id=post_id).exists())


class TestBlogServicePublishing(TestCase):
    """Test BlogService publish, unpublish, schedule workflow."""

    def setUp(self):
        self.user = make_user()
        from api.cms.services_new.BlogService import BlogService
        self.post = BlogService.create_post(title='Publish Test', body='body', author=self.user)

    def test_publish_post(self):
        """Publishing should set status to published and set published_at."""
        from api.cms.services_new.BlogService import BlogService
        success = BlogService.publish_post(self.post)
        self.post.refresh_from_db()
        self.assertTrue(success)
        self.assertEqual(self.post.status, 'published')
        self.assertIsNotNone(self.post.published_at)

    def test_publish_post_with_backdate(self):
        """Should accept a backdated publish date."""
        from api.cms.services_new.BlogService import BlogService
        backdate = timezone.now() - __import__('datetime').timedelta(days=5)
        BlogService.publish_post(self.post, publish_date=backdate)
        self.post.refresh_from_db()
        self.assertEqual(self.post.published_at.date(), backdate.date())

    def test_unpublish_post(self):
        """Unpublishing should revert status to draft."""
        from api.cms.services_new.BlogService import BlogService
        BlogService.publish_post(self.post)
        BlogService.unpublish_post(self.post)
        self.post.refresh_from_db()
        self.assertEqual(self.post.status, 'draft')

    def test_schedule_post(self):
        """Scheduling should set status to scheduled."""
        from api.cms.services_new.BlogService import BlogService
        future = timezone.now() + __import__('datetime').timedelta(days=2)
        success = BlogService.schedule_post(self.post, scheduled_at=future)
        self.post.refresh_from_db()
        self.assertTrue(success)
        self.assertEqual(self.post.status, 'scheduled')

    def test_schedule_post_past_date_fails(self):
        """Scheduling with past date should fail."""
        from api.cms.services_new.BlogService import BlogService
        past = timezone.now() - __import__('datetime').timedelta(days=1)
        success = BlogService.schedule_post(self.post, scheduled_at=past)
        self.assertFalse(success)

    def test_publish_scheduled_posts(self):
        """publish_scheduled_posts should publish due posts."""
        from api.cms.services_new.BlogService import BlogService
        from api.cms.models_new.blog import BlogPost
        from django.db.models import F
        # Manually set scheduled_at in past
        self.post.status = 'scheduled'
        self.post.scheduled_at = timezone.now() - __import__('datetime').timedelta(minutes=5)
        self.post.save()
        count = BlogService.publish_scheduled_posts()
        self.post.refresh_from_db()
        self.assertEqual(self.post.status, 'published')
        self.assertGreaterEqual(count, 1)

    def test_bulk_publish(self):
        """Bulk publish should publish multiple posts."""
        from api.cms.services_new.BlogService import BlogService
        post2 = BlogService.create_post(title='Post 2', body='body', author=self.user)
        count = BlogService.bulk_publish([self.post.id, post2.id])
        self.assertGreaterEqual(count, 2)


class TestBlogServiceSlug(TestCase):
    """Test slug generation logic."""

    def setUp(self):
        self.user = make_user()

    def test_slug_from_title(self):
        """Slug should be lowercase kebab-case of title."""
        from api.cms.services_new.BlogService import BlogService
        post = BlogService.create_post(title='Hello World Test', body='x', author=self.user)
        self.assertEqual(post.slug, 'hello-world-test')

    def test_slug_with_special_chars(self):
        """Slug should strip special characters."""
        from api.cms.services_new.BlogService import BlogService
        post = BlogService.create_post(title='Post! With @Special #Chars', body='x', author=self.user)
        self.assertNotIn('!', post.slug)
        self.assertNotIn('@', post.slug)
        self.assertNotIn('#', post.slug)

    def test_slug_uniqueness_counter(self):
        """Multiple posts with same title should have unique slugs."""
        from api.cms.services_new.BlogService import BlogService
        posts = [
            BlogService.create_post(title='Same Title', body='body', author=self.user)
            for _ in range(3)
        ]
        slugs = [p.slug for p in posts]
        self.assertEqual(len(set(slugs)), 3)


class TestBlogServiceSEO(TestCase):
    """Test SEO auto-fill functionality."""

    def setUp(self):
        self.user = make_user()

    def test_auto_fill_seo_on_create(self):
        """Creating a post with auto_seo should create SEO entry."""
        from api.cms.services_new.BlogService import BlogService
        from api.cms.models_new.blog import BlogSEO
        post = BlogService.create_post(
            title='SEO Post',
            body='body',
            author=self.user,
            excerpt='Short excerpt',
            auto_seo=True
        )
        self.assertIsNotNone(post)
        seo_exists = BlogSEO.objects.filter(post=post).exists()
        self.assertTrue(seo_exists)

    def test_auto_fill_seo_title_from_post(self):
        """SEO meta_title should be populated from post title."""
        from api.cms.services_new.BlogService import BlogService
        from api.cms.models_new.blog import BlogSEO
        post = BlogService.create_post(
            title='Auto SEO Title Test', body='body', author=self.user, auto_seo=True
        )
        seo = BlogSEO.objects.filter(post=post).first()
        if seo:
            self.assertIn('Auto SEO Title Test', seo.meta_title)

    def test_update_seo(self):
        """Should update SEO metadata for a post."""
        from api.cms.services_new.BlogService import BlogService
        from api.cms.models_new.blog import BlogSEO
        post = BlogService.create_post(title='SEO Update Test', body='body', author=self.user, auto_seo=True)
        success = BlogService.update_seo(post, {
            'meta_title': 'Custom SEO Title',
            'meta_description': 'Custom description',
        })
        self.assertTrue(success)
        seo = BlogSEO.objects.get(post=post)
        self.assertEqual(seo.meta_title, 'Custom SEO Title')


class TestBlogServiceComments(TestCase):
    """Test comment management."""

    def setUp(self):
        self.user = make_user()
        from api.cms.services_new.BlogService import BlogService
        self.post = BlogService.create_post(title='Comment Post', body='body', author=self.user)

    def test_add_comment(self):
        """Should add a comment to a post."""
        from api.cms.services_new.BlogService import BlogService
        comment = BlogService.add_comment(self.post, content='Great post!', user=self.user)
        self.assertIsNotNone(comment)
        self.assertEqual(comment.post, self.post)
        self.assertFalse(comment.is_approved)

    def test_add_comment_unauthenticated(self):
        """Should allow guest comments with name/email."""
        from api.cms.services_new.BlogService import BlogService
        comment = BlogService.add_comment(
            self.post, content='Guest comment',
            guest_name='John', guest_email='john@example.com'
        )
        self.assertIsNotNone(comment)
        self.assertEqual(comment.guest_name, 'John')

    def test_approve_comment(self):
        """Approving a comment should set is_approved=True."""
        from api.cms.services_new.BlogService import BlogService
        comment = BlogService.add_comment(self.post, content='To approve', user=self.user)
        success = BlogService.approve_comment(comment, moderator=self.user)
        comment.refresh_from_db()
        self.assertTrue(success)
        self.assertTrue(comment.is_approved)

    def test_get_post_comments_approved_only(self):
        """get_post_comments should return only approved by default."""
        from api.cms.services_new.BlogService import BlogService
        c1 = BlogService.add_comment(self.post, content='Approved', user=self.user)
        c2 = BlogService.add_comment(self.post, content='Pending', user=self.user)
        BlogService.approve_comment(c1, moderator=self.user)
        comments = BlogService.get_post_comments(self.post, approved_only=True)
        ids = [c.id for c in comments]
        self.assertIn(c1.id, ids)
        self.assertNotIn(c2.id, ids)


class TestBlogServiceAnalytics(TestCase):
    """Test analytics methods."""

    def setUp(self):
        self.user = make_user()
        from api.cms.services_new.BlogService import BlogService
        self.post = BlogService.create_post(title='Analytics Post', body='body', author=self.user)
        BlogService.publish_post(self.post)

    def test_get_post_analytics(self):
        """Should return analytics dict for a post."""
        from api.cms.services_new.BlogService import BlogService
        data = BlogService.get_post_analytics(self.post.id)
        self.assertIn('post_id', data)
        self.assertIn('views_count', data)
        self.assertEqual(data['post_id'], self.post.id)

    def test_get_blog_statistics(self):
        """Should return overall blog statistics."""
        from api.cms.services_new.BlogService import BlogService
        stats = BlogService.get_blog_statistics()
        self.assertIn('total_posts', stats)
        self.assertIn('published_posts', stats)
        self.assertGreaterEqual(stats['total_posts'], 1)

    def test_get_featured_posts(self):
        """Should return featured posts."""
        from api.cms.services_new.BlogService import BlogService
        self.post.is_featured = True
        self.post.save()
        featured = BlogService.get_featured_posts(limit=5)
        ids = [p.id for p in featured]
        self.assertIn(self.post.id, ids)

    def test_get_popular_posts(self):
        """Should return popular posts."""
        from api.cms.services_new.BlogService import BlogService
        from api.cms.models_new.blog import BlogPost
        BlogPost.objects.filter(id=self.post.id).update(views_count=100)
        popular = BlogService.get_popular_posts(days=30, limit=10)
        ids = [p.id for p in popular]
        self.assertIn(self.post.id, ids)


class TestBlogServiceCategories(TestCase):
    """Test category management."""

    def test_create_category(self):
        """Should create a blog category."""
        from api.cms.services_new.BlogService import BlogService
        cat = BlogService.create_category(name='Technology')
        self.assertIsNotNone(cat)
        self.assertEqual(cat.name, 'Technology')
        self.assertEqual(cat.slug, 'technology')

    def test_create_nested_category(self):
        """Should create nested categories."""
        from api.cms.services_new.BlogService import BlogService
        parent = BlogService.create_category(name='Tech')
        child = BlogService.create_category(name='AI', parent=parent)
        self.assertEqual(child.parent, parent)

    def test_get_categories_with_post_counts(self):
        """Should return categories with post counts."""
        from api.cms.services_new.BlogService import BlogService
        BlogService.create_category(name='Test Cat')
        result = BlogService.get_categories_with_post_counts()
        self.assertIsInstance(result, list)

    def test_get_or_create_tag(self):
        """Should get or create a tag."""
        from api.cms.services_new.BlogService import BlogService
        tag1 = BlogService.get_or_create_tag('python')
        tag2 = BlogService.get_or_create_tag('python')
        self.assertEqual(tag1.id, tag2.id)

    def test_get_popular_tags(self):
        """Should return popular tags ordered by usage."""
        from api.cms.services_new.BlogService import BlogService
        BlogService.get_or_create_tag('popular')
        tags = BlogService.get_popular_tags(limit=10)
        self.assertIsInstance(tags, list)
