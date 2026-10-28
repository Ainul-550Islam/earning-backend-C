# =============================================================================
# fraud_detection/attachment_upload_view.py
# =============================================================================
"""
Attachment Upload Views for Fraud Detection System.

Provides file upload handling for fraud evidence, documents,
and supporting materials with security validation and processing.
"""

from __future__ import annotations

import logging
import os
import hashlib
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser

from api.fraud_detection.encryption import encrypt_sensitive_data, generate_integrity_hash
from api.fraud_detection.exceptions import AttachmentError


logger = logging.getLogger(__name__)


class AttachmentUploadHandler:
    """
    Handler for fraud detection file attachments.
    
    Manages secure file uploads, validation, storage,
    and metadata tracking for fraud evidence and documents.
    """
    
    def __init__(self):
        """Initialize attachment upload handler."""
        self.allowed_extensions = getattr(settings, 'FRAUD_ATTACHMENT_ALLOWED_EXTENSIONS', [
            '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.csv', '.txt', '.jpg', '.jpeg', '.png', '.gif'
        ])
        self.max_file_size = getattr(settings, 'FRAUD_ATTACHMENT_MAX_FILE_SIZE', 50 * 1024 * 1024)  # 50MB
        self.upload_path = getattr(settings, 'FRAUD_ATTACHMENT_UPLOAD_PATH', 'fraud_attachments/')
        self.virus_scan_enabled = getattr(settings, 'FRAUD_ATTACHMENT_VIRUS_SCAN', False)
        
        # Ensure upload directory exists
        os.makedirs(self.upload_path, exist_ok=True)
    
    def validate_file(self, file: UploadedFile, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Validate uploaded file for security and compliance.
        
        Args:
            file: Uploaded file object
            context: Additional context for validation
            
        Returns:
            Validation results dictionary
            
        Raises:
            ValidationError: If validation fails
        """
        validation_results = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'metadata': {}
        }
        
        # Check file size
        if file.size > self.max_file_size:
            validation_results['valid'] = False
            validation_results['errors'].append(f"File size {file.size} exceeds maximum {self.max_file_size}")
        
        # Check file extension
        file_extension = os.path.splitext(file.name)[1].lower()
        if file_extension not in self.allowed_extensions:
            validation_results['valid'] = False
            validation_results['errors'].append(f"File extension {file_extension} not allowed")
        
        # Check file content type
        expected_mime_types = {
            '.pdf': 'application/pdf',
            '.doc': 'application/msword',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.xls': 'application/vnd.ms-excel',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.csv': 'text/csv',
            '.txt': 'text/plain',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif'
        }
        
        expected_mime = expected_mime_types.get(file_extension)
        if expected_mime and file.content_type != expected_mime:
            validation_results['warnings'].append(f"Content type {file.content_type} doesn't match expected {expected_mime}")
        
        # Generate file metadata
        validation_results['metadata'] = {
            'original_filename': file.name,
            'file_size': file.size,
            'content_type': file.content_type,
            'file_extension': file_extension,
            'upload_time': timezone.now().isoformat()
        }
        
        # Calculate file hash
        file_hash = self._calculate_file_hash(file)
        validation_results['metadata']['file_hash'] = file_hash
        
        # Check for duplicate files
        if self._file_exists(file_hash):
            validation_results['warnings'].append("File with identical content already exists")
        
        # Virus scan (if enabled)
        if self.virus_scan_enabled:
            scan_result = self._scan_file(file)
            validation_results['metadata']['virus_scan'] = scan_result
            if not scan_result.get('clean', True):
                validation_results['valid'] = False
                validation_results['errors'].append("File failed virus scan")
        
        return validation_results
    
    def process_upload(self, file: UploadedFile, 
                      case_id: Optional[Union[int, str]] = None,
                      alert_id: Optional[Union[int, str]] = None,
                      metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Process and store uploaded file.
        
        Args:
            file: Uploaded file object
            case_id: Associated fraud case ID
            alert_id: Associated fraud alert ID
            metadata: Additional metadata
            
        Returns:
            Processing results dictionary
        """
        try:
            # Validate file first
            validation_results = self.validate_file(file, {
                'case_id': case_id,
                'alert_id': alert_id
            })
            
            if not validation_results['valid']:
                raise AttachmentError(f"File validation failed: {validation_results['errors']}")
            
            # Generate secure filename
            file_hash = validation_results['metadata']['file_hash']
            file_extension = os.path.splitext(file.name)[1]
            secure_filename = f"{file_hash}{file_extension}"
            
            # Save file
            file_path = os.path.join(self.upload_path, secure_filename)
            
            with open(file_path, 'wb') as destination:
                for chunk in file.chunks():
                    destination.write(chunk)
            
            # Create attachment record
            attachment_data = {
                'case_id': case_id,
                'alert_id': alert_id,
                'original_filename': file.name,
                'secure_filename': secure_filename,
                'file_path': file_path,
                'file_size': file.size,
                'content_type': file.content_type,
                'file_hash': file_hash,
                'metadata': {
                    **validation_results['metadata'],
                    **(metadata or {})
                },
                'uploaded_by': metadata.get('user_id') if metadata else None,
                'uploaded_at': timezone.now(),
                'status': 'uploaded'
            }
            
            # Save to database (simplified - would use actual model)
            attachment_record = self._save_attachment_record(attachment_data)
            
            return {
                'success': True,
                'attachment_id': attachment_record.get('id'),
                'filename': secure_filename,
                'file_size': file.size,
                'validation_results': validation_results,
                'upload_time': attachment_data['uploaded_at'].isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error processing file upload: {e}")
            # Clean up uploaded file if it exists
            if 'file_path' in locals() and os.path.exists(file_path):
                os.remove(file_path)
            
            raise AttachmentError(f"Failed to process file upload: {e}")
    
    def _calculate_file_hash(self, file: UploadedFile) -> str:
        """Calculate SHA-256 hash of file content."""
        hash_sha256 = hashlib.sha256()
        
        # Reset file pointer
        file.seek(0)
        
        # Read file in chunks
        for chunk in file.chunks():
            hash_sha256.update(chunk)
        
        # Reset file pointer again
        file.seek(0)
        
        return hash_sha256.hexdigest()
    
    def _file_exists(self, file_hash: str) -> bool:
        """Check if file with same hash already exists."""
        # In practice, this would query the database
        # For now, just check file system
        for filename in os.listdir(self.upload_path):
            if filename.startswith(file_hash):
                return True
        return False
    
    def _scan_file(self, file: UploadedFile) -> Dict[str, Any]:
        """Perform virus scan on uploaded file."""
        # Placeholder for virus scanning
        # In practice, this would integrate with antivirus software
        return {
            'clean': True,
            'scan_time': timezone.now().isoformat(),
            'scanner': 'placeholder'
        }
    
    def _save_attachment_record(self, attachment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Save attachment record to database."""
        # Placeholder for database save
        # In practice, this would save to actual model
        return {
            'id': f"attachment_{timezone.now().timestamp()}",
            **attachment_data
        }
    
    def get_attachment_info(self, attachment_id: Union[int, str]) -> Optional[Dict[str, Any]]:
        """Get attachment information."""
        # Placeholder for database retrieval
        # In practice, this would query actual model
        return {
            'id': attachment_id,
            'filename': 'example.pdf',
            'file_size': 1024,
            'uploaded_at': timezone.now().isoformat()
        }
    
    def delete_attachment(self, attachment_id: Union[int, str]) -> bool:
        """Delete attachment file and record."""
        try:
            # Get attachment info
            attachment_info = self.get_attachment_info(attachment_id)
            if not attachment_info:
                return False
            
            # Delete file
            file_path = attachment_info.get('file_path')
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
            
            # Delete database record (placeholder)
            # In practice, this would delete from actual model
            
            return True
            
        except Exception as e:
            logger.error(f"Error deleting attachment {attachment_id}: {e}")
            return False


# Global attachment handler instance
attachment_handler = AttachmentUploadHandler()


@csrf_exempt
@require_http_methods(["POST"])
@login_required
def upload_fraud_attachment(request: Request) -> JsonResponse:
    """
    Upload fraud attachment endpoint.
    
    Handles file uploads for fraud cases and alerts with
    security validation and metadata tracking.
    """
    try:
        if 'file' not in request.FILES:
            return JsonResponse(
                {'error': 'No file provided', 'status': 'error'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        file = request.FILES['file']
        case_id = request.POST.get('case_id')
        alert_id = request.POST.get('alert_id')
        
        # Additional metadata
        metadata = {
            'user_id': request.user.id,
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            'ip_address': request.META.get('REMOTE_ADDR', ''),
            'description': request.POST.get('description', ''),
            'attachment_type': request.POST.get('attachment_type', 'evidence')
        }
        
        # Process upload
        result = attachment_handler.process_upload(
            file=file,
            case_id=case_id,
            alert_id=alert_id,
            metadata=metadata
        )
        
        return JsonResponse(result, status=status.HTTP_201_CREATED)
        
    except AttachmentError as e:
        logger.error(f"Attachment upload error: {e}")
        return JsonResponse(
            {'error': str(e), 'status': 'error'},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"Unexpected error in attachment upload: {e}")
        return JsonResponse(
            {'error': 'Internal server error', 'status': 'error'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_multiple_attachments(request: Request) -> Response:
    """
    Upload multiple fraud attachments.
    
    Handles batch file uploads with validation and tracking.
    """
    try:
        if 'files' not in request.FILES:
            return Response(
                {'error': 'No files provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        files = request.FILES.getlist('files')
        case_id = request.data.get('case_id')
        alert_id = request.data.get('alert_id')
        
        results = []
        errors = []
        
        for file in files:
            try:
                metadata = {
                    'user_id': request.user.id,
                    'batch_upload': True,
                    'attachment_type': request.data.get('attachment_type', 'evidence')
                }
                
                result = attachment_handler.process_upload(
                    file=file,
                    case_id=case_id,
                    alert_id=alert_id,
                    metadata=metadata
                )
                
                results.append(result)
                
            except Exception as e:
                errors.append({
                    'filename': file.name,
                    'error': str(e)
                })
        
        return Response({
            'results': results,
            'errors': errors,
            'total_uploaded': len(results),
            'total_errors': len(errors)
        }, status=status.HTTP_201_CREATED if results else status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        logger.error(f"Unexpected error in multiple attachment upload: {e}")
        return Response(
            {'error': 'Internal server error'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_attachment_info(request: Request, attachment_id: str) -> Response:
    """
    Get attachment information.
    
    Returns metadata and download information for a specific attachment.
    """
    try:
        attachment_info = attachment_handler.get_attachment_info(attachment_id)
        
        if not attachment_info:
            return Response(
                {'error': 'Attachment not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        return Response(attachment_info, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error getting attachment info: {e}")
        return Response(
            {'error': 'Internal server error'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def download_attachment(request: Request, attachment_id: str) -> HttpResponse:
    """
    Download attachment file.
    
    Provides secure file download with access validation.
    """
    try:
        attachment_info = attachment_handler.get_attachment_info(attachment_id)
        
        if not attachment_info:
            return HttpResponse(
                'Attachment not found',
                status=status.HTTP_404_NOT_FOUND
            )
        
        file_path = attachment_info.get('file_path')
        if not file_path or not os.path.exists(file_path):
            return HttpResponse(
                'File not found',
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Serve file
        with open(file_path, 'rb') as f:
            response = HttpResponse(f.read(), content_type=attachment_info.get('content_type', 'application/octet-stream'))
            response['Content-Disposition'] = f'attachment; filename="{attachment_info.get("original_filename", "download")}"'
            response['Content-Length'] = attachment_info.get('file_size', 0)
        
        return response
        
    except Exception as e:
        logger.error(f"Error downloading attachment: {e}")
        return HttpResponse(
            'Internal server error',
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_attachment(request: Request, attachment_id: str) -> Response:
    """
    Delete attachment.
    
    Removes attachment file and database record with proper validation.
    """
    try:
        # Check permissions (simplified - would check user permissions)
        success = attachment_handler.delete_attachment(attachment_id)
        
        if success:
            return Response(
                {'message': 'Attachment deleted successfully'},
                status=status.HTTP_200_OK
            )
        else:
            return Response(
                {'error': 'Attachment not found or could not be deleted'},
                status=status.HTTP_404_NOT_FOUND
            )
        
    except Exception as e:
        logger.error(f"Error deleting attachment: {e}")
        return Response(
            {'error': 'Internal server error'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_attachments(request: Request) -> Response:
    """
    List attachments for case or alert.
    
    Returns paginated list of attachments with metadata.
    """
    try:
        case_id = request.query_params.get('case_id')
        alert_id = request.query_params.get('alert_id')
        
        if not case_id and not alert_id:
            return Response(
                {'error': 'case_id or alert_id required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Placeholder for database query
        # In practice, this would query actual model with pagination
        attachments = [
            {
                'id': 'attachment_1',
                'original_filename': 'evidence.pdf',
                'file_size': 1024,
                'content_type': 'application/pdf',
                'uploaded_at': timezone.now().isoformat()
            }
        ]
        
        return Response({
            'attachments': attachments,
            'total_count': len(attachments),
            'case_id': case_id,
            'alert_id': alert_id
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error listing attachments: {e}")
        return Response(
            {'error': 'Internal server error'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def validate_attachment(request: Request) -> Response:
    """
    Validate attachment before upload.
    
    Performs security and compliance checks without storing the file.
    """
    try:
        if 'file' not in request.FILES:
            return Response(
                {'error': 'No file provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        file = request.FILES['file']
        
        # Validate file
        validation_results = attachment_handler.validate_file(file)
        
        return Response(validation_results, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error validating attachment: {e}")
        return Response(
            {'error': 'Internal server error'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

# ── CLASS WRAPPER: urls.py expects AttachmentUploadAPIView ───────────────────
from rest_framework.views import APIView as _AUV
from rest_framework.permissions import IsAuthenticated as _AUA

class AttachmentUploadAPIView(_AUV):
    permission_classes = [_AUA]
    def post(self, request):
        return upload_fraud_attachment(request)
    def get(self, request):
        attachment_id = request.query_params.get("id", "")
        return get_attachment_info(request, attachment_id)
