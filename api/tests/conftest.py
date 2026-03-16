# api/tests/conftest.py - Shared Test Fixtures & Helpers
# python manage.py test api.tests --keepdb

from django.test import TestCase
from django.contrib.auth import get_user_model
from decimal import Decimal
import uuid

User = get_user_model()


class BaseTestCase(TestCase):
    """সব test এর base class - common fixtures"""

    @classmethod
    def setUpTestData(cls):
        # ============ USERS ============
        cls.admin_user = User.objects.create_superuser(
            username='admin_test',
            email='admin@test.com',
            password='Admin@12345'
        )
        cls.regular_user = User.objects.create_user(
            username='user_test',
            email='user@test.com',
            password='User@12345'
        )
        cls.user2 = User.objects.create_user(
            username='user2_test',
            email='user2@test.com',
            password='User@12345'
        )

    def login_admin(self):
        self.client.force_login(self.admin_user)

    def login_user(self):
        self.client.force_login(self.regular_user)

    def login_user2(self):
        self.client.force_login(self.user2)


class BaseAPITestCase(TestCase):
    """DRF API test এর base class"""

    def setUp(self):
        from rest_framework.test import APIClient
        self.client = APIClient()
        self.admin_user = User.objects.create_superuser(
            username=f'admin_{uuid.uuid4().hex[:6]}',
            email=f'admin_{uuid.uuid4().hex[:6]}@test.com',
            password='Admin@12345'
        )
        self.regular_user = User.objects.create_user(
            username=f'user_{uuid.uuid4().hex[:6]}',
            email=f'user_{uuid.uuid4().hex[:6]}@test.com',
            password='User@12345'
        )

    def authenticate_admin(self):
        self.client.force_authenticate(user=self.admin_user)

    def authenticate_user(self):
        self.client.force_authenticate(user=self.regular_user)

    def logout(self):
        self.client.force_authenticate(user=None)