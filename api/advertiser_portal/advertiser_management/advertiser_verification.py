"""
Advertiser Verification Management

This module handles advertiser verification processes, KYC compliance,
and verification document management.
"""

from typing import Optional, List, Dict, Any, Union
from decimal import Decimal
from datetime import datetime, date
from uuid import UUID
import os
import hashlib
import secrets

from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.mail import send_mail
from django.conf import settings

from ..database_models.advertiser_model import Advertiser, AdvertiserVerification
from ..database_models.notification_model import Notification
from ..models import AdvertiserPortalBaseModel
from ..enums import *
from ..utils import *
from ..validators import *
from ..exceptions import *

User = get_user_model()


class AdvertiserVerificationService:
    """Service for managing advertiser verification processes."""
    
    @staticmethod
    def initiate_verification(advertiser_id: UUID, verification_type: str = 'business',
                            initiated_by: Optional[User] = None) -> AdvertiserVerification:
        """Initiate advertiser verification process."""
        try:
            advertiser = AdvertiserVerificationService.get_advertiser(advertiser_id)
            
            # Check if verification already exists
            existing_verification = AdvertiserVerification.objects.filter(
                advertiser=advertiser,
                verification_type=verification_type,
                status__in=['pending', 'in_review']
            ).first()
            
            if existing_verification:
                raise AdvertiserValidationError(f"Verification already in progress: {existing_verification.id}")
            
            with transaction.atomic():
                # Create verification record
                verification = AdvertiserVerification.objects.create(
                    advertiser=advertiser,
                    verification_type=verification_type,
                    status=VerificationStatusEnum.PENDING.value,
                    submitted_documents=[],
                    verification_notes='',
                    reviewed_by=None,
                    reviewed_at=None,
                    expires_at=timezone.now() + timezone.timedelta(days=30),
                    created_by=initiated_by
                )
                
                # Generate verification token
                verification_token = AdvertiserVerificationService._generate_verification_token()
                verification.verification_token = verification_token
                verification.save(update_fields=['verification_token'])
                
                # Send verification email
                AdvertiserVerificationService._send_verification_email(advertiser, verification)
                
                # Send notification
                Notification.objects.create(
                    advertiser=advertiser,
                    user=initiated_by,
                    title='Verification Initiated',
                    message=f'{verification_type.title()} verification has been initiated for your account.',
                    notification_type='verification',
                    priority='high',
                    channels=['in_app', 'email']
                )
                
                # Log initiation
                from ..database_models.audit_model import AuditLog
                AuditLog.log_action(
                    action='initiate_verification',
                    object_type='AdvertiserVerification',
                    object_id=str(verification.id),
                    user=initiated_by,
                    advertiser=advertiser,
                    description=f"Initiated {verification_type} verification"
                )
                
                return verification
                
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error initiating verification {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to initiate verification: {str(e)}")
    
    @staticmethod
    def submit_verification_documents(advertiser_id: UUID, documents: List[Dict[str, Any]],
                                       submitted_by: Optional[User] = None) -> AdvertiserVerification:
        """Submit verification documents."""
        try:
            advertiser = AdvertiserVerificationService.get_advertiser(advertiser_id)
            
            # Get pending verification
            verification = AdvertiserVerification.objects.filter(
                advertiser=advertiser,
                status__in=['pending', 'submitted']
            ).first()
            
            if not verification:
                raise AdvertiserValidationError("No pending verification found")
            
            with transaction.atomic():
                # Process uploaded documents
                processed_documents = []
                for doc_data in documents:
                    if 'file' in doc_data:
                        processed_doc = AdvertiserVerificationService._process_document(
                            doc_data['file'],
                            doc_data.get('document_type', 'identity'),
                            doc_data.get('description', '')
                        )
                        processed_documents.append(processed_doc)
                
                # Update verification
                verification.submitted_documents = processed_documents
                verification.status = VerificationStatusEnum.SUBMITTED.value
                verification.save(update_fields=['submitted_documents', 'status'])
                
                # Send notification
                Notification.objects.create(
                    advertiser=advertiser,
                    user=submitted_by,
                    title='Documents Submitted',
                    message=f'Veification documents have been submitted for review.',
                    notification_type='verification',
                    priority='medium',
                    channels=['in_app']
                )
                
                # Log submission
                from ..database_models.audit_model import AuditLog
                AuditLog.log_action(
                    action='submit_documents',
                    object_type='AdvertiserVerification',
                    object_id=str(verification.id),
                    user=submitted_by,
                    advertiser=advertiser,
                    description="Submitted verification documents"
                )
                
                return verification
                
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error submitting verification documents {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to submit verification documents: {str(e)}")
    
    @staticmethod
    def verify_advertiser_token(token: str) -> Dict[str, Any]:
        """Verify advertiser using token."""
        try:
            verification = AdvertiserVerification.objects.filter(
                verification_token=token,
                status__in=['pending', 'submitted']
            ).first()
            
            if not verification:
                raise AdvertiserValidationError("Invalid or expired verification token")
            
            # Check if token is expired
            if verification.expires_at and verification.expires_at < timezone.now():
                verification.status = VerificationStatusEnum.EXPIRED.value
                verification.save(update_fields=['status'])
                raise AdvertiserValidationError("Verification token has expired")
            
            return {
                'verification_id': str(verification.id),
                'advertiser_id': str(verification.advertiser.id),
                'verification_type': verification.verification_type,
                'status': verification.status
            }
            
        except Exception as e:
            logger.error(f"Error verifying token {token}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to verify token: {str(e)}")
    
    @staticmethod
    def review_verification(verification_id: UUID, decision: str, notes: str = '',
                           reviewed_by: Optional[User] = None) -> bool:
        """Review and approve/reject verification."""
        try:
            verification = AdvertiserVerificationService.get_verification(verification_id)
            
            if verification.status not in ['submitted', 'in_review']:
                raise AdvertiserValidationError(f"Cannot review verification in status: {verification.status}")
            
            with transaction.atomic():
                # Update verification status
                if decision.lower() == 'approve':
                    verification.status = VerificationStatusEnum.APPROVED.value
                    verification.reviewed_by = reviewed_by
                    verification.reviewed_at = timezone.now()
                    verification.verification_notes = notes
                    
                    # Update advertiser verification status
                    verification.advertiser.is_verified = True
                    verification.advertiser.verification_date = timezone.now()
                    verification.advertiser.verified_by = reviewed_by
                    verification.advertiser.save(update_fields=['is_verified', 'verification_date', 'verified_by'])
                    
                    # Send approval notification
                    Notification.objects.create(
                        advertiser=verification.advertiser,
                        user=verification.advertiser.user,
                        title='Verification Approved',
                        message=f'Your {verification.verification_type} verification has been approved successfully.',
                        notification_type='verification',
                        priority='high',
                        channels=['in_app', 'email']
                    )
                    
                elif decision.lower() == 'reject':
                    verification.status = VerificationStatusEnum.REJECTED.value
                    verification.reviewed_by = reviewed_by
                    verification.reviewed_at = timezone.now()
                    verification.verification_notes = notes
                    
                    # Send rejection notification
                    Notification.objects.create(
                        advertiser=verification.advertiser,
                        user=verification.advertiser.user,
                        title='Verification Rejected',
                        message=f'Your {verification.verification_type} verification has been rejected. Reason: {notes}',
                        notification_type='verification',
                        priority='high',
                        channels=['in_app', 'email']
                    )
                    
                elif decision.lower() == 'request_more_info':
                    verification.status = VerificationStatusEnum.ADDITIONAL_INFO_REQUIRED.value
                    verification.reviewed_by = reviewed_by
                    verification.reviewed_at = timezone.now()
                    verification.verification_notes = notes
                    
                    # Send request for more info notification
                    Notification.objects.create(
                        advertiser=verification.advertiser,
                        user=verification.advertiser.user,
                        title='Additional Information Required',
                        message=f'Additional information is required for your {verification.verification_type} verification. {notes}',
                        notification_type='verification',
                        priority='high',
                        channels=['in_app', 'email']
                    )
                    
                else:
                    raise AdvertiserValidationError(f"Invalid decision: {decision}")
                
                verification.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'verification_notes'])
                
                # Log review
                from ..database_models.audit_model import AuditLog
                AuditLog.log_action(
                    action='review_verification',
                    object_type='AdvertiserVerification',
                    object_id=str(verification.id),
                    user=reviewed_by,
                    advertiser=verification.advertiser,
                    description=f"Reviewed verification: {decision}"
                )
                
                return True
                
        except AdvertiserVerification.DoesNotExist:
            raise AdvertiserNotFoundError(f"Verification {verification_id} not found")
        except Exception as e:
            logger.error(f"Error reviewing verification {verification_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to review verification: {str(e)}")
    
    @staticmethod
    def get_verification_status(advertiser_id: UUID, verification_type: Optional[str] = None) -> Dict[str, Any]:
        """Get verification status."""
        try:
            advertiser = AdvertiserVerificationService.get_advertiser(advertiser_id)
            
            queryset = AdvertiserVerification.objects.filter(advertiser=advertiser)
            
            if verification_type:
                queryset = queryset.filter(verification_type=verification_type)
            
            verification = queryset.order_by('-created_at').first()
            
            if not verification:
                return {
                    'status': 'not_initiated',
                    'message': 'No verification process initiated'
                }
            
            return {
                'verification_id': str(verification.id),
                'verification_type': verification.verification_type,
                'status': verification.status,
                'submitted_documents': verification.submitted_documents,
                'verification_notes': verification.verification_notes,
                'reviewed_by': verification.reviewed_by.username if verification.reviewed_by else None,
                'reviewed_at': verification.reviewed_at.isoformat() if verification.reviewed_at else None,
                'expires_at': verification.expires_at.isoformat() if verification.expires_at else None,
                'created_at': verification.created_at.isoformat()
            }
            
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error getting verification status {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to get verification status: {str(e)}")
    
    @staticmethod
    def get_verification_history(advertiser_id: UUID) -> List[Dict[str, Any]]:
        """Get verification history."""
        try:
            advertiser = AdvertiserVerificationService.get_advertiser(advertiser_id)
            
            verifications = AdvertiserVerification.objects.filter(
                advertiser=advertiser
            ).order_by('-created_at')
            
            return [
                {
                    'id': str(verification.id),
                    'verification_type': verification.verification_type,
                    'status': verification.status,
                    'submitted_documents': len(verification.submitted_documents),
                    'verification_notes': verification.verification_notes,
                    'reviewed_by': verification.reviewed_by.username if verification.reviewed_by else None,
                    'reviewed_at': verification.reviewed_at.isoformat() if verification.reviewed_at else None,
                    'expires_at': verification.expires_at.isoformat() if verification.expires_at else None,
                    'created_at': verification.created_at.isoformat()
                }
                for verification in verifications
            ]
            
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error getting verification history {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to get verification history: {str(e)}")
    
    @staticmethod
    def _generate_verification_token() -> str:
        """Generate verification token."""
        return f"verify_{secrets.token_urlsafe(32)}_{int(timezone.now().timestamp())}"
    
    @staticmethod
    def _process_document(file: InMemoryUploadedFile, document_type: str, description: str) -> Dict[str, Any]:
        """Process uploaded verification document."""
        try:
            # Generate unique filename
            timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
            filename = f"verification_{timestamp}_{file.name}"
            
            # Create upload directory if not exists
            upload_dir = os.path.join(settings.MEDIA_ROOT, 'verification_documents')
            os.makedirs(upload_dir, exist_ok=True)
            
            # Save file
            file_path = os.path.join(upload_dir, filename)
            with open(file_path, 'wb+') as destination:
                for chunk in file.chunks():
                    destination.write(chunk)
            
            # Calculate file hash
            file_hash = AdvertiserVerificationService._calculate_file_hash(file_path)
            
            # Get file info
            file_size = file.size
            mime_type = file.content_type
            
            return {
                'file_path': file_path,
                'file_name': file.name,
                'file_size': file_size,
                'mime_type': mime_type,
                'file_hash': file_hash,
                'document_type': document_type,
                'description': description,
                'uploaded_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error processing verification document: {str(e)}")
            raise AdvertiserServiceError(f"Failed to process verification document: {str(e)}")
    
    @staticmethod
    def _calculate_file_hash(file_path: str) -> str:
        """Calculate SHA-256 hash of file."""
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    
    @staticmethod
    def _send_verification_email(advertiser: Advertiser, verification: AdvertiserVerification) -> bool:
        """Send verification email to advertiser."""
        try:
            subject = f"Complete Your {verification.verification_type.title()} Verification"
            
            # Generate verification link
            verification_link = f"{settings.FRONTEND_URL}/verify/{verification.verification_token}"
            
            message = f"""
Dear {advertiser.contact_name},

Thank you for choosing our platform! To complete your {verification.verification_type} verification, please click the link below:

{verification_link}

This link will expire in 30 days.

If you have any questions, please contact our support team.

Best regards,
The Team
            """
            
            # Send email
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[advertiser.contact_email],
                fail_silently=False
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending verification email: {str(e)}")
            return False
    
    @staticmethod
    def get_advertiser(advertiser_id: UUID) -> Advertiser:
        """Get advertiser by ID."""
        try:
            return Advertiser.objects.get(id=advertiser_id, is_deleted=False)
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
    
    @staticmethod
    def get_verification(verification_id: UUID) -> AdvertiserVerification:
        """Get verification by ID."""
        try:
            return AdvertiserVerification.objects.get(id=verification_id)
        except AdvertiserVerification.DoesNotExist:
            raise AdvertiserNotFoundError(f"Verification {verification_id} not found")
    
    @staticmethod
    def validate_document_requirements(verification_type: str, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate document requirements for verification type."""
        try:
            requirements = {
                'business': {
                    'required': ['business_license', 'tax_certificate', 'proof_of_address'],
                    'optional': ['bank_statement', 'company_registration'],
                    'max_size': 10 * 1024 * 1024,  # 10MB
                    'allowed_types': ['pdf', 'jpg', 'jpeg', 'png']
                },
                'identity': {
                    'required': ['government_id', 'proof_of_address'],
                    'optional': ['passport', 'driver_license'],
                    'max_size': 5 * 1024 * 1024,  # 5MB
                    'allowed_types': ['pdf', 'jpg', 'jpeg', 'png']
                },
                'financial': {
                    'required': ['bank_statement', 'proof_of_income'],
                    'optional': ['tax_returns', 'financial_statement'],
                    'max_size': 15 * 1024 * 1024,  # 15MB
                    'allowed_types': ['pdf', 'csv', 'xlsx']
                }
            }
            
            if verification_type not in requirements:
                return {
                    'valid': True,
                    'message': f'Unknown verification type: {verification_type}'
                }
            
            req = requirements[verification_type]
            errors = []
            warnings = []
            
            # Check required documents
            submitted_types = [doc.get('document_type') for doc in documents]
            for required_type in req['required']:
                if required_type not in submitted_types:
                    errors.append(f"Missing required document: {required_type}")
            
            # Check file sizes
            for doc in documents:
                file_size = doc.get('file_size', 0)
                if file_size > req['max_size']:
                    errors.append(f"File too large: {doc.get('file_name')} (max: {req['max_size']} bytes)")
            
            # Check file types
            for doc in documents:
                mime_type = doc.get('mime_type', '')
                file_name = doc.get('file_name', '')
                file_ext = file_name.split('.')[-1].lower() if '.' in file_name else ''
                
                if file_ext not in req['allowed_types']:
                    errors.append(f"Invalid file type: {file_name} (allowed: {', '.join(req['allowed_types'])})")
            
            return {
                'valid': len(errors) == 0,
                'errors': errors,
                'warnings': warnings,
                'requirements': req
            }
            
        except Exception as e:
            logger.error(f"Error validating document requirements: {str(e)}")
            return {
                'valid': False,
                'errors': ['Validation error occurred'],
                'warnings': [],
                'requirements': {}
            }
    
    @staticmethod
    def get_verification_statistics() -> Dict[str, Any]:
        """Get verification statistics."""
        try:
            total_verifications = AdvertiserVerification.objects.count()
            pending_verifications = AdvertiserVerification.objects.filter(status='pending').count()
            submitted_verifications = AdvertiserVerification.objects.filter(status='submitted').count()
            approved_verifications = AdvertiserVerification.objects.filter(status='approved').count()
            rejected_verifications = AdvertiserVerification.objects.filter(status='rejected').count()
            
            # Calculate approval rate
            completed_verifications = approved_verifications + rejected_verifications
            approval_rate = (approved_verifications / completed_verifications * 100) if completed_verifications > 0 else 0
            
            # Get verification by type
            verification_by_type = AdvertiserVerification.objects.values('verification_type').annotate(
                count=Count('id')
            )
            
            return {
                'total_verifications': total_verifications,
                'pending_verifications': pending_verifications,
                'submitted_verifications': submitted_verifications,
                'approved_verifications': approved_verifications,
                'rejected_verifications': rejected_verifications,
                'approval_rate': approval_rate,
                'verification_by_type': list(verification_by_type)
            }
            
        except Exception as e:
            logger.error(f"Error getting verification statistics: {str(e)}")
            return {
                'total_verifications': 0,
                'pending_verifications': 0,
                'submitted_verifications': 0,
                'approved_verifications': 0,
                'rejected_verifications': 0,
                'approval_rate': 0,
                'verification_by_type': []
            }
    
    @staticmethod
    def expire_pending_verifications() -> int:
        """Expire pending verification requests."""
        try:
            expired_count = AdvertiserVerification.objects.filter(
                status__in=['pending', 'submitted'],
                expires_at__lt=timezone.now()
            ).update(status='expired')
            
            return expired_count
            
        except Exception as e:
            logger.error(f"Error expiring pending verifications: {str(e)}")
            return 0
