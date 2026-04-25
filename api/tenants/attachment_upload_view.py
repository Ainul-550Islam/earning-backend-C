"""
Tenant Attachment Upload View - Comprehensive File Management

This module handles file uploads for tenants with security validation,
storage management, and proper access control.
"""

import os
import uuid
import hashlib
from datetime import datetime
from django.conf import settings
from django.core.files.storage import default_storage
from django.http import JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser

from .models_improved import Tenant
from .permissions_improved import IsTenantOwner
from .services_improved import tenant_security_service


class TenantAttachmentUploadView(APIView):
    """
    View for handling tenant file uploads with comprehensive security.
    
    Supports multiple file types, validation, and secure storage.
    """
    
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [IsAuthenticated, IsTenantOwner]
    
    # Allowed file types and their max sizes (in MB)
    ALLOWED_FILE_TYPES = {
        'image': ['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg'],
        'document': ['pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx'],
        'archive': ['zip', 'rar', '7z', 'tar', 'gz'],
        'video': ['mp4', 'avi', 'mov', 'wmv', 'flv'],
        'audio': ['mp3', 'wav', 'ogg', 'aac'],
    }
    
    MAX_FILE_SIZES = {
        'image': 10,  # 10MB
        'document': 50,  # 50MB
        'archive': 100,  # 100MB
        'video': 500,  # 500MB
        'audio': 50,  # 50MB
    }
    
    def post(self, request, *args, **kwargs):
        """
        Handle file upload with comprehensive validation.
        """
        try:
            # Get tenant from request
            tenant = getattr(request, 'tenant', None)
            if not tenant:
                return Response({
                    'error': 'Tenant not found',
                    'message': 'No tenant context available'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Check rate limiting
            if not tenant_security_service.check_rate_limit(
                tenant, 'file_upload', request.META.get('REMOTE_ADDR'), 10
            ):
                return Response({
                    'error': 'Rate limit exceeded',
                    'message': 'Too many upload attempts. Please try again later.'
                }, status=status.HTTP_429_TOO_MANY_REQUESTS)
            
            # Get uploaded file
            if 'file' not in request.FILES:
                return Response({
                    'error': 'No file provided',
                    'message': 'Please select a file to upload'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            uploaded_file = request.FILES['file']
            
            # Validate file
            validation_result = self._validate_file(uploaded_file)
            if not validation_result['valid']:
                return Response({
                    'error': 'File validation failed',
                    'message': validation_result['error'],
                    'details': validation_result.get('details', {})
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Generate secure filename
            secure_filename = self._generate_secure_filename(uploaded_file)
            
            # Create tenant-specific upload path
            upload_path = self._get_upload_path(tenant, validation_result['file_type'])
            
            # Save file
            file_path = default_storage.save(os.path.join(upload_path, secure_filename), uploaded_file)
            
            # Generate file metadata
            file_metadata = self._generate_file_metadata(uploaded_file, file_path, validation_result)
            
            # Log upload
            tenant.audit_log(
                action='file_uploaded',
                details={
                    'filename': uploaded_file.name,
                    'file_path': file_path,
                    'file_size': uploaded_file.size,
                    'file_type': validation_result['file_type'],
                    'content_type': uploaded_file.content_type,
                },
                user=request.user
            )
            
            return Response({
                'success': True,
                'message': 'File uploaded successfully',
                'data': {
                    'file_id': file_metadata['file_id'],
                    'filename': uploaded_file.name,
                    'file_path': file_path,
                    'file_url': file_metadata['file_url'],
                    'file_size': uploaded_file.size,
                    'file_type': validation_result['file_type'],
                    'content_type': uploaded_file.content_type,
                    'uploaded_at': file_metadata['uploaded_at'],
                    'checksum': file_metadata['checksum'],
                }
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response({
                'error': 'Upload failed',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _validate_file(self, uploaded_file):
        """
        Validate uploaded file for security and compliance.
        """
        validation_result = {'valid': True, 'error': None, 'file_type': None}
        
        # Check file size
        max_size = self._get_max_file_size(uploaded_file)
        if uploaded_file.size > max_size * 1024 * 1024:  # Convert MB to bytes
            validation_result['valid'] = False
            validation_result['error'] = f'File size exceeds maximum allowed size of {max_size}MB'
            validation_result['details'] = {
                'file_size': uploaded_file.size,
                'max_size': max_size * 1024 * 1024
            }
            return validation_result
        
        # Check file extension
        file_extension = self._get_file_extension(uploaded_file.name)
        file_type = self._get_file_type(file_extension)
        
        if not file_type:
            validation_result['valid'] = False
            validation_result['error'] = 'File type not allowed'
            validation_result['details'] = {
                'file_extension': file_extension,
                'allowed_types': list(self.ALLOWED_FILE_TYPES.keys())
            }
            return validation_result
        
        validation_result['file_type'] = file_type
        
        # Additional validation based on file type
        if file_type == 'image':
            image_validation = self._validate_image_file(uploaded_file)
            if not image_validation['valid']:
                return image_validation
        
        elif file_type == 'document':
            document_validation = self._validate_document_file(uploaded_file)
            if not document_validation['valid']:
                return document_validation
        
        # Check for malicious content
        security_validation = self._validate_file_security(uploaded_file)
        if not security_validation['valid']:
            return security_validation
        
        return validation_result
    
    def _get_file_extension(self, filename):
        """Get file extension from filename."""
        return filename.lower().split('.')[-1] if '.' in filename else ''
    
    def _get_file_type(self, extension):
        """Determine file type from extension."""
        for file_type, extensions in self.ALLOWED_FILE_TYPES.items():
            if extension in extensions:
                return file_type
        return None
    
    def _get_max_file_size(self, uploaded_file):
        """Get maximum allowed file size for the file type."""
        file_type = self._get_file_type(self._get_file_extension(uploaded_file.name))
        return self.MAX_FILE_SIZES.get(file_type, 10)  # Default 10MB
    
    def _validate_image_file(self, uploaded_file):
        """Validate image file for security and format."""
        validation_result = {'valid': True, 'error': None}
        
        try:
            from PIL import Image
            from io import BytesIO
            
            # Open image to verify it's valid
            image = Image.open(uploaded_file)
            
            # Check image dimensions
            max_width = getattr(settings, 'MAX_IMAGE_WIDTH', 5000)
            max_height = getattr(settings, 'MAX_IMAGE_HEIGHT', 5000)
            
            if image.width > max_width or image.height > max_height:
                validation_result['valid'] = False
                validation_result['error'] = f'Image dimensions exceed maximum allowed size of {max_width}x{max_height}'
                validation_result['details'] = {
                    'width': image.width,
                    'height': image.height,
                    'max_width': max_width,
                    'max_height': max_height
                }
                return validation_result
            
            # Check for embedded malicious content
            image.verify()
            
        except Exception as e:
            validation_result['valid'] = False
            validation_result['error'] = 'Invalid image file'
            validation_result['details'] = {'error_details': str(e)}
        
        return validation_result
    
    def _validate_document_file(self, uploaded_file):
        """Validate document file for security."""
        validation_result = {'valid': True, 'error': None}
        
        try:
            # Read first few bytes to check for malicious content
            file_content = uploaded_file.read(1024)
            uploaded_file.seek(0)
            
            # Check for suspicious patterns
            suspicious_patterns = [
                b'<script',
                b'javascript:',
                b'vbscript:',
                b'data:text/html',
                b'<?php',
                b'<%',
            ]
            
            for pattern in suspicious_patterns:
                if pattern in file_content.lower():
                    validation_result['valid'] = False
                    validation_result['error'] = 'File contains potentially malicious content'
                    validation_result['details'] = {'suspicious_pattern': pattern.decode()}
                    return validation_result
        
        except Exception as e:
            validation_result['valid'] = False
            validation_result['error'] = 'Failed to validate document file'
            validation_result['details'] = {'error_details': str(e)}
        
        return validation_result
    
    def _validate_file_security(self, uploaded_file):
        """Validate file for security threats."""
        validation_result = {'valid': True, 'error': None}
        
        try:
            # Check file signature
            file_content = uploaded_file.read(512)
            uploaded_file.seek(0)
            
            # Common executable signatures to block
            executable_signatures = [
                b'MZ',  # Windows executable
                b'\x7fELF',  # Linux executable
                b'\xca\xfe\xba\xbe',  # Java class
                b'\xfe\xed\xfa\xce',  # Mach-O binary (macOS)
                b'\xfe\xed\xfa\xcf',  # Mach-O binary (macOS)
            ]
            
            for signature in executable_signatures:
                if file_content.startswith(signature):
                    validation_result['valid'] = False
                    validation_result['error'] = 'Executable files are not allowed'
                    validation_result['details'] = {'signature': signature.hex()}
                    return validation_result
        
        except Exception as e:
            validation_result['valid'] = False
            validation_result['error'] = 'Failed to validate file security'
            validation_result['details'] = {'error_details': str(e)}
        
        return validation_result
    
    def _generate_secure_filename(self, uploaded_file):
        """Generate secure filename to prevent conflicts and attacks."""
        original_extension = self._get_file_extension(uploaded_file.name)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        random_uuid = uuid.uuid4().hex[:8]
        
        # Sanitize original filename
        original_name = uploaded_file.name.replace(' ', '_').replace('.', '_')
        original_name = ''.join(c for c in original_name if c.isalnum() or c == '_')
        
        secure_filename = f"{original_name}_{timestamp}_{random_uuid}.{original_extension}"
        return secure_filename
    
    def _get_upload_path(self, tenant, file_type):
        """Generate secure upload path for tenant."""
        current_date = datetime.now().strftime('%Y/%m/%d')
        return f"tenants/{tenant.id}/{file_type}/{current_date}"
    
    def _generate_file_metadata(self, uploaded_file, file_path, validation_result):
        """Generate comprehensive file metadata."""
        # Generate file checksum
        file_hash = hashlib.sha256()
        for chunk in uploaded_file.chunks():
            file_hash.update(chunk)
        checksum = file_hash.hexdigest()
        
        # Reset file pointer
        uploaded_file.seek(0)
        
        # Generate file URL
        file_url = default_storage.url(file_path)
        
        return {
            'file_id': uuid.uuid4().hex,
            'file_path': file_path,
            'file_url': file_url,
            'uploaded_at': datetime.now().isoformat(),
            'checksum': checksum,
            'file_type': validation_result['file_type'],
        }


class TenantAttachmentListView(APIView):
    """
    View for listing tenant attachments with filtering and pagination.
    """
    
    permission_classes = [IsAuthenticated, IsTenantOwner]
    
    def get(self, request, *args, **kwargs):
        """List tenant attachments with filtering."""
        try:
            tenant = getattr(request, 'tenant', None)
            if not tenant:
                return Response({
                    'error': 'Tenant not found',
                    'message': 'No tenant context available'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get query parameters
            file_type = request.query_params.get('file_type')
            date_from = request.query_params.get('date_from')
            date_to = request.query_params.get('date_to')
            page = int(request.query_params.get('page', 1))
            page_size = int(request.query_params.get('page_size', 20))
            
            # Query audit logs for file uploads
            queryset = TenantAuditLog.objects.filter(
                tenant=tenant,
                action='file_uploaded'
            ).order_by('-created_at')
            
            # Apply filters
            if file_type:
                queryset = queryset.filter(details__file_type=file_type)
            
            if date_from:
                queryset = queryset.filter(created_at__date__gte=date_from)
            
            if date_to:
                queryset = queryset.filter(created_at__date__lte=date_to)
            
            # Paginate
            total_count = queryset.count()
            start = (page - 1) * page_size
            end = start + page_size
            files = queryset[start:end]
            
            # Format response
            file_list = []
            for file_log in files:
                details = file_log.details
                file_list.append({
                    'file_id': details.get('checksum', ''),  # Use checksum as ID
                    'filename': details.get('filename', ''),
                    'file_path': details.get('file_path', ''),
                    'file_size': details.get('file_size', 0),
                    'file_type': details.get('file_type', ''),
                    'content_type': details.get('content_type', ''),
                    'uploaded_at': file_log.created_at.isoformat(),
                    'uploaded_by': file_log.user_email if file_log.user_email else 'Unknown',
                })
            
            return Response({
                'success': True,
                'data': {
                    'files': file_list,
                    'pagination': {
                        'page': page,
                        'page_size': page_size,
                        'total_count': total_count,
                        'total_pages': (total_count + page_size - 1) // page_size,
                    }
                }
            })
            
        except Exception as e:
            return Response({
                'error': 'Failed to list files',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TenantAttachmentDeleteView(APIView):
    """
    View for deleting tenant attachments with proper cleanup.
    """
    
    permission_classes = [IsAuthenticated, IsTenantOwner]
    
    def delete(self, request, file_id, *args, **kwargs):
        """Delete tenant attachment with proper cleanup."""
        try:
            tenant = getattr(request, 'tenant', None)
            if not tenant:
                return Response({
                    'error': 'Tenant not found',
                    'message': 'No tenant context available'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Find file in audit logs
            file_log = TenantAuditLog.objects.filter(
                tenant=tenant,
                action='file_uploaded',
                details__checksum=file_id
            ).first()
            
            if not file_log:
                return Response({
                    'error': 'File not found',
                    'message': 'The specified file does not exist'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Delete file from storage
            file_path = file_log.details.get('file_path')
            if file_path and default_storage.exists(file_path):
                default_storage.delete(file_path)
            
            # Log deletion
            tenant.audit_log(
                action='file_deleted',
                details={
                    'filename': file_log.details.get('filename', ''),
                    'file_path': file_path,
                    'file_id': file_id,
                    'deleted_by': request.user.email,
                },
                user=request.user
            )
            
            return Response({
                'success': True,
                'message': 'File deleted successfully'
            })
            
        except Exception as e:
            return Response({
                'error': 'Failed to delete file',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
