# python manage.py generate_statements
from django.core.management.base import BaseCommand
from datetime import date, timedelta

class Command(BaseCommand):
    help = "Generate monthly account statements"

    def add_arguments(self, parser):
        parser.add_argument("--month", type=int, default=None, help="Month (1-12)")
        parser.add_argument("--year",  type=int, default=None, help="Year (e.g. 2025)")
        parser.add_argument("--wallet-id", type=int, help="Specific wallet only")

    def handle(self, *args, **options):
        from api.wallet.models.core import Wallet
        from api.wallet.reporting.statement_generator import StatementGenerator

        today = date.today()
        year  = options.get("year")  or today.year
        month = options.get("month") or today.month - 1 or 12

        period_start = date(year, month, 1)
        if month == 12:
            period_end = date(year, 12, 31)
        else:
            period_end = date(year, month + 1, 1) - timedelta(days=1)

        self.stdout.write(f"Generating statements for {period_start} → {period_end}")

        if options.get("wallet_id"):
            wallets = Wallet.objects.filter(id=options["wallet_id"])
        else:
            wallets = Wallet.objects.all()

        ok = failed = 0
        for wallet in wallets:
            result = StatementGenerator.generate(wallet, period_start, period_end)
            if result["success"]: ok += 1
            else: failed += 1

        self.stdout.write(self.style.SUCCESS(f"Generated {ok} statements. Failed={failed}"))
