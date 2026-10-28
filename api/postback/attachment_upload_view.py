"""
attachment_upload_view.py – Attachment upload view for postback module.

Provides file upload functionality for postback attachments and documents.
Handles secure file uploads with validation, storage, and metadata tracking.
"""
import logging
import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from django.conf import settings
from django.core.files.storage import default_storage
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views import View
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import PostbackLog, NetworkPostbackConfig
from .exceptions import PostbackException
from .permissions import IsPostbackAdmin

logger = logging.getLogger(__name__)


class AttachmentUploadView(APIView):
    """
    View for handling file uploads related to postback processing.
    
    Supports:
    - Multi-file uploads
    - File type validation
    - Size limitations
    - Secure storage
    - Metadata tracking
    """
    
    permission_classes = [IsAuthenticated, IsPostbackAdmin]
    
    # Allowed file extensions
    ALLOWED_EXTENSIONS = {
        'image': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'],
        'document': ['.pdf', '.doc', '.docx', '.txt', '.rtf'],
        'spreadsheet': ['.xls', '.xlsx', '.csv'],
        'archive': ['.zip', '.rar', '.7z', '.tar', '.gz'],
    }
    
    # Maximum file sizes (in bytes)
    MAX_FILE_SIZES = {
        'image': 10 * 1024 * 1024,      # 10MB
        'document': 50 * 1024 * 1024,   # 50MB
        'spreadsheet': 20 * 1024 * 1024, # 20MB
        'archive': 100 * 1024 * 1024,   # 100MB
    }
    
    def post(self, request, *args, **kwargs):
        """
        Handle file upload requests.
        
        Expected format:
        - multipart/form-data
        - files: List of files to upload
        - postback_id: Optional postback log ID to associate with
        - category: File category (image, document, spreadsheet, archive)
        """
        try:
            files = request.FILES.getlist('files')
            postback_id = request.data.get('postback_id')
            category = request.data.get('category', 'document')
            
            if not files:
                return Response(
                    {'error': 'No files provided'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate category
            if category not in self.ALLOWED_EXTENSIONS:
                return Response(
                    {'error': f'Invalid category. Must be one of: {list(self.ALLOWED_EXTENSIONS.keys())}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate postback_id if provided
            postback = None
            if postback_id:
                try:
                    postback = get_object_or_404(PostbackLog, id=postback_id)
                except Exception:
                    return Response(
                        {'error': 'Invalid postback_id'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            uploaded_files = []
            errors = []
            
            for file in files:
                try:
                    result = self._handle_single_file(file, category, postback)
                    uploaded_files.append(result)
                except Exception as e:
                    errors.append({
                        'filename': file.name,
                        'error': str(e)
                    })
                    logger.error(f"Failed to upload file {file.name}: {str(e)}")
            
            response_data = {
                'uploaded_files': uploaded_files,
                'errors': errors,
                'total_uploaded': len(uploaded_files),
                'total_errors': len(errors)
            }
            
            if errors and not uploaded_files:
                return Response(
                    response_data,
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            return Response(response_data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Upload request failed: {str(e)}")
            return Response(
                {'error': 'Upload failed due to server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _handle_single_file(self, file, category, postback=None) -> Dict:
        """Handle upload of a single file."""
        # Validate file
        self._validate_file(file, category)
        
        # Generate unique filename
        file_extension = os.path.splitext(file.name)[1].lower()
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        
        # Create upload path
        upload_date = datetime.now().strftime('%Y/%m/%d')
        upload_path = f"postback_attachments/{upload_date}/{unique_filename}"
        
        # Save file
        saved_path = default_storage.save(upload_path, file)
        
        # Get file URL
        file_url = default_storage.url(saved_path)
        
        # Create metadata
        metadata = {
            'id': str(uuid.uuid4()),
            'original_filename': file.name,
            'saved_filename': unique_filename,
            'file_path': saved_path,
            'file_url': file_url,
            'file_size': file.size,
            'file_type': file.content_type,
            'category': category,
            'upload_date': datetime.now().isoformat(),
            'postback_id': str(postback.id) if postback else None,
        }
        
        # Store metadata (could be saved to database in future)
        self._store_file_metadata(metadata)
        
        logger.info(f"Successfully uploaded file: {file.name} -> {saved_path}")
        
        return metadata
    
    def _validate_file(self, file, category):
        """Validate file before upload."""
        # Check file extension
        file_extension = os.path.splitext(file.name)[1].lower()
        allowed_extensions = self.ALLOWED_EXTENSIONS[category]
        
        if file_extension not in allowed_extensions:
            raise ValueError(
                f"File extension '{file_extension}' not allowed for category '{category}'. "
                f"Allowed extensions: {allowed_extensions}"
            )
        
        # Check file size
        max_size = self.MAX_FILE_SIZES[category]
        if file.size > max_size:
            raise ValueError(
                f"File size {file.size} bytes exceeds maximum allowed size {max_size} bytes "
                f"for category '{category}'"
            )
        
        # Additional validation based on file type
        if category == 'image':
            self._validate_image_file(file)
        elif category == 'document':
            self._validate_document_file(file)
    
    def _validate_image_file(self, file):
        """Validate image file."""
        from PIL import Image
        
        try:
            # Try to open the image to verify it's valid
            image = Image.open(file)
            image.verify()
            
            # Reset file pointer
            file.seek(0)
            
            # Check image dimensions (optional)
            if hasattr(settings, 'POSTBACK_MAX_IMAGE_DIMENSIONS'):
                max_width, max_height = settings.POSTBACK_MAX_IMAGE_DIMENSIONS
                if image.width > max_width or image.height > max_height:
                    raise ValueError(
                        f"Image dimensions {image.width}x{image.height} exceed maximum "
                        f"allowed dimensions {max_width}x{max_height}"
                    )
        
        except Exception as e:
            raise ValueError(f"Invalid image file: {str(e)}")
    
    def _validate_document_file(self, file):
        """Validate document file."""
        # Basic validation for document files
        if file.content_type not in [
            'application/pdf',
            'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'text/plain',
            'application/rtf',
        ]:
            # Try to detect file type by content
            content_type = self._detect_content_type(file)
            if content_type not in [
                'application/pdf',
                'application/msword',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'text/plain',
                'application/rtf',
            ]:
                raise ValueError(f"Invalid document file type: {file.content_type}")
    
    def _detect_content_type(self, file):
        """Detect file content type."""
        import magic
        
        try:
            # Read first few bytes to detect content type
            file.seek(0)
            content = file.read(1024)
            file.seek(0)
            
            mime = magic.Magic(mime=True)
            return mime.from_buffer(content)
        
        except ImportError:
            # Fallback if python-magic is not available
            return file.content_type
    
    def _store_file_metadata(self, metadata):
        """Store file metadata."""
        # For now, just log the metadata
        # In future, this could be stored in a database model
        logger.info(f"File metadata stored: {metadata['id']} - {metadata['original_filename']}")
        
        # Could implement database storage here:
        # PostbackAttachment.objects.create(**metadata)


@method_decorator(csrf_exempt, name='dispatch')
class AttachmentDownloadView(View):
    """View for downloading uploaded attachments."""
    
    def get(self, request, file_id):
        """Handle file download request."""
        try:
            # Retrieve file metadata (placeholder implementation)
            file_metadata = self._get_file_metadata(file_id)
            
            if not file_metadata:
                return HttpResponse(
                    'File not found',
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Check permissions
            if not self._has_download_permission(request, file_metadata):
                return HttpResponse(
                    'Permission denied',
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Serve file
            file_path = file_metadata['file_path']
            if default_storage.exists(file_path):
                file_obj = default_storage.open(file_path, 'rb')
                response = HttpResponse(
                    file_obj,
                    content_type=file_metadata['file_type']
                )
                response['Content-Disposition'] = f'attachment; filename="{file_metadata["original_filename"]}"'
                response['Content-Length'] = file_metadata['file_size']
                return response
            else:
                return HttpResponse(
                    'File not found on storage',
                    status=status.HTTP_404_NOT_FOUND
                )
        
        except Exception as e:
            logger.error(f"Download failed for file {file_id}: {str(e)}")
            return HttpResponse(
                'Download failed',
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _get_file_metadata(self, file_id):
        """Retrieve file metadata."""
        # Placeholder implementation
        # In future, this would query the database
        return None
    
    def _has_download_permission(self, request, file_metadata):
        """Check if user has permission to download file."""
        # Placeholder implementation
        # In future, this would check user permissions
        return True


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsPostbackAdmin])
def attachment_list_view(request):
    """
    API view to list uploaded attachments.
    
    Query parameters:
    - postback_id: Filter by postback ID
    - category: Filter by file category
    - date: Filter by upload date (YYYY-MM-DD)
    """
    try:
        postback_id = request.query_params.get('postback_id')
        category = request.query_params.get('category')
        date_filter = request.query_params.get('date')
        
        # Placeholder implementation
        # In future, this would query the database
        attachments = []
        
        return Response({
            'attachments': attachments,
            'total_count': len(attachments),
            'filters': {
                'postback_id': postback_id,
                'category': category,
                'date': date_filter
            }
        })
    
    except Exception as e:
        logger.error(f"Failed to list attachments: {str(e)}")
        return Response(
            {'error': 'Failed to retrieve attachments'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['DELETE'])
@permission_classes([IsAuthenticated, IsPostbackAdmin])
def attachment_delete_view(request, file_id):
    """
    API view to delete an uploaded attachment.
    """
    try:
        # Retrieve file metadata
        file_metadata = _get_file_metadata(file_id)
        
        if not file_metadata:
            return Response(
                {'error': 'File not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Delete file from storage
        file_path = file_metadata['file_path']
        if default_storage.exists(file_path):
            default_storage.delete(file_path)
        
        # Delete metadata (placeholder)
        # PostbackAttachment.objects.filter(id=file_id).delete()
        
        logger.info(f"Deleted attachment: {file_id}")
        
        return Response({'message': 'File deleted successfully'})
    
    except Exception as e:
        logger.error(f"Failed to delete attachment {file_id}: {str(e)}")
        return Response(
            {'error': 'Failed to delete file'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


def _get_file_metadata(file_id):
    """Helper function to retrieve file metadata."""
    # Placeholder implementation
    return None


# URL configuration for this module
urlpatterns = [
    # These would be included in the main urls.py
    # path('attachments/upload/', AttachmentUploadView.as_view(), name='attachment-upload'),
    # path('attachments/download/<uuid:file_id>/', AttachmentDownloadView.as_view(), name='attachment-download'),
    # path('attachments/', attachment_list_view, name='attachment-list'),
    # path('attachments/<uuid:file_id>/delete/', attachment_delete_view, name='attachment-delete'),
]
