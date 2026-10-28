# api/support/management/commands/auto_close_stale_tickets.py
from django.core.management.base import BaseCommand
class Command(BaseCommand):
    help = "Auto-close tickets waiting for user reply for too long"
    def add_arguments(self, p):
        p.add_argument("--days", type=int, default=7)
    def handle(self, *args, **options):
        from api.support.tasks.cleanup_tasks import auto_close_stale_tickets
        result = auto_close_stale_tickets(waiting_days=options["days"])
        self.stdout.write(self.style.SUCCESS(f"Closed: {result}"))