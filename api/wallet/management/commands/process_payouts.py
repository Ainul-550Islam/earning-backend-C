# python manage.py process_payouts
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = "Process CPAlead daily auto-payouts"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Simulate without processing")

    def handle(self, *args, **options):
        from api.wallet.services.earning.PayoutService import PayoutService
        if options.get("dry_run"):
            self.stdout.write("DRY RUN — no actual payouts processed")
            return
        self.stdout.write("Processing daily payouts...")
        result = PayoutService.process_daily_payouts()
        self.stdout.write(self.style.SUCCESS(
            f"Processed={result['processed']} Failed={result['failed']} Skipped={result['skipped']}"
        ))
