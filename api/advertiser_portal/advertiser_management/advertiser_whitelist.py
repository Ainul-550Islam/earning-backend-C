"""
Advertiser Whitelist Management

This module handles whitelist management for advertisers including
whitelist entries, verification, trusted status, and compliance monitoring.
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
from ..database_models.whitelist_model import WhitelistEntry, TrustLevel, VerificationRequest
from ..database_models.notification_model import Notification
from ..models import AdvertiserPortalBaseModel
from ..enums import *
from ..utils import *
from ..validators import *
from ..exceptions import *

User = get_user_model()


class AdvertiserWhitelistService:
    """Service for managing advertiser whitelist operations."""
    
    @staticmethod
    def add_to_whitelist(advertiser_id: UUID, whitelist_data: Dict[str, Any],
                         added_by: Optional[User] = None) -> WhitelistEntry:
        """Add advertiser to whitelist."""
        try:
            advertiser = AdvertiserWhitelistService.get_advertiser(advertiser_id)
            
            # Check if already whitelisted
            existing_entry = WhitelistEntry.objects.filter(
                advertiser=advertiser,
                status='active'
            ).first()
            
            if existing_entry:
                raise AdvertiserValidationError(f"Advertiser is already whitelisted: {existing_entry.id}")
            
            # Validate whitelist data
            reason = whitelist_data.get('reason')
            if not reason:
                raise AdvertiserValidationError("reason is required")
            
            trust_level = whitelist_data.get('trust_level', 'standard')
            if trust_level not in ['basic', 'standard', 'premium', 'enterprise']:
                raise AdvertiserValidationError("Invalid trust_level")
            
            with transaction.atomic():
                # Create whitelist entry
                whitelist_entry = WhitelistEntry.objects.create(
                    advertiser=advertiser,
                    trust_level=trust_level,
                    reason=reason,
                    description=whitelist_data.get('description', ''),
                    verification_status='verified',
                    verification_date=timezone.now().date(),
                    verified_by=added_by,
                    benefits=whitelist_data.get('benefits', {}),
                    restrictions=whitelist_data.get('restrictions', {}),
                    expires_at=whitelist_data.get('expires_at'),
                    permanent=whitelist_data.get('permanent', True),
                    status='active',
                    added_by=added_by
                )
                
                # Update advertiser status
                advertiser.is_verified = True
                advertiser.verification_date = timezone.now()
                advertiser.verified_by = added_by
                advertiser.trust_level = trust_level
                advertiser.save(update_fields=['is_verified', 'verification_date', 'verified_by', 'trust_level'])
                
                # Send notification
                Notification.objects.create(
                    advertiser=advertiser,
                    user=added_by,
                    title='Added to Whitelist',
                    message=f'Your account has been added to the whitelist with {trust_level} trust level.',
                    notification_type='verification',
                    priority='medium',
                    channels=['in_app', 'email']
                )
                
                # Log addition
                from ..database_models.audit_model import AuditLog
                AuditLog.log_action(
                    action='add_to_whitelist',
                    object_type='WhitelistEntry',
                    object_id=str(whitelist_entry.id),
                    user=added_by,
                    advertiser=advertiser,
                    description=f"Added to whitelist: {reason}"
                )
                
                return whitelist_entry
                
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error adding to whitelist {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to add to whitelist: {str(e)}")
    
    @staticmethod
    def remove_from_whitelist(whitelist_id: UUID, removal_data: Dict[str, Any],
                                removed_by: Optional[User] = None) -> bool:
        """Remove advertiser from whitelist."""
        try:
            whitelist_entry = AdvertiserWhitelistService.get_whitelist_entry(whitelist_id)
            
            if whitelist_entry.status != 'active':
                raise AdvertiserValidationError(f"Whitelist entry is not active: {whitelist_entry.status}")
            
            with transaction.atomic():
                # Update whitelist entry
                whitelist_entry.status = 'removed'
                whitelist_entry.removed_at = timezone.now()
                whitelist_entry.removal_reason = removal_data.get('removal_reason', '')
                whitelist_entry.removed_by = removed_by
                whitelist_entry.save(update_fields=['status', 'removed_at', 'removal_reason', 'removed_by'])
                
                # Update advertiser status
                advertiser = whitelist_entry.advertiser
                advertiser.is_verified = False
                advertiser.verification_date = None
                advertiser.verified_by = None
                advertiser.trust_level = 'basic'
                advertiser.save(update_fields=['is_verified', 'verification_date', 'verified_by', 'trust_level'])
                
                # Send notification
                Notification.objects.create(
                    advertiser=advertiser,
                    user=removed_by,
                    title='Removed from Whitelist',
                    message=f'Your account has been removed from the whitelist.',
                    notification_type='verification',
                    priority='high',
                    channels=['in_app', 'email']
                )
                
                # Log removal
                from ..database_models.audit_model import AuditLog
                AuditLog.log_action(
                    action='remove_from_whitelist',
                    object_type='WhitelistEntry',
                    object_id=str(whitelist_entry.id),
                    user=removed_by,
                    advertiser=advertiser,
                    description=f"Removed from whitelist: {removal_data.get('removal_reason', '')}"
                )
                
                return True
                
        except WhitelistEntry.DoesNotExist:
            raise AdvertiserNotFoundError(f"Whitelist entry {whitelist_id} not found")
        except Exception as e:
            logger.error(f"Error removing from whitelist {whitelist_id}: {str(e)}")
            return False
    
    @staticmethod
    def request_verification(advertiser_id: UUID, verification_data: Dict[str, Any],
                            requested_by: Optional[User] = None) -> VerificationRequest:
        """Request whitelist verification."""
        try:
            advertiser = AdvertiserWhitelistService.get_advertiser(advertiser_id)
            
            # Check if verification request already exists
            existing_request = VerificationRequest.objects.filter(
                advertiser=advertiser,
                status__in=['pending', 'under_review']
            ).first()
            
            if existing_request:
                raise AdvertiserValidationError(f"Verification request already exists: {existing_request.id}")
            
            # Validate verification data
            verification_type = verification_data.get('verification_type', 'business')
            if verification_type not in ['business', 'identity', 'financial', 'compliance']:
                raise AdvertiserValidationError("Invalid verification_type")
            
            with transaction.atomic():
                # Create verification request
                verification_request = VerificationRequest.objects.create(
                    advertiser=advertiser,
                    verification_type=verification_type,
                    request_reason=verification_data.get('request_reason', ''),
                    documents=verification_data.get('documents', []),
                    contact_email=verification_data.get('contact_email', advertiser.contact_email),
                    contact_phone=verification_data.get('contact_phone', advertiser.contact_phone),
                    business_details=verification_data.get('business_details', {}),
                    status='pending',
                    requested_at=timezone.now(),
                    requested_by=requested_by
                )
                
                # Send notification
                Notification.objects.create(
                    advertiser=advertiser,
                    user=requested_by,
                    title='Verification Request Submitted',
                    message=f'Your {verification_type} verification request has been submitted for review.',
                    notification_type='verification',
                    priority='medium',
                    channels=['in_app']
                )
                
                # Log request
                from ..database_models.audit_model import AuditLog
                AuditLog.log_action(
                    action='request_verification',
                    object_type='VerificationRequest',
                    object_id=str(verification_request.id),
                    user=requested_by,
                    advertiser=advertiser,
                    description=f"Requested {verification_type} verification"
                )
                
                return verification_request
                
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error requesting verification {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to request verification: {str(e)}")
    
    @staticmethod
    def review_verification_request(request_id: UUID, review_data: Dict[str, Any],
                                  reviewed_by: Optional[User] = None) -> bool:
        """Review and process verification request."""
        try:
            verification_request = AdvertiserWhitelistService.get_verification_request(request_id)
            
            if verification_request.status not in ['pending', 'under_review']:
                raise AdvertiserValidationError(f"Verification request cannot be reviewed in status: {verification_request.status}")
            
            decision = review_data.get('decision')
            if decision not in ['approve', 'reject', 'request_more_info']:
                raise AdvertiserValidationError("decision must be 'approve', 'reject', or 'request_more_info'")
            
            with transaction.atomic():
                # Update verification request
                verification_request.status = decision
                verification_request.reviewed_at = timezone.now()
                verification_request.reviewed_by = reviewed_by
                verification_request.review_notes = review_data.get('review_notes', '')
                verification_request.save(update_fields=['status', 'reviewed_at', 'reviewed_by', 'review_notes'])
                
                advertiser = verification_request.advertiser
                
                if decision == 'approve':
                    # Add to whitelist
                    trust_level = review_data.get('trust_level', 'standard')
                    AdvertiserWhitelistService.add_to_whitelist(
                        str(advertiser.id),
                        {
                            'trust_level': trust_level,
                            'reason': f'Verification approved: {verification_request.verification_type}',
                            'description': f'Verification request {request_id} approved',
                            'verification_status': 'verified',
                            'verification_date': timezone.now().date()
                        },
                        reviewed_by
                    )
                    
                    # Send approval notification
                    Notification.objects.create(
                        advertiser=advertiser,
                        user=advertiser.user,
                        title='Verification Approved',
                        message=f'Your {verification_request.verification_type} verification has been approved.',
                        notification_type='verification',
                        priority='high',
                        channels=['in_app', 'email']
                    )
                    
                elif decision == 'reject':
                    # Send rejection notification
                    Notification.objects.create(
                        advertiser=advertiser,
                        user=advertiser.user,
                        title='Verification Rejected',
                        message=f'Your {verification_request.verification_type} verification has been rejected.',
                        notification_type='verification',
                        priority='high',
                        channels=['in_app', 'email']
                    )
                    
                elif decision == 'request_more_info':
                    # Send request for more info notification
                    Notification.objects.create(
                        advertiser=advertiser,
                        user=advertiser.user,
                        title='Additional Information Required',
                        message=f'Additional information is required for your {verification_request.verification_type} verification.',
                        notification_type='verification',
                        priority='medium',
                        channels=['in_app', 'email']
                    )
                
                # Log review
                from ..database_models.audit_model import AuditLog
                AuditLog.log_action(
                    action='review_verification_request',
                    object_type='VerificationRequest',
                    object_id=str(verification_request.id),
                    user=reviewed_by,
                    advertiser=advertiser,
                    description=f"Reviewed verification request: {decision}"
                )
                
                return True
                
        except VerificationRequest.DoesNotExist:
            raise AdvertiserNotFoundError(f"Verification request {request_id} not found")
        except Exception as e:
            logger.error(f"Error reviewing verification request {request_id}: {str(e)}")
            return False
    
    @staticmethod
    def get_whitelist_status(advertiser_id: UUID) -> Dict[str, Any]:
        """Get whitelist status for advertiser."""
        try:
            advertiser = AdvertiserWhitelistService.get_advertiser(advertiser_id)
            
            # Get active whitelist entry
            whitelist_entry = WhitelistEntry.objects.filter(
                advertiser=advertiser,
                status='active'
            ).first()
            
            if not whitelist_entry:
                return {
                    'advertiser_id': str(advertiser_id),
                    'is_whitelisted': False,
                    'status': 'not_whitelisted',
                    'message': 'Advertiser is not whitelisted',
                    'trust_level': 'basic'
                }
            
            # Get verification history
            verification_requests = VerificationRequest.objects.filter(
                advertiser=advertiser
            ).order_by('-requested_at')[:5]
            
            return {
                'advertiser_id': str(advertiser_id),
                'is_whitelisted': True,
                'status': 'whitelisted',
                'whitelist_entry': {
                    'id': str(whitelist_entry.id),
                    'trust_level': whitelist_entry.trust_level,
                    'reason': whitelist_entry.reason,
                    'description': whitelist_entry.description,
                    'verification_status': whitelist_entry.verification_status,
                    'verification_date': whitelist_entry.verification_date.isoformat(),
                    'expires_at': whitelist_entry.expires_at.isoformat() if whitelist_entry.expires_at else None,
                    'permanent': whitelist_entry.permanent,
                    'benefits': whitelist_entry.benefits,
                    'restrictions': whitelist_entry.restrictions
                },
                'verification_requests': [
                    {
                        'id': str(request.id),
                        'verification_type': request.verification_type,
                        'status': request.status,
                        'requested_at': request.requested_at.isoformat(),
                        'reviewed_at': request.reviewed_at.isoformat() if request.reviewed_at else None
                    }
                    for request in verification_requests
                ]
            }
            
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error getting whitelist status {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to get whitelist status: {str(e)}")
    
    @staticmethod
    def get_trust_benefits(trust_level: str) -> Dict[str, Any]:
        """Get benefits for trust level."""
        try:
            benefits = {
                'basic': {
                    'description': 'Basic trust level with standard features',
                    'benefits': [
                        'Standard campaign limits',
                        'Basic analytics access',
                        'Standard support'
                    ],
                    'restrictions': [
                        'Limited daily spend',
                        'Basic targeting options',
                        'No premium features'
                    ]
                },
                'standard': {
                    'description': 'Standard trust level with enhanced features',
                    'benefits': [
                        'Increased campaign limits',
                        'Advanced analytics',
                        'Priority support',
                        'API access'
                    ],
                    'restrictions': [
                        'No real-time bidding',
                        'Limited custom reports'
                    ]
                },
                'premium': {
                    'description': 'Premium trust level with full features',
                    'benefits': [
                        'Unlimited campaign limits',
                        'Real-time analytics',
                        'Dedicated support',
                        'Advanced API access',
                        'Custom integrations',
                        'Priority delivery'
                    ],
                    'restrictions': []
                },
                'enterprise': {
                    'description': 'Enterprise trust level with maximum benefits',
                    'benefits': [
                        'Unlimited everything',
                        'White-label solutions',
                        'Custom development',
                        '24/7 dedicated support',
                        'SLA guarantees',
                        'Custom pricing',
                        'Early feature access'
                    ],
                    'restrictions': []
                }
            }
            
            return benefits.get(trust_level, benefits['basic'])
            
        except Exception as e:
            logger.error(f"Error getting trust benefits: {str(e)}")
            return {}
    
    @staticmethod
    def update_trust_level(whitelist_id: UUID, new_trust_level: str,
                            updated_by: Optional[User] = None) -> bool:
        """Update trust level for whitelist entry."""
        try:
            whitelist_entry = AdvertiserWhitelistService.get_whitelist_entry(whitelist_id)
            
            if new_trust_level not in ['basic', 'standard', 'premium', 'enterprise']:
                raise AdvertiserValidationError("Invalid trust_level")
            
            with transaction.atomic():
                old_trust_level = whitelist_entry.trust_level
                whitelist_entry.trust_level = new_trust_level
                whitelist_entry.modified_by = updated_by
                whitelist_entry.save(update_fields=['trust_level', 'modified_by'])
                
                # Update advertiser trust level
                advertiser = whitelist_entry.advertiser
                advertiser.trust_level = new_trust_level
                advertiser.save(update_fields=['trust_level'])
                
                # Send notification
                Notification.objects.create(
                    advertiser=advertiser,
                    user=updated_by,
                    title='Trust Level Updated',
                    message=f'Your trust level has been updated from {old_trust_level} to {new_trust_level}.',
                    notification_type='verification',
                    priority='medium',
                    channels=['in_app']
                )
                
                # Log update
                from ..database_models.audit_model import AuditLog
                AuditLog.log_action(
                    action='update_trust_level',
                    object_type='WhitelistEntry',
                    object_id=str(whitelist_entry.id),
                    user=updated_by,
                    advertiser=advertiser,
                    description=f"Updated trust level: {old_trust_level} -> {new_trust_level}"
                )
                
                return True
                
        except WhitelistEntry.DoesNotExist:
            raise AdvertiserNotFoundError(f"Whitelist entry {whitelist_id} not found")
        except Exception as e:
            logger.error(f"Error updating trust level {whitelist_id}: {str(e)}")
            return False
    
    @staticmethod
    def get_whitelist_statistics() -> Dict[str, Any]:
        """Get whitelist statistics."""
        try:
            # Get total whitelist entries
            total_entries = WhitelistEntry.objects.count()
            active_entries = WhitelistEntry.objects.filter(status='active').count()
            
            # Get entries by trust level
            entries_by_trust_level = WhitelistEntry.objects.values('trust_level').annotate(
                count=Count('id')
            )
            
            # Get verification request statistics
            total_requests = VerificationRequest.objects.count()
            requests_by_status = VerificationRequest.objects.values('status').annotate(
                count=Count('id')
            )
            
            # Get verification type distribution
            requests_by_type = VerificationRequest.objects.values('verification_type').annotate(
                count=Count('id')
            )
            
            return {
                'whitelist_entries': {
                    'total': total_entries,
                    'active': active_entries,
                    'by_trust_level': list(entries_by_trust_level)
                },
                'verification_requests': {
                    'total': total_requests,
                    'by_status': list(requests_by_status),
                    'by_type': list(requests_by_type)
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting whitelist statistics: {str(e)}")
            return {
                'whitelist_entries': {'total': 0, 'active': 0, 'by_trust_level': []},
                'verification_requests': {'total': 0, 'by_status': [], 'by_type': []}
            }
    
    @staticmethod
    def get_verification_requests(filters: Optional[Dict[str, Any]] = None,
                                  page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """Get verification requests with filtering and pagination."""
        try:
            queryset = VerificationRequest.objects.all()
            
            # Apply filters
            if filters:
                if 'status' in filters:
                    queryset = queryset.filter(status=filters['status'])
                if 'verification_type' in filters:
                    queryset = queryset.filter(verification_type=filters['verification_type'])
                if 'date_from' in filters:
                    queryset = queryset.filter(requested_at__date__gte=filters['date_from'])
                if 'date_to' in filters:
                    queryset = queryset.filter(requested_at__date__lte=filters['date_to'])
                if 'search' in filters:
                    search = filters['search']
                    queryset = queryset.filter(
                        Q(advertiser__company_name__icontains=search) |
                        Q(request_reason__icontains=search) |
                        Q(contact_email__icontains=search)
                    )
            
            # Count total
            total_count = queryset.count()
            
            # Apply pagination
            offset = (page - 1) * page_size
            requests = queryset[offset:offset + page_size].order_by('-requested_at')
            
            return {
                'requests': [
                    {
                        'id': str(request.id),
                        'advertiser': {
                            'id': str(request.advertiser.id),
                            'company_name': request.advertiser.company_name,
                            'contact_email': request.advertiser.contact_email
                        },
                        'verification_type': request.verification_type,
                        'request_reason': request.request_reason,
                        'status': request.status,
                        'contact_email': request.contact_email,
                        'contact_phone': request.contact_phone,
                        'documents': request.documents,
                        'requested_at': request.requested_at.isoformat(),
                        'reviewed_at': request.reviewed_at.isoformat() if request.reviewed_at else None,
                        'reviewed_by': request.reviewed_by.username if request.reviewed_by else None,
                        'review_notes': request.review_notes
                    }
                    for request in requests
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
            logger.error(f"Error getting verification requests: {str(e)}")
            return {'requests': [], 'pagination': {}}
    
    @staticmethod
    def get_pending_verification_requests(page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """Get pending verification requests for review."""
        try:
            queryset = VerificationRequest.objects.filter(
                status__in=['pending', 'under_review']
            ).order_by('-requested_at')
            
            # Count total
            total_count = queryset.count()
            
            # Apply pagination
            offset = (page - 1) * page_size
            requests = queryset[offset:offset + page_size]
            
            return {
                'requests': [
                    {
                        'id': str(request.id),
                        'advertiser': {
                            'id': str(request.advertiser.id),
                            'company_name': request.advertiser.company_name,
                            'contact_email': request.advertiser.contact_email
                        },
                        'verification_type': request.verification_type,
                        'request_reason': request.request_reason,
                        'status': request.status,
                        'documents': request.documents,
                        'business_details': request.business_details,
                        'requested_at': request.requested_at.isoformat()
                    }
                    for request in requests
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
            logger.error(f"Error getting pending verification requests: {str(e)}")
            return {'requests': [], 'pagination': {}}
    
    @staticmethod
    def check_verification_alerts(advertiser_id: UUID) -> List[Dict[str, Any]]:
        """Check for verification-related alerts."""
        try:
            advertiser = AdvertiserWhitelistService.get_advertiser(advertiser_id)
            
            alerts = []
            
            # Check if not whitelisted
            whitelist_status = AdvertiserWhitelistService.get_whitelist_status(advertiser_id)
            if not whitelist_status['is_whitelisted']:
                alerts.append({
                    'type': 'not_whitelisted',
                    'severity': 'medium',
                    'message': 'Account is not whitelisted. Consider applying for verification.',
                    'action': 'apply_for_verification'
                })
            
            # Check for expiring whitelist entry
            if whitelist_status['is_whitelisted']:
                whitelist_entry = whitelist_status['whitelist_entry']
                if whitelist_entry.get('expires_at'):
                    expires_at = date.fromisoformat(whitelist_entry['expires_at'])
                    days_until_expiry = (expires_at - date.today()).days
                    
                    if days_until_expiry <= 30 and days_until_expiry > 0:
                        alerts.append({
                            'type': 'whitelist_expiring',
                            'severity': 'medium',
                            'message': f'Whitelist entry expires in {days_until_expiry} days.',
                            'expires_at': whitelist_entry['expires_at'],
                            'days_until_expiry': days_until_expiry
                        })
                    elif days_until_expiry <= 0:
                        alerts.append({
                            'type': 'whitelist_expired',
                            'severity': 'high',
                            'message': 'Whitelist entry has expired.',
                            'expires_at': whitelist_entry['expires_at']
                        })
            
            # Check for pending verification requests
            pending_requests = VerificationRequest.objects.filter(
                advertiser=advertiser,
                status__in=['pending', 'under_review']
            ).count()
            
            if pending_requests > 0:
                alerts.append({
                    'type': 'pending_verification',
                    'severity': 'medium',
                    'message': f'{pending_requests} verification request(s) pending review.',
                    'count': pending_requests
                })
            
            return alerts
            
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error checking verification alerts {advertiser_id}: {str(e)}")
            return []
    
    @staticmethod
    def get_advertiser(advertiser_id: UUID) -> Advertiser:
        """Get advertiser by ID."""
        try:
            return Advertiser.objects.get(id=advertiser_id, is_deleted=False)
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
    
    @staticmethod
    def get_whitelist_entry(whitelist_id: UUID) -> WhitelistEntry:
        """Get whitelist entry by ID."""
        try:
            return WhitelistEntry.objects.get(id=whitelist_id)
        except WhitelistEntry.DoesNotExist:
            raise AdvertiserNotFoundError(f"Whitelist entry {whitelist_id} not found")
    
    @staticmethod
    def get_verification_request(request_id: UUID) -> VerificationRequest:
        """Get verification request by ID."""
        try:
            return VerificationRequest.objects.get(id=request_id)
        except VerificationRequest.DoesNotExist:
            raise AdvertiserNotFoundError(f"Verification request {request_id} not found")
    
    @staticmethod
    def get_whitelist_entries(filters: Optional[Dict[str, Any]] = None,
                                page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """Get whitelist entries with filtering and pagination."""
        try:
            queryset = WhitelistEntry.objects.all()
            
            # Apply filters
            if filters:
                if 'status' in filters:
                    queryset = queryset.filter(status=filters['status'])
                if 'trust_level' in filters:
                    queryset = queryset.filter(trust_level=filters['trust_level'])
                if 'verification_status' in filters:
                    queryset = queryset.filter(verification_status=filters['verification_status'])
                if 'date_from' in filters:
                    queryset = queryset.filter(verification_date__gte=filters['date_from'])
                if 'date_to' in filters:
                    queryset = queryset.filter(verification_date__lte=filters['date_to'])
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
            entries = queryset[offset:offset + page_size].order_by('-verification_date')
            
            return {
                'entries': [
                    {
                        'id': str(entry.id),
                        'advertiser': {
                            'id': str(entry.advertiser.id),
                            'company_name': entry.advertiser.company_name,
                            'contact_email': entry.advertiser.contact_email
                        },
                        'trust_level': entry.trust_level,
                        'reason': entry.reason,
                        'description': entry.description,
                        'verification_status': entry.verification_status,
                        'verification_date': entry.verification_date.isoformat(),
                        'verified_by': entry.verified_by.username if entry.verified_by else None,
                        'expires_at': entry.expires_at.isoformat() if entry.expires_at else None,
                        'permanent': entry.permanent,
                        'status': entry.status,
                        'benefits': entry.benefits,
                        'restrictions': entry.restrictions,
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
            logger.error(f"Error getting whitelist entries: {str(e)}")
            return {'entries': [], 'pagination': {}}
