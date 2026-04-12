"""
Advertiser Blacklist Management

This module handles blacklist management for advertisers including
blacklist entries, violations, appeals, and compliance monitoring.
"""

from typing import Optional, List, Dict, Any, Union
from decimal import Decimal
from datetime import datetime, date, timedelta
from uuid import UUID

from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings

from ..database_models.advertiser_model import Advertiser
from ..database_models.blacklist_model import BlacklistEntry, BlacklistViolation, BlacklistAppeal
from ..database_models.notification_model import Notification
from ..models import AdvertiserPortalBaseModel
from ..enums import *
from ..utils import *
from ..validators import *
from ..exceptions import *

User = get_user_model()


class AdvertiserBlacklistService:
    """Service for managing advertiser blacklist operations."""
    
    @staticmethod
    def add_to_blacklist(advertiser_id: UUID, blacklist_data: Dict[str, Any],
                          added_by: Optional[User] = None) -> BlacklistEntry:
        """Add advertiser to blacklist."""
        try:
            advertiser = AdvertiserBlacklistService.get_advertiser(advertiser_id)
            
            # Check if already blacklisted
            existing_entry = BlacklistEntry.objects.filter(
                advertiser=advertiser,
                status='active'
            ).first()
            
            if existing_entry:
                raise AdvertiserValidationError(f"Advertiser is already blacklisted: {existing_entry.id}")
            
            # Validate blacklist data
            reason = blacklist_data.get('reason')
            if not reason:
                raise AdvertiserValidationError("reason is required")
            
            blacklist_type = blacklist_data.get('blacklist_type', 'manual')
            if blacklist_type not in ['manual', 'automatic', 'fraud', 'compliance', 'policy_violation']:
                raise AdvertiserValidationError("Invalid blacklist_type")
            
            severity = blacklist_data.get('severity', 'medium')
            if severity not in ['low', 'medium', 'high', 'critical']:
                raise AdvertiserValidationError("Invalid severity")
            
            with transaction.atomic():
                # Create blacklist entry
                blacklist_entry = BlacklistEntry.objects.create(
                    advertiser=advertiser,
                    blacklist_type=blacklist_type,
                    reason=reason,
                    severity=severity,
                    description=blacklist_data.get('description', ''),
                    evidence=blacklist_data.get('evidence', {}),
                    violation_count=blacklist_data.get('violation_count', 1),
                    blacklist_date=timezone.now().date(),
                    expires_at=blacklist_data.get('expires_at'),
                    permanent=blacklist_data.get('permanent', False),
                    status='active',
                    added_by=added_by
                )
                
                # Update advertiser status
                advertiser.status = 'blacklisted'
                advertiser.blacklisted_at = timezone.now()
                advertiser.save(update_fields=['status', 'blacklisted_at'])
                
                # Deactivate all campaigns
                from ..database_models.campaign_model import Campaign
                Campaign.objects.filter(
                    advertiser=advertiser,
                    status='active'
                ).update(status='paused', modified_at=timezone.now())
                
                # Send notification
                Notification.objects.create(
                    advertiser=advertiser,
                    user=added_by,
                    title='Added to Blacklist',
                    message=f'Your account has been blacklisted due to: {reason}',
                    notification_type='compliance',
                    priority='high',
                    channels=['in_app', 'email']
                )
                
                # Log blacklisting
                from ..database_models.audit_model import AuditLog
                AuditLog.log_action(
                    action='add_to_blacklist',
                    object_type='BlacklistEntry',
                    object_id=str(blacklist_entry.id),
                    user=added_by,
                    advertiser=advertiser,
                    description=f"Added to blacklist: {reason}"
                )
                
                return blacklist_entry
                
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error adding to blacklist {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to add to blacklist: {str(e)}")
    
    @staticmethod
    def remove_from_blacklist(blacklist_id: UUID, removal_data: Dict[str, Any],
                               removed_by: Optional[User] = None) -> bool:
        """Remove advertiser from blacklist."""
        try:
            blacklist_entry = AdvertiserBlacklistService.get_blacklist_entry(blacklist_id)
            
            if blacklist_entry.status != 'active':
                raise AdvertiserValidationError(f"Blacklist entry is not active: {blacklist_entry.status}")
            
            with transaction.atomic():
                # Update blacklist entry
                blacklist_entry.status = 'removed'
                blacklist_entry.removed_at = timezone.now()
                blacklist_entry.removal_reason = removal_data.get('removal_reason', '')
                blacklist_entry.removed_by = removed_by
                blacklist_entry.save(update_fields=['status', 'removed_at', 'removal_reason', 'removed_by'])
                
                # Update advertiser status
                advertiser = blacklist_entry.advertiser
                advertiser.status = 'active'
                advertiser.blacklisted_at = None
                advertiser.save(update_fields=['status', 'blacklisted_at'])
                
                # Send notification
                Notification.objects.create(
                    advertiser=advertiser,
                    user=removed_by,
                    title='Removed from Blacklist',
                    message=f'Your account has been removed from the blacklist.',
                    notification_type='compliance',
                    priority='high',
                    channels=['in_app', 'email']
                )
                
                # Log removal
                from ..database_models.audit_model import AuditLog
                AuditLog.log_action(
                    action='remove_from_blacklist',
                    object_type='BlacklistEntry',
                    object_id=str(blacklist_entry.id),
                    user=removed_by,
                    advertiser=advertiser,
                    description=f"Removed from blacklist: {removal_data.get('removal_reason', '')}"
                )
                
                return True
                
        except BlacklistEntry.DoesNotExist:
            raise AdvertiserNotFoundError(f"Blacklist entry {blacklist_id} not found")
        except Exception as e:
            logger.error(f"Error removing from blacklist {blacklist_id}: {str(e)}")
            return False
    
    @staticmethod
    def record_violation(advertiser_id: UUID, violation_data: Dict[str, Any],
                         recorded_by: Optional[User] = None) -> BlacklistViolation:
        """Record blacklist violation."""
        try:
            advertiser = AdvertiserBlacklistService.get_advertiser(advertiser_id)
            
            # Validate violation data
            violation_type = violation_data.get('violation_type')
            if not violation_type:
                raise AdvertiserValidationError("violation_type is required")
            
            violation_severity = violation_data.get('severity', 'medium')
            if violation_severity not in ['low', 'medium', 'high', 'critical']:
                raise AdvertiserValidationError("Invalid severity")
            
            with transaction.atomic():
                # Create violation record
                violation = BlacklistViolation.objects.create(
                    advertiser=advertiser,
                    violation_type=violation_type,
                    violation_severity=violation_severity,
                    description=violation_data.get('description', ''),
                    evidence=violation_data.get('evidence', {}),
                    violation_date=violation_data.get('violation_date', timezone.now().date()),
                    detected_at=timezone.now(),
                    detected_by=recorded_by,
                    status='active'
                )
                
                # Check if this violation should trigger blacklisting
                if AdvertiserBlacklistService._should_blacklist_for_violation(advertiser, violation):
                    # Add to blacklist automatically
                    AdvertiserBlacklistService.add_to_blacklist(
                        advertiser_id,
                        {
                            'blacklist_type': 'automatic',
                            'reason': f'Automatic blacklisting due to {violation_type}',
                            'description': violation.description,
                            'severity': violation_severity,
                            'evidence': violation.evidence,
                            'violation_count': 1
                        },
                        recorded_by
                    )
                
                # Send notification for critical violations
                if violation_severity in ['high', 'critical']:
                    Notification.objects.create(
                        advertiser=advertiser,
                        user=recorded_by,
                        title='Policy Violation Recorded',
                        message=f'A {violation_severity} violation has been recorded: {violation_type}',
                        notification_type='compliance',
                        priority='high',
                        channels=['in_app']
                    )
                
                # Log violation
                from ..database_models.audit_model import AuditLog
                AuditLog.log_action(
                    action='record_violation',
                    object_type='BlacklistViolation',
                    object_id=str(violation.id),
                    user=recorded_by,
                    advertiser=advertiser,
                    description=f"Recorded violation: {violation_type}"
                )
                
                return violation
                
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error recording violation {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to record violation: {str(e)}")
    
    @staticmethod
    def submit_appeal(blacklist_id: UUID, appeal_data: Dict[str, Any],
                       submitted_by: Optional[User] = None) -> BlacklistAppeal:
        """Submit appeal for blacklist entry."""
        try:
            blacklist_entry = AdvertiserBlacklistService.get_blacklist_entry(blacklist_id)
            
            # Check if appeal already exists
            existing_appeal = BlacklistAppeal.objects.filter(
                blacklist_entry=blacklist_entry,
                status__in=['pending', 'under_review']
            ).first()
            
            if existing_appeal:
                raise AdvertiserValidationError(f"Appeal already exists: {existing_appeal.id}")
            
            # Validate appeal data
            appeal_reason = appeal_data.get('appeal_reason')
            if not appeal_reason:
                raise AdvertiserValidationError("appeal_reason is required")
            
            with transaction.atomic():
                # Create appeal
                appeal = BlacklistAppeal.objects.create(
                    blacklist_entry=blacklist_entry,
                    appeal_reason=appeal_reason,
                    appeal_description=appeal_data.get('appeal_description', ''),
                    evidence=appeal_data.get('evidence', {}),
                    supporting_documents=appeal_data.get('supporting_documents', []),
                    contact_email=appeal_data.get('contact_email', blacklist_entry.advertiser.contact_email),
                    contact_phone=appeal_data.get('contact_phone', blacklist_entry.advertiser.contact_phone),
                    status='pending',
                    submitted_at=timezone.now(),
                    submitted_by=submitted_by
                )
                
                # Send notification
                Notification.objects.create(
                    advertiser=blacklist_entry.advertiser,
                    user=submitted_by,
                    title='Appeal Submitted',
                    message=f'Your appeal for blacklist removal has been submitted for review.',
                    notification_type='compliance',
                    priority='medium',
                    channels=['in_app']
                )
                
                # Log appeal submission
                from ..database_models.audit_model import AuditLog
                AuditLog.log_action(
                    action='submit_appeal',
                    object_type='BlacklistAppeal',
                    object_id=str(appeal.id),
                    user=submitted_by,
                    advertiser=blacklist_entry.advertiser,
                    description=f"Submitted appeal: {appeal_reason}"
                )
                
                return appeal
                
        except BlacklistEntry.DoesNotExist:
            raise AdvertiserNotFoundError(f"Blacklist entry {blacklist_id} not found")
        except Exception as e:
            logger.error(f"Error submitting appeal {blacklist_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to submit appeal: {str(e)}")
    
    @staticmethod
    def review_appeal(appeal_id: UUID, review_data: Dict[str, Any],
                      reviewed_by: Optional[User] = None) -> bool:
        """Review and process appeal."""
        try:
            appeal = AdvertiserBlacklistService.get_appeal(appeal_id)
            
            if appeal.status not in ['pending', 'under_review']:
                raise AdvertiserValidationError(f"Appeal cannot be reviewed in status: {appeal.status}")
            
            decision = review_data.get('decision')
            if decision not in ['approve', 'reject']:
                raise AdvertiserValidationError("decision must be 'approve' or 'reject'")
            
            with transaction.atomic():
                # Update appeal
                appeal.status = 'approved' if decision == 'approve' else 'rejected'
                appeal.reviewed_at = timezone.now()
                appeal.reviewed_by = reviewed_by
                appeal.review_notes = review_data.get('review_notes', '')
                appeal.save(update_fields=['status', 'reviewed_at', 'reviewed_by', 'review_notes'])
                
                blacklist_entry = appeal.blacklist_entry
                
                if decision == 'approve':
                    # Remove from blacklist
                    AdvertiserBlacklistService.remove_from_blacklist(
                        blacklist_entry.id,
                        {'removal_reason': f'Appeal approved: {appeal.appeal_reason}'},
                        reviewed_by
                    )
                    
                    # Send approval notification
                    Notification.objects.create(
                        advertiser=blacklist_entry.advertiser,
                        user=blacklist_entry.advertiser.user,
                        title='Appeal Approved',
                        message='Your appeal has been approved and you have been removed from the blacklist.',
                        notification_type='compliance',
                        priority='high',
                        channels=['in_app', 'email']
                    )
                else:
                    # Send rejection notification
                    Notification.objects.create(
                        advertiser=blacklist_entry.advertiser,
                        user=blacklist_entry.advertiser.user,
                        title='Appeal Rejected',
                        message=f'Your appeal has been rejected. Reason: {review_data.get("review_notes", "")}',
                        notification_type='compliance',
                        priority='high',
                        channels=['in_app', 'email']
                    )
                
                # Log review
                from ..database_models.audit_model import AuditLog
                AuditLog.log_action(
                    action='review_appeal',
                    object_type='BlacklistAppeal',
                    object_id=str(appeal.id),
                    user=reviewed_by,
                    advertiser=blacklist_entry.advertiser,
                    description=f"Reviewed appeal: {decision}"
                )
                
                return True
                
        except BlacklistAppeal.DoesNotExist:
            raise AdvertiserNotFoundError(f"Appeal {appeal_id} not found")
        except Exception as e:
            logger.error(f"Error reviewing appeal {appeal_id}: {str(e)}")
            return False
    
    @staticmethod
    def get_blacklist_status(advertiser_id: UUID) -> Dict[str, Any]:
        """Get blacklist status for advertiser."""
        try:
            advertiser = AdvertiserBlacklistService.get_advertiser(advertiser_id)
            
            # Get active blacklist entry
            blacklist_entry = BlacklistEntry.objects.filter(
                advertiser=advertiser,
                status='active'
            ).first()
            
            if not blacklist_entry:
                return {
                    'advertiser_id': str(advertiser_id),
                    'is_blacklisted': False,
                    'status': 'clean',
                    'message': 'Advertiser is not blacklisted'
                }
            
            # Get violation history
            violations = BlacklistViolation.objects.filter(
                advertiser=advertiser
            ).order_by('-violation_date')[:10]
            
            # Get appeal history
            appeals = BlacklistAppeal.objects.filter(
                blacklist_entry=blacklist_entry
            ).order_by('-submitted_at')
            
            return {
                'advertiser_id': str(advertiser_id),
                'is_blacklisted': True,
                'status': 'blacklisted',
                'blacklist_entry': {
                    'id': str(blacklist_entry.id),
                    'blacklist_type': blacklist_entry.blacklist_type,
                    'reason': blacklist_entry.reason,
                    'severity': blacklist_entry.severity,
                    'description': blacklist_entry.description,
                    'blacklist_date': blacklist_entry.blacklist_date.isoformat(),
                    'expires_at': blacklist_entry.expires_at.isoformat() if blacklist_entry.expires_at else None,
                    'permanent': blacklist_entry.permanent,
                    'violation_count': blacklist_entry.violation_count
                },
                'violations': [
                    {
                        'id': str(violation.id),
                        'violation_type': violation.violation_type,
                        'severity': violation.violation_severity,
                        'description': violation.description,
                        'violation_date': violation.violation_date.isoformat(),
                        'detected_at': violation.detected_at.isoformat()
                    }
                    for violation in violations
                ],
                'appeals': [
                    {
                        'id': str(appeal.id),
                        'appeal_reason': appeal.appeal_reason,
                        'status': appeal.status,
                        'submitted_at': appeal.submitted_at.isoformat(),
                        'reviewed_at': appeal.reviewed_at.isoformat() if appeal.reviewed_at else None
                    }
                    for appeal in appeals
                ]
            }
            
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error getting blacklist status {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to get blacklist status: {str(e)}")
    
    @staticmethod
    def get_blacklist_statistics() -> Dict[str, Any]:
        """Get blacklist statistics."""
        try:
            # Get total blacklist entries
            total_entries = BlacklistEntry.objects.count()
            active_entries = BlacklistEntry.objects.filter(status='active').count()
            
            # Get entries by type
            entries_by_type = BlacklistEntry.objects.values('blacklist_type').annotate(
                count=Count('id')
            )
            
            # Get entries by severity
            entries_by_severity = BlacklistEntry.objects.values('severity').annotate(
                count=Count('id')
            )
            
            # Get violation statistics
            total_violations = BlacklistViolation.objects.count()
            violations_by_type = BlacklistViolation.objects.values('violation_type').annotate(
                count=Count('id')
            )
            
            # Get appeal statistics
            total_appeals = BlacklistAppeal.objects.count()
            appeals_by_status = BlacklistAppeal.objects.values('status').annotate(
                count=Count('id')
            )
            
            return {
                'blacklist_entries': {
                    'total': total_entries,
                    'active': active_entries,
                    'by_type': list(entries_by_type),
                    'by_severity': list(entries_by_severity)
                },
                'violations': {
                    'total': total_violations,
                    'by_type': list(violations_by_type)
                },
                'appeals': {
                    'total': total_appeals,
                    'by_status': list(appeals_by_status)
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting blacklist statistics: {str(e)}")
            return {
                'blacklist_entries': {'total': 0, 'active': 0, 'by_type': [], 'by_severity': []},
                'violations': {'total': 0, 'by_type': []},
                'appeals': {'total': 0, 'by_status': []}
            }
    
    @staticmethod
    def get_violation_history(advertiser_id: UUID, filters: Optional[Dict[str, Any]] = None,
                              page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """Get violation history for advertiser."""
        try:
            advertiser = AdvertiserBlacklistService.get_advertiser(advertiser_id)
            
            queryset = BlacklistViolation.objects.filter(advertiser=advertiser)
            
            # Apply filters
            if filters:
                if 'violation_type' in filters:
                    queryset = queryset.filter(violation_type=filters['violation_type'])
                if 'severity' in filters:
                    queryset = queryset.filter(violation_severity=filters['severity'])
                if 'date_from' in filters:
                    queryset = queryset.filter(violation_date__gte=filters['date_from'])
                if 'date_to' in filters:
                    queryset = queryset.filter(violation_date__lte=filters['date_to'])
                if 'status' in filters:
                    queryset = queryset.filter(status=filters['status'])
            
            # Count total
            total_count = queryset.count()
            
            # Apply pagination
            offset = (page - 1) * page_size
            violations = queryset[offset:offset + page_size].order_by('-violation_date')
            
            return {
                'advertiser_id': str(advertiser_id),
                'violations': [
                    {
                        'id': str(violation.id),
                        'violation_type': violation.violation_type,
                        'violation_severity': violation.violation_severity,
                        'description': violation.description,
                        'evidence': violation.evidence,
                        'violation_date': violation.violation_date.isoformat(),
                        'detected_at': violation.detected_at.isoformat(),
                        'detected_by': violation.detected_by.username if violation.detected_by else None,
                        'status': violation.status
                    }
                    for violation in violations
                ],
                'pagination': {
                    'total_count': total_count,
                    'page': page,
                    'page_size': page_size,
                    'total_pages': (total_count + page_size - 1) // page_size,
                    'has_next': offset + page_size < total_count,
                    'has_previous': page > 1
                }
            }
            
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error getting violation history {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to get violation history: {str(e)}")
    
    @staticmethod
    def get_appeal_history(blacklist_id: UUID) -> List[Dict[str, Any]]:
        """Get appeal history for blacklist entry."""
        try:
            blacklist_entry = AdvertiserBlacklistService.get_blacklist_entry(blacklist_id)
            
            appeals = BlacklistAppeal.objects.filter(
                blacklist_entry=blacklist_entry
            ).order_by('-submitted_at')
            
            return [
                {
                    'id': str(appeal.id),
                    'appeal_reason': appeal.appeal_reason,
                    'appeal_description': appeal.appeal_description,
                    'status': appeal.status,
                    'submitted_at': appeal.submitted_at.isoformat(),
                    'reviewed_at': appeal.reviewed_at.isoformat() if appeal.reviewed_at else None,
                    'reviewed_by': appeal.reviewed_by.username if appeal.reviewed_by else None,
                    'review_notes': appeal.review_notes
                }
                for appeal in appeals
            ]
            
        except BlacklistEntry.DoesNotExist:
            raise AdvertiserNotFoundError(f"Blacklist entry {blacklist_id} not found")
        except Exception as e:
            logger.error(f"Error getting appeal history {blacklist_id}: {str(e)}")
            return []
    
    @staticmethod
    def _should_blacklist_for_violation(advertiser: Advertiser, violation: BlacklistViolation) -> bool:
        """Determine if violation should trigger blacklisting."""
        try:
            # Get violation count for advertiser
            violation_count = BlacklistViolation.objects.filter(
                advertiser=advertiser,
                status='active'
            ).count()
            
            # Auto-blacklist for critical violations
            if violation.violation_severity == 'critical':
                return True
            
            # Auto-blacklist for multiple high severity violations
            if violation.violation_severity == 'high' and violation_count >= 2:
                return True
            
            # Auto-blacklist for many medium severity violations
            if violation.violation_severity == 'medium' and violation_count >= 5:
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error determining blacklist trigger: {str(e)}")
            return False
    
    @staticmethod
    def check_compliance_alerts(advertiser_id: UUID) -> List[Dict[str, Any]]:
        """Check for compliance alerts."""
        try:
            advertiser = AdvertiserBlacklistService.get_advertiser(advertiser_id)
            
            alerts = []
            
            # Check for recent violations
            recent_violations = BlacklistViolation.objects.filter(
                advertiser=advertiser,
                violation_date__gte=timezone.now().date() - timedelta(days=30)
            ).count()
            
            if recent_violations >= 3:
                alerts.append({
                    'type': 'multiple_violations',
                    'severity': 'high',
                    'message': f'Multiple violations detected in the last 30 days: {recent_violations}',
                    'count': recent_violations
                })
            
            # Check for high severity violations
            high_severity_violations = BlacklistViolation.objects.filter(
                advertiser=advertiser,
                violation_severity='high',
                violation_date__gte=timezone.now().date() - timedelta(days=90)
            ).count()
            
            if high_severity_violations > 0:
                alerts.append({
                    'type': 'high_severity_violations',
                    'severity': 'critical',
                    'message': f'High severity violations detected: {high_severity_violations}',
                    'count': high_severity_violations
                })
            
            # Check if close to blacklisting threshold
            total_violations = BlacklistViolation.objects.filter(
                advertiser=advertiser,
                status='active'
            ).count()
            
            if total_violations >= 3:
                alerts.append({
                    'type': 'blacklist_threshold',
                    'severity': 'high',
                    'message': f'Approaching blacklist threshold: {total_violations} violations',
                    'count': total_violations
                })
            
            return alerts
            
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error checking compliance alerts {advertiser_id}: {str(e)}")
            return []
    
    @staticmethod
    def get_advertiser(advertiser_id: UUID) -> Advertiser:
        """Get advertiser by ID."""
        try:
            return Advertiser.objects.get(id=advertiser_id, is_deleted=False)
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
    
    @staticmethod
    def get_blacklist_entry(blacklist_id: UUID) -> BlacklistEntry:
        """Get blacklist entry by ID."""
        try:
            return BlacklistEntry.objects.get(id=blacklist_id)
        except BlacklistEntry.DoesNotExist:
            raise AdvertiserNotFoundError(f"Blacklist entry {blacklist_id} not found")
    
    @staticmethod
    def get_appeal(appeal_id: UUID) -> BlacklistAppeal:
        """Get appeal by ID."""
        try:
            return BlacklistAppeal.objects.get(id=appeal_id)
        except BlacklistAppeal.DoesNotExist:
            raise AdvertiserNotFoundError(f"Appeal {appeal_id} not found")
    
    @staticmethod
    def get_blacklist_entries(filters: Optional[Dict[str, Any]] = None,
                               page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """Get blacklist entries with filtering and pagination."""
        try:
            queryset = BlacklistEntry.objects.all()
            
            # Apply filters
            if filters:
                if 'status' in filters:
                    queryset = queryset.filter(status=filters['status'])
                if 'blacklist_type' in filters:
                    queryset = queryset.filter(blacklist_type=filters['blacklist_type'])
                if 'severity' in filters:
                    queryset = queryset.filter(severity=filters['severity'])
                if 'date_from' in filters:
                    queryset = queryset.filter(blacklist_date__gte=filters['date_from'])
                if 'date_to' in filters:
                    queryset = queryset.filter(blacklist_date__lte=filters['date_to'])
                if 'search' in filters:
                    search = filters['search']
                    queryset = queryset.filter(
                        Q(advertiser__company_name__icontains=search) |
                        Q(reason__icontains=search) |
                        Q(description__icontains=search)
                    )
            
            # Count total
            total_count = queryset.count()
            
            # Apply pagination
            offset = (page - 1) * page_size
            entries = queryset[offset:offset + page_size].order_by('-blacklist_date')
            
            return {
                'entries': [
                    {
                        'id': str(entry.id),
                        'advertiser': {
                            'id': str(entry.advertiser.id),
                            'company_name': entry.advertiser.company_name,
                            'contact_email': entry.advertiser.contact_email
                        },
                        'blacklist_type': entry.blacklist_type,
                        'reason': entry.reason,
                        'severity': entry.severity,
                        'description': entry.description,
                        'blacklist_date': entry.blacklist_date.isoformat(),
                        'expires_at': entry.expires_at.isoformat() if entry.expires_at else None,
                        'permanent': entry.permanent,
                        'status': entry.status,
                        'violation_count': entry.violation_count,
                        'added_at': entry.created_at.isoformat()
                    }
                    for entry in entries
                ],
                'pagination': {
                    'total_count': total_count,
                    'page': page,
                    'page_size': page_size,
                    'total_pages': (total_count + page_size - 1) // page_size,
                    'has_next': offset + page_size < total_count,
                    'has_previous': page > 1
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting blacklist entries: {str(e)}")
            return {'entries': [], 'pagination': {}}
    
    @staticmethod
    def get_pending_appeals(page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """Get pending appeals for review."""
        try:
            queryset = BlacklistAppeal.objects.filter(
                status__in=['pending', 'under_review']
            ).order_by('-submitted_at')
            
            # Count total
            total_count = queryset.count()
            
            # Apply pagination
            offset = (page - 1) * page_size
            appeals = queryset[offset:offset + page_size]
            
            return {
                'appeals': [
                    {
                        'id': str(appeal.id),
                        'blacklist_entry': {
                            'id': str(appeal.blacklist_entry.id),
                            'advertiser': appeal.blacklist_entry.advertiser.company_name,
                            'reason': appeal.blacklist_entry.reason,
                            'severity': appeal.blacklist_entry.severity
                        },
                        'appeal_reason': appeal.appeal_reason,
                        'appeal_description': appeal.appeal_description,
                        'status': appeal.status,
                        'submitted_at': appeal.submitted_at.isoformat(),
                        'supporting_documents': appeal.supporting_documents
                    }
                    for appeal in appeals
                ],
                'pagination': {
                    'total_count': total_count,
                    'page': page,
                    'page_size': page_size,
                    'total_pages': (total_count + page_size - 1) // page_size,
                    'has_next': offset + page_size < total_count,
                    'has_previous': page > 1
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting pending appeals: {str(e)}")
            return {'appeals': [], 'pagination': {}}
