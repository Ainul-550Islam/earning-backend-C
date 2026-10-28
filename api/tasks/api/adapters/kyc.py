"""
api/adapters/kyc.py
KYC (Know Your Customer) adapter for earning backend platform
"""
from django.db.models import Q
import logging
from typing import Dict, Any, Optional, List
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.utils import timezone
from django.db.models import Count, Sum, Avg, F, ExpressionWrapper, fields
from decimal import Decimal
from datetime import timedelta

logger = logging.getLogger(__name__)
User = get_user_model()


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_kyc_profile(request):
    """Get user's KYC profile."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get user's KYC profile
        from kyc.models import KYCProfile
        try:
            profile = KYCProfile.objects.get(
                user=user,
                tenant_id=tenant_id
            )
        except KYCProfile.DoesNotExist:
            # Create default KYC profile
            profile = KYCProfile.objects.create(
                user=user,
                status='not_started',
                tier='none',
                tenant_id=tenant_id,
                created_at=timezone.now()
            )
        
        # Get verification documents
        from kyc.models import KYCDocument
        documents = KYCDocument.objects.filter(
            profile=profile
        ).order_by('-created_at')
        
        # Get verification history
        from kyc.models import KYCVerification
        verifications = KYCVerification.objects.filter(
            profile=profile
        ).order_by('-created_at')
        
        profile_data = {
            'user_id': user.id,
            'tenant_id': tenant_id,
            'kyc_profile': {
                'profile_id': profile.id,
                'status': profile.status,
                'tier': profile.tier,
                'created_at': profile.created_at.isoformat(),
                'updated_at': profile.updated_at.isoformat() if profile.updated_at else None,
                'completed_at': profile.completed_at.isoformat() if profile.completed_at else None,
                'expires_at': profile.expires_at.isoformat() if profile.expires_at else None,
                'verification_level': profile.verification_level,
                'risk_score': profile.risk_score,
                'manual_review_required': profile.manual_review_required,
                'review_notes': profile.review_notes,
                'verification_methods': profile.verification_methods,
                'metadata': profile.metadata
            },
            'documents': [
                {
                    'id': doc.id,
                    'document_type': doc.document_type,
                    'status': doc.status,
                    'file_url': doc.file_url,
                    'file_name': doc.file_name,
                    'file_size': doc.file_size,
                    'mime_type': doc.mime_type,
                    'uploaded_at': doc.uploaded_at.isoformat(),
                    'verified_at': doc.verified_at.isoformat() if doc.verified_at else None,
                    'rejection_reason': doc.rejection_reason,
                    'expiry_date': doc.expiry_date.isoformat() if doc.expiry_date else None,
                    'metadata': doc.metadata,
                    'is_valid': _is_document_valid(doc)
                }
                for doc in documents
            ],
            'verifications': [
                {
                    'id': verification.id,
                    'verification_type': verification.verification_type,
                    'status': verification.status,
                    'initiated_at': verification.initiated_at.isoformat(),
                    'completed_at': verification.completed_at.isoformat() if verification.completed_at else None,
                    'result': verification.result,
                    'confidence_score': verification.confidence_score,
                    'verification_data': verification.verification_data,
                    'provider': verification.provider,
                    'transaction_id': verification.transaction_id,
                    'rejection_reason': verification.rejection_reason,
                    'metadata': verification.metadata
                }
                for verification in verifications
            ],
            'requirements': _get_kyc_requirements(profile),
            'next_steps': _get_kyc_next_steps(profile),
            'tier_benefits': _get_tier_benefits(profile.tier, tenant_id),
            'verification_history': _get_verification_summary(verifications)
        }
        
        return Response({
            'success': True,
            'data': profile_data,
            'message': 'KYC profile retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[KYCAdapter] Error getting KYC profile: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve KYC profile',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_kyc_verification(request):
    """Start KYC verification process."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        data = request.data
        
        # Validate required fields
        verification_type = data.get('verification_type')
        if not verification_type:
            return Response({
                'success': False,
                'error': 'Verification type required',
                'details': 'Please specify verification type'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get user's KYC profile
        from kyc.models import KYCProfile
        try:
            profile = KYCProfile.objects.get(
                user=user,
                tenant_id=tenant_id
            )
        except KYCProfile.DoesNotExist:
            profile = KYCProfile.objects.create(
                user=user,
                status='in_progress',
                tier='none',
                tenant_id=tenant_id,
                created_at=timezone.now()
            )
        
        # Check if verification is already in progress
        if profile.status == 'in_progress':
            return Response({
                'success': False,
                'error': 'Verification already in progress',
                'details': 'Please complete current verification before starting new one'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create verification record
        from kyc.models import KYCVerification
        verification = KYCVerification.objects.create(
            profile=profile,
            verification_type=verification_type,
            status='pending',
            initiated_at=timezone.now(),
            provider=_get_verification_provider(verification_type),
            metadata=data.get('metadata', {}),
            tenant_id=tenant_id,
            created_at=timezone.now()
        )
        
        # Update profile status
        profile.status = 'in_progress'
        profile.updated_at = timezone.now()
        profile.save()
        
        # Emit verification started event
        from api.tasks.integration.event_bus import EventBus
        EventBus.emit('kyc.verification_started', {
            'user_id': user.id,
            'verification_id': verification.id,
            'verification_type': verification_type,
            'tenant_id': tenant_id
        })
        
        return Response({
            'success': True,
            'data': {
                'verification_id': verification.id,
                'verification_type': verification_type,
                'status': 'pending',
                'initiated_at': verification.initiated_at.isoformat(),
                'provider': verification.provider,
                'estimated_completion_time': _get_estimated_completion_time(verification_type),
                'next_steps': _get_verification_steps(verification_type, provider=verification.provider),
                'requirements': _get_verification_requirements(verification_type, tenant_id)
            },
            'message': 'KYC verification started successfully'
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"[KYCAdapter] Error starting KYC verification: {e}")
        return Response({
            'success': False,
            'error': 'Failed to start KYC verification',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_kyc_document(request):
    """Upload KYC verification document."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        data = request.data
        
        # Validate required fields
        required_fields = ['document_type', 'file']
        for field in required_fields:
            if field not in data:
                return Response({
                    'success': False,
                    'error': 'Missing required field',
                    'details': f'{field} is required'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get user's KYC profile
        from kyc.models import KYCProfile
        try:
            profile = KYCProfile.objects.get(
                user=user,
                tenant_id=tenant_id
            )
        except KYCProfile.DoesNotExist:
            return Response({
                'success': False,
                'error': 'KYC profile not found',
                'details': 'Please start KYC verification first'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Handle file upload
        file_data = data['file']
        document_type = data['document_type']
        
        # Validate document type
        if not _is_valid_document_type(document_type):
            return Response({
                'success': False,
                'error': 'Invalid document type',
                'details': f'{document_type} is not a valid document type'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create document record
        from kyc.models import KYCDocument
        document = KYCDocument.objects.create(
            profile=profile,
            document_type=document_type,
            file_name=file_data.get('name', ''),
            file_url=file_data.get('url', ''),
            file_size=file_data.get('size', 0),
            mime_type=file_data.get('mime_type', 'application/octet-stream'),
            status='pending',
            expiry_date=_get_document_expiry_date(document_type),
            metadata=data.get('metadata', {}),
            tenant_id=tenant_id,
            uploaded_at=timezone.now()
        )
        
        # Process document verification
        verification_result = _process_document_verification(document, document_type)
        
        # Update document status
        document.status = verification_result['status']
        document.verified_at = verification_result['verified_at'] if verification_result['status'] == 'verified' else None
        document.rejection_reason = verification_result.get('rejection_reason')
        document.save()
        
        # Update profile if all documents verified
        _update_profile_status(profile)
        
        # Emit document uploaded event
        from api.tasks.integration.event_bus import EventBus
        EventBus.emit('kyc.document_uploaded', {
            'user_id': user.id,
            'document_id': document.id,
            'document_type': document_type,
            'status': document.status,
            'tenant_id': tenant_id
        })
        
        return Response({
            'success': True,
            'data': {
                'document_id': document.id,
                'document_type': document_type,
                'status': document.status,
                'file_name': document.file_name,
                'file_size': document.file_size,
                'uploaded_at': document.uploaded_at.isoformat(),
                'verified_at': document.verified_at.isoformat() if document.verified_at else None,
                'rejection_reason': document.rejection_reason,
                'expiry_date': document.expiry_date.isoformat() if document.expiry_date else None,
                'metadata': document.metadata
            },
            'message': 'Document uploaded successfully'
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"[KYCAdapter] Error uploading KYC document: {e}")
        return Response({
            'success': False,
            'error': 'Failed to upload KYC document',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_verification_status(request):
    """Get verification status."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get user's KYC profile
        from kyc.models import KYCProfile
        try:
            profile = KYCProfile.objects.get(
                user=user,
                tenant_id=tenant_id
            )
        except KYCProfile.DoesNotExist:
            return Response({
                'success': False,
                'error': 'KYC profile not found',
                'details': 'Please start KYC verification first'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Get latest verification
        from kyc.models import KYCVerification
        latest_verification = KYCVerification.objects.filter(
            profile=profile
        ).order_by('-created_at').first()
        
        # Get verification progress
        progress = _calculate_verification_progress(profile, latest_verification)
        
        status_data = {
            'user_id': user.id,
            'tenant_id': tenant_id,
            'profile_status': profile.status,
            'verification_level': profile.verification_level,
            'tier': profile.tier,
            'current_verification': {
                'verification_id': latest_verification.id if latest_verification else None,
                'verification_type': latest_verification.verification_type if latest_verification else None,
                'status': latest_verification.status if latest_verification else None,
                'initiated_at': latest_verification.initiated_at.isoformat() if latest_verification else None,
                'estimated_completion': latest_verification.initiated_at + timedelta(hours=24) if latest_verification else None,
                'provider': latest_verification.provider if latest_verification else None,
                'progress_percentage': progress['percentage'],
                'completed_steps': progress['completed_steps'],
                'remaining_steps': progress['remaining_steps'],
                'current_step': progress['current_step'],
                'confidence_score': latest_verification.confidence_score if latest_verification else 0,
            } if latest_verification else None,
            'requirements': _get_verification_requirements(latest_verification.verification_type if latest_verification else None, tenant_id),
            'next_actions': _get_next_verification_actions(profile, latest_verification),
            'tier_benefits': _get_tier_benefits(profile.tier, tenant_id),
            'estimated_completion_time': latest_verification.initiated_at + timedelta(hours=24) if latest_verification else None,
            'expires_at': profile.expires_at.isoformat() if profile.expires_at else None,
            'manual_review_required': profile.manual_review_required,
            'review_notes': profile.review_notes
        }
        
        return Response({
            'success': True,
            'data': status_data,
            'message': 'Verification status retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[KYCAdapter] Error getting verification status: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve verification status',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def get_kyc_analytics(request):
    """Get KYC analytics for admin."""
    try:
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get date range
        days = int(request.GET.get('days', 30))
        start_date = timezone.now() - timedelta(days=days)
        
        # Get KYC analytics
        from kyc.models import KYCProfile, KYCVerification, KYCDocument
        profiles = KYCProfile.objects.filter(
            tenant_id=tenant_id,
            created_at__gte=start_date
        )
        
        verifications = KYCVerification.objects.filter(
            tenant_id=tenant_id,
            created_at__gte=start_date
        )
        
        documents = KYCDocument.objects.filter(
            tenant_id=tenant_id,
            uploaded_at__gte=start_date
        )
        
        # Calculate analytics
        analytics_data = {
            'tenant_id': tenant_id,
            'period': {
                'days': days,
                'start_date': start_date.isoformat(),
                'end_date': timezone.now().isoformat()
            },
            'profile_metrics': {
                'total_profiles': profiles.count(),
                'new_profiles': profiles.filter(
                    created_at__gte=timezone.now() - timedelta(days=7)
                ).count(),
                'completed_profiles': profiles.filter(status='completed').count(),
                'in_progress_profiles': profiles.filter(status='in_progress').count(),
                'not_started_profiles': profiles.filter(status='not_started').count(),
                'tier_distribution': list(profiles.values('tier').annotate(
                    count=Count('id')
                ).order_by('-count')),
                'average_completion_time_hours': profiles.filter(
                    status='completed',
                    completed_at__isnull=False
                ).aggregate(
                    avg_time=Avg(F('completed_at') - F('created_at'))
                )['avg_time'].total_seconds() / 3600 if profiles.filter(status='completed').exists() else 0,
                'verification_level_distribution': list(profiles.values('verification_level').annotate(
                    count=Count('id')
                ).order_by('-count'))
            },
            'verification_metrics': {
                'total_verifications': verifications.count(),
                'completed_verifications': verifications.filter(status='completed').count(),
                'failed_verifications': verifications.filter(status='failed').count(),
                'pending_verifications': verifications.filter(status='pending').count(),
                'success_rate': round((verifications.filter(status='completed').count() / max(verifications.count(), 1)) * 100, 2),
                'verification_types': list(verifications.values('verification_type').annotate(
                    count=Count('id')
                ).order_by('-count')),
                'provider_performance': list(verifications.values('provider').annotate(
                    count=Count('id'),
                    success_rate=Avg('confidence_score')
                ).order_by('-count')),
                'average_processing_time_hours': verifications.filter(
                    status='completed'
                ).aggregate(
                    avg_time=Avg(F('completed_at') - F('initiated_at'))
                )['avg_time'].total_seconds() / 3600 if verifications.filter(status='completed').exists() else 0,
                'daily_trends': _get_verification_trends(verifications, days)
            },
            'document_metrics': {
                'total_documents': documents.count(),
                'verified_documents': documents.filter(status='verified').count(),
                'pending_documents': documents.filter(status='pending').count(),
                'rejected_documents': documents.filter(status='rejected').count(),
                'expired_documents': documents.filter(
                    expiry_date__lt=timezone.now()
                ).count(),
                'document_types': list(documents.values('document_type').annotate(
                    count=Count('id')
                ).order_by('-count')),
                'average_file_size': documents.aggregate(
                    avg_size=Avg(F('file_size'))
                )['avg_size'] or 0,
                'total_storage_used': documents.aggregate(
                    total=Sum(F('file_size'))
                )['total'] or 0,
                'daily_upload_trends': _get_document_upload_trends(documents, days)
            },
            'risk_assessment': {
                'high_risk_profiles': profiles.filter(
                    risk_score__gte=70
                ).count(),
                'medium_risk_profiles': profiles.filter(
                    risk_score__gte=40,
                    risk_score__lt=70
                ).count(),
                'low_risk_profiles': profiles.filter(
                    risk_score__lt=40
                ).count(),
                'average_risk_score': profiles.aggregate(
                    avg_score=Avg(F('risk_score'))
                )['avg_score'] or 0,
                'manual_reviews_required': profiles.filter(
                    manual_review_required=True
                ).count(),
                'fraud_detection': {
                    'total_flags': profiles.filter(
                        metadata__contains={'fraud_flag': True}
                    ).count(),
                    'confirmed_cases': profiles.filter(
                        metadata__contains={'fraud_confirmed': True}
                    ).count(),
                    'false_positives': profiles.filter(
                        metadata__contains={'fraud_false_positive': True}
                    ).count()
                }
            }
        }
        
        return Response({
            'success': True,
            'data': analytics_data,
            'message': 'KYC analytics retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[KYCAdapter] Error getting KYC analytics: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve KYC analytics',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Helper functions
def _get_kyc_requirements(profile) -> List[Dict]:
    """Get KYC requirements for profile."""
    requirements = []
    
    if profile.status == 'not_started':
        requirements.extend([
            {
                'type': 'identity_verification',
                'title': 'Identity Verification',
                'description': 'Verify your identity with government-issued ID',
                'status': 'pending',
                'priority': 'high'
            },
            {
                'type': 'address_verification',
                'title': 'Address Verification',
                'description': 'Verify your residential address',
                'status': 'pending',
                'priority': 'medium'
            }
        ])
    
    if profile.status == 'in_progress':
        # Get current verification type
        from kyc.models import KYCVerification
        current_verification = KYCVerification.objects.filter(
            profile=profile,
            status='pending'
        ).order_by('-created_at').first()
        
        if current_verification:
            requirements.append({
                'type': current_verification.verification_type,
                'title': f'{current_verification.verification_type.title()} Verification',
                'description': f'Complete your {current_verification.verification_type} verification',
                'status': 'in_progress',
                'priority': 'high'
            })
    
    if profile.status == 'completed':
        requirements.append({
            'type': 'additional_verification',
            'title': 'Additional Verification',
            'description': 'Complete additional verification for higher tier',
            'status': 'optional',
            'priority': 'low'
        })
    
    return requirements


def _get_kyc_next_steps(profile) -> List[str]:
    """Get next steps for KYC verification."""
    steps = []
    
    if profile.status == 'not_started':
        steps.extend([
            'Start identity verification',
            'Upload required documents',
            'Complete verification process'
        ])
    
    if profile.status == 'in_progress':
        steps.append('Complete current verification process')
    
    if profile.status == 'completed':
        steps.append('Enjoy your enhanced benefits')
    
    return steps


def _get_tier_benefits(tier, tenant_id) -> List[str]:
    """Get benefits for KYC tier."""
    tier_benefits = {
        'none': ['Basic access', 'Standard limits'],
        'basic': ['Standard access', 'Higher limits', 'Email support'],
        'standard': ['Enhanced access', 'Higher limits', 'Priority support', 'Faster withdrawals'],
        'enhanced': ['Premium access', 'Maximum limits', 'Dedicated support', 'Instant withdrawals'],
        'full': ['Ultimate access', 'No limits', 'VIP support', 'Instant withdrawals', 'Exclusive features']
    }
    
    return tier_benefits.get(tier, ['Basic access'])


def _get_verification_summary(verifications) -> Dict:
    """Get verification summary statistics."""
    try:
        total_verifications = verifications.count()
        completed_verifications = verifications.filter(status='completed').count()
        failed_verifications = verifications.filter(status='failed').count()
        
        return {
            'total_verifications': total_verifications,
            'completed_verifications': completed_verifications,
            'failed_verifications': failed_verifications,
            'success_rate': round((completed_verifications / max(total_verifications, 1)) * 100, 2),
            'verification_types': list(verifications.values('verification_type').annotate(
                count=Count('id')
            ).order_by('-count')),
            'average_confidence_score': verifications.filter(
                status='completed'
            ).aggregate(
                avg_score=Avg('confidence_score')
            )['avg_score'] or 0
        }
    except Exception:
        return {}


def _get_verification_provider(verification_type) -> str:
    """Get verification provider for verification type."""
    providers = {
        'identity': 'identity_verification_service',
        'address': 'address_verification_service',
        'document': 'document_verification_service',
        'biometric': 'biometric_verification_service',
        'phone': 'phone_verification_service',
        'email': 'email_verification_service'
    }
    return providers.get(verification_type, 'identity_verification_service')


def _get_estimated_completion_time(verification_type) -> str:
    """Get estimated completion time for verification type."""
    completion_times = {
        'identity': '2-3 business days',
        'address': '1-2 business days',
        'document': 'instant to 24 hours',
        'biometric': 'instant to 1 hour',
        'phone': 'instant to 5 minutes',
        'email': 'instant to 1 hour'
    }
    return completion_times.get(verification_type, '1-2 business days')


def _get_verification_steps(verification_type, provider) -> List[str]:
    """Get verification steps for verification type."""
    steps = []
    
    if verification_type == 'identity':
        steps.extend([
            'Enter personal information',
            'Upload ID document',
            'Verify phone number',
            'Complete verification'
        ])
    
    elif verification_type == 'address':
        steps.extend([
            'Enter address details',
            'Upload proof of address',
            'Verify address',
            'Complete verification'
        ])
    
    elif verification_type == 'document':
        steps.extend([
            'Select document type',
            'Upload document',
            'Wait for verification',
            'Document verified'
        ])
    
    return steps


def _get_verification_requirements(verification_type, tenant_id) -> List[Dict]:
    """Get requirements for verification type."""
    requirements = []
    
    if verification_type == 'identity':
        requirements.extend([
            {
                'name': 'government_id',
                'display_name': 'Government Issued ID',
                'description': 'Valid government-issued photo ID',
                'required': True,
                'file_types': ['image/jpeg', 'image/png'],
                'max_file_size': 5 * 1024 * 1024,  # 5MB
                'expiry_required': True
            },
            {
                'name': 'selfie',
                'display_name': 'Selfie Photo',
                'description': 'Clear selfie with face visible',
                'required': True,
                'file_types': ['image/jpeg', 'image/png'],
                'max_file_size': 2 * 1024 * 1024,  # 2MB
                'expiry_required': False
            }
        ])
    
    elif verification_type == 'address':
        requirements.extend([
            {
                'name': 'proof_of_address',
                'display_name': 'Proof of Address',
                'description': 'Utility bill or bank statement',
                'required': True,
                'file_types': ['image/jpeg', 'image/png', 'application/pdf'],
                'max_file_size': 10 * 1024 * 1024,  # 10MB
                'expiry_required': True
            }
        ])
    
    return requirements


def _is_valid_document_type(document_type) -> bool:
    """Check if document type is valid."""
    valid_types = [
        'government_id',
        'passport',
        'driving_license',
        'national_id',
        'proof_of_address',
        'utility_bill',
        'bank_statement',
        'selfie',
        'passport_photo',
        'id_card_front',
        'id_card_back'
    ]
    return document_type in valid_types


def _get_document_expiry_date(document_type) -> Optional[timezone.datetime]:
    """Get expiry date for document type."""
    if document_type in ['government_id', 'driving_license', 'passport']:
        return timezone.now() + timedelta(days=365)  # 1 year
    elif document_type in ['proof_of_address', 'utility_bill', 'bank_statement']:
        return timezone.now() + timedelta(days=90)  # 3 months
    return None


def _is_document_valid(document) -> bool:
    """Check if document is valid."""
    if document.status != 'verified':
        return False
    
    if document.expiry_date and document.expiry_date < timezone.now():
        return False
    
    return True


def _process_document_verification(document, document_type) -> Dict:
    """Process document verification automatically."""
    try:
        # Simulate automatic verification for certain document types
        if document_type in ['selfie', 'passport_photo']:
            return {
                'status': 'verified',
                'verified_at': timezone.now(),
                'confidence_score': 0.95,
                'rejection_reason': None
            }
        elif document_type in ['government_id', 'driving_license', 'passport']:
            return {
                'status': 'pending',
                'verified_at': None,
                'confidence_score': 0.0,
                'rejection_reason': None
            }
        else:
            return {
                'status': 'pending',
                'verified_at': None,
                'confidence_score': 0.0,
                'rejection_reason': None
            }
    except Exception:
        return {
            'status': 'failed',
            'verified_at': None,
            'confidence_score': 0.0,
            'rejection_reason': 'Processing error'
        }


def _update_profile_status(profile):
    """Update profile status based on document verification."""
    try:
        from kyc.models import KYCDocument
        
        # Get all documents
        documents = KYCDocument.objects.filter(profile=profile)
        
        # Check if all required documents are verified
        required_documents = ['government_id', 'selfie']
        verified_required = documents.filter(
            document_type__in=required_documents,
            status='verified'
        ).count()
        
        if verified_required == len(required_documents):
            profile.status = 'completed'
            profile.completed_at = timezone.now()
            profile.verification_level = 'full'
            profile.tier = 'standard'
        else:
            profile.status = 'in_progress'
            profile.verification_level = 'partial'
        
        profile.updated_at = timezone.now()
        profile.save()
        
    except Exception:
        pass


def _calculate_verification_progress(profile, latest_verification) -> Dict:
    """Calculate verification progress."""
    try:
        if not latest_verification:
            return {
                'percentage': 0,
                'completed_steps': 0,
                'remaining_steps': 100,
                'current_step': 'Not started'
            }
        
        # Get verification steps
        steps = _get_verification_steps(
            latest_verification.verification_type,
            latest_verification.provider
        )
        
        # Calculate progress based on verification status
        if latest_verification.status == 'completed':
            return {
                'percentage': 100,
                'completed_steps': len(steps),
                'remaining_steps': 0,
                'current_step': 'Completed'
            }
        elif latest_verification.status == 'failed':
            return {
                'percentage': 0,
                'completed_steps': 0,
                'remaining_steps': len(steps),
                'current_step': 'Failed - Please retry'
            }
        else:
            # Estimate progress based on time elapsed
            elapsed_time = timezone.now() - latest_verification.initiated_at
            estimated_time = _get_estimated_completion_time(latest_verification.verification_type)
            
            if elapsed_time.total_seconds() > estimated_time.total_seconds():
                return {
                    'percentage': 100,
                    'completed_steps': len(steps),
                    'remaining_steps': 0,
                    'current_step': 'Processing - Please wait'
                }
            
            # Simple progress calculation
            progress_percentage = min(95, (elapsed_time.total_seconds() / estimated_time.total_seconds()) * 100)
            
            # Calculate completed steps
            completed_steps = int((progress_percentage / 100) * len(steps))
            
            return {
                'percentage': round(progress_percentage, 2),
                'completed_steps': completed_steps,
                'remaining_steps': len(steps) - completed_steps,
                'current_step': steps[min(completed_steps, len(steps) - 1)] if completed_steps < len(steps) else steps[-1]
            }
    except Exception:
        return {
            'percentage': 0,
            'completed_steps': 0,
            'remaining_steps': 100,
            'current_step': 'Unknown'
        }


def _get_next_verification_actions(profile, latest_verification) -> List[str]:
    """Get next actions for verification."""
    actions = []
    
    if profile.status == 'not_started':
        actions.extend([
            'Start identity verification',
            'Upload required documents'
        ])
    
    if profile.status == 'in_progress' and latest_verification:
        if latest_verification.status == 'pending':
            actions.extend([
                'Complete verification process',
                'Upload additional documents if required'
            ])
        elif latest_verification.status == 'failed':
            actions.extend([
                'Retry verification',
                'Contact support if issue persists',
                'Upload new documents'
            ])
    
    if profile.status == 'completed':
        actions.extend([
            'Enjoy enhanced benefits',
            'Complete additional verification for higher tier',
            'Update expired documents'
        ])
    
    return actions


def _get_verification_trends(verifications, days) -> List[Dict]:
    """Get verification trends."""
    try:
        from django.db.models import TruncDay
        from datetime import timedelta
        
        start_date = timezone.now() - timedelta(days=days)
        
        daily_trends = verifications.filter(
            created_at__gte=start_date
        ).extra({
            'day': TruncDay('created_at')
        }).values('day').annotate(
            total=Count('id'),
            completed=Count('id', filter=Q(status='completed')),
            failed=Count('id', filter=Q(status='failed'))
        ).order_by('day')
        
        return [
            {
                'date': trend['day'].isoformat(),
                'total_verifications': trend['total'],
                'completed_verifications': trend['completed'],
                'failed_verifications': trend['failed'],
                'success_rate': round((trend['completed'] / max(trend['total'], 1)) * 100, 2)
            }
            for trend in daily_trends
        ]
    except Exception:
        return []


def _get_document_upload_trends(documents, days) -> List[Dict]:
    """Get document upload trends."""
    try:
        from django.db.models import TruncDay
        from datetime import timedelta
        
        start_date = timezone.now() - timedelta(days=days)
        
        daily_trends = documents.filter(
            uploaded_at__gte=start_date
        ).extra({
            'day': TruncDay('uploaded_at')
        }).values('day').annotate(
            total=Count('id'),
            verified=Count('id', filter=Q(status='verified')),
            rejected=Count('id', filter=Q(status='rejected')),
            total_size=Sum(F('file_size'))
        ).order_by('day')
        
        return [
            {
                'date': trend['day'].isoformat(),
                'total_uploads': trend['total'],
                'verified_uploads': trend['verified'],
                'rejected_uploads': trend['rejected'],
                'verification_rate': round((trend['verified'] / max(trend['total'], 1)) * 100, 2),
                'average_file_size': trend['total_size'] / max(trend['total'], 1)
            }
            for trend in daily_trends
        ]
    except Exception:
        return []
