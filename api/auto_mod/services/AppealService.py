# =============================================================================
# auto_mod/services/AppealService.py
# =============================================================================

"""
Service for managing moderation appeals.
Handles appeal creation, assignment, review, and resolution.
"""

from __future__ import annotations
from django.db import models

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model

from ..choices import AppealStatus, DecisionType
from ..constants import APPEAL_TIMEOUT_DAYS, APPEAL_MAX_RETRIES
from ..exceptions import (
    AppealCreationError,
    AppealNotFoundError,
    AppealAlreadyExistsError,
    AppealReviewPermissionError,
    AppealResolutionError,
    AppealTimeoutError,
    DecisionNotFoundError,
)
from ..models import ModerationAppeal, ModerationDecision, SuspiciousSubmission
from ..signals import appeal_created, appeal_assigned, appeal_resolved, appeal_escalated

logger = logging.getLogger(__name__)
User = get_user_model()


class AppealService:
    """
    Service for managing moderation appeals.
    """
    
    def __init__(self):
        self.logger = logger

    # ---------------------------------------------------------------------------
    # Appeal Creation
    # ---------------------------------------------------------------------------

    @transaction.atomic
    def create_appeal(
        self,
        decision: ModerationDecision,
        appellant: User,
        reason: str,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> ModerationAppeal:
        """
        Create a new appeal against a moderation decision.
        
        Args:
            decision: The decision being appealed
            appellant: User filing the appeal
            reason: Appeal reason
            additional_data: Additional appeal data
            
        Returns:
            Created ModerationAppeal instance
            
        Raises:
            AppealCreationError: If appeal cannot be created
            AppealAlreadyExistsError: If appeal already exists
        """
        try:
            # Check if appeal already exists
            existing_appeal = ModerationAppeal.objects.filter(
                original_decision=decision,
                user=appellant,
                status__in=[AppealStatus.PENDING, AppealStatus.UNDER_REVIEW]
            ).first()
            
            if existing_appeal:
                raise AppealAlreadyExistsError(
                    f"Appeal already exists for decision {decision.pk}"
                )
            
            # Check appeal timeout
            if self._is_appeal_timeout(decision):
                raise AppealTimeoutError(
                    f"Appeal timeout exceeded for decision {decision.pk}"
                )
            
            # Create appeal
            appeal = ModerationAppeal.objects.create(
                submission=decision.submission,
                user=appellant,
                original_decision=decision,
                reason=reason,
                appeal_data=additional_data or {}
            )
            
            # Send signal
            appeal_created.send(
                sender=ModerationAppeal,
                appeal=appeal,
                original_decision=decision,
                appellant=appellant
            )
            
            self.logger.info(
                f"appeal_created decision={decision.pk} user={appellant.username} "
                f"appeal={appeal.pk} reason={reason[:100]}"
            )
            
            return appeal
            
        except (AppealAlreadyExistsError, AppealTimeoutError):
            raise
        except Exception as exc:
            self.logger.error(f"create_appeal.failed decision={decision.pk}: {exc}")
            raise AppealCreationError(f"Failed to create appeal: {exc}")

    # ---------------------------------------------------------------------------
    # Appeal Assignment and Review
    # ---------------------------------------------------------------------------

    @transaction.atomic
    def assign_reviewer(
        self,
        appeal: ModerationAppeal,
        reviewer: User,
        assigned_by: User,
        notes: Optional[str] = None
    ) -> ModerationAppeal:
        """
        Assign an appeal to a reviewer.
        
        Args:
            appeal: The appeal to assign
            reviewer: The reviewer to assign
            assigned_by: User making the assignment
            notes: Assignment notes
            
        Returns:
            Updated ModerationAppeal instance
            
        Raises:
            AppealNotFoundError: If appeal doesn't exist
            AppealReviewPermissionError: If no permission
        """
        try:
            # Refresh appeal
            appeal = ModerationAppeal.objects.get(pk=appeal.pk)
            
            # Check status
            if appeal.status != AppealStatus.PENDING:
                raise AppealReviewPermissionError(
                    f"Cannot assign appeal in {appeal.status} status"
                )
            
            # Check reviewer permissions
            if not self._can_review_appeals(reviewer):
                raise AppealReviewPermissionError(
                    f"User {reviewer.username} cannot review appeals"
                )
            
            # Update assignment
            appeal.status = AppealStatus.UNDER_REVIEW
            appeal.reviewed_by = reviewer
            appeal.reviewed_at = timezone.now()
            
            if notes:
                appeal.review_notes = f"Assigned: {notes}"
            
            appeal.save()
            
            # Send signal
            appeal_assigned.send(
                sender=ModerationAppeal,
                appeal=appeal,
                reviewer=reviewer,
                assigned_by=assigned_by
            )
            
            self.logger.info(
                f"appeal_assigned appeal={appeal.pk} reviewer={reviewer.username} "
                f"assigned_by={assigned_by.username}"
            )
            
            return appeal
            
        except ModerationAppeal.DoesNotExist:
            raise AppealNotFoundError(f"Appeal {appeal.pk} not found")
        except (AppealReviewPermissionError,):
            raise
        except Exception as exc:
            self.logger.error(f"assign_reviewer.failed appeal={appeal.pk}: {exc}")
            raise AppealReviewPermissionError(f"Failed to assign reviewer: {exc}")

    @transaction.atomic
    def resolve_appeal(
        self,
        appeal: ModerationAppeal,
        final_decision: str,
        final_reason: str,
        reviewer: User,
        override_original: bool = False
    ) -> ModerationAppeal:
        """
        Resolve an appeal with a final decision.
        
        Args:
            appeal: The appeal to resolve
            final_decision: Final decision (approve/reject/escalate)
            final_reason: Reason for the decision
            reviewer: The reviewer making the decision
            override_original: Whether to override the original decision
            
        Returns:
            Updated ModerationAppeal instance
            
        Raises:
            AppealNotFoundError: If appeal doesn't exist
            AppealResolutionError: If resolution fails
        """
        try:
            # Refresh appeal
            appeal = ModerationAppeal.objects.get(pk=appeal.pk)
            
            # Check status
            if appeal.status != AppealStatus.UNDER_REVIEW:
                raise AppealResolutionError(
                    f"Cannot resolve appeal in {appeal.status} status"
                )
            
            # Validate final decision
            if final_decision not in [choice[0] for choice in DecisionType.choices]:
                raise AppealResolutionError(f"Invalid final decision: {final_decision}")
            
            # Resolve appeal
            appeal.resolve(final_decision, final_reason, reviewer)
            appeal.save()
            
            # Override original decision if requested
            if override_original and final_decision in [DecisionType.APPROVE, DecisionType.REJECT]:
                self._override_original_decision(appeal, final_decision, final_reason, reviewer)
            
            # Send signal
            appeal_resolved.send(
                sender=ModerationAppeal,
                appeal=appeal,
                final_decision=final_decision,
                reviewer=reviewer
            )
            
            self.logger.info(
                f"appeal_resolved appeal={appeal.pk} decision={final_decision} "
                f"reviewer={reviewer.username} override={override_original}"
            )
            
            return appeal
            
        except ModerationAppeal.DoesNotExist:
            raise AppealNotFoundError(f"Appeal {appeal.pk} not found")
        except AppealResolutionError:
            raise
        except Exception as exc:
            self.logger.error(f"resolve_appeal.failed appeal={appeal.pk}: {exc}")
            raise AppealResolutionError(f"Failed to resolve appeal: {exc}")

    # ---------------------------------------------------------------------------
    # Appeal Escalation
    # ---------------------------------------------------------------------------

    @transaction.atomic
    def escalate_appeal(
        self,
        appeal: ModerationAppeal,
        escalated_to: User,
        reason: str,
        escalated_by: User
    ) -> ModerationAppeal:
        """
        Escalate an appeal to higher authority.
        
        Args:
            appeal: The appeal to escalate
            escalated_to: User to escalate to
            reason: Escalation reason
            escalated_by: User performing escalation
            
        Returns:
            Updated ModerationAppeal instance
        """
        try:
            # Refresh appeal
            appeal = ModerationAppeal.objects.get(pk=appeal.pk)
            
            # Update appeal status
            appeal.status = AppealStatus.PENDING  # Reset to pending for new reviewer
            appeal.reviewed_by = None
            appeal.reviewed_at = None
            appeal.review_notes = f"Escalated: {reason}"
            
            # Add escalation data
            appeal_data = appeal.appeal_data or {}
            appeal_data['escalations'] = appeal_data.get('escalations', [])
            appeal_data['escalations'].append({
                'escalated_by': escalated_by.username,
                'escalated_to': escalated_to.username,
                'reason': reason,
                'escalated_at': timezone.now().isoformat()
            })
            appeal.appeal_data = appeal_data
            
            appeal.save()
            
            # Send signal
            appeal_escalated.send(
                sender=ModerationAppeal,
                appeal=appeal,
                escalated_to=escalated_to,
                reason=reason
            )
            
            self.logger.info(
                f"appeal_escalated appeal={appeal.pk} to={escalated_to.username} "
                f"by={escalated_by.username} reason={reason}"
            )
            
            return appeal
            
        except ModerationAppeal.DoesNotExist:
            raise AppealNotFoundError(f"Appeal {appeal.pk} not found")
        except Exception as exc:
            self.logger.error(f"escalate_appeal.failed appeal={appeal.pk}: {exc}")
            raise AppealResolutionError(f"Failed to escalate appeal: {exc}")

    # ---------------------------------------------------------------------------
    # Appeal Management and Monitoring
    # ---------------------------------------------------------------------------

    def get_pending_appeals(
        self,
        reviewer: Optional[User] = None,
        submission_type: Optional[str] = None,
        limit: int = 100
    ) -> List[ModerationAppeal]:
        """
        Get pending appeals for review.
        
        Args:
            reviewer: Filter by assigned reviewer
            submission_type: Filter by submission type
            limit: Maximum number of appeals to return
            
        Returns:
            List of pending appeals
        """
        queryset = ModerationAppeal.objects.filter(
            status__in=[AppealStatus.PENDING, AppealStatus.UNDER_REVIEW]
        ).select_related('user', 'original_decision', 'submission')
        
        if reviewer:
            queryset = queryset.filter(reviewed_by=reviewer)
        
        if submission_type:
            queryset = queryset.filter(submission__submission_type=submission_type)
        
        return list(queryset.order_by('created_at')[:limit])

    def get_appeal_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive appeal statistics.
        
        Returns:
            Appeal statistics dictionary
        """
        from django.db.models import Count, Avg
        from django.utils import timezone
        from datetime import timedelta
        
        now = timezone.now()
        day_ago = now - timedelta(days=1)
        week_ago = now - timedelta(weeks=1)
        month_ago = now - timedelta(days=30)
        
        # Base stats
        total_appeals = ModerationAppeal.objects.count()
        pending_appeals = ModerationAppeal.objects.filter(
            status__in=[AppealStatus.PENDING, AppealStatus.UNDER_REVIEW]
        ).count()
        
        # Status breakdown
        status_stats = {}
        for status_choice in AppealStatus.choices:
            status = status_choice[0]
            count = ModerationAppeal.objects.filter(status=status).count()
            status_stats[status] = count
        
        # Success rate
        successful_appeals = ModerationAppeal.objects.filter(status=AppealStatus.APPROVED).count()
        success_rate = (successful_appeals / total_appeals * 100) if total_appeals > 0 else 0
        
        # Recent activity
        appeals_last_day = ModerationAppeal.objects.filter(created_at__gte=day_ago).count()
        appeals_last_week = ModerationAppeal.objects.filter(created_at__gte=week_ago).count()
        appeals_last_month = ModerationAppeal.objects.filter(created_at__gte=month_ago).count()
        
        # Resolution time
        resolved_appeals = ModerationAppeal.objects.filter(
            status__in=[AppealStatus.APPROVED, AppealStatus.REJECTED, AppealStatus.CLOSED]
        )
        avg_resolution_time = resolved_appeals.aggregate(
            avg_time=Avg('reviewed_at') - Avg('created_at')
        )['avg_time']
        
        # Top appellants
        top_appellants = (
            ModerationAppeal.objects.values('user__username')
            .annotate(count=Count('id'))
            .order_by('-count')[:10]
        )
        
        # Top reviewers
        top_reviewers = (
            ModerationAppeal.objects.values('reviewed_by__username')
            .annotate(count=Count('id'))
            .exclude(reviewed_by__username__isnull=True)
            .order_by('-count')[:10]
        )
        
        return {
            "total_appeals": total_appeals,
            "pending_appeals": pending_appeals,
            "success_rate": success_rate,
            "status_breakdown": status_stats,
            "recent_activity": {
                "last_day": appeals_last_day,
                "last_week": appeals_last_week,
                "last_month": appeals_last_month
            },
            "avg_resolution_time_hours": avg_resolution_time.total_seconds() / 3600 if avg_resolution_time else 0,
            "top_appellants": list(top_appellants),
            "top_reviewers": list(top_reviewers)
        }

    def get_reviewer_workload(
        self,
        reviewer: User,
        days_back: int = 7
    ) -> Dict[str, Any]:
        """
        Get workload statistics for a specific reviewer.
        
        Args:
            reviewer: The reviewer
            days_back: Number of days to look back
            
        Returns:
            Reviewer workload statistics
        """
        from django.db.models import Count, Q
        from django.utils import timezone
        from datetime import timedelta
        
        cutoff_date = timezone.now() - timedelta(days=days_back)
        
        # Appeals assigned to reviewer
        assigned_appeals = ModerationAppeal.objects.filter(
            reviewed_by=reviewer,
            reviewed_at__gte=cutoff_date
        )
        
        # Breakdown by status
        status_breakdown = (
            assigned_appeals.values('status')
            .annotate(count=Count('id'))
            .order_by('status')
        )
        
        # Resolution rate
        resolved_appeals = assigned_appeals.filter(
            status__in=[AppealStatus.APPROVED, AppealStatus.REJECTED, AppealStatus.CLOSED]
        ).count()
        resolution_rate = (resolved_appeals / assigned_appeals.count() * 100) if assigned_appeals.count() > 0 else 0
        
        # Average resolution time
        resolved_with_time = assigned_appeals.filter(
            status__in=[AppealStatus.APPROVED, AppealStatus.REJECTED, AppealStatus.CLOSED],
            reviewed_at__isnull=False
        )
        
        avg_resolution_times = []
        for appeal in resolved_with_time:
            if appeal.reviewed_at and appeal.created_at:
                resolution_time = appeal.reviewed_at - appeal.created_at
                avg_resolution_times.append(resolution_time.total_seconds() / 3600)
        
        avg_hours = sum(avg_resolution_times) / len(avg_resolution_times) if avg_resolution_times else 0
        
        return {
            "reviewer": reviewer.username,
            "period_days": days_back,
            "total_assigned": assigned_appeals.count(),
            "resolved_count": resolved_appeals,
            "resolution_rate": resolution_rate,
            "avg_resolution_hours": avg_hours,
            "status_breakdown": list(status_breakdown)
        }

    def auto_assign_appeals(
        self,
        batch_size: int = 20,
        submission_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Automatically assign pending appeals to available reviewers.
        
        Args:
            batch_size: Number of appeals to process
            submission_type: Filter by submission type
            
        Returns:
            Assignment statistics
        """
        try:
            # Get pending appeals
            pending_appeals = ModerationAppeal.objects.filter(
                status=AppealStatus.PENDING
            ).select_related('submission', 'original_decision')
            
            if submission_type:
                pending_appeals = pending_appeals.filter(
                    submission__submission_type=submission_type
                )
            
            pending_appeals = pending_appeals.order_by('created_at')[:batch_size]
            
            # Get available reviewers
            available_reviewers = self._get_available_reviewers(submission_type)
            
            if not available_reviewers:
                return {
                    "processed": 0,
                    "assigned": 0,
                    "failed": 0,
                    "available_reviewers": 0
                }
            
            assigned_count = 0
            failed_count = 0
            
            # Simple round-robin assignment
            for i, appeal in enumerate(pending_appeals):
                reviewer = available_reviewers[i % len(available_reviewers)]
                
                try:
                    self.assign_reviewer(
                        appeal=appeal,
                        reviewer=reviewer,
                        assigned_by=None,  # System assignment
                        notes="Auto-assigned by system"
                    )
                    assigned_count += 1
                except Exception as exc:
                    self.logger.warning(f"auto_assign_appeal.failed appeal={appeal.pk}: {exc}")
                    failed_count += 1
            
            return {
                "processed": len(pending_appeals),
                "assigned": assigned_count,
                "failed": failed_count,
                "available_reviewers": len(available_reviewers)
            }
            
        except Exception as exc:
            self.logger.error(f"auto_assign_appeals.failed: {exc}")
            raise

    # ---------------------------------------------------------------------------
    # Helper Methods
    # ---------------------------------------------------------------------------

    def _is_appeal_timeout(self, decision: ModerationDecision) -> bool:
        """Check if appeal timeout has been exceeded."""
        if not decision.decided_at:
            return False
        
        timeout_date = decision.decided_at + timedelta(days=APPEAL_TIMEOUT_DAYS)
        return timezone.now() > timeout_date

    def _can_review_appeals(self, user: User) -> bool:
        """Check if user can review appeals."""
        return (
            user.is_staff or
            user.groups.filter(name='appeal_reviewers').exists() or
            user.groups.filter(name='senior_moderators').exists()
        )

    def _get_available_reviewers(
        self,
        submission_type: Optional[str] = None,
        max_workload: int = 15
    ) -> List[User]:
        """Get list of available appeal reviewers."""
        from django.db.models import Count, Q
        
        # Base reviewer query
        reviewers = User.objects.filter(
            Q(is_staff=True) | Q(groups__name__in=['appeal_reviewers', 'senior_moderators']),
            is_active=True
        ).distinct()
        
        # Filter by submission type expertise if specified
        if submission_type:
            reviewers = reviewers.filter(
                Q(userprofile__expertise__contains=[submission_type]) |
                Q(userprofile__expertise__contains=['all'])
            )
        
        # Calculate current workload
        reviewers = reviewers.annotate(
            current_workload=Count(
                'moderationappeal',
                filter=Q(
                    moderationappeal__reviewed_by=models.OuterRef('pk'),
                    moderationappeal__status__in=[AppealStatus.PENDING, AppealStatus.UNDER_REVIEW]
                )
            )
        ).filter(current_workload__lt=max_workload)
        
        # Order by workload (least busy first)
        reviewers = reviewers.order_by('current_workload')
        
        return list(reviewers)

    def _override_original_decision(
        self,
        appeal: ModerationAppeal,
        new_decision: str,
        reason: str,
        reviewer: User
    ) -> None:
        """Override the original moderation decision."""
        try:
            original_decision = appeal.original_decision
            
            # Create new decision
            new_decision_obj = ModerationDecision.objects.create(
                submission=appeal.submission,
                decision_type=new_decision,
                reason=f"Overridden via appeal: {reason}",
                decided_by=reviewer,
                is_automated=False,
                previous_decision=original_decision
            )
            
            # Update submission status
            if new_decision == DecisionType.APPROVE:
                appeal.submission.status = "human_approved"
            elif new_decision == DecisionType.REJECT:
                appeal.submission.status = "human_rejected"
            elif new_decision == DecisionType.ESCALATE:
                appeal.submission.status = "escalated"
            
            appeal.submission.save(update_fields=["status"])
            
            self.logger.info(
                f"decision_overridden original={original_decision.pk} "
                f"new={new_decision_obj.pk} appeal={appeal.pk}"
            )
            
        except Exception as exc:
            self.logger.error(f"override_original_decision.failed appeal={appeal.pk}: {exc}")
            # Don't raise - this is a secondary operation

    def get_appeal_history_for_submission(
        self,
        submission: SuspiciousSubmission
    ) -> List[Dict[str, Any]]:
        """
        Get complete appeal history for a submission.
        
        Args:
            submission: The submission to get history for
            
        Returns:
            List of appeal history entries
        """
        appeals = ModerationAppeal.objects.filter(
            submission=submission
        ).select_related('user', 'original_decision', 'reviewed_by').order_by('created_at')
        
        history = []
        for appeal in appeals:
            entry = {
                "appeal_id": str(appeal.pk),
                "created_at": appeal.created_at.isoformat(),
                "user": appeal.user.username,
                "reason": appeal.reason,
                "status": appeal.status,
                "original_decision": appeal.original_decision.decision_type,
                "original_decider": (
                    appeal.original_decision.decided_by.username
                    if appeal.original_decision.decided_by else "System"
                ),
                "reviewed_by": (
                    appeal.reviewed_by.username if appeal.reviewed_by else None
                ),
                "reviewed_at": (
                    appeal.reviewed_at.isoformat() if appeal.reviewed_at else None
                ),
                "final_decision": appeal.final_decision,
                "final_reason": appeal.final_reason,
                "was_successful": appeal.was_successful
            }
            history.append(entry)
        
        return history
