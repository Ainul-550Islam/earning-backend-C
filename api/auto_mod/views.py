# =============================================================================
# auto_mod/views.py
# =============================================================================

from __future__ import annotations

import logging

from django.utils import timezone
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AutoApprovalRule, SuspiciousSubmission, TaskBot
from .permissions import IsModeratorOrStaff, IsStaffOnly
from .serializers import SuspiciousSubmissionSerializer
from .services import ModerationService, SubmissionService

logger = logging.getLogger(__name__)


class ModerationDashboardView(APIView):
    """
    GET /auto-mod/dashboard/
    Summary stats for the moderation dashboard.
    """
    permission_classes = [IsModeratorOrStaff]

    def get(self, request: Request) -> Response:
        from .choices import BotStatus, ModerationStatus, RiskLevel
        from django.db.models import Avg, Count

        today = timezone.localdate()

        data = {
            "today": str(today),
            "submissions": {
                "pending":       SuspiciousSubmission.objects.pending().count(),
                "human_review":  SuspiciousSubmission.objects.awaiting_review().count(),
                "escalated":     SuspiciousSubmission.objects.escalated().count(),
                "auto_approved": SuspiciousSubmission.objects.filter(
                    status=ModerationStatus.AUTO_APPROVED, created_at__date=today
                ).count(),
                "auto_rejected": SuspiciousSubmission.objects.filter(
                    status=ModerationStatus.AUTO_REJECTED, created_at__date=today
                ).count(),
                "high_risk":     SuspiciousSubmission.objects.high_risk().count(),
            },
            "rules": {
                "active": AutoApprovalRule.objects.active().count(),
                "total":  AutoApprovalRule.objects.count(),
            },
            "bots": {
                "running": TaskBot.objects.running().count(),
                "idle":    TaskBot.objects.idle().count(),
                "error":   TaskBot.objects.filter(status=BotStatus.ERROR).count(),
            },
        }
        return Response(data)


class SubmissionRescanView(APIView):
    """
    POST /auto-mod/submissions/<pk>/rescan/
    Re-trigger AI scan for an existing submission (staff only).
    """
    permission_classes = [IsStaffOnly]

    def post(self, request: Request, pk: str) -> Response:
        submission = SubmissionService.get_or_404(pk)

        try:
            from .tasks import scan_submission
            scan_submission.delay(
                content_type=submission.content_type,
                content_id=submission.content_id,
                submission_type=submission.submission_type,
                user_id=str(request.user.pk),
                metadata={"rescan": True, "triggered_by": str(request.user.pk)},
            )
        except Exception:
            logger.exception("rescan.task_dispatch_failed pk=%s", pk)
            return Response(
                {"detail": "Rescan task could not be dispatched."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            {"detail": "Rescan queued.", "id": str(submission.pk)},
            status=status.HTTP_202_ACCEPTED,
        )


class BulkModerationActionView(APIView):
    """
    POST /auto-mod/submissions/bulk-action/
    Apply approve/reject/escalate to multiple submissions at once.
    Staff/moderator only.
    """
    permission_classes = [IsModeratorOrStaff]

    def post(self, request: Request) -> Response:
        ids    = request.data.get("ids", [])
        action = request.data.get("action", "")
        note   = request.data.get("note", "")

        if not ids or not isinstance(ids, list):
            return Response(
                {"detail": "'ids' must be a non-empty list."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if action not in ("approve", "reject"):
            return Response(
                {"detail": "'action' must be 'approve' or 'reject'."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(ids) > 100:
            return Response(
                {"detail": "Cannot bulk-process more than 100 submissions at once."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        results = {"processed": [], "errors": []}
        for pk in ids:
            try:
                sub = SubmissionService.get_or_404(str(pk))
                if action == "approve":
                    SubmissionService.human_approve(
                        submission=sub, reviewer=request.user, note=note
                    )
                else:
                    SubmissionService.human_reject(
                        submission=sub, reviewer=request.user, note=note
                    )
                results["processed"].append(str(pk))
            except Exception as exc:
                results["errors"].append({"id": str(pk), "error": str(exc)})

        return Response(results, status=status.HTTP_200_OK)