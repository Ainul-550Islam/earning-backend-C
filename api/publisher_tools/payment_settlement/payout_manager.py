# api/publisher_tools/payment_settlement/payout_manager.py
"""Payout Manager — Payout processing and management."""
from decimal import Decimal
from typing import Dict, List, Optional
from django.db import transaction
from django.utils import timezone


def check_payout_eligibility(publisher) -> Dict:
    """Publisher payout-এর জন্য eligible কিনা check করে।"""
    from api.publisher_tools.models import PayoutThreshold
    threshold = PayoutThreshold.objects.filter(publisher=publisher, is_primary=True, is_verified=True).first()
    if not threshold:
        return {"eligible": False, "reason": "No verified payment method configured."}
    if not publisher.is_kyc_verified:
        return {"eligible": False, "reason": "KYC verification required before payout."}
    available = publisher.available_balance
    if available < threshold.minimum_threshold:
        return {
            "eligible": False,
            "reason": f"Balance ${float(available):.2f} below minimum ${float(threshold.minimum_threshold):.2f}.",
            "balance": float(available), "threshold": float(threshold.minimum_threshold),
        }
    return {
        "eligible": True, "balance": float(available),
        "payment_method": threshold.payment_method,
        "threshold": float(threshold.minimum_threshold),
    }


@transaction.atomic
def process_payout_request(publisher, amount: Decimal, bank_account_id: str, notes: str = "") -> Dict:
    """Payout request process করে।"""
    from api.publisher_tools.publisher_management.publisher_payout import PayoutRequest
    eligibility = check_payout_eligibility(publisher)
    if not eligibility["eligible"]:
        return {"success": False, "reason": eligibility["reason"]}
    if amount > publisher.available_balance:
        return {"success": False, "reason": "Requested amount exceeds available balance."}
    from api.publisher_tools.publisher_management.publisher_bank_account import PublisherBankAccount
    try:
        bank_account = PublisherBankAccount.objects.get(id=bank_account_id, publisher=publisher)
    except Exception:
        return {"success": False, "reason": "Invalid bank account."}
    fee_info = bank_account.calculate_net_payout(amount)
    payout = PayoutRequest.objects.create(
        publisher=publisher, bank_account=bank_account,
        requested_amount=amount,
        processing_fee=Decimal(str(fee_info["processing_fee"])),
        withholding_tax=Decimal(str(fee_info["withholding_tax"])),
        net_amount=Decimal(str(fee_info["net_amount"])),
        publisher_notes=notes, status="pending",
    )
    return {"success": True, "payout_id": payout.request_id, "amount": float(amount), "net_amount": fee_info["net_amount"]}


def get_payout_history(publisher, limit: int = 20) -> List[Dict]:
    from api.publisher_tools.publisher_management.publisher_payout import PayoutRequest
    payouts = PayoutRequest.objects.filter(publisher=publisher).order_by("-created_at")[:limit]
    return [
        {"request_id": p.request_id, "amount": float(p.requested_amount), "net": float(p.net_amount or 0),
         "status": p.status, "created": str(p.created_at.date()), "completed": str(p.completed_at) if p.completed_at else None}
        for p in payouts
    ]
