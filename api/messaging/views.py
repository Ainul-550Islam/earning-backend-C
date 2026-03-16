"""
Bulletproof File Upload View — Messaging Attachments
POST /api/messaging/upload/
"""
from __future__ import annotations
import hashlib, logging, mimetypes, os, uuid
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import UploadedFile
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)

ALLOWED_TYPES = {
    "image/jpeg":    {"ext": ".jpg",  "max_mb": 10, "category": "image"},
    "image/png":     {"ext": ".png",  "max_mb": 10, "category": "image"},
    "image/gif":     {"ext": ".gif",  "max_mb": 10, "category": "image"},
    "image/webp":    {"ext": ".webp", "max_mb": 10, "category": "image"},
    "video/mp4":     {"ext": ".mp4",  "max_mb": 50, "category": "video"},
    "video/webm":    {"ext": ".webm", "max_mb": 50, "category": "video"},
    "video/quicktime":{"ext": ".mov", "max_mb": 50, "category": "video"},
    "audio/mpeg":    {"ext": ".mp3",  "max_mb": 20, "category": "audio"},
    "audio/wav":     {"ext": ".wav",  "max_mb": 20, "category": "audio"},
    "audio/ogg":     {"ext": ".ogg",  "max_mb": 20, "category": "audio"},
    "audio/mp4":     {"ext": ".m4a",  "max_mb": 20, "category": "audio"},
    "application/pdf":{"ext": ".pdf", "max_mb": 20, "category": "document"},
    "text/plain":    {"ext": ".txt",  "max_mb": 5,  "category": "document"},
    "application/zip":{"ext": ".zip", "max_mb": 20, "category": "document"},
    "application/msword": {"ext": ".doc", "max_mb": 20, "category": "document"},
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": {"ext": ".docx", "max_mb": 20, "category": "document"},
    "application/vnd.ms-excel": {"ext": ".xls", "max_mb": 20, "category": "document"},
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {"ext": ".xlsx", "max_mb": 20, "category": "document"},
}

DANGEROUS_SIGNATURES = [b"MZ", b"\x7fELF", b"#!/", b"<?php"]
MAX_FILES_PER_REQUEST = 10


def _detect_mimetype(file: UploadedFile) -> str:
    header = file.read(512)
    file.seek(0)
    for sig in DANGEROUS_SIGNATURES:
        if header.startswith(sig):
            return "application/octet-stream"
    claimed = (file.content_type or "").split(";")[0].strip().lower()
    return claimed if claimed in ALLOWED_TYPES else (
        mimetypes.guess_type(file.name or "")[0] or "application/octet-stream"
    )


def _file_checksum(file: UploadedFile) -> str:
    sha = hashlib.sha256()
    for chunk in file.chunks(8192):
        sha.update(chunk)
    file.seek(0)
    return sha.hexdigest()


def _upload_path(category: str, filename: str) -> str:
    today = timezone.now()
    return os.path.join(
        "messaging", category,
        str(today.year), f"{today.month:02d}", f"{today.day:02d}", filename,
    )


class MessageAttachmentUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes     = [MultiPartParser, FormParser]

    def post(self, request: Request) -> Response:
        files: list[UploadedFile] = request.FILES.getlist("files")

        if not files:
            return Response({"detail": "No files provided. Use field name 'files'."}, status=400)
        if len(files) > MAX_FILES_PER_REQUEST:
            return Response({"detail": f"Max {MAX_FILES_PER_REQUEST} files per request."}, status=400)

        attachments, errors = [], []
        for file in files:
            result = self._process_file(file, request.user)
            (errors if "error" in result else attachments).append(result)

        return Response(
            {"attachments": attachments, "errors": errors},
            status=status.HTTP_200_OK if attachments else status.HTTP_400_BAD_REQUEST,
        )

    def _process_file(self, file: UploadedFile, user) -> dict:
        name = (file.name or "file").strip()
        mimetype = _detect_mimetype(file)
        type_info = ALLOWED_TYPES.get(mimetype)

        if not type_info:
            return {"error": f"'{name}': type '{mimetype}' not allowed.", "filename": name}
        if file.size == 0:
            return {"error": f"'{name}': file is empty.", "filename": name}
        if file.size > type_info["max_mb"] * 1024 * 1024:
            return {"error": f"'{name}': exceeds {type_info['max_mb']}MB limit.", "filename": name}

        checksum   = _file_checksum(file)
        safe_name  = f"{uuid.uuid4().hex}{type_info['ext']}"
        saved_path = default_storage.save(_upload_path(type_info["category"], safe_name), file)

        logger.info("Attachment uploaded: user=%s file=%s size=%d", user.pk, safe_name, file.size)
        return {
            "url":        f"http://127.0.0.1:8000{settings.MEDIA_URL}{saved_path}",
            "filename":   name,
            "mimetype":   mimetype,
            "size_bytes": file.size,
            "category":   type_info["category"],
            "checksum":   checksum,
        }
