# api/support/attachment_upload_view.py
import logging
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

logger = logging.getLogger(__name__)

ALLOWED_TYPES = ['image/jpeg','image/png','image/gif','image/webp','application/pdf','text/plain']
MAX_SIZE = 10 * 1024 * 1024  # 10MB


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser])
def upload_ticket_attachment(request, ticket_id):
    from api.support.dependencies import get_ticket_or_404
    ticket = get_ticket_or_404(ticket_id, user=request.user)
    file = request.FILES.get('file')
    if not file:
        return Response({'error': 'No file provided.'}, status=400)
    if file.size > MAX_SIZE:
        return Response({'error': 'File exceeds 10MB limit.'}, status=400)
    mime = getattr(file, 'content_type', '')
    if mime and mime not in ALLOWED_TYPES:
        return Response({'error': f'File type {mime} not allowed.'}, status=400)
    try:
        from api.support.models import TicketAttachment
        attachment = TicketAttachment.objects.create(
            ticket=ticket, file=file, filename=file.name,
            mime_type=mime, size_bytes=file.size, uploaded_by=request.user,
        )
        return Response({
            'success': True,
            'id':       attachment.id,
            'filename': attachment.filename,
            'size_mb':  attachment.size_mb,
            'url':      request.build_absolute_uri(attachment.file.url),
        }, status=201)
    except Exception as e:
        logger.error(f'upload: {e}')
        return Response({'error': 'Upload failed.'}, status=500)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_ticket_attachment(request, ticket_id, attachment_id):
    from api.support.models import TicketAttachment
    try:
        att = TicketAttachment.objects.get(id=attachment_id)
    except TicketAttachment.DoesNotExist:
        return Response({'error': 'Not found.'}, status=404)
    if not request.user.is_staff and att.uploaded_by != request.user:
        return Response({'detail': 'Access denied.'}, status=403)
    att.file.delete(save=False)
    att.delete()
    return Response({'success': True}, status=204)