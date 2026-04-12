"""
DISPUTE_RESOLUTION/dispute_evidence.py — Evidence Management
"""
from .dispute_model import Dispute, DisputeEvidence
import os

MAX_EVIDENCE_FILES = 5
ALLOWED_EVIDENCE_TYPES = {".jpg",".jpeg",".png",".webp",".pdf",".mp4"}
MAX_FILE_SIZE_MB = 20


def add_evidence(dispute: Dispute, uploader, role: str, file, caption: str = "") -> dict:
    if dispute.status not in ("open","under_review","escalated"):
        return {"success": False, "error": "Dispute is closed — cannot add evidence"}

    existing = DisputeEvidence.objects.filter(dispute=dispute, uploader=uploader).count()
    if existing >= MAX_EVIDENCE_FILES:
        return {"success": False, "error": f"Maximum {MAX_EVIDENCE_FILES} evidence files allowed"}

    ext = os.path.splitext(file.name)[1].lower()
    if ext not in ALLOWED_EVIDENCE_TYPES:
        return {"success": False, "error": f"File type not allowed. Use: {ALLOWED_EVIDENCE_TYPES}"}

    size_mb = file.size / 1024 / 1024
    if size_mb > MAX_FILE_SIZE_MB:
        return {"success": False, "error": f"File too large: {size_mb:.1f}MB (max {MAX_FILE_SIZE_MB}MB)"}

    ev = DisputeEvidence.objects.create(
        tenant=dispute.tenant, dispute=dispute,
        uploader=uploader, role=role, file=file, caption=caption,
    )
    return {"success": True, "evidence_id": ev.pk, "file": ev.file.name}


def get_evidence(dispute: Dispute) -> dict:
    buyer_ev  = DisputeEvidence.objects.filter(dispute=dispute, role="buyer")
    seller_ev = DisputeEvidence.objects.filter(dispute=dispute, role="seller")
    def _format(ev):
        return [{"id": e.pk, "file": e.file.name, "caption": e.caption,
                 "uploaded": e.created_at.strftime("%Y-%m-%d %H:%M")} for e in ev]
    return {"buyer": _format(buyer_ev), "seller": _format(seller_ev)}
