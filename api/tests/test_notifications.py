# api/tests/test_notifications.py
from django.test import TestCase
from django.contrib.auth import get_user_model
import uuid

User = get_user_model()
def uid(): return uuid.uuid4().hex[:8]


class NotificationTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username=f'u_{uid()}', email=f'{uid()}@test.com', password='x'
        )

    def test_notification_creation(self):
        from api.notifications.models import Notification
        notif = Notification.objects.create(user=self.user, title='Welcome!', message='Welcome.', is_read=False)
        self.assertFalse(notif.is_read)

    def test_mark_notification_read(self):
        from api.notifications.models import Notification
        notif = Notification.objects.create(user=self.user, title='Test', message='Test message', is_read=False)
        notif.is_read = True
        notif.save()
        notif.refresh_from_db()
        self.assertTrue(notif.is_read)