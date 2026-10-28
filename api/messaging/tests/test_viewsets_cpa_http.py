"""
test_viewsets_cpa_http.py
==========================
HTTP-level coverage for the 4 CPA REST viewsets, which previously had ZERO
test coverage at the controller layer (permissions, status codes, request
parsing, response shape) despite the underlying service-layer logic being
tested in test_cpa.py / test_services_cpa_missing.py.

Covers:
  CPANotificationViewSet  — list, counts, mark_read, mark_all_read,
                            dismiss, dismiss_all
  CPABroadcastViewSet     — list, send, schedule, analytics,
                            track_open, track_click, cancel
  MessageTemplateViewSet  — list, create, retrieve, destroy,
                            preview, send_to_user
  AffiliateThreadViewSet  — list, get_or_create_my_thread,
                            reassign_manager, add_tags, add_note

Place in: messaging/tests/test_viewsets_cpa_http.py
"""
from __future__ import annotations

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .factories import UserFactory
from ..models import (
    AffiliateConversationThread,
    CPABroadcast,
    CPANotification,
    MessageTemplate,
)


def _api(user=None) -> APIClient:
    client = APIClient()
    if user:
        client.force_authenticate(user=user)
    return client


def _admin():
    return UserFactory(is_staff=True, is_superuser=True)


# ─────────────────────────────────────────────────────────────────────────────
# CPANotificationViewSet
# ─────────────────────────────────────────────────────────────────────────────

