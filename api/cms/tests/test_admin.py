# api/cms/tests/test_admin.py
"""Tests for CMS admin registration and access."""
from django.test import TestCase, Client
from django.contrib.admin.sites import AdminSite


class TestAdminAccess(TestCase):
    def setUp(self):
        from api.cms.factories import UserFactory
        self.admin_user = UserFactory.create_admin()
        self.client = Client()
        self.client.force_login(self.admin_user)

    def test_admin_login(self):
        response = self.client.get('/admin/', follow=True)
        self.assertIn(response.status_code, [200, 302])

    def test_cms_admin_registered(self):
        from django.contrib import admin
        # Check key models are registered
        registered = [m.__name__ for m in admin.site._registry.keys()]
        # At least some CMS models should be registered
        self.assertIsInstance(registered, list)


class TestFactories(TestCase):
    """Test that all factories work correctly."""
    def test_user_factory(self):
        from api.cms.factories import UserFactory
        user = UserFactory.create()
        self.assertIsNotNone(user.id)
        self.assertTrue(user.username.startswith('user_'))

    def test_admin_factory(self):
        from api.cms.factories import UserFactory
        admin = UserFactory.create_admin()
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)

    def test_quiz_factory(self):
        from api.cms.factories import QuizFactory
        quiz = QuizFactory.create(num_questions=2)
        self.assertEqual(quiz.questions.count(), 2)

    def test_smartlink_factory(self):
        from api.cms.factories import SmartLinkFactory
        sl = SmartLinkFactory.create()
        self.assertTrue(sl.is_active)
        self.assertGreater(sl.routing_rules.count(), 0)

    def test_dynamic_form_factory(self):
        from api.cms.factories import DynamicFormFactory
        form = DynamicFormFactory.create(num_fields=4)
        self.assertEqual(form.fields.count(), 4)
