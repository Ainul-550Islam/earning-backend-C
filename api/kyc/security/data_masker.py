# kyc/security/data_masker.py  ── WORLD #1
"""Data masking for KYC PII — safe display in logs/APIs"""


def mask_nid(nid: str) -> str:
    if not nid or len(nid) < 5:
        return '****'
    return nid[:3] + '*' * (len(nid) - 6) + nid[-3:]


def mask_phone(phone: str) -> str:
    if not phone or len(phone) < 7:
        return '****'
    return phone[:4] + '****' + phone[-3:]


def mask_name(name: str) -> str:
    if not name:
        return '***'
    parts = name.strip().split()
    masked = []
    for part in parts:
        if len(part) <= 2:
            masked.append(part[0] + '*')
        else:
            masked.append(part[0] + '*' * (len(part) - 2) + part[-1])
    return ' '.join(masked)


def mask_email(email: str) -> str:
    if not email or '@' not in email:
        return '****'
    local, domain = email.split('@', 1)
    if len(local) <= 2:
        return local[0] + '*@' + domain
    return local[:2] + '***@' + domain


def mask_document_number(doc: str) -> str:
    if not doc or len(doc) < 5:
        return '****'
    return doc[:3] + '****' + doc[-3:]


def mask_kyc_for_log(kyc) -> dict:
    """Return a masked version of KYC data safe for logging."""
    return {
        'id':              getattr(kyc, 'id', None),
        'user_id':         getattr(kyc.user, 'id', None) if hasattr(kyc, 'user') else None,
        'full_name':       mask_name(getattr(kyc, 'full_name', '')),
        'phone_number':    mask_phone(getattr(kyc, 'phone_number', '')),
        'document_number': mask_document_number(getattr(kyc, 'document_number', '')),
        'status':          getattr(kyc, 'status', ''),
        'risk_score':      getattr(kyc, 'risk_score', 0),
    }
