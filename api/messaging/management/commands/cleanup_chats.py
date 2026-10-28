"""
Management Command: cleanup_chats — Remove soft-deleted chats, old archived
messages, and (Part 21) enforce any tenant's configured message retention
policy.
"""
from __future__ import annotations
import logging
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.conf import settings

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Cleanup soft-deleted chats and old archived inbox items, and "
        "enforce any tenant's configured message retention policy. "
        "Legal holds are respected in both cases."
    )

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=30,
                            help="Delete soft-deleted chats older than N days (default: 30).")
        parser.add_argument("--inbox-days", type=int, default=90,
                            help="Delete archived inbox items older than N days (default: 90).")
        parser.add_argument("--dry-run", action="store_true",
                            help="Show what would be deleted without actually deleting.")

    def handle(self, *args, **options):
        days = options["days"]
        inbox_days = options["inbox_days"]
        dry_run = options["dry_run"]

        if days < 1 or inbox_days < 1:
            raise CommandError("--days and --inbox-days must be at least 1.")

        from datetime import timedelta
        from django.utils import timezone
        from ...models import InternalChat, UserInbox, ChatMessage
        from ...choices import ChatStatus, AuditAction
        from ...utils.search_engine import delete_from_index
        from ... import services

        cutoff_chats = timezone.now() - timedelta(days=days)
        cutoff_inbox = timezone.now() - timedelta(days=inbox_days)

        deleted_chats_qs = InternalChat.objects.filter(
            status=ChatStatus.DELETED, updated_at__lt=cutoff_chats
        )
        deleted_inbox_qs = UserInbox.objects.filter(
            is_archived=True, created_at__lt=cutoff_inbox
        )

        # Part 21 (world-system audit): a chat under legal hold - either
        # directly, or because one of its participants is personally
        # under hold - must survive this cleanup regardless of how long
        # it's been soft-deleted. Previously there was no such check at
        # all: a chat relevant to a dispute or investigation could be
        # silently, permanently destroyed by the next scheduled run.
        all_candidate_ids = list(deleted_chats_qs.values_list("id", flat=True))
        held_ids = services.chats_under_legal_hold(all_candidate_ids)
        if held_ids:
            if not dry_run:
                held_tenants = dict(
                    InternalChat.objects.filter(id__in=held_ids).values_list("id", "tenant_id")
                )
                for chat_id in held_ids:
                    services.log_audit_event(
                        actor_id=None, action=AuditAction.CLEANUP_SKIPPED_HOLD,
                        target_type="InternalChat", target_id=chat_id,
                        tenant_id=held_tenants.get(chat_id),
                        metadata={"reason": "active legal hold"},
                    )
            deleted_chats_qs = deleted_chats_qs.exclude(id__in=held_ids)
            self.stdout.write(self.style.WARNING(
                f"Skipping {len(held_ids)} chat(s) under active legal hold."
            ))

        chats_to_delete = deleted_chats_qs.count()
        inbox_to_delete = deleted_inbox_qs.count()
        self.stdout.write(f"Chats to delete: {chats_to_delete}")
        self.stdout.write(f"Inbox items to delete: {inbox_to_delete}")

        # Part 21 follow-up: per-tenant message retention enforcement.
        # Opt-in by construction - a tenant with no RetentionPolicy row,
        # or one with chat_message_retention_days left blank (the
        # default), is completely unaffected by this loop. Runs before
        # the dry-run early-return below so --dry-run previews this too.
        expired_count, retention_skipped_hold = self._enforce_retention_policies(
            dry_run=dry_run, services=services, timezone=timezone, timedelta=timedelta,
        )

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — nothing deleted."))
            return

        # Message IDs must be collected BEFORE the cascade delete below
        # destroys them - there is no way to recover which messages
        # belonged to these chats afterward.
        message_ids = list(
            ChatMessage.objects.filter(chat__in=deleted_chats_qs).values_list("id", flat=True)
        )
        # Same reasoning for the audit trail itself (Part 21): (id, tenant_id)
        # pairs must be captured now - AuditLogEntry.target_id is a plain
        # string specifically so this record outlives the row it describes.
        deleted_chat_audit_pairs = list(deleted_chats_qs.values_list("id", "tenant_id"))

        with transaction.atomic():
            # QuerySet.delete()'s first return value is the TOTAL number
            # of rows deleted across every cascaded model (chat +
            # messages + participants + reactions + search-index rows +
            # ...), not just InternalChat/UserInbox rows - using it
            # directly here would report a confusing, inflated, and
            # non-reproducible number as "chats deleted". Report the
            # counts already computed above instead, since those are
            # the actual InternalChat/UserInbox row counts.
            deleted_chats_qs.delete()
            deleted_inbox_qs.delete()
        chat_count, inbox_count = chats_to_delete, inbox_to_delete

        for chat_id, tenant_id in deleted_chat_audit_pairs:
            services.log_audit_event(
                actor_id=None, action=AuditAction.CHAT_DELETED,
                target_type="InternalChat", target_id=chat_id, tenant_id=tenant_id,
                metadata={"reason": "cleanup_chats", "days_threshold": days},
            )

        # Deindex from real Elasticsearch now that the DB delete has
        # committed. Deliberately done outside the transaction (ES is a
        # network call and shouldn't hold a DB transaction open) and
        # deliberately best-effort per message (one ES hiccup shouldn't
        # make an otherwise-successful DB cleanup look like it failed).
        # delete_from_index() catches its own exceptions and returns
        # False rather than raising, so success/failure is read from its
        # return value, not from a try/except around it.
        deindexed = 0
        deindex_errors = 0
        for message_id in message_ids:
            try:
                ok = delete_from_index(str(message_id))
            except Exception as exc:
                ok = False
                logger.warning("cleanup_chats: failed to deindex message=%s err=%s", message_id, exc)
            if ok:
                deindexed += 1
            else:
                deindex_errors += 1

        summary = (
            f"Deleted {chat_count} chats and {inbox_count} inbox items. "
            f"Expired {expired_count} message(s) under retention policy"
            f"{f' ({retention_skipped_hold} skipped - legal hold)' if retention_skipped_hold else ''}. "
            f"Deindexed {deindexed} messages from search."
        )
        if deindex_errors:
            summary += f" ({deindex_errors} deindex errors - see logs.)"
        self.stdout.write(self.style.SUCCESS(summary))
        logger.info(
            "cleanup_chats: deleted %d chats, %d inbox items, expired %d retention messages "
            "(%d skipped-hold), deindexed %d messages (%d errors).",
            chat_count, inbox_count, expired_count, retention_skipped_hold, deindexed, deindex_errors,
        )

    def _enforce_retention_policies(self, *, dry_run, services, timezone, timedelta) -> tuple:
        """Part 21 follow-up (world-system audit): auto-expire messages
        per tenant's configured RetentionPolicy.chat_message_retention_days.

        A message whose chat is under legal hold (directly, or via a
        user-level hold on one of the chat's participants) is excluded,
        same protection as the soft-deleted-chat cleanup above -
        chats_under_legal_hold() is the single source of truth for both.

        Returns (expired_count, skipped_for_hold_count). In dry-run mode,
        computes and reports both counts without deleting or writing any
        audit entries - mirrors the existing --dry-run contract for the
        rest of this command.
        """
        from ...models import RetentionPolicy, ChatMessage, AuditLogEntry
        from ...choices import AuditAction
        from ...utils.search_engine import delete_from_index

        total_expired = 0
        total_skipped_hold = 0

        policies = RetentionPolicy.objects.filter(chat_message_retention_days__isnull=False)
        for policy in policies:
            cutoff = timezone.now() - timedelta(days=policy.chat_message_retention_days)
            candidates = list(
                ChatMessage.objects.filter(tenant=policy.tenant, created_at__lt=cutoff)
                .values_list("id", "chat_id")
            )
            if not candidates:
                continue

            chat_ids = {cid for _mid, cid in candidates}
            held_chat_ids = services.chats_under_legal_hold(list(chat_ids))
            to_delete = [(mid, cid) for mid, cid in candidates if cid not in held_chat_ids]
            skipped = len(candidates) - len(to_delete)
            total_skipped_hold += skipped

            if not to_delete:
                if skipped:
                    self.stdout.write(
                        f"Retention policy for tenant={policy.tenant_id}: "
                        f"all {skipped} eligible message(s) skipped - legal hold"
                    )
                continue

            self.stdout.write(
                f"Retention policy for tenant={policy.tenant_id}: "
                f"{len(to_delete)} message(s) older than {policy.chat_message_retention_days}d"
                + (f" ({skipped} skipped - legal hold)" if skipped else "")
            )

            if dry_run:
                total_expired += len(to_delete)
                continue

            del_ids = [mid for mid, _cid in to_delete]
            with transaction.atomic():
                ChatMessage.objects.filter(id__in=del_ids).delete()
                AuditLogEntry.objects.bulk_create([
                    AuditLogEntry(
                        actor=None, action=AuditAction.MESSAGE_DELETED,
                        target_type="ChatMessage", target_id=str(mid),
                        tenant_id=policy.tenant_id,
                        metadata={
                            "reason": "retention_policy",
                            "retention_days": policy.chat_message_retention_days,
                        },
                    )
                    for mid in del_ids
                ])

            for mid in del_ids:
                try:
                    delete_from_index(str(mid))
                except Exception as exc:
                    logger.warning(
                        "cleanup_chats: retention deindex failed for msg=%s err=%s", mid, exc,
                    )

            total_expired += len(to_delete)

        return total_expired, total_skipped_hold
