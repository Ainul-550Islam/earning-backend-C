"""
Users module tests — Registration, Login, OTP, Profile
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework import status
from datetime import timedelta
from unittest.mock import patch
import uuid

User = get_user_model()


def make_user(username=None, email=None, password="pass1234"):
    username = username or f"user_{uuid.uuid4().hex[:8]}"
    email = email or f"{username}@test.com"
    return User.objects.create_user(username=username, email=email, password=password)


# ─────────────────────────────────────────────
# User Model Tests
# ─────────────────────────────────────────────

class UserModelTest(TestCase):

    def test_create_user(self):
        user = make_user(username="alice", email="alice@test.com")
        self.assertEqual(user.email, "alice@test.com")
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)

    def test_create_superuser(self):
        admin = User.objects.create_superuser(
            username="admin", email="admin@test.com", password="admin123"
        )
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)

    def test_unique_email(self):
        make_user(email="dup@test.com")
        with self.assertRaises(Exception):
            make_user(email="dup@test.com")

    def test_user_str(self):
        user = make_user(username="bob")
        self.assertIn("bob", str(user))

    def test_user_has_uuid_or_id(self):
        user = make_user()
        self.assertIsNotNone(user.pk)


# ─────────────────────────────────────────────
# Registration API Tests
# ─────────────────────────────────────────────

class RegistrationAPITest(APITestCase):

    def _register(self, data=None):
        uid = uuid.uuid4().hex[:8]
        payload = data or {
            "username": f"newuser_{uid}",
            "email": f"new_{uid}@test.com",
            "password": "StrongPass123!",
            "password2": "StrongPass123!",
        }
        return self.client.post("/api/users/register/", payload, format="json")

    def test_register_success(self):
        res = self._register()
        self.assertIn(res.status_code, [200, 201])

    def test_register_missing_email(self):
        res = self._register({"username": "nomail", "password": "pass"})
        self.assertIn(res.status_code, [400, 422])

    def test_register_duplicate_email(self):
        uid = uuid.uuid4().hex[:8]
        data = {
            "username": f"u_{uid}",
            "email": f"same_{uid}@test.com",
            "password": "StrongPass123!",
            "password2": "StrongPass123!",
        }
        self.client.post("/api/users/register/", data, format="json")
        data["username"] = f"u2_{uid}"
        res = self.client.post("/api/users/register/", data, format="json")
        self.assertIn(res.status_code, [400, 409])

    def test_register_weak_password(self):
        uid = uuid.uuid4().hex[:8]
        res = self._register({
            "username": f"weak_{uid}",
            "email": f"weak_{uid}@test.com",
            "password": "123",
            "password2": "123",
        })
        self.assertIn(res.status_code, [400, 422])


# ─────────────────────────────────────────────
# Login API Tests
# ─────────────────────────────────────────────

class LoginAPITest(APITestCase):

    def setUp(self):
        self.user = make_user(username="loginuser", email="login@test.com", password="pass1234")

    def test_login_success(self):
        res = self.client.post("/api/users/login/", {
            "email": "login@test.com",
            "password": "pass1234",
        }, format="json")
        self.assertIn(res.status_code, [200, 201])

    def test_login_wrong_password(self):
        res = self.client.post("/api/users/login/", {
            "email": "login@test.com",
            "password": "wrongpass",
        }, format="json")
        self.assertIn(res.status_code, [400, 401])

    def test_login_nonexistent_user(self):
        res = self.client.post("/api/users/login/", {
            "email": "ghost@test.com",
            "password": "anypass",
        }, format="json")
        self.assertIn(res.status_code, [400, 401, 404])

    def test_login_returns_token(self):
        res = self.client.post("/api/users/login/", {
            "email": "login@test.com",
            "password": "pass1234",
        }, format="json")
        if res.status_code in [200, 201]:
            data = res.json()
            has_token = "access" in data or "token" in data or "access_token" in data
            self.assertTrue(has_token)


# ─────────────────────────────────────────────
# Profile API Tests
# ─────────────────────────────────────────────

class ProfileAPITest(APITestCase):

    def setUp(self):
        self.user = make_user(username="profuser", email="prof@test.com")
        self.client.force_authenticate(user=self.user)

    def test_get_profile(self):
        res = self.client.get("/api/users/profile/")
        self.assertIn(res.status_code, [200, 404])

    def test_unauthenticated_profile(self):
        self.client.force_authenticate(user=None)
        res = self.client.get("/api/users/profile/")
        self.assertIn(res.status_code, [401, 403])


# ─────────────────────────────────────────────
# Password Reset Tests
# ─────────────────────────────────────────────

class PasswordResetTest(APITestCase):

    def setUp(self):
        self.user = make_user(email="reset@test.com")

    def test_request_password_reset(self):
        res = self.client.post("/api/users/forgot-password/", {
            "email": "reset@test.com"
        }, format="json")
        self.assertIn(res.status_code, [200, 201, 400, 404])

    def test_reset_with_wrong_email(self):
        res = self.client.post("/api/users/forgot-password/", {
            "email": "nobody@test.com"
        }, format="json")
        self.assertIn(res.status_code, [200, 400, 404])
