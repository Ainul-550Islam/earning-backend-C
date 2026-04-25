"""
Attachment Upload View for Offer Routing System

This module provides file upload functionality for offer routing attachments,
including creative assets, documents, and media files.
"""

import logging
import os
import uuid
from django.conf import settings
from django.core.files.storage import default_storage
from django.http import JsonResponse, HttpResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.core.exceptions import ValidationError
from django.contrib.auth.mixins import LoginRequiredMixin
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated

from .models import OfferRoute, RouteCondition, RouteAction
from .serializers import AttachmentUploadSerializer
from .exceptions import AttachmentUploadError, InvalidFileTypeError
from .utils import validate_file_type, get_file_size, generate_unique_filename

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class AttachmentUploadView(LoginRequiredMixin, View):
    """
    View for handling file uploads for offer routing attachments.
    
    Supports various file types including:
    - Images (jpg, png, gif, webp)
    - Videos (mp4, avi, mov)
    - Documents (pdf, doc, docx, xls, xlsx)
    - Archives (zip, rar, tar, gz)
    """
    
    def post(self, request):
        """Handle file upload POST request."""
        try:
            if 'file' not in request.FILES:
                return JsonResponse({
                    'success': False,
                    'error': 'No file provided'
                }, status=400)
            
            uploaded_file = request.FILES['file']
            attachment_type = request.POST.get('attachment_type', 'general')
            route_id = request.POST.get('route_id')
            
            # Validate file
            validate_file_type(uploaded_file, attachment_type)
            
            # Generate unique filename
            filename = generate_unique_filename(uploaded_file.name)
            
            # Save file
            file_path = self.save_file(uploaded_file, filename, attachment_type)
            
            # Create attachment record if route_id is provided
            attachment_data = {
                'file_path': file_path,
                'original_name': uploaded_file.name,
                'file_size': get_file_size(uploaded_file),
                'file_type': attachment_type,
                'uploaded_by': request.user
            }
            
            if route_id:
                try:
                    route = OfferRoute.objects.get(id=route_id)
                    attachment_data['route'] = route
                except OfferRoute.DoesNotExist:
                    return JsonResponse({
                        'success': False,
                        'error': 'Invalid route ID'
                    }, status=400)
            
            # Save attachment record
            from .models import Attachment  # Import here to avoid circular import
            attachment = Attachment.objects.create(**attachment_data)
            
            return JsonResponse({
                'success': True,
                'attachment_id': attachment.id,
                'file_path': file_path,
                'file_size': attachment.file_size,
                'download_url': attachment.get_download_url()
            })
            
        except ValidationError as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)
        except Exception as e:
            logger.error(f"Error uploading file: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Internal server error'
            }, status=500)
    
    def save_file(self, uploaded_file, filename, attachment_type):
        """Save uploaded file to storage."""
        # Create directory based on attachment type
        upload_dir = os.path.join('attachments', attachment_type)
        file_path = os.path.join(upload_dir, filename)
        
        # Save file using Django's default storage
        saved_path = default_storage.save(file_path, uploaded_file)
        
        return saved_path


