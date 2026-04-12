# api/publisher_tools/api_endpoints/payment_api.py
"""Payment API — Payout request and payment management endpoints."""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from decimal import Decimal


class PaymentAPIView(APIView):
    """Payment overview and history。"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            publisher = request.user.publisher_profile
        except Exception:
            return Response({"success": False, "message": "No publisher profile."}, status=404)

        from api.publisher_tools.payment_settlement.payment_history import (
            get_payment_history, get_payment_summary, get_lifetime_payment_stats,
        )
        from api.publisher_tools.payment_settlement.threshold_manager import get_all_thresholds
        return Response({"success": True, "data": {
            "summary":          get_payment_summary(publisher),
            "lifetime_stats":   get_lifetime_payment_stats(publisher),
            "payment_history":  get_payment_history(publisher, limit=20),
            "payment_methods":  get_all_thresholds(publisher),
        }})


class PayoutRequestAPIView(APIView):
    """Payout request creation and management。"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Payout eligibility check。"""
        try:
            publisher = request.user.publisher_profile
        except Exception:
            return Response({"success": False, "message": "No publisher profile."}, status=404)
        from api.publisher_tools.payment_settlement.payout_manager import check_payout_eligibility
        return Response({"success": True, "data": check_payout_eligibility(publisher)})

    def post(self, request):
        """New payout request submit করে।"""
        try:
            publisher = request.user.publisher_profile
        except Exception:
            return Response({"success": False, "message": "No publisher profile."}, status=404)
        amount          = request.data.get("amount")
        bank_account_id = request.data.get("bank_account_id")
        notes           = request.data.get("notes", "")
        if not amount or not bank_account_id:
            return Response({"success": False, "message": "amount and bank_account_id required."}, status=400)
        from api.publisher_tools.payment_settlement.payout_manager import process_payout_request
        result = process_payout_request(publisher, Decimal(str(amount)), bank_account_id, notes)
        status_code = 201 if result.get("success") else 400
        return Response({"success": result.get("success"), "data": result}, status=status_code)


class InvoiceDownloadAPIView(APIView):
    """Invoice HTML/PDF download。"""
    permission_classes = [IsAuthenticated]

    def get(self, request, invoice_number=None):
        from api.publisher_tools.models import PublisherInvoice
        try:
            publisher = request.user.publisher_profile
            invoice   = PublisherInvoice.objects.get(invoice_number=invoice_number, publisher=publisher)
        except Exception:
            return Response({"success": False, "message": "Invoice not found."}, status=404)
        from api.publisher_tools.payment_settlement.invoice_generator import generate_invoice_html
        html = generate_invoice_html(invoice)
        return Response({"success": True, "data": {
            "invoice_number": invoice.invoice_number,
            "html":           html,
            "download_url":   f"https://publishertools.io/api/invoices/{invoice.invoice_number}/pdf/",
        }})
