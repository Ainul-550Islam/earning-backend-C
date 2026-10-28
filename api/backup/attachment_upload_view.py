"""
Backup Module Attachment Upload Views
Views for handling file attachments in backup operations
"""

import os
import uuid
import hashlib
from datetime import datetime
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import InMemoryUploadedFile, TemporaryUploadedFile
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework import serializers

from .permissions import IsBackupAdmin, CanCreateBackup
from .exceptions import BackupException, ValidationError
from .models import Backup, BackupLog
from .validators import validate_file_upload, validate_backup_attachment


class AttachmentUploadSerializer(serializers.Serializer):
    """Serializer for attachment upload validation"""
    
    file = serializers.FileField(required=True)
    backup_id = serializers.UUIDField(required=False)
    description = serializers.CharField(max_length=500, required=False, allow_blank=True)
    category = serializers.ChoiceField(
        choices=[
            ('config', 'Configuration'),
            ('script', 'Script'),
            ('log', 'Log File'),
            ('metadata', 'Metadata'),
            ('other', 'Other')
        ],
        default='other'
    )
    is_encrypted = serializers.BooleanField(default=False)
    
    def validate_file(self, value):
        """Validate uploaded file"""
        try:
            validate_file_upload(value)
        except ValidationError as e:
            raise serializers.ValidationError(str(e))
        return value


