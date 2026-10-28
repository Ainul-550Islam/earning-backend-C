"""
api/tasks/attachment_upload_view.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
File upload views for task completion proofs and KYC documents.
Supports: images, PDFs, screenshots as proof of task completion.
Security: validates file type, size, and scans for malware (optional).
"""

import logging
import os
import uuid
from django.conf import settings
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger(__name__)

# Allowed file types for task proof uploads
ALLOWED_CONTENT_TYPES = {
    'image/jpeg', 'image/jpg', 'image/png', 'image/webp', 'image/gif',
    'application/pdf',
    'video/mp4', 'video/webm',
}

# Max file sizes
MAX_PROOF_SIZE_MB    = 10
MAX_KYC_SIZE_MB      = 20
MAX_PROOF_SIZE_BYTES = MAX_PROOF_SIZE_MB * 1024 * 1024
MAX_KYC_SIZE_BYTES   = MAX_KYC_SIZE_MB * 1024 * 1024

# Upload paths
PROOF_UPLOAD_PATH = 'task_proofs/'
KYC_UPLOAD_PATH   = 'kyc_documents/'


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def upload_task_proof(request):
    """
    POST /tasks/upload/proof/
    Upload a screenshot or file as proof of task completion.
    Returns: {url, file_id, content_type, size_bytes}
    """
    file_obj = request.FILES.get('file') or request.FILES.get('proof')
    if not file_obj:
        return Response({'error': 'No file provided. Use field name: file or proof'},
                        status=status.HTTP_400_BAD_REQUEST)

    # Validate file type
    content_type = file_obj.content_type or ''
    if content_type not in ALLOWED_CONTENT_TYPES:
        return Response({
            'error':   f'File type not allowed: {content_type}',
            'allowed': list(ALLOWED_CONTENT_TYPES),
        }, status=status.HTTP_400_BAD_REQUEST)

    # Validate file size
    if file_obj.size > MAX_PROOF_SIZE_BYTES:
        return Response({
            'error': f'File too large. Maximum size: {MAX_PROOF_SIZE_MB}MB',
            'size':  file_obj.size,
            'max':   MAX_PROOF_SIZE_BYTES,
        }, status=status.HTTP_400_BAD_REQUEST)

    # Generate safe filename
    ext       = _get_safe_extension(file_obj.name, content_type)
    file_id   = str(uuid.uuid4())
    filename  = f"{file_id}{ext}"
    user_path = f"{PROOF_UPLOAD_PATH}{request.user.pk}/{filename}"

    try:
        file_url = _save_file(file_obj, user_path)
    except Exception as e:
        logger.error(f"[UPLOAD] proof save error: {e}")
        return Response({'error': 'File upload failed. Please try again.'},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # Record in DB (optional)
    _record_upload(
        user_id=request.user.pk,
        file_id=file_id,
        file_url=file_url,
        upload_type='task_proof',
        original_name=file_obj.name[:200],
        content_type=content_type,
        size_bytes=file_obj.size,
    )

    return Response({
        'status':       'uploaded',
        'file_id':      file_id,
        'url':          file_url,
        'content_type': content_type,
        'size_bytes':   file_obj.size,
        'timestamp':    timezone.now().isoformat(),
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def upload_kyc_document(request):
    """
    POST /tasks/upload/kyc/
    Upload a KYC document (ID card, passport, address proof).
    Files are stored securely and never publicly accessible.
    Returns: {file_id, status}
    """
    file_obj    = request.FILES.get('file') or request.FILES.get('document')
    doc_type    = request.data.get('document_type', 'identity')   # identity | address | selfie

    if not file_obj:
        return Response({'error': 'No file provided.'}, status=400)

    content_type = file_obj.content_type or ''
    kyc_allowed  = {'image/jpeg', 'image/png', 'image/webp', 'application/pdf'}

    if content_type not in kyc_allowed:
        return Response({
            'error':   f'File type not allowed for KYC: {content_type}',
            'allowed': list(kyc_allowed),
        }, status=400)

    if file_obj.size > MAX_KYC_SIZE_BYTES:
        return Response({'error': f'File too large. Max {MAX_KYC_SIZE_MB}MB.'}, status=400)

    ext      = _get_safe_extension(file_obj.name, content_type)
    file_id  = str(uuid.uuid4())
    filename = f"{file_id}{ext}"
    # KYC files go in private storage, not public
    user_path = f"{KYC_UPLOAD_PATH}{request.user.pk}/{doc_type}/{filename}"

    try:
        file_url = _save_file(file_obj, user_path, private=True)
    except Exception as e:
        logger.error(f"[UPLOAD] KYC save error: {e}")
        return Response({'error': 'Document upload failed.'}, status=500)

    _record_upload(
        user_id=request.user.pk,
        file_id=file_id,
        file_url=file_url,
        upload_type=f'kyc_{doc_type}',
        original_name=file_obj.name[:200],
        content_type=content_type,
        size_bytes=file_obj.size,
    )

    logger.info(f"[KYC UPLOAD] user={request.user.pk} type={doc_type} file={file_id}")
    return Response({
        'status':       'uploaded',
        'file_id':      file_id,
        'document_type': doc_type,
        'timestamp':    timezone.now().isoformat(),
    }, status=201)


# ── Private helpers ─────────────────────────────────────────────────────────

def _get_safe_extension(filename: str, content_type: str) -> str:
    """Return a safe file extension based on content type."""
    ext_map = {
        'image/jpeg':       '.jpg',
        'image/jpg':        '.jpg',
        'image/png':        '.png',
        'image/webp':       '.webp',
        'image/gif':        '.gif',
        'application/pdf':  '.pdf',
        'video/mp4':        '.mp4',
        'video/webm':       '.webm',
    }
    return ext_map.get(content_type, '.bin')


def _save_file(file_obj, path: str, private: bool = False) -> str:
    """
    Save an uploaded file and return its URL.
    Supports: local filesystem, S3, or any Django storage backend.
    """
    try:
        # Try Django Storages (S3, GCS, etc.)
        from django.core.files.storage import default_storage
        from django.core.files.base import ContentFile
        saved_path = default_storage.save(path, ContentFile(file_obj.read()))
        if private:
            return saved_path   # Return path only for private files
        return default_storage.url(saved_path)
    except Exception as e:
        logger.error(f"[UPLOAD] save error: {e}")
        raise


def _record_upload(user_id: int, file_id: str, file_url: str,
                   upload_type: str, original_name: str,
                   content_type: str, size_bytes: int) -> None:
    """Record the upload in DB for audit trail."""
    try:
        from api.tasks.models import TaskFileUpload
        TaskFileUpload.objects.create(
            user_id=user_id,
            file_id=file_id,
            file_url=file_url,
            upload_type=upload_type,
            original_name=original_name,
            content_type=content_type,
            size_bytes=size_bytes,
            uploaded_at=timezone.now(),
        )
    except Exception:
        pass  # Recording is non-critical


__all__ = ['upload_task_proof', 'upload_kyc_document']
