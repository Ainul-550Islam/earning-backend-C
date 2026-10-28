# api/referral/attachment_upload_view.py
# File attachment handling for referral campaigns/invitations
# Upload referral banners, custom landing pages assets, invite cards
# ============================================================

import os
import uuid
import logging
from django.conf import settings
from django.core.files.storage import default_storage
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework import status

logger = logging.getLogger(__name__)

ALLOWED_TYPES = {
    'image': ['image/jpeg', 'image/png', 'image/gif', 'image/webp'],
    'document': ['application/pdf', 'text/plain'],
}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB


class ReferralAttachmentUploadView(APIView):
    """
    POST /referral/upload/
    Upload attachments for referral invitations and campaigns.

    Supported types:
    - Campaign banner images (for email invites)
    - QR code branding assets
    - Custom referral card images
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, *args, **kwargs):
        file = request.FILES.get('file')
        if not file:
            return Response({'error': 'No file provided.'}, status=400)

        # Size check
        if file.size > MAX_FILE_SIZE:
            return Response(
                {'error': f'File too large. Max size: {MAX_FILE_SIZE // 1024 // 1024}MB'},
                status=400
            )

        # Type check
        content_type = file.content_type or ''
        allowed = ALLOWED_TYPES['image'] + ALLOWED_TYPES['document']
        if content_type not in allowed:
            return Response(
                {'error': f'File type not allowed. Allowed: {allowed}'},
                status=400
            )

        # Generate safe filename
        ext = os.path.splitext(file.name)[1].lower()
        filename = f"referral/uploads/{request.user.id}/{uuid.uuid4().hex}{ext}"

        try:
            saved_path = default_storage.save(filename, file)
            file_url = default_storage.url(saved_path)

            return Response({
                'success': True,
                'file_url': file_url,
                'file_name': file.name,
                'file_size': file.size,
                'content_type': content_type,
                'path': saved_path,
            })
        except Exception as e:
            logger.error(f'[AttachmentUpload] Upload failed: {e}')
            return Response({'error': 'Upload failed.'}, status=500)

    def delete(self, request, *args, **kwargs):
        """DELETE /referral/upload/ — Delete uploaded file."""
        path = request.data.get('path', '')
        if not path:
            return Response({'error': 'No path provided.'}, status=400)

        # Security: only allow deletion of user's own files
        if f'referral/uploads/{request.user.id}/' not in path:
            return Response({'error': 'Permission denied.'}, status=403)

        try:
            if default_storage.exists(path):
                default_storage.delete(path)
                return Response({'success': True, 'deleted': path})
            return Response({'error': 'File not found.'}, status=404)
        except Exception as e:
            return Response({'error': str(e)}, status=500)


class AdminAttachmentUploadView(APIView):
    """
    POST /referral/admin/upload/
    Admin upload for campaign assets — no user folder restriction.
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, *args, **kwargs):
        if not request.user.is_staff:
            return Response({'error': 'Admin access required.'}, status=403)

        file = request.FILES.get('file')
        if not file:
            return Response({'error': 'No file.'}, status=400)

        if file.size > MAX_FILE_SIZE * 2:  # Admins get 10MB
            return Response({'error': 'File too large.'}, status=400)

        purpose = request.data.get('purpose', 'general')
        ext = os.path.splitext(file.name)[1].lower()
        filename = f"referral/admin/{purpose}/{uuid.uuid4().hex}{ext}"

        try:
            saved = default_storage.save(filename, file)
            return Response({
                'success': True,
                'file_url': default_storage.url(saved),
                'path': saved,
            })
        except Exception as e:
            return Response({'error': str(e)}, status=500)