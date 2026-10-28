from django.utils import timezone
from rest_framework import permissions
# =============================================================================
# auto_mod/viewsets.py
# =============================================================================

# from __future__ import annotations
import logging
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from django.db.models import Q

from .exceptions import BotAlreadyRunningError, SubmissionAlreadyProcessedError
from .filters import (ModerationQueueFilter, ModerationDecisionFilter, ModerationAppealFilter, MLModelVersionFilter, AutoApprovalRuleFilter, ProofScannerFilter, SuspiciousSubmissionFilter, TaskBotFilter,
                      TaskBotFilter
)
from .models import (
    AutoApprovalRule, ContentSignal, MLModelVersion, 
    ModerationAppeal, ModerationDecision, ModerationQueue, 
    ProofScanner, SuspiciousSubmission, TaskBot
)
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
from api.auto_mod.services import BotService, ModerationService, SubmissionService
from api.auto_mod.choices import ModelType

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


# =============================================================================
# New ViewSets for Enhanced Moderation System
# =============================================================================

class ModerationQueueViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """
    ViewSet for managing moderation queue items.
    """
    permission_classes = [IsModeratorOrStaff]
    filterset_class = ModerationQueueFilter
    search_fields = ["submission__content_id", "processing_notes"]
    ordering_fields = ["queued_at", "due_at", "priority", "escalation_level"]
    ordering = ["-queued_at"]

    def get_queryset(self):
        return ModerationQueue.objects.select_related(
            "submission", "assigned_to", "assigned_by"
        ).prefetch_related("submission__decisions", "submission__signals")

    def get_serializer_class(self):
        from .serializers import ModerationQueueSerializer
        return ModerationQueueSerializer

    @action(detail=True, methods=["post"], url_path="assign")
    def assign(self, request: Request, pk=None) -> Response:
        """Assign queue item to a moderator."""
        queue_item = self.get_object()
        moderator_id = request.data.get("moderator_id")
        notes = request.data.get("notes", "")
        
        if not moderator_id:
            return Response(
                {"detail": "moderator_id is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        try:
            moderator = User.objects.get(pk=moderator_id)
            
            # Use service for assignment
            from api.auto_mod.services.ModerationQueueService import ModerationQueueService
            queue_service = ModerationQueueService()
            
            updated_item = queue_service.assign_to_moderator(
                queue_item=queue_item,
                moderator=moderator,
                assigned_by=request.user,
                notes=notes
            )
            
            return Response(ModerationQueueSerializer(updated_item).data)
        except User.DoesNotExist:
            return Response(
                {"detail": "Moderator not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as exc:
            return Response(
                {"detail": str(exc)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=["post"], url_path="escalate")
    def escalate(self, request: Request, pk=None) -> Response:
        """Escalate queue item to higher priority."""
        queue_item = self.get_object()
        new_priority = request.data.get("priority")
        reason = request.data.get("reason", "Manual escalation")
        
        try:
            # Use service for escalation
            from api.auto_mod.services.ModerationQueueService import ModerationQueueService
            queue_service = ModerationQueueService()
            
            updated_item = queue_service.escalate_queue_item(
                queue_item=queue_item,
                new_priority=new_priority,
                reason=reason,
                escalated_by=request.user
            )
            
            return Response(ModerationQueueSerializer(updated_item).data)
        except Exception as exc:
            return Response(
                {"detail": str(exc)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=["post"], url_path="release")
    def release(self, request: Request, pk=None) -> Response:
        """Release queue item back to unassigned pool."""
        queue_item = self.get_object()
        reason = request.data.get("reason", "Released by moderator")
        
        try:
            from api.auto_mod.services.ModerationQueueService import ModerationQueueService
            queue_service = ModerationQueueService()
            
            updated_item = queue_service.release_queue_item(
                queue_item=queue_item,
                released_by=request.user,
                reason=reason
            )
            
            return Response(ModerationQueueSerializer(updated_item).data)
        except Exception as exc:
            return Response(
                {"detail": str(exc)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=["post"], url_path="prioritize")
    def prioritize(self, request: Request, pk=None) -> Response:
        """Change queue item priority."""
        queue_item = self.get_object()
        new_priority = request.data.get("priority")
        reason = request.data.get("reason", "Priority change")
        
        if not new_priority:
            return Response(
                {"detail": "priority is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            queue_item.priority = new_priority
            queue_item.processing_notes = f"Priority changed: {reason}"
            queue_item.save(update_fields=["priority", "processing_notes", "updated_at"])
            
            return Response(ModerationQueueSerializer(queue_item).data)
        except Exception as exc:
            return Response(
                {"detail": str(exc)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=["get"], url_path="my-queue")
    def my_queue(self, request: Request) -> Response:
        """Get queue items assigned to current user."""
        from api.auto_mod.services.ModerationQueueService import ModerationQueueService
        queue_service = ModerationQueueService()
        
        my_items = queue_service.get_queue_items_for_moderator(
            moderator=request.user,
            limit=100,
            include_completed=False
        )
        
        serializer = ModerationQueueSerializer(my_items, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="statistics")
    def statistics(self, request: Request) -> Response:
        """Get queue statistics."""
        from api.auto_mod.services.ModerationQueueService import ModerationQueueService
        queue_service = ModerationQueueService()
        
        stats = queue_service.get_queue_statistics()
        return Response(stats)

    @action(detail=False, methods=["post"], url_path="auto-assign")
    def auto_assign(self, request: Request) -> Response:
        """Auto-assign unassigned queue items."""
        batch_size = request.data.get("batch_size", 50)
        submission_type = request.data.get("submission_type")
        
        try:
            from api.auto_mod.services.ModerationQueueService import ModerationQueueService
            queue_service = ModerationQueueService()
            
            results = queue_service.auto_assign_queue_items(
                batch_size=batch_size,
                submission_type=submission_type
            )
            
            return Response(results)
        except Exception as exc:
            return Response(
                {"detail": str(exc)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=["post"], url_path="escalate-overdue")
    def escalate_overdue(self, request: Request) -> Response:
        """Escalate all overdue queue items."""
        try:
            from api.auto_mod.services.ModerationQueueService import ModerationQueueService
            queue_service = ModerationQueueService()
            
            results = queue_service.escalate_overdue_items()
            return Response(results)
        except Exception as exc:
            return Response(
                {"detail": str(exc)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=["get"], url_path="available-moderators")
    def available_moderators(self, request: Request) -> Response:
        """Get list of available moderators."""
        submission_type = request.query_params.get("submission_type")
        max_workload = int(request.query_params.get("max_workload", 10))
        
        try:
            from api.auto_mod.services.ModerationQueueService import ModerationQueueService
            queue_service = ModerationQueueService()
            
            moderators = queue_service.get_available_moderators(
                submission_type=submission_type,
                max_workload=max_workload
            )
            
            # Return moderator info
            data = []
            for moderator in moderators:
                data.append({
                    "id": str(moderator.pk),
                    "username": moderator.username,
                    "email": moderator.email,
                    "first_name": moderator.first_name,
                    "last_name": moderator.last_name
                })
            
            return Response(data)
        except Exception as exc:
            return Response(
                {"detail": str(exc)}, 
                status=status.HTTP_400_BAD_REQUEST
            )


class ModerationDecisionViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """
    ViewSet for viewing and managing moderation decisions.
    """
    permission_classes = [IsModeratorOrStaff]
    filterset_class = ModerationDecisionFilter
    search_fields = ["submission__content_id", "reason"]
    ordering_fields = ["decided_at", "confidence"]
    ordering = ["-decided_at"]

    def get_queryset(self):
        return ModerationDecision.objects.select_related(
            "submission", "decided_by", "applied_rule"
        ).prefetch_related("appeals")

    def get_serializer_class(self):
        from .serializers import ModerationDecisionSerializer
        return ModerationDecisionSerializer

    def create(self, request: Request, *args, **kwargs) -> Response:
        """Create a moderation decision."""
        try:
            submission_id = request.data.get("submission_id")
            decision_type = request.data.get("decision_type")
            reason = request.data.get("reason", "")
            confidence = request.data.get("confidence", 0.8)
            
            if not all([submission_id, decision_type]):
                return Response(
                    {"detail": "submission_id and decision_type are required"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            from .models import SuspiciousSubmission
            submission = SuspiciousSubmission.objects.get(pk=submission_id)
            
            # Create decision
            decision = ModerationDecision.objects.create(
                submission=submission,
                decision_type=decision_type,
                reason=reason,
                confidence=confidence,
                decided_by=request.user,
                is_automated=False
            )
            
            # Update submission status
            from .choices import ModerationStatus
            if decision_type == "approve":
                submission.status = ModerationStatus.HUMAN_APPROVED
            elif decision_type == "reject":
                submission.status = ModerationStatus.HUMAN_REJECTED
            elif decision_type == "escalate":
                submission.status = ModerationStatus.ESCALATED
            
            submission.save(update_fields=["status"])
            
            # Send signal
            from .signals import moderation_decision_made
            moderation_decision_made.send(
                sender=SuspiciousSubmission,
                submission=submission,
                decision=decision_type
            )
            
            return Response(ModerationDecisionSerializer(decision).data, status=status.HTTP_201_CREATED)
            
        except SuspiciousSubmission.DoesNotExist:
            return Response(
                {"detail": "Submission not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as exc:
            return Response(
                {"detail": str(exc)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=["post"], url_path="appeal")
    def create_appeal(self, request: Request, pk=None) -> Response:
        """Create an appeal against this decision."""
        decision = self.get_object()
        appeal_reason = request.data.get("reason")
        
        if not appeal_reason:
            return Response(
                {"detail": "reason is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from api.auto_mod.services.AppealService import AppealService
            appeal_service = AppealService()
            
            appeal = appeal_service.create_appeal(
                decision=decision,
                appellant=request.user,
                reason=appeal_reason
            )
            
            return Response({"appeal_id": str(appeal.pk)}, status=status.HTTP_201_CREATED)
            
        except Exception as exc:
            return Response(
                {"detail": str(exc)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=["post"], url_path="override")
    def override(self, request: Request, pk=None) -> Response:
        """Override this decision with a new one."""
        decision = self.get_object()
        new_decision_type = request.data.get("decision_type")
        new_reason = request.data.get("reason", "Decision overridden")
        new_confidence = request.data.get("confidence", 0.8)
        
        if not new_decision_type:
            return Response(
                {"detail": "decision_type is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Create new decision
            new_decision = ModerationDecision.objects.create(
                submission=decision.submission,
                decision_type=new_decision_type,
                reason=new_reason,
                confidence=new_confidence,
                decided_by=request.user,
                is_automated=False,
                previous_decision=decision
            )
            
            # Update submission status
            from .choices import ModerationStatus
            if new_decision_type == "approve":
                decision.submission.status = ModerationStatus.HUMAN_APPROVED
            elif new_decision_type == "reject":
                decision.submission.status = ModerationStatus.HUMAN_REJECTED
            elif new_decision_type == "escalate":
                decision.submission.status = ModerationStatus.ESCALATED
            
            decision.submission.save(update_fields=["status"])
            
            # Send override signal
            from .signals import decision_overridden
            decision_overridden.send(
                sender=ModerationDecision,
                old_decision=decision,
                new_decision=new_decision,
                reason=new_reason
            )
            
            return Response(ModerationDecisionSerializer(new_decision).data)
            
        except Exception as exc:
            return Response(
                {"detail": str(exc)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=["post"], url_path="bulk-approve")
    def bulk_approve(self, request: Request) -> Response:
        """Bulk approve multiple submissions."""
        submission_ids = request.data.get("submission_ids", [])
        reason = request.data.get("reason", "Bulk approval")
        confidence = request.data.get("confidence", 0.8)
        
        if not submission_ids:
            return Response(
                {"detail": "submission_ids is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from .models import SuspiciousSubmission
            from .choices import ModerationStatus
            
            approved_count = 0
            errors = []
            
            for submission_id in submission_ids:
                try:
                    submission = SuspiciousSubmission.objects.get(pk=submission_id)
                    
                    # Create decision
                    decision = ModerationDecision.objects.create(
                        submission=submission,
                        decision_type="approve",
                        reason=reason,
                        confidence=confidence,
                        decided_by=request.user,
                        is_automated=False
                    )
                    
                    # Update submission
                    submission.status = ModerationStatus.HUMAN_APPROVED
                    submission.save(update_fields=["status"])
                    
                    approved_count += 1
                    
                except Exception as exc:
                    errors.append({
                        "submission_id": submission_id,
                        "error": str(exc)
                    })
            
            return Response({
                "approved": approved_count,
                "errors": errors
            })
            
        except Exception as exc:
            return Response(
                {"detail": str(exc)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=["post"], url_path="bulk-reject")
    def bulk_reject(self, request: Request) -> Response:
        """Bulk reject multiple submissions."""
        submission_ids = request.data.get("submission_ids", [])
        reason = request.data.get("reason", "Bulk rejection")
        confidence = request.data.get("confidence", 0.8)
        
        if not submission_ids:
            return Response(
                {"detail": "submission_ids is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from .models import SuspiciousSubmission
            from .choices import ModerationStatus
            
            rejected_count = 0
            errors = []
            
            for submission_id in submission_ids:
                try:
                    submission = SuspiciousSubmission.objects.get(pk=submission_id)
                    
                    # Create decision
                    decision = ModerationDecision.objects.create(
                        submission=submission,
                        decision_type="reject",
                        reason=reason,
                        confidence=confidence,
                        decided_by=request.user,
                        is_automated=False
                    )
                    
                    # Update submission
                    submission.status = ModerationStatus.HUMAN_REJECTED
                    submission.save(update_fields=["status"])
                    
                    rejected_count += 1
                    
                except Exception as exc:
                    errors.append({
                        "submission_id": submission_id,
                        "error": str(exc)
                    })
            
            return Response({
                "rejected": rejected_count,
                "errors": errors
            })
            
        except Exception as exc:
            return Response(
                {"detail": str(exc)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=["post"], url_path="bulk-escalate")
    def bulk_escalate(self, request: Request) -> Response:
        """Bulk escalate multiple submissions."""
        submission_ids = request.data.get("submission_ids", [])
        reason = request.data.get("reason", "Bulk escalation")
        confidence = request.data.get("confidence", 0.8)
        
        if not submission_ids:
            return Response(
                {"detail": "submission_ids is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from .models import SuspiciousSubmission
            from .choices import ModerationStatus
            
            escalated_count = 0
            errors = []
            
            for submission_id in submission_ids:
                try:
                    submission = SuspiciousSubmission.objects.get(pk=submission_id)
                    
                    # Create decision
                    decision = ModerationDecision.objects.create(
                        submission=submission,
                        decision_type="escalate",
                        reason=reason,
                        confidence=confidence,
                        decided_by=request.user,
                        is_automated=False
                    )
                    
                    # Update submission
                    submission.status = ModerationStatus.ESCALATED
                    submission.save(update_fields=["status"])
                    
                    escalated_count += 1
                    
                except Exception as exc:
                    errors.append({
                        "submission_id": submission_id,
                        "error": str(exc)
                    })
            
            return Response({
                "escalated": escalated_count,
                "errors": errors
            })
            
        except Exception as exc:
            return Response(
                {"detail": str(exc)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=["get"], url_path="statistics")
    def statistics(self, request: Request) -> Response:
        """Get decision statistics."""
        from django.db.models import Count, Avg
        from django.utils import timezone
        from datetime import timedelta
        
        # Time period
        days_back = int(request.query_params.get("days_back", 30))
        cutoff_date = timezone.now() - timedelta(days=days_back)
        
        # Base queryset
        decisions = ModerationDecision.objects.filter(decided_at__gte=cutoff_date)
        
        # Decision type breakdown
        decision_stats = decisions.values('decision_type').annotate(
            count=Count('id'),
            avg_confidence=Avg('confidence')
        ).order_by('-count')
        
        # Automated vs manual
        automated_stats = decisions.values('is_automated').annotate(
            count=Count('id')
        ).order_by('is_automated')
        
        # By decider
        decider_stats = decisions.values('decided_by__username').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        return Response({
            "period_days": days_back,
            "total_decisions": decisions.count(),
            "decision_breakdown": list(decision_stats),
            "automation_breakdown": list(automated_stats),
            "top_deciders": list(decider_stats)
        })

    @action(detail=True, methods=["get"], url_path="history")
    def history(self, request: Request, pk=None) -> Response:
        """Get decision history for this submission."""
        decision = self.get_object()
        
        # Get all decisions for this submission
        all_decisions = ModerationDecision.objects.filter(
            submission=decision.submission
        ).order_by('decided_at')
        
        serializer = ModerationDecisionSerializer(all_decisions, many=True)
        return Response(serializer.data)


class ModerationAppealViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """
    ViewSet for managing moderation appeals.
    """
    permission_classes = [IsModeratorOrStaff]
    filterset_class = ModerationAppealFilter
    search_fields = ["user__username", "reason", "review_notes"]
    ordering_fields = ["created_at", "reviewed_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return ModerationAppeal.objects.select_related(
            "user", "original_decision", "reviewed_by", "submission"
        ).prefetch_related("original_decision__appeals")

    def get_serializer_class(self):
        from .serializers import ModerationAppealSerializer
        return ModerationAppealSerializer

    def create(self, request: Request, *args, **kwargs) -> Response:
        """Submit a new appeal."""
        try:
            decision_id = request.data.get("decision_id")
            reason = request.data.get("reason")
            additional_data = request.data.get("additional_data", {})
            
            if not all([decision_id, reason]):
                return Response(
                    {"detail": "decision_id and reason are required"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            from .models import ModerationDecision
            decision = ModerationDecision.objects.get(pk=decision_id)
            
            # Use service to create appeal
            from api.auto_mod.services.AppealService import AppealService
            appeal_service = AppealService()
            
            appeal = appeal_service.create_appeal(
                decision=decision,
                appellant=request.user,
                reason=reason,
                additional_data=additional_data
            )
            
            return Response(ModerationAppealSerializer(appeal).data, status=status.HTTP_201_CREATED)
            
        except ModerationDecision.DoesNotExist:
            return Response(
                {"detail": "Decision not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as exc:
            return Response(
                {"detail": str(exc)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=["post"], url_path="assign")
    def assign_reviewer(self, request: Request, pk=None) -> Response:
        """Assign appeal to a reviewer."""
        appeal = self.get_object()
        reviewer_id = request.data.get("reviewer_id")
        notes = request.data.get("notes", "")
        
        if not reviewer_id:
            return Response(
                {"detail": "reviewer_id is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        try:
            reviewer = User.objects.get(pk=reviewer_id)
            
            # Use service for assignment
            from api.auto_mod.services.AppealService import AppealService
            appeal_service = AppealService()
            
            updated_appeal = appeal_service.assign_reviewer(
                appeal=appeal,
                reviewer=reviewer,
                assigned_by=request.user,
                notes=notes
            )
            
            return Response(ModerationAppealSerializer(updated_appeal).data)
        except User.DoesNotExist:
            return Response(
                {"detail": "Reviewer not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as exc:
            return Response(
                {"detail": str(exc)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=["post"], url_path="resolve")
    def resolve(self, request: Request, pk=None) -> Response:
        """Resolve the appeal with a final decision."""
        appeal = self.get_object()
        final_decision = request.data.get("final_decision")
        final_reason = request.data.get("final_reason")
        override_original = request.data.get("override_original", False)
        
        if not final_decision or not final_reason:
            return Response(
                {"detail": "final_decision and final_reason are required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Use service for resolution
            from api.auto_mod.services.AppealService import AppealService
            appeal_service = AppealService()
            
            updated_appeal = appeal_service.resolve_appeal(
                appeal=appeal,
                final_decision=final_decision,
                final_reason=final_reason,
                reviewer=request.user,
                override_original=override_original
            )
            
            return Response(ModerationAppealSerializer(updated_appeal).data)
        except Exception as exc:
            return Response(
                {"detail": str(exc)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=["post"], url_path="escalate")
    def escalate(self, request: Request, pk=None) -> Response:
        """Escalate appeal to higher authority."""
        appeal = self.get_object()
        escalated_to_id = request.data.get("escalated_to_id")
        reason = request.data.get("reason", "Appeal escalation")
        
        if not escalated_to_id:
            return Response(
                {"detail": "escalated_to_id is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        try:
            escalated_to = User.objects.get(pk=escalated_to_id)
            
            # Use service for escalation
            from api.auto_mod.services.AppealService import AppealService
            appeal_service = AppealService()
            
            updated_appeal = appeal_service.escalate_appeal(
                appeal=appeal,
                escalated_to=escalated_to,
                reason=reason,
                escalated_by=request.user
            )
            
            return Response(ModerationAppealSerializer(updated_appeal).data)
        except User.DoesNotExist:
            return Response(
                {"detail": "Escalated to user not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as exc:
            return Response(
                {"detail": str(exc)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=["get"], url_path="my-appeals")
    def my_appeals(self, request: Request) -> Response:
        """Get appeals submitted by current user."""
        from api.auto_mod.services.AppealService import AppealService
        appeal_service = AppealService()
        
        my_appeals = appeal_service.get_pending_appeals(
            reviewer=request.user,
            limit=100
        )
        
        serializer = ModerationAppealSerializer(my_appeals, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="pending")
    def pending(self, request: Request) -> Response:
        """Get all pending appeals for review."""
        submission_type = request.query_params.get("submission_type")
        limit = int(request.query_params.get("limit", 100))
        
        try:
            from api.auto_mod.services.AppealService import AppealService
            appeal_service = AppealService()
            
            pending_appeals = appeal_service.get_pending_appeals(
                reviewer=None,  # Get all pending
                submission_type=submission_type,
                limit=limit
            )
            
            serializer = ModerationAppealSerializer(pending_appeals, many=True)
            return Response(serializer.data)
        except Exception as exc:
            return Response(
                {"detail": str(exc)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=["post"], url_path="auto-assign")
    def auto_assign(self, request: Request) -> Response:
        """Auto-assign pending appeals to reviewers."""
        batch_size = request.data.get("batch_size", 20)
        submission_type = request.data.get("submission_type")
        
        try:
            from api.auto_mod.services.AppealService import AppealService
            appeal_service = AppealService()
            
            results = appeal_service.auto_assign_appeals(
                batch_size=batch_size,
                submission_type=submission_type
            )
            
            return Response(results)
        except Exception as exc:
            return Response(
                {"detail": str(exc)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=["get"], url_path="statistics")
    def statistics(self, request: Request) -> Response:
        """Get appeal statistics."""
        try:
            from api.auto_mod.services.AppealService import AppealService
            appeal_service = AppealService()
            
            stats = appeal_service.get_appeal_statistics()
            return Response(stats)
        except Exception as exc:
            return Response(
                {"detail": str(exc)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=["get"], url_path="reviewer-workload")
    def reviewer_workload(self, request: Request) -> Response:
        """Get workload statistics for reviewers."""
        days_back = int(request.query_params.get("days_back", 7))
        
        try:
            from api.auto_mod.services.AppealService import AppealService
            appeal_service = AppealService()
            
            # Get all reviewers with workload
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            reviewers = User.objects.filter(
                Q(is_staff=True) | Q(groups__name__in=['appeal_reviewers', 'senior_moderators']),
                is_active=True
            ).distinct()
            
            workload_data = []
            for reviewer in reviewers:
                workload = appeal_service.get_reviewer_workload(reviewer, days_back)
                workload_data.append(workload)
            
            return Response(workload_data)
        except Exception as exc:
            return Response(
                {"detail": str(exc)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=["get"], url_path="history")
    def history(self, request: Request, pk=None) -> Response:
        """Get appeal history for this submission."""
        appeal = self.get_object()
        
        try:
            from api.auto_mod.services.AppealService import AppealService
            appeal_service = AppealService()
            
            history = appeal_service.get_appeal_history_for_submission(appeal.submission)
            return Response(history)
        except Exception as exc:
            return Response(
                {"detail": str(exc)}, 
                status=status.HTTP_400_BAD_REQUEST
            )


class MLModelVersionViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """
    ViewSet for managing ML model versions.
    """
    permission_classes = [IsStaffOnly]
    filterset_class = MLModelVersionFilter
    search_fields = ["version", "display_name", "description"]
    ordering_fields = ["created_at", "deployed_at", "accuracy"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return MLModelVersion.objects.select_related("created_by").prefetch_related("training_logs")

    def get_serializer_class(self):
        from .serializers import MLModelVersionSerializer
        return MLModelVersionSerializer

    def create(self, request: Request, *args, **kwargs) -> Response:
        """Create a new ML model version."""
        try:
            # Use service for creation
            from api.auto_mod.services.MLModelService import MLModelService
            model_service = MLModelService()
            
            model_version = model_service.create_model_version(
                model_type=request.data.get("model_type"),
                version=request.data.get("version"),
                display_name=request.data.get("display_name"),
                description=request.data.get("description", ""),
                file_path=request.data.get("file_path"),
                model_file=request.FILES.get("model_file"),
                created_by=request.user,
                hyperparameters=request.data.get("hyperparameters", {}),
                metadata=request.data.get("metadata", {})
            )
            
            return Response(MLModelVersionSerializer(model_version).data, status=status.HTTP_201_CREATED)
            
        except Exception as exc:
            return Response(
                {"detail": str(exc)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=["post"], url_path="deploy")
    def deploy(self, request: Request, pk=None) -> Response:
        """Deploy this model version to production."""
        model_version = self.get_object()
        deployment_config = request.data.get("config", {})
        
        try:
            from api.auto_mod.services.MLModelService import MLModelService
            model_service = MLModelService()
            
            updated_model = model_service.deploy_model(
                model_version=model_version,
                deployed_by=request.user,
                deployment_config=deployment_config
            )
            
            return Response(MLModelVersionSerializer(updated_model).data)
        except Exception as exc:
            return Response(
                {"detail": str(exc)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=["post"], url_path="train")
    def train(self, request: Request, pk=None) -> Response:
        """Start training for this model version."""
        model_version = self.get_object()
        training_config = request.data.get("config", {})
        training_data_version = request.data.get("training_data_version")
        
        try:
            from api.auto_mod.services.MLModelService import MLModelService
            model_service = MLModelService()
            
            updated_model = model_service.start_model_training(
                model_version=model_version,
                training_config=training_config,
                training_data_version=training_data_version,
                created_by=request.user
            )
            
            return Response(MLModelVersionSerializer(updated_model).data)
        except Exception as exc:
            return Response(
                {"detail": str(exc)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=["post"], url_path="complete-training")
    def complete_training(self, request: Request, pk=None) -> Response:
        """Complete model training with performance metrics."""
        model_version = self.get_object()
        performance_metrics = request.data.get("performance_metrics", {})
        training_log = request.data.get("training_log", "")
        training_duration_hours = request.data.get("training_duration_hours")
        
        if not performance_metrics:
            return Response(
                {"detail": "performance_metrics is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from api.auto_mod.services.MLModelService import MLModelService
            model_service = MLModelService()
            
            updated_model = model_service.complete_model_training(
                model_version=model_version,
                performance_metrics=performance_metrics,
                training_log=training_log,
                training_duration_hours=training_duration_hours
            )
            
            return Response(MLModelVersionSerializer(updated_model).data)
        except Exception as exc:
            return Response(
                {"detail": str(exc)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=["post"], url_path="retire")
    def retire(self, request: Request, pk=None) -> Response:
        """Retire this model version."""
        model_version = self.get_object()
        retirement_reason = request.data.get("reason", "Manual retirement")
        
        try:
            from api.auto_mod.services.MLModelService import MLModelService
            model_service = MLModelService()
            
            updated_model = model_service.retire_model(
                model_version=model_version,
                retirement_reason=retirement_reason,
                retired_by=request.user
            )
            
            return Response(MLModelVersionSerializer(updated_model).data)
        except Exception as exc:
            return Response(
                {"detail": str(exc)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=["get"], url_path="active")
    def get_active_models(self, request: Request) -> Response:
        """Get all currently active model versions."""
        try:
            from api.auto_mod.services.MLModelService import MLModelService
            model_service = MLModelService()
            
            active_models = model_service.get_active_models()
            serializer = MLModelVersionSerializer(active_models, many=True)
            return Response(serializer.data)
        except Exception as exc:
            return Response(
                {"detail": str(exc)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=["get"], url_path="best-models")
    def get_best_models(self, request: Request) -> Response:
        """Get best performing model for each type."""
        try:
            from api.auto_mod.services.MLModelService import MLModelService
            model_service = MLModelService()
            
            best_models = []
            for model_type_choice in ModelType.choices:
                model_type = model_type_choice[0]
                best_model = model_service.get_best_model_for_type(model_type)
                if best_model:
                    best_models.append(best_model)
            
            serializer = MLModelVersionSerializer(best_models, many=True)
            return Response(serializer.data)
        except Exception as exc:
            return Response(
                {"detail": str(exc)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=["get"], url_path="health")
    def health_check(self, request: Request, pk=None) -> Response:
        """Check health of this model version."""
        model_version = self.get_object()
        
        try:
            from api.auto_mod.services.MLModelService import MLModelService
            model_service = MLModelService()
            
            health_data = model_service.check_model_health(model_version)
            return Response(health_data)
        except Exception as exc:
            return Response(
                {"detail": str(exc)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=["get"], url_path="performance-history")
    def performance_history(self, request: Request, pk=None) -> Response:
        """Get performance history for this model type."""
        model_version = self.get_object()
        limit = int(request.query_params.get("limit", 20))
        
        try:
            from api.auto_mod.services.MLModelService import MLModelService
            model_service = MLModelService()
            
            history = model_service.get_model_performance_history(
                model_type=model_version.model_type,
                limit=limit
            )
            return Response(history)
        except Exception as exc:
            return Response(
                {"detail": str(exc)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=["get"], url_path="compare")
    def compare_with(self, request: Request, pk=None) -> Response:
        """Compare this model with another version."""
        model_version = self.get_object()
        compare_with_id = request.query_params.get("compare_with")
        
        if not compare_with_id:
            return Response(
                {"detail": "compare_with parameter is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from .models import MLModelVersion
            other_model = MLModelVersion.objects.get(pk=compare_with_id)
            
            from api.auto_mod.services.MLModelService import MLModelService
            model_service = MLModelService()
            
            comparison = model_service.compare_model_versions(model_version, other_model)
            return Response(comparison)
        except MLModelVersion.DoesNotExist:
            return Response(
                {"detail": "Model to compare with not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as exc:
            return Response(
                {"detail": str(exc)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=["get"], url_path="statistics")
    def statistics(self, request: Request) -> Response:
        """Get comprehensive model statistics."""
        try:
            from api.auto_mod.services.MLModelService import MLModelService
            model_service = MLModelService()
            
            stats = model_service.get_model_statistics()
            return Response(stats)
        except Exception as exc:
            return Response(
                {"detail": str(exc)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=["post"], url_path="bulk-retire")
    def bulk_retire(self, request: Request) -> Response:
        """Bulk retire multiple model versions."""
        model_ids = request.data.get("model_ids", [])
        retirement_reason = request.data.get("reason", "Bulk retirement")
        
        if not model_ids:
            return Response(
                {"detail": "model_ids is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from api.auto_mod.services.MLModelService import MLModelService
            model_service = MLModelService()
            
            retired_count = 0
            errors = []
            
            for model_id in model_ids:
                try:
                    from .models import MLModelVersion
                    model = MLModelVersion.objects.get(pk=model_id)
                    
                    model_service.retire_model(
                        model_version=model,
                        retirement_reason=retirement_reason,
                        retired_by=request.user
                    )
                    
                    retired_count += 1
                    
                except Exception as exc:
                    errors.append({
                        "model_id": model_id,
                        "error": str(exc)
                    })
            
            return Response({
                "retired": retired_count,
                "errors": errors
            })
        except Exception as exc:
            return Response(
                {"detail": str(exc)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=["get"], url_path="training-status")
    def training_status(self, request: Request) -> Response:
        """Get status of all training models."""
        try:
            from .models import MLModelVersion
            from .choices import ModelTrainingStatus
            
            training_models = MLModelVersion.objects.filter(
                status=ModelTrainingStatus.TRAINING
            ).select_related("created_by")
            
            data = []
            for model in training_models:
                data.append({
                    "id": str(model.pk),
                    "model_type": model.model_type,
                    "version": model.version,
                    "display_name": model.display_name,
                    "created_by": model.created_by.username,
                    "training_started_at": model.updated_at,
                    "training_duration_hours": (
                        (timezone.now() - model.updated_at).total_seconds() / 3600
                    )
                })
            
            return Response(data)
        except Exception as exc:
            return Response(
                {"detail": str(exc)}, 
                status=status.HTTP_400_BAD_REQUEST
            )


class ContentSignalViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """
    ViewSet for viewing content signals.
    Note: Signals are typically created automatically during content analysis.
    """
    permission_classes = [IsModeratorOrStaff]
    filterset_fields = ["signal_type", "is_positive", "severity", "processed"]
    search_fields = ["submission__content_id", "value", "source"]
    ordering_fields = ["created_at", "weight", "confidence"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return ContentSignal.objects.select_related("submission")

    def get_serializer_class(self):
        # Return appropriate serializer based on action
        from .serializers import SuspiciousSubmissionSerializer, SuspiciousSubmissionCreateSerializer
        if self.action in ('create', 'update', 'partial_update'):
            return SuspiciousSubmissionCreateSerializer
        from .serializers import ContentSignalSerializer
        return ContentSignalSerializer

    @action(detail=False, methods=["post"], url_path="bulk-create")
    def bulk_create_signals(self, request: Request) -> Response:
        """Create multiple signals in bulk."""
        signals_data = request.data.get("signals", [])
        
        if not signals_data:
            return Response(
                {"detail": "signals array is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        created_signals = []
        errors = []
        
        for signal_data in signals_data:
            try:
                submission_id = signal_data.get("submission_id")
                signal_type = signal_data.get("signal_type")
                value = signal_data.get("value")
                
                if not all([submission_id, signal_type, value]):
                    errors.append({"error": "Missing required fields", "data": signal_data})
                    continue
                
                # Get submission
                submission = SuspiciousSubmission.objects.get(pk=submission_id)
                
                # Create signal
                signal = ContentSignal.create_signal(
                    submission=submission,
                    signal_type=signal_type,
                    value=value,
                    weight=signal_data.get("weight", 1.0),
                    confidence=signal_data.get("confidence"),
                    source=signal_data.get("source", ""),
                    metadata=signal_data.get("metadata", {}),
                    is_positive=signal_data.get("is_positive", True),
                    severity=signal_data.get("severity", "low")
                )
                
                created_signals.append(str(signal.pk))
                
            except Exception as exc:
                errors.append({"error": str(exc), "data": signal_data})
        
        return Response({
            "created": len(created_signals),
            "signal_ids": created_signals,
            "errors": errors
        })

    @action(detail=True, methods=["post"], url_path="process")
    def process_signal(self, request: Request, pk=None) -> Response:
        """Mark signal as processed."""
        signal = self.get_object()
        
        if signal.processed:
            return Response(
                {"detail": "Signal is already processed"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        signal.mark_processed()
        signal.save()
        
        return Response({"status": "processed"})

    @action(detail=False, methods=["get"], url_path="unprocessed")
    def get_unprocessed_signals(self, request: Request) -> Response:
        """Get all unprocessed signals."""
        unprocessed = ContentSignal.objects.unprocessed().order_by("-created_at")[:100]
        
        # Serializer resolved from registry dynamically
        data = []
        for signal in unprocessed:
            data.append({
                "id": str(signal.pk),
                "submission_id": str(signal.submission.pk),
                "signal_type": signal.signal_type,
                "value": signal.value,
                "weight": signal.weight,
                "confidence": signal.confidence,
                "created_at": signal.created_at
            })
        
        return Response(data)


# =============================================================================
# Compliance model viewsets
# =============================================================================

from .models import (
    ModerationRule as _ModerationRule,
    ModerationAction as _ModerationAction,
    ModerationLog as _ModerationLog,
    ContentFlag as _ContentFlag,
    AutoModerationQueue as _AutoModerationQueue,
    ModerationStats as _ModerationStats,
)
from .serializers import (
    ModerationRuleSerializer,
    ModerationActionSerializer,
    ModerationLogSerializer,
    ContentFlagSerializer,
    AutoModerationQueueSerializer,
    ModerationStatsSerializer,
)


class ModerationRuleViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    queryset         = _ModerationRule.objects.all()
    serializer_class = ModerationRuleSerializer
    permission_classes = [permissions.IsAdminUser]


class ModerationActionViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset         = _ModerationAction.objects.all()
    serializer_class = ModerationActionSerializer
    permission_classes = [permissions.IsAdminUser]


class ModerationLogViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset         = _ModerationLog.objects.all()
    serializer_class = ModerationLogSerializer
    permission_classes = [permissions.IsAdminUser]


class ContentFlagViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset         = _ContentFlag.objects.all()
    serializer_class = ContentFlagSerializer


class AutoModerationQueueViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset         = _AutoModerationQueue.objects.all()
    serializer_class = AutoModerationQueueSerializer
    permission_classes = [permissions.IsAdminUser]


class ModerationStatsViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset         = _ModerationStats.objects.all()
    serializer_class = ModerationStatsSerializer
    permission_classes = [permissions.IsAdminUser]


# =============================================================================
# Offerwall / Monlix ViewSets
# =============================================================================
from .offerwall import (
    VirtualCurrencyConfig as _VC, OfferwallOfferType as _OOT,
    OfferwallConfig as _OC, PostbackLog as _PBL, SiteApproval as _SA,
    PerformanceReport as _PR, PaymentSchedule as _PS, OfferwallPromotion as _OP,
    PostbackService, SiteApprovalService, VirtualCurrencyService,
    PerformanceReportService, PaymentScheduleService,
)
from .serializers import (
    VirtualCurrencyConfigSerializer, OfferwallOfferTypeSerializer,
    OfferwallConfigSerializer, PostbackLogSerializer, SiteApprovalSerializer,
    PerformanceReportSerializer, PaymentScheduleSerializer, OfferwallPromotionSerializer,
)
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status as http_status


class VirtualCurrencyConfigViewSet(
    mixins.CreateModelMixin, mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin, mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """Manage per-publisher virtual currency config (name, multiplier, award settings)."""
    queryset         = _VC.objects.all()
    serializer_class = VirtualCurrencyConfigSerializer
    permission_classes = [permissions.IsAdminUser]


class OfferwallOfferTypeViewSet(
    mixins.CreateModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
    mixins.ListModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet,
):
    """Manage offer types: Survey, Video, GameInstall, AppInstall, Task."""
    queryset         = _OOT.objects.filter(is_active=True)
    serializer_class = OfferwallOfferTypeSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        offer_type = self.request.query_params.get('offer_type')
        os_target  = self.request.query_params.get('os')
        if offer_type: qs = qs.filter(offer_type=offer_type)
        if os_target:  qs = qs.filter(os_target=os_target)
        return qs


class OfferwallConfigViewSet(
    mixins.CreateModelMixin, mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin, mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """Publisher offerwall widget configuration (theme, sorting, embed)."""
    queryset         = _OC.objects.all()
    serializer_class = OfferwallConfigSerializer
    permission_classes = [permissions.IsAdminUser]

    @action(detail=True, methods=['get'], url_path='sdk-config')
    def sdk_config(self, request, pk=None):
        """Return SDK integration config for a given platform."""
        from .offerwall import OfferwallSDKBridge
        obj      = self.get_object()
        platform = request.query_params.get('platform', 'web')
        config   = OfferwallSDKBridge.get_integration_config(obj.publisher_id, platform)
        return Response(config)

    @action(detail=True, methods=['get'], url_path='embed')
    def embed(self, request, pk=None):
        """Return embed HTML for this publisher's offerwall."""
        obj       = self.get_object()
        user_id   = request.query_params.get('user_id', '{{USER_ID}}')
        embed_html = obj.get_embed_html(user_id)
        return Response({"embed_html": embed_html, "publisher_id": obj.publisher_id})


class PostbackLogViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet,
):
    """View S2S postback logs — verified, rejected, duplicate, retried."""
    queryset         = _PBL.objects.all()
    serializer_class = PostbackLogSerializer
    permission_classes = [permissions.IsAdminUser]

    def get_queryset(self):
        qs = super().get_queryset()
        publisher = self.request.query_params.get('publisher_id')
        status    = self.request.query_params.get('status')
        if publisher: qs = qs.filter(publisher_id=publisher)
        if status:    qs = qs.filter(status=status)
        return qs

    @action(detail=False, methods=['post'], url_path='receive',
            permission_classes=[permissions.AllowAny])
    def receive(self, request):
        """
        S2S postback endpoint.
        POST /api/auto_mod/postback-logs/receive/
        """
        data           = request.data
        publisher_id   = data.get('publisherId') or data.get('publisher_id', '')
        user_id        = data.get('userId')       or data.get('user_id', '')
        transaction_id = data.get('transactionId')
        reward_value   = float(data.get('rewardValue') or data.get('reward_value', 0))
        received_sig   = data.get('secretKey')    or data.get('signature', '')
        user_ip        = data.get('userIp')        or request.META.get('REMOTE_ADDR', '')
        offer_id       = data.get('offerId', '')

        if not all([publisher_id, user_id, transaction_id]):
            return Response({"error": "Missing required fields"}, status=400)

        # Get publisher secret
        try:
            cfg    = _OC.objects.get(publisher_id=publisher_id)
            secret = cfg.postback_secret
        except _OC.DoesNotExist:
            return Response({"error": "Publisher not found"}, status=404)

        result = PostbackService.process(
            publisher_id=publisher_id, user_id=user_id,
            transaction_id=transaction_id, reward_value=reward_value,
            secret=secret, received_sig=received_sig,
            user_ip=user_ip, offer_id=offer_id, raw_payload=dict(data),
        )
        code = 200 if result["status"] in ("verified", "duplicate") else 400
        return Response(result, status=code)

    @action(detail=False, methods=['post'], url_path='retry')
    def retry(self, request):
        """Retry failed postbacks for a publisher."""
        publisher_id = request.data.get('publisher_id', '')
        result = PostbackService.retry_failed(publisher_id)
        return Response(result)


class SiteApprovalViewSet(
    mixins.CreateModelMixin, mixins.RetrieveModelMixin,
    mixins.ListModelMixin, viewsets.GenericViewSet,
):
    """Publisher site approval workflow (submit, approve, reject)."""
    queryset         = _SA.objects.all()
    serializer_class = SiteApprovalSerializer

    def get_permissions(self):
        if self.action in ('approve', 'reject', 'list'):
            return [permissions.IsAdminUser()]
        return [permissions.IsAuthenticated()]

    def create(self, request, *args, **kwargs):
        data   = request.data
        result = SiteApprovalService.submit_for_approval(
            publisher_id=data.get('publisher_id', ''),
            site_url=data.get('site_url', ''),
            site_category=data.get('site_category', ''),
            monthly_traffic=data.get('monthly_traffic', ''),
            description=data.get('description', ''),
        )
        return Response(SiteApprovalSerializer(result).data, status=201)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve a publisher site (issues API keys)."""
        obj = self.get_object()
        SiteApprovalService.approve(obj, request.user)
        return Response(SiteApprovalSerializer(obj).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject a publisher site."""
        obj    = self.get_object()
        reason = request.data.get('reason', '')
        SiteApprovalService.reject(obj, request.user, reason)
        return Response(SiteApprovalSerializer(obj).data)

    @action(detail=False, methods=['get'], url_path='pending')
    def pending(self, request):
        """List all pending site approvals."""
        qs = SiteApprovalService.get_pending_approvals()
        return Response(SiteApprovalSerializer(qs, many=True).data)


class PerformanceReportViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet,
):
    """Publisher performance reports (eCPM, fills, completions, revenue)."""
    queryset         = _PR.objects.all()
    serializer_class = PerformanceReportSerializer
    permission_classes = [permissions.IsAdminUser]

    def get_queryset(self):
        qs = super().get_queryset()
        pub = self.request.query_params.get('publisher_id')
        if pub: qs = qs.filter(publisher_id=pub)
        return qs

    @action(detail=False, methods=['get'], url_path='summary')
    def summary(self, request):
        """Return aggregated stats for a publisher."""
        publisher_id = request.query_params.get('publisher_id', '')
        days_back    = int(request.query_params.get('days', 30))
        summary      = PerformanceReportService.get_report_summary(publisher_id, days_back)
        return Response(summary)

    @action(detail=False, methods=['post'], url_path='generate')
    def generate(self, request):
        """Manually trigger daily report generation."""
        publisher_id = request.data.get('publisher_id', '')
        report       = PerformanceReportService.generate_daily_report(publisher_id)
        return Response(PerformanceReportSerializer(report).data, status=201)


class PaymentScheduleViewSet(
    mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
    mixins.ListModelMixin, viewsets.GenericViewSet,
):
    """Publisher payment schedule (NET30, min payout, method)."""
    queryset         = _PS.objects.all()
    serializer_class = PaymentScheduleSerializer
    permission_classes = [permissions.IsAdminUser]

    @action(detail=False, methods=['get'], url_path='eligibility')
    def eligibility(self, request):
        """Check if publisher is eligible for payout."""
        publisher_id = request.query_params.get('publisher_id', '')
        balance      = float(request.query_params.get('balance', 0))
        result       = PaymentScheduleService.is_eligible_for_payout(publisher_id, balance)
        return Response(result)


class OfferwallPromotionViewSet(
    mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet,
):
    """Seasonal/event promotions with currency multipliers."""
    queryset         = _OP.objects.filter(is_active=True)
    serializer_class = OfferwallPromotionSerializer
    permission_classes = [permissions.IsAdminUser]

    @action(detail=False, methods=['get'], url_path='active')
    def active(self, request):
        """Return currently active promotions."""
        from django.utils import timezone
        now  = timezone.now()
        qs   = _OP.objects.filter(is_active=True, starts_at__lte=now, ends_at__gte=now)
        pub  = request.query_params.get('publisher_id')
        if pub: qs = qs.filter(publisher_id=pub)
        return Response(OfferwallPromotionSerializer(qs, many=True).data)
