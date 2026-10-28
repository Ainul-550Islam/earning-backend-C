# =============================================================================
# auto_mod/attachment_upload_view.py
# =============================================================================

"""
Attachment upload view for auto moderation system.
Handles file uploads and triggers automatic moderation.
"""

import os
import uuid
import logging
from django.conf import settings
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.files.storage import default_storage
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.views.generic import View
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser

from .models import SuspiciousSubmission, ProofScanner
from .choices import SubmissionType, ModerationStatus, ScanType
from .services import ModerationService, BotService
from .validators import validate_image_size, validate_content_type, validate_submission_data
from .exceptions import InvalidSubmissionError, ScanFailedError

logger = logging.getLogger(__name__)
User = get_user_model()


@method_decorator(csrf_exempt, name='dispatch')
class AttachmentUploadView(View):
    """
    Handle file uploads for auto moderation.
    Supports image uploads and triggers automatic scanning.
    """
    
    def __init__(self):
        super().__init__()
        self.allowed_mime_types = getattr(settings, 'AUTO_MOD_ALLOWED_MIME_TYPES', [
            'image/jpeg',
            'image/png', 
            'image/gif',
            'image/webp',
            'application/pdf',
            'text/plain'
        ])
        self.max_file_size = getattr(settings, 'AUTO_MOD_MAX_FILE_SIZE', 10 * 1024 * 1024)  # 10MB
    
    def post(self, request):
        """Handle file upload and moderation."""
        try:
            # Validate user authentication
            if not request.user.is_authenticated:
                return JsonResponse({
                    'success': False,
                    'error': 'Authentication required',
                    'error_code': 'AUTH_REQUIRED'
                }, status=status.HTTP_401_UNAUTHORIZED)
            
            # Get uploaded file
            file_obj = request.FILES.get('file')
            if not file_obj:
                return JsonResponse({
                    'success': False,
                    'error': 'No file provided',
                    'error_code': 'NO_FILE'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Validate file
            validation_result = self._validate_file(file_obj)
            if not validation_result['valid']:
                return JsonResponse({
                    'success': False,
                    'error': validation_result['error'],
                    'error_code': validation_result['error_code']
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Save file and create submission
            submission = self._create_submission(request, file_obj, validation_result)
            
            # Trigger automatic moderation
            moderation_result = self._trigger_moderation(submission)
            
            return JsonResponse({
                'success': True,
                'submission_id': str(submission.pk),
                'content_id': submission.content_id,
                'status': submission.status,
                'moderation_result': moderation_result,
                'file_info': {
                    'name': file_obj.name,
                    'size': file_obj.size,
                    'content_type': validation_result['content_type']
                }
            })
            
        except InvalidSubmissionError as exc:
            logger.warning(f"Invalid submission: {exc}")
            return JsonResponse({
                'success': False,
                'error': str(exc),
                'error_code': 'INVALID_SUBMISSION'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as exc:
            logger.error(f"Attachment upload error: {exc}")
            return JsonResponse({
                'success': False,
                'error': 'Internal server error',
                'error_code': 'INTERNAL_ERROR'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _validate_file(self, file_obj):
        """Validate uploaded file."""
        try:
            # Check file size
            if file_obj.size > self.max_file_size:
                return {
                    'valid': False,
                    'error': f'File size exceeds maximum allowed size of {self.max_file_size // (1024*1024)}MB',
                    'error_code': 'FILE_TOO_LARGE'
                }
            
            # Validate content type
            content_type = validate_content_type(file_obj, self.allowed_mime_types)
            
            # Additional validation based on content type
            if content_type.startswith('image/'):
                validate_image_size(file_obj)
            
            return {
                'valid': True,
                'content_type': content_type,
                'submission_type': self._determine_submission_type(content_type)
            }
            
        except Exception as exc:
            return {
                'valid': False,
                'error': str(exc),
                'error_code': 'VALIDATION_ERROR'
            }
    
    def _determine_submission_type(self, content_type):
        """Determine submission type from content type."""
        if content_type.startswith('image/'):
            return SubmissionType.IMAGE
        elif content_type == 'application/pdf':
            return SubmissionType.DOCUMENT
        elif content_type.startswith('text/'):
            return SubmissionType.TEXT
        else:
            return SubmissionType.IMAGE  # Default to image for unknown types
    
    def _create_submission(self, request, file_obj, validation_result):
        """Create SuspiciousSubmission from uploaded file."""
        try:
            # Generate unique content ID
            content_id = str(uuid.uuid4())
            
            # Save file to storage
            file_path = self._save_file(file_obj, content_id)
            
            # Create submission
            submission = SuspiciousSubmission.objects.create(
                content_id=content_id,
                submission_type=validation_result['submission_type'],
                user=request.user,
                status=ModerationStatus.PENDING,
                risk_score=5.0,  # Default risk score
                ai_confidence=0.0,
                flag_reason='File upload for moderation',
                metadata={
                    'original_filename': file_obj.name,
                    'file_path': file_path,
                    'file_size': file_obj.size,
                    'content_type': validation_result['content_type'],
                    'upload_ip': self._get_client_ip(request),
                    'upload_user_agent': request.META.get('HTTP_USER_AGENT', ''),
                    'upload_timestamp': timezone.now().isoformat()
                }
            )
            
            logger.info(f"Created submission {submission.pk} for file upload by {request.user}")
            return submission
            
        except Exception as exc:
            logger.error(f"Failed to create submission: {exc}")
            raise InvalidSubmissionError(f"Failed to create submission: {exc}")
    
    def _save_file(self, file_obj, content_id):
        """Save uploaded file to storage."""
        try:
            # Generate unique filename
            file_extension = os.path.splitext(file_obj.name)[1]
            filename = f"{content_id}{file_extension}"
            
            # Save to storage
            file_path = default_storage.save(f"auto_mod/uploads/{filename}", file_obj)
            
            return file_path
            
        except Exception as exc:
            logger.error(f"Failed to save file: {exc}")
            raise InvalidSubmissionError(f"Failed to save file: {exc}")
    
    def _trigger_moderation(self, submission):
        """Trigger automatic moderation for the submission."""
        try:
            # Use ModerationService to process the submission
            moderation_service = ModerationService()
            
            # Get file path from metadata
            file_path = submission.metadata.get('file_path')
            if not file_path:
                raise InvalidSubmissionError("No file path available for moderation")
            
            # Process submission through moderation pipeline
            result = moderation_service.process_submission(
                submission_id=str(submission.pk),
                file_urls=[file_path] if file_path else []
            )
            
            logger.info(f"Moderation completed for {submission.pk}: {result.get('status')}")
            return result
            
        except Exception as exc:
            logger.error(f"Moderation failed for {submission.pk}: {exc}")
            # Don't fail the upload, just log the error
            return {
                'status': 'moderation_failed',
                'error': str(exc),
                'message': 'File uploaded but moderation failed'
            }
    
    def _get_client_ip(self, request):
        """Get client IP address."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class AttachmentUploadAPIView(APIView):
    """
    REST API view for file uploads with auto moderation.
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    
    def __init__(self):
        super().__init__()
        self.upload_view = AttachmentUploadView()
    
    def post(self, request):
        """Handle file upload via REST API."""
        # Delegate to the main upload view
        return self.upload_view.post(request)
    
    def get(self, request):
        """Get upload status and limits."""
        return Response({
            'allowed_mime_types': self.upload_view.allowed_mime_types,
            'max_file_size': self.upload_view.max_file_size,
            'max_file_size_mb': self.upload_view.max_file_size // (1024 * 1024),
            'user_authenticated': request.user.is_authenticated,
            'upload_endpoint': '/api/auto_mod/upload/',
            'supported_submission_types': [
                {'type': SubmissionType.IMAGE, 'mime_types': ['image/jpeg', 'image/png', 'image/gif', 'image/webp']},
                {'type': SubmissionType.DOCUMENT, 'mime_types': ['application/pdf']},
                {'type': SubmissionType.TEXT, 'mime_types': ['text/plain']}
            ]
        })


@method_decorator(csrf_exempt, name='dispatch')
@require_http_methods(["POST"])
def bulk_attachment_upload(request):
    """
    Handle bulk file uploads.
    """
    if not request.user.is_authenticated:
        return JsonResponse({
            'success': False,
            'error': 'Authentication required',
            'error_code': 'AUTH_REQUIRED'
        }, status=status.HTTP_401_UNAUTHORIZED)
    
    files = request.FILES.getlist('files')
    if not files:
        return JsonResponse({
            'success': False,
            'error': 'No files provided',
            'error_code': 'NO_FILES'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    upload_view = AttachmentUploadView()
    results = []
    
    for file_obj in files:
        try:
            # Create a mock request for each file
            class MockRequest:
                def __init__(self, original_request, file_obj):
                    self.user = original_request.user
                    self.META = original_request.META
                    self.FILES = {'file': file_obj}
            
            mock_request = MockRequest(request, file_obj)
            result = upload_view.post(mock_request)
            
            # Parse the JSON response
            import json
            result_data = json.loads(result.content.decode('utf-8'))
            results.append(result_data)
            
        except Exception as exc:
            logger.error(f"Bulk upload error for {file_obj.name}: {exc}")
            results.append({
                'success': False,
                'error': str(exc),
                'error_code': 'BULK_UPLOAD_ERROR',
                'filename': file_obj.name
            })
    
    # Count successful and failed uploads
    successful = sum(1 for r in results if r.get('success'))
    failed = len(results) - successful
    
    return JsonResponse({
        'success': True,
        'total_files': len(files),
        'successful': successful,
        'failed': failed,
        'results': results
    })


@method_decorator(csrf_exempt, name='dispatch')
@require_http_methods(["GET"])
def upload_status(request):
    """
    Get upload status for a specific submission.
    """
    if not request.user.is_authenticated:
        return JsonResponse({
            'success': False,
            'error': 'Authentication required',
            'error_code': 'AUTH_REQUIRED'
        }, status=status.HTTP_401_UNAUTHORIZED)
    
    submission_id = request.GET.get('submission_id')
    if not submission_id:
        return JsonResponse({
            'success': False,
            'error': 'Submission ID required',
            'error_code': 'SUBMISSION_ID_REQUIRED'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        submission = SuspiciousSubmission.objects.get(pk=submission_id)
        
        # Check if user has permission to view this submission
        if submission.user != request.user and not request.user.is_staff:
            return JsonResponse({
                'success': False,
                'error': 'Permission denied',
                'error_code': 'PERMISSION_DENIED'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Get scan results
        scanners = ProofScanner.objects.filter(submission=submission)
        scan_results = []
        
        for scanner in scanners:
            scan_results.append({
                'scan_type': scanner.scan_type,
                'confidence': scanner.confidence,
                'is_flagged': scanner.is_flagged,
                'labels': scanner.labels,
                'error_message': scanner.error_message,
                'duration_ms': scanner.duration_ms,
                'created_at': scanner.created_at.isoformat()
            })
        
        return JsonResponse({
            'success': True,
            'submission': {
                'id': str(submission.pk),
                'content_id': submission.content_id,
                'status': submission.status,
                'risk_score': submission.risk_score,
                'ai_confidence': submission.ai_confidence,
                'flag_reason': submission.flag_reason,
                'created_at': submission.created_at.isoformat(),
                'updated_at': submission.updated_at.isoformat()
            },
            'scan_results': scan_results,
            'metadata': submission.metadata
        })
        
    except SuspiciousSubmission.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Submission not found',
            'error_code': 'SUBMISSION_NOT_FOUND'
        }, status=status.HTTP_404_NOT_FOUND)
    
    except Exception as exc:
        logger.error(f"Upload status error: {exc}")
        return JsonResponse({
            'success': False,
            'error': 'Internal server error',
            'error_code': 'INTERNAL_ERROR'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
