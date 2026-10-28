# api/cms/attachment_upload_view.py
"""File/image attachment upload for CMS content blocks and blog posts."""
import os
import uuid
import logging
import mimetypes
from django.conf import settings
from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework.parsers import MultiPartParser
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.authentication import JWTAuthentication
from .constants import ATTACHMENT_MAX_SIZE_MB, ATTACHMENT_ALLOWED_TYPES

logger = logging.getLogger(__name__)

MAX_BYTES = ATTACHMENT_MAX_SIZE_MB * 1024 * 1024


class AttachmentUploadView(APIView):
    """
    Upload file/image attachments for CMS content.
    POST /api/cms/attachments/upload/
    Accepts: images, PDFs, videos (see ATTACHMENT_ALLOWED_TYPES)
    Returns: { url, filename, size, content_type, uuid }
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser]

    def post(self, request, *args, **kwargs):
        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response({'error': 'No file provided'}, status=400)

        # Size check
        if file_obj.size > MAX_BYTES:
            return Response({
                'error': f'File too large. Max {ATTACHMENT_MAX_SIZE_MB}MB'
            }, status=400)

        # MIME type check
        content_type = file_obj.content_type or mimetypes.guess_type(file_obj.name)[0] or ''
        if content_type not in ATTACHMENT_ALLOWED_TYPES:
            return Response({
                'error': f'File type not allowed: {content_type}',
                'allowed': ATTACHMENT_ALLOWED_TYPES,
            }, status=400)

        # Generate safe filename
        ext = os.path.splitext(file_obj.name)[1].lower()
        safe_name = f"{uuid.uuid4().hex}{ext}"
        upload_folder = AttachmentUploadView._get_upload_folder(content_type)
        relative_path = f"{upload_folder}/{safe_name}"

        # Save file
        try:
            full_path = os.path.join(settings.MEDIA_ROOT, relative_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, 'wb') as f:
                for chunk in file_obj.chunks():
                    f.write(chunk)
        except Exception as e:
            logger.error(f"[Upload] File save failed: {e}")
            return Response({'error': 'Upload failed'}, status=500)

        # Build URL
        media_url = getattr(settings, 'MEDIA_URL', '/media/')
        file_url = f"{media_url}{relative_path}"

        # Log upload
        logger.info(
            f"[Upload] {request.user.username} uploaded {file_obj.name} "
            f"({file_obj.size} bytes) → {relative_path}"
        )

        return Response({
            'success': True,
            'url': file_url,
            'filename': file_obj.name,
            'safe_name': safe_name,
            'size': file_obj.size,
            'size_kb': round(file_obj.size / 1024, 1),
            'content_type': content_type,
            'uuid': safe_name.split('.')[0],
        }, status=status.HTTP_201_CREATED)

    @staticmethod
    def _get_upload_folder(content_type: str) -> str:
        if content_type.startswith('image/'):
            return 'cms/images'
        elif content_type.startswith('video/'):
            return 'cms/videos'
        elif content_type == 'application/pdf':
            return 'cms/documents'
        else:
            return 'cms/files'


class BulkAttachmentUploadView(APIView):
    """Upload multiple files at once. Max 5 files per request."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser]
    MAX_FILES = 5

    def post(self, request, *args, **kwargs):
        files = request.FILES.getlist('files')
        if not files:
            return Response({'error': 'No files provided'}, status=400)
        if len(files) > self.MAX_FILES:
            return Response({'error': f'Max {self.MAX_FILES} files per upload'}, status=400)

        results = []
        errors = []
        for file_obj in files:
            # Process each file via AttachmentUploadView logic
            content_type = file_obj.content_type or ''
            if file_obj.size > MAX_BYTES:
                errors.append({'filename': file_obj.name, 'error': 'Too large'})
                continue
            if content_type not in ATTACHMENT_ALLOWED_TYPES:
                errors.append({'filename': file_obj.name, 'error': 'Type not allowed'})
                continue
            ext = os.path.splitext(file_obj.name)[1].lower()
            safe_name = f"{uuid.uuid4().hex}{ext}"
            folder = AttachmentUploadView._get_upload_folder(content_type)
            relative = f"{folder}/{safe_name}"
            try:
                full = os.path.join(getattr(settings, 'MEDIA_ROOT', '/tmp'), relative)
                os.makedirs(os.path.dirname(full), exist_ok=True)
                with open(full, 'wb') as f:
                    for chunk in file_obj.chunks():
                        f.write(chunk)
                media_url = getattr(settings, 'MEDIA_URL', '/media/')
                results.append({
                    'filename': file_obj.name,
                    'url': f"{media_url}{relative}",
                    'size': file_obj.size,
                    'content_type': content_type,
                })
            except Exception as e:
                errors.append({'filename': file_obj.name, 'error': str(e)})

        return Response({
            'uploaded': results,
            'errors': errors,
            'count': len(results),
        }, status=207 if errors else 201)
