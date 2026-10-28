"""
Tests for the Part 21 changes to the cleanup_chats management command:
legal-hold exclusion and audit logging on top of the existing soft-delete
cleanup. No test file existed for this command before - these are new,
not a regression suite for prior behavior.
"""
from __future__ import annotations
from datetime import timedelta

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from .factories import InternalChatFactory, UserFactory, ChatMessageFactory
from .. import services
from ..models import AuditLogEntry, InternalChat, ChatMessage, RetentionPolicy
from ..choices import ChatStatus, AuditAction


class TestCleanupChatsLegalHold(TestCase):
    def setUp(self):
        self.admin = UserFactory()
        old = timezone.now() - timedelta(days=60)
        self.normal_chat = InternalChatFactory(status=ChatStatus.DELETED)
        InternalChat.objects.filter(pk=self.normal_chat.pk).update(updated_at=old)
        self.held_chat = InternalChatFactory(status=ChatStatus.DELETED)
        InternalChat.objects.filter(pk=self.held_chat.pk).update(updated_at=old)

        services.apply_legal_hold(
            tenant=None, chat_id=self.held_chat.id, reason="dispute",
            applied_by_id=self.admin.id,
        )

    def test_normal_chat_deleted_held_chat_survives(self):
        call_command("cleanup_chats", days=30)

        self.assertFalse(InternalChat.objects.filter(pk=self.normal_chat.pk).exists())
        self.assertTrue(InternalChat.objects.filter(pk=self.held_chat.pk).exists())

    def test_deletion_and_hold_skip_are_both_logged(self):
        call_command("cleanup_chats", days=30)

        self.assertTrue(
            AuditLogEntry.objects.filter(
                action=AuditAction.CHAT_DELETED, target_id=str(self.normal_chat.id),
            ).exists()
        )
        self.assertTrue(
            AuditLogEntry.objects.filter(
                action=AuditAction.CLEANUP_SKIPPED_HOLD, target_id=str(self.held_chat.id),
            ).exists()
        )

    def test_dry_run_writes_no_audit_entries_and_deletes_nothing(self):
        call_command("cleanup_chats", days=30, **{"dry_run": True})

        # setUp() itself already logged a LEGAL_HOLD_APPLIED entry - what
        # this test checks is that the dry run added no *cleanup* entries.
        self.assertFalse(
            AuditLogEntry.objects.filter(
                action__in=[AuditAction.CHAT_DELETED, AuditAction.CLEANUP_SKIPPED_HOLD],
            ).exists()
        )
        self.assertTrue(InternalChat.objects.filter(pk=self.normal_chat.pk).exists())
        self.assertTrue(InternalChat.objects.filter(pk=self.held_chat.pk).exists())

    def test_released_hold_chat_gets_cleaned_up_next_run(self):
        hold = services.chats_under_legal_hold([self.held_chat.id])
        self.assertIn(self.held_chat.id, hold)

        from ..models import LegalHold
        active_hold = LegalHold.objects.get(chat_id=self.held_chat.id, is_active=True)
        services.release_legal_hold(hold_id=active_hold.id, released_by_id=self.admin.id, tenant_id=None)

        call_command("cleanup_chats", days=30)

        self.assertFalse(InternalChat.objects.filter(pk=self.held_chat.pk).exists())


class TestCleanupChatsRetentionPolicy(TestCase):
    """Part 21 follow-up: per-tenant message retention enforcement."""

    def setUp(self):
        from ..tests._tenant_stub.models import Tenant
        self.admin = UserFactory()
        self.tenant = Tenant.objects.create(name="retention-tenant")
        self.other_tenant = Tenant.objects.create(name="other-tenant")
        self.sender = UserFactory()
        self.chat = InternalChatFactory(tenant=self.tenant)

        self.old_message = ChatMessageFactory(
            chat=self.chat, sender=self.sender, content="old", tenant=self.tenant,
        )
        ChatMessage.objects.filter(pk=self.old_message.pk).update(
            created_at=timezone.now() - timedelta(days=100)
        )
        self.recent_message = ChatMessageFactory(
            chat=self.chat, sender=self.sender, content="recent", tenant=self.tenant,
        )

    def test_no_policy_means_no_expiry(self):
        # No RetentionPolicy row at all for self.tenant.
        call_command("cleanup_chats", days=30)
        self.assertTrue(ChatMessage.objects.filter(pk=self.old_message.pk).exists())

    def test_unlimited_policy_means_no_expiry(self):
        services.set_retention_policy(
            tenant=self.tenant, chat_message_retention_days=None, updated_by_id=self.admin.id,
        )
        call_command("cleanup_chats", days=30)
        self.assertTrue(ChatMessage.objects.filter(pk=self.old_message.pk).exists())

    def test_old_message_expired_recent_message_kept(self):
        services.set_retention_policy(
            tenant=self.tenant, chat_message_retention_days=90, updated_by_id=self.admin.id,
        )
        call_command("cleanup_chats", days=30)

        self.assertFalse(ChatMessage.objects.filter(pk=self.old_message.pk).exists())
        self.assertTrue(ChatMessage.objects.filter(pk=self.recent_message.pk).exists())

    def test_expiry_is_logged(self):
        services.set_retention_policy(
            tenant=self.tenant, chat_message_retention_days=90, updated_by_id=self.admin.id,
        )
        call_command("cleanup_chats", days=30)

        self.assertTrue(
            AuditLogEntry.objects.filter(
                action=AuditAction.MESSAGE_DELETED, target_id=str(self.old_message.id),
            ).exists()
        )

    def test_legal_hold_on_chat_protects_its_messages_from_retention(self):
        services.set_retention_policy(
            tenant=self.tenant, chat_message_retention_days=90, updated_by_id=self.admin.id,
        )
        services.apply_legal_hold(
            tenant=self.tenant, chat_id=self.chat.id, reason="dispute",
            applied_by_id=self.admin.id,
        )

        call_command("cleanup_chats", days=30)

        self.assertTrue(ChatMessage.objects.filter(pk=self.old_message.pk).exists())

    def test_dry_run_expires_nothing(self):
        services.set_retention_policy(
            tenant=self.tenant, chat_message_retention_days=90, updated_by_id=self.admin.id,
        )
        call_command("cleanup_chats", days=30, **{"dry_run": True})

        self.assertTrue(ChatMessage.objects.filter(pk=self.old_message.pk).exists())
        self.assertFalse(
            AuditLogEntry.objects.filter(action=AuditAction.MESSAGE_DELETED).exists()
        )

    def test_other_tenants_policy_does_not_affect_this_tenant(self):
        services.set_retention_policy(
            tenant=self.other_tenant, chat_message_retention_days=7, updated_by_id=self.admin.id,
        )
        call_command("cleanup_chats", days=30)

        # self.tenant has no policy of its own - other_tenant's 7-day
        # policy must not leak across and expire self.tenant's messages.
        self.assertTrue(ChatMessage.objects.filter(pk=self.old_message.pk).exists())
