# api/rate_limit/attachment_upload_view.py
"""
Attachment Upload View for Rate Limit Module

Handles file uploads for rate limit attachments, screenshots, and evidence files.
Integrates with rate limiting to prevent abuse of file upload functionality.
"""

import os
import uuid
import json
import logging
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser

from api.rate_limit.decorators import rate_limit, premium_only
from api.rate_limit.services import RateLimitService
from api.rate_limit.exceptions import RateLimitExceededException

logger = logging.getLogger(__name__)


class AttachmentUploadView(APIView):
    """
    Handle file uploads for rate limit attachments with security checks.
    """
    parser_classes = [MultiPartParser, FormParser]
    
    # File upload restrictions
    ALLOWED_FILE_TYPES = {
        'image/jpeg': ['.jpg', '.jpeg'],
        'image/png': ['.png'],
        'image/gif': ['.gif'],
        'application/pdf': ['.pdf'],
        'text/plain': ['.txt'],
        'application/json': ['.json'],
        'text/csv': ['.csv'],
        'image/webp': ['.webp'],
    }
    
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    MAX_FILES_PER_REQUEST = 5
    
    @rate_limit(requests=10, minutes=1)  # 10 uploads per minute
    @csrf_exempt
    def post(self, request, *args, **kwargs):
        """
        Handle file upload with rate limiting and security validation.
        """
        try:
            # Check if user is authenticated
            if not request.user.is_authenticated:
                return Response({
                    'success': False,
                    'error': 'authentication_required',
                    'message': 'Authentication required for file uploads'
                }, status=status.HTTP_401_UNAUTHORIZED)
            
            # Get uploaded files
            files = request.FILES.getlist('files')
            if not files:
                return Response({
                    'success': False,
                    'error': 'no_files',
                    'message': 'No files provided'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Check file count limit
            if len(files) > self.MAX_FILES_PER_REQUEST:
                return Response({
                    'success': False,
                    'error': 'too_many_files',
                    'message': f'Maximum {self.MAX_FILES_PER_REQUEST} files allowed per request'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            uploaded_files = []
            errors = []
            
            for file in files:
                try:
                    # Validate file
                    validation_result = self._validate_file(file)
                    if not validation_result['valid']:
                        errors.append({
                            'filename': file.name,
                            'error': validation_result['error'],
                            'message': validation_result['message']
                        })
                        continue
                    
                    # Generate unique filename
                    unique_filename = self._generate_unique_filename(file.name)
                    
                    # Save file
                    file_path = self._save_file(file, unique_filename)
                    
                    # Create file metadata
                    file_metadata = {
                        'id': str(uuid.uuid4()),
                        'original_name': file.name,
                        'filename': unique_filename,
                        'file_path': file_path,
                        'size': file.size,
                        'content_type': file.content_type,
                        'uploaded_at': timezone.now().isoformat(),
                        'uploaded_by': request.user.username,
                        'url': self._get_file_url(file_path)
                    }
                    
                    uploaded_files.append(file_metadata)
                    
                    # Log successful upload
                    logger.info(f"File uploaded successfully: {file.name} by {request.user.username}")
                    
                except Exception as e:
                    logger.error(f"Error uploading file {file.name}: {str(e)}")
                    errors.append({
                        'filename': file.name,
                        'error': 'upload_failed',
                        'message': f'Failed to upload file: {str(e)}'
                    })
            
            # Return response
            response_data = {
                'success': len(uploaded_files) > 0,
                'uploaded_files': uploaded_files,
                'errors': errors,
                'total_uploaded': len(uploaded_files),
                'total_errors': len(errors)
            }
            
            if len(uploaded_files) == 0:
                return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
            
            return Response(response_data, status=status.HTTP_201_CREATED)
            
        except RateLimitExceededException as e:
            return Response({
                'success': False,
                'error': 'rate_limit_exceeded',
                'message': 'Upload rate limit exceeded. Please try again later.',
                'details': e.details
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)
            
        except Exception as e:
            logger.error(f"Unexpected error in file upload: {str(e)}")
            return Response({
                'success': False,
                'error': 'server_error',
                'message': 'An unexpected error occurred during file upload'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _validate_file(self, file):
        """
        Validate uploaded file for security and size restrictions.
        """
        # Check file size
        if file.size > self.MAX_FILE_SIZE:
            return {
                'valid': False,
                'error': 'file_too_large',
                'message': f'File size exceeds maximum allowed size of {self.MAX_FILE_SIZE // (1024*1024)}MB'
            }
        
        # Check file type
        if file.content_type not in self.ALLOWED_FILE_TYPES:
            return {
                'valid': False,
                'error': 'invalid_file_type',
                'message': f'File type {file.content_type} is not allowed'
            }
        
        # Check file extension
        allowed_extensions = self.ALLOWED_FILE_TYPES.get(file.content_type, [])
        file_extension = os.path.splitext(file.name)[1].lower()
        
        if file_extension not in allowed_extensions:
            return {
                'valid': False,
                'error': 'invalid_extension',
                'message': f'File extension {file_extension} is not allowed for this file type'
            }
        
        # Additional security checks
        if self._is_suspicious_file(file):
            return {
                'valid': False,
                'error': 'suspicious_file',
                'message': 'File appears to be suspicious and was rejected'
            }
        
        return {'valid': True}
    
    def _is_suspicious_file(self, file):
        """
        Check for suspicious file patterns.
        """
        suspicious_patterns = [
            b'<script',
            b'javascript:',
            b'vbscript:',
            b'onload=',
            b'onerror=',
            b'eval(',
            b'exec(',
        ]
        
        try:
            # Read first 1KB of file to check for suspicious content
            file_content = file.read(1024)
            file.seek(0)  # Reset file pointer
            
            for pattern in suspicious_patterns:
                if pattern in file_content.lower():
                    return True
                    
        except Exception:
            # If we can't read the file, consider it suspicious
            return True
        
        return False
    
    def _generate_unique_filename(self, original_name):
        """
        Generate a unique filename to prevent conflicts.
        """
        file_extension = os.path.splitext(original_name)[1]
        unique_id = str(uuid.uuid4())
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        
        return f"{timestamp}_{unique_id}{file_extension}"
    
    def _save_file(self, file, filename):
        """
        Save file to storage with proper path structure.
        """
        # Create directory structure based on date
        date_path = timezone.now().strftime('rate_limit_attachments/%Y/%m/%d')
        file_path = os.path.join(date_path, filename)
        
        # Ensure directory exists
        if not default_storage.exists(date_path):
            default_storage.makedirs(date_path)
        
        # Save file
        path = default_storage.save(file_path, ContentFile(file.read()))
        
        return path
    
    def _get_file_url(self, file_path):
        """
        Generate URL for accessing the uploaded file.
        """
        if hasattr(default_storage, 'url'):
            return default_storage.url(file_path)
        
        # Fallback URL construction
        return f"{settings.MEDIA_URL}{file_path}"


class AttachmentDownloadView(APIView):
    """
    Handle file downloads for rate limit attachments.
    """
    
    @rate_limit(requests=50, minutes=1)  # 50 downloads per minute
    def get(self, request, file_id):
        """
        Handle file download with rate limiting.
        """
        try:
            if not request.user.is_authenticated:
                return Response({
                    'success': False,
                    'error': 'authentication_required',
                    'message': 'Authentication required for file downloads'
                }, status=status.HTTP_401_UNAUTHORIZED)
            
            # Find file by ID (this would typically query a database)
            # For now, we'll implement a simple file lookup
            file_info = self._get_file_info(file_id)
            
            if not file_info:
                return Response({
                    'success': False,
                    'error': 'file_not_found',
                    'message': 'File not found'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Check if file exists in storage
            if not default_storage.exists(file_info['file_path']):
                return Response({
                    'success': False,
                    'error': 'file_missing',
                    'message': 'File is missing from storage'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Serve file
            file_handle = default_storage.open(file_info['file_path'])
            response = HttpResponse(
                file_handle.read(),
                content_type=file_info['content_type']
            )
            
            response['Content-Disposition'] = f'attachment; filename="{file_info["original_name"]}"'
            response['Content-Length'] = file_info['size']
            
            # Log download
            logger.info(f"File downloaded: {file_info['original_name']} by {request.user.username}")
            
            return response
            
        except RateLimitExceededException as e:
            return Response({
                'success': False,
                'error': 'rate_limit_exceeded',
                'message': 'Download rate limit exceeded. Please try again later.',
                'details': e.details
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)
            
        except Exception as e:
            logger.error(f"Error downloading file {file_id}: {str(e)}")
            return Response({
                'success': False,
                'error': 'server_error',
                'message': 'An unexpected error occurred during file download'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _get_file_info(self, file_id):
        """
        Get file information by ID.
        This is a placeholder implementation.
        In a real application, this would query a database.
        """
        # This is a simplified implementation
        # In practice, you would store file metadata in a database
        try:
            # For demonstration, we'll return None (file not found)
            # Implement your actual file lookup logic here
            return None
        except Exception:
            return None


class AttachmentListView(APIView):
    """
    List uploaded files for the authenticated user.
    """
    
    @rate_limit(requests=100, minutes=1)
    def get(self, request):
        """
        Get list of uploaded files for the user.
        """
        try:
            if not request.user.is_authenticated:
                return Response({
                    'success': False,
                    'error': 'authentication_required',
                    'message': 'Authentication required'
                }, status=status.HTTP_401_UNAUTHORIZED)
            
            # This would typically query a database for user's files
            # For now, return empty list as placeholder
            user_files = []
            
            return Response({
                'success': True,
                'files': user_files,
                'total_files': len(user_files)
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error listing files for user {request.user.username}: {str(e)}")
            return Response({
                'success': False,
                'error': 'server_error',
                'message': 'An unexpected error occurred'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# URL patterns for this view
urlpatterns = [
    # These would be added to the main urls.py
    # path('api/rate-limit/attachments/upload/', AttachmentUploadView.as_view(), name='rate_limit_attachment_upload'),
    # path('api/rate-limit/attachments/download/<uuid:file_id>/', AttachmentDownloadView.as_view(), name='rate_limit_attachment_download'),
    # path('api/rate-limit/attachments/', AttachmentListView.as_view(), name='rate_limit_attachment_list'),
]
