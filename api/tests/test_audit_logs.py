# api/tests/test_audit_logs.py
from django.test import TestCase
from django.contrib.auth import get_user_model
import uuid

User = get_user_model()
def uid(): return uuid.uuid4().hex[:8]


class AuditLogTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username=f'u_{uid()}', email=f'{uid()}@test.com', password='x'
        )

    def _get_valid_action(self):
        """AuditLogAction এর প্রথম valid choice নাও"""
        from api.audit_logs.models import AuditLogAction
        return AuditLogAction.choices[0][0]  # প্রথম choice এর value

    def test_audit_log_creation(self):
        from api.audit_logs.models import AuditLog
        action = self._get_valid_action()
        log = AuditLog.objects.create(
            user=self.user,
            action=action,
            message='User logged in',
            resource_type='User',
            resource_id=str(self.user.id),
        )
        self.assertEqual(log.user, self.user)
        self.assertTrue(log.success)

    def test_audit_log_without_user(self):
        from api.audit_logs.models import AuditLog
        action = self._get_valid_action()
        log = AuditLog.objects.create(
            user=None,
            action=action,
            message='Anonymous action',
        )
        self.assertIsNone(log.user)

    def test_audit_log_with_data(self):
        from api.audit_logs.models import AuditLog
        action = self._get_valid_action()
        log = AuditLog.objects.create(
            user=self.user,
            action=action,
            message='Profile updated',
            old_data={'name': 'Old Name'},
            new_data={'name': 'New Name'},
            metadata={'source': 'api'},
            success=True,
        )
        self.assertEqual(log.old_data['name'], 'Old Name')
        self.assertEqual(log.new_data['name'], 'New Name')

    def test_audit_log_failure(self):
        from api.audit_logs.models import AuditLog
        action = self._get_valid_action()
        log = AuditLog.objects.create(
            user=self.user,
            action=action,
            message='Login failed',
            success=False,
            error_message='Invalid credentials',
            status_code=401,
        )
        self.assertFalse(log.success)
        self.assertEqual(log.status_code, 401)

    def test_audit_log_config(self):
        from api.audit_logs.models import AuditLogConfig
        config, _ = AuditLogConfig.objects.get_or_create(
            pk=1, defaults={'retention_days': 90}
        )
        self.assertIsNotNone(config)