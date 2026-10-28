# api/support/error_codes.py
"""
Standard error codes for support API responses.
Use these in exception handlers and response builders.
"""

# ── Ticket Errors ─────────────────────────────────────────────
ERR_TICKET_NOT_FOUND        = 'TICKET_NOT_FOUND'
ERR_TICKET_CLOSED           = 'TICKET_CLOSED'
ERR_TICKET_SPAM             = 'TICKET_SPAM'
ERR_TICKET_FORBIDDEN        = 'TICKET_FORBIDDEN'
ERR_TICKET_ALREADY_RATED    = 'TICKET_ALREADY_RATED'
ERR_TICKET_ALREADY_ESCALATED= 'TICKET_ALREADY_ESCALATED'
ERR_TICKET_CREATE_FAILED    = 'TICKET_CREATE_FAILED'
ERR_TICKET_REPLY_FAILED     = 'TICKET_REPLY_FAILED'

# ── Validation Errors ─────────────────────────────────────────
ERR_SUBJECT_TOO_SHORT       = 'SUBJECT_TOO_SHORT'
ERR_SUBJECT_TOO_LONG        = 'SUBJECT_TOO_LONG'
ERR_DESCRIPTION_TOO_SHORT   = 'DESCRIPTION_TOO_SHORT'
ERR_INVALID_RATING          = 'INVALID_RATING'
ERR_INVALID_AMOUNT          = 'INVALID_AMOUNT'
ERR_INVALID_CATEGORY        = 'INVALID_CATEGORY'
ERR_INVALID_PRIORITY        = 'INVALID_PRIORITY'
ERR_INVALID_OFFER_ID        = 'INVALID_OFFER_ID'
ERR_INVALID_TRANSACTION_ID  = 'INVALID_TRANSACTION_ID'

# ── Dispute Errors ────────────────────────────────────────────
ERR_DISPUTE_LIMIT_EXCEEDED  = 'DISPUTE_LIMIT_EXCEEDED'
ERR_DISPUTE_BANNED          = 'DISPUTE_BANNED'
ERR_DISPUTE_NOT_FOUND       = 'DISPUTE_NOT_FOUND'
ERR_DISPUTE_ALREADY_RESOLVED= 'DISPUTE_ALREADY_RESOLVED'
ERR_DISPUTE_HIGH_RISK       = 'DISPUTE_HIGH_RISK'

# ── Chat Errors ───────────────────────────────────────────────
ERR_CHAT_DISABLED           = 'CHAT_DISABLED'
ERR_CHAT_NOT_FOUND          = 'CHAT_NOT_FOUND'
ERR_CHAT_ENDED              = 'CHAT_ENDED'
ERR_CHAT_NO_AGENT           = 'CHAT_NO_AGENT_AVAILABLE'

# ── Auth Errors ───────────────────────────────────────────────
ERR_UNAUTHORIZED            = 'UNAUTHORIZED'
ERR_FORBIDDEN               = 'FORBIDDEN'
ERR_AGENT_REQUIRED          = 'AGENT_REQUIRED'
ERR_SUPERVISOR_REQUIRED     = 'SUPERVISOR_REQUIRED'

# ── System Errors ─────────────────────────────────────────────
ERR_MAINTENANCE             = 'MAINTENANCE_MODE'
ERR_RATE_LIMIT              = 'RATE_LIMIT_EXCEEDED'
ERR_ATTACHMENT_TOO_LARGE    = 'ATTACHMENT_TOO_LARGE'
ERR_UNSUPPORTED_FILE        = 'UNSUPPORTED_FILE_TYPE'
ERR_INTERNAL                = 'INTERNAL_ERROR'
ERR_SERVICE_UNAVAILABLE     = 'SERVICE_UNAVAILABLE'

# ── Integration Errors ────────────────────────────────────────
ERR_WALLET_LOCKED           = 'WALLET_LOCKED'
ERR_WALLET_UNAVAILABLE      = 'WALLET_SERVICE_UNAVAILABLE'
ERR_FRAUD_SERVICE_DOWN      = 'FRAUD_SERVICE_UNAVAILABLE'

# ── HTTP Status mapping ───────────────────────────────────────
ERROR_HTTP_STATUS = {
    ERR_TICKET_NOT_FOUND:   404,
    ERR_DISPUTE_NOT_FOUND:  404,
    ERR_CHAT_NOT_FOUND:     404,
    ERR_TICKET_CLOSED:      400,
    ERR_CHAT_ENDED:         400,
    ERR_INVALID_RATING:     400,
    ERR_DISPUTE_LIMIT_EXCEEDED: 429,
    ERR_RATE_LIMIT:         429,
    ERR_UNAUTHORIZED:       401,
    ERR_FORBIDDEN:          403,
    ERR_MAINTENANCE:        503,
    ERR_CHAT_NO_AGENT:      503,
    ERR_INTERNAL:           500,
}


def get_http_status(error_code: str) -> int:
    """Get HTTP status code for an error code."""
    return ERROR_HTTP_STATUS.get(error_code, 400)


def error_response(code: str, message: str = '', field: str = '') -> dict:
    """Build standard error response dict."""
    resp = {'error': code, 'code': code}
    if message:
        resp['message'] = message
    if field:
        resp['field'] = field
    return resp