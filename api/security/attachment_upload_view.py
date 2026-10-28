"""
Security Attachment Upload View
Handles secure file uploads with virus scanning and validation
Author: System Security Team
Version: 1.0.0
"""
from django.urls import path

import os
import uuid
import hashlib
from datetime import datetime
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.utils.decorators import method_decorator
from django.views import View
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
import logging

logger = logging.getLogger(__name__)


class SecurityAttachmentUploadView(APIView):
    """
    Secure attachment upload view with comprehensive security checks
    """
    permission_classes = [IsAuthenticated]
    
    # Allowed file types and maximum sizes
    ALLOWED_EXTENSIONS = {
        'image': ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp'],
        'document': ['pdf', 'doc', 'docx', 'txt', 'rtf', 'odt'],
        'spreadsheet': ['xls', 'xlsx', 'csv', 'ods'],
        'presentation': ['ppt', 'pptx', 'odp'],
        'archive': ['zip', 'rar', '7z', 'tar', 'gz'],
    }
    
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    MAX_FILES_PER_REQUEST = 5
    
    def post(self, request, *args, **kwargs):
        """
        Handle secure file upload
        """
        try:
            files = request.FILES.getlist('files')
            
            # Validate number of files
            if len(files) > self.MAX_FILES_PER_REQUEST:
                return Response({
                    'error': f'Maximum {self.MAX_FILES_PER_REQUEST} files allowed per request'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            uploaded_files = []
            errors = []
            
            for file in files:
                try:
                    result = self._process_file(file, request.user)
                    if result['success']:
                        uploaded_files.append(result['file_info'])
                    else:
                        errors.append({
                            'filename': file.name,
                            'error': result['error']
                        })
                except Exception as e:
                    logger.error(f"Error processing file {file.name}: {e}")
                    errors.append({
                        'filename': file.name,
                        'error': 'Internal server error'
                    })
            
            response_data = {
                'uploaded_files': uploaded_files,
                'errors': errors,
                'total_uploaded': len(uploaded_files),
                'total_errors': len(errors)
            }
            
            if errors and not uploaded_files:
                return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
            elif errors:
                return Response(response_data, status=status.HTTP_207_MULTI_STATUS)
            else:
                return Response(response_data, status=status.HTTP_201_CREATED)
                
        except Exception as e:
            logger.error(f"Unexpected error in file upload: {e}")
            return Response({
                'error': 'Internal server error'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _process_file(self, file, user):
        """
        Process individual file with security checks
        """
        try:
            # Validate file size
            if file.size > self.MAX_FILE_SIZE:
                return {
                    'success': False,
                    'error': f'File size exceeds maximum limit of {self.MAX_FILE_SIZE // (1024*1024)}MB'
                }
            
            # Validate file extension
            file_extension = self._get_file_extension(file.name)
            if not self._is_allowed_extension(file_extension):
                return {
                    'success': False,
                    'error': f'File type .{file_extension} is not allowed'
                }
            
            # Scan for malicious content
            scan_result = self._scan_file(file)
            if not scan_result['clean']:
                return {
                    'success': False,
                    'error': f'Security scan detected: {scan_result["threat"]}'
                }
            
            # Generate secure filename
            secure_filename = self._generate_secure_filename(file.name, file_extension)
            
            # Calculate file hash
            file_hash = self._calculate_file_hash(file)
            
            # Check for duplicate files
            existing_file = self._check_duplicate_file(file_hash, user)
            if existing_file:
                return {
                    'success': False,
                    'error': 'File already uploaded',
                    'existing_file': existing_file
                }
            
            # Save file securely
            file_path = self._save_file_securely(file, secure_filename)
            
            # Log upload event
            self._log_upload_event(file, user, file_path, file_hash)
            
            return {
                'success': True,
                'file_info': {
                    'filename': file.name,
                    'secure_filename': secure_filename,
                    'file_path': file_path,
                    'file_size': file.size,
                    'file_type': self._get_file_category(file_extension),
                    'file_hash': file_hash,
                    'uploaded_at': datetime.now().isoformat(),
                    'uploaded_by': user.username
                }
            }
            
        except Exception as e:
            logger.error(f"Error processing file {file.name}: {e}")
            return {
                'success': False,
                'error': 'File processing failed'
            }
    
    def _get_file_extension(self, filename):
        """Get file extension from filename"""
        return filename.split('.')[-1].lower() if '.' in filename else ''
    
    def _is_allowed_extension(self, extension):
        """Check if file extension is allowed"""
        for category, extensions in self.ALLOWED_EXTENSIONS.items():
            if extension in extensions:
                return True
        return False
    
    def _get_file_category(self, extension):
        """Get file category based on extension"""
        for category, extensions in self.ALLOWED_EXTENSIONS.items():
            if extension in extensions:
                return category
        return 'unknown'
    
    def _scan_file(self, file):
        """
        Scan file for malicious content
        In production, integrate with actual antivirus API
        """
        try:
            # Mock virus scan - replace with real implementation
            file_content = file.read(1024)  # Read first 1KB for basic scanning
            file.seek(0)  # Reset file pointer
            
            # Basic malicious content patterns
            malicious_patterns = [
                b'<script',
                b'javascript:',
                b'vbscript:',
                b'data:text/html',
                b'eval(',
                b'exec(',
                b'system(',
                b'shell_exec(',
            ]
            
            for pattern in malicious_patterns:
                if pattern.lower() in file_content.lower():
                    return {
                        'clean': False,
                        'threat': f'Potentially malicious content detected: {pattern.decode()}'
                    }
            
            # Check for executable file signatures
            executable_signatures = [
                b'MZ',      # Windows PE
                b'\x7fELF', # Linux ELF
                b'\xca\xfe\xba\xbe', # Java class
            ]
            
            file.seek(0)
            header = file.read(4)
            file.seek(0)
            
            for signature in executable_signatures:
                if header.startswith(signature):
                    return {
                        'clean': False,
                        'threat': 'Executable file detected'
                    }
            
            return {'clean': True}
            
        except Exception as e:
            logger.error(f"Error scanning file: {e}")
            return {'clean': False, 'threat': 'Scan failed'}
    
    def _generate_secure_filename(self, original_name, extension):
        """Generate secure filename with UUID"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_id = str(uuid.uuid4())[:8]
        return f"{timestamp}_{unique_id}.{extension}"
    
    def _calculate_file_hash(self, file):
        """Calculate SHA-256 hash of file"""
        file.seek(0)
        hash_sha256 = hashlib.sha256()
        for chunk in iter(lambda: file.read(4096), b""):
            hash_sha256.update(chunk)
        file.seek(0)
        return hash_sha256.hexdigest()
    
    def _check_duplicate_file(self, file_hash, user):
        """Check if file already exists for this user"""
        # In production, check against database
        # For now, return None (no duplicate)
        return None
    
    def _save_file_securely(self, file, secure_filename):
        """Save file with secure path"""
        # Create secure directory structure
        upload_dir = os.path.join('security_attachments', datetime.now().strftime('%Y/%m/%d'))
        file_path = os.path.join(upload_dir, secure_filename)
        
        # Save file
        path = default_storage.save(file_path, ContentFile(file.read()))
        
        return path
    
    def _log_upload_event(self, file, user, file_path, file_hash):
        """Log file upload event for audit"""
        try:
            from .models import SecurityLog
            
            SecurityLog.objects.create(
                user=user,
                security_type='file_upload',
                severity='info',
                ip_address=self._get_client_ip(),
                user_agent=self._get_user_agent(),
                metadata={
                    'filename': file.name,
                    'file_path': file_path,
                    'file_size': file.size,
                    'file_hash': file_hash,
                    'upload_time': datetime.now().isoformat()
                }
            )
        except Exception as e:
            logger.error(f"Error logging upload event: {e}")
    
    def _get_client_ip(self):
        """Get client IP address from request"""
        # Implementation depends on request context
        return '127.0.0.1'
    
    def _get_user_agent(self):
        """Get user agent from request"""
        # Implementation depends on request context
        return 'Security Attachment Upload'


@method_decorator(csrf_exempt, name='dispatch')
class LegacyAttachmentUploadView(View):
    """
    Legacy attachment upload view for backward compatibility
    """
    
    def post(self, request):
        """
        Handle legacy file upload
        """
        try:
            api_view = SecurityAttachmentUploadView()
            api_view.request = request
            response = api_view.post(request)
            
            if response.status_code == 201:
                return JsonResponse(response.data, status=201)
            elif response.status_code == 207:
                return JsonResponse(response.data, status=207)
            else:
                return JsonResponse(response.data, status=400)
                
        except Exception as e:
            logger.error(f"Error in legacy upload view: {e}")
            return JsonResponse({'error': 'Upload failed'}, status=500)


# URL configuration
urlpatterns = [
    path('upload/', SecurityAttachmentUploadView.as_view(), name='security-attachment-upload'),
    path('upload/legacy/', LegacyAttachmentUploadView.as_view(), name='security-attachment-upload-legacy'),
]