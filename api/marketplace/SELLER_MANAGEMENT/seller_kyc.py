"""
SELLER_MANAGEMENT/seller_kyc.py — KYC Document Validation & Processing
"""
import re
from api.marketplace.validators import validate_nid_number, validate_phone_bd


def validate_kyc_docs(nid_number: str, nid_front, nid_back, selfie) -> list:
    """Validate KYC documents. Returns list of errors (empty = OK)."""
    errors = []
    try:
        validate_nid_number(nid_number)
    except Exception as e:
        errors.append(str(e))
    if not nid_front:
        errors.append("NID front image is required")
    if not nid_back:
        errors.append("NID back image is required")
    if not selfie:
        errors.append("Selfie with ID is required")
    return errors


def validate_business_docs(trade_license_no: str = "", tin_number: str = "") -> dict:
    """Validate business registration documents."""
    errors = []
    if trade_license_no:
        if not re.match(r"^[A-Za-z0-9\-/]+$", trade_license_no):
            errors.append("Invalid trade license number format")
    if tin_number:
        tin_clean = tin_number.replace("-","").replace(" ","")
        if not tin_clean.isdigit() or len(tin_clean) not in (9, 12):
            errors.append("TIN must be 9 or 12 digits")
    return {"valid": len(errors) == 0, "errors": errors}


def kyc_completion_status(seller) -> dict:
    """Check KYC completion percentage and what's missing."""
    try:
        ver = seller.verification
    except Exception:
        return {"complete": False, "percent": 0, "missing": ["Submit KYC documents to get started"]}

    checks = {
        "NID Number":   bool(ver.nid_number),
        "NID Front":    bool(ver.nid_front),
        "NID Back":     bool(ver.nid_back),
        "Selfie":       bool(ver.selfie),
    }
    # Business docs (optional but boost trust)
    if seller.business_type == "company":
        checks["Trade License"] = bool(ver.trade_license_doc)
        checks["TIN Certificate"] = bool(ver.tin_certificate)

    done    = sum(1 for v in checks.values() if v)
    total   = len(checks)
    missing = [k for k, v in checks.items() if not v]

    return {
        "complete":       len(missing) == 0,
        "percent":        int(done / total * 100),
        "completed":      [k for k, v in checks.items() if v],
        "missing":        missing,
        "status":         ver.status,
        "rejection_reason": ver.rejection_reason,
    }


def prepare_kyc_submission(seller, **doc_data) -> dict:
    """Prepare and validate KYC before submission."""
    nid  = doc_data.get("nid_number","")
    errors = validate_kyc_docs(
        nid,
        doc_data.get("nid_front"),
        doc_data.get("nid_back"),
        doc_data.get("selfie"),
    )
    if errors:
        return {"ready": False, "errors": errors}

    # Submit
    from api.marketplace.SELLER_MANAGEMENT.seller_verification import submit_kyc
    ver = submit_kyc(seller, **doc_data)
    return {"ready": True, "status": ver.status, "message": "KYC submitted for review"}
