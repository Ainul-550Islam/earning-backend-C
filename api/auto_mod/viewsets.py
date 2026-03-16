# =============================================================================
# auto_mod/viewsets.py
# =============================================================================

from __future__ import annotations

import logging

from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from .exceptions import BotAlreadyRunningError, SubmissionAlreadyProcessedError
from .filters import (
    AutoApprovalRuleFilter,
    ProofScannerFilter,
    SuspiciousSubmissionFilter,
    TaskBotFilter,
)
from .models import AutoApprovalRule, ProofScanner, SuspiciousSubmission, TaskBot
from .permissions import CanManageRules, IsModeratorOrStaff, IsOwnerOrModerator, IsStaffOnly
from .serializers import (
    AutoApprovalRuleCreateSerializer,
    AutoApprovalRuleSerializer,
    HumanReviewSerializer,
    ProofScannerSerializer,
    SuspiciousSubmissionCreateSerializer,
    SuspiciousSubmissionSerializer,
    TaskBotCreateSerializer,
    TaskBotSerializer,
)
from .services import BotService, ModerationService, SubmissionService

logger = logging.getLogger(__name__)


# =============================================================================
# AutoApprovalRule
# =============================================================================

class AutoApprovalRuleViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [CanManageRules]
    filterset_class    = AutoApprovalRuleFilter
    ordering_fields    = ["priority", "name", "created_at"]
    ordering           = ["priority"]

    def get_queryset(self):
        return AutoApprovalRule.objects.select_related("created_by").all()

    def get_serializer_class(self):
        if self.action == "create":
            return AutoApprovalRuleCreateSerializer
        return AutoApprovalRuleSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def destroy(self, request, *args, **kwargs):
        rule = self.get_object()
        if rule.is_system:
            return Response(
                {"detail": "System rules cannot be deleted."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["post"], url_path="toggle")
    def toggle_active(self, request: Request, pk=None) -> Response:
        rule = self.get_object()
        rule.is_active = not rule.is_active
        rule.save(update_fields=["is_active", "updated_at"])
        return Response(AutoApprovalRuleSerializer(rule).data)


# =============================================================================
# SuspiciousSubmission
# =============================================================================

class SuspiciousSubmissionViewSet(
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsOwnerOrModerator]
    filterset_class    = SuspiciousSubmissionFilter
    ordering_fields    = ["created_at", "risk_score", "ai_confidence"]
    ordering           = ["-created_at"]

    def get_queryset(self):
        qs = SuspiciousSubmission.objects.select_full()
        user = self.request.user
        if user.is_staff or user.groups.filter(name="moderators").exists():
            return qs
        return qs.for_user(user)

    def get_serializer_class(self):
        if self.action == "submit":
            return SuspiciousSubmissionCreateSerializer
        if self.action in ("approve", "reject", "escalate"):
            return HumanReviewSerializer
        return SuspiciousSubmissionSerializer

    @action(detail=False, methods=["post"], url_path="submit",
            permission_classes=[IsModeratorOrStaff])
    def submit(self, request: Request) -> Response:
        """
        Submit content for AI moderation.
        Queues a Celery task for async processing.
        """
        serializer = SuspiciousSubmissionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vd = serializer.validated_data

        try:
            from .tasks import scan_submission
            scan_submission.delay(
                content_type=vd["content_type"],
                content_id=vd["content_id"],
                submission_type=vd["submission_type"],
                user_id=str(request.user.pk),
                text_content=vd.get("text_content", ""),
                file_urls=vd.get("file_urls", []),
                metadata=vd.get("metadata", {}),
            )
        except Exception:
            logger.exception("submission.enqueue_failed")
            return Response(
                {"detail": "Submission queued but task dispatch failed. Will retry."},
                status=status.HTTP_202_ACCEPTED,
            )

        return Response(
            {"detail": "Submission accepted for moderation."},
            status=status.HTTP_202_ACCEPTED,
        )

    @action(detail=True, methods=["post"])
    def review(self, request: Request, pk=None) -> Response:
        """Human review: approve, reject, or escalate."""
        submission = self.get_object()
        serializer = HumanReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vd = serializer.validated_data

        action_name = vd["action"]
        note        = vd.get("note", "")

        if action_name == "approve":
            updated = SubmissionService.human_approve(
                submission=submission, reviewer=request.user, note=note
            )
        elif action_name == "reject":
            updated = SubmissionService.human_reject(
                submission=submission, reviewer=request.user, note=note
            )
        else:  # escalate
            from django.contrib.auth import get_user_model
            User = get_user_model()
            try:
                escalate_to = User.objects.get(pk=vd["escalate_to_user_id"])
            except User.DoesNotExist:
                return Response(
                    {"detail": "escalate_to_user_id does not exist."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            updated = SubmissionService.escalate(
                submission=submission, escalated_to=escalate_to, note=note
            )

        return Response(SuspiciousSubmissionSerializer(updated).data)

    @action(detail=False, methods=["get"], url_path="queue",
            permission_classes=[IsModeratorOrStaff])
    def review_queue(self, request: Request) -> Response:
        """Returns high-priority pending human-review submissions."""
        qs = (
            SuspiciousSubmission.objects
            .awaiting_review()
            .high_risk()
            .select_full()
            .order_by("-risk_score", "created_at")[:50]
        )
        return Response(SuspiciousSubmissionSerializer(qs, many=True).data)

    @action(detail=False, methods=["get"], url_path="stats",
            permission_classes=[IsModeratorOrStaff])
    def stats(self, request: Request) -> Response:
        """Aggregate stats for the moderator dashboard."""
        data = SuspiciousSubmission.objects.risk_stats()
        data["pending_count"]  = SuspiciousSubmission.objects.pending().count()
        data["review_count"]   = SuspiciousSubmission.objects.awaiting_review().count()
        data["escalated_count"] = SuspiciousSubmission.objects.escalated().count()
        return Response(data)


# =============================================================================
# ProofScanner
# =============================================================================

class ProofScannerViewSet(
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class   = ProofScannerSerializer
    permission_classes = [IsModeratorOrStaff]
    filterset_class    = ProofScannerFilter
    ordering           = ["-created_at"]

    def get_queryset(self):
        return ProofScanner.objects.select_related("submission").all()


# =============================================================================
# TaskBot
# =============================================================================

class TaskBotViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsStaffOnly]
    filterset_class    = TaskBotFilter
    ordering_fields    = ["name", "status", "created_at"]
    ordering           = ["name"]

    def get_queryset(self):
        return TaskBot.objects.select_related("assigned_to").all()

    def get_serializer_class(self):
        if self.action == "create":
            return TaskBotCreateSerializer
        return TaskBotSerializer

    @action(detail=True, methods=["post"], url_path="start")
    def start(self, request: Request, pk=None) -> Response:
        bot = self.get_object()
        try:
            bot = BotService.start_bot(bot)
            from .tasks import bot_process_task
            bot_process_task.delay(str(bot.pk))
        except BotAlreadyRunningError as exc:
            return Response({"detail": str(exc.detail)}, status=exc.status_code)
        return Response(TaskBotSerializer(bot).data)

    @action(detail=True, methods=["post"], url_path="stop")
    def stop(self, request: Request, pk=None) -> Response:
        bot = self.get_object()
        bot = BotService.stop_bot(bot)
        return Response(TaskBotSerializer(bot).data)

    @action(detail=True, methods=["get"], url_path="health")
    def health(self, request: Request, pk=None) -> Response:
        bot = self.get_object()
        return Response({
            "id":            str(bot.pk),
            "name":          bot.name,
            "status":        bot.status,
            "is_healthy":    bot.is_healthy,
            "last_heartbeat": bot.last_heartbeat,
            "retry_count":   bot.retry_count,
            "last_error":    bot.last_error,
        })
