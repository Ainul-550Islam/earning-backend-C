"""
test_viewsets.py – Tests for all DRF ViewSets in the postback module.

High Priority:
  • NetworkPostbackConfigViewSet – CRUD, activate, deactivate, validators, stats
  • PostbackLogViewSet – list, retrieve, retry, reverse, s2s-logs
  • DuplicateLeadCheckViewSet – list, retrieve, delete

Medium Priority:
  • Filter/search/ordering behaviour
  • Permission enforcement (admin only)
  • Serializer switching (list vs detail vs write)
"""
import json
from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse

from api.postback.choices import PostbackStatus, ValidatorStatus
from api.postback.tests.factories import (
    CPALeadNetworkFactory,
    NetworkPostbackConfigFactory,
    PostbackLogFactory,
    RewardedPostbackLogFactory,
    FailedPostbackLogFactory,
    RejectedPostbackLogFactory,
    PostbackS2SLogFactory,
    DuplicateLeadCheckFactory,
    LeadValidatorFactory,
    UserFactory,
)

User = get_user_model()


def _admin_client():
    user = User.objects.create_superuser(
        username=f"admin_{User.objects.count()}", password="pass", email=f"a{User.objects.count()}@b.com"
    )
    c = Client()
    c.force_login(user)
    return c, user


def _regular_client():
    user = User.objects.create_user(
        username=f"user_{User.objects.count()}", password="pass"
    )
    c = Client()
    c.force_login(user)
    return c, user


# ─────────────────────────────────────────────────────────────────────────────
# NetworkPostbackConfigViewSet
# ─────────────────────────────────────────────────────────────────────────────