class TestCPANotificationViewSetHTTP(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.other = UserFactory()
        self.n1 = CPANotification.objects.create(
            recipient=self.user, notification_type="offer.approved",
            title="Offer approved", body="Your offer was approved.",
        )
        self.n2 = CPANotification.objects.create(
            recipient=self.user, notification_type="payout.processed",
            title="Payout sent", body="Your payout was processed.",
        )

    def test_list_requires_auth(self):
        r = _api().get("/messaging/notifications/")
        self.assertEqual(r.status_code, 403)

    def test_list_returns_own_notifications_only(self):
        CPANotification.objects.create(
            recipient=self.other, notification_type="offer.approved",
            title="Not yours", body="x",
        )
        r = _api(self.user).get("/messaging/notifications/")
        self.assertEqual(r.status_code, 200)
        ids = {item["id"] for item in r.data["results"]}
        self.assertEqual(ids, {str(self.n1.id), str(self.n2.id)})

    def test_list_filters_by_type_category(self):
        r = _api(self.user).get("/messaging/notifications/?type=payments")
        self.assertEqual(r.status_code, 200)
        ids = {item["id"] for item in r.data["results"]}
        self.assertEqual(ids, {str(self.n2.id)})

    def test_list_filters_by_unread(self):
        CPANotification.objects.filter(pk=self.n1.pk).update(is_read=True)
        r = _api(self.user).get("/messaging/notifications/?unread=1")
        ids = {item["id"] for item in r.data["results"]}
        self.assertEqual(ids, {str(self.n2.id)})

    def test_counts_returns_category_breakdown(self):
        r = _api(self.user).get("/messaging/notifications/counts/")
        self.assertEqual(r.status_code, 200)
        self.assertIsInstance(r.data, dict)

    def test_mark_read_marks_single_notification(self):
        r = _api(self.user).post(f"/messaging/notifications/{self.n1.id}/mark_read/")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["marked_read"])
        self.n1.refresh_from_db()
        self.assertTrue(self.n1.is_read)

    def test_mark_read_cannot_mark_other_users_notification(self):
        other_notif = CPANotification.objects.create(
            recipient=self.other, notification_type="offer.approved",
            title="Theirs", body="x",
        )
        r = _api(self.user).post(f"/messaging/notifications/{other_notif.id}/mark_read/")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.data["marked_read"])
        other_notif.refresh_from_db()
        self.assertFalse(other_notif.is_read)

    def test_mark_all_read_marks_everything_unread(self):
        r = _api(self.user).post("/messaging/notifications/mark_all_read/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["marked_read"], 2)
        self.assertEqual(
            CPANotification.objects.filter(recipient=self.user, is_read=False).count(), 0
        )

    def test_mark_all_read_filters_by_type(self):
        r = _api(self.user).post(
            "/messaging/notifications/mark_all_read/", {"type": "payout.processed"}, format="json"
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["marked_read"], 1)
        self.n1.refresh_from_db()
        self.n2.refresh_from_db()
        self.assertFalse(self.n1.is_read)
        self.assertTrue(self.n2.is_read)

    def test_dismiss_hides_notification_from_list(self):
        r = _api(self.user).post(f"/messaging/notifications/{self.n1.id}/dismiss/")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["dismissed"])
        r2 = _api(self.user).get("/messaging/notifications/")
        ids = {item["id"] for item in r2.data["results"]}
        self.assertNotIn(str(self.n1.id), ids)

    def test_dismiss_all_dismisses_everything(self):
        CPANotification.objects.filter(recipient=self.user).update(is_read=True)
        r = _api(self.user).post("/messaging/notifications/dismiss_all/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["dismissed"], 2)
        r2 = _api(self.user).get("/messaging/notifications/")
        self.assertEqual(len(r2.data["results"]), 0)


# ─────────────────────────────────────────────────────────────────────────────
# CPABroadcastViewSet
# ─────────────────────────────────────────────────────────────────────────────

class TestCPABroadcastViewSetHTTP(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.admin = _admin()
        self.user = UserFactory()
        self.broadcast = CPABroadcast.objects.create(
            title="Q3 Promo", body="New offers live!", status="SENT",
            recipient_count=100, delivered_count=90, opened_count=40, clicked_count=10,
            created_by=self.admin,
        )

    def test_list_requires_admin(self):
        r = _api(self.user).get("/messaging/cpa-broadcasts/")
        self.assertEqual(r.status_code, 403)

    def test_list_returns_broadcasts_for_admin(self):
        r = _api(self.admin).get("/messaging/cpa-broadcasts/")
        self.assertEqual(r.status_code, 200)
        self.assertGreaterEqual(len(r.data), 1)

    def test_send_creates_broadcast_immediately(self):
        r = _api(self.admin).post(
            "/messaging/cpa-broadcasts/send/",
            {"title": "Flash sale", "body": "50% off today", "audience_filter": "all"},
            format="json",
        )
        self.assertEqual(r.status_code, 201)
        self.assertIn("id", r.data)
        self.assertTrue(CPABroadcast.objects.filter(pk=r.data["id"]).exists())

    def test_send_requires_admin(self):
        r = _api(self.user).post(
            "/messaging/cpa-broadcasts/send/", {"title": "x", "body": "y"}, format="json"
        )
        self.assertEqual(r.status_code, 403)

    def test_send_returns_400_on_service_error(self):
        # audience_filter accepts any string at the view layer (no validation),
        # but an empty title is rejected deeper in the model/clean chain — this
        # exercises the except Exception -> 400 branch.
        r = _api(self.admin).post(
            "/messaging/cpa-broadcasts/send/", {"title": "", "body": "y"}, format="json"
        )
        self.assertEqual(r.status_code, 400)

    def test_schedule_requires_scheduled_at(self):
        r = _api(self.admin).post(
            "/messaging/cpa-broadcasts/schedule/", {"title": "x", "body": "y"}, format="json"
        )
        self.assertEqual(r.status_code, 400)

    def test_schedule_creates_scheduled_broadcast(self):
        future = (timezone.now() + timezone.timedelta(days=1)).isoformat()
        r = _api(self.admin).post(
            "/messaging/cpa-broadcasts/schedule/",
            {"title": "Future promo", "body": "Coming soon", "scheduled_at": future},
            format="json",
        )
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["status"], "SCHEDULED")

    def test_analytics_returns_rates(self):
        r = _api(self.admin).get(f"/messaging/cpa-broadcasts/{self.broadcast.id}/analytics/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["recipient_count"], 100)
        self.assertEqual(r.data["delivered_count"], 90)
        self.assertIn("open_rate", r.data)
        self.assertIn("click_rate", r.data)
        self.assertEqual(r.data["delivery_rate"], 90.0)

    def test_analytics_404_for_missing_broadcast(self):
        r = _api(self.admin).get("/messaging/cpa-broadcasts/00000000-0000-0000-0000-000000000000/analytics/")
        self.assertEqual(r.status_code, 404)

    def test_track_open_authenticated_user_only(self):
        r = _api().post(f"/messaging/cpa-broadcasts/{self.broadcast.id}/track_open/")
        self.assertEqual(r.status_code, 403)

    def test_track_open_records_open(self):
        r = _api(self.user).post(f"/messaging/cpa-broadcasts/{self.broadcast.id}/track_open/")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["tracked"])
        self.broadcast.refresh_from_db()
        self.assertEqual(self.broadcast.opened_count, 41)

    def test_track_click_records_click(self):
        r = _api(self.user).post(f"/messaging/cpa-broadcasts/{self.broadcast.id}/track_click/")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["tracked"])
        self.broadcast.refresh_from_db()
        self.assertEqual(self.broadcast.clicked_count, 11)

    def test_cancel_scheduled_broadcast(self):
        scheduled = CPABroadcast.objects.create(
            title="Will cancel", body="x", status="SCHEDULED",
            scheduled_at=timezone.now() + timezone.timedelta(days=1),
        )
        r = _api(self.admin).post(f"/messaging/cpa-broadcasts/{scheduled.id}/cancel/")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["cancelled"])
        scheduled.refresh_from_db()
        self.assertEqual(scheduled.status, "CANCELLED")

    def test_cancel_already_sent_broadcast_returns_false(self):
        r = _api(self.admin).post(f"/messaging/cpa-broadcasts/{self.broadcast.id}/cancel/")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.data["cancelled"])


