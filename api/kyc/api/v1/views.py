# kyc/api/v1/views.py  ── WORLD #1
"""API v1 — thin wrappers around core views for versioned routing"""
from ...views import (
    kyc_status, kyc_submit, kyc_fraud_check, kyc_logs,
    kyc_admin_list, kyc_admin_stats, kyc_admin_review,
    kyc_admin_delete, kyc_admin_reset, kyc_admin_logs,
    kyc_admin_add_note, kyc_admin_bulk_action,
)

# Re-export so v1 URLs can import from here
__all__ = [
    'kyc_status', 'kyc_submit', 'kyc_fraud_check', 'kyc_logs',
    'kyc_admin_list', 'kyc_admin_stats', 'kyc_admin_review',
    'kyc_admin_delete', 'kyc_admin_reset', 'kyc_admin_logs',
    'kyc_admin_add_note', 'kyc_admin_bulk_action',
]
