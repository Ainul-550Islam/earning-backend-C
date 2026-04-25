# api/payment_gateways/attachment_upload_view.py
# File upload for support tickets and KYC documents

from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from django.conf import settings
import os, uuid


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def upload_attachment(request):
    """
    Upload attachment for support tickets or KYC.
    Accepts: images (JPG/PNG), PDF, max 5MB.

    POST /api/payment/upload/
    Form field: file (required), purpose (support_ticket|kyc|withdrawal_proof)
    """
    file    = request.FILES.get('file')
    purpose = request.data.get('purpose', 'general')

    if not file:
        return Response({'success': False, 'error': 'No file provided'}, status=400)

    # Validate file type
    ALLOWED_TYPES = {'image/jpeg', 'image/png', 'application/pdf'}
    if file.content_type not in ALLOWED_TYPES:
        return Response({'success': False, 'error': 'Only JPG, PNG, PDF allowed'}, status=400)

    # Validate file size (5MB max)
    if file.size > 5 * 1024 * 1024:
        return Response({'success': False, 'error': 'File too large (max 5MB)'}, status=400)

    # Generate safe filename
    ext      = os.path.splitext(file.name)[1].lower()
    filename = f'{uuid.uuid4().hex}{ext}'
    path     = f'payment_attachments/{purpose}/{request.user.id}/{filename}'

    # Save file
    try:
        from django.core.files.storage import default_storage
        saved_path = default_storage.save(path, file)
        url        = default_storage.url(saved_path)
        return Response({'success': True, 'url': url, 'filename': filename})
    except Exception as e:
        return Response({'success': False, 'error': str(e)}, status=500)
