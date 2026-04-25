"""
Advertiser Verification Service

Service for managing advertiser verification processes,
including document review, approval/rejection workflows.
"""

import logging
from typing import Dict, List, Optional, Any
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from ...models.advertiser import Advertiser, AdvertiserVerification
from ...models.notification import AdvertiserNotification

User = get_user_model()
logger = logging.getLogger(__name__)


class AdvertiserVerificationService:
    """
    Service for managing advertiser verification processes.
    
    Handles document review, approval/rejection workflows,
    and verification status management.
    """
    
    def __init__(self):
        self.logger = logger
    
    def submit_verification_document(self, advertiser: Advertiser, document_type: str, 
                                   document_file, additional_data: Dict[str, Any] = None) -> AdvertiserVerification:
        """
        Submit verification document for review.
        
        Args:
            advertiser: Advertiser instance
            document_type: Type of document being submitted
            document_file: Document file
            additional_data: Additional verification data
            
        Returns:
            AdvertiserVerification: Created verification record
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            with transaction.atomic():
                # Check if verification already exists for this document type
                existing_verification = AdvertiserVerification.objects.filter(
                    advertiser=advertiser,
                    document_type=document_type,
                    status__in=['pending', 'approved']
                ).first()
                
                if existing_verification:
                    raise ValidationError(f"Verification for {document_type} already exists")
                
                # Create verification record
                verification = AdvertiserVerification.objects.create(
                    advertiser=advertiser,
                    document_type=document_type,
                    document_file=document_file,
                    status='pending',
                    submitted_at=timezone.now(),
                    metadata=additional_data or {}
                )
                
                # Update advertiser verification status if needed
                self._update_advertiser_verification_status(advertiser)
                
                # Send notification to advertiser
                self._send_document_submitted_notification(advertiser, document_type)
                
                # Send notification to account manager
                self._send_verification_review_notification(advertiser, verification)
                
                self.logger.info(f"Submitted verification document: {advertiser.company_name} - {document_type}")
                return verification
                
        except Exception as e:
            self.logger.error(f"Error submitting verification document: {e}")
            raise ValidationError(f"Failed to submit verification document: {str(e)}")
    
    def review_verification_document(self, verification_id: int, reviewer: User, 
                                   status: str, notes: str = None) -> AdvertiserVerification:
        """
        Review and approve/reject verification document.
        
        Args:
            verification_id: Verification record ID
            reviewer: User reviewing the document
            status: Approval status ('approved' or 'rejected')
            notes: Review notes
            
        Returns:
            AdvertiserVerification: Updated verification record
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            with transaction.atomic():
                verification = AdvertiserVerification.objects.select_related('advertiser').get(id=verification_id)
                
                if verification.status != 'pending':
                    raise ValidationError("Verification document has already been reviewed")
                
                # Update verification record
                verification.status = status
                verification.reviewed_by = reviewer
                verification.reviewed_at = timezone.now()
                verification.review_notes = notes
                verification.save()
                
                # Update advertiser verification status
                self._update_advertiser_verification_status(verification.advertiser)
                
                # Send notification to advertiser
                if status == 'approved':
                    self._send_document_approved_notification(verification.advertiser, verification)
                else:
                    self._send_document_rejected_notification(verification.advertiser, verification, notes)
                
                self.logger.info(f"Reviewed verification document: {verification.advertiser.company_name} - {verification.document_type} - {status}")
                return verification
                
        except AdvertiserVerification.DoesNotExist:
            raise ValidationError("Verification document not found")
        except Exception as e:
            self.logger.error(f"Error reviewing verification document: {e}")
            raise ValidationError(f"Failed to review verification document: {str(e)}")
    
    def get_pending_verifications(self, reviewer: User = None) -> List[AdvertiserVerification]:
        """
        Get pending verification documents.
        
        Args:
            reviewer: Optional reviewer filter
            
        Returns:
            List[AdvertiserVerification]: Pending verification documents
        """
        queryset = AdvertiserVerification.objects.filter(
            status='pending'
        ).select_related('advertiser', 'advertiser__account_manager').order_by('submitted_at')
        
        if reviewer:
            # Filter by account manager if reviewer is not admin
            if not reviewer.is_staff:
                queryset = queryset.filter(advertiser__account_manager=reviewer)
        
        return list(queryset)
    
    def get_verification_history(self, advertiser: Advertiser) -> List[AdvertiserVerification]:
        """
        Get verification history for advertiser.
        
        Args:
            advertiser: Advertiser instance
            
        Returns:
            List[AdvertiserVerification]: Verification history
        """
        return list(
            AdvertiserVerification.objects.filter(
                advertiser=advertiser
            ).order_by('-submitted_at')
        )
    
    def get_required_documents(self, advertiser: Advertiser) -> List[str]:
        """
        Get list of required documents for advertiser.
        
        Args:
            advertiser: Advertiser instance
            
        Returns:
            List[str]: Required document types
        """
        required_docs = ['business_registration']
        
        # Add additional requirements based on business type
        if advertiser.business_type in ['corporation', 'partnership']:
            required_docs.extend(['tax_certificate', 'operating_license'])
        
        if advertiser.business_type == 'individual':
            required_docs.append('government_id')
        
        # Check what's already submitted/approved
        submitted_docs = AdvertiserVerification.objects.filter(
            advertiser=advertiser,
            status__in=['submitted', 'approved']
        ).values_list('document_type', flat=True)
        
        # Return required docs that haven't been submitted/approved
        return [doc for doc in required_docs if doc not in submitted_docs]
    
    def get_verification_progress(self, advertiser: Advertiser) -> Dict[str, Any]:
        """
        Get verification progress for advertiser.
        
        Args:
            advertiser: Advertiser instance
            
        Returns:
            Dict[str, Any]: Verification progress
        """
        required_docs = self.get_required_documents(advertiser)
        total_required = len(required_docs)
        
        # Get submitted documents
        submitted_docs = AdvertiserVerification.objects.filter(
            advertiser=advertiser,
            document_type__in=required_docs
        )
        
        approved_count = submitted_docs.filter(status='approved').count()
        pending_count = submitted_docs.filter(status='pending').count()
        rejected_count = submitted_docs.filter(status='rejected').count()
        
        progress_percentage = (approved_count / total_required * 100) if total_required > 0 else 0
        
        return {
            'total_required': total_required,
            'approved_count': approved_count,
            'pending_count': pending_count,
            'rejected_count': rejected_count,
            'progress_percentage': round(progress_percentage, 2),
            'is_complete': approved_count == total_required,
            'required_documents': required_docs,
            'verification_status': advertiser.verification_status,
        }
    
    def request_additional_document(self, advertiser: Advertiser, document_type: str, 
                                 reason: str, requested_by: User) -> AdvertiserVerification:
        """
        Request additional verification document from advertiser.
        
        Args:
            advertiser: Advertiser instance
            document_type: Type of document requested
            reason: Reason for request
            requested_by: User making the request
            
        Returns:
            AdvertiserVerification: Created verification record
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            with transaction.atomic():
                verification = AdvertiserVerification.objects.create(
                    advertiser=advertiser,
                    document_type=document_type,
                    status='requested',
                    requested_by=requested_by,
                    requested_at=timezone.now(),
                    review_notes=reason
                )
                
                # Send notification to advertiser
                self._send_additional_document_request_notification(advertiser, verification, reason)
                
                self.logger.info(f"Requested additional document: {advertiser.company_name} - {document_type}")
                return verification
                
        except Exception as e:
            self.logger.error(f"Error requesting additional document: {e}")
            raise ValidationError(f"Failed to request additional document: {str(e)}")
    
    def waive_verification_requirement(self, advertiser: Advertiser, document_type: str, 
                                     reason: str, waived_by: User) -> AdvertiserVerification:
        """
        Waive verification requirement for advertiser.
        
        Args:
            advertiser: Advertiser instance
            document_type: Type of document to waive
            reason: Reason for waiver
            waived_by: User waiving the requirement
            
        Returns:
            AdvertiserVerification: Created verification record
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            with transaction.atomic():
                verification = AdvertiserVerification.objects.create(
                    advertiser=advertiser,
                    document_type=document_type,
                    status='waived',
                    reviewed_by=waived_by,
                    reviewed_at=timezone.now(),
                    review_notes=f"Waived: {reason}"
                )
                
                # Update advertiser verification status
                self._update_advertiser_verification_status(advertiser)
                
                # Send notification to advertiser
                self._send_waiver_notification(advertiser, verification, reason)
                
                self.logger.info(f"Waived verification requirement: {advertiser.company_name} - {document_type}")
                return verification
                
        except Exception as e:
            self.logger.error(f"Error waiving verification requirement: {e}")
            raise ValidationError(f"Failed to waive verification requirement: {str(e)}")
    
    def _update_advertiser_verification_status(self, advertiser: Advertiser):
        """Update advertiser verification status based on document status."""
        required_docs = self.get_required_documents(advertiser)
        
        if not required_docs:
            # No documents required
            advertiser.verification_status = 'verified'
        else:
            # Check if all required documents are approved
            approved_docs = AdvertiserVerification.objects.filter(
                advertiser=advertiser,
                document_type__in=required_docs,
                status='approved'
            ).count()
            
            if approved_docs == len(required_docs):
                advertiser.verification_status = 'verified'
            elif approved_docs > 0:
                advertiser.verification_status = 'partial'
            else:
                advertiser.verification_status = 'pending'
        
        advertiser.save()
    
    def _send_document_submitted_notification(self, advertiser: Advertiser, document_type: str):
        """Send notification when document is submitted."""
        AdvertiserNotification.objects.create(
            advertiser=advertiser,
            type='verification_required',
            title=_('Verification Document Submitted'),
            message=_(
                'Your {document_type} document has been submitted for review. '
                'We will review it within 2-3 business days.'
            ).format(document_type=document_type),
            priority='medium'
        )
    
    def _send_verification_review_notification(self, advertiser: Advertiser, verification: AdvertiserVerification):
        """Send notification to account manager for review."""
        if advertiser.account_manager:
            AdvertiserNotification.objects.create(
                advertiser=advertiser,
                type='verification_required',
                title=_('Verification Document Review Required'),
                message=_(
                    'Verification document "{document_type}" submitted by {advertiser} '
                    'requires your review.'
                ).format(
                    document_type=verification.document_type,
                    advertiser=advertiser.company_name
                ),
                priority='high',
                action_url='/admin/advertiser/verification/',
                action_text=_('Review Document')
            )
    
    def _send_document_approved_notification(self, advertiser: Advertiser, verification: AdvertiserVerification):
        """Send notification when document is approved."""
        AdvertiserNotification.objects.create(
            advertiser=advertiser,
            type='verification_required',
            title=_('Verification Document Approved'),
            message=_(
                'Your {document_type} document has been approved. '
                'Thank you for your cooperation.'
            ).format(document_type=verification.document_type),
            priority='medium'
        )
    
    def _send_document_rejected_notification(self, advertiser: Advertiser, verification: AdvertiserVerification, notes: str):
        """Send notification when document is rejected."""
        AdvertiserNotification.objects.create(
            advertiser=advertiser,
            type='verification_required',
            title=_('Verification Document Rejected'),
            message=_(
                'Your {document_type} document has been rejected. '
                'Reason: {reason}. Please submit a corrected document.'
            ).format(
                document_type=verification.document_type,
                reason=notes or 'Document does not meet requirements'
            ),
            priority='high',
            action_url='/advertiser/verification/',
            action_text=_('Resubmit Document')
        )
    
    def _send_additional_document_request_notification(self, advertiser: Advertiser, verification: AdvertiserVerification, reason: str):
        """Send notification when additional document is requested."""
        AdvertiserNotification.objects.create(
            advertiser=advertiser,
            type='verification_required',
            title=_('Additional Document Required'),
            message=_(
                'We require an additional document: {document_type}. '
                'Reason: {reason}.'
            ).format(
                document_type=verification.document_type,
                reason=reason
            ),
            priority='high',
            action_url='/advertiser/verification/',
            action_text=_('Upload Document')
        )
    
    def _send_waiver_notification(self, advertiser: Advertiser, verification: AdvertiserVerification, reason: str):
        """Send notification when requirement is waived."""
        AdvertiserNotification.objects.create(
            advertiser=advertiser,
            type='verification_required',
            title=_('Verification Requirement Waived'),
            message=_(
                'The {document_type} requirement has been waived for your account. '
                'Reason: {reason}.'
            ).format(
                document_type=verification.document_type,
                reason=reason
            ),
            priority='medium'
        )
