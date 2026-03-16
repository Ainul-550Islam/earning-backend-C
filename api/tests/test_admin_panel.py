# api/tests/test_admin_panel.py
from django.test import TestCase
from django.contrib.auth import get_user_model
import uuid

User = get_user_model()
def uid(): return uuid.uuid4().hex[:8]


class AdminPanelTest(TestCase):

    def setUp(self):
        self.admin = User.objects.create_superuser(
            username=f'admin_{uid()}', email=f'{uid()}@test.com', password='x'
        )
        self.user = User.objects.create_user(
            username=f'u_{uid()}', email=f'{uid()}@test.com', password='x'
        )

    def test_admin_action_creation(self):
        from api.admin_panel.models import AdminAction
        action = AdminAction.objects.create(
            admin=self.admin,
            action_type='user_ban',
            target_user=self.user,
            description='Test ban action',
        )
        self.assertEqual(action.action_type, 'user_ban')

    def test_admin_action_without_target(self):
        from api.admin_panel.models import AdminAction
        action = AdminAction.objects.create(
            admin=self.admin,
            action_type='setting_change',
            description='Changed site settings',
        )
        self.assertIsNone(action.target_user)

    def test_system_settings_import(self):
        from api.admin_panel.models import SystemSettings
        self.assertTrue(True)

    def test_site_notification(self):
        from api.admin_panel.models import SiteNotification
        notif = SiteNotification.objects.create(
            title=f'Notice_{uid()}',
            message='Test notice',
            is_active=True,
        )
        self.assertTrue(notif.is_active)

    def test_site_content(self):
        from api.admin_panel.models import SiteContent
        content = SiteContent.objects.create(
            identifier=f'test-content-{uid()}',  # ✅ key → identifier (SlugField unique)
            title=f'Test Title_{uid()}',          # ✅ required
            content='Test content body',          # ✅ required TextField
            content_type='PAGE',
        )
        self.assertTrue(content.is_active)

    def test_report_creation(self):
        from api.admin_panel.models import Report
        report = Report.objects.create(
            title=f'Report_{uid()}',
            report_type='user',
            generated_by=self.admin,
        )
        self.assertIsNotNone(report)