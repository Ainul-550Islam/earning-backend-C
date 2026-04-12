"""TESTS/test_payment.py - Payment processing tests."""
from decimal import Decimal
from ..PAYMENT_PROCESSING.invoice_generator import InvoiceGenerator


class TestInvoiceGenerator:
    def test_generate_structure(self):
        class MockUser:
            id = 1; email = "test@test.com"; username = "tester"
            def get_full_name(self): return "Test User"

        inv = InvoiceGenerator.generate(MockUser(), Decimal("199.00"), "BDT", [])
        assert "invoice_number" in inv
        assert inv["total"] == "199.00"
        assert inv["currency"] == "BDT"

    def test_invoice_number_format(self):
        class MockUser:
            id = 2; email = "b@b.com"; username = "user2"
            def get_full_name(self): return "User Two"

        inv = InvoiceGenerator.generate(MockUser(), Decimal("50.00"), "USD", [],
                                         invoice_number="INV-2024-001")
        assert inv["invoice_number"] == "INV-2024-001"
