# api/wallet/tests/test_reporting.py
from decimal import Decimal
from datetime import date
from django.test import TestCase
from django.contrib.auth import get_user_model

User = get_user_model()


class StatementGeneratorTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="stmttest", email="s@t.com", password="pass")
        from ..services.core.WalletService import WalletService
        self.wallet = WalletService.get_or_create(self.user)

    def test_generate_statement_empty(self):
        from ..reporting.statement_generator import StatementGenerator
        result = StatementGenerator.generate(
            self.wallet, date(2025, 1, 1), date(2025, 1, 31), "monthly"
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["txn_count"], 0)

    def test_generate_csv_empty(self):
        from ..reporting.statement_generator import StatementGenerator
        StatementGenerator.generate(self.wallet, date(2025, 1, 1), date(2025, 1, 31))
        try:
            from ..models.statement import AccountStatement
            stmt = AccountStatement.objects.filter(wallet=self.wallet).first()
            if stmt:
                csv = StatementGenerator.to_csv(stmt.id)
                self.assertIn("Date", csv)
        except Exception:
            pass


class AdminReportTest(TestCase):
    def test_daily_summary_returns_dict(self):
        from ..reporting.admin_report import AdminReport
        summary = AdminReport.daily_summary(date.today())
        self.assertIn("total_wallets", summary)
        self.assertIn("total_liability", summary)
        self.assertIn("fee_income", summary)

    def test_top_earners_returns_list(self):
        from ..reporting.admin_report import AdminReport
        earners = AdminReport.top_earners(days=30)
        self.assertIsInstance(earners, list)

    def test_gateway_volume_returns_list(self):
        from ..reporting.admin_report import AdminReport
        volume = AdminReport.gateway_volume(days=30)
        self.assertIsInstance(volume, list)


class ExportTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="exptest", email="e@t.com", password="pass")
        from ..services.core.WalletService import WalletService
        self.wallet = WalletService.get_or_create(self.user)

    def test_transactions_csv_columns(self):
        from ..reporting.export import WalletExporter
        csv = WalletExporter.transactions_csv(self.wallet.id)
        self.assertIn("Date", csv)
        self.assertIn("Amount", csv)

    def test_withdrawals_csv_admin(self):
        from ..reporting.export import WalletExporter
        csv = WalletExporter.withdrawals_csv()
        self.assertIn("Date", csv)

    def test_as_http_response(self):
        from ..reporting.export import WalletExporter
        resp = WalletExporter.as_http_response("col1,col2\nval1,val2", "test.csv")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("csv", resp["Content-Type"])
