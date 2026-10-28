# api/admin_panel/attachment_upload_view.py
"""
Admin Panel Attachment Upload View.
Handles file uploads for: admin reports, KYC documents review,
broadcast attachments, export files, evidence uploads.
"""
import os
import uuid
from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView


ALLOWED_TYPES = {
    'image':    ['image/jpeg', 'image/png', 'image/gif', 'image/webp'],
    'document': ['application/pdf', 'application/msword',
                 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                 'text/csv', 'application/vnd.ms-excel',
                 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'],
    'data':     ['application/json', 'text/plain', 'text/csv'],
}
MAX_SIZE_MB = 25
UPLOAD_BASE = 'admin_panel/uploads'


class AdminAttachmentUploadView(APIView):
    """
    Upload attachments for admin use.
    POST /api/admin-panel/upload/
    Form fields: file, upload_type (image|document|data), context (kyc|report|broadcast)
    """
    parser_classes  = [MultiPartParser, FormParser]
    permission_classes = [IsAdminUser]

    def post(self, request, *args, **kwargs):
        file_obj    = request.FILES.get('file')
        upload_type = request.data.get('upload_type', 'document')
        context     = request.data.get('context', 'general')

        if not file_obj:
            return Response({'error': 'No file provided'}, status=400)

        # Size check
        max_bytes = MAX_SIZE_MB * 1024 * 1024
        if file_obj.size > max_bytes:
            return Response({'error': f'File too large. Max {MAX_SIZE_MB}MB'}, status=400)

        # MIME check
        allowed_mimes = ALLOWED_TYPES.get(upload_type, ALLOWED_TYPES['document'])
        content_type  = file_obj.content_type or ''
        if content_type not in allowed_mimes:
            return Response({
                'error': f'File type not allowed: {content_type}',
                'allowed': allowed_mimes,
            }, status=400)

        # Save file
        ext       = os.path.splitext(file_obj.name)[1].lower()
        filename  = f"{uuid.uuid4().hex}{ext}"
        rel_path  = os.path.join(UPLOAD_BASE, context, timezone.now().strftime('%Y/%m'), filename)
        abs_path  = os.path.join(settings.MEDIA_ROOT, rel_path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)

        with open(abs_path, 'wb+') as dest:
            for chunk in file_obj.chunks():
                dest.write(chunk)

        file_url = f"{settings.MEDIA_URL}{rel_path}"

        # Log
        try:
            from api.admin_panel.models.activity import AdminActivity
            AdminActivity.log(
                actor=request.user,
                action='file_upload',
                changes={
                    'filename': file_obj.name,
                    'size': file_obj.size,
                    'context': context,
                    'upload_type': upload_type,
                },
            )
        except Exception:
            pass

        return Response({
            'success': True,
            'url': file_url,
            'filename': filename,
            'original_name': file_obj.name,
            'size': file_obj.size,
            'content_type': content_type,
            'context': context,
        }, status=201)

    def delete(self, request, *args, **kwargs):
        """Delete an uploaded file."""
        if not request.user.is_superuser:
            return Response({'error': 'Superadmin only'}, status=403)

        file_url = request.data.get('url', '')
        if not file_url or UPLOAD_BASE not in file_url:
            return Response({'error': 'Invalid file URL'}, status=400)

        rel = file_url.replace(settings.MEDIA_URL, '')
        abs_path = os.path.join(settings.MEDIA_ROOT, rel)

        if os.path.exists(abs_path):
            os.remove(abs_path)
            return Response({'success': True, 'deleted': file_url})
        return Response({'error': 'File not found'}, status=404)