class AttachmentAPIView(APIView):
    """
    REST API view for attachment management.
    """
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Upload attachment via REST API."""
        try:
            serializer = AttachmentUploadSerializer(data=request.data)
            if serializer.is_valid():
                attachment = serializer.save()
                return Response({
                    'success': True,
                    'attachment_id': attachment.id,
                    'file_path': attachment.file_path,
                    'download_url': attachment.get_download_url()
                }, status=status.HTTP_201_CREATED)
            else:
                return Response({
                    'success': False,
                    'errors': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            logger.error(f"Error uploading attachment via API: {str(e)}")
            return Response({
                'success': False,
                'error': 'Internal server error'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def get(self, request):
        """List attachments for the current user."""
        try:
            from .models import Attachment
            
            attachments = Attachment.objects.filter(uploaded_by=request.user)
            
            attachment_data = []
            for attachment in attachments:
                attachment_data.append({
                    'id': attachment.id,
                    'file_name': attachment.original_name,
                    'file_size': attachment.file_size,
                    'file_type': attachment.file_type,
                    'upload_date': attachment.created_at,
                    'download_url': attachment.get_download_url()
                })
            
            return Response({
                'success': True,
                'attachments': attachment_data
            })
            
        except Exception as e:
            logger.error(f"Error listing attachments: {str(e)}")
            return Response({
                'success': False,
                'error': 'Internal server error'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@method_decorator(csrf_exempt, name='dispatch')
class AttachmentDownloadView(LoginRequiredMixin, View):
    """
    View for downloading attachments.
    """
    
    def get(self, request, attachment_id):
        """Download attachment file."""
        try:
            from .models import Attachment
            
            attachment = Attachment.objects.get(id=attachment_id)
            
            # Check permissions
            if not self.has_download_permission(request.user, attachment):
                return JsonResponse({
                    'success': False,
                    'error': 'Permission denied'
                }, status=403)
            
            # Serve file
            if default_storage.exists(attachment.file_path):
                file_handle = default_storage.open(attachment.file_path, 'rb')
                response = HttpResponse(
                    file_handle.read(),
                    content_type='application/octet-stream'
                )
                response['Content-Disposition'] = f'attachment; filename="{attachment.original_name}"'
                return response
            else:
                return JsonResponse({
                    'success': False,
                    'error': 'File not found'
                }, status=404)
                
        except Attachment.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Attachment not found'
            }, status=404)
        except Exception as e:
            logger.error(f"Error downloading attachment: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Internal server error'
            }, status=500)
    
    def has_download_permission(self, user, attachment):
        """Check if user has permission to download attachment."""
        # User can download their own attachments
        if attachment.uploaded_by == user:
            return True
        
        # Admin can download any attachment
        if user.is_superuser or user.is_staff:
            return True
        
        # Check if user has access to the associated route
        if attachment.route:
            return attachment.route.has_access_permission(user)
        
        return False


@method_decorator(csrf_exempt, name='dispatch')
class AttachmentDeleteView(LoginRequiredMixin, View):
    """
    View for deleting attachments.
    """
    
    def delete(self, request, attachment_id):
        """Delete attachment."""
        try:
            from .models import Attachment
            
            attachment = Attachment.objects.get(id=attachment_id)
            
            # Check permissions
            if not self.has_delete_permission(request.user, attachment):
                return JsonResponse({
                    'success': False,
                    'error': 'Permission denied'
                }, status=403)
            
            # Delete file from storage
            if default_storage.exists(attachment.file_path):
                default_storage.delete(attachment.file_path)
            
            # Delete attachment record
            attachment.delete()
            
            return JsonResponse({
                'success': True,
                'message': 'Attachment deleted successfully'
            })
            
        except Attachment.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Attachment not found'
            }, status=404)
        except Exception as e:
            logger.error(f"Error deleting attachment: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Internal server error'
            }, status=500)
    
    def has_delete_permission(self, user, attachment):
        """Check if user has permission to delete attachment."""
        # User can delete their own attachments
        if attachment.uploaded_by == user:
            return True
        
        # Admin can delete any attachment
        if user.is_superuser:
            return True
        
        # Check if user has delete permission for the associated route
        if attachment.route:
            return attachment.route.has_delete_permission(user)
        
        return False


# URL patterns for attachment views
urlpatterns = [
    path('upload/', AttachmentUploadView.as_view(), name='attachment_upload'),
    path('api/upload/', AttachmentAPIView.as_view(), name='attachment_api_upload'),
    path('download/<int:attachment_id>/', AttachmentDownloadView.as_view(), name='attachment_download'),
    path('delete/<int:attachment_id>/', AttachmentDeleteView.as_view(), name='attachment_delete'),
]
