# engagement/attachment_upload_view.py
"""
File attachment upload handling for engagement system.
Supports images, documents, and other media files for user profiles, achievements, etc.
"""
import os
import uuid
from django.conf import settings
from django.core.files.storage import default_storage
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from ..utils.validators import validate_file_type, validate_file_size
from ..utils.helpers import get_file_extension, generate_safe_filename


@csrf_exempt
@require_http_methods(["POST"])
def upload_attachment(request):
    """
    Generic file upload endpoint for engagement attachments.
    Endpoint: /engagement/upload/attachment/
    
    Supports: images, documents, achievement badges, profile pictures, etc.
    """
    try:
        if 'file' not in request.FILES:
            return JsonResponse({
                'error': 'No file provided'
            }, status=400)
        
        file = request.FILES['file']
        attachment_type = request.POST.get('type', 'general')  # general, profile, badge, etc.
        
        # Validate file
        if not validate_file_type(file, attachment_type):
            return JsonResponse({
                'error': f'Invalid file type for {attachment_type}'
            }, status=400)
        
        if not validate_file_size(file, attachment_type):
            return JsonResponse({
                'error': f'File too large for {attachment_type}'
            }, status=400)
        
        # Generate safe filename
        file_extension = get_file_extension(file.name)
        safe_filename = generate_safe_filename(file.name)
        unique_filename = f"{uuid.uuid4()}_{safe_filename}"
        
        # Determine upload path
        upload_path = f"engagement/attachments/{attachment_type}/{unique_filename}"
        
        # Save file
        file_path = default_storage.save(upload_path, file)
        file_url = default_storage.url(file_path)
        
        return JsonResponse({
            'success': True,
            'file_url': file_url,
            'file_path': file_path,
            'filename': safe_filename,
            'size': file.size,
            'type': attachment_type
        })
        
    except Exception as exc:
        return JsonResponse({
            'error': str(exc)
        }, status=500)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def upload_profile_picture(request):
    """
    Upload user profile picture.
    Endpoint: /engagement/upload/profile-picture/
    """
    try:
        if 'file' not in request.FILES:
            return Response({
                'error': 'No file provided'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        file = request.FILES['file']
        
        # Validate profile picture
        if not validate_file_type(file, 'profile'):
            return Response({
                'error': 'Invalid image format. Allowed: jpg, jpeg, png, gif'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not validate_file_size(file, 'profile'):
            return Response({
                'error': 'Profile picture too large. Max 5MB'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Delete old profile picture if exists
        user = request.user
        if hasattr(user, 'profile_picture') and user.profile_picture:
            try:
                default_storage.delete(user.profile_picture.name)
            except:
                pass
        
        # Save new profile picture
        file_extension = get_file_extension(file.name)
        unique_filename = f"profile_{user.pk}_{uuid.uuid4()}.{file_extension}"
        upload_path = f"engagement/profiles/{unique_filename}"
        
        file_path = default_storage.save(upload_path, file)
        file_url = default_storage.url(file_path)
        
        # Update user profile
        user.profile_picture = file_path
        user.save(update_fields=['profile_picture'])
        
        return Response({
            'success': True,
            'profile_picture_url': file_url,
            'message': 'Profile picture updated successfully'
        })
        
    except Exception as exc:
        return Response({
            'error': str(exc)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_attachment(request):
    """
    Delete an uploaded attachment.
    Endpoint: /engagement/upload/delete/
    """
    try:
        file_path = request.data.get('file_path')
        if not file_path:
            return Response({
                'error': 'file_path is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if user owns this file (basic security)
        if not file_path.startswith('engagement/attachments/') and not file_path.startswith('engagement/profiles/'):
            return Response({
                'error': 'Invalid file path'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Delete file
        try:
            default_storage.delete(file_path)
        except FileNotFoundError:
            return Response({
                'error': 'File not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        return Response({
            'success': True,
            'message': 'File deleted successfully'
        })
        
    except Exception as exc:
        return Response({
            'error': str(exc)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