# ─────────────────────────────────────────────────────────────────────────────
# MessageTemplateViewSet
# ─────────────────────────────────────────────────────────────────────────────

class TestMessageTemplateViewSetHTTP(TestCase):
    def setUp(self):
        self.admin = _admin()
        self.user = UserFactory()
        self.template = MessageTemplate.objects.create(
            name="Welcome",
            category="account",
            subject="Welcome!",
            body="Hi {affiliate_name}, welcome to {platform_name}!",
            created_by=self.admin,
        )

    def test_list_requires_admin(self):
        r = _api(self.user).get("/messaging/templates/")
        self.assertEqual(r.status_code, 403)

    def test_list_returns_active_templates(self):
        r = _api(self.admin).get("/messaging/templates/")
        self.assertEqual(r.status_code, 200)
        names = [t["name"] for t in r.data]
        self.assertIn("Welcome", names)

    def test_list_excludes_inactive_templates(self):
        MessageTemplate.objects.create(
            name="Old template", body="x", is_active=False,
        )
        r = _api(self.admin).get("/messaging/templates/")
        names = [t["name"] for t in r.data]
        self.assertNotIn("Old template", names)

    def test_list_filters_by_category(self):
        MessageTemplate.objects.create(name="Payout note", category="payout", body="x")
        r = _api(self.admin).get("/messaging/templates/?category=payout")
        names = [t["name"] for t in r.data]
        self.assertEqual(names, ["Payout note"])

    def test_create_template(self):
        r = _api(self.admin).post(
            "/messaging/templates/",
            {"name": "New offer", "body": "Check out {offer_name}", "category": "offer"},
            format="json",
        )
        self.assertEqual(r.status_code, 201)
        self.assertTrue(MessageTemplate.objects.filter(name="New offer").exists())

    def test_create_rejects_empty_name(self):
        r = _api(self.admin).post(
            "/messaging/templates/", {"name": "", "body": "x"}, format="json"
        )
        self.assertEqual(r.status_code, 400)

    def test_create_rejects_invalid_category(self):
        r = _api(self.admin).post(
            "/messaging/templates/",
            {"name": "x", "body": "y", "category": "not_a_real_category"},
            format="json",
        )
        self.assertEqual(r.status_code, 400)

    def test_retrieve_returns_full_body(self):
        r = _api(self.admin).get(f"/messaging/templates/{self.template.id}/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["body"], self.template.body)

    def test_retrieve_404_for_missing_template(self):
        r = _api(self.admin).get("/messaging/templates/00000000-0000-0000-0000-000000000000/")
        self.assertEqual(r.status_code, 404)

    def test_destroy_deactivates_template(self):
        r = _api(self.admin).delete(f"/messaging/templates/{self.template.id}/")
        self.assertEqual(r.status_code, 204)
        self.template.refresh_from_db()
        self.assertFalse(self.template.is_active)

    def test_preview_renders_with_default_context(self):
        r = _api(self.admin).post(f"/messaging/templates/{self.template.id}/preview/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("John Doe", r.data["body"])

    def test_preview_renders_with_custom_context(self):
        r = _api(self.admin).post(
            f"/messaging/templates/{self.template.id}/preview/",
            {"context": {"affiliate_name": "Naim", "platform_name": "RewardHub"}},
            format="json",
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn("Naim", r.data["body"])
        self.assertIn("RewardHub", r.data["body"])

    def test_preview_does_not_increment_usage_count(self):
        _api(self.admin).post(f"/messaging/templates/{self.template.id}/preview/")
        self.template.refresh_from_db()
        self.assertEqual(self.template.usage_count, 0)

    def test_send_to_user_requires_recipient_id(self):
        r = _api(self.admin).post(
            f"/messaging/templates/{self.template.id}/send_to_user/", {}, format="json"
        )
        self.assertEqual(r.status_code, 400)

    def test_send_to_user_sends_and_increments_usage(self):
        recipient = UserFactory()
        r = _api(self.admin).post(
            f"/messaging/templates/{self.template.id}/send_to_user/",
            {"recipient_id": recipient.pk, "context": {"affiliate_name": "Naim", "platform_name": "RH"}},
            format="json",
        )
        self.assertEqual(r.status_code, 201)
        self.assertIn("notification_id", r.data)
        self.template.refresh_from_db()
        self.assertEqual(self.template.usage_count, 1)

    def test_send_to_user_404_for_missing_template(self):
        recipient = UserFactory()
        r = _api(self.admin).post(
            "/messaging/templates/00000000-0000-0000-0000-000000000000/send_to_user/",
            {"recipient_id": recipient.pk},
            format="json",
        )
        self.assertEqual(r.status_code, 404)


# ─────────────────────────────────────────────────────────────────────────────
# AffiliateThreadViewSet
# ─────────────────────────────────────────────────────────────────────────────

class TestAffiliateThreadViewSetHTTP(TestCase):
    def setUp(self):
        self.admin = _admin()
        self.manager = UserFactory(is_staff=True)
        self.affiliate = UserFactory()
        self.other_affiliate = UserFactory()

    def _make_thread(self, affiliate, manager=None):
        from .. import services as msg_services
        chat = msg_services.create_group_chat(
            creator_id=affiliate.pk, name=f"thread-{affiliate.pk}", member_ids=[]
        )
        return AffiliateConversationThread.objects.create(
            affiliate=affiliate, manager=manager, chat=chat,
        )

    def test_list_requires_auth(self):
        r = _api().get("/messaging/affiliate-threads/")
        self.assertEqual(r.status_code, 403)

    def test_affiliate_sees_only_own_thread(self):
        mine = self._make_thread(self.affiliate, self.manager)
        self._make_thread(self.other_affiliate, self.manager)
        r = _api(self.affiliate).get("/messaging/affiliate-threads/")
        self.assertEqual(r.status_code, 200)
        ids = {t["id"] for t in r.data}
        self.assertEqual(ids, {str(mine.id)})

    def test_get_or_create_my_thread_creates_new(self):
        self.assertFalse(
            AffiliateConversationThread.objects.filter(affiliate=self.affiliate).exists()
        )
        r = _api(self.affiliate).post("/messaging/affiliate-threads/get_or_create_my_thread/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("thread_id", r.data)
        self.assertTrue(
            AffiliateConversationThread.objects.filter(affiliate=self.affiliate).exists()
        )

    def test_get_or_create_my_thread_is_idempotent(self):
        r1 = _api(self.affiliate).post("/messaging/affiliate-threads/get_or_create_my_thread/")
        r2 = _api(self.affiliate).post("/messaging/affiliate-threads/get_or_create_my_thread/")
        self.assertEqual(r1.data["thread_id"], r2.data["thread_id"])
        self.assertEqual(AffiliateConversationThread.objects.filter(affiliate=self.affiliate).count(), 1)

    def test_reassign_manager_requires_admin(self):
        thread = self._make_thread(self.affiliate, self.manager)
        new_manager = UserFactory(is_staff=True)
        r = _api(self.affiliate).post(
            f"/messaging/affiliate-threads/{thread.id}/reassign_manager/",
            {"manager_id": new_manager.pk}, format="json",
        )
        self.assertEqual(r.status_code, 403)

    def test_reassign_manager_requires_manager_id(self):
        thread = self._make_thread(self.affiliate, self.manager)
        r = _api(self.admin).post(
            f"/messaging/affiliate-threads/{thread.id}/reassign_manager/", {}, format="json"
        )
        self.assertEqual(r.status_code, 400)

    def test_reassign_manager_updates_thread(self):
        thread = self._make_thread(self.affiliate, self.manager)
        new_manager = UserFactory(is_staff=True)
        r = _api(self.admin).post(
            f"/messaging/affiliate-threads/{thread.id}/reassign_manager/",
            {"manager_id": new_manager.pk}, format="json",
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["reassigned"])
        thread.refresh_from_db()
        self.assertEqual(thread.manager_id, new_manager.pk)

    def test_reassign_manager_404_for_missing_thread(self):
        new_manager = UserFactory(is_staff=True)
        r = _api(self.admin).post(
            "/messaging/affiliate-threads/00000000-0000-0000-0000-000000000000/reassign_manager/",
            {"manager_id": new_manager.pk}, format="json",
        )
        self.assertEqual(r.status_code, 404)

    def test_add_tags_requires_admin(self):
        thread = self._make_thread(self.affiliate, self.manager)
        r = _api(self.affiliate).post(
            f"/messaging/affiliate-threads/{thread.id}/add_tags/",
            {"tags": ["vip"]}, format="json",
        )
        self.assertEqual(r.status_code, 403)

    def test_add_tags_merges_into_existing(self):
        thread = self._make_thread(self.affiliate, self.manager)
        AffiliateConversationThread.objects.filter(pk=thread.pk).update(tags=["existing"])
        r = _api(self.admin).post(
            f"/messaging/affiliate-threads/{thread.id}/add_tags/",
            {"tags": ["vip", "high-value"]}, format="json",
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(set(r.data["tags"]), {"existing", "vip", "high-value"})

    def test_add_note_requires_admin(self):
        thread = self._make_thread(self.affiliate, self.manager)
        r = _api(self.affiliate).post(
            f"/messaging/affiliate-threads/{thread.id}/add_note/",
            {"note": "VIP affiliate"}, format="json",
        )
        self.assertEqual(r.status_code, 403)

    def test_add_note_saves_note(self):
        thread = self._make_thread(self.affiliate, self.manager)
        r = _api(self.admin).post(
            f"/messaging/affiliate-threads/{thread.id}/add_note/",
            {"note": "VIP affiliate, escalate fast"}, format="json",
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["saved"])
        thread.refresh_from_db()
        self.assertEqual(thread.notes, "VIP affiliate, escalate fast")
