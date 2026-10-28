# =============================================================================
# fraud_detection/services/FraudCaseService.py
# =============================================================================
"""
Fraud Case Service.

Comprehensive service for managing fraud cases including creation,
updates, resolution, and workflow automation.
"""

from __future__ import annotations

import json
import logging
from datetime import timedelta
from typing import Any, Dict, List, Optional, Tuple

from django.db import transaction
from django.utils import timezone
from django.core.cache import cache

from api.fraud_detection.models import (
    FraudCase, FraudCaseEvidence, FraudCaseAction, FraudNotification,
    FraudAlert, UserRiskProfile
)
from api.fraud_detection.choices import CaseStatus, EvidenceType, NotificationType
from api.fraud_detection.constants import RISK_THRESHOLDS, CACHE_KEYS

logger = logging.getLogger(__name__)


class FraudCaseService:
    """Service for managing fraud cases and related operations."""
    
    def __init__(self):
        self.cache_ttl = 3600  # 1 hour
    
    def create_case(self, user_id: int, title: str, description: str, 
                   risk_score: int, evidence_data: Optional[Dict] = None,
                   fraud_attempt_id: Optional[str] = None) -> Tuple[FraudCase, bool]:
        """
        Create a new fraud case with automatic case number generation.
        
        Args:
            user_id: User ID the case belongs to
            title: Case title
            description: Case description
            risk_score: Risk score (0-100)
            evidence_data: Initial evidence data
            fraud_attempt_id: Related fraud attempt ID
            
        Returns:
            Tuple of (FraudCase instance, created_flag)
        """
        try:
            with transaction.atomic():
                # Generate unique case number
                case_number = self._generate_case_number(user_id)
                
                # Determine priority based on risk score
                priority = self._determine_priority(risk_score)
                
                # Create the case
                case = FraudCase.objects.create(
                    case_number=case_number,
                    user_id=user_id,
                    title=title,
                    description=description,
                    risk_score=risk_score,
                    priority=priority,
                    status=CaseStatus.OPEN,
                    opened_at=timezone.now(),
                )
                
                # Add initial evidence if provided
                if evidence_data:
                    self.add_evidence(
                        case.id,
                        EvidenceType.LOG_DATA,
                        json.dumps(evidence_data),
                        "System"
                    )
                
                # Link to fraud attempt if provided
                if fraud_attempt_id:
                    from api.fraud_detection.models import FraudAttempt
                    try:
                        fraud_attempt = FraudAttempt.objects.get(attempt_id=fraud_attempt_id)
                        case.fraud_attempts.add(fraud_attempt)
                    except FraudAttempt.DoesNotExist:
                        logger.warning(f"Fraud attempt {fraud_attempt_id} not found for case {case_number}")
                
                # Auto-assign if high priority
                if priority in ['critical', 'high']:
                    self._auto_assign_case(case)
                
                # Create initial action
                self._create_initial_action(case)
                
                # Invalidate cache
                self._invalidate_case_cache(case.id)
                
                logger.info(f"Created fraud case {case_number} for user {user_id}")
                return case, True
                
        except Exception as e:
            logger.error(f"Error creating fraud case for user {user_id}: {e}")
            raise
    
    def update_case_status(self, case_id: int, new_status: str, 
                          resolved_by: Optional[int] = None,
                          resolution_notes: Optional[str] = None) -> bool:
        """
        Update fraud case status with proper workflow validation.
        
        Args:
            case_id: Case ID to update
            new_status: New status value
            resolved_by: User ID resolving the case (if applicable)
            resolution_notes: Resolution notes
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with transaction.atomic():
                case = FraudCase.objects.select_for_update().get(id=case_id)
                
                # Validate status transition
                if not self._is_valid_status_transition(case.status, new_status):
                    logger.warning(f"Invalid status transition for case {case.case_number}: {case.status} -> {new_status}")
                    return False
                
                old_status = case.status
                case.status = new_status
                
                # Set resolution details if resolving
                if new_status in [CaseStatus.RESOLVED, CaseStatus.CLOSED]:
                    case.resolved_at = timezone.now()
                    case.resolved_by_id = resolved_by
                    case.resolution_notes = resolution_notes
                
                case.save()
                
                # Create status change action
                FraudCaseAction.objects.create(
                    fraud_case=case,
                    action_type='status_change',
                    note=f"Status changed from {old_status} to {new_status}",
                    performed_by_id=resolved_by,
                    is_completed=True,
                )
                
                # Send notifications
                self._send_status_notification(case, old_status, new_status)
                
                # Invalidate cache
                self._invalidate_case_cache(case_id)
                
                logger.info(f"Updated case {case.case_number} status to {new_status}")
                return True
                
        except FraudCase.DoesNotExist:
            logger.error(f"Case {case_id} not found")
            return False
        except Exception as e:
            logger.error(f"Error updating case {case_id} status: {e}")
            return False
    
    def add_evidence(self, case_id: int, evidence_type: str, data: str, 
                    added_by: str, metadata: Optional[Dict] = None) -> FraudCaseEvidence:
        """
        Add evidence to a fraud case.
        
        Args:
            case_id: Case ID to add evidence to
            evidence_type: Type of evidence
            data: Evidence data (JSON string)
            added_by: Who added the evidence
            metadata: Additional metadata
            
        Returns:
            Created FraudCaseEvidence instance
        """
        try:
            with transaction.atomic():
                case = FraudCase.objects.select_for_update().get(id=case_id)
                
                evidence = FraudCaseEvidence.objects.create(
                    fraud_case=case,
                    evidence_type=evidence_type,
                    data=data,
                    added_by=added_by,
                    metadata=metadata or {},
                )
                
                # Update case priority based on new evidence
                self._update_case_priority_from_evidence(case)
                
                # Invalidate cache
                self._invalidate_case_cache(case_id)
                
                logger.info(f"Added evidence to case {case.case_number}: {evidence_type}")
                return evidence
                
        except FraudCase.DoesNotExist:
            logger.error(f"Case {case_id} not found")
            raise
        except Exception as e:
            logger.error(f"Error adding evidence to case {case_id}: {e}")
            raise
    
    def create_action(self, case_id: int, action_type: str, note: str,
                     performed_by: int, metadata: Optional[Dict] = None) -> FraudCaseAction:
        """
        Create an action for a fraud case.
        
        Args:
            case_id: Case ID to create action for
            action_type: Type of action
            note: Action note/description
            performed_by: User ID performing the action
            metadata: Additional metadata
            
        Returns:
            Created FraudCaseAction instance
        """
        try:
            with transaction.atomic():
                case = FraudCase.objects.select_for_update().get(id=case_id)
                
                action = FraudCaseAction.objects.create(
                    fraud_case=case,
                    action_type=action_type,
                    note=note,
                    performed_by_id=performed_by,
                    metadata=metadata or {},
                )
                
                # Update case status based on action
                self._update_case_from_action(case, action)
                
                # Send notifications for important actions
                if action_type in ['escalate', 'resolve', 'close']:
                    self._send_action_notification(case, action)
                
                # Invalidate cache
                self._invalidate_case_cache(case_id)
                
                logger.info(f"Created action {action_type} for case {case.case_number}")
                return action
                
        except FraudCase.DoesNotExist:
            logger.error(f"Case {case_id} not found")
            raise
        except Exception as e:
            logger.error(f"Error creating action for case {case_id}: {e}")
            raise
    
    def get_case_details(self, case_id: int, include_evidence: bool = True,
                        include_actions: bool = True) -> Optional[Dict]:
        """
        Get comprehensive case details with caching.
        
        Args:
            case_id: Case ID to retrieve
            include_evidence: Whether to include evidence
            include_actions: Whether to include actions
            
        Returns:
            Case details dictionary or None if not found
        """
        cache_key = f'fraud_case_details_{case_id}'
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return cached_data
        
        try:
            case = FraudCase.objects.select_related('user', 'assigned_to', 'resolved_by').get(id=case_id)
            
            details = {
                'id': case.id,
                'case_number': case.case_number,
                'user': {
                    'id': case.user.id,
                    'username': case.user.username,
                    'email': case.user.email,
                } if case.user else None,
                'title': case.title,
                'description': case.description,
                'risk_score': case.risk_score,
                'priority': case.priority,
                'status': case.status,
                'opened_at': case.opened_at.isoformat(),
                'resolved_at': case.resolved_at.isoformat() if case.resolved_at else None,
                'assigned_to': {
                    'id': case.assigned_to.id,
                    'username': case.assigned_to.username,
                } if case.assigned_to else None,
                'resolved_by': {
                    'id': case.resolved_by.id,
                    'username': case.resolved_by.username,
                } if case.resolved_by else None,
                'resolution_notes': case.resolution_notes,
            }
            
            if include_evidence:
                details['evidence'] = list(
                    case.evidence.all().values(
                        'id', 'evidence_type', 'data', 'added_by', 'created_at'
                    ).order_by('-created_at')
                )
            
            if include_actions:
                details['actions'] = list(
                    case.actions.all().values(
                        'id', 'action_type', 'note', 'performed_by_id', 'is_completed', 'created_at'
                    ).order_by('-created_at')
                )
            
            # Cache the result
            cache.set(cache_key, details, self.cache_ttl)
            
            return details
            
        except FraudCase.DoesNotExist:
            logger.warning(f"Case {case_id} not found")
            return None
        except Exception as e:
            logger.error(f"Error getting case details {case_id}: {e}")
            return None
    
    def get_user_cases(self, user_id: int, status: Optional[str] = None,
                      limit: int = 50, offset: int = 0) -> List[Dict]:
        """
        Get cases for a specific user with filtering and pagination.
        
        Args:
            user_id: User ID to get cases for
            status: Optional status filter
            limit: Maximum number of cases to return
            offset: Offset for pagination
            
        Returns:
            List of case dictionaries
        """
        try:
            queryset = FraudCase.objects.filter(user_id=user_id)
            
            if status:
                queryset = queryset.filter(status=status)
            
            cases = queryset.select_related('user', 'assigned_to').order_by('-opened_at')[offset:offset+limit]
            
            return [
                {
                    'id': case.id,
                    'case_number': case.case_number,
                    'title': case.title,
                    'risk_score': case.risk_score,
                    'priority': case.priority,
                    'status': case.status,
                    'opened_at': case.opened_at.isoformat(),
                    'assigned_to': case.assigned_to.username if case.assigned_to else None,
                }
                for case in cases
            ]
            
        except Exception as e:
            logger.error(f"Error getting user cases for user {user_id}: {e}")
            return []
    
    def bulk_update_cases(self, case_ids: List[int], updates: Dict[str, Any]) -> Dict[str, int]:
        """
        Bulk update multiple cases with the same updates.
        
        Args:
            case_ids: List of case IDs to update
            updates: Dictionary of fields to update
            
        Returns:
            Dictionary with update counts
        """
        try:
            with transaction.atomic():
                cases = FraudCase.objects.filter(id__in=case_ids).select_for_update()
                
                updated_count = 0
                error_count = 0
                
                for case in cases:
                    try:
                        # Apply updates
                        for field, value in updates.items():
                            if hasattr(case, field):
                                setattr(case, field, value)
                        
                        case.save()
                        
                        # Create action for bulk update
                        FraudCaseAction.objects.create(
                            fraud_case=case,
                            action_type='bulk_update',
                            note=f"Bulk update: {', '.join(updates.keys())}",
                            is_completed=True,
                        )
                        
                        updated_count += 1
                        
                        # Invalidate cache
                        self._invalidate_case_cache(case.id)
                        
                    except Exception as e:
                        logger.error(f"Error bulk updating case {case.id}: {e}")
                        error_count += 1
                
                logger.info(f"Bulk updated {updated_count} cases, {error_count} errors")
                return {'updated': updated_count, 'errors': error_count}
                
        except Exception as e:
            logger.error(f"Error in bulk case update: {e}")
            return {'updated': 0, 'errors': len(case_ids)}
    
    # =============================================================================
    # PRIVATE HELPER METHODS
    # =============================================================================
    
    def _generate_case_number(self, user_id: int) -> str:
        """Generate unique case number for user."""
        today = timezone.now().strftime('%Y%m%d')
        
        # Get existing case count for today
        today_count = FraudCase.objects.filter(
            opened_at__date=timezone.now().date()
        ).count()
        
        return f"FC-{today}-{today_count + 1:03d}"
    
    def _determine_priority(self, risk_score: int) -> str:
        """Determine case priority based on risk score."""
        if risk_score >= RISK_THRESHOLDS['critical']:
            return 'critical'
        elif risk_score >= RISK_THRESHOLDS['high']:
            return 'high'
        elif risk_score >= RISK_THRESHOLDS['medium']:
            return 'medium'
        else:
            return 'low'
    
    def _auto_assign_case(self, case: FraudCase):
        """Auto-assign case to available staff based on priority."""
        # Simple auto-assignment logic - in production, use more sophisticated rules
        from django.contrib.auth.models import User
        
        available_staff = User.objects.filter(
            is_staff=True,
            is_active=True
        ).order_by('?').first()
        
        if available_staff:
            case.assigned_to = available_staff
            case.save()
            
            # Create assignment action
            FraudCaseAction.objects.create(
                fraud_case=case,
                action_type='assign',
                note=f"Auto-assigned to {available_staff.username}",
                performed_by=available_staff,
                is_completed=True,
            )
    
    def _create_initial_action(self, case: FraudCase):
        """Create initial action for new case."""
        FraudCaseAction.objects.create(
            fraud_case=case,
            action_type='create',
            note="Case created",
            is_completed=True,
        )
    
    def _is_valid_status_transition(self, current_status: str, new_status: str) -> bool:
        """Validate if status transition is allowed."""
        valid_transitions = {
            CaseStatus.OPEN: [CaseStatus.INVESTIGATING, CaseStatus.REVIEWING, CaseStatus.CLOSED, CaseStatus.DISMISSED],
            CaseStatus.INVESTIGATING: [CaseStatus.REVIEWING, CaseStatus.RESOLVED, CaseStatus.CLOSED],
            CaseStatus.REVIEWING: [CaseStatus.RESOLVED, CaseStatus.CLOSED, CaseStatus.OPEN],
            CaseStatus.RESOLVED: [CaseStatus.CLOSED],
            CaseStatus.CLOSED: [],  # Terminal state
            CaseStatus.DISMISSED: [CaseStatus.OPEN],  # Can be reopened
        }
        
        return new_status in valid_transitions.get(current_status, [])
    
    def _update_case_priority_from_evidence(self, case: FraudCase):
        """Update case priority based on new evidence."""
        evidence_count = case.evidence.count()
        
        # Increase priority if there's significant evidence
        if evidence_count >= 5 and case.priority != 'critical':
            old_priority = case.priority
            case.priority = 'high'
            case.save()
            
            FraudCaseAction.objects.create(
                fraud_case=case,
                action_type='priority_change',
                note=f"Priority changed from {old_priority} to high (evidence count: {evidence_count})",
                is_completed=True,
            )
    
    def _update_case_from_action(self, case: FraudCase, action: FraudCaseAction):
        """Update case based on action type."""
        if action.action_type == 'resolve':
            case.status = CaseStatus.RESOLVED
            case.resolved_at = timezone.now()
            case.resolved_by = action.performed_by
            case.save()
        elif action.action_type == 'close':
            case.status = CaseStatus.CLOSED
            case.resolved_at = timezone.now()
            case.resolved_by = action.performed_by
            case.save()
        elif action.action_type == 'escalate':
            if case.priority != 'critical':
                old_priority = case.priority
                case.priority = 'critical'
                case.save()
                
                FraudCaseAction.objects.create(
                    fraud_case=case,
                    action_type='priority_change',
                    note=f"Priority escalated from {old_priority} to critical",
                    performed_by=action.performed_by,
                    is_completed=True,
                )
    
    def _send_status_notification(self, case: FraudCase, old_status: str, new_status: str):
        """Send notification for status change."""
        try:
            FraudNotification.objects.create(
                user=case.user,
                fraud_case=case,
                notification_type=NotificationType.DASHBOARD,
                message=f"Case {case.case_number} status changed from {old_status} to {new_status}",
                data={
                    'case_number': case.case_number,
                    'old_status': old_status,
                    'new_status': new_status,
                }
            )
        except Exception as e:
            logger.error(f"Error sending status notification for case {case.id}: {e}")
    
    def _send_action_notification(self, case: FraudCase, action: FraudCaseAction):
        """Send notification for important actions."""
        try:
            if action.action_type in ['escalate', 'resolve', 'close']:
                FraudNotification.objects.create(
                    user=case.user,
                    fraud_case=case,
                    notification_type=NotificationType.DASHBOARD,
                    message=f"Case {case.case_number}: {action.action_type} action performed",
                    data={
                        'case_number': case.case_number,
                        'action_type': action.action_type,
                        'performed_by': action.performed_by.username if action.performed_by else None,
                    }
                )
        except Exception as e:
            logger.error(f"Error sending action notification for case {case.id}: {e}")
    
    def _invalidate_case_cache(self, case_id: int):
        """Invalidate cache entries for a case."""
        cache_keys = [
            f'fraud_case_details_{case_id}',
            f'user_cases_{case_id}',
        ]
        
        for key in cache_keys:
            cache.delete(key)
