# =============================================================================
# api/auto_mod/graphql_schema.py
# =============================================================================
"""
GraphQL API for auto_mod using Strawberry (Python 3.12+ native).

Setup:
    pip install strawberry-graphql[django]

    In settings.py add to INSTALLED_APPS:
        'strawberry.django'

    In root urls.py:
        from strawberry.django.views import GraphQLView
        from api.auto_mod.graphql_schema import schema
        urlpatterns += [
            path("api/auto_mod/graphql/", GraphQLView.as_view(schema=schema)),
        ]

Usage example:
    query {
        submissions(status: "pending", limit: 10) {
            id contentId submissionType status riskLevel aiConfidence
        }
        moderationStats {
            totalPending approvedToday rejectedToday avgConfidence
        }
        queueDepth { priority count }
    }

    mutation {
        humanApprove(submissionId: "uuid-here", note: "Looks good")
        { success message }
    }
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger("auto_mod.graphql")

# ── Graceful degradation ─────────────────────────────────────────────────────
try:
    import strawberry
    from strawberry.types import Info
    STRAWBERRY_AVAILABLE = True
except ImportError:
    STRAWBERRY_AVAILABLE = False

    # Minimal stubs so the file stays importable without strawberry installed
    class _Stub:
        def __getattr__(self, _): return lambda *a, **kw: (lambda fn: fn)

    strawberry = _Stub()  # type: ignore

    class Info:  # type: ignore
        pass


# =============================================================================
# GraphQL Types
# =============================================================================

if STRAWBERRY_AVAILABLE:
    @strawberry.type
    class SubmissionType:
        id:              str
        content_id:      str
        submission_type: str
        status:          str
        risk_level:      str
        ai_confidence:   Optional[float]
        created_at:      str
        updated_at:      str

    @strawberry.type
    class AppealType:
        id:          str
        status:      str
        reason:      str
        created_at:  str
        resolved_at: Optional[str]

    @strawberry.type
    class ModerationStatsType:
        total_pending:    int
        approved_today:   int
        rejected_today:   int
        avg_confidence:   float
        queue_depth:      int
        healthy_bots:     int

    @strawberry.type
    class QueueDepthType:
        priority: str
        count:    int

    @strawberry.type
    class BotStatusType:
        id:         str
        name:       str
        status:     str
        bot_type:   str
        is_healthy: bool

    @strawberry.type
    class MutationResult:
        success: bool
        message: str

    # =========================================================================
    # Query
    # =========================================================================

    @strawberry.type
    class Query:

        @strawberry.field(description="List submissions with optional filters")
        def submissions(
            self,
            status:          Optional[str] = None,
            submission_type: Optional[str] = None,
            risk_level:      Optional[str] = None,
            limit:           int = 20,
        ) -> list[SubmissionType]:
            try:
                from .models import SuspiciousSubmission
                qs = SuspiciousSubmission.objects.all()
                if status:          qs = qs.filter(status=status)
                if submission_type: qs = qs.filter(submission_type=submission_type)
                if risk_level:      qs = qs.filter(risk_level=risk_level)
                return [
                    SubmissionType(
                        id=str(s.pk), content_id=s.content_id,
                        submission_type=s.submission_type, status=s.status,
                        risk_level=s.risk_level or "",
                        ai_confidence=s.ai_confidence,
                        created_at=str(s.created_at), updated_at=str(s.updated_at),
                    )
                    for s in qs[:limit]
                ]
            except Exception as exc:
                logger.warning("GraphQL.submissions error: %s", exc)
                return []

        @strawberry.field(description="Get a single submission by ID")
        def submission(self, id: str) -> Optional[SubmissionType]:
            try:
                from .models import SuspiciousSubmission
                s = SuspiciousSubmission.objects.get(pk=id)
                return SubmissionType(
                    id=str(s.pk), content_id=s.content_id,
                    submission_type=s.submission_type, status=s.status,
                    risk_level=s.risk_level or "", ai_confidence=s.ai_confidence,
                    created_at=str(s.created_at), updated_at=str(s.updated_at),
                )
            except Exception:
                return None

        @strawberry.field(description="Real-time moderation statistics")
        def moderation_stats(self) -> ModerationStatsType:
            try:
                from .models import SuspiciousSubmission, ModerationQueue, TaskBot
                from .choices import ModerationStatus, BotStatus
                from django.utils import timezone
                from django.db.models import Avg

                now   = timezone.now()
                today = now.replace(hour=0, minute=0, second=0, microsecond=0)
                qs    = SuspiciousSubmission.objects
                conf  = qs.filter(ai_confidence__isnull=False).aggregate(
                    a=Avg("ai_confidence")
                )["a"] or 0.0

                return ModerationStatsType(
                    total_pending=qs.filter(status=ModerationStatus.PENDING).count(),
                    approved_today=qs.filter(
                        updated_at__gte=today,
                        status__in=[ModerationStatus.AUTO_APPROVED,
                                     ModerationStatus.HUMAN_APPROVED]
                    ).count(),
                    rejected_today=qs.filter(
                        updated_at__gte=today,
                        status__in=[ModerationStatus.AUTO_REJECTED,
                                     ModerationStatus.HUMAN_REJECTED]
                    ).count(),
                    avg_confidence=round(float(conf), 4),
                    queue_depth=ModerationQueue.objects.filter(
                        completed_at__isnull=True
                    ).count(),
                    healthy_bots=TaskBot.objects.filter(
                        status=BotStatus.RUNNING
                    ).count(),
                )
            except Exception as exc:
                logger.warning("GraphQL.moderation_stats: %s", exc)
                return ModerationStatsType(0, 0, 0, 0.0, 0, 0)

        @strawberry.field(description="Queue depth by priority")
        def queue_depth(self) -> list[QueueDepthType]:
            try:
                from .models import ModerationQueue
                from django.db.models import Count
                rows = (
                    ModerationQueue.objects.filter(completed_at__isnull=True)
                    .values("priority")
                    .annotate(c=Count("id"))
                    .order_by("-c")
                )
                return [QueueDepthType(priority=r["priority"], count=r["c"])
                        for r in rows]
            except Exception as exc:
                logger.warning("GraphQL.queue_depth: %s", exc)
                return []

        @strawberry.field(description="List all TaskBots with health status")
        def bots(self) -> list[BotStatusType]:
            try:
                from .models import TaskBot
                return [
                    BotStatusType(
                        id=str(b.pk), name=b.name,
                        status=b.status, bot_type=b.bot_type,
                        is_healthy=b.is_healthy(),
                    )
                    for b in TaskBot.objects.all()
                ]
            except Exception as exc:
                logger.warning("GraphQL.bots: %s", exc)
                return []

        @strawberry.field(description="List pending appeals")
        def appeals(
            self,
            status: Optional[str] = None,
            limit:  int = 20,
        ) -> list[AppealType]:
            try:
                from .models import ModerationAppeal
                qs = ModerationAppeal.objects.all()
                if status: qs = qs.filter(status=status)
                return [
                    AppealType(
                        id=str(a.pk), status=a.status, reason=a.reason,
                        created_at=str(a.created_at),
                        resolved_at=str(a.resolved_at) if a.resolved_at else None,
                    )
                    for a in qs[:limit]
                ]
            except Exception as exc:
                logger.warning("GraphQL.appeals: %s", exc)
                return []

    # =========================================================================
    # Mutation
    # =========================================================================

    @strawberry.type
    class Mutation:

        @strawberry.mutation(description="Human-approve a submission")
        def human_approve(
            self,
            info: Info,
            submission_id: str,
            note: str = "",
        ) -> MutationResult:
            try:
                from .models import SuspiciousSubmission
                from .services import SubmissionService
                sub      = SubmissionService.get_or_404(submission_id)
                reviewer = getattr(info.context, "user", None)
                if not reviewer or not getattr(reviewer, "is_authenticated", False):
                    return MutationResult(success=False, message="Authentication required")
                SubmissionService.human_approve(
                    submission=sub, reviewer=reviewer, note=note
                )
                return MutationResult(success=True, message="Submission approved")
            except Exception as exc:
                return MutationResult(success=False, message=str(exc))

        @strawberry.mutation(description="Human-reject a submission")
        def human_reject(
            self,
            info: Info,
            submission_id: str,
            note: str = "",
        ) -> MutationResult:
            try:
                from .models import SuspiciousSubmission
                from .services import SubmissionService
                sub      = SubmissionService.get_or_404(submission_id)
                reviewer = getattr(info.context, "user", None)
                if not reviewer or not getattr(reviewer, "is_authenticated", False):
                    return MutationResult(success=False, message="Authentication required")
                SubmissionService.human_reject(
                    submission=sub, reviewer=reviewer, note=note
                )
                return MutationResult(success=True, message="Submission rejected")
            except Exception as exc:
                return MutationResult(success=False, message=str(exc))

        @strawberry.mutation(description="Start a TaskBot")
        def start_bot(self, info: Info, bot_id: str) -> MutationResult:
            try:
                from .models import TaskBot
                from .services import BotService
                bot    = TaskBot.objects.get(pk=bot_id)
                result = BotService.start_bot(bot)
                return MutationResult(success=result["success"],
                                      message=f"Bot status: {result['status']}")
            except Exception as exc:
                return MutationResult(success=False, message=str(exc))

        @strawberry.mutation(description="Stop a TaskBot")
        def stop_bot(self, info: Info, bot_id: str) -> MutationResult:
            try:
                from .models import TaskBot
                from .services import BotService
                bot    = TaskBot.objects.get(pk=bot_id)
                result = BotService.stop_bot(bot)
                return MutationResult(success=result["success"],
                                      message=f"Bot status: {result['status']}")
            except Exception as exc:
                return MutationResult(success=False, message=str(exc))

        @strawberry.mutation(description="Bulk-approve multiple submissions")
        def bulk_approve(
            self,
            info: Info,
            submission_ids: list[str],
            note: str = "",
        ) -> MutationResult:
            try:
                from .missing_components import BulkModerationService
                reviewer = getattr(info.context, "user", None)
                if not reviewer or not getattr(reviewer, "is_staff", False):
                    return MutationResult(success=False, message="Staff access required")
                result = BulkModerationService.bulk_approve(
                    submission_ids, reviewer=reviewer, note=note
                )
                return MutationResult(
                    success=result["failed"] == 0,
                    message=f"Approved: {result['approved']} | Failed: {result['failed']}"
                )
            except Exception as exc:
                return MutationResult(success=False, message=str(exc))

    # =========================================================================
    # Schema
    # =========================================================================
    schema = strawberry.Schema(query=Query, mutation=Mutation)

else:
    # Stub schema when strawberry not installed
    schema = None  # type: ignore
    logger.info("auto_mod.graphql: strawberry not installed — GraphQL disabled")
