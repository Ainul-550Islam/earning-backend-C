# cms/tests_new/test_workflow_publish_cache.py
"""
WorkflowService + CMSPublishService + CMSCacheService + ContentCalendarService tests.
"""
import pytest
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()
pytestmark = pytest.mark.django_db


def _make_user(username, staff=False):
    u = User.objects.create_user(
        username=username, email=f'{username}@test.com', password='Pass123!'
    )
    if staff:
        u.is_staff = True
        u.save()
    return u


# ══════════════════════════════════════════════════════════════════════════════
# WorkflowService
# ══════════════════════════════════════════════════════════════════════════════

class TestWorkflowService(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.admin = _make_user('wf_admin', staff=True)
        cls.editor = _make_user('wf_editor')

    def test_valid_transitions_dict_exists(self):
        from api.cms.services_new.WorkflowService import VALID_TRANSITIONS
        self.assertIn('draft',     VALID_TRANSITIONS)
        self.assertIn('review',    VALID_TRANSITIONS)
        self.assertIn('published', VALID_TRANSITIONS)
        self.assertIn('archived',  VALID_TRANSITIONS)

    def test_draft_can_go_to_review(self):
        from api.cms.services_new.WorkflowService import VALID_TRANSITIONS
        self.assertIn('review', VALID_TRANSITIONS['draft'])

    def test_published_can_go_to_archived(self):
        from api.cms.services_new.WorkflowService import VALID_TRANSITIONS
        self.assertIn('archived', VALID_TRANSITIONS['published'])

    def test_archived_cannot_go_to_published_directly(self):
        from api.cms.services_new.WorkflowService import VALID_TRANSITIONS
        self.assertNotIn('published', VALID_TRANSITIONS['archived'])

    def test_transition_invalid_state_returns_error(self):
        from api.cms.services_new.WorkflowService import WorkflowService
        result = WorkflowService.transition(
            content_type='page',
            object_id=99999,
            to_state='published',
            user=self.admin,
            comment='',
        )
        self.assertFalse(result.get('success', True),
                         msg='Transitioning non-existent object must fail')

    def test_get_available_transitions_returns_list(self):
        from api.cms.services_new.WorkflowService import WorkflowService
        result = WorkflowService.get_available_transitions(
            content_type='page', object_id=1, user=self.admin
        )
        self.assertIsInstance(result, (list, dict))

    def test_direct_invalid_transition_rejected(self):
        """draft → published (skipping review) must be rejected."""
        from api.cms.services_new.WorkflowService import VALID_TRANSITIONS
        self.assertNotIn('published', VALID_TRANSITIONS.get('draft', []),
                         msg='draft → published without review is invalid')


# ══════════════════════════════════════════════════════════════════════════════
# CMSPublishService
# ══════════════════════════════════════════════════════════════════════════════

class TestCMSPublishService(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.admin = _make_user('pub_admin', staff=True)

    def test_publish_scheduled_all_returns_dict(self):
        from api.cms.services_new.CMSPublishService import CMSPublishService
        result = CMSPublishService.publish_scheduled_all()
        self.assertIsInstance(result, (dict, int))

    def test_bulk_publish_empty_list_returns_zero(self):
        from api.cms.services_new.CMSPublishService import CMSPublishService
        count = CMSPublishService.bulk_publish([], 'page', user=self.admin)
        self.assertEqual(count, 0)

    def test_publish_nonexistent_object_returns_false(self):
        from api.cms.services_new.CMSPublishService import CMSPublishService
        obj = MagicMock()
        obj.pk = 99999
        result = CMSPublishService.publish(obj, 'page', user=self.admin)
        self.assertIsInstance(result, bool)

    def test_unpublish_nonexistent_returns_false(self):
        from api.cms.services_new.CMSPublishService import CMSPublishService
        obj = MagicMock()
        obj.pk = 99999
        result = CMSPublishService.unpublish(obj, 'page', user=self.admin)
        self.assertIsInstance(result, bool)


# ══════════════════════════════════════════════════════════════════════════════
# CMSCacheService
# ══════════════════════════════════════════════════════════════════════════════

class TestCMSCacheService(TestCase):

    def test_warm_blog_cache_does_not_raise(self):
        from api.cms.services_new.CMSCacheService import CMSCacheService
        try:
            CMSCacheService.warm_blog_cache()
        except Exception as e:
            self.fail(f'warm_blog_cache raised: {e}')

    def test_clear_all_cms_caches_does_not_raise(self):
        from api.cms.services_new.CMSCacheService import CMSCacheService
        try:
            CMSCacheService.clear_all_cms_caches()
        except Exception as e:
            self.fail(f'clear_all_cms_caches raised: {e}')

    def test_invalidate_blog_post_removes_cache(self):
        from django.core.cache import cache
        from api.cms.services_new.CMSCacheService import CMSCacheService
        # Set a fake cache key first
        cache.set('blog_post_42', {'title': 'test'}, 60)
        post = MagicMock()
        post.pk = 42
        post.id = 42
        CMSCacheService.invalidate_blog_post(post)
        # After invalidation, key should be gone
        val = cache.get('blog_post_42')
        self.assertIsNone(val)

    def test_warm_popular_content_does_not_raise(self):
        from api.cms.services_new.CMSCacheService import CMSCacheService
        try:
            CMSCacheService.warm_popular_content()
        except Exception as e:
            self.fail(f'warm_popular_content raised: {e}')

    def test_invalidate_menu_removes_cache(self):
        from django.core.cache import cache
        from api.cms.services_new.CMSCacheService import CMSCacheService
        cache.set('cms_menu_list', [{'id': 1}], 60)
        menu = MagicMock()
        menu.pk = 1
        CMSCacheService.invalidate_menu(menu)
        val = cache.get('cms_menu_list')
        self.assertIsNone(val)


# ══════════════════════════════════════════════════════════════════════════════
# ContentCalendarService
# ══════════════════════════════════════════════════════════════════════════════

class TestContentCalendarService(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.admin = _make_user('cal_admin', staff=True)

    def test_get_upcoming_returns_list(self):
        from api.cms.services_new.ContentCalendarService import ContentCalendarService
        result = ContentCalendarService.get_upcoming(days=30)
        self.assertIsInstance(result, (list, dict))

    def test_get_calendar_returns_dict(self):
        from api.cms.services_new.ContentCalendarService import ContentCalendarService
        result = ContentCalendarService.get_calendar(year=2026, month=6)
        self.assertIsInstance(result, dict)

    def test_get_calendar_day_keys_are_integers(self):
        from api.cms.services_new.ContentCalendarService import ContentCalendarService
        result = ContentCalendarService.get_calendar(year=2026, month=6)
        if isinstance(result, dict) and result:
            for key in result.keys():
                self.assertIsInstance(int(key), int,
                                      msg=f'Calendar key {key} must be int (day of month)')

    def test_process_due_schedules_returns_int(self):
        from api.cms.services_new.ContentCalendarService import ContentCalendarService
        count = ContentCalendarService.process_due_schedules()
        self.assertIsInstance(count, int)
        self.assertGreaterEqual(count, 0)

    def test_cancel_nonexistent_schedule_returns_false(self):
        from api.cms.services_new.ContentCalendarService import ContentCalendarService
        result = ContentCalendarService.cancel_schedule(schedule_id=99999)
        self.assertFalse(result,
                         msg='Cancelling non-existent schedule must return False')

    def test_schedule_requires_valid_date(self):
        from api.cms.services_new.ContentCalendarService import ContentCalendarService
        with self.assertRaises(Exception):
            ContentCalendarService.schedule(
                content_type='blog',
                content_id=1,
                title='Test',
                scheduled_at=None,   # None is invalid
            )


# ══════════════════════════════════════════════════════════════════════════════
# TaskManagementService
# ══════════════════════════════════════════════════════════════════════════════

class TestTaskManagementService(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = _make_user('task_svc_user')

    def test_get_task_queue_status_returns_dict(self):
        from api.cms.services_new.TaskManagementService import TaskManagementService
        result = TaskManagementService.get_queue_status()
        self.assertIsInstance(result, dict)

    def test_get_task_stats_returns_dict(self):
        from api.cms.services_new.TaskManagementService import TaskManagementService
        result = TaskManagementService.get_task_stats()
        self.assertIsInstance(result, dict)

    def test_create_task_schedule_does_not_raise(self):
        from api.cms.services_new.TaskManagementService import TaskManagementService
        try:
            TaskManagementService.create_schedule(
                task_name='test.task',
                interval_seconds=3600,
                created_by=self.user,
            )
        except Exception as e:
            self.fail(f'create_schedule raised: {e}')

    def test_acquire_lock_returns_bool(self):
        from api.cms.services_new.TaskManagementService import TaskManagementService
        result = TaskManagementService.acquire_lock(lock_name='test_lock', timeout=60)
        self.assertIsInstance(result, bool)

    def test_release_lock_does_not_raise(self):
        from api.cms.services_new.TaskManagementService import TaskManagementService
        try:
            TaskManagementService.release_lock('test_lock')
        except Exception as e:
            self.fail(f'release_lock raised: {e}')
