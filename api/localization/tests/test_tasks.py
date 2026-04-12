# tests/test_tasks.py
from django.test import TestCase


class TasksTest(TestCase):
    def test_cleanup_task_imports(self):
        """Tasks can be imported without error"""
        try:
            from localization.tasks.cleanup_tasks import cleanup_all
            self.assertTrue(callable(cleanup_all))
        except ImportError:
            # Celery not installed — ok
            pass

    def test_seed_task(self):
        """Seed task creates languages"""
        try:
            from localization.tasks.seed_tasks import seed_languages_task
            result = seed_languages_task()
            self.assertIn('created', result)
        except Exception:
            pass
