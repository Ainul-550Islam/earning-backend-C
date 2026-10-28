"""
Tests for Part 21 (world-system audit): compliance audit trail, retention
policy, and legal hold.
"""
from __future__ import annotations

from django.test import TestCase
from rest_framework.test import APIClient

from .factories import UserFactory, InternalChatFactory, ChatParticipantFactory
from .. import services
from ..models import AuditLogEntry, RetentionPolicy, LegalHold
from ..choices import AuditAction
from ..exceptions import MessagingError


def _admin_api(user) -> APIClient:
    user.is_staff = True
    user.save(update_fields=["is_staff"])
    client = APIClient()
    client.force_authenticate(user=user)
    return client


class TestAuditLog(TestCase):
    def test_log_audit_event_creates_entry(self):
        admin = UserFactory()
        entry = services.log_audit_event(
            actor_id=admin.id, action=AuditAction.DATA_EXPORTED,
            target_type="User", target_id=admin.id, tenant_id=None,
            metadata={"format": "json"},
        )
        self.assertEqual(AuditLogEntry.objects.count(), 1)
        self.assertEqual(entry.target_id, str(admin.id))  # stored as string
        self.assertEqual(entry.metadata["format"], "json")

    def test_log_audit_event_allows_null_actor_for_system_actions(self):
        entry = services.log_audit_event(
            actor_id=None, action=AuditAction.CHAT_DELETED,
            target_type="InternalChat", target_id="some-id", tenant_id=None,
        )
        self.assertIsNone(entry.actor)


class TestRetentionPolicy(TestCase):
    def setUp(self):
        from ..tests._tenant_stub.models import Tenant
        self.tenant = Tenant.objects.create(name="t1")
        self.admin = UserFactory()

    def test_default_policy_is_unlimited(self):
        policy = services.get_retention_policy(self.tenant)
        self.assertIsNone(policy.chat_message_retention_days)

    def test_set_retention_policy_updates_and_logs(self):
        policy = services.set_retention_policy(
            tenant=self.tenant, chat_message_retention_days=180, updated_by_id=self.admin.id,
        )
        self.assertEqual(policy.chat_message_retention_days, 180)
        self.assertEqual(
            AuditLogEntry.objects.filter(action=AuditAction.RETENTION_POLICY_CHANGED).count(), 1,
        )

    def test_set_retention_policy_rejects_zero_days(self):
        with self.assertRaises(MessagingError):
            services.set_retention_policy(
                tenant=self.tenant, chat_message_retention_days=0, updated_by_id=self.admin.id,
            )

    def test_one_policy_per_tenant(self):
        services.set_retention_policy(tenant=self.tenant, chat_message_retention_days=90, updated_by_id=self.admin.id)
        services.set_retention_policy(tenant=self.tenant, chat_message_retention_days=30, updated_by_id=self.admin.id)
        self.assertEqual(RetentionPolicy.objects.filter(tenant=self.tenant).count(), 1)
        self.assertEqual(RetentionPolicy.objects.get(tenant=self.tenant).chat_message_retention_days, 30)


