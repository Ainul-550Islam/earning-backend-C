# =============================================================================
# auto_mod/services/ModerationQueueService.py
# =============================================================================
"""ModerationQueueService — full queue management for moderation workflow."""
from __future__ import annotations
from api.auto_mod.constants import QueuePriority
import logging
from django.db import transaction
from django.utils import timezone
from django.db.models import Count, Avg
from django.contrib.auth import get_user_model

from ..choices import QueuePriority, ModerationStatus
from ..exceptions import QueueAssignmentError, QueueEscalationError
from ..models import ModerationQueue, SuspiciousSubmission

User = get_user_model()
logger = logging.getLogger(__name__)
MAX_ESCALATION_LEVEL = 3
OVERDUE_HOURS = 24
MAX_WORKLOAD = 10


class ModerationQueueService:

    # ------------------------------------------------------------------
    # Add / get
    # ------------------------------------------------------------------

    def add_to_queue(
        self,
        submission: SuspiciousSubmission,
        priority: str = QueuePriority.NORMAL,
        due_hours: int | None = None,
    ) -> ModerationQueue:
        obj, _ = ModerationQueue.objects.get_or_create(
            submission=submission,
            completed_at__isnull=True,
            defaults={
                "priority": priority,
                "due_at": timezone.now() + timezone.timedelta(hours=due_hours) if due_hours else None,
            },
        )
        return obj

    def get_queue_items_for_moderator(
        self,
        moderator,
        limit: int = 50,
        include_completed: bool = False,
    ):
        qs = ModerationQueue.objects.filter(assigned_to=moderator)
        if not include_completed:
            qs = qs.filter(completed_at__isnull=True)
        return list(qs.order_by("priority", "queued_at")[:limit])

    # ------------------------------------------------------------------
    # Assign
    # ------------------------------------------------------------------

    @transaction.atomic
    def assign_to_moderator(
        self,
        *,
        queue_item: ModerationQueue,
        moderator,
        assigned_by=None,
        notes: str = "",
    ) -> ModerationQueue:
        if queue_item.assigned_to is not None:
            raise QueueAssignmentError("Queue item is already assigned.")
        queue_item.assigned_to = moderator
        queue_item.assigned_by = assigned_by
        queue_item.assigned_at = timezone.now()
        if notes:
            queue_item.processing_notes = (queue_item.processing_notes or "") + f"\n{notes}"
        queue_item.save()

        try:
            from ..signals import queue_item_assigned
            queue_item_assigned.send(
                sender=ModerationQueue,
                queue_item=queue_item,
                assigned_to=moderator,
                assigned_by=assigned_by,
            )
        except Exception:
            pass
        return queue_item

    # ------------------------------------------------------------------
    # Escalate
    # ------------------------------------------------------------------

    @transaction.atomic
    def escalate_queue_item(
        self,
        *,
        queue_item: ModerationQueue,
        escalated_by=None,
        new_priority: str = QueuePriority.HIGH,
        reason: str = "",
    ) -> ModerationQueue:
        if (queue_item.escalation_level or 0) >= MAX_ESCALATION_LEVEL:
            raise QueueEscalationError(f"Max escalation level ({MAX_ESCALATION_LEVEL}) reached.")

        old_level = queue_item.escalation_level or 0
        queue_item.escalation_level = old_level + 1
        queue_item.priority = new_priority
        if reason:
            queue_item.processing_notes = (queue_item.processing_notes or "") + f"\n{reason}"
        queue_item.save()

        try:
            from ..signals import queue_item_escalated
            queue_item_escalated.send(
                sender=ModerationQueue,
                queue_item=queue_item,
                old_level=old_level,
                new_level=queue_item.escalation_level,
                reason=reason,
            )
        except Exception:
            pass
        return queue_item

    # ------------------------------------------------------------------
    # Release
    # ------------------------------------------------------------------

    @transaction.atomic
    def release_queue_item(
        self,
        *,
        queue_item: ModerationQueue,
        released_by=None,
        reason: str = "",
    ) -> ModerationQueue:
        queue_item.assigned_to = None
        queue_item.assigned_at = None
        note = f"Released: {reason}" if reason else "released"
        queue_item.processing_notes = (queue_item.processing_notes or "") + f"\n{note}"
        queue_item.save()
        return queue_item

    # ------------------------------------------------------------------
    # Overdue / auto-escalate
    # ------------------------------------------------------------------

    def get_overdue_items(self):
        return list(ModerationQueue.objects.get_overdue_items())

    def escalate_overdue_items(self) -> dict:
        overdue = ModerationQueue.objects.get_overdue_items()
        escalated = 0
        for item in overdue:
            try:
                self.escalate_queue_item(queue_item=item, reason="Auto-escalated: overdue")
                escalated += 1
            except QueueEscalationError:
                pass
        return {"escalated": escalated}

    # ------------------------------------------------------------------
    # Auto-assign
    # ------------------------------------------------------------------

    def get_available_moderators(
        self,
        submission_type: str | None = None,
        max_workload: int = MAX_WORKLOAD,
    ):
        overloaded = set(
            ModerationQueue.objects.filter(completed_at__isnull=True, assigned_to__isnull=False)
            .values("assigned_to")
            .annotate(c=Count("id"))
            .filter(c__gte=max_workload)
            .values_list("assigned_to", flat=True)
        )
        return list(User.objects.filter(is_staff=True).exclude(pk__in=overloaded))

    def auto_assign_queue_items(
        self,
        *,
        batch_size: int = 50,
        submission_type: str | None = None,
    ) -> dict:
        unassigned = ModerationQueue.objects.get_unassigned_items()
        if submission_type:
            unassigned = unassigned.filter(submission__submission_type=submission_type)
        unassigned = list(unassigned[:batch_size])

        moderators = self.get_available_moderators(submission_type=submission_type)
        if not moderators:
            return {"assigned": 0, "unassigned": len(unassigned)}

        assigned = 0
        for i, item in enumerate(unassigned):
            moderator = moderators[i % len(moderators)]
            try:
                self.assign_to_moderator(
                    queue_item=item, moderator=moderator
                )
                assigned += 1
            except QueueAssignmentError:
                pass

        return {"assigned": assigned, "unassigned": max(0, len(unassigned) - assigned)}

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_queue_statistics(self) -> dict:
        qs    = ModerationQueue.objects.all()
        total = qs.count()
        by_priority = dict(
            qs.values("priority").annotate(c=Count("id")).values_list("priority", "c")
        )
        unassigned = qs.filter(assigned_to__isnull=True, completed_at__isnull=True).count()
        assigned   = qs.filter(assigned_to__isnull=False, completed_at__isnull=True).count()
        completed  = qs.filter(completed_at__isnull=False).count()
        by_esc = dict(
            qs.values("escalation_level").annotate(c=Count("id")).values_list("escalation_level", "c")
        )
        overdue = ModerationQueue.objects.get_overdue_items().count()
        avg_wait = qs.aggregate(a=Avg("estimated_processing_time"))["a"] or 0
        return {
            "total_items":         total,
            "by_priority":         by_priority,
            "by_status":           {"unassigned": unassigned, "assigned": assigned, "completed": completed},
            "by_escalation_level": by_esc,
            "average_wait_time":   avg_wait,
            "overdue_count":       overdue,
        }
