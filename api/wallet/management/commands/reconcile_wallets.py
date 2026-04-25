# python manage.py reconcile_wallets
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = "Run ledger reconciliation for all wallets"

    def add_arguments(self, parser):
        parser.add_argument("--wallet-id", type=int, help="Reconcile specific wallet only")
        parser.add_argument("--fix", action="store_true", help="Auto-fix small discrepancies")

    def handle(self, *args, **options):
        from api.wallet.services.ledger.ReconciliationService import ReconciliationService
        self.stdout.write("Running reconciliation...")
        if options.get("wallet_id"):
            from api.wallet.models.core import Wallet
            wallet = Wallet.objects.get(id=options["wallet_id"])
            result = ReconciliationService.run_one(wallet)
            self.stdout.write(self.style.SUCCESS(f"Result: {result}"))
        else:
            result = ReconciliationService.run_all()
            self.stdout.write(self.style.SUCCESS(
                f"Reconciled {result.get('total',0)} wallets. "
                f"OK={result.get('ok',0)} Errors={result.get('errors',0)}"
            ))