class TestLegalHold(TestCase):
    def setUp(self):
        from ..tests._tenant_stub.models import Tenant
        self.tenant = Tenant.objects.create(name="t1")
        self.admin = UserFactory()
        self.chat = InternalChatFactory(tenant=self.tenant)

    def test_apply_hold_requires_chat_or_user(self):
        with self.assertRaises(MessagingError):
            services.apply_legal_hold(
                tenant=self.tenant, reason="dispute", applied_by_id=self.admin.id,
            )

    def test_apply_and_release_hold(self):
        hold = services.apply_legal_hold(
            tenant=self.tenant, chat_id=self.chat.id, reason="dispute #123",
            applied_by_id=self.admin.id,
        )
        self.assertTrue(hold.is_active)
        self.assertEqual(
            AuditLogEntry.objects.filter(action=AuditAction.LEGAL_HOLD_APPLIED).count(), 1,
        )

        released = services.release_legal_hold(hold_id=hold.id, released_by_id=self.admin.id, tenant_id=self.tenant.id)
        self.assertFalse(released.is_active)
        self.assertIsNotNone(released.released_at)
        self.assertEqual(
            AuditLogEntry.objects.filter(action=AuditAction.LEGAL_HOLD_RELEASED).count(), 1,
        )

    def test_chats_under_legal_hold_by_chat(self):
        services.apply_legal_hold(
            tenant=self.tenant, chat_id=self.chat.id, reason="x", applied_by_id=self.admin.id,
        )
        held = services.chats_under_legal_hold([self.chat.id])
        self.assertIn(self.chat.id, held)

    def test_chats_under_legal_hold_by_user_protects_all_their_chats(self):
        user = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=user)
        other_chat = InternalChatFactory(tenant=self.tenant)
        ChatParticipantFactory(chat=other_chat, user=user)

        services.apply_legal_hold(
            tenant=self.tenant, user_id=user.id, reason="under investigation",
            applied_by_id=self.admin.id,
        )

        held = services.chats_under_legal_hold([self.chat.id, other_chat.id])
        self.assertIn(self.chat.id, held)
        self.assertIn(other_chat.id, held)

    def test_released_hold_no_longer_protects(self):
        hold = services.apply_legal_hold(
            tenant=self.tenant, chat_id=self.chat.id, reason="x", applied_by_id=self.admin.id,
        )
        services.release_legal_hold(hold_id=hold.id, released_by_id=self.admin.id, tenant_id=self.tenant.id)
        held = services.chats_under_legal_hold([self.chat.id])
        self.assertNotIn(self.chat.id, held)

    def test_cannot_release_hold_belonging_to_a_different_tenant(self):
        """The bug this guards against: release_legal_hold() used to look
        a hold up by id alone with no tenant check, and the viewset's
        release action never called get_object() (which would have
        applied get_queryset()'s tenant filter) - together, any admin
        from any tenant could release any other tenant's legal hold."""
        from ..tests._tenant_stub.models import Tenant
        from ..exceptions import PermissionDeniedError

        other_tenant = Tenant.objects.create(name="other-tenant")
        hold = services.apply_legal_hold(
            tenant=self.tenant, chat_id=self.chat.id, reason="x", applied_by_id=self.admin.id,
        )

        with self.assertRaises(PermissionDeniedError):
            services.release_legal_hold(
                hold_id=hold.id, released_by_id=self.admin.id, tenant_id=other_tenant.id,
            )
        self.assertTrue(LegalHold.objects.get(pk=hold.id).is_active)


class TestComplianceViewsets(TestCase):
    def setUp(self):
        self.admin = UserFactory()
        self.regular_user = UserFactory()

    def test_non_admin_cannot_access_audit_log(self):
        client = APIClient()
        client.force_authenticate(user=self.regular_user)
        resp = client.get("/messaging/audit-log/")
        self.assertEqual(resp.status_code, 403)

    def test_admin_can_list_audit_log(self):
        resp = _admin_api(self.admin).get("/messaging/audit-log/")
        self.assertEqual(resp.status_code, 200)

    def test_admin_can_get_and_set_retention_policy(self):
        client = _admin_api(self.admin)
        resp = client.get("/messaging/retention-policy/")
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.data["chat_message_retention_days"])

        resp = client.put("/messaging/retention-policy/set_policy/",
                           {"chat_message_retention_days": 365}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["chat_message_retention_days"], 365)

    def test_admin_can_apply_and_release_legal_hold(self):
        chat = InternalChatFactory()
        client = _admin_api(self.admin)

        resp = client.post("/messaging/legal-holds/", {
            "chat_id": str(chat.id), "reason": "dispute",
        }, format="json")
        self.assertEqual(resp.status_code, 201)
        hold_id = resp.data["id"]

        resp = client.post(f"/messaging/legal-holds/{hold_id}/release/")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data["is_active"])