class BackupAttachmentUploadView(APIView):
    """
    View for uploading attachments to backups
    """
    
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [IsAuthenticated, IsBackupAdmin]
    
    def post(self, request, *args, **kwargs):
        """
        Handle file upload for backup attachment
        """
        try:
            serializer = AttachmentUploadSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(
                    {'error': 'Validation failed', 'details': serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get validated data
            uploaded_file = serializer.validated_data['file']
            backup_id = serializer.validated_data.get('backup_id')
            description = serializer.validated_data.get('description', '')
            category = serializer.validated_data.get('category', 'other')
            is_encrypted = serializer.validated_data.get('is_encrypted', False)
            
            # Process the upload
            result = self._process_attachment_upload(
                request.user,
                uploaded_file,
                backup_id,
                description,
                category,
                is_encrypted
            )
            
            return Response(result, status=status.HTTP_201_CREATED)
            
        except BackupException as e:
            return Response(
                {'error': str(e), 'error_code': e.error_code if hasattr(e, 'error_code') else 'UPLOAD_ERROR'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            # Log the error
            BackupLog.log_backup_error(
                action='attachment_upload',
                error_message=str(e),
                error_type=type(e).__name__,
                user=request.user
            )
            
            return Response(
                {'error': 'Internal server error during upload'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _process_attachment_upload(self, user, uploaded_file, backup_id, description, category, is_encrypted):
        """
        Process the attachment upload
        """
        # Generate unique filename
        file_extension = os.path.splitext(uploaded_file.name)[1]
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        
        # Calculate file hash
        file_hash = self._calculate_file_hash(uploaded_file)
        
        # Determine upload path
        upload_date = timezone.now().strftime('%Y/%m/%d')
        upload_path = f"backup_attachments/{upload_date}/{unique_filename}"
        
        # Check for duplicates
        if self._file_exists_by_hash(file_hash):
            raise BackupException("File with same content already exists")
        
        # Upload file to storage
        try:
            # Save the file
            file_path = default_storage.save(upload_path, uploaded_file)
            file_url = default_storage.url(file_path)
            
            # Get file size
            file_size = uploaded_file.size
            
            # Create attachment record (this would be implemented in the model)
            attachment_data = {
                'id': str(uuid.uuid4()),
                'filename': uploaded_file.name,
                'original_filename': uploaded_file.name,
                'file_path': file_path,
                'file_url': file_url,
                'file_size': file_size,
                'file_hash': file_hash,
                'mime_type': uploaded_file.content_type or 'application/octet-stream',
                'category': category,
                'description': description,
                'is_encrypted': is_encrypted,
                'uploaded_by': user.id,
                'uploaded_at': timezone.now().isoformat(),
                'backup_id': str(backup_id) if backup_id else None
            }
            
            # Log the upload
            BackupLog.log_backup_start(
                action='attachment_upload',
                backup_id=backup_id,
                details={
                    'filename': uploaded_file.name,
                    'file_size': file_size,
                    'category': category,
                    'file_hash': file_hash
                },
                user=user
            )
            
            return {
                'success': True,
                'attachment': attachment_data,
                'message': 'File uploaded successfully'
            }
            
        except Exception as e:
            # Clean up if upload failed
            if default_storage.exists(upload_path):
                default_storage.delete(upload_path)
            raise BackupException(f"Failed to save file: {str(e)}")
    
    def _calculate_file_hash(self, uploaded_file):
        """
        Calculate SHA-256 hash of the uploaded file
        """
        hash_sha256 = hashlib.sha256()
        
        # Reset file pointer
        uploaded_file.seek(0)
        
        # Read file in chunks to handle large files
        for chunk in iter(lambda: uploaded_file.read(4096), b""):
            hash_sha256.update(chunk)
        
        # Reset file pointer
        uploaded_file.seek(0)
        
        return hash_sha256.hexdigest()
    
    def _file_exists_by_hash(self, file_hash):
        """
        Check if a file with the same hash already exists
        """
        # This would typically query a database model for attachments
        # For now, return False (implement based on your attachment model)
        return False


class MultipleAttachmentUploadView(APIView):
    """
    View for uploading multiple attachments at once
    """
    
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [IsAuthenticated, IsBackupAdmin]
    
    def post(self, request, *args, **kwargs):
        """
        Handle multiple file uploads
        """
        try:
            files = request.FILES.getlist('files')
            backup_id = request.data.get('backup_id')
            description = request.data.get('description', '')
            category = request.data.get('category', 'other')
            is_encrypted = request.data.get('is_encrypted', 'false').lower() == 'true'
            
            if not files:
                return Response(
                    {'error': 'No files provided'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate number of files
            max_files = getattr(settings, 'BACKUP_MAX_ATTACHMENT_UPLOAD', 10)
            if len(files) > max_files:
                return Response(
                    {'error': f'Maximum {max_files} files allowed per upload'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            results = []
            errors = []
            
            single_upload_view = BackupAttachmentUploadView()
            
            for i, uploaded_file in enumerate(files):
                try:
                    # Create a mock request data for single upload
                    mock_data = {
                        'file': uploaded_file,
                        'backup_id': backup_id,
                        'description': f"{description} (File {i+1})" if description else '',
                        'category': category,
                        'is_encrypted': is_encrypted
                    }
                    
                    # Validate file
                    serializer = AttachmentUploadSerializer(data=mock_data)
                    if not serializer.is_valid():
                        errors.append({
                            'file': uploaded_file.name,
                            'error': 'Validation failed',
                            'details': serializer.errors
                        })
                        continue
                    
                    # Process upload
                    result = single_upload_view._process_attachment_upload(
                        request.user,
                        uploaded_file,
                        backup_id,
                        mock_data['description'],
                        category,
                        is_encrypted
                    )
                    results.append(result)
                    
                except Exception as e:
                    errors.append({
                        'file': uploaded_file.name,
                        'error': str(e)
                    })
            
            return Response({
                'success': len(results) > 0,
                'uploaded_count': len(results),
                'error_count': len(errors),
                'attachments': results,
                'errors': errors
            }, status=status.HTTP_201_CREATED if results else status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            BackupLog.log_backup_error(
                action='multiple_attachment_upload',
                error_message=str(e),
                error_type=type(e).__name__,
                user=request.user
            )
            
            return Response(
                {'error': 'Internal server error during multiple upload'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AttachmentInfoView(APIView):
    """
    View for getting information about uploaded attachments
    """
    
    permission_classes = [IsAuthenticated, IsBackupAdmin]
    
    def get(self, request, attachment_id=None):
        """
        Get attachment information
        """
        try:
            if attachment_id:
                # Get specific attachment info
                attachment = self._get_attachment_by_id(attachment_id)
                if not attachment:
                    return Response(
                        {'error': 'Attachment not found'},
                        status=status.HTTP_404_NOT_FOUND
                    )
                return Response({'attachment': attachment})
            else:
                # List attachments with filters
                backup_id = request.query_params.get('backup_id')
                category = request.query_params.get('category')
                
                attachments = self._list_attachments(
                    backup_id=backup_id,
                    category=category,
                    user=request.user
                )
                
                return Response({
                    'attachments': attachments,
                    'count': len(attachments)
                })
                
        except Exception as e:
            return Response(
                {'error': 'Failed to retrieve attachment information'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _get_attachment_by_id(self, attachment_id):
        """
        Get attachment by ID (implement based on your attachment model)
        """
        # This would typically query your attachment model
        # For now, return None (implement based on your model)
        return None
    
    def _list_attachments(self, backup_id=None, category=None, user=None):
        """
        List attachments with optional filters
        """
        # This would typically query your attachment model with filters
        # For now, return empty list (implement based on your model)
        return []


class AttachmentDeleteView(APIView):
    """
    View for deleting attachments
    """
    
    permission_classes = [IsAuthenticated, IsBackupAdmin]
    
    def delete(self, request, attachment_id):
        """
        Delete an attachment
        """
        try:
            attachment = self._get_attachment_by_id(attachment_id)
            if not attachment:
                return Response(
                    {'error': 'Attachment not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Check if user can delete this attachment
            if not self._can_delete_attachment(request.user, attachment):
                return Response(
                    {'error': 'Permission denied'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Delete file from storage
            if default_storage.exists(attachment['file_path']):
                default_storage.delete(attachment['file_path'])
            
            # Delete attachment record (implement based on your model)
            self._delete_attachment_record(attachment_id)
            
            # Log the deletion
            BackupLog.log_backup_start(
                action='attachment_delete',
                details={
                    'attachment_id': attachment_id,
                    'filename': attachment['filename']
                },
                user=request.user
            )
            
            return Response({
                'success': True,
                'message': 'Attachment deleted successfully'
            })
            
        except Exception as e:
            BackupLog.log_backup_error(
                action='attachment_delete',
                error_message=str(e),
                error_type=type(e).__name__,
                user=request.user
            )
            
            return Response(
                {'error': 'Failed to delete attachment'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _get_attachment_by_id(self, attachment_id):
        """
        Get attachment by ID (implement based on your attachment model)
        """
        return None
    
    def _can_delete_attachment(self, user, attachment):
        """
        Check if user can delete the attachment
        """
        # Superusers can delete any attachment
        if user.is_superuser:
            return True
        
        # Users can delete their own attachments
        if attachment.get('uploaded_by') == user.id:
            return True
        
        return False
    
    def _delete_attachment_record(self, attachment_id):
        """
        Delete attachment record from database (implement based on your model)
        """
        pass


class AttachmentDownloadView(APIView):
    """
    View for downloading attachments
    """
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request, attachment_id):
        """
        Download an attachment
        """
        try:
            attachment = self._get_attachment_by_id(attachment_id)
            if not attachment:
                return Response(
                    {'error': 'Attachment not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Check if user can download this attachment
            if not self._can_download_attachment(request.user, attachment):
                return Response(
                    {'error': 'Permission denied'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Check if file exists
            if not default_storage.exists(attachment['file_path']):
                return Response(
                    {'error': 'File not found on storage'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Log the download
            BackupLog.log_backup_start(
                action='attachment_download',
                details={
                    'attachment_id': attachment_id,
                    'filename': attachment['filename']
                },
                user=request.user
            )
            
            # Serve the file
            return self._serve_file(attachment)
            
        except Exception as e:
            BackupLog.log_backup_error(
                action='attachment_download',
                error_message=str(e),
                error_type=type(e).__name__,
                user=request.user
            )
            
            return Response(
                {'error': 'Failed to download attachment'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _get_attachment_by_id(self, attachment_id):
        """
        Get attachment by ID (implement based on your attachment model)
        """
        return None
    
    def _can_download_attachment(self, user, attachment):
        """
        Check if user can download the attachment
        """
        # Superusers can download any attachment
        if user.is_superuser:
            return True
        
        # Backup admins can download any attachment
        from .permissions import has_backup_group_permission
        if has_backup_group_permission(user, 'backup_admin'):
            return True
        
        # Users can download their own attachments
        if attachment.get('uploaded_by') == user.id:
            return True
        
        # Users can download attachments for backups they have access to
        if attachment.get('backup_id'):
            backup = Backup.objects.filter(id=attachment['backup_id']).first()
            if backup and backup.created_by == user:
                return True
        
        return False
    
    def _serve_file(self, attachment):
        """
        Serve the file for download
        """
        # Open the file
        file_handle = default_storage.open(attachment['file_path'])
        
        # Create response
        response = HttpResponse(
            file_handle,
            content_type=attachment.get('mime_type', 'application/octet-stream')
        )
        
        # Set headers for download
        response['Content-Disposition'] = f'attachment; filename="{attachment["original_filename"]}"'
        response['Content-Length'] = attachment.get('file_size', 0)
        
        return response


# Utility functions for attachment handling
def validate_attachment_file(file_obj, max_size=None):
    """
    Validate attachment file
    
    Args:
        file_obj: Uploaded file object
        max_size: Maximum allowed file size in bytes
        
    Raises:
        ValidationError: If validation fails
    """
    if not file_obj:
        raise ValidationError("No file provided")
    
    # Check file size
    if max_size is None:
        max_size = getattr(settings, 'BACKUP_MAX_ATTACHMENT_SIZE', 100 * 1024 * 1024)  # 100MB default
    
    if file_obj.size > max_size:
        raise ValidationError(f"File size exceeds maximum allowed size of {max_size} bytes")
    
    # Check file extension
    allowed_extensions = getattr(settings, 'BACKUP_ALLOWED_ATTACHMENT_EXTENSIONS', 
                               ['.txt', '.log', '.conf', '.cfg', '.json', '.xml', '.yml', '.yaml', '.sh', '.py', '.sql'])
    
    file_extension = os.path.splitext(file_obj.name)[1].lower()
    if file_extension not in allowed_extensions:
        raise ValidationError(f"File extension '{file_extension}' is not allowed")
    
    # Additional validation can be added here
    validate_file_upload(file_obj)


def get_attachment_storage_path(backup_id=None, category=None):
    """
    Generate storage path for attachment
    
    Args:
        backup_id: Backup ID (optional)
        category: Attachment category (optional)
        
    Returns:
        str: Storage path
    """
    date_path = timezone.now().strftime('%Y/%m/%d')
    
    if backup_id:
        return f"backup_attachments/{date_path}/backup_{backup_id}"
    elif category:
        return f"backup_attachments/{date_path}/{category}"
    else:
        return f"backup_attachments/{date_path}/general"


def cleanup_orphaned_attachments():
    """
    Clean up attachments that are not associated with any backup
    This would typically be run as a management command or periodic task
    """
    # This would query for attachments without associated backups
    # and clean them up from storage
    pass


def get_attachment_statistics():
    """
    Get statistics about attachments
    
    Returns:
        dict: Attachment statistics
    """
    # This would query your attachment model and return statistics
    return {
        'total_attachments': 0,
        'total_size': 0,
        'by_category': {},
        'by_date': {},
        'largest_attachments': []
    }
