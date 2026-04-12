# api/publisher_tools/payment_settlement/receipt_generator.py
"""Receipt Generator — Payment receipt generation."""
from decimal import Decimal
from django.utils import timezone


def generate_payment_receipt(payout_request) -> Dict:
    """Payout receipt generate করে।"""
    pub = payout_request.publisher
    return {
        "receipt_number":   f"RCP-{payout_request.request_id}",
        "receipt_date":     timezone.now().strftime("%Y-%m-%d %H:%M:%S"),
        "publisher":        {"id": pub.publisher_id, "name": pub.display_name, "email": pub.contact_email},
        "payment_details":  {
            "method":       payout_request.bank_account.get_account_type_display() if payout_request.bank_account else "N/A",
            "account":      payout_request.bank_account.masked_account_number if payout_request.bank_account else "N/A",
        },
        "amounts":          {
            "requested":    float(payout_request.requested_amount),
            "processing_fee": float(payout_request.processing_fee or 0),
            "withholding_tax": float(payout_request.withholding_tax or 0),
            "net_paid":     float(payout_request.net_amount or 0),
            "currency":     "USD",
        },
        "status":           payout_request.status,
        "reference":        payout_request.payment_reference,
        "completed_at":     str(payout_request.completed_at) if payout_request.completed_at else None,
    }


def generate_receipt_html(payout_request) -> str:
    """HTML receipt template।"""
    data = generate_payment_receipt(payout_request)
    return f"""<!DOCTYPE html><html><head><title>Payment Receipt</title></head>
<body style="font-family:Arial;max-width:600px;margin:auto;padding:20px">
<h1 style="color:#2563eb">💰 Payment Receipt</h1>
<p><strong>Receipt:</strong> {data['receipt_number']}</p>
<p><strong>Date:</strong> {data['receipt_date']}</p>
<p><strong>Publisher:</strong> {data['publisher']['name']} ({data['publisher']['id']})</p>
<h3>Payment Summary</h3>
<table width="100%"><tr><td>Requested Amount</td><td>${data['amounts']['requested']:.4f}</td></tr>
<tr><td>Processing Fee</td><td>-${data['amounts']['processing_fee']:.4f}</td></tr>
<tr><td>Withholding Tax</td><td>-${data['amounts']['withholding_tax']:.4f}</td></tr>
<tr style="font-weight:bold;color:#22c55e"><td>Net Paid</td><td>${data['amounts']['net_paid']:.4f} USD</td></tr></table>
<p><strong>Status:</strong> {data['status'].upper()}</p>
<p><em>Publisher Tools Platform | support@publishertools.io</em></p>
</body></html>"""

from typing import Dict