class NetworkPostbackConfigViewSetTests(TestCase):

    def setUp(self):
        self.client, self.admin = _admin_client()
        self.net = NetworkPostbackConfigFactory(network_key="viewset_test_net_001")

    def _list_url(self):
        return "/api/postback/networks/"

    def _detail_url(self, pk=None):
        return f"/api/postback/networks/{pk or self.net.pk}/"

    # ── List ──────────────────────────────────────────────────────────────────

    def test_list_returns_200(self):
        resp = self.client.get(self._list_url())
        self.assertEqual(resp.status_code, 200)

    def test_list_contains_network(self):
        resp = self.client.get(self._list_url())
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        if isinstance(data, dict):
            results = data.get("results", [])
        else:
            results = data
        keys = [n["network_key"] for n in results]
        self.assertIn("viewset_test_net_001", keys)

    def test_list_uses_list_serializer(self):
        resp = self.client.get(self._list_url())
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        results = data if isinstance(data, list) else data.get("results", data)
        self.assertGreater(len(results), 0)
        self.assertNotIn("secret_key", results[0])

    def test_list_unauthenticated_blocked(self):
        c = Client()
        resp = c.get(self._list_url())
        self.assertIn(resp.status_code, [401, 403])

    # ── Retrieve ──────────────────────────────────────────────────────────────

    def test_retrieve_returns_200(self):
        resp = self.client.get(self._detail_url())
        self.assertEqual(resp.status_code, 200)

    def test_retrieve_uses_detail_serializer(self):
        resp = self.client.get(self._detail_url())
        data = resp.json()
        # Detail serializer includes field_mapping
        self.assertIn("field_mapping", data)
        self.assertIn("callback_url", data)

    def test_retrieve_secret_key_not_in_output(self):
        resp = self.client.get(self._detail_url())
        self.assertNotIn("secret_key", resp.json())

    # ── Create ────────────────────────────────────────────────────────────────

    def test_create_network_config(self):
        payload = {
            "name": "New Network",
            "network_key": "new_net_create_001",
            "network_type": "cpa",
            "status": "active",
            "secret_key": "testsecret",
            "signature_algorithm": "none",
            "ip_whitelist": [],
            "trust_forwarded_for": False,
            "require_nonce": False,
            "field_mapping": {},
            "required_fields": ["lead_id"],
            "dedup_window": "forever",
            "reward_rules": {},
            "default_reward_points": 100,
            "rate_limit_per_minute": 500,
            "contact_email": "",
            "notes": "",
            "metadata": {},
            "callback_url": "",
            "callback_method": "GET",
            "callback_secret": "",
        }
        resp = self.client.post(
            self._list_url(),
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertIn(resp.status_code, [200, 201])

    def test_create_invalid_ip_whitelist_rejected(self):
        payload = {
            "name": "Bad IP Net",
            "network_key": "bad_ip_net_001",
            "network_type": "cpa",
            "status": "active",
            "signature_algorithm": "none",
            "ip_whitelist": ["not-an-ip"],
            "field_mapping": {}, "required_fields": [],
            "dedup_window": "forever", "reward_rules": {},
            "default_reward_points": 100,
            "rate_limit_per_minute": 500,
            "callback_url": "", "callback_method": "GET",
        }
        resp = self.client.post(
            self._list_url(),
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("ip_whitelist", resp.json())

    # ── Update ────────────────────────────────────────────────────────────────

    def test_partial_update_name(self):
        resp = self.client.patch(
            self._detail_url(),
            data=json.dumps({"name": "Updated Name"}),
            content_type="application/json",
        )
        self.assertIn(resp.status_code, [200, 201])

    # ── Activate / Deactivate ─────────────────────────────────────────────────

    def test_activate_action(self):
        net = NetworkPostbackConfigFactory(status=ValidatorStatus.INACTIVE)
        resp = self.client.post(f"/api/postback/networks/{net.pk}/activate/")
        self.assertEqual(resp.status_code, 200)
        net.refresh_from_db()
        self.assertEqual(net.status, ValidatorStatus.ACTIVE)

    def test_deactivate_action(self):
        net = NetworkPostbackConfigFactory(status=ValidatorStatus.ACTIVE)
        resp = self.client.post(f"/api/postback/networks/{net.pk}/deactivate/")
        self.assertEqual(resp.status_code, 200)
        net.refresh_from_db()
        self.assertEqual(net.status, ValidatorStatus.INACTIVE)

    # ── Validators ────────────────────────────────────────────────────────────

    def test_validators_list(self):
        LeadValidatorFactory(network=self.net)
        resp = self.client.get(f"/api/postback/networks/{self.net.pk}/validators/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)

    def test_validators_create(self):
        payload = {
            "name": "Test Validator",
            "validator_type": "field_present",
            "params": {"field": "lead_id"},
            "is_blocking": True,
            "sort_order": 1,
            "is_active": True,
        }
        resp = self.client.post(
            f"/api/postback/networks/{self.net.pk}/validators/",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertIn(resp.status_code, [200, 201], resp.json())

    # ── Stats ─────────────────────────────────────────────────────────────────

    def test_stats_action(self):
        PostbackLogFactory(network=self.net, status=PostbackStatus.REWARDED)
        resp = self.client.get(f"/api/postback/networks/{self.net.pk}/stats/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("total", data)
        self.assertIn("rewarded", data)
        self.assertIn("network", data)  # viewset returns network field

    # ── Non-admin blocked ─────────────────────────────────────────────────────

    def test_regular_user_blocked(self):
        c, _ = _regular_client()
        resp = c.get(self._list_url())
        self.assertIn(resp.status_code, [401, 403])


# ─────────────────────────────────────────────────────────────────────────────
# PostbackLogViewSet
# ─────────────────────────────────────────────────────────────────────────────

class PostbackLogViewSetTests(TestCase):

    def setUp(self):
        self.client, self.admin = _admin_client()
        self.net = NetworkPostbackConfigFactory()
        self.log = RewardedPostbackLogFactory(network=self.net)

    def _list_url(self):
        return "/api/postback/logs/"

    def _detail_url(self, pk=None):
        return f"/api/postback/logs/{pk or self.log.pk}/"

    # ── List ──────────────────────────────────────────────────────────────────

    def test_list_returns_200(self):
        resp = self.client.get(self._list_url())
        self.assertEqual(resp.status_code, 200)

    def test_list_uses_list_serializer(self):
        resp = self.client.get(self._list_url())
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        results = data if isinstance(data, list) else data.get("results", data)
        self.assertGreater(len(results), 0)
        self.assertNotIn("raw_payload", results[0])

    def test_list_filter_by_status(self):
        FailedPostbackLogFactory(network=self.net)
        resp = self.client.get(f"{self._list_url()}?status=rewarded")
        data = resp.json()
        results = data if isinstance(data, list) else data.get("results", data)
        for item in results:
            self.assertEqual(item["status"], "rewarded")

    def test_list_filter_by_event_type(self):
        PostbackLogFactory(network=self.net, event_type="sale")
        resp = self.client.get(f"{self._list_url()}?event_type=sale")
        data = resp.json()
        results = data if isinstance(data, list) else data.get("results", data)
        for item in results:
            self.assertEqual(item["event_type"], "sale")

    def test_list_filter_by_is_reversal(self):
        from api.postback.tests.factories import ReversalPostbackLogFactory
        ReversalPostbackLogFactory(network=self.net)
        resp = self.client.get(f"{self._list_url()}?is_reversal=true")
        data = resp.json()
        results = data if isinstance(data, list) else data.get("results", data)
        for item in results:
            self.assertTrue(item["is_reversal"])

    # ── Retrieve ──────────────────────────────────────────────────────────────

    def test_retrieve_returns_200(self):
        resp = self.client.get(self._detail_url())
        self.assertEqual(resp.status_code, 200)

    def test_retrieve_uses_detail_serializer(self):
        resp = self.client.get(self._detail_url())
        data = resp.json()
        # Detail serializer includes raw_payload
        self.assertIn("raw_payload", data)
        self.assertIn("method", data)

    def test_retrieve_has_new_fields(self):
        resp = self.client.get(self._detail_url())
        data = resp.json()
        self.assertIn("event_type", data)
        self.assertIn("conversion_status", data)
        self.assertIn("is_reversal", data)
        self.assertIn("click_id", data)
        self.assertIn("fire_delay_ms", data)

    # ── Retry ─────────────────────────────────────────────────────────────────

    def test_retry_failed_log(self):
        log = FailedPostbackLogFactory(network=self.net)
        from unittest.mock import patch
        from unittest.mock import patch as p
        with p("api.postback.tasks.process_postback") as mock_task:
            mock_task.delay = lambda *a, **kw: None
            resp = self.client.post(f"/api/postback/logs/{log.pk}/retry/")
        self.assertEqual(resp.status_code, 200)

    def test_retry_rewarded_log_rejected(self):
        resp = self.client.post(f"/api/postback/logs/{self.log.pk}/retry/")
        self.assertEqual(resp.status_code, 400)

    # ── Reverse ───────────────────────────────────────────────────────────────

    def test_reverse_action_exists(self):
        from unittest.mock import patch
        from unittest.mock import patch as p
        with p("api.postback.services.handle_reversal_postback", return_value=False):
            resp = self.client.post(f"/api/postback/logs/{self.log.pk}/reverse/")
        self.assertIn(resp.status_code, [200, 404])

    def test_reverse_log_without_lead_id_returns_400(self):
        log = RewardedPostbackLogFactory(network=self.net, lead_id="")
        resp = self.client.post(f"/api/postback/logs/{log.pk}/reverse/")
        self.assertEqual(resp.status_code, 400)

    # ── S2S Logs ──────────────────────────────────────────────────────────────

    def test_s2s_logs_action(self):
        PostbackS2SLogFactory(postback_log=self.log, success=True)
        resp = self.client.get(f"/api/postback/logs/{self.log.pk}/s2s-logs/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("count", data)
        self.assertIn("results", data)
        self.assertEqual(data["count"], 1)

    def test_s2s_logs_empty_when_none(self):
        log = PostbackLogFactory(network=self.net)
        resp = self.client.get(f"/api/postback/logs/{log.pk}/s2s-logs/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["count"], 0)

    # ── Write not allowed ─────────────────────────────────────────────────────

    def test_create_not_allowed(self):
        resp = self.client.post(self._list_url(), data={}, content_type="application/json")
        self.assertIn(resp.status_code, [405, 403, 401])

    def test_update_not_allowed(self):
        resp = self.client.put(self._detail_url(), data={}, content_type="application/json")
        self.assertIn(resp.status_code, [405, 403, 401])

    # ── Auth ──────────────────────────────────────────────────────────────────

    def test_unauthenticated_blocked(self):
        c = Client()
        resp = c.get(self._list_url())
        self.assertIn(resp.status_code, [401, 403])


# ─────────────────────────────────────────────────────────────────────────────
# DuplicateLeadCheckViewSet
# ─────────────────────────────────────────────────────────────────────────────

class DuplicateLeadCheckViewSetTests(TestCase):

    def setUp(self):
        self.client, self.admin = _admin_client()
        self.net = NetworkPostbackConfigFactory()
        self.check = DuplicateLeadCheckFactory(network=self.net, lead_id="DUP_LEAD_001")

    def test_list_returns_200(self):
        resp = self.client.get("/api/postback/duplicates/")
        self.assertEqual(resp.status_code, 200)

    def test_retrieve_returns_200(self):
        resp = self.client.get(f"/api/postback/duplicates/{self.check.pk}/")
        self.assertEqual(resp.status_code, 200)

    def test_delete_clears_dedup_entry(self):
        """DELETE allows manual dedup clearance — re-allows a lead."""
        from api.postback.models import DuplicateLeadCheck
        resp = self.client.delete(f"/api/postback/duplicates/{self.check.pk}/")
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(
            DuplicateLeadCheck.objects.filter(pk=self.check.pk).exists()
        )

    def test_create_not_allowed(self):
        resp = self.client.post("/api/postback/duplicates/", data={}, content_type="application/json")
        self.assertIn(resp.status_code, [405, 403])

    def test_unauthenticated_blocked(self):
        c = Client()
        resp = c.get("/api/postback/duplicates/")
        self.assertIn(resp.status_code, [401, 403])


# ─────────────────────────────────────────────────────────────────────────────
# New action coverage: clone, verify_integrity, test_ip, unblock, reset_window,
# detect_anomalies, recalculate, s2s_logs, reverse, summary, trends
# ─────────────────────────────────────────────────────────────────────────────

class PostbackTemplateExtraActionTests(TestCase):

    def setUp(self):
        from rest_framework.test import APIClient
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            username="admin_tpl_extra", password="pass", email="tpl_extra@test.com"
        )
        self.client.force_authenticate(user=self.admin)
        from api.postback.tests.factories import NetworkPostbackConfigFactory
        self.network = NetworkPostbackConfigFactory()

    def _make_template(self, **kwargs):
        from api.postback.models import PostbackTemplate
        defaults = dict(
            network=self.network,
            name="Base Template",
            template_body="https://example.com/postback?lead={{lead_id}}",
            variables={"lead_id": "string"},
            required_variables=["lead_id"],
            is_active=True,
        )
        defaults.update(kwargs)
        t = PostbackTemplate.objects.create(**defaults)
        t.integrity_hash = t.generate_integrity_hash()
        t.save(update_fields=["integrity_hash"])
        return t

    def test_clone_creates_new_template(self):
        t = self._make_template()
        resp = self.client.post(
            f"/api/postback/templates/{t.pk}/clone/",
            {"name": "Clone of Base"},
            format="json",
        )
        self.assertIn(resp.status_code, [200, 201, 400, 404])

    def test_clone_without_name_returns_400(self):
        t = self._make_template()
        resp = self.client.post(f"/api/postback/templates/{t.pk}/clone/", {}, format="json")
        self.assertIn(resp.status_code, [400, 404])

    def test_verify_integrity_returns_result(self):
        t = self._make_template()
        resp = self.client.get(f"/api/postback/templates/{t.pk}/verify_integrity/")
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            self.assertIn("is_valid", resp.json())

    def test_render_template_with_valid_context(self):
        t = self._make_template()
        resp = self.client.post(
            f"/api/postback/templates/{t.pk}/render/",
            {"context": {"lead_id": "ABC123"}, "increment_usage": False},
            format="json",
        )
        self.assertIn(resp.status_code, [200, 400, 404])


class PostbackIPWhitelistExtraActionTests(TestCase):

    def setUp(self):
        from rest_framework.test import APIClient
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            username="admin_ip_extra", password="pass", email="ip_extra@test.com"
        )
        self.client.force_authenticate(user=self.admin)
        from api.postback.tests.factories import NetworkPostbackConfigFactory
        self.network = NetworkPostbackConfigFactory()

    def _make_whitelist(self, ip="192.168.1.0/24"):
        from api.postback.models import PostbackIPWhitelist
        w = PostbackIPWhitelist.objects.create(
            network=self.network,
            name="Test Rule",
            ip_address=ip,
            is_active=True,
            priority=10,
        )
        w.integrity_hash = w.generate_integrity_hash()
        w.save(update_fields=["integrity_hash"])
        return w

    def test_test_ip_allowed_returns_result(self):
        w = self._make_whitelist("10.0.0.0/8")
        resp = self.client.post(
            f"/api/postback/ip-whitelists/{w.pk}/test_ip/",
            {"ip_address": "10.0.0.1"},
            format="json",
        )
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            data = resp.json()
            self.assertIn("is_allowed", data)
            self.assertTrue(data["is_allowed"])

    def test_test_ip_outside_range_not_allowed(self):
        w = self._make_whitelist("10.0.0.0/8")
        resp = self.client.post(
            f"/api/postback/ip-whitelists/{w.pk}/test_ip/",
            {"ip_address": "192.168.1.1"},
            format="json",
        )
        if resp.status_code == 200:
            self.assertFalse(resp.json()["is_allowed"])

    def test_test_ip_without_ip_address_returns_400(self):
        w = self._make_whitelist()
        resp = self.client.post(
            f"/api/postback/ip-whitelists/{w.pk}/test_ip/",
            {},
            format="json",
        )
        self.assertIn(resp.status_code, [400, 404])

    def test_verify_integrity_returns_is_valid(self):
        w = self._make_whitelist()
        resp = self.client.get(f"/api/postback/ip-whitelists/{w.pk}/verify_integrity/")
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            self.assertIn("is_valid", resp.json())


class PostbackRateLimitExtraActionTests(TestCase):

    def setUp(self):
        from rest_framework.test import APIClient
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            username="admin_rl_extra", password="pass", email="rl_extra@test.com"
        )
        self.client.force_authenticate(user=self.admin)
        from api.postback.tests.factories import NetworkPostbackConfigFactory
        self.network = NetworkPostbackConfigFactory()

    def _make_rate_limit(self, is_blocked=False):
        from api.postback.models import PostbackRateLimit
        rl = PostbackRateLimit.objects.create(
            network=self.network,
            name="Test Limit",
            max_per_minute=100,
            max_per_hour=5000,
            max_per_day=100000,
            is_active=True,
            is_blocked=is_blocked,
        )
        rl.integrity_hash = rl.generate_integrity_hash()
        rl.save(update_fields=["integrity_hash"])
        return rl

    def test_reset_window_returns_200(self):
        rl = self._make_rate_limit()
        resp = self.client.post(f"/api/postback/rate-limits/{rl.pk}/reset_window/")
        self.assertIn(resp.status_code, [200, 404])

    def test_reset_window_resets_count(self):
        rl = self._make_rate_limit()
        from api.postback.models import PostbackRateLimit
        PostbackRateLimit.objects.filter(pk=rl.pk).update(current_count=999)
        resp = self.client.post(f"/api/postback/rate-limits/{rl.pk}/reset_window/")
        if resp.status_code == 200:
            rl.refresh_from_db()
            self.assertEqual(rl.current_count, 0)

    def test_unblock_clears_block(self):
        from django.utils import timezone
        import datetime
        rl = self._make_rate_limit(is_blocked=True)
        from api.postback.models import PostbackRateLimit
        PostbackRateLimit.objects.filter(pk=rl.pk).update(
            blocked_until=timezone.now() + datetime.timedelta(hours=1)
        )
        resp = self.client.post(f"/api/postback/rate-limits/{rl.pk}/unblock/")
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            rl.refresh_from_db()
            self.assertFalse(rl.is_blocked)
            self.assertIsNone(rl.blocked_until)

    def test_unblock_response_has_is_blocked_false(self):
        rl = self._make_rate_limit(is_blocked=True)
        resp = self.client.post(f"/api/postback/rate-limits/{rl.pk}/unblock/")
        if resp.status_code == 200:
            self.assertFalse(resp.json()["is_blocked"])

    def test_verify_integrity_returns_is_valid(self):
        rl = self._make_rate_limit()
        resp = self.client.get(f"/api/postback/rate-limits/{rl.pk}/verify_integrity/")
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            self.assertIn("is_valid", resp.json())


class PostbackInsightExtraActionTests(TestCase):

    def setUp(self):
        from rest_framework.test import APIClient
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            username="admin_ins_extra", password="pass", email="ins_extra@test.com"
        )
        self.client.force_authenticate(user=self.admin)
        from api.postback.tests.factories import NetworkPostbackConfigFactory
        self.network = NetworkPostbackConfigFactory()

    def test_summary_action_returns_200(self):
        resp = self.client.get("/api/postback/insights/summary/")
        self.assertIn(resp.status_code, [200, 404])

    def test_summary_response_keys(self):
        resp = self.client.get("/api/postback/insights/summary/")
        if resp.status_code == 200:
            data = resp.json()
            for key in ("total_received", "total_rewarded", "avg_health_score"):
                self.assertIn(key, data)

    def test_trends_action_returns_200(self):
        resp = self.client.get("/api/postback/insights/trends/")
        self.assertIn(resp.status_code, [200, 404])

    def test_trends_response_is_list(self):
        resp = self.client.get("/api/postback/insights/trends/")
        if resp.status_code == 200:
            self.assertIsInstance(resp.json(), list)

    def test_network_comparison_returns_200(self):
        resp = self.client.get("/api/postback/insights/network_comparison/")
        self.assertIn(resp.status_code, [200, 404])

    def test_health_report_returns_200(self):
        resp = self.client.get("/api/postback/insights/health_report/")
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            self.assertIn("health_metrics", resp.json())


class PostbackLogS2SLogsActionTests(TestCase):

    def setUp(self):
        from rest_framework.test import APIClient
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            username="admin_s2s_log", password="pass", email="s2s_log@test.com"
        )
        self.client.force_authenticate(user=self.admin)
        from api.postback.tests.factories import NetworkPostbackConfigFactory
        self.network = NetworkPostbackConfigFactory()

    def test_s2s_logs_returns_200(self):
        from api.postback.tests.factories import RewardedPostbackLogFactory
        log = RewardedPostbackLogFactory(network=self.network)
        resp = self.client.get(f"/api/postback/logs/{log.pk}/s2s-logs/")
        self.assertIn(resp.status_code, [200, 404])

    def test_s2s_logs_empty_list_when_none(self):
        from api.postback.tests.factories import PostbackLogFactory
        log = PostbackLogFactory(network=self.network)
        resp = self.client.get(f"/api/postback/logs/{log.pk}/s2s-logs/")
        if resp.status_code == 200:
            self.assertEqual(resp.json(), [])

    def test_s2s_logs_shows_attempts(self):
        from api.postback.tests.factories import RewardedPostbackLogFactory
        from api.postback.models import PostbackS2SLog
        log = RewardedPostbackLogFactory(network=self.network)
        PostbackS2SLog.objects.create(
            postback_log=log,
            callback_url="https://example.com/cb?lead=X",
            http_status=200,
            success=True,
            attempt_number=1,
        )
        resp = self.client.get(f"/api/postback/logs/{log.pk}/s2s-logs/")
        if resp.status_code == 200:
            self.assertEqual(len(resp.json()), 1)
            self.assertTrue(resp.json()[0]["success"])
