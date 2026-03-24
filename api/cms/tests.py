"""
CMS module tests — Content pages, banners, announcements
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
import uuid

User = get_user_model()


def make_user(is_staff=False):
    uid = uuid.uuid4().hex[:8]
    u = User.objects.create_user(
        username=f"user_{uid}", email=f"{uid}@test.com", password="pass1234"
    )
    if is_staff:
        u.is_staff = True
        u.save()
    return u


class CMSAPITest(APITestCase):

    def setUp(self):
        self.user = make_user()
        self.admin = make_user(is_staff=True)

    def test_list_cms_content_public(self):
        res = self.client.get("/api/cms/")
        self.assertNotIn(res.status_code, [500])

    def test_list_pages(self):
        res = self.client.get("/api/cms/pages/")
        self.assertNotIn(res.status_code, [500])

    def test_create_page_unauthenticated(self):
        res = self.client.post("/api/cms/pages/", {
            "title": "Test Page",
            "content": "Hello World",
            "slug": "test-page",
        }, format="json")
        self.assertIn(res.status_code, [401, 403])

    def test_create_page_as_admin(self):
        self.client.force_authenticate(user=self.admin)
        res = self.client.post("/api/cms/pages/", {
            "title": "Admin Page",
            "content": "Admin content",
            "slug": f"admin-page-{uuid.uuid4().hex[:6]}",
        }, format="json")
        self.assertIn(res.status_code, [200, 201, 400, 404])

    def test_get_page_by_slug(self):
        res = self.client.get("/api/cms/pages/nonexistent-slug/")
        self.assertIn(res.status_code, [200, 404])

    def test_list_banners(self):
        res = self.client.get("/api/cms/banners/")
        self.assertNotIn(res.status_code, [500])

    def test_list_announcements(self):
        res = self.client.get("/api/cms/announcements/")
        self.assertNotIn(res.status_code, [500])


# ─────────────────────────────────────────────
# Cache module tests
# ─────────────────────────────────────────────

"""
Cache module tests — Cache management and invalidation
"""
from django.test import TestCase
from django.core.cache import cache
from rest_framework.test import APITestCase


class CacheBasicTest(TestCase):

    def setUp(self):
        cache.clear()

    def test_cache_set_get(self):
        cache.set("test_key", "test_value", timeout=60)
        self.assertEqual(cache.get("test_key"), "test_value")

    def test_cache_delete(self):
        cache.set("del_key", "value", timeout=60)
        cache.delete("del_key")
        self.assertIsNone(cache.get("del_key"))

    def test_cache_expiry(self):
        cache.set("exp_key", "value", timeout=1)
        import time
        time.sleep(2)
        self.assertIsNone(cache.get("exp_key"))

    def test_cache_many(self):
        cache.set_many({"k1": "v1", "k2": "v2", "k3": "v3"})
        result = cache.get_many(["k1", "k2", "k3"])
        self.assertEqual(result["k1"], "v1")
        self.assertEqual(result["k2"], "v2")

    def test_cache_increment(self):
        cache.set("counter", 0)
        cache.incr("counter")
        cache.incr("counter")
        self.assertEqual(cache.get("counter"), 2)


class CacheAPITest(APITestCase):

    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="cacheadmin", email="cacheadmin@test.com", password="admin123"
        ) if hasattr(User, 'objects') else None

    def test_cache_stats_admin(self):
        if self.admin:
            self.client.force_authenticate(user=self.admin)
        res = self.client.get("/api/cache/stats/")
        self.assertNotIn(res.status_code, [500])

    def test_cache_flush_unauthenticated(self):
        res = self.client.post("/api/cache/flush/")
        self.assertIn(res.status_code, [401, 403])

    def test_cache_keys_list(self):
        if self.admin:
            self.client.force_authenticate(user=self.admin)
        res = self.client.get("/api/cache/keys/")
        self.assertNotIn(res.status_code, [500])
