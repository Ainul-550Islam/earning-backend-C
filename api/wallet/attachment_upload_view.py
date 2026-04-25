# api/wallet/attachment_upload_view.py
"""
Attachment upload views — KYC documents, withdrawal proof, dispute evidence.
"""
import os
import uuid
import logging
from django.conf import settings
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

logger = logging.getLogger("wallet.attachment")

ALLOWED_TYPES = {"image/jpeg","image/png","image/webp","application/pdf"}
MAX_SIZE_MB   = 10


class KYCDocumentUploadView(APIView):
    """
    POST /api/wallet/kyc/upload/
    Upload KYC identity document (NID, passport, selfie).
    """
    parser_classes     = [MultiPartParser, FormParser]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        file      = request.FILES.get("file")
        doc_type  = request.data.get("doc_type", "nid")  # nid, passport, selfie, bank_statement

        if not file:
            return Response({"success": False, "error": "No file uploaded"}, status=400)

        # Validate type
        if file.content_type not in ALLOWED_TYPES:
            return Response({"success": False,
                             "error": f"Invalid file type: {file.content_type}. Allowed: jpeg, png, pdf"}, status=400)

        # Validate size
        if file.size > MAX_SIZE_MB * 1024 * 1024:
            return Response({"success": False,
                             "error": f"File too large. Max {MAX_SIZE_MB}MB"}, status=400)

        # Save file
        try:
            ext      = file.name.rsplit(".", 1)[-1].lower()
            filename = f"kyc/{request.user.id}/{doc_type}_{uuid.uuid4().hex}.{ext}"
            file_url = self._save_file(file, filename)

            logger.info(f"KYC document uploaded: user={request.user.id} type={doc_type}")
            return Response({"success": True, "file_url": file_url, "doc_type": doc_type})

        except Exception as e:
            logger.error(f"KYC upload error: {e}", exc_info=True)
            return Response({"success": False, "error": "Upload failed"}, status=500)

    def _save_file(self, file, filename: str) -> str:
        """Save file to storage and return URL."""
        # Try Django default storage (S3, local, etc.)
        from django.core.files.storage import default_storage
        path = default_storage.save(filename, file)
        return default_storage.url(path)


class DisputeEvidenceUploadView(APIView):
    """
    POST /api/wallet/disputes/{id}/upload_evidence/
    Upload evidence for a dispute (screenshot, receipt, etc.)
    """
    parser_classes     = [MultiPartParser, FormParser]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk=None, *args, **kwargs):
        file = request.FILES.get("file")
        if not file:
            return Response({"success": False, "error": "No file"}, status=400)

        if file.size > MAX_SIZE_MB * 1024 * 1024:
            return Response({"success": False, "error": f"Max {MAX_SIZE_MB}MB"}, status=400)

        try:
            ext      = file.name.rsplit(".", 1)[-1].lower()
            filename = f"disputes/{pk}/{uuid.uuid4().hex}.{ext}"
            from django.core.files.storage import default_storage
            path = default_storage.save(filename, file)
            url  = default_storage.url(path)
            return Response({"success": True, "file_url": url})
        except Exception as e:
            return Response({"success": False, "error": str(e)}, status=500)
