"""
DISPUTE_RESOLUTION/dispute_category.py — Dispute Category Configuration
"""
from api.marketplace.enums import DisputeType

DISPUTE_CATEGORY_CONFIG = {
    DisputeType.NOT_RECEIVED: {
        "description":      "Item has not arrived by the expected delivery date",
        "auto_approve_days":14,   # auto-approve refund if not delivered in 14 days
        "requires_evidence":False,
        "typical_resolution":"refund",
    },
    DisputeType.NOT_AS_DESCRIBED: {
        "description":      "Item received is significantly different from listing",
        "auto_approve_days":None,
        "requires_evidence":True,
        "typical_resolution":"partial_refund",
    },
    DisputeType.COUNTERFEIT: {
        "description":      "Item appears to be fake or counterfeit",
        "auto_approve_days":None,
        "requires_evidence":True,
        "typical_resolution":"full_refund",
        "escalate_immediately": True,
    },
    DisputeType.DAMAGED: {
        "description":      "Item arrived damaged",
        "auto_approve_days":None,
        "requires_evidence":True,
        "typical_resolution":"full_refund",
    },
    DisputeType.WRONG_ITEM: {
        "description":      "Received a different item than what was ordered",
        "auto_approve_days":None,
        "requires_evidence":True,
        "typical_resolution":"full_refund",
    },
    DisputeType.OTHER: {
        "description":      "Other issue not listed above",
        "auto_approve_days":None,
        "requires_evidence":True,
        "typical_resolution":"admin_decision",
    },
}


def get_dispute_category_info(dispute_type: str) -> dict:
    return DISPUTE_CATEGORY_CONFIG.get(dispute_type, DISPUTE_CATEGORY_CONFIG[DisputeType.OTHER])


def get_all_categories() -> list:
    return [
        {"type": k, **v}
        for k, v in DISPUTE_CATEGORY_CONFIG.items()
    ]
