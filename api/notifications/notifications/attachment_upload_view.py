# earning_backend/api/notifications/attachment_upload_view.py
"""
Attachment Upload View — Handles file/image uploads for rich notifications.
Uploaded files are used as notification images (rich push, email hero images).
"""
import logging, os, uuid
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

logger = logging.getLogger(__name__)

ALLOWED_TYPES = {'image/jpeg', 'image/png', 'image/gif', 'image/webp'}
MAX_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB


@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser])
@permission_classes([IsAuthenticated])
def upload_notification_attachment(request):
    """
    Upload an image attachment for use in rich push notifications or email.

    POST /api/notifications/upload-attachment/
    Content-Type: multipart/form-data
    Body: file (image/jpeg | image/png | image/gif | image/webp, max 5MB)

    Returns:
        {'url': 'https://...', 'filename': '...', 'size': 12345}
    """
    file = request.FILES.get('file')
    if not file:
        return Response({'error': 'No file provided.'}, status=400)

    if file.content_type not in ALLOWED_TYPES:
        return Response({'error': f'File type not allowed. Allowed: {ALLOWED_TYPES}'}, status=400)

    if file.size > MAX_SIZE_BYTES:
        return Response({'error': f'File too large. Max size: {MAX_SIZE_BYTES // 1024 // 1024}MB'}, status=400)

    # Generate a unique filename
    ext = file.name.rsplit('.', 1)[-1].lower() if '.' in file.name else 'jpg'
    unique_name = f'notif_attach_{uuid.uuid4().hex}.{ext}'

    try:
        # Try S3 first
        s3_key = getattr(settings, 'NOTIFICATION_ATTACHMENT_S3_PREFIX', 'notification-attachments')
        bucket = getattr(settings, 'AWS_STORAGE_BUCKET_NAME', '')

        if bucket:
            import boto3
            s3 = boto3.client('s3')
            s3.upload_fileobj(
                file,
                bucket,
                f'{s3_key}/{unique_name}',
                ExtraArgs={'ContentType': file.content_type, 'ACL': 'public-read'},
            )
            url = f'https://{bucket}.s3.amazonaws.com/{s3_key}/{unique_name}'
        else:
            # Fallback: local media storage
            media_root = getattr(settings, 'MEDIA_ROOT', '/tmp')
            upload_dir = os.path.join(media_root, 'notification_attachments')
            os.makedirs(upload_dir, exist_ok=True)
            save_path = os.path.join(upload_dir, unique_name)
            with open(save_path, 'wb') as f_out:
                for chunk in file.chunks():
                    f_out.write(chunk)
            media_url = getattr(settings, 'MEDIA_URL', '/media/')
            url = f'{request.build_absolute_uri(media_url)}notification_attachments/{unique_name}'

        logger.info(f'Notification attachment uploaded: {unique_name} by user #{request.user.pk}')
        return Response({'url': url, 'filename': unique_name, 'size': file.size, 'content_type': file.content_type})

    except Exception as exc:
        logger.error(f'upload_notification_attachment: {exc}')
        return Response({'error': f'Upload failed: {str(exc)}'}, status=500)
